import uuid
from unittest.mock import patch

import pytest
from prometheus_client import REGISTRY

from apps.notifications.models import Notification
from apps.notifications.tasks import send_email_notification


def _counter(name: str, labels: dict) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.mark.django_db
class TestNotificationsSentCounter:
    def test_sent_label_increments_on_success(self):
        notification = Notification.objects.create(
            event_id=str(uuid.uuid4()),
            event_type="policy.created",
            recipient_email="user@example.com",
            subject="Póliza creada",
            context={"policy_number": "POL-0001"},
        )
        before = _counter(
            "riskcore_notifications_sent_total",
            {"event_type": "policy.created", "status": "sent"},
        )
        with (
            patch("apps.notifications.tasks.send_mail"),
            patch("apps.notifications.tasks.render_to_string", return_value="<html/>"),
        ):
            send_email_notification(str(notification.id))
        after = _counter(
            "riskcore_notifications_sent_total",
            {"event_type": "policy.created", "status": "sent"},
        )
        assert after == before + 1

    def test_failed_label_increments_on_smtp_error(self):
        notification = Notification.objects.create(
            event_id=str(uuid.uuid4()),
            event_type="claim.filed",
            recipient_email="user@example.com",
            subject="Siniestro registrado",
            context={"claim_number": "CLM-0001"},
        )
        before = _counter(
            "riskcore_notifications_sent_total",
            {"event_type": "claim.filed", "status": "failed"},
        )
        with (
            patch(
                "apps.notifications.tasks.send_mail",
                side_effect=Exception("SMTP error"),
            ),
            patch("apps.notifications.tasks.render_to_string", return_value="<html/>"),
            pytest.raises(Exception),  # noqa: B017
        ):
            send_email_notification(str(notification.id))
        after = _counter(
            "riskcore_notifications_sent_total",
            {"event_type": "claim.filed", "status": "failed"},
        )
        assert after == before + 1

    def test_event_type_labels_are_independent(self):
        notification = Notification.objects.create(
            event_id=str(uuid.uuid4()),
            event_type="policy.cancelled",
            recipient_email="user2@example.com",
            subject="Póliza cancelada",
            context={"policy_number": "POL-0002"},
        )
        created_before = _counter(
            "riskcore_notifications_sent_total",
            {"event_type": "policy.created", "status": "sent"},
        )
        with (
            patch("apps.notifications.tasks.send_mail"),
            patch("apps.notifications.tasks.render_to_string", return_value="<html/>"),
        ):
            send_email_notification(str(notification.id))
        # policy.created counter must not change
        assert (
            _counter(
                "riskcore_notifications_sent_total",
                {"event_type": "policy.created", "status": "sent"},
            )
            == created_before
        )


@pytest.mark.django_db
class TestCeleryDurationHistogram:
    def test_count_increments_on_success(self):
        notification = Notification.objects.create(
            event_id=str(uuid.uuid4()),
            event_type="claim.resolved",
            recipient_email="user@example.com",
            subject="Siniestro resuelto",
            context={"claim_number": "CLM-0002"},
        )
        before = _counter(
            "riskcore_celery_task_duration_seconds_count",
            {"task_name": "send_email_notification"},
        )
        with (
            patch("apps.notifications.tasks.send_mail"),
            patch("apps.notifications.tasks.render_to_string", return_value="<html/>"),
        ):
            send_email_notification(str(notification.id))
        after = _counter(
            "riskcore_celery_task_duration_seconds_count",
            {"task_name": "send_email_notification"},
        )
        assert after == before + 1

    def test_sum_is_non_negative_after_success(self):
        notification = Notification.objects.create(
            event_id=str(uuid.uuid4()),
            event_type="claim.status_changed",
            recipient_email="user@example.com",
            subject="Siniestro actualizado",
            context={"claim_number": "CLM-0003"},
        )
        with (
            patch("apps.notifications.tasks.send_mail"),
            patch("apps.notifications.tasks.render_to_string", return_value="<html/>"),
        ):
            send_email_notification(str(notification.id))
        total_sum = _counter(
            "riskcore_celery_task_duration_seconds_sum",
            {"task_name": "send_email_notification"},
        )
        assert total_sum >= 0
