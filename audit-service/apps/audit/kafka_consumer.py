import json

import structlog
from confluent_kafka import Consumer, KafkaError
from decouple import config
from django.db import IntegrityError

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
            logger.error("invalid_message_format", topic=msg.topic(), error=str(e))
            return

        try:
            self._service.process_event(payload, topic=msg.topic())
            self._consumer.commit(message=msg)
        except IntegrityError:
            logger.warning("duplicate_event", event_id=payload.get("event_id"))
            self._consumer.commit(message=msg)
        except Exception as e:
            logger.error(
                "event_processing_failed",
                error=str(e),
                event_id=payload.get("event_id"),
            )
