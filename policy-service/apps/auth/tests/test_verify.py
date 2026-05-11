import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def auth_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.mark.django_db
def test_verify_valid_jwt(auth_client):
    response = auth_client.get("/api/auth/verify/")
    assert response.status_code == 200
    assert response.data["valid"] is True


@pytest.mark.django_db
def test_verify_no_token():
    client = APIClient()
    response = client.get("/api/auth/verify/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_verify_invalid_token():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.here")
    response = client.get("/api/auth/verify/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_token_obtain(user):
    client = APIClient()
    response = client.post(
        "/api/auth/token/", {"username": "testuser", "password": "testpass"}
    )
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_token_refresh(user):
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    response = client.post("/api/auth/token/refresh/", {"refresh": str(refresh)})
    assert response.status_code == 200
    assert "access" in response.data
