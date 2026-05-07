import io
import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory

from apps.core.middleware import RequestIDMiddleware, RequestLoggingMiddleware


def _make_stack(inner):
    return RequestIDMiddleware(RequestLoggingMiddleware(inner))


def _capture_json_logs(fn):
    """Run fn and return all JSON log lines emitted to the root logger."""
    buf = io.StringIO()
    root = logging.getLogger()
    old_handlers = root.handlers[:]

    # Reuse the formatter already configured by structlog
    formatter = old_handlers[0].formatter if old_handlers else None
    handler = logging.StreamHandler(buf)
    if formatter:
        handler.setFormatter(formatter)
    root.handlers = [handler]

    try:
        fn()
    finally:
        root.handlers = old_handlers

    lines = [ln for ln in buf.getvalue().strip().splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def test_request_log_emits_valid_json():
    request = RequestFactory().get("/health/")
    logs = _capture_json_logs(
        lambda: _make_stack(lambda req: HttpResponse(status=200))(request)
    )
    assert logs, "No log output captured"
    last = logs[-1]
    assert last.get("event") == "request_finished"


def test_request_log_contains_required_keys():
    request = RequestFactory().get("/health/", HTTP_X_REQUEST_ID="test-req-id")
    logs = _capture_json_logs(
        lambda: _make_stack(lambda req: HttpResponse(status=200))(request)
    )
    last = logs[-1]
    for key in ("timestamp", "level", "service", "event", "request_id"):
        assert key in last, f"Missing key '{key}' in log: {last}"


def test_request_log_service_matches_settings():
    request = RequestFactory().get("/health/")
    logs = _capture_json_logs(
        lambda: _make_stack(lambda req: HttpResponse(status=200))(request)
    )
    assert logs[-1]["service"] == settings.SERVICE_NAME


def test_request_log_propagates_request_id():
    request = RequestFactory().get("/health/", HTTP_X_REQUEST_ID="propagated-id")
    logs = _capture_json_logs(
        lambda: _make_stack(lambda req: HttpResponse(status=200))(request)
    )
    assert logs[-1]["request_id"] == "propagated-id"


def test_request_log_contains_http_fields():
    request = RequestFactory().get("/health/")
    logs = _capture_json_logs(
        lambda: _make_stack(lambda req: HttpResponse(status=204))(request)
    )
    last = logs[-1]
    assert last["method"] == "GET"
    assert last["path"] == "/health/"
    assert last["status_code"] == 204
    assert isinstance(last["duration_ms"], float)
