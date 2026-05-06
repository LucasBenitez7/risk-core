import uuid

import structlog
from confluent_kafka import Producer
from django.conf import settings
from django.utils import timezone

from apps.policies.models import Policy

logger = structlog.get_logger()


def _get_producer() -> Producer:
    return Producer({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})


def _delivery_callback(err, msg):
    if err:
        logger.error("kafka_delivery_failed", topic=msg.topic(), error=str(err))
    else:
        logger.info(
            "kafka_delivery_ok",
            topic=msg.topic(),
            partition=msg.partition(),
            offset=msg.offset(),
        )


class PolicyEventProducer:
    def __init__(self):
        self._producer = _get_producer()

    def _produce(self, topic: str, payload: dict) -> None:
        import json

        self._producer.produce(
            topic=topic,
            value=json.dumps(payload).encode("utf-8"),
            key=payload["data"]["policy_id"].encode("utf-8"),
            on_delivery=_delivery_callback,
        )
        self._producer.flush()

    @staticmethod
    def _date_to_str(value) -> str:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    def _build_event(self, event_type: str, policy: Policy) -> dict:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "occurred_at": timezone.now().isoformat(),
            "service": "policy-service",
            "data": {
                "policy_id": str(policy.id),
                "policy_number": policy.policy_number,
                "customer_id": str(policy.customer_id),
                "policy_type": policy.policy_type,
                "status": policy.status,
                "premium_amount": str(policy.premium_amount),
                "start_date": self._date_to_str(policy.start_date),
                "end_date": self._date_to_str(policy.end_date),
            },
        }

    def produce_policy_created(self, policy: Policy) -> None:
        payload = self._build_event("policy.created", policy)
        self._produce("policy.created", payload)
        logger.info(
            "event_produced", event_type="policy.created", policy_id=str(policy.id)
        )

    def produce_policy_updated(self, policy: Policy) -> None:
        payload = self._build_event("policy.updated", policy)
        self._produce("policy.updated", payload)
        logger.info(
            "event_produced", event_type="policy.updated", policy_id=str(policy.id)
        )

    def produce_policy_cancelled(self, policy: Policy) -> None:
        payload = self._build_event("policy.cancelled", policy)
        payload["data"]["cancellation_reason"] = policy.cancellation_reason
        self._produce("policy.cancelled", payload)
        logger.info(
            "event_produced", event_type="policy.cancelled", policy_id=str(policy.id)
        )
