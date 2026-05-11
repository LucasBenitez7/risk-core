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


class NotificationNotFoundError(APIException):
    status_code = 404
    default_code = "NOTIFICATION_NOT_FOUND"
    code = "NOTIFICATION_NOT_FOUND"
    details = {}

    def __init__(self, notification_id=None):
        self.details = (
            {"notification_id": str(notification_id)} if notification_id else {}
        )
        super().__init__(detail="La notificación solicitada no existe.")
