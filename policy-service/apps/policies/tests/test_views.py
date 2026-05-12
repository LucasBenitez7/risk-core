import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.policies.models import Customer, Policy


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


@pytest.mark.django_db
class TestCustomerViews:
    def test_create_customer_201(self, api_client):
        response = api_client.post(
            "/api/policies/customers/",
            {
                "full_name": "Ana García",
                "email": "ana@test.com",
                "dni": "12345678A",
                "phone": "600000001",
                "address": "Calle Mayor 1",
            },
        )
        assert response.status_code == 201
        assert response.data["full_name"] == "Ana García"
        assert response.data["email"] == "ana@test.com"
        assert "id" in response.data

    def test_create_customer_duplicate_email(self, api_client):
        Customer.objects.create(
            full_name="Existing", email="dup@test.com", dni="11111111A"
        )
        response = api_client.post(
            "/api/policies/customers/",
            {
                "full_name": "Duplicate",
                "email": "dup@test.com",
                "dni": "22222222B",
            },
        )
        assert response.status_code == 400
        assert response.data["error"]["code"] == "VALIDATION_ERROR"
        assert "email" in response.data["error"]["details"]

    def test_create_customer_duplicate_dni(self, api_client):
        Customer.objects.create(
            full_name="Existing", email="a@test.com", dni="33333333C"
        )
        response = api_client.post(
            "/api/policies/customers/",
            {
                "full_name": "Duplicate",
                "email": "b@test.com",
                "dni": "33333333C",
            },
        )
        assert response.status_code == 400
        assert response.data["error"]["code"] == "VALIDATION_ERROR"
        assert "dni" in response.data["error"]["details"]

    def test_list_customers(self, api_client):
        Customer.objects.create(full_name="User A", email="a@test.com", dni="44444444D")
        Customer.objects.create(full_name="User B", email="b@test.com", dni="55555555E")
        response = api_client.get("/api/policies/customers/")
        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_retrieve_customer(self, api_client):
        customer = Customer.objects.create(
            full_name="Detail User", email="detail@test.com", dni="66666666F"
        )
        response = api_client.get(f"/api/policies/customers/{customer.id}/")
        assert response.status_code == 200
        assert response.data["full_name"] == "Detail User"

    def test_customer_update_not_allowed(self, api_client):
        customer = Customer.objects.create(
            full_name="No Update", email="noupdate@test.com", dni="77777777G"
        )
        response = api_client.patch(
            f"/api/policies/customers/{customer.id}/",
            {"full_name": "Updated Name"},
        )
        assert response.status_code == 405


@pytest.mark.django_db
class TestPolicyViews:
    def test_create_policy_201(self, api_client):
        customer = Customer.objects.create(
            full_name="Policy User", email="policy@test.com", dni="88888888H"
        )
        response = api_client.post(
            "/api/policies/policies/",
            {
                "customer_id": str(customer.id),
                "policy_type": Policy.PolicyType.LIFE,
                "premium_amount": "150.00",
                "start_date": "2025-01-01",
                "end_date": "2026-01-01",
            },
        )
        assert response.status_code == 201
        assert response.data["status"] == Policy.Status.ACTIVE
        assert response.data["policy_type"] == Policy.PolicyType.LIFE
        assert response.data["policy_number"].startswith("POL-")

    def test_list_policies_filter_by_status(self, api_client):
        customer = Customer.objects.create(
            full_name="Filter User", email="filter@test.com", dni="99999999I"
        )
        Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=100.00,
            start_date="2025-01-01",
            end_date="2026-01-01",
            status=Policy.Status.ACTIVE,
        )
        Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.AUTO,
            premium_amount=200.00,
            start_date="2025-02-01",
            end_date="2026-02-01",
            status=Policy.Status.CANCELLED,
        )
        response = api_client.get("/api/policies/policies/?status=ACTIVE")
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["status"] == Policy.Status.ACTIVE

    def test_cancel_policy_success(self, api_client):
        customer = Customer.objects.create(
            full_name="Cancel Ok", email="cancelok@test.com", dni="00000001J"
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.HOME,
            premium_amount=350.00,
            start_date="2025-03-01",
            end_date="2026-03-01",
        )
        response = api_client.post(
            f"/api/policies/policies/{policy.id}/cancel/",
            {"reason": "Client request"},
        )
        assert response.status_code == 200
        assert response.data["status"] == Policy.Status.CANCELLED
        assert response.data["cancellation_reason"] == "Client request"

    def test_cancel_policy_already_cancelled(self, api_client):
        customer = Customer.objects.create(
            full_name="Double Cancel", email="dcancel@test.com", dni="11111111K"
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=100.00,
            start_date="2025-04-01",
            end_date="2026-04-01",
            status=Policy.Status.CANCELLED,
        )
        response = api_client.post(
            f"/api/policies/policies/{policy.id}/cancel/",
            {"reason": "Second attempt"},
        )
        assert response.status_code == 400
        assert "error" in response.data
        assert response.data["error"]["code"] == "INVALID_POLICY_STATUS"

    def test_verify_active_policy(self, api_client_no_auth):
        customer = Customer.objects.create(
            full_name="Verify User", email="verify@test.com", dni="22222222L"
        )
        policy = Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.LIFE,
            premium_amount=150.00,
            start_date="2025-05-01",
            end_date="2026-05-01",
        )
        response = api_client_no_auth.get(f"/api/policies/policies/{policy.id}/verify/")
        assert response.status_code == 200
        assert response.data["is_valid"] is True
        assert response.data["status"] == Policy.Status.ACTIVE

    def test_verify_nonexistent_policy(self, api_client_no_auth):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = api_client_no_auth.get(f"/api/policies/policies/{fake_id}/verify/")
        assert response.status_code == 404
        assert "error" in response.data
        assert response.data["error"]["code"] == "POLICY_NOT_FOUND"


@pytest.mark.django_db
class TestPolicyMetricsView:
    def test_metrics_returns_200_with_schema(self, api_client):
        response = api_client.get("/api/policies/metrics/")
        assert response.status_code == 200
        data = response.data
        assert "active_policies" in data
        assert "policies_today" in data
        assert "policies_by_type" in data
        assert "total_premium_active" in data
        assert isinstance(data["active_policies"], int)
        assert isinstance(data["policies_by_type"], dict)

    def test_metrics_requires_auth(self, api_client_no_auth):
        response = api_client_no_auth.get("/api/policies/metrics/")
        assert response.status_code == 401

    def test_metrics_reflects_real_data(self, api_client):
        from apps.policies.models import Customer, Policy

        customer = Customer.objects.create(
            full_name="Metrics User", email="metrics@test.com", dni="99999999A"
        )
        Policy.objects.create(
            customer=customer,
            policy_type=Policy.PolicyType.AUTO,
            premium_amount="500.00",
            start_date="2025-01-01",
            end_date="2026-01-01",
            status=Policy.Status.ACTIVE,
        )
        response = api_client.get("/api/policies/metrics/")
        assert response.status_code == 200
        assert response.data["active_policies"] >= 1
        assert response.data["policies_by_type"]["AUTO"] >= 1
