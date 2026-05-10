import threading
import uuid
from unittest.mock import MagicMock

import pytest
from django.db import transaction

from apps.outbox.management.commands.run_outbox_relay import (
    BATCH_SIZE,
    MAX_ATTEMPTS,
    Command,
)
from apps.outbox.models import OutboxEvent


@pytest.mark.django_db
class TestOutboxEventModel:
    def test_create_outbox_event(self):
        event = OutboxEvent.objects.create(
            aggregate_type="claim",
            aggregate_id=uuid.uuid4(),
            event_type="claim.filed",
            topic="claim.filed",
            key=str(uuid.uuid4()),
            payload={"test": "data"},
        )
        assert event.status == OutboxEvent.Status.PENDING
        assert event.attempts == 0
        assert event.published_at is None
        assert str(event) == "OutboxEvent(claim.filed, status=PENDING)"

    def test_partial_index_exists(self):
        OutboxEvent.objects.create(
            aggregate_type="claim",
            aggregate_id=uuid.uuid4(),
            event_type="claim.filed",
            topic="claim.filed",
            payload={},
        )
        indexes = [
            idx.name
            for idx in OutboxEvent._meta.indexes
            if "pending" in idx.name.lower()
        ]
        assert "outbox_pending_idx" in indexes


@pytest.mark.django_db
class TestRollbackGuarantee:
    def test_rollback_prevents_outbox_event(self):
        try:
            with transaction.atomic():
                OutboxEvent.objects.create(
                    aggregate_type="claim",
                    aggregate_id=uuid.uuid4(),
                    event_type="claim.filed",
                    topic="claim.filed",
                    payload={"test": "data"},
                )
                raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass

        assert OutboxEvent.objects.count() == 0


@pytest.mark.django_db
class TestRelayProcessBatch:
    def test_publishes_pending_events(self):
        event = OutboxEvent.objects.create(
            aggregate_type="claim",
            aggregate_id=uuid.uuid4(),
            event_type="claim.filed",
            topic="claim.filed",
            key=str(uuid.uuid4()),
            payload={"data": "test"},
        )

        mock_producer = MagicMock()
        cmd = Command()
        result = cmd._process_batch(mock_producer)

        assert result == 1
        event.refresh_from_db()
        assert event.status == OutboxEvent.Status.PUBLISHED
        assert event.published_at is not None
        mock_producer.produce.assert_called_once()
        mock_producer.flush.assert_called_once()

    def test_empty_batch_returns_zero(self):
        mock_producer = MagicMock()
        cmd = Command()
        result = cmd._process_batch(mock_producer)
        assert result == 0
        mock_producer.produce.assert_not_called()

    def test_failed_produce_increments_attempts(self):
        event = OutboxEvent.objects.create(
            aggregate_type="claim",
            aggregate_id=uuid.uuid4(),
            event_type="claim.filed",
            topic="claim.filed",
            payload={},
        )

        mock_producer = MagicMock()
        mock_producer.produce.side_effect = Exception("Kafka down")

        cmd = Command()
        cmd._process_batch(mock_producer)

        event.refresh_from_db()
        assert event.attempts == 1
        assert event.last_error == "Kafka down"
        assert event.status == OutboxEvent.Status.PENDING

    def test_max_attempts_marks_as_failed(self):
        event = OutboxEvent.objects.create(
            aggregate_type="claim",
            aggregate_id=uuid.uuid4(),
            event_type="claim.filed",
            topic="claim.filed",
            payload={},
            attempts=MAX_ATTEMPTS - 1,
        )

        mock_producer = MagicMock()
        mock_producer.produce.side_effect = Exception("Permanent failure")

        cmd = Command()
        cmd._process_batch(mock_producer)

        event.refresh_from_db()
        assert event.status == OutboxEvent.Status.FAILED
        assert event.attempts == MAX_ATTEMPTS

    def test_respects_batch_size(self):
        for _ in range(BATCH_SIZE + 10):
            OutboxEvent.objects.create(
                aggregate_type="claim",
                aggregate_id=uuid.uuid4(),
                event_type="claim.filed",
                topic="claim.filed",
                payload={},
            )

        mock_producer = MagicMock()
        cmd = Command()
        result = cmd._process_batch(mock_producer)

        assert result == BATCH_SIZE
        assert (
            OutboxEvent.objects.filter(status=OutboxEvent.Status.PENDING).count() == 10
        )

    def test_produce_called_with_correct_args(self):
        aggregate_id = uuid.uuid4()
        OutboxEvent.objects.create(
            aggregate_type="claim",
            aggregate_id=aggregate_id,
            event_type="claim.filed",
            topic="claim.filed",
            key=str(aggregate_id),
            payload={"event_id": "test-123"},
        )

        mock_producer = MagicMock()
        cmd = Command()
        cmd._process_batch(mock_producer)

        call_kwargs = mock_producer.produce.call_args.kwargs
        assert call_kwargs["topic"] == "claim.filed"
        assert call_kwargs["key"] == str(aggregate_id).encode("utf-8")


@pytest.mark.django_db
class TestConcurrency:
    def test_skip_locked_prevents_double_publish(self):
        from django.conf import settings

        if "sqlite3" in settings.DATABASES["default"]["ENGINE"]:
            pytest.skip("SQLite does not support select_for_update(skip_locked)")

        OutboxEvent.objects.create(
            aggregate_type="claim",
            aggregate_id=uuid.uuid4(),
            event_type="claim.filed",
            topic="claim.filed",
            payload={},
        )

        results = {"thread1": 0, "thread2": 0}
        errors = {"thread1": None, "thread2": None}

        def run_relay(thread_name):
            try:
                mock_producer = MagicMock()
                cmd = Command()
                results[thread_name] = cmd._process_batch(mock_producer)
            except Exception as e:
                errors[thread_name] = e

        t1 = threading.Thread(target=run_relay, args=("thread1",))
        t2 = threading.Thread(target=run_relay, args=("thread2",))

        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        total_published = results["thread1"] + results["thread2"]
        assert total_published == 1
        assert errors["thread1"] is None or errors["thread2"] is None
