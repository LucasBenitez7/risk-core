import uuid
from unittest.mock import patch

import pytest

from apps.core.exceptions import (
    CustomerNotFoundError,
    InvalidPolicyStatusError,
    PolicyNotFoundError,
)
from apps.outbox.models import OutboxEvent
from apps.policies.models import Customer, Policy
from apps.policies.services import PolicyService


@pytest.mark.django_db
class TestCreatePolicy:
    def test_create_policy_success(self):
        customer = Customer.objects.create(
            full_name="Test User",
            email="create@example.com",
            dni="12345678A",
        )
        data = {
            "customer_id": customer.id,
            "policy_type": Policy.PolicyType.LIFE,
            "premium_amount": 150.00,
            "start_date": "2025-01-01",
            "end_date": "2026-01-01",
        }
        policy = PolicyService().create_policy(data)
        assert policy.customer == customer
        assert policy.policy_type == Policy.PolicyType.LIFE
        assert policy.status == Policy.Status.ACTIVE
        assert float(policy.premium_amount) == 150.00
        assert policy.policy_number.startswith("POL-")

        assert OutboxEvent.objects.filter(
            event_type="policy.created", aggregate_id=policy.id
        ).exists()

    def test_create_policy_with_coverages(self):
        customer = Customer.objects.create(
            full_name="Coverage User",
            email="coverage@example.com",
            dni="23456789B",
        )
        data = {
            "customer_id": customer.id,
            "policy_type": Policy.PolicyType.HEALTH,
            "premium_amount": 200.00,
            "start_date": "2025-02-01",
            "end_date": "2026-02-01",
        }
        coverages_data = [
            {
                "coverage_type": "LIFE",
                "coverage_amount": 100000.00,
                "description": "Life coverage",
            },
            {
                "coverage_type": "DISABILITY",
                "coverage_amount": 50000.00,
                "description": "Disability coverage",
            },
        ]
        policy = PolicyService().create_policy(data, coverages_data)
        assert policy.coverages.count() == 2
        coverage_types = {c.coverage_type for c in policy.coverages.all()}
        assert coverage_types == {"LIFE", "DISABILITY"}

    def test_create_policy_customer_not_found(self):
        data = {
            "customer_id": "00000000-0000-0000-0000-000000000000",
            "policy_type": Policy.PolicyType.AUTO,
            "premium_amount": 300.00,
            "start_date": "2025-03-01",
            "end_date": "2026-03-01",
        }
        with pytest.raises(CustomerNotFoundError) as exc_info:
            PolicyService().create_policy(data)
        assert exc_info.value.status_code == 404
        assert exc_info.value.code == "CUSTOMER_NOT_FOUND"


@pytest.mark.django_db
class TestCancelPolicy:
    def test_cancel_active_policy(self):
        customer = Customer.objects.create(
            full_name="Cancel User",
            email="cancel@example.com",
            dni="34567890C",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.HOME,
            premium_amount=350.00,
            start_date="2025-04-01",
            end_date="2026-04-01",
        )
        result = PolicyService().cancel_policy(policy, reason="Client request")
        assert result.status == Policy.Status.CANCELLED
        assert result.cancellation_reason == "Client request"

        assert OutboxEvent.objects.filter(
            event_type="policy.cancelled", aggregate_id=policy.id
        ).exists()

    def test_cancel_already_cancelled_policy(self):
        customer = Customer.objects.create(
            full_name="Double Cancel",
            email="dcancel@example.com",
            dni="45678901D",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=100.00,
            start_date="2025-05-01",
            end_date="2026-05-01",
            status=Policy.Status.CANCELLED,
        )
        with pytest.raises(InvalidPolicyStatusError) as exc_info:
            PolicyService().cancel_policy(policy, reason="Second attempt")
        assert exc_info.value.status_code == 400
        assert exc_info.value.code == "INVALID_POLICY_STATUS"

    def test_cancel_expired_policy(self):
        customer = Customer.objects.create(
            full_name="Expired User",
            email="expired@example.com",
            dni="56789012E",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.AUTO,
            premium_amount=250.00,
            start_date="2024-01-01",
            end_date="2024-12-31",
            status=Policy.Status.EXPIRED,
        )
        with pytest.raises(InvalidPolicyStatusError):
            PolicyService().cancel_policy(policy, reason="Should fail")


