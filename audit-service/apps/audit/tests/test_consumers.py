import json
from unittest.mock import MagicMock, patch

import pytest
from confluent_kafka import KafkaError

from apps.audit.kafka_consumer import AuditKafkaConsumer
from apps.audit.models import AuditEvent


def make_mock_message(payload: dict | None, topic: str = "policy.created"):
    msg = MagicMock()
    msg.error.return_value = None
    msg.topic.return_value = topic
    if payload is not None:
        msg.value.return_value = json.dumps(payload).encode("utf-8")
    else:
        msg.value.return_value = b"not-valid-json{"
    return msg


@pytest.fixture
def consumer():
    with patch("apps.audit.kafka_consumer.Consumer"):
        c = AuditKafkaConsumer()
    return c


@pytest.mark.django_db
def test_handle_valid_message_saves_event(consumer, policy_payload):
    msg = make_mock_message(policy_payload)
    with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
        consumer._handle(msg)

    assert AuditEvent.objects.filter(event_id=policy_payload["event_id"]).exists()
    consumer._consumer.commit.assert_called_once_with(message=msg)


@pytest.mark.django_db
def test_handle_duplicate_event_commits_offset(consumer, policy_payload):
    msg = make_mock_message(policy_payload)
    with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
        consumer._handle(msg)
        consumer._consumer.commit.reset_mock()
        consumer._handle(msg)

    consumer._consumer.commit.assert_called_once_with(message=msg)


@pytest.mark.django_db
def test_handle_invalid_json_does_not_commit(consumer):
    msg = make_mock_message(None)
    consumer._handle(msg)
    consumer._consumer.commit.assert_not_called()


@pytest.mark.django_db
def test_handle_processing_error_does_not_commit(consumer, policy_payload):
    msg = make_mock_message(policy_payload)
    with patch(
        "apps.audit.services.AuditService.process_event",
        side_effect=RuntimeError("DB down"),
    ):
        consumer._handle(msg)

    consumer._consumer.commit.assert_not_called()


@pytest.mark.django_db
def test_run_processes_message_then_stops(consumer, policy_payload):
    msg = make_mock_message(policy_payload)

    # poll returns: message, then raises KeyboardInterrupt to exit the loop
    consumer._consumer.poll.side_effect = [msg, KeyboardInterrupt]

    with (
        patch("apps.audit.services.AuditService._broadcast_to_websocket"),
        pytest.raises(KeyboardInterrupt),
    ):
        consumer.run()

    consumer._consumer.subscribe.assert_called_once()
    consumer._consumer.close.assert_called_once()
    assert AuditEvent.objects.filter(event_id=policy_payload["event_id"]).exists()


def test_run_skips_none_poll_result(consumer):
    consumer._consumer.poll.side_effect = [None, KeyboardInterrupt]

    with pytest.raises(KeyboardInterrupt):
        consumer.run()

    consumer._consumer.commit.assert_not_called()
    consumer._consumer.close.assert_called_once()


def test_run_skips_partition_eof_error(consumer):
    eof_msg = MagicMock()
    error = MagicMock()
    error.code.return_value = KafkaError._PARTITION_EOF
    eof_msg.error.return_value = error

    consumer._consumer.poll.side_effect = [eof_msg, KeyboardInterrupt]

    with pytest.raises(KeyboardInterrupt):
        consumer.run()

    consumer._consumer.commit.assert_not_called()
    consumer._consumer.close.assert_called_once()
