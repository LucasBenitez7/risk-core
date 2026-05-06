import structlog
from django.core.management.base import BaseCommand

from apps.audit.kafka_consumer import AuditKafkaConsumer

logger = structlog.get_logger()


class Command(BaseCommand):
    help = "Run the Audit Service Kafka consumer"

    def handle(self, *args, **options):
        logger.info("starting_audit_consumer")
        AuditKafkaConsumer().run()
