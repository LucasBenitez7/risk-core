from rest_framework import serializers

from .models import AuditEvent


class AuditEventListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "event_id",
            "event_type",
            "entity_type",
            "entity_id",
            "service",
            "occurred_at",
        ]
        read_only_fields = fields


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "event_id",
            "event_type",
            "kafka_topic",
            "entity_type",
            "entity_id",
            "service",
            "occurred_at",
            "received_at",
            "payload",
        ]
        read_only_fields = fields
