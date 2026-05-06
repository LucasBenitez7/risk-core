import uuid
from unittest.mock import MagicMock, patch

import factory
import pytest
from factory.django import DjangoModelFactory

from apps.notifications.models import Notification, NotificationLog


class NotificationFactory(DjangoModelFactory):
    class Meta:
        model = Notification

    id = factory.LazyFunction(uuid.uuid4)
    event_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    event_type = "policy.created"
    recipient_email = factory.Sequence(lambda n: f"user{n}@example.com")
    subject = "Póliza creada"
    context = {"policy_number": "POL-0001"}
    status = Notification.Status.PENDING


class NotificationLogFactory(DjangoModelFactory):
    class Meta:
        model = NotificationLog

    id = factory.LazyFunction(uuid.uuid4)
    notification = factory.SubFactory(NotificationFactory)
    attempt = 1
    status = NotificationLog.Status.SUCCESS
    error_message = ""


@pytest.fixture(autouse=True)
def mock_kafka_consumer():
    with patch("apps.notifications.kafka_consumer.Consumer") as mock:
        consumer_instance = MagicMock()
        consumer_instance.commit = MagicMock()
        mock.return_value = consumer_instance
        yield consumer_instance
