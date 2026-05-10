import uuid
from unittest.mock import MagicMock, patch

import httpx
import pybreaker
import pytest

from apps.claims.clients import PolicyServiceClient, _ClientBusinessError
from apps.core.exceptions import PolicyInactiveError, PolicyServiceUnavailableError


def _make_test_breaker() -> pybreaker.CircuitBreaker:
    return pybreaker.CircuitBreaker(
        fail_max=5,
        reset_timeout=0.01,
        exclude=[_ClientBusinessError],
    )


def _mock_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestPolicyServiceClientCircuitBreaker:
    def test_circuit_opens_after_five_500_errors(self):
        """After 5 consecutive 5xx errors the circuit opens; 6th call is immediate fail-fast."""
        breaker = _make_test_breaker()
        client = PolicyServiceClient(breaker=breaker)
        policy_id = str(uuid.uuid4())

        with patch("apps.claims.clients.httpx.Client") as mock_cls:
            mock_ctx = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_ctx
            mock_ctx.get.return_value = _mock_response(500)

            for _ in range(5):
                with pytest.raises(PolicyServiceUnavailableError):
                    client.verify_policy(policy_id)

            assert mock_ctx.get.call_count == 5

            # Circuit is now open — this must raise without touching the network
            with pytest.raises(PolicyServiceUnavailableError):
                client.verify_policy(policy_id)

            assert mock_ctx.get.call_count == 5, (
                "Open circuit made an unexpected network call"
            )

    def test_404_does_not_open_circuit(self):
        """404s are excluded from the breaker; circuit stays closed after 6 consecutive calls."""
        breaker = _make_test_breaker()
        client = PolicyServiceClient(breaker=breaker)
        policy_id = str(uuid.uuid4())

        with patch("apps.claims.clients.httpx.Client") as mock_cls:
            mock_ctx = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_ctx
            mock_ctx.get.return_value = _mock_response(404)

            for _ in range(6):
                with pytest.raises(PolicyInactiveError):
                    client.verify_policy(policy_id)

            # All 6 calls went through the network — circuit never opened
            assert mock_ctx.get.call_count == 6

    def test_200_with_invalid_policy_does_not_open_circuit(self):
        """A valid HTTP 200 with is_valid=False raises PolicyInactiveError, not a network error."""
        breaker = _make_test_breaker()
        client = PolicyServiceClient(breaker=breaker)
        policy_id = str(uuid.uuid4())

        with patch("apps.claims.clients.httpx.Client") as mock_cls:
            mock_ctx = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_ctx
            mock_ctx.get.return_value = _mock_response(
                200, {"is_valid": False, "status": "CANCELLED"}
            )

            for _ in range(6):
                with pytest.raises(PolicyInactiveError) as exc_info:
                    client.verify_policy(policy_id)
                assert exc_info.value.details["policy_status"] == "CANCELLED"

            assert mock_ctx.get.call_count == 6

    def test_verify_policy_success_returns_data(self):
        """Happy path: valid policy returns the response payload."""
        breaker = _make_test_breaker()
        client = PolicyServiceClient(breaker=breaker)
        policy_id = str(uuid.uuid4())

        with patch("apps.claims.clients.httpx.Client") as mock_cls:
            mock_ctx = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_ctx
            mock_ctx.get.return_value = _mock_response(
                200, {"is_valid": True, "status": "ACTIVE", "policy_id": policy_id}
            )

            result = client.verify_policy(policy_id)

        assert result["is_valid"] is True
        assert result["status"] == "ACTIVE"
