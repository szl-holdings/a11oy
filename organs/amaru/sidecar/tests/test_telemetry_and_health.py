"""Tests for structured logging, span no-op behaviour, and the enriched /healthz."""

from __future__ import annotations

import importlib
import json
import logging
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi.testclient import TestClient  # noqa: E402

from amaru import telemetry  # noqa: E402
from amaru import version as version_mod  # noqa: E402


def _client() -> TestClient:
    for name in list(sys.modules):
        if name == "amaru" or (name.startswith("amaru.") and name != "amaru.telemetry" and name != "amaru.version"):
            del sys.modules[name]
    module = importlib.import_module("amaru.app")
    return TestClient(module.app)


def test_json_formatter_emits_valid_json_with_extra_fields() -> None:
    fmt = telemetry.JsonLogFormatter()
    record = logging.LogRecord(
        name="amaru.test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello", args=(), exc_info=None,
    )
    record.tick_id = 7  # extra structured field
    line = fmt.format(record)
    obj = json.loads(line)
    assert obj["level"] == "INFO"
    assert obj["logger"] == "amaru.test"
    assert obj["msg"] == "hello"
    assert obj["tick_id"] == 7
    assert obj["ts"].endswith("Z")


def test_span_is_noop_when_otel_disabled() -> None:
    # With AMARU_OTEL_ENABLED unset (default), spans must not raise and
    # otel_active() must report False.
    assert telemetry.otel_active() is False
    with telemetry.span("amaru.test.span", foo="bar"):
        pass  # must complete without error


def test_configure_logging_is_idempotent() -> None:
    telemetry._CONFIGURED = False
    telemetry.configure_logging()
    handlers_first = list(logging.getLogger().handlers)
    telemetry.configure_logging()
    handlers_second = list(logging.getLogger().handlers)
    assert handlers_first == handlers_second
    assert len(handlers_second) == 1


def test_version_resolves_non_empty_sha() -> None:
    # In a git checkout this is the real HEAD; in a bare container it is
    # "unknown". Either way it must be a non-empty string.
    assert isinstance(version_mod.GIT_SHA, str)
    assert version_mod.GIT_SHA
    assert version_mod.BOOT_TS.endswith("Z")


def test_healthz_includes_git_sha_and_otel_flag(monkeypatch) -> None:
    # Force the no-otel default so this assertion is order-independent: a
    # fully fresh telemetry import with AMARU_OTEL_ENABLED unset.
    monkeypatch.delenv("AMARU_OTEL_ENABLED", raising=False)
    for name in list(sys.modules):
        if name.startswith("amaru"):
            del sys.modules[name]
    client = _client()
    body = client.get("/healthz").json()
    assert body["ok"] is True
    assert "gitSha" in body and isinstance(body["gitSha"], str) and body["gitSha"]
    assert "gitShaShort" in body
    assert "bootTs" in body and body["bootTs"].endswith("Z")
    assert body["otel"] is False  # otel off by default in tests
    assert body["version"] == "0.1.0"


def test_receipts_endpoint_returns_structured_body() -> None:
    client = _client()
    # Drive one tick so there are receipts to read.
    client.post("/scheduler/tick", json={"envelope": {"signals": {
        "grounded": 0.9, "integrity": 0.9, "novelty": 0.4, "fluency": 0.7,
        "intent": 0.8, "agency": 0.9, "friction": 0.1, "care": 0.8, "harm": 0.2,
        "clarity": 0.9, "truth": 0.9, "pattern_strength": 0.7, "uncertainty": 0.2,
    }}})
    r = client.get("/receipts?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert body["head_seq"] >= 1
    assert isinstance(body["items"], list)
    assert len(body["items"]) <= 5
