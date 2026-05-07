import uuid

import structlog
from django.db import transaction

from apps.core.exceptions import (
    CustomerNotFoundError,
    InvalidPolicyStatusError,
    PolicyNotFoundError,
)
from apps.core.metrics import policies_cancelled_total, policies_created_total
from apps.policies.models import Coverage, Customer, Policy

logger = structlog.get_logger()


def _get_producer():
    from apps.policies.events import PolicyEventProducer

    return PolicyEventProducer()


class PolicyService:
    CANCELABLE_STATUSES = {Policy.Status.ACTIVE, Policy.Status.SUSPENDED}
    UPDATABLE_STATUSES = {
        Policy.Status.ACTIVE,
        Policy.Status.SUSPENDED,
    }
    UPDATABLE_FIELDS = {
        "premium_amount",
        "start_date",
        "end_date",
        "description",
        "policy_type",
    }

    def create_policy(
        self, data: dict, coverages_data: list[dict] | None = None
    ) -> Policy:
        customer_id = data.get("customer_id")
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist as err:
            raise CustomerNotFoundError(customer_id=customer_id) from err

        with transaction.atomic():
            policy = Policy.objects.create(
                customer=customer,
                policy_type=data["policy_type"],
                premium_amount=data["premium_amount"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                description=data.get("description", ""),
            )

            if coverages_data:
                coverages = [
                    Coverage(
                        policy=policy,
                        coverage_type=c["coverage_type"],
                        coverage_amount=c["coverage_amount"],
                        description=c.get("description", ""),
                    )
                    for c in coverages_data
                ]
                Coverage.objects.bulk_create(coverages)

        _get_producer().produce_policy_created(policy)
        policies_created_total.labels(policy_type=policy.policy_type).inc()
        logger.info(
            "policy_created",
            policy_id=str(policy.id),
            policy_type=policy.policy_type,
            customer_id=str(policy.customer_id),
        )
        return policy

    def cancel_policy(self, policy: Policy, reason: str) -> Policy:
        if policy.status not in self.CANCELABLE_STATUSES:
            raise InvalidPolicyStatusError(
                policy_id=policy.id,
                current_status=policy.status,
                allowed_statuses=list(self.CANCELABLE_STATUSES),
            )

        with transaction.atomic():
            policy = Policy.objects.select_for_update().get(pk=policy.id)
            if policy.status not in self.CANCELABLE_STATUSES:
                raise InvalidPolicyStatusError(
                    policy_id=policy.id,
                    current_status=policy.status,
                    allowed_statuses=list(self.CANCELABLE_STATUSES),
                )
            policy.status = Policy.Status.CANCELLED
            policy.cancellation_reason = reason
            policy.save(update_fields=["status", "cancellation_reason", "updated_at"])

        _get_producer().produce_policy_cancelled(policy)
        policies_cancelled_total.inc()
        logger.info(
            "policy_cancelled",
            policy_id=str(policy.id),
            policy_type=policy.policy_type,
        )
        return policy

    def update_policy(self, policy: Policy, data: dict) -> Policy:
        if policy.status not in self.UPDATABLE_STATUSES:
            raise InvalidPolicyStatusError(
                policy_id=policy.id,
                current_status=policy.status,
                allowed_statuses=list(self.UPDATABLE_STATUSES),
            )

        changed_fields = []
        for field in self.UPDATABLE_FIELDS:
            if field in data:
                setattr(policy, field, data[field])
                changed_fields.append(field)

        if changed_fields:
            changed_fields.append("updated_at")
            policy.save(update_fields=changed_fields)
            _get_producer().produce_policy_updated(policy)

        return policy

    def verify_policy(self, policy_id: uuid.UUID) -> dict:
        try:
            policy = Policy.objects.select_related("customer").get(pk=policy_id)
        except Policy.DoesNotExist as err:
            raise PolicyNotFoundError(policy_id=policy_id) from err

        return {
            "policy_id": str(policy.id),
            "status": policy.status,
            "is_valid": policy.status == Policy.Status.ACTIVE,
            "customer_id": str(policy.customer_id),
            "policy_type": policy.policy_type,
        }

    def get_policies_queryset(
        self,
        queryset=None,
        *,
        status: str | None = None,
        policy_type: str | None = None,
        customer_id: str | None = None,
        start_date_from: str | None = None,
        start_date_to: str | None = None,
    ):
        if queryset is None:
            queryset = Policy.objects.select_related("customer").all()

        if status:
            queryset = queryset.filter(status=status)
        if policy_type:
            queryset = queryset.filter(policy_type=policy_type)
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        if start_date_from:
            queryset = queryset.filter(start_date__gte=start_date_from)
        if start_date_to:
            queryset = queryset.filter(start_date__lte=start_date_to)

        return queryset
