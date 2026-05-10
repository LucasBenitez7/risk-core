import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import REGISTRY

from apps.claims.models import Claim
from apps.claims.services import ClaimService


def _counter(name: str, labels: dict) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.fixture(autouse=True)
def mock_policy_client():
    with patch("apps.claims.services.PolicyServiceClient") as mock:
        client = MagicMock()
        client.verify_policy.return_value = {"status": "ACTIVE", "is_valid": True}
        mock.return_value = client
        yield mock


@pytest.mark.django_db
class TestClaimsFiledMetric:
    def test_increments_counter_with_incident_type_label(self):
        data = {
            "policy_id": str(uuid.uuid4()),
            "claimant_name": "Metrics Claimant",
            "claimant_email": "metrics_claim@example.com",
            "incident_date": "2025-01-15",
            "incident_type": Claim.IncidentType.ACCIDENTE,
            "description": "Collision",
            "estimated_damage": Decimal("5000.00"),
        }
        before = _counter(
            "riskcore_claims_filed_total",
            {"incident_type": Claim.IncidentType.ACCIDENTE},
        )
        ClaimService().file_claim(data)
        after = _counter(
            "riskcore_claims_filed_total",
            {"incident_type": Claim.IncidentType.ACCIDENTE},
        )
        assert after == before + 1

    def test_different_incident_types_use_separate_labels(self):
        robo_data = {
            "policy_id": str(uuid.uuid4()),
            "claimant_name": "Robo Claimant",
            "claimant_email": "robo@example.com",
            "incident_date": "2025-01-15",
            "incident_type": Claim.IncidentType.ROBO,
            "description": "Theft",
            "estimated_damage": Decimal("1000.00"),
        }
        accidente_before = _counter(
            "riskcore_claims_filed_total",
            {"incident_type": Claim.IncidentType.ACCIDENTE},
        )
        ClaimService().file_claim(robo_data)
        assert (
            _counter(
                "riskcore_claims_filed_total",
                {"incident_type": Claim.IncidentType.ACCIDENTE},
            )
            == accidente_before
        )


@pytest.mark.django_db
class TestClaimsStatusChangedMetric:
    def test_increments_counter_on_transition(self):
        claim = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="Status Claimant",
            claimant_email="status_metrics@example.com",
            incident_date="2025-01-15",
            incident_type=Claim.IncidentType.ACCIDENTE,
            description="Test",
            estimated_damage=Decimal("1000.00"),
        )
        before = _counter(
            "riskcore_claims_status_changed_total",
            {"from_status": "FILED", "to_status": "UNDER_REVIEW"},
        )
        ClaimService().transition_status(claim, Claim.Status.UNDER_REVIEW)
        after = _counter(
            "riskcore_claims_status_changed_total",
            {"from_status": "FILED", "to_status": "UNDER_REVIEW"},
        )
        assert after == before + 1

    def test_labels_reflect_actual_transition(self):
        claim = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="Review Claimant",
            claimant_email="review_metrics@example.com",
            incident_date="2025-01-15",
            incident_type=Claim.IncidentType.INCENDIO,
            description="Fire damage",
            estimated_damage=Decimal("20000.00"),
            status=Claim.Status.UNDER_REVIEW,
        )
        before = _counter(
            "riskcore_claims_status_changed_total",
            {"from_status": "UNDER_REVIEW", "to_status": "APPROVED"},
        )
        ClaimService().transition_status(
            claim, Claim.Status.APPROVED, approved_amount=Decimal("18000.00")
        )
        after = _counter(
            "riskcore_claims_status_changed_total",
            {"from_status": "UNDER_REVIEW", "to_status": "APPROVED"},
        )
        assert after == before + 1
