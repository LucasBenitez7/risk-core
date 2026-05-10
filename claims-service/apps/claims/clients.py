import httpx
import pybreaker
import structlog
from django.conf import settings

from apps.core.exceptions import PolicyInactiveError, PolicyServiceUnavailableError
from apps.core.metrics import circuit_breaker_state, circuit_breaker_state_changes_total

logger = structlog.get_logger()


class _ClientBusinessError(Exception):
    """4xx errors — not infra failures, excluded from circuit breaker count."""

    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self.data = data


class _BreakerMetrics(pybreaker.CircuitBreakerListener):
    """Emits Prometheus metrics on every circuit breaker state change."""

    def state_change(self, cb, old_state, new_state):
        circuit_breaker_state.labels(target="policy-service").set(
            {"closed": 0, "open": 1, "half-open": 2}[new_state.name]
        )
        circuit_breaker_state_changes_total.labels(
            target="policy-service",
            from_state=old_state.name,
            to_state=new_state.name,
        ).inc()


_policy_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    exclude=[_ClientBusinessError],
    listeners=[_BreakerMetrics()],
)


class PolicyServiceClient:
    def __init__(self, breaker=None):
        self.base_url = settings.POLICY_SERVICE_URL.rstrip("/")
        self.timeout = settings.POLICY_SERVICE_TIMEOUT
        self._breaker = breaker if breaker is not None else _policy_breaker

    def _http_verify(self, policy_id: str) -> dict:
        """Raw HTTP call — the circuit breaker wraps this via verify_policy."""
        url = f"{self.base_url}/api/policies/policies/{policy_id}/verify/"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if 400 <= e.response.status_code < 500:
                    raise _ClientBusinessError(
                        e.response.status_code, e.response.json()
                    ) from e
                raise  # 5xx counts as infra failure for the breaker
            return response.json()

    def verify_policy(self, policy_id: str) -> dict:
        try:
            data = self._breaker.call(self._http_verify, policy_id)
        except pybreaker.CircuitBreakerError:
            logger.warning("policy_circuit_open", policy_id=str(policy_id))
            raise PolicyServiceUnavailableError(policy_id=policy_id) from None
        except _ClientBusinessError as e:
            if e.status_code == 404:
                raise PolicyInactiveError(
                    policy_id=policy_id, policy_status="NOT_FOUND"
                ) from None
            raise PolicyServiceUnavailableError(policy_id=policy_id) from None
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError):
            raise PolicyServiceUnavailableError(policy_id=policy_id) from None

        if not data.get("is_valid"):
            raise PolicyInactiveError(
                policy_id=policy_id, policy_status=data.get("status")
            )
        logger.info("policy_verified", policy_id=str(policy_id))
        return data
