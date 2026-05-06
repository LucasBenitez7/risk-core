import uuid

import factory
from factory.django import DjangoModelFactory

from apps.policies.models import Coverage, Customer, Policy


class CustomerFactory(DjangoModelFactory):
    class Meta:
        model = Customer

    id = factory.LazyFunction(uuid.uuid4)
    full_name = factory.Faker("name")
    email = factory.Sequence(lambda n: f"customer{n}@example.com")
    dni = factory.Sequence(lambda n: f"{n:08d}A")
    phone = factory.Faker("phone_number")
    address = factory.Faker("address")


class PolicyFactory(DjangoModelFactory):
    class Meta:
        model = Policy

    id = factory.LazyFunction(uuid.uuid4)
    customer = factory.SubFactory(CustomerFactory)
    policy_type = Policy.PolicyType.LIFE
    status = Policy.Status.ACTIVE
    premium_amount = factory.Faker(
        "pydecimal", left_digits=5, right_digits=2, positive=True
    )
    start_date = factory.Faker("past_date")
    end_date = factory.Faker("future_date")


class CoverageFactory(DjangoModelFactory):
    class Meta:
        model = Coverage

    id = factory.LazyFunction(uuid.uuid4)
    policy = factory.SubFactory(PolicyFactory)
    coverage_type = "LIFE"
    coverage_amount = factory.Faker(
        "pydecimal", left_digits=6, right_digits=2, positive=True
    )
    description = factory.Faker("sentence")