@pytest.mark.django_db
class TestUpdatePolicy:
    def test_update_active_policy(self):
        customer = Customer.objects.create(
            full_name="Update User",
            email="update@example.com",
            dni="67890123F",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=100.00,
            start_date="2025-06-01",
            end_date="2026-06-01",
        )
        data = {"premium_amount": 200.00, "description": "Updated policy"}
        result = PolicyService().update_policy(policy, data)
        assert float(result.premium_amount) == 200.00
        assert result.description == "Updated policy"

        assert OutboxEvent.objects.filter(
            event_type="policy.updated", aggregate_id=policy.id
        ).exists()

    def test_update_cancelled_policy_fails(self):
        customer = Customer.objects.create(
            full_name="Cancelled Update",
            email="cupdate@example.com",
            dni="78901234G",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.HOME,
            premium_amount=350.00,
            start_date="2025-07-01",
            end_date="2026-07-01",
            status=Policy.Status.CANCELLED,
        )
        data = {"premium_amount": 500.00}
        with pytest.raises(InvalidPolicyStatusError) as exc_info:
            PolicyService().update_policy(policy, data)
        assert exc_info.value.code == "INVALID_POLICY_STATUS"

    def test_update_expired_policy_fails(self):
        customer = Customer.objects.create(
            full_name="Expired Update",
            email="eupdate@example.com",
            dni="89012345H",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.BUSINESS,
            premium_amount=500.00,
            start_date="2024-01-01",
            end_date="2024-12-31",
            status=Policy.Status.EXPIRED,
        )
        data = {"premium_amount": 600.00}
        with pytest.raises(InvalidPolicyStatusError):
            PolicyService().update_policy(policy, data)


@pytest.mark.django_db
class TestVerifyPolicy:
    def test_verify_active_policy(self):
        customer = Customer.objects.create(
            full_name="Verify User",
            email="verify@example.com",
            dni="90123456I",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=150.00,
            start_date="2025-08-01",
            end_date="2026-08-01",
        )
        result = PolicyService().verify_policy(policy.id)
        assert result["is_valid"] is True
        assert result["status"] == Policy.Status.ACTIVE
        assert result["policy_id"] == str(policy.id)
        assert result["customer_id"] == str(customer.id)

    def test_verify_cancelled_policy(self):
        customer = Customer.objects.create(
            full_name="Cancelled Verify",
            email="cverify@example.com",
            dni="01234567J",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.HOME,
            premium_amount=250.00,
            start_date="2025-09-01",
            end_date="2026-09-01",
            status=Policy.Status.CANCELLED,
        )
        result = PolicyService().verify_policy(policy.id)
        assert result["is_valid"] is False
        assert result["status"] == Policy.Status.CANCELLED

    def test_verify_nonexistent_policy(self):
        with pytest.raises(PolicyNotFoundError) as exc_info:
            PolicyService().verify_policy(
                uuid.UUID("00000000-0000-0000-0000-000000000000")
            )
        assert exc_info.value.status_code == 404
        assert exc_info.value.code == "POLICY_NOT_FOUND"


