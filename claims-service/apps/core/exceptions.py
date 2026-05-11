from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        request = context["request"]
        request_id = getattr(request, "request_id", "")

        if isinstance(exc, ValidationError) and isinstance(exc.detail, dict):
            details = {
                field: [
                    str(e) for e in (errors if isinstance(errors, list) else [errors])
                ]
                for field, errors in exc.detail.items()
            }
            message = "Error de validación de los datos enviados."
            code = getattr(exc, "code", "VALIDATION_ERROR")
        else:
            details = getattr(exc, "details", {})
            message = str(exc)
            code = getattr(exc, "code", "INTERNAL_ERROR")

        response.data = {
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
            "request_id": request_id,
        }

    return response


class ClaimNotFoundError(APIException):
    status_code = 404
    default_code = "CLAIM_NOT_FOUND"
    code = "CLAIM_NOT_FOUND"
    details = {}

    def __init__(self, claim_id=None):
        self.details = {"claim_id": str(claim_id)} if claim_id else {}
        super().__init__(detail="El siniestro solicitado no existe.")


class InvalidClaimStatusError(APIException):
    status_code = 400
    default_code = "INVALID_CLAIM_STATUS"
    code = "INVALID_CLAIM_STATUS"
    details = {}

    def __init__(self, claim_id=None, current_status=None, allowed_transitions=None):
        self.details = {
            "claim_id": str(claim_id) if claim_id else None,
            "current_status": current_status,
            "allowed_transitions": allowed_transitions or [],
        }
        super().__init__(
            detail=f"La transición desde el estado '{current_status}' no es válida."
        )


class PolicyServiceUnavailableError(APIException):
    status_code = 503
    default_code = "POLICY_SERVICE_UNAVAILABLE"
    code = "POLICY_SERVICE_UNAVAILABLE"
    details = {}

    def __init__(self, policy_id=None):
        self.details = {"policy_id": str(policy_id)} if policy_id else {}
        super().__init__(
            detail="El servicio de pólizas no está disponible. Intente nuevamente en unos momentos."
        )


class PolicyInactiveError(APIException):
    status_code = 400
    default_code = "POLICY_INACTIVE"
    code = "POLICY_INACTIVE"
    details = {}

    def __init__(self, policy_id=None, policy_status=None):
        self.details = {
            "policy_id": str(policy_id) if policy_id else None,
            "policy_status": policy_status,
        }
        super().__init__(
            detail="No se puede crear un siniestro sobre una póliza que no está activa."
        )
