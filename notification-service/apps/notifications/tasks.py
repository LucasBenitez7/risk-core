from uuid import UUID

import structlog
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = structlog.get_logger()


def _template_name(event_type: str) -> str:
    return f"notifications/emails/{event_type.replace('.', '_')}.html"


@shared_task(bind=True, max_retries=3, soft_time_limit=25)
def send_email_notification(self, notification_id: str):
    from .models import Notification, NotificationLog

    try:
        notification = Notification.objects.get(id=UUID(notification_id))
    except Notification.DoesNotExist:
        logger.warning(
            "notification_not_found",
            notification_id=notification_id,
            task_id=self.request.id,
        )
        return

    template = _template_name(notification.event_type)

    html = render_to_string(template, notification.context)
    plain_message = notification.subject

    try:
        send_mail(
            subject=notification.subject,
            message=plain_message,
            from_email=None,
            recipient_list=[notification.recipient_email],
            html_message=html,
        )
    except Exception as exc:
        notification.status = Notification.Status.FAILED
        notification.save(update_fields=["status"])

        NotificationLog.objects.create(
            notification=notification,
            attempt=self.request.retries + 1,
            status=NotificationLog.Status.FAILURE,
            error_message=str(exc),
        )

        logger.error(
            "email_send_failed",
            notification_id=notification_id,
            event_type=notification.event_type,
            attempt=self.request.retries + 1,
            error=str(exc),
        )

        raise self.retry(exc=exc, countdown=300) from exc

    notification.status = Notification.Status.SENT
    notification.sent_at = timezone.now()
    notification.save(update_fields=["status", "sent_at"])

    NotificationLog.objects.create(
        notification=notification,
        attempt=self.request.retries + 1,
        status=NotificationLog.Status.SUCCESS,
    )

    logger.info(
        "email_sent",
        notification_id=notification_id,
        event_type=notification.event_type,
        recipient=notification.recipient_email,
    )
