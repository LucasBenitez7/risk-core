import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from apps.notifications.kafka_consumer import NotificationKafkaConsumer
from apps.notifications.models import Notification


def _make_msg(topic: str, payload: dict):
    msg = MagicMock()
    msg.value.return_value = json.dumps(payload).encode("utf-8")
    msg.topic.return_value = topic
    msg.error.return_value = None
    return msg


def _policy_created_payload():
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "policy.created",
        "occurred_at": "2026-03-15T10:00:00Z",
        "service": "policy-service",
        "data": {
            "policy_id": str(uuid.uuid4()),
            "policy_number": "POL-0001",
            "customer_id": str(uuid.uuid4()),
            "customer_email": "customer@example.com",
        },
    }


def _claim_filed_payload():
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "claim.filed",
        "occurred_at": "2026-03-15T10:00:00Z",
        "service": "claims-service",
        "data": {
            "claim_id": str(uuid.uuid4()),
            "claim_number": "CLM-0001",
            "policy_id": str(uuid.uuid4()),
            "claimant_email": "claimant@example.com",
        },
    }


@pytest.mark.django_db
class TestNotificationKafkaConsumer:
    def test_policy_created_creates_notification_and_dispatches_task(
        self, mock_kafka_consumer
    ):
        payload = _policy_created_payload()
        msg = _make_msg("policy.created", payload)
        consumer = NotificationKafkaConsumer()

        with patch(
            "apps.notifications.kafka_consumer.send_email_notification.delay"
        ) as mock_delay:
            consumer._handle_message(msg)

        notification = Notification.objects.get(event_id=payload["event_id"])
        assert notification.event_type == "policy.created"
        assert notification.recipient_email == "customer@example.com"
        assert notification.subject == "Póliza creada"
        assert notification.status == Notification.Status.PENDING
        assert notification.context == {"policy_number": "POL-0001"}

        mock_delay.assert_called_once_with(str(notification.id))

    def test_claim_filed_creates_notification_with_correct_type(
        self, mock_kafka_consumer
    ):
        payload = _claim_filed_payload()
        msg = _make_msg("claim.filed", payload)
        consumer = NotificationKafkaConsumer()

        with patch("apps.notifications.kafka_consumer.send_email_notification.delay"):
            consumer._handle_message(msg)

        notification = Notification.objects.get(event_id=payload["event_id"])
        assert notification.event_type == "claim.filed"
        assert notification.recipient_email == "claimant@example.com"
        assert notification.subject == "Siniestro registrado"
        assert notification.context == {"claim_number": "CLM-0001"}

    def test_offset_committed_on_success(self, mock_kafka_consumer):
        payload = _policy_created_payload()
        msg = _make_msg("policy.created", payload)
        consumer = NotificationKafkaConsumer()

        with patch("apps.notifications.kafka_consumer.send_email_notification.delay"):
            consumer._handle_message(msg)

        mock_kafka_consumer.commit.assert_called_once_with(message=msg)

    def test_duplicate_event_commits_offset(self, mock_kafka_consumer):
        from django.db import transaction

        payload = _policy_created_payload()
        msg = _make_msg("policy.created", payload)

        Notification.objects.create(
            event_id=payload["event_id"],
            event_type="policy.created",
            recipient_email="customer@example.com",
            subject="Póliza creada",
            context={},
        )

        consumer = NotificationKafkaConsumer()
        with (
            patch(
                "apps.notifications.kafka_consumer.send_email_notification.delay"
            ) as mock_delay,
            transaction.atomic(),
        ):
            consumer._handle_message(msg)

        mock_delay.assert_not_called()
        mock_kafka_consumer.commit.assert_called_once_with(message=msg)
        assert Notification.objects.filter(event_id=payload["event_id"]).count() == 1

    def test_invalid_json_does_not_crash(self, mock_kafka_consumer):
        msg = MagicMock()
        msg.value.return_value = b"not valid json"
        msg.topic.return_value = "policy.created"
        msg.error.return_value = None

        consumer = NotificationKafkaConsumer()
        with patch(
            "apps.notifications.kafka_consumer.send_email_notification.delay"
        ) as mock_delay:
            consumer._handle_message(msg)

        mock_delay.assert_not_called()
        assert Notification.objects.count() == 0

    def test_policy_event_falls_back_to_default_email(self, mock_kafka_consumer):
        payload = _policy_created_payload()
        del payload["data"]["customer_email"]
        msg = _make_msg("policy.created", payload)
        consumer = NotificationKafkaConsumer()

        with patch("apps.notifications.kafka_consumer.send_email_notification.delay"):
            consumer._handle_message(msg)

        notification = Notification.objects.get(event_id=payload["event_id"])
        assert notification.recipient_email == "noreply@riskcore.com"

    def test_claim_status_changed_builds_correct_context(self, mock_kafka_consumer):
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": "claim.status_changed",
            "occurred_at": "2026-03-15T10:00:00Z",
            "service": "claims-service",
            "data": {
                "claim_id": str(uuid.uuid4()),
                "claim_number": "CLM-0001",
                "policy_id": str(uuid.uuid4()),
                "claimant_email": "claimant@example.com",
                "from_status": "FILED",
                "to_status": "UNDER_REVIEW",
            },
        }
        msg = _make_msg("claim.status_changed", payload)
        consumer = NotificationKafkaConsumer()

        with patch("apps.notifications.kafka_consumer.send_email_notification.delay"):
            consumer._handle_message(msg)

        notification = Notification.objects.get(event_id=payload["event_id"])
        assert notification.event_type == "claim.status_changed"
        assert notification.context["claim_number"] == "CLM-0001"
        assert notification.context["new_status"] == "UNDER_REVIEW"

    def test_claim_resolved_builds_correct_context(self, mock_kafka_consumer):
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": "claim.resolved",
            "occurred_at": "2026-03-15T10:00:00Z",
            "service": "claims-service",
            "data": {
                "claim_id": str(uuid.uuid4()),
                "claim_number": "CLM-0001",
                "policy_id": str(uuid.uuid4()),
                "claimant_email": "claimant@example.com",
                "approved_amount": "5000.00",
            },
        }
        msg = _make_msg("claim.resolved", payload)
        consumer = NotificationKafkaConsumer()

        with patch("apps.notifications.kafka_consumer.send_email_notification.delay"):
            consumer._handle_message(msg)

        notification = Notification.objects.get(event_id=payload["event_id"])
        assert notification.event_type == "claim.resolved"
        assert notification.context["claim_number"] == "CLM-0001"
        assert notification.context["approved_amount"] == "5000.00"

    def test_generic_exception_does_not_commit(self, mock_kafka_consumer):
        payload = _policy_created_payload()
        msg = _make_msg("policy.created", payload)
        consumer = NotificationKafkaConsumer()

        with patch(
            "apps.notifications.kafka_consumer.send_email_notification.delay",
            side_effect=RuntimeError("Celery broker down"),
        ):
            consumer._handle_message(msg)

        mock_kafka_consumer.commit.assert_not_called()

    def test_run_subscribes_and_processes_messages(self, mock_kafka_consumer):
        from apps.notifications.kafka_consumer import NOTIFICATION_TOPICS

        payload = _policy_created_payload()
        msg = _make_msg("policy.created", payload)
        mock_kafka_consumer.poll.side_effect = [msg, KeyboardInterrupt()]

        consumer = NotificationKafkaConsumer()

        with patch(
            "apps.notifications.kafka_consumer.send_email_notification.delay"
        ) as mock_delay:
            consumer.run()

        mock_kafka_consumer.subscribe.assert_called_once_with(NOTIFICATION_TOPICS)
        mock_delay.assert_called_once()
        mock_kafka_consumer.close.assert_called_once()
