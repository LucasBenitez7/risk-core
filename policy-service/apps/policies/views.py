from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.core.pagination import StandardPagination
from apps.policies.models import Customer
from apps.policies.serializers import (
    CustomerSerializer,
    PolicyCancelSerializer,
    PolicyMetricsSerializer,
    PolicySerializer,
    PolicyVerifySerializer,
)
from apps.policies.services import PolicyService


class PolicyMetricsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = PolicyService().get_metrics()
        return Response(PolicyMetricsSerializer(data).data)


class CustomerViewSet(
    RetrieveModelMixin, CreateModelMixin, ListModelMixin, GenericViewSet
):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    pagination_class = StandardPagination


class PolicyViewSet(ModelViewSet):
    serializer_class = PolicySerializer
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return PolicyService().get_policies_queryset(
            status=self.request.query_params.get("status"),
            policy_type=self.request.query_params.get("policy_type"),
            customer_id=self.request.query_params.get("customer_id"),
            start_date_from=self.request.query_params.get("start_date_from"),
            start_date_to=self.request.query_params.get("start_date_to"),
        )

    def create(self, request, *args, **kwargs):
        serializer = PolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        policy = PolicyService().create_policy(serializer.validated_data)
        return Response(PolicySerializer(policy).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        policy = self.get_object()
        serializer = PolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        policy = PolicyService().update_policy(policy, serializer.validated_data)
        return Response(PolicySerializer(policy).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        policy = self.get_object()
        serializer = PolicyCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        policy = PolicyService().cancel_policy(
            policy, reason=serializer.validated_data["reason"]
        )
        return Response(PolicySerializer(policy).data)

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
    def verify(self, request, pk=None):
        result = PolicyService().verify_policy(policy_id=pk)
        return Response(PolicyVerifySerializer(result).data)
