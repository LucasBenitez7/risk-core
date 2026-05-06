import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.claims.models import Claim, ClaimStatusHistory


@pytest.fixture
def user():
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def api_client_no_auth():
    return APIClient()


@pytest.fixture(autouse=True)
def mock_kafka():
    with patch("apps.claims.services._get_producer") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture
def filed_claim():
    claim = Claim.objects.create(
        policy_id=uuid.uuid4(),
        claimant_name="Test User",
        claimant_email="test@test.com",
        incident_date="2026-03-15",
        incident_type=Claim.IncidentType.ACCIDENTE,
        description="Accidente en la A-6",
        estimated_damage=Decimal("5000.00"),
    )
    ClaimStatusHistory.objects.create(
        claim=claim,
        from_status="",
        to_status=Claim.Status.FILED,
        notes="Siniestro reportado",
    )
    return claim


MOCK_VERIFY_VIEW = "apps.claims.clients.PolicyServiceClient.verify_policy"


def _mock_verify(return_value):
    return patch(MOCK_VERIFY_VIEW, return_value=return_value)


@pytest.mark.django_db
class TestClaimCreateView:
    def test_create_claim_201(self, api_client):
        policy_id = str(uuid.uuid4())
        with _mock_verify({"status": "ACTIVE", "is_valid": True}):
            response = api_client.post(
                "/api/claims/claims/",
                {
                    "policy_id": policy_id,
                    "claimant_name": "Ana García",
                    "claimant_email": "ana@test.com",
                    "incident_date": "2026-03-15",
                    "incident_type": "ACCIDENTE",
                    "description": "Accidente en la A-6",
                    "estimated_damage": "5000.00",
                },
                format="json",
            )

        assert response.status_code == 201
        assert response.data["status"] == "FILED"
        assert response.data["claim_number"].startswith("CLM-")
        assert response.data["claimant_name"] == "Ana García"
        assert "status_history" in response.data
        assert len(response.data["status_history"]) == 1
        assert response.data["status_history"][0]["to_status"] == "FILED"

    def test_create_claim_policy_inactive_400(self, api_client):
        policy_id = str(uuid.uuid4())
        from apps.core.exceptions import PolicyInactiveError

        with patch(
            "apps.claims.clients.PolicyServiceClient.verify_policy",
            side_effect=PolicyInactiveError(
                policy_id=policy_id, policy_status="CANCELLED"
            ),
        ):
            response = api_client.post(
                "/api/claims/claims/",
                {
                    "policy_id": policy_id,
                    "claimant_name": "Test",
                    "claimant_email": "test@test.com",
                    "incident_date": "2026-01-01",
                    "incident_type": "ACCIDENTE",
                    "description": "Test",
                    "estimated_damage": "100.00",
                },
                format="json",
            )

        assert response.status_code == 400
        assert response.data["error"]["code"] == "POLICY_INACTIVE"
        assert response.data["error"]["details"]["policy_status"] == "CANCELLED"

    def test_create_claim_policy_service_unavailable_503(self, api_client):
        policy_id = str(uuid.uuid4())
        from apps.core.exceptions import PolicyServiceUnavailableError

        with patch(
            "apps.claims.clients.PolicyServiceClient.verify_policy",
            side_effect=PolicyServiceUnavailableError(policy_id=policy_id),
        ):
            response = api_client.post(
                "/api/claims/claims/",
                {
                    "policy_id": policy_id,
                    "claimant_name": "Test",
                    "claimant_email": "test@test.com",
                    "incident_date": "2026-01-01",
                    "incident_type": "ACCIDENTE",
                    "description": "Test",
                    "estimated_damage": "100.00",
                },
                format="json",
            )

        assert response.status_code == 503
        assert response.data["error"]["code"] == "POLICY_SERVICE_UNAVAILABLE"

    def test_create_claim_future_incident_date_400(self, api_client):
        policy_id = str(uuid.uuid4())
        with _mock_verify({"status": "ACTIVE", "is_valid": True}):
            response = api_client.post(
                "/api/claims/claims/",
                {
                    "policy_id": policy_id,
                    "claimant_name": "Test",
                    "claimant_email": "test@test.com",
                    "incident_date": "2099-01-01",
                    "incident_type": "ACCIDENTE",
                    "description": "Test",
                    "estimated_damage": "100.00",
                },
                format="json",
            )

        assert response.status_code == 400
        assert response.data["error"]["code"] == "VALIDATION_ERROR"
        assert "incident_date" in response.data["error"]["details"]

    def test_create_claim_requires_auth(self, api_client_no_auth):
        response = api_client_no_auth.post(
            "/api/claims/claims/",
            {
                "policy_id": str(uuid.uuid4()),
                "claimant_name": "Test",
                "claimant_email": "test@test.com",
                "incident_date": "2026-01-01",
                "incident_type": "ACCIDENTE",
                "description": "Test",
                "estimated_damage": "100.00",
            },
            format="json",
        )
        assert response.status_code == 401


