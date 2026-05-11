from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(ModelAdmin):
    list_display = ["event_type", "entity_type", "entity_id", "service", "occurred_at"]
    list_filter = ["event_type", "entity_type", "kafka_topic"]
    search_fields = ["event_id", "entity_id"]
    readonly_fields = [
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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
