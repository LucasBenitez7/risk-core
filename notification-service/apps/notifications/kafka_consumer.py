import json
import time

import structlog
from confluent_kafka import Consumer, KafkaError
from django.conf import settings
from django.db import IntegrityError, transaction

from apps.notifications.models import Notification
from apps.notifications.tasks import send_email_notification

logger = structlog.get_logger()

NOTIFICATION_TOPICS = [
    "policy.created",
    "policy.cancelled",
    "claim.filed",
    "claim.status_changed",
    "claim.resolved",
]


def _build_subject(event_type: str, data: dict) -> str:
    subjects = {
        "policy.created": "Póliza creada",
        "policy.cancelled": "Póliza cancelada",
        "claim.filed": "Siniestro registrado",
        "claim.status_changed": "Siniestro actualizado",
        "claim.resolved": "Siniestro resuelto",
    }
    return subjects.get(event_type, "Notificación RiskCore")


def _build_context(event_type: str, data: dict) -> dict:
    ctx = {}
    if event_type.startswith("policy."):
        ctx["policy_number"] = data.get("policy_number", "")
    elif event_type.startswith("claim."):
        ctx["claim_number"] = data.get("claim_number", "")
        if event_type == "claim.status_changed":
            ctx["new_status"] = data.get("to_status", "")
        elif event_type == "claim.resolved":
            ctx["approved_amount"] = data.get("approved_amount", "")
    return ctx


def _extract_recipient(data: dict, event_type: str) -> str:
    if event_type.startswith("claim."):
        return data.get("claimant_email") or settings.DEFAULT_FROM_EMAIL
    return data.get("customer_email") or settings.DEFAULT_FROM_EMAIL


class NotificationKafkaConsumer:
    def __init__(self):
        self.consumer = Consumer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "group.id": "notification-service",
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )

    def run(self) -> None:
        self.consumer.subscribe(NOTIFICATION_TOPICS)
        logger.info(
            "notification_consumer_started",
            topics=NOTIFICATION_TOPICS,
            group_id="notification-service",
        )

        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("kafka_consumer_error", error=str(msg.error()))
                    continue
                self._handle_message(msg)
        except KeyboardInterrupt:
            logger.info("notification_consumer_stopped")
        finally:
            self.consumer.close()

    def _handle_message(self, msg) -> None:
        try:
            payload = json.loads(msg.value().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error(
                "invalid_json_payload",
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
                error=str(exc),
            )
            return

        topic = msg.topic()
        event_type = payload.get("event_type", "")
        event_id = payload.get("event_id", "")
        data = payload.get("data", {})

        structlog.contextvars.bind_contextvars(event_id=event_id)
        logger.info(
            "kafka_message_received",
            topic=topic,
            partition=msg.partition(),
            offset=msg.offset(),
            event_type=event_type,
        )

        recipient = _extract_recipient(data, event_type)
        subject = _build_subject(event_type, data)
        context = _build_context(event_type, data)

        start = time.perf_counter()
        try:
            with transaction.atomic():
                notification = Notification.objects.create(
                    event_id=event_id,
                    event_type=event_type,
                    recipient_email=recipient,
                    subject=subject,
                    context=context,
                )
                send_email_notification.delay(str(notification.id))
            self.consumer.commit(message=msg)
            duration = time.perf_counter() - start

            logger.info(
                "kafka_message_processed",
                topic=topic,
                offset=msg.offset(),
                event_type=event_type,
                notification_id=str(notification.id),
                processing_time_ms=round(duration * 1000, 2),
            )
        except IntegrityError:
            self.consumer.commit(message=msg)
            logger.warning(
                "kafka_message_duplicate",
                event_id=event_id,
                event_type=event_type,
                topic=topic,
                offset=msg.offset(),
            )
        except Exception as exc:
            logger.error(
                "kafka_message_failed",
                event_type=event_type,
                event_id=event_id,
                topic=topic,
                offset=msg.offset(),
                error=str(exc),
                exc_info=True,
            )
        finally:
            structlog.contextvars.unbind_contextvars("event_id")
