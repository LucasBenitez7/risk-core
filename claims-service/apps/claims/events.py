import json
import uuid

import structlog
from confluent_kafka import Producer
from django.conf import settings
from django.utils import timezone

from apps.claims.models import Claim

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


class ClaimEventProducer:
    def __init__(self):
        self._producer = _get_producer()

    def _produce(self, topic: str, payload: dict) -> None:
        try:
            self._producer.produce(
                topic=topic,
                value=json.dumps(payload).encode("utf-8"),
                key=payload["data"]["claim_id"].encode("utf-8"),
                on_delivery=_delivery_callback,
            )
            self._producer.flush(timeout=3)
        except Exception:
            logger.warning(
                "kafka_produce_failed",
                event_type=payload.get("event_type"),
                claim_id=payload["data"].get("claim_id"),
            )

    def _build_base_data(self, claim: Claim) -> dict:
        return {
            "claim_id": str(claim.id),
            "claim_number": claim.claim_number,
            "policy_id": str(claim.policy_id),
            "status": claim.status,
            "incident_type": claim.incident_type,
            "claimant_email": claim.claimant_email,
        }

    def _build_event(self, event_type: str, data: dict) -> dict:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "occurred_at": timezone.now().isoformat(),
            "service": "claims-service",
            "data": data,
        }

    def produce_claim_filed(self, claim: Claim) -> None:
        data = self._build_base_data(claim)
        data["estimated_damage"] = str(claim.estimated_damage)
        payload = self._build_event("claim.filed", data)
        self._produce("claim.filed", payload)
        logger.info("event_produced", event_type="claim.filed", claim_id=str(claim.id))

    def produce_claim_status_changed(self, claim: Claim, from_status: str) -> None:
        data = self._build_base_data(claim)
        data["from_status"] = from_status
        data["to_status"] = claim.status
        if claim.approved_amount is not None:
            data["approved_amount"] = str(claim.approved_amount)
        payload = self._build_event("claim.status_changed", data)
        self._produce("claim.status_changed", payload)
        logger.info(
            "event_produced",
            event_type="claim.status_changed",
            claim_id=str(claim.id),
            from_status=from_status,
            to_status=claim.status,
        )

    def produce_claim_resolved(self, claim: Claim) -> None:
        data = self._build_base_data(claim)
        if claim.approved_amount is not None:
            data["approved_amount"] = str(claim.approved_amount)
        payload = self._build_event("claim.resolved", data)
        self._produce("claim.resolved", payload)
        logger.info(
            "event_produced", event_type="claim.resolved", claim_id=str(claim.id)
        )
