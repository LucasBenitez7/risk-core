import structlog
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.claims.clients import PolicyServiceClient
from apps.claims.models import Claim, ClaimStatusHistory
from apps.core.exceptions import InvalidClaimStatusError
from apps.core.metrics import claims_filed_total, claims_status_changed_total

logger = structlog.get_logger()


def _get_producer():
    from apps.claims.events import ClaimEventProducer

    return ClaimEventProducer()


class ClaimService:
    VALID_TRANSITIONS = {
        "FILED": ["UNDER_REVIEW"],
        "UNDER_REVIEW": ["APPROVED", "REJECTED"],
        "APPROVED": ["RESOLVED"],
        "REJECTED": ["RESOLVED"],
        "RESOLVED": [],
    }

    def file_claim(self, data: dict) -> Claim:
        policy_id = data["policy_id"]
        PolicyServiceClient().verify_policy(policy_id)

        with transaction.atomic():
            claim = Claim.objects.create(
                policy_id=policy_id,
                claimant_name=data["claimant_name"],
                claimant_email=data["claimant_email"],
                incident_date=data["incident_date"],
                incident_type=data["incident_type"],
                description=data["description"],
                estimated_damage=data["estimated_damage"],
                location=data.get("location", ""),
            )
            ClaimStatusHistory.objects.create(
                claim=claim,
                from_status="",
                to_status=Claim.Status.FILED,
                notes="Siniestro reportado",
            )

        _get_producer().produce_claim_filed(claim)
        claims_filed_total.labels(incident_type=claim.incident_type).inc()
        logger.info(
            "claim_filed",
            claim_number=claim.claim_number,
            claim_id=str(claim.id),
            policy_id=str(claim.policy_id),
            incident_type=claim.incident_type,
        )
        return claim

    def transition_status(
        self,
        claim: Claim,
        new_status: str,
        notes: str = "",
        approved_amount=None,
    ) -> Claim:
        current_status = claim.status
        allowed = self.VALID_TRANSITIONS.get(current_status, [])

        if new_status not in allowed:
            raise InvalidClaimStatusError(
                claim_id=claim.id,
                current_status=current_status,
                allowed_transitions=allowed,
            )

        if new_status == Claim.Status.APPROVED and approved_amount is None:
            raise ValidationError(
                {
                    "approved_amount": (
                        "El monto aprobado es requerido para aprobar un siniestro."
                    )
                }
            )

        with transaction.atomic():
            claim = Claim.objects.select_for_update().get(pk=claim.id)
            claim.status = new_status
            update_fields = ["status"]

            if new_status == Claim.Status.APPROVED and approved_amount is not None:
                claim.approved_amount = approved_amount
                update_fields.append("approved_amount")

            update_fields.append("updated_at")
            claim.save(update_fields=update_fields)

            ClaimStatusHistory.objects.create(
                claim=claim,
                from_status=current_status,
                to_status=new_status,
                notes=notes,
            )

        _get_producer().produce_claim_status_changed(claim, current_status)
        claims_status_changed_total.labels(
            from_status=current_status, to_status=new_status
        ).inc()
        logger.info(
            "claim_status_changed",
            claim_number=claim.claim_number,
            claim_id=str(claim.id),
            from_status=current_status,
            to_status=new_status,
        )

        if new_status == Claim.Status.RESOLVED:
            _get_producer().produce_claim_resolved(claim)
            logger.info(
                "claim_resolved",
                claim_number=claim.claim_number,
                claim_id=str(claim.id),
            )

        return claim

    def get_claims_queryset(
        self,
        *,
        status: str | None = None,
        policy_id: str | None = None,
        incident_type: str | None = None,
    ):
        queryset = Claim.objects.prefetch_related("status_history", "documents").all()

        if status:
            queryset = queryset.filter(status=status)
        if policy_id:
            queryset = queryset.filter(policy_id=policy_id)
        if incident_type:
            queryset = queryset.filter(incident_type=incident_type)

        return queryset
