import uuid

import pytest

from apps.claims.models import Claim


@pytest.mark.django_db
class TestClaimNumberGeneration:
    def test_claim_number_format(self):
        claim = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="Test",
            claimant_email="test@example.com",
            incident_date="2026-01-01",
            incident_type=Claim.IncidentType.ACCIDENTE,
            description="Test",
            estimated_damage=100.00,
        )
        parts = claim.claim_number.split("-")
        assert parts[0] == "CLM"
        assert len(parts[1]) == 4
        assert parts[1].isdigit()
        assert len(parts[2]) == 6
        assert parts[2].isdigit()

    def test_claim_number_increments(self):
        claim1 = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="A",
            claimant_email="a@example.com",
            incident_date="2026-01-01",
            incident_type=Claim.IncidentType.ROBO,
            description="A",
            estimated_damage=50.00,
        )
        claim2 = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="B",
            claimant_email="b@example.com",
            incident_date="2026-02-01",
            incident_type=Claim.IncidentType.INCENDIO,
            description="B",
            estimated_damage=75.00,
        )
        num1 = int(claim1.claim_number.split("-")[2])
        num2 = int(claim2.claim_number.split("-")[2])
        assert num2 == num1 + 1


@pytest.mark.django_db
class TestClaimModel:
    def test_claim_has_uuid_pk(self):
        claim = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="UUID",
            claimant_email="uuid@example.com",
            incident_date="2026-03-01",
            incident_type=Claim.IncidentType.INUNDACION,
            description="Test",
            estimated_damage=200.00,
        )
        assert isinstance(claim.id, uuid.UUID)

    def test_claim_status_default_filed(self):
        claim = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="Status",
            claimant_email="status@example.com",
            incident_date="2026-04-01",
            incident_type=Claim.IncidentType.OTRO,
            description="Test",
            estimated_damage=300.00,
        )
        assert claim.status == Claim.Status.FILED

    def test_claim_approved_amount_null_by_default(self):
        claim = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="Null",
            claimant_email="null@example.com",
            incident_date="2026-05-01",
            incident_type=Claim.IncidentType.ACCIDENTE,
            description="Test",
            estimated_damage=400.00,
        )
        assert claim.approved_amount is None

    def test_claim_str_returns_claim_number(self):
        claim = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="Str",
            claimant_email="str@example.com",
            incident_date="2026-06-01",
            incident_type=Claim.IncidentType.ACCIDENTE,
            description="Test",
            estimated_damage=500.00,
        )
        assert str(claim) == claim.claim_number


@pytest.mark.django_db
class TestClaimStatusHistoryModel:
    def test_history_from_status_empty_on_first_record(self):
        claim = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="History",
            claimant_email="history@example.com",
            incident_date="2026-07-01",
            incident_type=Claim.IncidentType.ACCIDENTE,
            description="Test",
            estimated_damage=600.00,
        )
        from apps.claims.models import ClaimStatusHistory

        history = ClaimStatusHistory.objects.create(
            claim=claim,
            from_status="",
            to_status=Claim.Status.FILED,
            notes="First record",
        )
        assert history.from_status == ""
        assert history.to_status == Claim.Status.FILED

    def test_history_cascade_on_claim_delete(self):
        claim = Claim.objects.create(
            policy_id=uuid.uuid4(),
            claimant_name="Cascade",
            claimant_email="cascade@example.com",
            incident_date="2026-08-01",
            incident_type=Claim.IncidentType.ACCIDENTE,
            description="Test",
            estimated_damage=700.00,
        )
        from apps.claims.models import ClaimStatusHistory

        history = ClaimStatusHistory.objects.create(
            claim=claim,
            from_status="",
            to_status=Claim.Status.FILED,
        )
        history_id = history.id
        claim.delete()
        from apps.claims.models import ClaimStatusHistory as CSH

        assert not CSH.objects.filter(id=history_id).exists()
