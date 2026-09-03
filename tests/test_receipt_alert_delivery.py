#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Network-free, fail-closed contracts for durable receipt-alert delivery."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "receipt_alert_delivery.py"
SPEC = importlib.util.spec_from_file_location("receipt_alert_delivery", MODULE_PATH)
assert SPEC and SPEC.loader
alert = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = alert
SPEC.loader.exec_module(alert)


class FakeClient:
    def __init__(self) -> None:
        self.created: list[tuple[str, str, list[str] | None]] = []
        self.commented: list[tuple[int, str]] = []
        self.closed: list[tuple[int, str]] = []
        self.reopened: list[int] = []
        self.open_exact: list[dict[str, object]] = []
        self.closed_exact: list[dict[str, object]] = []
        self.issue_comments: dict[int, list[dict[str, str]]] = {}
        self.next_number = 41

    def exact_issues(self, title: str, marker: str, *, state: str = "open") -> list[dict[str, object]]:
        del title, marker
        return list(self.open_exact if state == "open" else self.closed_exact)

    def create_issue(self, title: str, body: str, labels: list[str] | None = None) -> dict[str, object]:
        self.created.append((title, body, labels))
        number = self.next_number
        self.next_number += 1
        return {
            "number": number,
            "html_url": f"https://github.com/szl-holdings/a11oy/issues/{number}",
            "title": title,
            "body": body,
        }

    def comments(self, number: int) -> list[dict[str, str]]:
        return list(self.issue_comments.get(number, []))

    def comment(self, number: int, body: str) -> None:
        self.commented.append((number, body))
        self.issue_comments.setdefault(number, []).append({"body": body})

    def close(self, number: int, *, reason: str = "completed") -> None:
        self.closed.append((number, reason))

    def reopen(self, number: int) -> None:
        self.reopened.append(number)


def test_validation_rejects_empty_or_unbounded_messages_and_bad_severity() -> None:
    assert alert.validate_severity(" WARNING ") == "warning"
    for value in ("", "unknown", "panic"):
        try:
            alert.validate_severity(value)
        except alert.DeliveryError:
            pass
        else:
            raise AssertionError(f"invalid severity was admitted: {value!r}")
    for value in ("", "   ", "x" * 4001):
        try:
            alert.validate_message(value)
        except alert.DeliveryError:
            pass
        else:
            raise AssertionError("invalid alert message was admitted")


def test_source_url_must_be_credential_free_https() -> None:
    assert alert.validate_source_url(None) is None
    assert alert.validate_source_url("https://github.com/szl-holdings/a11oy/actions/runs/1")
    for value in (
        "http://example.com/run",
        "https://user:pass@example.com/run",
        "ftp://example.com/run",
        "not-a-url",
    ):
        try:
            alert.validate_source_url(value)
        except alert.DeliveryError:
            pass
        else:
            raise AssertionError(f"unsafe source URL was admitted: {value}")


def test_ntfy_topic_identity_never_accepts_or_returns_credentials() -> None:
    assert alert.ntfy_identity(None) == (None, None)
    url, host = alert.ntfy_identity("https://ntfy.sh/szl-receipts")
    assert url == "https://ntfy.sh/szl-receipts"
    assert host == "ntfy.sh"
    for value in (
        "http://ntfy.sh/topic",
        "https://user:pass@ntfy.sh/topic",
        "https://ntfy.sh/",
        "https://ntfy.sh/topic?token=secret",
        "https://ntfy.sh/topic#fragment",
    ):
        try:
            alert.ntfy_identity(value)
        except alert.DeliveryError:
            pass
        else:
            raise AssertionError(f"unsafe ntfy identity was admitted: {value}")


def test_delivery_digest_is_stable_and_payload_sensitive() -> None:
    first = alert.delivery_digest(
        severity="error", message="Receipt failed", source_url="https://example.com/run/1"
    )
    second = alert.delivery_digest(
        severity="error", message="Receipt failed", source_url="https://example.com/run/1"
    )
    changed = alert.delivery_digest(
        severity="critical", message="Receipt failed", source_url="https://example.com/run/1"
    )
    assert first == second
    assert first != changed
    assert len(first) == 64


def test_real_alert_creates_one_durable_github_issue() -> None:
    client = FakeClient()
    result = alert.deliver_github_alert(
        client,
        severity="error",
        message="Signature verification failed",
        source_url="https://github.com/szl-holdings/a11oy/actions/runs/7",
        canary=False,
        observed_at="2026-09-02T20:00:00Z",
    )
    assert result.status == "DELIVERED"
    assert result.action == "CREATED"
    assert result.issue_number == 41
    assert len(client.created) == 1
    title, body, labels = client.created[0]
    assert title == alert.ALERT_TITLE
    assert alert.ALERT_MARKER in body
    assert result.delivery_digest in body
    assert labels is None


def test_existing_alert_comments_once_then_deduplicates_same_digest() -> None:
    client = FakeClient()
    client.open_exact = [
        {
            "number": 12,
            "html_url": "https://github.com/szl-holdings/a11oy/issues/12",
            "updated_at": "2026-09-02T20:00:00Z",
        }
    ]
    kwargs = {
        "severity": "warning",
        "message": "Evidence sink is delayed",
        "source_url": "https://github.com/szl-holdings/a11oy/actions/runs/8",
        "canary": False,
        "observed_at": "2026-09-02T20:00:00Z",
    }
    first = alert.deliver_github_alert(client, **kwargs)
    assert first.action == "COMMENTED"
    assert len(client.commented) == 1
    second = alert.deliver_github_alert(client, **kwargs)
    assert second.action == "DEDUPLICATED"
    assert len(client.commented) == 1


