import asyncio

import pytest
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.urls import path

from apps.audit.ws_consumers import AuditEventsConsumer
from apps.audit.ws_middleware import JWTAuthMiddleware


def _make_app():
    return JWTAuthMiddleware(
        URLRouter(
            [
                path("ws/events/", AuditEventsConsumer.as_asgi()),
            ]
        )
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ws_test", password="ws_test")


@pytest.fixture
def valid_token(user):
    from rest_framework_simplejwt.tokens import RefreshToken

    return str(RefreshToken.for_user(user).access_token)


@pytest.mark.django_db
def test_ws_no_token_closes_4001():
    async def _test():
        communicator = WebsocketCommunicator(_make_app(), "/ws/events/")
        connected, code = await communicator.connect()
        assert not connected
        assert code == 4001
        await communicator.disconnect()

    asyncio.run(_test())


@pytest.mark.django_db
def test_ws_invalid_token_closes_4001():
    async def _test():
        communicator = WebsocketCommunicator(
            _make_app(), "/ws/events/?token=invalid.token.here"
        )
        connected, code = await communicator.connect()
        assert not connected
        assert code == 4001
        await communicator.disconnect()

    asyncio.run(_test())


@pytest.mark.django_db
def test_ws_valid_token_accepts_and_receives_broadcast(valid_token):
    async def _test():
        communicator = WebsocketCommunicator(
            _make_app(), f"/ws/events/?token={valid_token}"
        )
        connected, code = await communicator.connect()
        assert connected
        assert code is None

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "audit_events",
            {
                "type": "audit_event",
                "payload": {
                    "event_type": "policy.created",
                    "event_id": "test-123",
                },
            },
        )

        response = await communicator.receive_json_from()
        assert response["event_type"] == "policy.created"
        assert response["event_id"] == "test-123"

        await communicator.disconnect()

    asyncio.run(_test())
