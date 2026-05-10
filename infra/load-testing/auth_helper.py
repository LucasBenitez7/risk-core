"""
JWT authentication helper shared by all locust scenarios.

Uses locust's @events.init hook to fetch a single JWT token BEFORE any
user greenlets are spawned. This avoids hammering the api_anon rate-limit
zone (20 req/min) during the spawn phase.

Usage in each scenario:
    from auth_helper import register_auth_hook, shared_token

    @events.init.add_listener
    def on_init(environment, **kwargs):
        register_auth_hook(environment)

    class MyUser(HttpUser):
        def on_start(self):
            self.client.headers["Authorization"] = f"Bearer {shared_token()}"
"""

import os

import requests as _requests

AUTH_USERNAME = os.getenv("LOAD_TEST_USER", "admin")
AUTH_PASSWORD = os.getenv("LOAD_TEST_PASSWORD", "admin")

_token: str | None = None


def shared_token() -> str:
    """Return the pre-fetched JWT. Raises if register_auth_hook wasn't called."""
    if _token is None:
        raise RuntimeError("shared_token() called before register_auth_hook()")
    return _token


def register_auth_hook(environment) -> None:
    """Register an events.init listener that fetches the JWT once at test startup.

    Call this at module level in each scenario file:
        @events.init.add_listener
        def on_init(environment, **kwargs):
            register_auth_hook(environment)
    """

    @environment.events.init.add_listener
    def _fetch_token(environment, **kwargs):  # noqa: ARG001
        global _token
        host = environment.host or "http://localhost:8080"
        url = f"{host}/api/auth/token/"
        # Pass Host: localhost so nginx forwards it to Django's ALLOWED_HOSTS
        # (the locust container resolves 'gateway' but Django rejects that hostname)
        resp = _requests.post(
            url,
            json={"username": AUTH_USERNAME, "password": AUTH_PASSWORD},
            headers={"Host": "localhost"},
            timeout=10,
        )
        if resp.status_code != 200:
            raise SystemExit(
                f"Cannot obtain JWT at startup ({resp.status_code}): {resp.text[:200]}"
            )
        _token = resp.json()["access"]
