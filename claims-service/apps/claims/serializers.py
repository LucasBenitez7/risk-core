from datetime import date

from rest_framework import serializers

from apps.claims.models import Claim, ClaimDocument, ClaimStatusHistory


class ClaimStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimStatusHistory
        fields = ["from_status", "to_status", "changed_at", "notes"]
        read_only_fields = fields


class ClaimDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimDocument
        fields = ["id", "document_type", "file_url", "uploaded_at"]
        read_only_fields = fields


class ClaimSerializer(serializers.ModelSerializer):
    status_history = ClaimStatusHistorySerializer(many=True, read_only=True)
    documents = ClaimDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Claim
        fields = [
            "id",
            "claim_number",
            "policy_id",
            "claimant_name",
            "claimant_email",
            "incident_date",
            "incident_type",
            "description",
            "estimated_damage",
            "approved_amount",
            "location",
            "status",
            "filed_at",
            "updated_at",
            "status_history",
            "documents",
        ]
        read_only_fields = [
            "id",
            "claim_number",
            "status",
            "approved_amount",
            "filed_at",
            "updated_at",
            "status_history",
            "documents",
        ]
        extra_kwargs = {
            "policy_id": {"read_only": False},
        }

    def validate_incident_date(self, value):
        if value > date.today():
            raise serializers.ValidationError(
                "La fecha del incidente no puede ser futura."
            )
        return value


class ClaimListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = [
            "id",
            "claim_number",
            "policy_id",
            "claimant_name",
            "claimant_email",
            "incident_date",
            "incident_type",
            "estimated_damage",
            "status",
            "filed_at",
        ]
        read_only_fields = fields


class ClaimTransitionSerializer(serializers.Serializer):
    new_status = serializers.ChoiceField(choices=Claim.Status.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    approved_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )

    def validate(self, attrs):
        if attrs.get("new_status") == Claim.Status.APPROVED and not attrs.get(
            "approved_amount"
        ):
            raise serializers.ValidationError(
                {
                    "approved_amount": "El monto aprobado es obligatorio al aprobar un siniestro."
                }
            )
        return attrs


class ClaimsMetricsSerializer(serializers.Serializer):
    open_claims = serializers.IntegerField()
    claims_today = serializers.IntegerField()
    claims_by_status = serializers.DictField(child=serializers.IntegerField())
    avg_resolution_days = serializers.FloatField()