@pytest.mark.django_db
class TestClaimListView:
    def test_list_claims(self, api_client, filed_claim):
        response = api_client.get("/api/claims/claims/")
        assert response.status_code == 200
        assert response.data["count"] >= 1

    def test_list_claims_filter_by_status(self, api_client, filed_claim):
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
        response = api_client.get("/api/claims/claims/?status=FILED")
        assert response.status_code == 200
        for item in response.data["results"]:
            assert item["status"] == "FILED"

    def test_list_uses_light_serializer(self, api_client, filed_claim):
        response = api_client.get("/api/claims/claims/")
        assert response.status_code == 200
        result = response.data["results"][0]
        assert "status_history" not in result
        assert "documents" not in result
        assert "claim_number" in result


@pytest.mark.django_db
class TestClaimRetrieveView:
    def test_retrieve_claim(self, api_client, filed_claim):
        response = api_client.get(f"/api/claims/claims/{filed_claim.id}/")
        assert response.status_code == 200
        assert response.data["id"] == str(filed_claim.id)
        assert "status_history" in response.data
        assert len(response.data["status_history"]) == 1

    def test_retrieve_nonexistent_claim_404(self, api_client):
        response = api_client.get(f"/api/claims/claims/{uuid.uuid4()}/")
        assert response.status_code == 404
        assert response.data["error"]["code"] == "CLAIM_NOT_FOUND"


@pytest.mark.django_db
class TestClaimTransitionView:
    def test_transition_valid(self, api_client, filed_claim):
        response = api_client.post(
            f"/api/claims/claims/{filed_claim.id}/transition/",
            {"new_status": "UNDER_REVIEW", "notes": "Asignado a perito"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["status"] == "UNDER_REVIEW"

    def test_transition_invalid_400(self, api_client, filed_claim):
        response = api_client.post(
            f"/api/claims/claims/{filed_claim.id}/transition/",
            {"new_status": "RESOLVED"},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["error"]["code"] == "INVALID_CLAIM_STATUS"
        assert "allowed_transitions" in response.data["error"]["details"]

    def test_transition_to_approved_without_amount_400(self, api_client, filed_claim):
        api_client.post(
            f"/api/claims/claims/{filed_claim.id}/transition/",
            {"new_status": "UNDER_REVIEW"},
            format="json",
        )
        response = api_client.post(
            f"/api/claims/claims/{filed_claim.id}/transition/",
            {"new_status": "APPROVED"},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_transition_nonexistent_claim_404(self, api_client):
        response = api_client.post(
            f"/api/claims/claims/{uuid.uuid4()}/transition/",
            {"new_status": "UNDER_REVIEW"},
            format="json",
        )
        assert response.status_code == 404
        assert response.data["error"]["code"] == "CLAIM_NOT_FOUND"

    def test_transition_requires_auth(self, api_client_no_auth, filed_claim):
        response = api_client_no_auth.post(
            f"/api/claims/claims/{filed_claim.id}/transition/",
            {"new_status": "UNDER_REVIEW"},
            format="json",
        )
        assert response.status_code == 401
