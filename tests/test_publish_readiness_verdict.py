from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "publish_readiness_verdict.py"
SPEC = importlib.util.spec_from_file_location("publish_readiness_verdict", SCRIPT)
assert SPEC and SPEC.loader
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


def valid_verdict(now: datetime) -> dict:
    return {
        "schema": publisher.VERDICT_SCHEMA,
        "harness": "a11oy-readiness probe",
        "doctrine": "v11",
        "base": "https://szlholdings-a11oy.hf.space",
        "checkedAt": now.isoformat().replace("+00:00", "Z"),
        "sourceRevision": "a" * 40,
        "summary": {
            "endpoints": 5,
            "ok": 5,
            "skippedStateChanging": 0,
            "lies": 0,
            "unreachable": 0,
            "throttled": 0,
            "p95_worst": 1806,
        },
        "results": [{"path": "/not-published"}],
    }


def compact(payload: dict, now: datetime) -> dict:
    return publisher.compact_verdict(
        payload,
        expected_origin="https://szlholdings-a11oy.hf.space",
        expected_source_sha="a" * 40,
        now=now,
    )


def test_compact_verdict_is_source_origin_and_freshness_bound() -> None:
    now = datetime(2026, 7, 26, 6, 0, tzinfo=timezone.utc)
    result = compact(valid_verdict(now), now)

    assert result["schema"] == publisher.VERDICT_SCHEMA
    assert result["sourceRevision"] == "a" * 40
    assert result["base"] == "https://szlholdings-a11oy.hf.space"
    assert result["summary"]["endpoints"] == 5
    assert "results" not in result


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("schema", "unknown", "identity"),
        ("sourceRevision", "b" * 40, "source revision"),
        ("base", "https://unrelated.example", "origin"),
    ),
)
def test_compact_verdict_rejects_identity_drift(
    field: str,
    value: str,
    message: str,
) -> None:
    now = datetime(2026, 7, 26, 6, 0, tzinfo=timezone.utc)
    payload = valid_verdict(now)
    payload[field] = value
    with pytest.raises(publisher.VerdictError, match=message):
        compact(payload, now)


def test_compact_verdict_rejects_future_stale_and_incomplete_results() -> None:
    now = datetime(2026, 7, 26, 6, 0, tzinfo=timezone.utc)
    for checked_at in (
        now + timedelta(seconds=1),
        now - timedelta(seconds=publisher.MAX_INGEST_AGE_SECONDS + 1),
    ):
        payload = valid_verdict(now)
        payload["checkedAt"] = checked_at.isoformat().replace("+00:00", "Z")
        with pytest.raises(publisher.VerdictError, match="future-dated|old"):
            compact(payload, now)

    payload = valid_verdict(now)
    payload["summary"]["endpoints"] = 6
    with pytest.raises(publisher.VerdictError, match="inconsistent"):
        compact(payload, now)


def test_compact_verdict_rejects_doctrine_lies() -> None:
    now = datetime(2026, 7, 26, 6, 0, tzinfo=timezone.utc)
    payload = valid_verdict(now)
    payload["summary"]["ok"] = 4
    payload["summary"]["lies"] = 1

    with pytest.raises(publisher.VerdictError, match="doctrine lies"):
        compact(payload, now)


def test_compact_verdict_rejects_all_unreachable_release_evidence() -> None:
    now = datetime(2026, 7, 26, 6, 0, tzinfo=timezone.utc)
    payload = valid_verdict(now)
    payload["summary"].update({
        "ok": 0,
        "lies": 0,
        "unreachable": payload["summary"]["endpoints"],
        "throttled": 0,
    })

    with pytest.raises(publisher.VerdictError, match="unreachable required endpoints"):
        compact(payload, now)


def test_compact_verdict_rejects_all_throttled_release_evidence() -> None:
    now = datetime(2026, 7, 26, 6, 0, tzinfo=timezone.utc)
    payload = valid_verdict(now)
    payload["summary"].update({
        "ok": 0,
        "lies": 0,
        "unreachable": 0,
        "throttled": payload["summary"]["endpoints"],
    })

    with pytest.raises(publisher.VerdictError, match="throttled required endpoints"):
        compact(payload, now)
