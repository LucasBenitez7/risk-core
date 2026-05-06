import httpx
import structlog
from django.conf import settings

from apps.core.exceptions import PolicyInactiveError, PolicyServiceUnavailableError

logger = structlog.get_logger()


class PolicyServiceClient:
    def __init__(self):
        self.base_url = settings.POLICY_SERVICE_URL.rstrip("/")
        self.timeout = settings.POLICY_SERVICE_TIMEOUT

    def verify_policy(self, policy_id: str) -> dict:
        url = f"{self.base_url}/api/policies/policies/{policy_id}/verify/"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise PolicyInactiveError(
                    policy_id=policy_id, policy_status="NOT_FOUND"
                ) from None
            raise PolicyServiceUnavailableError(policy_id=policy_id) from None
        except (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.RequestError,
        ):
            raise PolicyServiceUnavailableError(policy_id=policy_id) from None

        if not data.get("is_valid"):
            raise PolicyInactiveError(
                policy_id=policy_id, policy_status=data.get("status")
            )

        logger.info(
            "policy_verified",
            policy_id=str(policy_id),
            policy_status=data.get("status"),
        )
        return data
