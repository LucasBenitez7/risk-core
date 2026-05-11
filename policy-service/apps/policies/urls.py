from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.policies.views import CustomerViewSet, PolicyMetricsView, PolicyViewSet

router = DefaultRouter()
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"policies", PolicyViewSet, basename="policy")

urlpatterns = [
    path("metrics/", PolicyMetricsView.as_view(), name="policy-metrics"),
] + router.urls
