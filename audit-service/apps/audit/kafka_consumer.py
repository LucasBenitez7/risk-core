import json
import time

import structlog
from confluent_kafka import Consumer, KafkaError
from decouple import config
from django.db import IntegrityError

from apps.core.metrics import (
    kafka_messages_processed_total,
    kafka_processing_duration_seconds,
)

from .services import AuditService

logger = structlog.get_logger()

TOPICS = [
    "policy.created",
    "policy.updated",
    "policy.cancelled",
    "claim.filed",
    "claim.status_changed",
    "claim.resolved",
]


class AuditKafkaConsumer:
    def __init__(self):
        self._consumer = Consumer(
            {
                "bootstrap.servers": config(
                    "KAFKA_BOOTSTRAP_SERVERS", default="localhost:9092"
                ),
                "group.id": "audit-service",
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        self._service = AuditService()

    def run(self):
        self._consumer.subscribe(TOPICS)
        logger.info("audit_consumer_started", topics=TOPICS)
        try:
            while True:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("kafka_consumer_error", error=str(msg.error()))
                    continue
                self._handle(msg)
        finally:
            self._consumer.close()

    def _handle(self, msg):
        try:
            payload = json.loads(msg.value().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(
                "invalid_message_format",
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
                error=str(e),
            )
            return

        topic = msg.topic()
        event_id = payload.get("event_id", "")
        event_type = payload.get("event_type", "")

        structlog.contextvars.bind_contextvars(event_id=event_id)
        logger.info(
            "kafka_message_received",
            topic=topic,
            partition=msg.partition(),
            offset=msg.offset(),
            event_type=event_type,
        )

        start = time.perf_counter()
        try:
            self._service.process_event(payload, topic=topic)
            duration = time.perf_counter() - start
            self._consumer.commit(message=msg)
            kafka_messages_processed_total.labels(topic=topic, result="ok").inc()
            kafka_processing_duration_seconds.labels(topic=topic).observe(duration)
            logger.info(
                "kafka_message_processed",
                topic=topic,
                offset=msg.offset(),
                event_type=event_type,
                processing_time_ms=round(duration * 1000, 2),
            )
        except IntegrityError:
            self._consumer.commit(message=msg)
            kafka_messages_processed_total.labels(topic=topic, result="duplicate").inc()
            logger.warning(
                "kafka_message_duplicate",
                event_id=event_id,
                topic=topic,
                offset=msg.offset(),
            )
        except Exception as e:
            kafka_messages_processed_total.labels(topic=topic, result="error").inc()
            logger.error(
                "kafka_message_failed",
                topic=topic,
                offset=msg.offset(),
                event_type=event_type,
                error=str(e),
                exc_info=True,
            )
        finally:
            structlog.contextvars.unbind_contextvars("event_id")
