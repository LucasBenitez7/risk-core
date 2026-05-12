from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.notifications.views import NotificationMetricsView, NotificationViewSet

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("metrics/", NotificationMetricsView.as_view(), name="notification-metrics"),
] + router.urls
