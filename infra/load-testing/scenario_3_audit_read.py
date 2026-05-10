"""
Scenario 3 — Audit Log Read (read-heavy)

Target:  1000 concurrent users
         p95 < 200 ms · error rate < 1%

Pre-requisite: run `make load-test-seed` BEFORE this scenario to populate
the audit-service DB with ~10k AuditEvents. With an empty audit DB the
queries are trivial and not representative; with 10k events the cursor
pagination + filtered queries exercise the indexes meaningfully.
"""

from locust import HttpUser, between, events, task

from auth_helper import register_auth_hook, shared_token


@events.init.add_listener
def on_init(environment, **kwargs):
    register_auth_hook(environment)


class AuditReadUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        self.client.headers["Authorization"] = f"Bearer {shared_token()}"

    @task(4)
    def list_audit(self):
        self.client.get("/api/audit/events/?page_size=50")

    @task(2)
    def filter_by_entity_type(self):
        self.client.get("/api/audit/events/?entity_type=policy")

    @task(2)
    def filter_by_kafka_topic(self):
        self.client.get("/api/audit/events/?kafka_topic=policy.created")

    @task(1)
    def filter_by_date(self):
        self.client.get("/api/audit/events/?from_date=2026-01-01&to_date=2026-12-31")

    @task(1)
    def filter_combined(self):
        self.client.get(
            "/api/audit/events/?entity_type=claim&kafka_topic=claim.filed&page_size=100"
        )
