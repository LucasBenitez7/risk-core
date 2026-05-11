from django.http import Http404
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from apps.core.exceptions import AuditEventNotFoundError

from .models import AuditEvent
from .serializers import AuditEventListSerializer, AuditEventSerializer


class AuditEventViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = [AllowAny]
    queryset = AuditEvent.objects.all()

    def get_serializer_class(self):
        if self.action == "list":
            return AuditEventListSerializer
        return AuditEventSerializer

    def get_queryset(self):
        qs = AuditEvent.objects.all()
        params = self.request.query_params

        if event_type := params.get("event_type"):
            qs = qs.filter(event_type=event_type)
        if entity_type := params.get("entity_type"):
            qs = qs.filter(entity_type=entity_type)
        if entity_id := params.get("entity_id"):
            qs = qs.filter(entity_id=entity_id)
        if kafka_topic := params.get("kafka_topic"):
            qs = qs.filter(kafka_topic=kafka_topic)
        if from_date := params.get("from_date"):
            qs = qs.filter(occurred_at__date__gte=from_date)
        if to_date := params.get("to_date"):
            qs = qs.filter(occurred_at__date__lte=to_date)

        return qs

    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            raise AuditEventNotFoundError(event_id=self.kwargs.get("pk")) from None
