from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import REGISTRY

from apps.policies.models import Customer, Policy
from apps.policies.services import PolicyService


def _counter(name: str, labels: dict) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.fixture(autouse=True)
def mock_kafka():
    with patch("apps.policies.services._get_producer") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.mark.django_db
class TestPoliciesCreatedMetric:
    def test_increments_counter_on_create(self):
        customer = Customer.objects.create(
            full_name="Metrics User",
            email="metrics_create@example.com",
            dni="M1111111A",
        )
        data = {
            "customer_id": customer.id,
            "policy_type": Policy.PolicyType.LIFE,
            "premium_amount": 150.00,
            "start_date": "2025-01-01",
            "end_date": "2026-01-01",
        }
        before = _counter(
            "riskcore_policies_created_total",
            {"policy_type": Policy.PolicyType.LIFE},
        )
        PolicyService().create_policy(data)
        after = _counter(
            "riskcore_policies_created_total",
            {"policy_type": Policy.PolicyType.LIFE},
        )
        assert after == before + 1

    def test_counter_label_matches_policy_type(self):
        customer = Customer.objects.create(
            full_name="Auto Metrics",
            email="metrics_auto@example.com",
            dni="M2222222B",
        )
        data = {
            "customer_id": customer.id,
            "policy_type": Policy.PolicyType.AUTO,
            "premium_amount": 200.00,
            "start_date": "2025-01-01",
            "end_date": "2026-01-01",
        }
        life_before = _counter(
            "riskcore_policies_created_total",
            {"policy_type": Policy.PolicyType.LIFE},
        )
        PolicyService().create_policy(data)
        # LIFE label must not change when an AUTO policy is created
        assert (
            _counter(
                "riskcore_policies_created_total",
                {"policy_type": Policy.PolicyType.LIFE},
            )
            == life_before
        )


@pytest.mark.django_db
class TestPoliciesCancelledMetric:
    def test_increments_counter_on_cancel(self):
        customer = Customer.objects.create(
            full_name="Cancel Metrics",
            email="metrics_cancel@example.com",
            dni="M3333333C",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=100.00,
            start_date="2025-01-01",
            end_date="2026-01-01",
        )
        before = _counter("riskcore_policies_cancelled_total", {})
        PolicyService().cancel_policy(policy, reason="Test cancellation")
        after = _counter("riskcore_policies_cancelled_total", {})
        assert after == before + 1
