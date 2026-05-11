import uuid
from unittest.mock import patch

import pytest

from apps.notifications.models import Notification, NotificationLog
from apps.notifications.tasks import send_email_notification


@pytest.mark.django_db
class TestSendEmailNotificationTask:
    def test_sends_email_and_updates_status_to_sent(self):
        notification = Notification.objects.create(
            event_id=str(uuid.uuid4()),
            event_type="policy.created",
            recipient_email="user@example.com",
            subject="Póliza creada",
            context={"policy_number": "POL-0001"},
        )

        with (
            patch("apps.notifications.tasks.send_mail") as mock_send_mail,
            patch("apps.notifications.tasks.render_to_string") as mock_render,
        ):
            mock_render.return_value = "<html>Test</html>"
            send_email_notification(str(notification.id))

        notification.refresh_from_db()
        assert notification.status == Notification.Status.SENT
        assert notification.sent_at is not None

        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args.kwargs
        assert call_kwargs["subject"] == "Póliza creada"
        assert call_kwargs["recipient_list"] == ["user@example.com"]
        assert call_kwargs["html_message"] == "<html>Test</html>"

        log = notification.logs.first()
        assert log is not None
        assert log.status == NotificationLog.Status.SUCCESS
        assert log.attempt == 1

    def test_smtp_failure_sets_failed_and_retries(self):
        notification = Notification.objects.create(
            event_id=str(uuid.uuid4()),
            event_type="claim.filed",
            recipient_email="user@example.com",
            subject="Siniestro registrado",
            context={"claim_number": "CLM-0001"},
        )

        with (
            patch("apps.notifications.tasks.send_mail") as mock_send_mail,
            patch("apps.notifications.tasks.render_to_string") as mock_render,
        ):
            mock_render.return_value = "<html>Test</html>"
            mock_send_mail.side_effect = Exception("SMTP connection refused")

            with pytest.raises(Exception, match="SMTP connection refused"):
                send_email_notification(str(notification.id))

        notification.refresh_from_db()
        assert notification.status == Notification.Status.FAILED

        log = notification.logs.first()
        assert log is not None
        assert log.status == NotificationLog.Status.FAILURE
        assert "SMTP connection refused" in log.error_message
        assert log.attempt == 1

    def test_notification_not_found_returns_gracefully(self):
        fake_id = str(uuid.uuid4())

        with patch("apps.notifications.tasks.send_mail") as mock_send_mail:
            result = send_email_notification(fake_id)

        assert result is None
        mock_send_mail.assert_not_called()
