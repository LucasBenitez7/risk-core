"""
Scenario 1 — Policy Creation (write-heavy)

Target:  500 concurrent users
         p95 < 500 ms · error rate < 1%

Flow per user:
  on_start  → apply shared JWT header (token pre-fetched at test init)
  @task(3)  → create customer + create policy + verify policy
  @task(1)  → list policies (paginated)

Rate-limit note: the gateway limits api_auth to 200 req/min per zone
(shared across all locust workers on the same IP). The measurable
throughput ceiling from a single host is ~3.3 req/s total. To surpass
this, run locust in distributed mode (--master / --worker) across
multiple hosts with different IPs.
The bottleneck we want to surface here is the Django + DB stack,
not the rate limiter, so keep concurrency low enough that 429s stay < 1%.
"""

import random
import uuid
from datetime import date, timedelta

from locust import HttpUser, between, events, task

from auth_helper import register_auth_hook, shared_token

POLICY_TYPES = ["LIFE", "HEALTH", "AUTO", "HOME", "BUSINESS"]


def _random_email() -> str:
    return f"user_{uuid.uuid4().hex[:10]}@loadtest.example"


def _random_dni() -> str:
    return f"LT{random.randint(10_000_000, 99_999_999)}"


def _policy_payload(customer_id: str) -> dict:
    start = date.today()
    end = start + timedelta(days=365)
    return {
        "customer_id": customer_id,
        "policy_type": random.choice(POLICY_TYPES),
        "premium_amount": str(round(random.uniform(100, 5000), 2)),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "description": "Load test policy",
    }


@events.init.add_listener
def on_init(environment, **kwargs):
    register_auth_hook(environment)


class PolicyCreationUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.client.headers["Authorization"] = f"Bearer {shared_token()}"
        self._customer_id = self._create_customer()
        if self._customer_id:
            self._policy_id = self._create_policy(self._customer_id)
        else:
            self._policy_id = None

    def _create_customer(self) -> str | None:
        payload = {
            "full_name": f"Load Tester {uuid.uuid4().hex[:6]}",
            "email": _random_email(),
            "dni": _random_dni(),
            "phone": "+34600000000",
            "address": "Calle Test 1",
        }
        with self.client.post(
            "/api/policies/customers/",
            json=payload,
            catch_response=True,
            name="[P1] create_customer",
        ) as resp:
            if resp.status_code == 201:
                return resp.json()["id"]
            resp.failure(f"create_customer {resp.status_code}: {resp.text[:100]}")
            return None

    def _create_policy(self, customer_id: str) -> str | None:
        with self.client.post(
            "/api/policies/policies/",
            json=_policy_payload(customer_id),
            catch_response=True,
            name="[P1] create_policy",
        ) as resp:
            if resp.status_code == 201:
                return resp.json()["id"]
            resp.failure(f"create_policy {resp.status_code}: {resp.text[:100]}")
            return None

    @task(3)
    def create_customer_and_policy(self):
        customer_id = self._create_customer()
        if not customer_id:
            return
        policy_id = self._create_policy(customer_id)
        if not policy_id:
            return
        with self.client.get(
            f"/api/policies/policies/{policy_id}/",
            catch_response=True,
            name="[P1] get_policy",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"get_policy {resp.status_code}")

    @task(1)
    def list_policies(self):
        with self.client.get(
            "/api/policies/policies/?page_size=20",
            catch_response=True,
            name="[P1] list_policies",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"list_policies {resp.status_code}")
