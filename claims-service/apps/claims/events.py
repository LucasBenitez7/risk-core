import uuid

from django.utils import timezone

from apps.claims.models import Claim
from apps.outbox.models import OutboxEvent


class ClaimEventBuilder:
    """Construye payloads de eventos. NO publica a Kafka — eso lo hace el relay."""

    @staticmethod
    def _base_data(claim: Claim) -> dict:
        return {
            "claim_id": str(claim.id),
            "claim_number": claim.claim_number,
            "policy_id": str(claim.policy_id),
            "status": claim.status,
            "incident_type": claim.incident_type,
            "claimant_email": claim.claimant_email,
        }

    @classmethod
    def build_filed(cls, claim: Claim) -> dict:
        data = cls._base_data(claim)
        data["estimated_damage"] = str(claim.estimated_damage)
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "claim.filed",
            "occurred_at": timezone.now().isoformat(),
            "service": "claims-service",
            "data": data,
        }

    @classmethod
    def build_status_changed(
        cls, claim: Claim, from_status: str, to_status: str
    ) -> dict:
        data = cls._base_data(claim)
        data["from_status"] = from_status
        data["to_status"] = to_status
        if claim.approved_amount is not None:
            data["approved_amount"] = str(claim.approved_amount)
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "claim.status_changed",
            "occurred_at": timezone.now().isoformat(),
            "service": "claims-service",
            "data": data,
        }

    @classmethod
    def build_resolved(cls, claim: Claim) -> dict:
        data = cls._base_data(claim)
        if claim.approved_amount is not None:
            data["approved_amount"] = str(claim.approved_amount)
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "claim.resolved",
            "occurred_at": timezone.now().isoformat(),
            "service": "claims-service",
            "data": data,
        }


def emit_claim_event(claim: Claim, event_type: str, payload: dict) -> None:
    """Crea un OutboxEvent. DEBE llamarse dentro de transaction.atomic()."""
    OutboxEvent.objects.create(
        aggregate_type="claim",
        aggregate_id=claim.id,
        event_type=event_type,
        topic=event_type,
        key=str(claim.id),
        payload=payload,
    )
