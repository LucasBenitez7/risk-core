from rest_framework import serializers

from apps.notifications.models import Notification, NotificationLog


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = ["id", "attempt", "status", "error_message", "attempted_at"]
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    logs = NotificationLogSerializer(many=True, read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "event_type",
            "recipient_email",
            "subject",
            "context",
            "status",
            "created_at",
            "sent_at",
            "logs",
        ]
        read_only_fields = fields


class NotificationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "event_type",
            "recipient_email",
            "status",
            "created_at",
        ]
        read_only_fields = fields
