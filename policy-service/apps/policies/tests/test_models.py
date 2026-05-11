import uuid

import pytest
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError

from apps.policies.models import Customer, Policy


@pytest.mark.django_db
class TestPolicyNumberGeneration:
    def test_policy_number_generated_on_create(self):
        customer = Customer.objects.create(
            full_name="Test User",
            email="test@example.com",
            dni="12345678A",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=150.00,
            start_date="2025-01-01",
            end_date="2026-01-01",
        )
        assert policy.policy_number.startswith("POL-")
        year_part = policy.policy_number.split("-")[1]
        assert len(year_part) == 4
        num_part = policy.policy_number.split("-")[2]
        assert len(num_part) == 6
        assert num_part.isdigit()

    def test_policy_number_increments(self):
        customer = Customer.objects.create(
            full_name="Test User",
            email="test2@example.com",
            dni="87654321B",
        )
        policy1 = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.HEALTH,
            premium_amount=200.00,
            start_date="2025-02-01",
            end_date="2026-02-01",
        )
        policy2 = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.AUTO,
            premium_amount=300.00,
            start_date="2025-03-01",
            end_date="2026-03-01",
        )
        num1 = int(policy1.policy_number.split("-")[2])
        num2 = int(policy2.policy_number.split("-")[2])
        assert num2 == num1 + 1


@pytest.mark.django_db
class TestCustomerModel:
    def test_customer_has_uuid_pk(self):
        customer = Customer.objects.create(
            full_name="UUID User",
            email="uuid@example.com",
            dni="11111111X",
        )
        assert isinstance(customer.id, uuid.UUID)

    def test_customer_email_unique(self):
        Customer.objects.create(
            full_name="User A",
            email="dupe@example.com",
            dni="22222222Y",
        )
        with pytest.raises(IntegrityError):
            Customer.objects.create(
                full_name="User B",
                email="dupe@example.com",
                dni="33333333Z",
            )

    def test_customer_dni_unique(self):
        Customer.objects.create(
            full_name="User A",
            email="a@example.com",
            dni="44444444W",
        )
        with pytest.raises(IntegrityError):
            Customer.objects.create(
                full_name="User B",
                email="b@example.com",
                dni="44444444W",
            )


@pytest.mark.django_db
class TestPolicyModel:
    def test_policy_has_uuid_pk(self):
        customer = Customer.objects.create(
            full_name="Policy User",
            email="policy@example.com",
            dni="55555555V",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.HOME,
            premium_amount=350.00,
            start_date="2025-04-01",
            end_date="2026-04-01",
        )
        assert isinstance(policy.id, uuid.UUID)

    def test_policy_status_default_active(self):
        customer = Customer.objects.create(
            full_name="Status User",
            email="status@example.com",
            dni="66666666U",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.BUSINESS,
            premium_amount=500.00,
            start_date="2025-05-01",
            end_date="2026-05-01",
        )
        assert policy.status == Policy.Status.ACTIVE

    def test_policy_customer_protect(self):
        customer = Customer.objects.create(
            full_name="FK User",
            email="fk@example.com",
            dni="77777777T",
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.AUTO,
            premium_amount=120.00,
            start_date="2025-06-01",
            end_date="2026-06-01",
        )
        with pytest.raises(ProtectedError):
            customer.delete()
        assert Policy.objects.filter(pk=policy.pk).exists()
