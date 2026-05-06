import uuid
from unittest.mock import MagicMock, patch

import pytest

from apps.audit.models import AuditEvent
from apps.audit.services import AuditService, _extract_entity


@pytest.mark.django_db
def test_process_event_policy_created(policy_payload):
    with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
        event = AuditService().process_event(policy_payload, topic="policy.created")

    assert event.pk is not None
    assert event.event_id == policy_payload["event_id"]
    assert event.event_type == "policy.created"
    assert event.kafka_topic == "policy.created"
    assert event.entity_type == "policy"
    assert str(event.entity_id) == policy_payload["data"]["policy_id"]
    assert event.service == "policy-service"
    assert event.payload == policy_payload


@pytest.mark.django_db
def test_process_event_claim_filed(claim_payload):
    with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
        event = AuditService().process_event(claim_payload, topic="claim.filed")

    assert event.entity_type == "claim"
    assert str(event.entity_id) == claim_payload["data"]["claim_id"]
    assert event.event_type == "claim.filed"


@pytest.mark.django_db
def test_process_event_duplicate_raises_integrity_error(policy_payload):
    from django.db import IntegrityError

    with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
        AuditService().process_event(policy_payload, topic="policy.created")

    with (
        pytest.raises(IntegrityError),
        patch("apps.audit.services.AuditService._broadcast_to_websocket"),
    ):
        AuditService().process_event(policy_payload, topic="policy.created")


@pytest.mark.django_db
def test_process_event_saves_to_db(policy_payload):
    with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
        AuditService().process_event(policy_payload, topic="policy.created")

    assert AuditEvent.objects.filter(event_id=policy_payload["event_id"]).exists()


@pytest.mark.django_db
def test_process_event_invalid_occurred_at_falls_back_to_now(policy_payload):
    policy_payload["occurred_at"] = "not-a-date"
    with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
        event = AuditService().process_event(policy_payload, topic="policy.created")

    assert event.occurred_at is not None


@pytest.mark.django_db
def test_broadcast_to_websocket_is_called(policy_payload):
    with patch("apps.audit.services.async_to_sync") as mock_async_to_sync:
        mock_group_send = MagicMock()
        mock_async_to_sync.return_value = mock_group_send
        AuditService().process_event(policy_payload, topic="policy.created")

    mock_group_send.assert_called_once()
    call_args = mock_group_send.call_args[0]
    assert call_args[0] == "audit_events"
    assert call_args[1]["type"] == "audit.event"


def test_extract_entity_claim():
    claim_id = str(uuid.uuid4())
    entity_type, entity_id = _extract_entity(
        {"event_type": "claim.filed", "data": {"claim_id": claim_id}}
    )
    assert entity_type == "claim"
    assert entity_id == claim_id


def test_extract_entity_policy():
    policy_id = str(uuid.uuid4())
    entity_type, entity_id = _extract_entity(
        {"event_type": "policy.created", "data": {"policy_id": policy_id}}
    )
    assert entity_type == "policy"
    assert entity_id == policy_id


def test_extract_entity_fallback_claim_by_event_type():
    entity_type, entity_id = _extract_entity(
        {"event_type": "claim.status_changed", "data": {}}
    )
    assert entity_type == "claim"
    assert entity_id == ""


def test_extract_entity_fallback_policy_by_event_type():
    entity_type, entity_id = _extract_entity(
        {"event_type": "policy.updated", "data": {}}
    )
    assert entity_type == "policy"
    assert entity_id == ""
