import time
from uuid import UUID

import structlog
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.metrics import celery_task_duration_seconds, notifications_sent_total

logger = structlog.get_logger()


def _template_name(event_type: str) -> str:
    return f"notifications/emails/{event_type.replace('.', '_')}.html"


@shared_task(bind=True, max_retries=3, soft_time_limit=25)
def send_email_notification(self, notification_id: str):
    from .models import Notification, NotificationLog

    task_start = time.perf_counter()
    attempt = self.request.retries + 1

    try:
        notification = Notification.objects.get(id=UUID(notification_id))
    except Notification.DoesNotExist:
        logger.warning(
            "notification_not_found",
            notification_id=notification_id,
            task_id=self.request.id,
        )
        return

    logger.info(
        "celery_task_started",
        task_name="send_email_notification",
        task_id=self.request.id,
        notification_id=notification_id,
        event_type=notification.event_type,
        attempt=attempt,
    )

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
            attempt=attempt,
            status=NotificationLog.Status.FAILURE,
            error_message=str(exc),
        )

        notifications_sent_total.labels(
            event_type=notification.event_type, status="failed"
        ).inc()

        if self.request.retries < self.max_retries:
            logger.warning(
                "celery_task_retry",
                task_name="send_email_notification",
                task_id=self.request.id,
                notification_id=notification_id,
                event_type=notification.event_type,
                attempt=attempt,
                next_retry_in=300,
                error=str(exc),
            )
        else:
            logger.error(
                "celery_task_failed",
                task_name="send_email_notification",
                task_id=self.request.id,
                notification_id=notification_id,
                event_type=notification.event_type,
                attempt=attempt,
                error=str(exc),
                exc_info=True,
            )

        raise self.retry(exc=exc, countdown=300) from exc

    duration = time.perf_counter() - task_start
    notification.status = Notification.Status.SENT
    notification.sent_at = timezone.now()
    notification.save(update_fields=["status", "sent_at"])

    NotificationLog.objects.create(
        notification=notification,
        attempt=attempt,
        status=NotificationLog.Status.SUCCESS,
    )

    notifications_sent_total.labels(
        event_type=notification.event_type, status="sent"
    ).inc()
    celery_task_duration_seconds.labels(task_name="send_email_notification").observe(
        duration
    )
    logger.info(
        "celery_task_succeeded",
        task_name="send_email_notification",
        task_id=self.request.id,
        notification_id=notification_id,
        event_type=notification.event_type,
        recipient=notification.recipient_email,
        attempt=attempt,
        duration_ms=round(duration * 1000, 2),
    )
