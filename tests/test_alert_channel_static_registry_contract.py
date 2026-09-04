from __future__ import annotations

import json
import urllib.request

from scripts.alert_channel_canary import evaluate


class _Response:
    status = 204

    def getcode(self) -> int:
        return self.status

    def read(self, _limit: int) -> bytes:
        return b""

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _CapturingOpener:
    request: urllib.request.Request | None = None

    def open(
        self, request: urllib.request.Request, *, timeout: float
    ) -> _Response:
        del timeout
        self.request = request
        return _Response()


def test_legacy_static_host_uses_managed_relay_without_recording_path() -> None:
    opener = _CapturingOpener()
    result = evaluate(
        url="https://a11oy.net/private-secret-path?priority=3",
        should_send=True,
        opener=opener,
    )

    rendered = json.dumps(result.to_dict())
    assert result.state == "HEALTHY"
    assert result.canary_attempted is True
    assert result.attempt_count == 1
    assert result.endpoint is not None
    assert result.endpoint.hostname == "ntfy.a11oy.net"
    assert result.endpoint.port is None
    assert result.endpoint.mode == "ntfy"
    assert opener.request is not None
    assert (
        opener.request.full_url
        == "https://ntfy.a11oy.net/private-secret-path?priority=3"
    )
    assert "private-secret-path" not in rendered
    assert "priority=3" not in rendered


def test_legacy_static_root_fails_closed_without_delivery_attempt() -> None:
    result = evaluate(
        url="https://a11oy.net/",
        should_send=True,
    )

    assert result.state == "INVALID_CONFIGURATION"
    assert result.canary_attempted is False
    assert result.attempt_count == 0
    assert "static proof registry" in (result.error_detail or "")


def test_legacy_static_host_rejects_nondefault_port() -> None:
    result = evaluate(
        url="https://a11oy.net:8443/private-secret-path",
        should_send=True,
    )

    rendered = json.dumps(result.to_dict())
    assert result.state == "INVALID_CONFIGURATION"
    assert result.canary_attempted is False
    assert result.attempt_count == 0
    assert "default HTTPS port" in (result.error_detail or "")
    assert "private-secret-path" not in rendered


def test_managed_ntfy_relay_is_allowed_without_claiming_delivery() -> None:
    result = evaluate(
        url="https://ntfy.a11oy.net/private-topic",
        should_send=False,
    )

    rendered = json.dumps(result.to_dict())
    assert result.state == "PRESENT_UNPROBED"
    assert result.canary_attempted is False
    assert result.attempt_count == 0
    assert result.endpoint is not None
    assert result.endpoint.hostname == "ntfy.a11oy.net"
    assert result.endpoint.mode == "ntfy"
    assert "private-topic" not in rendered
