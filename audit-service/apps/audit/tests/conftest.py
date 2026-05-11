import uuid

import factory
import pytest
from django.utils import timezone

from apps.audit.models import AuditEvent


class AuditEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AuditEvent

    event_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    event_type = "policy.created"
    kafka_topic = "policy.created"
    entity_type = "policy"
    entity_id = factory.LazyFunction(uuid.uuid4)
    service = "policy-service"
    occurred_at = factory.LazyFunction(timezone.now)
    payload = factory.LazyAttribute(
        lambda o: {
            "event_id": o.event_id,
            "event_type": o.event_type,
            "occurred_at": timezone.now().isoformat(),
            "service": o.service,
            "data": {"policy_id": str(o.entity_id)},
        }
    )


@pytest.fixture
def audit_event(db):
    return AuditEventFactory()


@pytest.fixture
def policy_payload():
    policy_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    return {
        "event_id": event_id,
        "event_type": "policy.created",
        "occurred_at": "2026-01-15T10:00:00Z",
        "service": "policy-service",
        "data": {
            "policy_id": policy_id,
            "customer_email": "cliente@test.com",
        },
    }


@pytest.fixture
def claim_payload():
    claim_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    return {
        "event_id": event_id,
        "event_type": "claim.filed",
        "occurred_at": "2026-01-15T11:00:00Z",
        "service": "claims-service",
        "data": {
            "claim_id": claim_id,
            "claimant_email": "cliente@test.com",
        },
    }
