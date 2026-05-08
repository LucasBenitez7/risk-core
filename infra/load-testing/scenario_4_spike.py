"""
Scenario 4 — Spike Test

Simulates a sudden traffic surge: 0 → 1000 users in 30 seconds,
sustained for 2 minutes, then ramp-down to 0.

What to observe in Grafana during this test:
  - Latency spike (p95/p99) during ramp-up and recovery time
  - Kafka consumer lag per topic (policy.created, claim.filed)
    rising during the spike and draining after ramp-down
  - DB connection pool saturation (if exhausted, 500s appear)
  - Gateway 429s if the rate-limit zone gets saturated

Run headless:
  make load-test SCENARIO=4

Distributed mode (bypass single-IP rate limit ceiling):
  locust -f scenario_4_spike.py --master
  locust -f scenario_4_spike.py --worker --master-host=<master_ip>
"""

from locust import LoadTestShape, between

from scenario_1_policy_creation import PolicyCreationUser


class SpikeUser(PolicyCreationUser):
    """Reuses PolicyCreationUser tasks — spike measures the same write flow."""

    wait_time = between(0.5, 1.5)


class SpikeShape(LoadTestShape):
    """
    Stage-based ramp:
      0  –  30 s  : ramp up 0 → 1000 (spawn_rate=35)
      30 – 150 s  : hold at 1000
      150 – 180 s : ramp down to 0  (spawn_rate=35)
    """

    stages = [
        {"duration": 30, "users": 1000, "spawn_rate": 35},
        {"duration": 150, "users": 1000, "spawn_rate": 0},
        {"duration": 180, "users": 0, "spawn_rate": 35},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None
