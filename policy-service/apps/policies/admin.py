from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.policies.models import Coverage, Customer, Policy, PolicyDocument


@admin.register(Customer)
class CustomerAdmin(ModelAdmin):
    list_display = ["full_name", "email", "dni", "created_at"]
    search_fields = ["full_name", "email", "dni"]
    readonly_fields = ["id", "created_at", "updated_at"]


class CoverageInline(admin.TabularInline):
    model = Coverage
    extra = 0
    readonly_fields = ["id"]


class PolicyDocumentInline(admin.TabularInline):
    model = PolicyDocument
    extra = 0
    readonly_fields = ["id", "uploaded_at"]


@admin.register(Policy)
class PolicyAdmin(ModelAdmin):
    list_display = [
        "policy_number",
        "customer",
        "policy_type",
        "status",
        "premium_amount",
    ]
    list_filter = ["status", "policy_type"]
    search_fields = ["policy_number", "customer__full_name"]
    readonly_fields = ["id", "policy_number", "created_at", "updated_at"]
    inlines = [CoverageInline, PolicyDocumentInline]
