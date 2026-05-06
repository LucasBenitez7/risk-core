import uuid

import factory
from factory.django import DjangoModelFactory

from apps.claims.models import Claim, ClaimStatusHistory


class ClaimFactory(DjangoModelFactory):
    class Meta:
        model = Claim

    id = factory.LazyFunction(uuid.uuid4)
    policy_id = factory.LazyFunction(uuid.uuid4)
    claimant_name = factory.Faker("name")
    claimant_email = factory.Sequence(lambda n: f"claimant{n}@example.com")
    incident_date = factory.Faker("past_date")
    incident_type = Claim.IncidentType.ACCIDENTE
    description = factory.Faker("sentence")
    estimated_damage = factory.Faker(
        "pydecimal", left_digits=5, right_digits=2, positive=True
    )
    location = factory.Faker("city")
    status = Claim.Status.FILED


class ClaimStatusHistoryFactory(DjangoModelFactory):
    class Meta:
        model = ClaimStatusHistory

    id = factory.LazyFunction(uuid.uuid4)
    claim = factory.SubFactory(ClaimFactory)
    from_status = Claim.Status.FILED
    to_status = Claim.Status.UNDER_REVIEW
    notes = factory.Faker("sentence")
