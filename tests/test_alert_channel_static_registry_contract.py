from __future__ import annotations

import json

from scripts.alert_channel_canary import evaluate


def test_static_proof_registry_fails_closed_without_delivery_attempt() -> None:
    result = evaluate(
        url="https://a11oy.net/private-secret-path",
        should_send=True,
        requested_mode="ntfy",
    )

    rendered = json.dumps(result.to_dict())
    assert result.state == "INVALID_CONFIGURATION"
    assert result.canary_attempted is False
    assert result.attempt_count == 0
    assert "static proof registry" in (result.error_detail or "")
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
