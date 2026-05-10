import uuid

from django.db import models


class OutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        PUBLISHED = "PUBLISHED"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aggregate_type = models.CharField(max_length=50)
    aggregate_id = models.UUIDField()
    event_type = models.CharField(max_length=100)
    topic = models.CharField(max_length=100)
    key = models.CharField(max_length=100, blank=True)
    payload = models.JSONField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    attempts = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="outbox_pending_idx",
            ),
        ]
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"OutboxEvent({self.event_type}, status={self.status})"
