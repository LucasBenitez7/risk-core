"""
Scenario 2 — Claims Filing (inter-service write-heavy)

Target:  300 concurrent users
         p95 < 800 ms · error rate < 1%
         (higher budget than scenario 1: includes synchronous HTTP
          claims-service → policy-service to verify policy status)

Setup model:
  Pre-test: ONE setup phase (events.test_start) creates 50 ACTIVE policies
            in policy-service via the gateway. These IDs are stored in a
            module-level list shared by all virtual users.
  Per-user on_start: just apply the JWT header and pick a random policy_id
                     from the shared list.

Why this matters: with 300 users each running their own setup in on_start,
the first 30 seconds of the test would saturate policy-service with
customer/policy creation, distorting the "claims filing under load" metric.
The shared pre-test setup decouples the setup cost from the measured workload.

Per-user tasks:
  @task(2)  → POST new claim against a shared policy_id (this is the
              measured inter-service call)
  @task(1)  → PATCH transition FILED → UNDER_REVIEW on a filed claim
  @task(1)  → list claims
"""

import random
import uuid
from datetime import date, timedelta

import requests as _requests
from locust import HttpUser, between, events, task

from auth_helper import register_auth_hook, shared_token

INCIDENT_TYPES = ["ACCIDENTE", "ROBO", "INCENDIO", "INUNDACION", "OTRO"]
POLICY_TYPES = ["LIFE", "HEALTH", "AUTO", "HOME", "BUSINESS"]

SHARED_POLICY_IDS: list[str] = []
SETUP_POLICY_COUNT = 50


def _random_email() -> str:
    return f"claim_{uuid.uuid4().hex[:10]}@loadtest.example"


def _random_dni() -> str:
    return f"CL{random.randint(10_000_000, 99_999_999)}"


@events.init.add_listener
def on_init(environment, **kwargs):
    register_auth_hook(environment)


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Pre-create 50 policies for the whole test to share. Runs once before users spawn."""
    host = environment.host or "http://localhost:8080"
    token = shared_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Host": "localhost",
        "Content-Type": "application/json",
    }
    start = date.today()
    end = start + timedelta(days=365)

    for _ in range(SETUP_POLICY_COUNT):
        cust_payload = {
            "full_name": f"Setup Customer {uuid.uuid4().hex[:6]}",
            "email": _random_email(),
            "dni": _random_dni(),
            "phone": "+34600000001",
            "address": "Av. Setup 1",
        }
        r = _requests.post(
            f"{host}/api/policies/customers/",
            json=cust_payload,
            headers=headers,
            timeout=10,
        )
        if r.status_code != 201:
            continue
        customer_id = r.json()["id"]

        pol_payload = {
            "customer": customer_id,
            "policy_type": random.choice(POLICY_TYPES),
            "premium_amount": str(round(random.uniform(200, 3000), 2)),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "description": "Claims load test setup policy",
        }
        r = _requests.post(
            f"{host}/api/policies/policies/",
            json=pol_payload,
            headers=headers,
            timeout=10,
        )
        if r.status_code == 201:
            SHARED_POLICY_IDS.append(r.json()["id"])

    if not SHARED_POLICY_IDS:
        raise SystemExit("scenario_2 setup failed: no policies created")


class ClaimsFilingUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.client.headers["Authorization"] = f"Bearer {shared_token()}"
        self._policy_id = random.choice(SHARED_POLICY_IDS)
        self._filed_claim_ids: list[str] = []

    @task(2)
    def file_claim(self):
        incident_date = (
            date.today() - timedelta(days=random.randint(1, 30))
        ).isoformat()
        payload = {
            "policy_id": self._policy_id,
            "claimant_name": f"Claimant {uuid.uuid4().hex[:6]}",
            "claimant_email": _random_email(),
            "incident_date": incident_date,
            "incident_type": random.choice(INCIDENT_TYPES),
            "description": "Load test incident description",
            "estimated_damage": str(round(random.uniform(500, 20000), 2)),
            "location": "Madrid, España",
        }
        with self.client.post(
            "/api/claims/claims/",
            json=payload,
            catch_response=True,
            name="[P2] file_claim",
        ) as resp:
            if resp.status_code == 201:
                claim_id = resp.json().get("id")
                if claim_id:
                    self._filed_claim_ids.append(claim_id)
                    if len(self._filed_claim_ids) > 20:
                        self._filed_claim_ids.pop(0)
            else:
                resp.failure(f"file_claim {resp.status_code}: {resp.text[:100]}")

    @task(1)
    def transition_claim(self):
        if not self._filed_claim_ids:
            return
        claim_id = self._filed_claim_ids.pop(0)
        with self.client.post(
            f"/api/claims/claims/{claim_id}/transition/",
            json={"status": "UNDER_REVIEW"},
            catch_response=True,
            name="[P2] transition_claim",
        ) as resp:
            if resp.status_code not in (200, 400):
                resp.failure(f"transition_claim {resp.status_code}: {resp.text[:100]}")

    @task(1)
    def list_claims(self):
        with self.client.get(
            "/api/claims/claims/?page_size=20",
            catch_response=True,
            name="[P2] list_claims",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"list_claims {resp.status_code}")
