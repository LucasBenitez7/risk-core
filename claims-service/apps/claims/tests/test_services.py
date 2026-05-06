import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.exceptions import ValidationError

from apps.claims.models import Claim, ClaimStatusHistory
from apps.claims.services import ClaimService
from apps.core.exceptions import (
    InvalidClaimStatusError,
    PolicyInactiveError,
    PolicyServiceUnavailableError,
)


@pytest.fixture(autouse=True)
def mock_kafka():
    with patch("apps.claims.services._get_producer") as mock:
        mock.return_value = MagicMock()
        yield mock


MOCK_VERIFY = "apps.claims.clients.PolicyServiceClient.verify_policy"


@pytest.mark.django_db
class TestFileClaim:
    def test_file_claim_success(self):
        policy_id = str(uuid.uuid4())
        with patch(MOCK_VERIFY) as mock_verify:
            mock_verify.return_value = {
                "status": "ACTIVE",
                "is_valid": True,
                "customer_id": str(uuid.uuid4()),
                "policy_type": "AUTO",
            }

            data = {
                "policy_id": policy_id,
                "claimant_name": "Ana Garcia",
                "claimant_email": "ana@test.com",
                "incident_date": "2026-03-15",
                "incident_type": Claim.IncidentType.ACCIDENTE,
                "description": "Accidente en la A-6",
                "estimated_damage": Decimal("5000.00"),
            }
            claim = ClaimService().file_claim(data)

        assert claim.claim_number.startswith("CLM-")
        assert claim.status == Claim.Status.FILED
        assert str(claim.policy_id) == policy_id
        assert claim.claimant_name == "Ana Garcia"

        history = claim.status_history.first()
        assert history.from_status == ""
        assert history.to_status == Claim.Status.FILED
        assert history.notes == "Siniestro reportado"

    def test_file_claim_with_location(self):
        policy_id = str(uuid.uuid4())
        with patch(MOCK_VERIFY) as mock_verify:
            mock_verify.return_value = {
                "status": "ACTIVE",
                "is_valid": True,
            }

            data = {
                "policy_id": policy_id,
                "claimant_name": "Carlos",
                "claimant_email": "carlos@test.com",
                "incident_date": "2026-04-10",
                "incident_type": Claim.IncidentType.ROBO,
                "description": "Robo en vivienda",
                "estimated_damage": Decimal("2000.00"),
                "location": "Madrid",
            }
            claim = ClaimService().file_claim(data)

        assert claim.location == "Madrid"

    def test_file_claim_policy_inactive(self):
        policy_id = str(uuid.uuid4())
        with patch(MOCK_VERIFY) as mock_verify:
            mock_verify.side_effect = PolicyInactiveError(
                policy_id=policy_id, policy_status="CANCELLED"
            )

            data = {
                "policy_id": policy_id,
                "claimant_name": "Test",
                "claimant_email": "test@test.com",
                "incident_date": "2026-01-01",
                "incident_type": Claim.IncidentType.ACCIDENTE,
                "description": "Test",
                "estimated_damage": Decimal("100.00"),
            }

            with pytest.raises(PolicyInactiveError) as exc_info:
                ClaimService().file_claim(data)

        assert exc_info.value.status_code == 400
        assert exc_info.value.code == "POLICY_INACTIVE"
        assert exc_info.value.details["policy_status"] == "CANCELLED"

        assert Claim.objects.count() == 0

    def test_file_claim_policy_service_unavailable(self):
        policy_id = str(uuid.uuid4())
        with patch(MOCK_VERIFY) as mock_verify:
            mock_verify.side_effect = PolicyServiceUnavailableError(policy_id=policy_id)

            data = {
                "policy_id": policy_id,
                "claimant_name": "Test",
                "claimant_email": "test@test.com",
                "incident_date": "2026-01-01",
                "incident_type": Claim.IncidentType.ACCIDENTE,
                "description": "Test",
                "estimated_damage": Decimal("100.00"),
            }

            with pytest.raises(PolicyServiceUnavailableError) as exc_info:
                ClaimService().file_claim(data)

        assert exc_info.value.status_code == 503
        assert exc_info.value.code == "POLICY_SERVICE_UNAVAILABLE"
        assert Claim.objects.count() == 0


