import uuid

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.notifications.models import Notification, NotificationLog


@pytest.fixture
def user():
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def sent_notification():
    notification = Notification.objects.create(
        event_id=str(uuid.uuid4()),
        event_type="policy.created",
        recipient_email="user@example.com",
        subject="Póliza creada",
        context={"policy_number": "POL-0001"},
        status=Notification.Status.SENT,
    )
    NotificationLog.objects.create(
        notification=notification,
        attempt=1,
        status=NotificationLog.Status.SUCCESS,
    )
    return notification


@pytest.fixture
def pending_notification():
    return Notification.objects.create(
        event_id=str(uuid.uuid4()),
        event_type="claim.filed",
        recipient_email="claimant@example.com",
        subject="Siniestro registrado",
        context={"claim_number": "CLM-0001"},
        status=Notification.Status.PENDING,
    )


@pytest.mark.django_db
class TestNotificationListView:
    def test_list_notifications_200(self, api_client, sent_notification):
        response = api_client.get("/api/notifications/notifications/")
        assert response.status_code == 200
        assert response.data["count"] >= 1

    def test_list_notifications_filter_by_status(
        self, api_client, sent_notification, pending_notification
    ):
        response = api_client.get("/api/notifications/notifications/?status=SENT")
        assert response.status_code == 200
        for item in response.data["results"]:
            assert item["status"] == "SENT"

    def test_list_notifications_filter_by_event_type(
        self, api_client, sent_notification, pending_notification
    ):
        response = api_client.get(
            "/api/notifications/notifications/?event_type=policy.created"
        )
        assert response.status_code == 200
        for item in response.data["results"]:
            assert item["event_type"] == "policy.created"

    def test_list_uses_light_serializer(self, api_client, sent_notification):
        response = api_client.get("/api/notifications/notifications/")
        assert response.status_code == 200
        result = response.data["results"][0]
        assert "subject" not in result
        assert "context" not in result
        assert "logs" not in result
        assert "id" in result
        assert "event_type" in result

    def test_list_requires_auth(self):
        client = APIClient()
        response = client.get("/api/notifications/notifications/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestNotificationRetrieveView:
    def test_retrieve_notification_200(self, api_client, sent_notification):
        response = api_client.get(
            f"/api/notifications/notifications/{sent_notification.id}/"
        )
        assert response.status_code == 200
        assert response.data["id"] == str(sent_notification.id)
        assert "logs" in response.data
        assert len(response.data["logs"]) == 1
        assert response.data["logs"][0]["status"] == "SUCCESS"
        assert "context" in response.data
        assert "subject" in response.data

    def test_retrieve_nonexistent_404(self, api_client):
        response = api_client.get(f"/api/notifications/notifications/{uuid.uuid4()}/")
        assert response.status_code == 404
        assert response.data["error"]["code"] == "NOTIFICATION_NOT_FOUND"
        assert "notification_id" in response.data["error"]["details"]

    def test_retrieve_requires_auth(self, sent_notification):
        client = APIClient()
        response = client.get(
            f"/api/notifications/notifications/{sent_notification.id}/"
        )
        assert response.status_code == 401
