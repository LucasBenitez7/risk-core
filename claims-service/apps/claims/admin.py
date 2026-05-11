from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.claims.models import Claim, ClaimDocument, ClaimStatusHistory


class ClaimStatusHistoryInline(TabularInline):
    model = ClaimStatusHistory
    extra = 0
    readonly_fields = ["from_status", "to_status", "changed_at", "notes"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class ClaimDocumentInline(TabularInline):
    model = ClaimDocument
    extra = 0
    readonly_fields = ["document_type", "file_url", "uploaded_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Claim)
class ClaimAdmin(ModelAdmin):
    list_display = [
        "claim_number",
        "policy_id",
        "claimant_name",
        "status",
        "incident_type",
        "estimated_damage",
        "filed_at",
    ]
    list_filter = ["status", "incident_type"]
    search_fields = ["claim_number", "claimant_name", "claimant_email"]
    readonly_fields = [
        "id",
        "claim_number",
        "policy_id",
        "filed_at",
        "updated_at",
    ]
    inlines = [ClaimStatusHistoryInline, ClaimDocumentInline]
    ordering = ["-filed_at"]