@pytest.mark.django_db
class TestTransitionStatus:
    def _create_filed_claim(self):
        claim = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="Test",
            claimant_email="test@test.com",
            incident_date="2026-01-01",
            incident_type=Claim.IncidentType.ACCIDENTE,
            description="Test",
            estimated_damage=Decimal("1000.00"),
        )
        ClaimStatusHistory.objects.create(
            claim=claim,
            from_status="",
            to_status=Claim.Status.FILED,
            notes="Siniestro reportado",
        )
        return claim

    def test_transition_filed_to_under_review(self):
        claim = self._create_filed_claim()
        result = ClaimService().transition_status(
            claim, "UNDER_REVIEW", notes="Asignado a perito"
        )
        assert result.status == Claim.Status.UNDER_REVIEW
        assert result.status_history.count() == 2
        latest = result.status_history.order_by("-changed_at").first()
        assert latest.from_status == Claim.Status.FILED
        assert latest.to_status == Claim.Status.UNDER_REVIEW
        assert latest.notes == "Asignado a perito"

    def test_transition_to_approved_with_amount(self):
        claim = self._create_filed_claim()
        claim = ClaimService().transition_status(claim, "UNDER_REVIEW")
        result = ClaimService().transition_status(
            claim,
            "APPROVED",
            notes="Daños confirmados",
            approved_amount=Decimal("4500.00"),
        )
        assert result.status == Claim.Status.APPROVED
        assert result.approved_amount == Decimal("4500.00")

    def test_transition_to_approved_without_amount_raises(self):
        claim = self._create_filed_claim()
        claim = ClaimService().transition_status(claim, "UNDER_REVIEW")
        with pytest.raises(ValidationError) as exc_info:
            ClaimService().transition_status(claim, "APPROVED", notes="Sin monto")
        assert "approved_amount" in exc_info.value.detail

    def test_transition_to_rejected(self):
        claim = self._create_filed_claim()
        claim = ClaimService().transition_status(claim, "UNDER_REVIEW")
        result = ClaimService().transition_status(claim, "REJECTED", notes="No procede")
        assert result.status == Claim.Status.REJECTED

    def test_transition_rejected_to_resolved(self):
        claim = self._create_filed_claim()
        claim = ClaimService().transition_status(claim, "UNDER_REVIEW")
        claim = ClaimService().transition_status(claim, "REJECTED", notes="No procede")
        result = ClaimService().transition_status(claim, "RESOLVED")
        assert result.status == Claim.Status.RESOLVED

    def test_transition_invalid(self):
        claim = self._create_filed_claim()
        with pytest.raises(InvalidClaimStatusError) as exc_info:
            ClaimService().transition_status(claim, "APPROVED")
        assert exc_info.value.status_code == 400
        assert exc_info.value.code == "INVALID_CLAIM_STATUS"
        assert "UNDER_REVIEW" in exc_info.value.details["allowed_transitions"]

    def test_transition_from_resolved_not_allowed(self):
        claim = self._create_filed_claim()
        claim = ClaimService().transition_status(claim, "UNDER_REVIEW")
        claim = ClaimService().transition_status(
            claim, "APPROVED", approved_amount=Decimal("500.00")
        )
        claim = ClaimService().transition_status(claim, "RESOLVED")
        with pytest.raises(InvalidClaimStatusError) as exc_info:
            ClaimService().transition_status(claim, "UNDER_REVIEW")
        assert exc_info.value.details["allowed_transitions"] == []

    def test_transition_to_resolved_emits_both_events(self, mock_kafka):
        claim = self._create_filed_claim()
        claim = ClaimService().transition_status(claim, "UNDER_REVIEW")
        claim = ClaimService().transition_status(
            claim, "APPROVED", approved_amount=Decimal("500.00")
        )

        producer = mock_kafka.return_value
        assert producer.produce_claim_status_changed.called

        producer.produce_claim_resolved.reset_mock()
        ClaimService().transition_status(claim, "RESOLVED")
        assert producer.produce_claim_resolved.called


@pytest.mark.django_db
class TestGetClaimsQueryset:
    def test_filter_by_status(self):
        Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="A",
            claimant_email="a@test.com",
            incident_date="2026-01-01",
            incident_type=Claim.IncidentType.ACCIDENTE,
            description="A",
            estimated_damage=Decimal("100.00"),
            status=Claim.Status.FILED,
        )
        Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="B",
            claimant_email="b@test.com",
            incident_date="2026-02-01",
            incident_type=Claim.IncidentType.ROBO,
            description="B",
            estimated_damage=Decimal("200.00"),
            status=Claim.Status.RESOLVED,
        )
        qs = ClaimService().get_claims_queryset(status=Claim.Status.FILED)
        assert qs.count() == 1

    def test_filter_by_policy_id(self):
        policy_id = uuid.uuid4()
        Claim.objects.create(
            policy_id=policy_id,
            claimant_name="A",
            claimant_email="a@test.com",
            incident_date="2026-01-01",
            incident_type=Claim.IncidentType.ACCIDENTE,
            description="A",
            estimated_damage=Decimal("100.00"),
        )
        Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="B",
            claimant_email="b@test.com",
            incident_date="2026-02-01",
            incident_type=Claim.IncidentType.ROBO,
            description="B",
            estimated_damage=Decimal("200.00"),
        )
        qs = ClaimService().get_claims_queryset(policy_id=str(policy_id))
        assert qs.count() == 1

    def test_filter_by_incident_type(self):
        Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="A",
            claimant_email="a@test.com",
            incident_date="2026-01-01",
            incident_type=Claim.IncidentType.ROBO,
            description="A",
            estimated_damage=Decimal("100.00"),
        )
        Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="B",
            claimant_email="b@test.com",
            incident_date="2026-02-01",
            incident_type=Claim.IncidentType.INCENDIO,
            description="B",
            estimated_damage=Decimal("200.00"),
        )
        qs = ClaimService().get_claims_queryset(incident_type=Claim.IncidentType.ROBO)
        assert qs.count() == 1

    def test_no_filters_returns_all(self):
        Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="A",
            claimant_email="a@test.com",
            incident_date="2026-01-01",
            incident_type=Claim.IncidentType.ACCIDENTE,
            description="A",
            estimated_damage=Decimal("100.00"),
        )
        Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="B",
            claimant_email="b@test.com",
            incident_date="2026-02-01",
            incident_type=Claim.IncidentType.ROBO,
            description="B",
            estimated_damage=Decimal("200.00"),
        )
        qs = ClaimService().get_claims_queryset()
        assert qs.count() == 2
