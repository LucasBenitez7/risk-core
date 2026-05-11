from urllib.parse import parse_qs

import structlog
from channels.db import database_sync_to_async
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = structlog.get_logger()


@database_sync_to_async
def _validate_jwt(token_str: str) -> str | None:
    try:
        token = AccessToken(token_str)
        return str(token["user_id"])
    except (InvalidToken, TokenError, KeyError):
        return None


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]

        if token:
            user_id = await _validate_jwt(token)
            if user_id is not None:
                scope["user_id"] = user_id
                logger.debug("ws_auth_success", user_id=user_id)
            else:
                logger.warning("ws_auth_invalid_token")
        else:
            logger.debug("ws_auth_no_token")

        return await self.inner(scope, receive, send)
