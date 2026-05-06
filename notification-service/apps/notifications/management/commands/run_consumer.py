from django.core.management.base import BaseCommand

from apps.notifications.kafka_consumer import NotificationKafkaConsumer


class Command(BaseCommand):
    help = "Run the notification service Kafka consumer"

    def handle(self, *args, **options):
        consumer = NotificationKafkaConsumer()
        consumer.run()
