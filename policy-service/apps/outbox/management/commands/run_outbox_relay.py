import json
import time

import structlog
from confluent_kafka import Producer
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.metrics import (
    outbox_failed_total,
    outbox_lag_seconds,
    outbox_pending,
    outbox_published_total,
)
from apps.outbox.models import OutboxEvent

logger = structlog.get_logger()

BATCH_SIZE = 100
POLL_INTERVAL = 0.5
MAX_ATTEMPTS = 10


class Command(BaseCommand):
    help = "Outbox relay: publica OutboxEvents PENDING a Kafka."

    def handle(self, *args, **opts):
        producer = Producer({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})
        logger.info("outbox_relay_started")
        try:
            while True:
                published = self._process_batch(producer)
                if published == 0:
                    time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info("outbox_relay_stopped")
            producer.flush(10)

    def _process_batch(self, producer) -> int:
        with transaction.atomic():
            events = list(
                OutboxEvent.objects.select_for_update(skip_locked=True)
                .filter(status=OutboxEvent.Status.PENDING)
                .order_by("created_at")[:BATCH_SIZE]
            )
            if not events:
                return 0

            published_count = 0
            for event in events:
                try:
                    producer.produce(
                        topic=event.topic,
                        value=json.dumps(event.payload).encode("utf-8"),
                        key=(event.key or str(event.aggregate_id)).encode("utf-8"),
                    )
                    event.status = OutboxEvent.Status.PUBLISHED
                    event.published_at = timezone.now()
                    published_count += 1
                    outbox_published_total.labels(topic=event.topic).inc()
                    lag = (event.published_at - event.created_at).total_seconds()
                    outbox_lag_seconds.observe(lag)
                except Exception as e:
                    event.attempts += 1
                    event.last_error = str(e)[:1000]
                    if event.attempts >= MAX_ATTEMPTS:
                        event.status = OutboxEvent.Status.FAILED
                        outbox_failed_total.labels(topic=event.topic).inc()
                    logger.error(
                        "outbox_publish_failed",
                        event_id=str(event.id),
                        attempts=event.attempts,
                        error=str(e),
                    )
                event.save(
                    update_fields=["status", "published_at", "attempts", "last_error"]
                )

            producer.flush(5)

        self._update_pending_metric()
        return published_count

    def _update_pending_metric(self):
        count = OutboxEvent.objects.filter(status=OutboxEvent.Status.PENDING).count()
        outbox_pending.set(count)
