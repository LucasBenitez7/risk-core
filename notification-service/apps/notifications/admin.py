from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.notifications.models import Notification, NotificationLog


class NotificationLogInline(TabularInline):
    model = NotificationLog
    extra = 0
    readonly_fields = ["id", "attempt", "status", "error_message", "attempted_at"]
    can_delete = False
    ordering = ["attempted_at"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = [
        "id",
        "event_type",
        "recipient_email",
        "status",
        "created_at",
        "sent_at",
    ]
    list_filter = ["status", "event_type"]
    search_fields = ["recipient_email", "event_type"]
    readonly_fields = [
        "id",
        "event_type",
        "recipient_email",
        "subject",
        "context",
        "status",
        "created_at",
        "sent_at",
    ]
    inlines = [NotificationLogInline]
    ordering = ["-created_at"]
