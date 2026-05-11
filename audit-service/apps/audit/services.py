import structlog
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import AuditEvent
from .serializers import AuditEventSerializer

logger = structlog.get_logger()


def _extract_entity(payload: dict) -> tuple[str, str]:
    data = payload.get("data", {})
    if "claim_id" in data:
        return "claim", str(data["claim_id"])
    if "policy_id" in data:
        return "policy", str(data["policy_id"])
    event_type = payload.get("event_type", "")
    if event_type.startswith("claim"):
        return "claim", ""
    return "policy", ""


class AuditService:
    def process_event(self, payload: dict, topic: str) -> AuditEvent:
        entity_type, entity_id = _extract_entity(payload)

        occurred_at = parse_datetime(payload.get("occurred_at", "")) or timezone.now()

        event = AuditEvent.objects.create(
            event_id=payload["event_id"],
            event_type=payload.get("event_type", ""),
            kafka_topic=topic,
            entity_type=entity_type,
            entity_id=entity_id or "00000000-0000-0000-0000-000000000000",
            service=payload.get("service", ""),
            occurred_at=occurred_at,
            payload=payload,
        )

        logger.info(
            "audit_event_saved",
            event_id=event.event_id,
            event_type=event.event_type,
            entity_type=entity_type,
            entity_id=str(entity_id),
        )

        self._broadcast_to_websocket(event)
        return event

    def _broadcast_to_websocket(self, event: AuditEvent) -> None:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            "audit_events",
            {
                "type": "audit.event",
                "payload": AuditEventSerializer(event).data,
            },
        )
