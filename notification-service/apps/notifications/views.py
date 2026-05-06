from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet

from apps.core.exceptions import NotificationNotFoundError
from apps.core.pagination import StandardPagination
from apps.notifications.models import Notification
from apps.notifications.serializers import (
    NotificationListSerializer,
    NotificationSerializer,
)


class NotificationViewSet(RetrieveModelMixin, ListModelMixin, GenericViewSet):
    pagination_class = StandardPagination
    http_method_names = ["get", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return NotificationListSerializer
        return NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.all()
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        event_type = self.request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)
        return qs

    def get_object(self):
        queryset = self.get_queryset()
        pk = self.kwargs.get("pk")
        try:
            return queryset.get(pk=pk)
        except (Notification.DoesNotExist, ValueError):
            raise NotificationNotFoundError(notification_id=pk) from None
