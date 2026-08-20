from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts.alert_channel_canary import (
    EndpointContractError,
    evaluate,
    infer_mode,
    validate_endpoint,
)


class _Handler(BaseHTTPRequestHandler):
    status = 204
    response = b""
    delay = 0.0
    received: list[dict[str, object]] = []

    def do_POST(self) -> None:  # noqa: N802
        if type(self).delay:
            time.sleep(type(self).delay)
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length)
        type(self).received.append(
            {
                "path": self.path,
                "headers": {key.lower(): value for key, value in self.headers.items()},
                "body": body,
            }
        )
        self.send_response(type(self).status)
        self.end_headers()
        self.wfile.write(type(self).response)

    def log_message(self, *_args: object) -> None:
        return


@contextmanager
def _server(*, status: int = 204, response: bytes = b"", delay: float = 0.0):
    class Handler(_Handler):
        pass

    Handler.status = status
    Handler.response = response
    Handler.delay = delay
    Handler.received = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}/private-webhook-path", Handler
    finally:
        httpd.shutdown()
        thread.join(timeout=3)


def test_missing_secret_is_terminal_without_an_attempt() -> None:
    result = evaluate(url=None, should_send=True)
    assert result.state == "MISSING"
    assert result.attempt_count == 0
    assert result.secret_value_recorded is False


def test_presence_only_cannot_claim_delivery_health() -> None:
    with _server() as (url, _):
        result = evaluate(
            url=url,
            should_send=False,
            requested_mode="ntfy",
            allow_insecure_loopback=True,
        )
    assert result.state == "PRESENT_UNPROBED"
    assert result.canary_attempted is False
    assert "cannot close" in (result.error_detail or "")


def test_protocol_auto_detection() -> None:
    assert infer_mode("https://hooks.slack.com/services/a/b/c") == "slack"
    assert infer_mode("https://ntfy.sh/a11oy-uptime") == "ntfy"
    assert infer_mode("https://a11oy.net/alerts") == "ntfy"
    assert infer_mode("https://alerts.invalid/hook") == "generic-json"


def test_non_https_production_and_embedded_credentials_are_rejected() -> None:
    with pytest.raises(EndpointContractError):
        validate_endpoint("http://alerts.invalid/hook")
    with pytest.raises(EndpointContractError):
        validate_endpoint("https://user:pass@alerts.invalid/hook")


def test_slack_request_is_json() -> None:
    with _server() as (url, handler):
        result = evaluate(
            url=url,
            should_send=True,
            requested_mode="slack",
            allow_insecure_loopback=True,
        )
        received = handler.received[0]
    assert result.state == "HEALTHY"
    assert str(received["headers"]["content-type"]).startswith("application/json")
    assert "text" in json.loads(received["body"])


def test_ntfy_request_is_text_with_ntfy_headers() -> None:
    with _server() as (url, handler):
        result = evaluate(
            url=url,
            should_send=True,
            requested_mode="ntfy",
            allow_insecure_loopback=True,
        )
        received = handler.received[0]
    assert result.state == "HEALTHY"
    assert str(received["headers"]["content-type"]).startswith("text/plain")
    assert received["headers"]["title"] == "SZL alert-channel canary"


def test_502_remains_failing_and_receipt_omits_url_path() -> None:
    with _server(status=502, response=b"bad gateway") as (url, _):
        result = evaluate(
            url=url,
            should_send=True,
            requested_mode="ntfy",
            allow_insecure_loopback=True,
        )
    payload = json.dumps(result.to_dict())
    assert result.state == "FAILING"
    assert result.http_status == 502
    assert "private-webhook-path" not in payload
    assert url not in payload


def test_timeout_is_terminal_with_one_attempt() -> None:
    with _server(delay=0.3) as (url, _):
        result = evaluate(
            url=url,
            should_send=True,
            requested_mode="generic-json",
            timeout_seconds=0.05,
            allow_insecure_loopback=True,
        )
    assert result.state in {"TIMED_OUT", "UNAVAILABLE"}
    assert result.attempt_count == 1


def test_response_size_is_bounded() -> None:
    with _server(status=200, response=b"x" * 200) as (url, _):
        result = evaluate(
            url=url,
            should_send=True,
            requested_mode="generic-json",
            max_response_bytes=64,
            allow_insecure_loopback=True,
        )
    assert result.state == "INVALID_RESPONSE"
    assert result.error_class == "ResponseTooLarge"