def test_canary_creates_acknowledges_and_closes_synthetic_issue() -> None:
    client = FakeClient()
    result = alert.deliver_github_alert(
        client,
        severity="info",
        message="Receipt alert delivery canary",
        source_url=None,
        canary=True,
        observed_at="2026-09-02T20:00:00Z",
    )
    assert result.action == "CREATED_AND_CLOSED_CANARY"
    assert client.created[0][0] == alert.CANARY_TITLE
    assert alert.CANARY_MARKER in client.created[0][1]
    assert client.commented and client.commented[0][0] == result.issue_number
    assert client.closed == [(result.issue_number, "completed")]


def test_unconfigured_ntfy_is_honest_and_nonblocking() -> None:
    result = alert.deliver_ntfy(
        topic_url=None,
        token=None,
        severity="info",
        message="canary",
        source_url=None,
    )
    assert result.status == "UNCONFIGURED"
    assert result.configured is False
    assert result.host is None
    assert result.http_status is None


def test_configured_ntfy_success_records_host_not_topic_or_token() -> None:
    response = mock.MagicMock()
    response.status = 200
    response.read.return_value = b'{"id":"x"}'
    response.__enter__.return_value = response
    with mock.patch("urllib.request.urlopen", return_value=response) as opened:
        result = alert.deliver_ntfy(
            topic_url="https://ntfy.sh/private-topic-name",
            token="secondary-secret-token",
            severity="critical",
            message="receipt failed",
            source_url="https://example.com/run/9",
        )
    assert result.status == "DELIVERED"
    assert result.host == "ntfy.sh"
    encoded = json.dumps(alert.asdict(result))
    assert "private-topic-name" not in encoded
    assert "secondary-secret-token" not in encoded
    request = opened.call_args.args[0]
    assert request.get_method() == "POST"
    assert request.headers["Authorization"].startswith("Bearer ")


def test_configured_ntfy_http_failure_is_evidenced_without_topic_leak() -> None:
    error = urllib.error.HTTPError(
        "https://ntfy.sh/private-topic-name",
        404,
        "Not Found",
        {},
        io.BytesIO(b"not found"),
    )
    with mock.patch("urllib.request.urlopen", side_effect=error):
        result = alert.deliver_ntfy(
            topic_url="https://ntfy.sh/private-topic-name",
            token=None,
            severity="error",
            message="receipt failed",
            source_url=None,
        )
    assert result.status == "FAILED"
    assert result.http_status == 404
    assert result.host == "ntfy.sh"
    assert "private-topic-name" not in json.dumps(alert.asdict(result))


def test_provider_failure_creates_incident_and_recovery_closes_it() -> None:
    client = FakeClient()
    failed = alert.NtfyDelivery(
        status="FAILED",
        configured=True,
        host="ntfy.sh",
        http_status=404,
        error="ntfy returned HTTP 404",
    )
    created = alert.reconcile_provider_incident(
        client, ntfy=failed, observed_at="2026-09-02T20:00:00Z"
    )
    assert created["action"] == "CREATED"
    assert client.created[0][0] == alert.PROVIDER_TITLE
    assert alert.PROVIDER_MARKER in client.created[0][1]

    client.open_exact = [
        {
            "number": 77,
            "html_url": "https://github.com/szl-holdings/a11oy/issues/77",
        }
    ]
    recovered = alert.reconcile_provider_incident(
        client,
        ntfy=alert.NtfyDelivery(
            status="DELIVERED",
            configured=True,
            host="ntfy.sh",
            http_status=200,
        ),
        observed_at="2026-09-02T21:00:00Z",
    )
    assert recovered["action"] == "CLOSED_RECOVERED"
    assert client.closed[-1] == (77, "completed")


def test_token_shapes_are_redacted_recursively() -> None:
    payload = {
        "github": "github_pat_abcdefghijklmnopqrstuvwxyz0123456789",
        "hub": ["hf_abcdefghijklmnopqrstuvwxyz0123456789"],
        "authorization": "Bearer abcdefghijklmnopqrstuvwxyz",
    }
    encoded = json.dumps(alert.redact(payload))
    assert "github_pat_" not in encoded
    assert "hf_" not in encoded
    assert "Bearer abc" not in encoded
    assert encoded.count("[REDACTED]") == 3


def test_main_without_github_token_fails_closed_and_emits_secret_free_report() -> None:
    with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
        os.environ,
        {"GITHUB_REPOSITORY": "szl-holdings/a11oy"},
        clear=True,
    ):
        report_path = Path(directory) / "report.json"
        code = alert.main(["--canary", "--report", str(report_path)])
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert code == 1
    assert payload["status"] == "FAIL"
    assert payload["token_value_recorded"] is False
    assert "token" in payload["error"].casefold()
    assert "github_pat_" not in json.dumps(payload)


def test_source_does_not_mutate_protection_provider_resources_or_secrets() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "/branches/main/protection",
        "/rulesets",
        "actions/secrets",
        "dependabot/secrets",
        "codespaces/secrets",
        '"visibility":',
        '"private":',
        '"archived":',
    ):
        assert forbidden not in source
