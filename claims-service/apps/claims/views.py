from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from apps.claims.models import Claim
from apps.claims.serializers import (
    ClaimListSerializer,
    ClaimSerializer,
    ClaimsMetricsSerializer,
    ClaimTransitionSerializer,
)
from apps.claims.services import ClaimService
from apps.core.exceptions import ClaimNotFoundError
from apps.core.pagination import StandardPagination


class ClaimsMetricsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = ClaimService().get_metrics()
        return Response(ClaimsMetricsSerializer(data).data)


class ClaimViewSet(
    RetrieveModelMixin, CreateModelMixin, ListModelMixin, GenericViewSet
):
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return ClaimListSerializer
        return ClaimSerializer

    def get_queryset(self):
        return ClaimService().get_claims_queryset(
            status=self.request.query_params.get("status"),
            policy_id=self.request.query_params.get("policy_id"),
            incident_type=self.request.query_params.get("incident_type"),
        )

    def get_object(self):
        queryset = self.get_queryset()
        pk = self.kwargs.get("pk")
        try:
            return queryset.get(pk=pk)
        except (Claim.DoesNotExist, ValueError):
            raise ClaimNotFoundError(claim_id=pk) from None

    def create(self, request, *args, **kwargs):
        serializer = ClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        claim = ClaimService().file_claim(serializer.validated_data)
        return Response(ClaimSerializer(claim).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        claim = self.get_object()
        serializer = ClaimTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        claim = ClaimService().transition_status(
            claim=claim,
            new_status=serializer.validated_data["new_status"],
            notes=serializer.validated_data.get("notes", ""),
            approved_amount=serializer.validated_data.get("approved_amount"),
        )
        return Response(ClaimSerializer(claim).data)
