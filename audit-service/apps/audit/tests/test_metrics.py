import json
from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import REGISTRY

from apps.audit.kafka_consumer import AuditKafkaConsumer


def _counter(name: str, labels: dict) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def _make_msg(payload: dict | None, topic: str = "policy.created") -> MagicMock:
    msg = MagicMock()
    msg.error.return_value = None
    msg.topic.return_value = topic
    msg.partition.return_value = 0
    msg.offset.return_value = 0
    msg.value.return_value = (
        json.dumps(payload).encode() if payload is not None else b"not-json{"
    )
    return msg


@pytest.fixture
def consumer():
    with patch("apps.audit.kafka_consumer.Consumer"):
        return AuditKafkaConsumer()


@pytest.mark.django_db
class TestKafkaProcessedCounter:
    def test_ok_label_on_success(self, consumer, policy_payload):
        msg = _make_msg(policy_payload, topic="policy.created")
        before = _counter(
            "riskcore_kafka_messages_processed_total",
            {"topic": "policy.created", "result": "ok"},
        )
        with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
            consumer._handle(msg)
        after = _counter(
            "riskcore_kafka_messages_processed_total",
            {"topic": "policy.created", "result": "ok"},
        )
        assert after == before + 1

    def test_duplicate_label_on_integrity_error(self, consumer, policy_payload):
        msg = _make_msg(policy_payload, topic="policy.created")
        with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
            consumer._handle(msg)  # first → ok

        before = _counter(
            "riskcore_kafka_messages_processed_total",
            {"topic": "policy.created", "result": "duplicate"},
        )
        with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
            consumer._handle(msg)  # second → duplicate
        after = _counter(
            "riskcore_kafka_messages_processed_total",
            {"topic": "policy.created", "result": "duplicate"},
        )
        assert after == before + 1

    def test_error_label_on_processing_exception(self, consumer, policy_payload):
        msg = _make_msg(policy_payload, topic="policy.created")
        before = _counter(
            "riskcore_kafka_messages_processed_total",
            {"topic": "policy.created", "result": "error"},
        )
        with patch(
            "apps.audit.services.AuditService.process_event",
            side_effect=RuntimeError("DB error"),
        ):
            consumer._handle(msg)
        after = _counter(
            "riskcore_kafka_messages_processed_total",
            {"topic": "policy.created", "result": "error"},
        )
        assert after == before + 1

    def test_claim_topic_tracked_separately(self, consumer, claim_payload):
        msg = _make_msg(claim_payload, topic="claim.filed")
        policy_ok_before = _counter(
            "riskcore_kafka_messages_processed_total",
            {"topic": "policy.created", "result": "ok"},
        )
        with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
            consumer._handle(msg)
        assert (
            _counter(
                "riskcore_kafka_messages_processed_total",
                {"topic": "policy.created", "result": "ok"},
            )
            == policy_ok_before
        )


@pytest.mark.django_db
class TestKafkaDurationHistogram:
    def test_count_increments_on_successful_processing(self, consumer, policy_payload):
        msg = _make_msg(policy_payload, topic="policy.created")
        before = _counter(
            "riskcore_kafka_processing_duration_seconds_count",
            {"topic": "policy.created"},
        )
        with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
            consumer._handle(msg)
        after = _counter(
            "riskcore_kafka_processing_duration_seconds_count",
            {"topic": "policy.created"},
        )
        assert after == before + 1

    def test_sum_is_non_negative_after_processing(self, consumer, policy_payload):
        msg = _make_msg(policy_payload, topic="policy.created")
        with patch("apps.audit.services.AuditService._broadcast_to_websocket"):
            consumer._handle(msg)
        total_sum = _counter(
            "riskcore_kafka_processing_duration_seconds_sum",
            {"topic": "policy.created"},
        )
        assert total_sum >= 0
