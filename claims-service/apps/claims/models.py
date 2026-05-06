import uuid

from django.db import models, transaction
from django.utils import timezone


def generate_claim_number():
    year = timezone.now().year
    prefix = f"CLM-{year}-"

    with transaction.atomic():
        last = (
            Claim.objects.select_for_update()
            .filter(claim_number__startswith=prefix)
            .order_by("-claim_number")
            .first()
        )
        if last:
            last_num = int(last.claim_number.split("-")[-1])
            next_num = last_num + 1
        else:
            next_num = 1

    return f"{prefix}{next_num:06d}"


class Claim(models.Model):
    class IncidentType(models.TextChoices):
        ACCIDENTE = "ACCIDENTE", "Accidente"
        ROBO = "ROBO", "Robo"
        INCENDIO = "INCENDIO", "Incendio"
        INUNDACION = "INUNDACION", "Inundación"
        OTRO = "OTRO", "Otro"

    class Status(models.TextChoices):
        FILED = "FILED", "Filed"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        RESOLVED = "RESOLVED", "Resolved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim_number = models.CharField(max_length=20, unique=True)
    policy_id = models.UUIDField(editable=False)
    claimant_name = models.CharField(max_length=255)
    claimant_email = models.EmailField()
    incident_date = models.DateField()
    incident_type = models.CharField(max_length=20, choices=IncidentType.choices)
    description = models.TextField()
    estimated_damage = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.FILED
    )
    filed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-filed_at"]
        indexes = [
            models.Index(fields=["status"], name="idx_claims_status"),
            models.Index(fields=["policy_id"], name="idx_claims_policy_id"),
            models.Index(fields=["filed_at"], name="idx_claims_filed_at"),
            models.Index(fields=["incident_type"], name="idx_claims_incident_type"),
        ]

    def save(self, *args, **kwargs):
        if not self.claim_number:
            self.claim_number = generate_claim_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.claim_number


class ClaimStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim = models.ForeignKey(
        Claim, on_delete=models.CASCADE, related_name="status_history"
    )
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20)
    changed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["changed_at"]
        indexes = [
            models.Index(fields=["claim", "changed_at"], name="idx_history_claim_date"),
        ]

    def __str__(self):
        return f"{self.claim.claim_number}: {self.from_status} → {self.to_status}"


class ClaimDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=50)
    file_url = models.URLField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.document_type} — {self.claim.claim_number}"
