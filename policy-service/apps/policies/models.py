import uuid

from django.db import connection, models, transaction
from django.utils import timezone


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    dni = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name


def generate_policy_number():
    """Generate the next sequential policy_number.

    On PostgreSQL we use a native SEQUENCE — `nextval()` is lock-free and
    scales linearly with concurrent INSERTs. On SQLite (test backend) we keep
    the legacy `select_for_update()` path: SQLite serializes writes at the
    file level anyway, so contention is not an issue in tests.
    """
    year = timezone.now().year
    prefix = f"POL-{year}-"

    if connection.vendor == "postgresql":
        with connection.cursor() as cur:
            cur.execute("SELECT nextval('policy_number_seq')")
            next_num = cur.fetchone()[0]
        return f"{prefix}{next_num:06d}"

    with transaction.atomic():
        last = (
            Policy.objects.select_for_update()
            .filter(policy_number__startswith=prefix)
            .order_by("-policy_number")
            .first()
        )
        next_num = int(last.policy_number.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_num:06d}"


class Policy(models.Model):
    class PolicyType(models.TextChoices):
        LIFE = "LIFE", "Life Insurance"
        HEALTH = "HEALTH", "Health Insurance"
        AUTO = "AUTO", "Auto Insurance"
        HOME = "HOME", "Home Insurance"
        BUSINESS = "BUSINESS", "Business Insurance"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy_number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="policies"
    )
    policy_type = models.CharField(max_length=20, choices=PolicyType.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    premium_amount = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="idx_policies_status"),
            models.Index(fields=["customer"], name="idx_policies_customer"),
            models.Index(fields=["start_date", "end_date"], name="idx_policies_dates"),
        ]

    def save(self, *args, **kwargs):
        if not self.policy_number:
            self.policy_number = generate_policy_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.policy_number


class Coverage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey(
        Policy, on_delete=models.CASCADE, related_name="coverages"
    )
    coverage_type = models.CharField(max_length=50)
    coverage_amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["coverage_type"]

    def __str__(self):
        return f"{self.coverage_type} — {self.policy.policy_number}"


class PolicyDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey(
        Policy, on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(max_length=50)
    file_url = models.URLField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.document_type} — {self.policy.policy_number}"
