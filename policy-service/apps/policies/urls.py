from rest_framework.routers import DefaultRouter

from apps.policies.views import CustomerViewSet, PolicyViewSet

router = DefaultRouter()
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"policies", PolicyViewSet, basename="policy")

urlpatterns = router.urls
