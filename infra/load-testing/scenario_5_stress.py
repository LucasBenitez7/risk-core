"""
Scenario 5 — Stress Test (find the breaking point)

Ramps up users in steps of 100 every 60 seconds until the error rate
exceeds 10% or the runner explicitly stops.

Goal: identify the maximum sustainable load and the component that
breaks first (DB pool? Kafka backpressure? Django workers? Gateway?).

Run headless:
  make load-test SCENARIO=5

The test stops automatically when fail_ratio > 0.10.
Check the HTML report and Grafana dashboard to find where the
system started degrading (latency climb usually precedes error spike).
"""

from locust import LoadTestShape, between

from scenario_1_policy_creation import PolicyCreationUser


class StressUser(PolicyCreationUser):
    """Same write workload as scenario 1; we want DB/Django under stress."""

    wait_time = between(0.3, 1.0)


class StressShape(LoadTestShape):
    """
    Stepped ramp: adds 50 users every 60 seconds.
    Stops when the global fail ratio exceeds 10%.

    Step size of 50 (down from 100) gives finer resolution around the
    breaking point, which matters when the bottleneck is DB pool / Django
    workers rather than the rate limiter.

    Max ceiling: 5000 users (safety guard — stops even if error rate
    never hits 10%, preventing runaway resource consumption).
    """

    step_users = 50
    step_duration = 60  # seconds per step
    max_users = 5000
    fail_threshold = 0.10

    def tick(self):
        # Stop if error rate is too high
        runner = self.runner
        if runner and runner.stats.total.fail_ratio > self.fail_threshold:
            return None

        run_time = self.get_run_time()
        current_step = int(run_time // self.step_duration) + 1
        target_users = min(current_step * self.step_users, self.max_users)

        if target_users >= self.max_users:
            return None

        return target_users, self.step_users
