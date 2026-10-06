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
            "degraded": 0,
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


@pytest.mark.parametrize("value", [True, -1, 1.5, "1", None])
def test_compact_verdict_rejects_invalid_degraded_counts(value: object) -> None:
    now = datetime(2026, 7, 26, 6, 0, tzinfo=timezone.utc)
    payload = valid_verdict(now)
    payload["summary"]["degraded"] = value
    with pytest.raises(publisher.VerdictError, match="counts"):
        compact(payload, now)


def test_unavailable_required_source_cannot_be_published_as_ready() -> None:
    now = datetime(2026, 7, 26, 6, 0, tzinfo=timezone.utc)
    payload = valid_verdict(now)
    payload["summary"].update(ok=4, degraded=1)
    with pytest.raises(publisher.VerdictError, match="unavailable required sources"):
        compact(payload, now)
    payload["summary"].update(ok=5, degraded=0)
    assert compact(payload, now)["summary"]["degraded"] == 0


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


def test_validate_only_gates_the_verdict_without_any_space_write(tmp_path, monkeypatch, capsys) -> None:
    # The deploy path validates the fresh verdict but never writes it to a
    # Space variable, because a variable write restarts the deployed Space.
    import json
    import sys

    now = datetime.now(timezone.utc).replace(microsecond=0)
    probe = tmp_path / "verdict.json"
    probe.write_text(json.dumps(valid_verdict(now)), encoding="utf-8")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)  # any import fails
    arguments = ["--validate-only", "--input", str(probe),
                 "--expected-origin", "https://szlholdings-a11oy.hf.space",
                 "--expected-source-sha", "a" * 40]
    assert publisher.main(arguments) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["validated"] is True
    assert printed["space_variable_written"] is False
    assert printed["verdict"]["sourceRevision"] == "a" * 40

    payload = valid_verdict(now)
    payload["summary"].update(ok=4, lies=1)
    probe.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(publisher.VerdictError, match="doctrine lies"):
        publisher.main(arguments)


def test_publishing_still_requires_an_explicit_target(tmp_path) -> None:
    with pytest.raises(SystemExit):
        publisher.main(["--input", str(tmp_path / "missing.json"),
                        "--expected-origin", "https://szlholdings-a11oy.hf.space",
                        "--expected-source-sha", "a" * 40])
