from rest_framework import serializers

from apps.policies.models import Coverage, Customer, Policy, PolicyDocument


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id",
            "full_name",
            "email",
            "dni",
            "phone",
            "address",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_email(self, value):
        qs = Customer.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un cliente con este email.")
        return value

    def validate_dni(self, value):
        qs = Customer.objects.filter(dni=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un cliente con este DNI.")
        return value


class CoverageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coverage
        fields = ["id", "coverage_type", "coverage_amount", "description"]
        read_only_fields = ["id"]


class PolicyDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyDocument
        fields = ["id", "document_type", "file_url", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


class PolicySerializer(serializers.ModelSerializer):
    coverages = CoverageSerializer(many=True, read_only=True)
    customer_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Policy
        fields = [
            "id",
            "policy_number",
            "customer_id",
            "policy_type",
            "status",
            "premium_amount",
            "start_date",
            "end_date",
            "description",
            "cancellation_reason",
            "coverages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "policy_number",
            "status",
            "cancellation_reason",
            "created_at",
            "updated_at",
        ]

    def validate_premium_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "El monto de prima debe ser mayor a cero."
            )
        return value

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError(
                {"end_date": "La fecha de fin debe ser posterior a la fecha de inicio."}
            )
        return attrs


class PolicyVerifySerializer(serializers.Serializer):
    policy_id = serializers.UUIDField()
    status = serializers.CharField()
    is_valid = serializers.BooleanField()
    customer_id = serializers.UUIDField()


class PolicyCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, allow_blank=False)