@pytest.mark.django_db
class TestGetPoliciesQueryset:
    def test_filter_by_status(self):
        customer = Customer.objects.create(
            full_name="Filter User",
            email="filter@example.com",
            dni="12345000K",
        )
        Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=100.00,
            start_date="2025-01-01",
            end_date="2026-01-01",
            status=Policy.Status.ACTIVE,
        )
        Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.AUTO,
            premium_amount=200.00,
            start_date="2025-02-01",
            end_date="2026-02-01",
            status=Policy.Status.CANCELLED,
        )
        qs = PolicyService().get_policies_queryset(status=Policy.Status.ACTIVE)
        assert qs.count() == 1
        assert qs.first().status == Policy.Status.ACTIVE

    def test_filter_by_policy_type(self):
        customer = Customer.objects.create(
            full_name="Type User",
            email="type@example.com",
            dni="23456001L",
        )
        Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=100.00,
            start_date="2025-01-01",
            end_date="2026-01-01",
        )
        Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.HOME,
            premium_amount=200.00,
            start_date="2025-02-01",
            end_date="2026-02-01",
        )
        qs = PolicyService().get_policies_queryset(policy_type=Policy.PolicyType.LIFE)
        assert qs.count() == 1

    def test_filter_by_customer(self):
        customer1 = Customer.objects.create(
            full_name="C1",
            email="c1@example.com",
            dni="34567002M",
        )
        customer2 = Customer.objects.create(
            full_name="C2",
            email="c2@example.com",
            dni="45678003N",
        )
        Policy.objects.create(
            customer=customer1,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=100.00,
            start_date="2025-01-01",
            end_date="2026-01-01",
        )
        Policy.objects.create(
            customer=customer2,
            policy_type=Policy.PolicyType.AUTO,
            premium_amount=200.00,
            start_date="2025-02-01",
            end_date="2026-02-01",
        )
        qs = PolicyService().get_policies_queryset(customer_id=customer1.id)
        assert qs.count() == 1
        assert qs.first().customer == customer1

    def test_filter_by_date_range(self):
        customer = Customer.objects.create(
            full_name="Date User",
            email="date@example.com",
            dni="56789004O",
        )
        Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=100.00,
            start_date="2025-01-01",
            end_date="2026-01-01",
        )
        Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.HOME,
            premium_amount=200.00,
            start_date="2025-07-01",
            end_date="2026-07-01",
        )
        qs = PolicyService().get_policies_queryset(
            start_date_from="2025-06-01",
            start_date_to="2025-12-31",
        )
        assert qs.count() == 1
        assert qs.first().start_date.isoformat() == "2025-07-01"


@pytest.mark.django_db
class TestOutboxIntegration:
    def test_rollback_does_not_create_outbox_event(self):
        customer = Customer.objects.create(
            full_name="Rollback User",
            email="rollback@example.com",
            dni="99999999Z",
        )
        data = {
            "customer_id": customer.id,
            "policy_type": Policy.PolicyType.LIFE,
            "premium_amount": 150.00,
            "start_date": "2025-01-01",
            "end_date": "2026-01-01",
        }

        with (
            patch(
                "apps.policies.services.emit_policy_event",
                side_effect=Exception("Simulated failure"),
            ),
            pytest.raises(Exception, match="Simulated failure"),
        ):
            PolicyService().create_policy(data)

        assert Policy.objects.count() == 0
        assert OutboxEvent.objects.count() == 0


@pytest.mark.django_db
class TestPolicyMetricsService:
    def test_empty_db_returns_zeros(self):
        result = PolicyService().get_metrics()
        assert result["active_policies"] == 0
        assert result["policies_today"] == 0
        assert result["total_premium_active"] == "0.00"
        assert result["policies_by_type"] == {
            "LIFE": 0,
            "HEALTH": 0,
            "AUTO": 0,
            "HOME": 0,
            "BUSINESS": 0,
        }

    def test_counts_only_active_for_totals(self):
        customer = Customer.objects.create(
            full_name="Test", email="m1@test.com", dni="11111111A"
        )
        Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount="200.00",
            start_date="2025-01-01",
            end_date="2026-01-01",
            status=Policy.Status.ACTIVE,
        )
        Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.AUTO,
            premium_amount="300.00",
            start_date="2025-01-01",
            end_date="2026-01-01",
            status=Policy.Status.CANCELLED,
        )
        result = PolicyService().get_metrics()
        assert result["active_policies"] == 1
        assert result["total_premium_active"] == "200.00"
        assert result["policies_by_type"]["LIFE"] == 1
        assert result["policies_by_type"]["AUTO"] == 0

    def test_policies_by_type_distribution(self):
        customer = Customer.objects.create(
            full_name="Test2", email="m2@test.com", dni="22222222A"
        )
        for policy_type in [
            Policy.PolicyType.LIFE,
            Policy.PolicyType.LIFE,
            Policy.PolicyType.HOME,
        ]:
            Policy.objects.create(
                customer=customer,
                policy_type=policy_type,
                premium_amount="100.00",
                start_date="2025-01-01",
                end_date="2026-01-01",
            )
        result = PolicyService().get_metrics()
        assert result["policies_by_type"]["LIFE"] == 2
        assert result["policies_by_type"]["HOME"] == 1
        assert result["policies_by_type"]["AUTO"] == 0
