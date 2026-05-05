from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        request = context["request"]
        request_id = getattr(request, "request_id", "")
        response.data = {
            "error": {
                "code": getattr(exc, "code", "INTERNAL_ERROR"),
                "message": str(exc),
                "details": getattr(exc, "details", {}),
            },
            "request_id": request_id,
        }

    return response
