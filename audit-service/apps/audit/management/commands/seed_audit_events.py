import uuid
from datetime import timedelta
from random import choice, randint

import structlog
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import AuditEvent

logger = structlog.get_logger()

ENTITY_TYPES = ["policy", "claim", "customer"]
KAFKA_TOPICS = [
    "policy.created",
    "policy.updated",
    "policy.cancelled",
    "claim.filed",
    "claim.status_changed",
    "claim.resolved",
]
EVENT_TYPES = KAFKA_TOPICS
SERVICES = ["policy-service", "claims-service", "notification-service"]


class Command(BaseCommand):
    help = "Seed audit DB with synthetic events for load testing. Only runs when DEBUG=True."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=10000,
            help="Number of events to seed (default: 10000)",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            logger.info("seed_audit_skipped", reason="DEBUG is False")
            return

        count = options["count"]
        existing = AuditEvent.objects.count()

        if existing >= count:
            logger.info(
                "seed_audit_skipped",
                reason="enough events exist",
                existing=existing,
                requested=count,
            )
            return

        to_create = count - existing
        logger.info("seed_audit_starting", events_to_create=to_create)

        events = []
        base_time = timezone.now() - timedelta(days=90)
        batch_size = 1000

        for _ in range(to_create):
            topic = choice(KAFKA_TOPICS)
            entity_type = "policy" if topic.startswith("policy.") else "claim"

            events.append(
                AuditEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=topic,
                    kafka_topic=topic,
                    entity_type=entity_type,
                    entity_id=uuid.uuid4(),
                    service=choice(SERVICES),
                    occurred_at=base_time
                    + timedelta(hours=randint(0, 90 * 24), seconds=randint(0, 3599)),
                    payload={
                        "event": topic,
                        "entity_id": str(uuid.uuid4()),
                        "timestamp": timezone.now().isoformat(),
                    },
                )
            )

            if len(events) >= batch_size:
                AuditEvent.objects.bulk_create(events)
                events = []

        if events:
            AuditEvent.objects.bulk_create(events)

        final_count = AuditEvent.objects.count()
        logger.info("seed_audit_complete", total_events=final_count)
