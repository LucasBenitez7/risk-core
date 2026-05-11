from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.claims.views import ClaimsMetricsView, ClaimViewSet

router = DefaultRouter()
router.register(r"claims", ClaimViewSet, basename="claim")

urlpatterns = [
    path("metrics/", ClaimsMetricsView.as_view(), name="claims-metrics"),
] + router.urls
