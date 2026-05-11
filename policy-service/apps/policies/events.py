import uuid

from django.utils import timezone

from apps.outbox.models import OutboxEvent
from apps.policies.models import Policy


class PolicyEventBuilder:
    """Construye payloads de eventos. NO publica a Kafka — eso lo hace el relay."""

    @staticmethod
    def _date_to_str(value) -> str | None:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _base(event_type: str, policy: Policy) -> dict:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "occurred_at": timezone.now().isoformat(),
            "service": "policy-service",
            "data": {
                "policy_id": str(policy.id),
                "policy_number": policy.policy_number,
                "customer_id": str(policy.customer_id),
                "policy_type": policy.policy_type,
                "status": policy.status,
                "premium_amount": str(policy.premium_amount),
                "start_date": PolicyEventBuilder._date_to_str(policy.start_date),
                "end_date": PolicyEventBuilder._date_to_str(policy.end_date),
            },
        }

    @classmethod
    def build_created(cls, policy: Policy) -> dict:
        return cls._base("policy.created", policy)

    @classmethod
    def build_updated(cls, policy: Policy) -> dict:
        return cls._base("policy.updated", policy)

    @classmethod
    def build_cancelled(cls, policy: Policy) -> dict:
        payload = cls._base("policy.cancelled", policy)
        payload["data"]["cancellation_reason"] = policy.cancellation_reason
        return payload


def emit_policy_event(policy: Policy, event_type: str, payload: dict) -> None:
    """Crea un OutboxEvent. DEBE llamarse dentro de transaction.atomic()."""
    OutboxEvent.objects.create(
        aggregate_type="policy",
        aggregate_id=policy.id,
        event_type=event_type,
        topic=event_type,
        key=str(policy.id),
        payload=payload,
    )
