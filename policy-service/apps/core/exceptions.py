from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        request = context["request"]
        request_id = getattr(request, "request_id", "")

        if isinstance(exc, ValidationError) and isinstance(exc.detail, dict):
            details = {
                field: [str(e) for e in errors] for field, errors in exc.detail.items()
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


class PolicyNotFoundError(APIException):
    status_code = 404
    default_code = "POLICY_NOT_FOUND"
    code = "POLICY_NOT_FOUND"
    details = {}

    def __init__(self, policy_id=None):
        self.details = {"policy_id": str(policy_id)} if policy_id else {}
        super().__init__(detail="La póliza solicitada no existe.")


class CustomerNotFoundError(APIException):
    status_code = 404
    default_code = "CUSTOMER_NOT_FOUND"
    code = "CUSTOMER_NOT_FOUND"
    details = {}

    def __init__(self, customer_id=None):
        self.details = {"customer_id": str(customer_id)} if customer_id else {}
        super().__init__(detail="El cliente solicitado no existe.")


class InvalidPolicyStatusError(APIException):
    status_code = 400
    default_code = "INVALID_POLICY_STATUS"
    code = "INVALID_POLICY_STATUS"
    details = {}

    def __init__(self, policy_id=None, current_status=None, allowed_statuses=None):
        self.details = {
            "policy_id": str(policy_id) if policy_id else None,
            "current_status": current_status,
            "allowed_statuses": allowed_statuses or [],
        }
        super().__init__(
            detail=f"La operación no es válida para una póliza en estado '{current_status}'."
        )
