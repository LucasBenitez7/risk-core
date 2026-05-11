from django.urls import path

from apps.audit.ws_consumers import AuditEventsConsumer

websocket_urlpatterns = [
    path("ws/events/", AuditEventsConsumer.as_asgi()),
]
