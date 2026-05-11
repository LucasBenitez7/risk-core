import structlog
from django.http import HttpResponse
from django.test import RequestFactory

from apps.core.middleware import RequestIDMiddleware, RequestLoggingMiddleware


def _make_response_fn(capture: list | None = None):
    def get_response(request):
        if capture is not None:
            capture.append(structlog.contextvars.get_contextvars().copy())
        return HttpResponse(status=200)

    return get_response


class TestRequestIDMiddleware:
    def test_generates_request_id_when_header_absent(self):
        request = RequestFactory().get("/")
        ctx = []
        middleware = RequestIDMiddleware(_make_response_fn(ctx))
        response = middleware(request)

        assert ctx[0]["request_id"]
        assert response["X-Request-ID"] == ctx[0]["request_id"]

    def test_propagates_existing_request_id_header(self):
        request = RequestFactory().get("/", HTTP_X_REQUEST_ID="fixed-id-abc")
        ctx = []
        middleware = RequestIDMiddleware(_make_response_fn(ctx))
        response = middleware(request)

        assert ctx[0]["request_id"] == "fixed-id-abc"
        assert response["X-Request-ID"] == "fixed-id-abc"

    def test_clears_stale_contextvars_before_binding(self):
        structlog.contextvars.bind_contextvars(
            request_id="old-id", stale_field="garbage"
        )
        request = RequestFactory().get("/", HTTP_X_REQUEST_ID="fresh-id")
        ctx = []
        middleware = RequestIDMiddleware(_make_response_fn(ctx))
        middleware(request)

        assert ctx[0]["request_id"] == "fresh-id"
        assert "stale_field" not in ctx[0]

    def test_attaches_request_id_to_request_object(self):
        request = RequestFactory().get("/", HTTP_X_REQUEST_ID="req-attr-id")
        middleware = RequestIDMiddleware(_make_response_fn())
        middleware(request)

        assert request.request_id == "req-attr-id"


class TestRequestLoggingMiddleware:
    def test_passes_response_through_unchanged(self):
        request = RequestFactory().get("/health/")
        middleware = RequestLoggingMiddleware(lambda req: HttpResponse(status=204))
        response = middleware(request)

        assert response.status_code == 204
