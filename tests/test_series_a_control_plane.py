from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from routers import series_a_control_plane as control


def app(tmp_path: Path) -> FastAPI:
    os.environ["A11OY_SERIES_A_STARTUP_REFRESH"] = "0"
    value = FastAPI()
    control.register(value, db_path=str(tmp_path / "series-a.sqlite3"))
    return value


def observed_evidence(
    service: control.Service,
    *,
    status: str = "OBSERVED",
    critical_failures: list[str] | None = None,
) -> list[dict[str, str]]:
    now = datetime.now(timezone.utc)
    observed_at = now.isoformat().replace("+00:00", "Z")
    valid_until = (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    manifest = {
        "schema": control.SCHEMA_MANIFEST,
        "observed_at": observed_at,
        "valid_until": valid_until,
        "source_revision": "a" * 40,
        "status": status,
        "critical_failures": (
            critical_failures
            if critical_failures is not None
            else ([] if status == "OBSERVED" else ["ESTATE_BLOCKED"])
        ),
        "counts": {},
    }
    envelope = service.signer.sign(manifest)
    digest = service.store.save_snapshot(manifest, envelope)
    return [
        {
            "evidence_id": "estate-snapshot",
            "label": "OBSERVED",
            "content_digest": digest,
            "observed_at": observed_at,
            "valid_until": valid_until,
            "source_revision": manifest["source_revision"],
            "signature_status": envelope["signature_status"],
        }
    ]


def test_refresh_interval_is_bounded_before_snapshot_ttl(monkeypatch) -> None:
    monkeypatch.delenv("A11OY_SERIES_A_REFRESH_INTERVAL_SECONDS", raising=False)
    assert control._refresh_interval_seconds() == 240
    assert control._refresh_interval_seconds() < control.TTL_SECONDS

    monkeypatch.setenv("A11OY_SERIES_A_REFRESH_INTERVAL_SECONDS", "1")
    assert (
        control._refresh_interval_seconds()
        == control.MIN_REFRESH_INTERVAL_SECONDS
    )

    monkeypatch.setenv("A11OY_SERIES_A_REFRESH_INTERVAL_SECONDS", "999")
    assert (
        control._refresh_interval_seconds()
        == control.MAX_REFRESH_INTERVAL_SECONDS
    )

    monkeypatch.setenv("A11OY_SERIES_A_REFRESH_INTERVAL_SECONDS", "invalid")
    assert (
        control._refresh_interval_seconds()
        == control.DEFAULT_REFRESH_INTERVAL_SECONDS
    )


def test_periodic_refresh_retries_and_records_failure_honestly(
    tmp_path: Path, monkeypatch
) -> None:
    service = control.Service(str(tmp_path / "series-a.sqlite3"))
    actors: list[str] = []
    sleeps: list[int] = []

    async def refresh(actor: str) -> dict[str, object]:
        actors.append(actor)
        if actor == "startup":
            raise RuntimeError("collector unavailable")
        return {}

    async def sleep(seconds: int) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(service, "refresh", refresh)
    monkeypatch.setattr(control.asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(service._refresh_loop())

    events = service.store.events_since(0)
    assert actors == ["startup", "periodic"]
    assert len(sleeps) == 2
    assert all(
        0 <= value <= control.DEFAULT_REFRESH_INTERVAL_SECONDS
        for value in sleeps
    )
    assert events[-1]["kind"] == "estate.refresh.failed"
    assert events[-1]["payload"] == {
        "actor": "startup",
        "retry_in_seconds": control.DEFAULT_REFRESH_INTERVAL_SECONDS,
        "error_class": "RuntimeError",
        "error": "collector unavailable",
    }


def test_periodic_schedule_accounts_for_collection_time(
) -> None:
    assert control._refresh_delay_seconds(240, 75.0) == 165.0
    assert control._refresh_delay_seconds(240, 240.0) == 0.0
    assert control._refresh_delay_seconds(240, 300.0) == 0.0
    assert control._refresh_delay_seconds(240, -1.0) == 240.0


def test_required_storage_mount_fails_closed_when_not_attached(
    tmp_path: Path, monkeypatch
) -> None:
    mount = tmp_path / "data"
    database = mount / "a11oy" / "series-a" / "control-plane.sqlite3"
    monkeypatch.setenv("A11OY_REQUIRE_PERSISTENT_STORAGE", "1")
    monkeypatch.setenv("A11OY_SERIES_A_REQUIRE_MOUNT", str(mount))
    monkeypatch.setattr(control.os.path, "ismount", lambda _: False)

    with pytest.raises(RuntimeError, match="storage mount is not attached"):
        control.Store(str(database))

    assert not database.exists()


def test_persistent_store_identity_and_chain_survive_reopen(
    tmp_path: Path, monkeypatch
) -> None:
    mount = tmp_path / "data"
    database = mount / "a11oy" / "series-a" / "control-plane.sqlite3"
    monkeypatch.setenv("A11OY_REQUIRE_PERSISTENT_STORAGE", "1")
    monkeypatch.setenv("A11OY_SERIES_A_REQUIRE_MOUNT", str(mount))
    monkeypatch.setenv("A11OY_SERIES_A_SQLITE_JOURNAL", "DELETE")
    monkeypatch.setattr(
        control.os.path,
        "ismount",
        lambda value: Path(value).resolve() == mount.resolve(),
    )

    first = control.Store(str(database))
    signer = control.ReceiptSigner()
    receipt = first.append_receipt("restart-proof", {"value": 1}, signer)
    before = first.storage_status()

    reopened = control.Store(str(database))
    after = reopened.storage_status()

    assert before["persistence_required"] is True
    assert before["mount_verified"] is True
    assert before["journal_mode"] == "DELETE"
    assert before["instance_id"] == after["instance_id"]
    assert before["created_at"] == after["created_at"]
    assert after["receipt_count"] == 1
    assert after["last_receipt_sequence"] == 1
    assert after["chain_head"] == receipt["receipt_hash"]


def test_invalid_sqlite_journal_mode_fails_closed(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("A11OY_SERIES_A_SQLITE_JOURNAL", "MEMORY")
    with pytest.raises(RuntimeError, match="must be one of"):
        control.Store(str(tmp_path / "series-a.sqlite3"))


def test_refresh_fails_closed_before_collection_when_governance_denies(
    tmp_path: Path, monkeypatch
) -> None:
    service = control.Service(str(tmp_path / "series-a.sqlite3"))
    collected = False

    async def collect() -> dict[str, object]:
        nonlocal collected
        collected = True
        return {}

    monkeypatch.setattr(service.collector, "collect", collect)
    monkeypatch.setattr(
        service,
        "_governance_gate",
        lambda action: {
            "allowed": False,
            "decision": "DENY",
            "reason_codes": ["TEST_GOVERNANCE_DENY"],
        },
    )

    with pytest.raises(control.HTTPException) as error:
        asyncio.run(service.refresh("periodic"))

    receipts = service.store.list_receipts()
    assert error.value.status_code == 403
    assert collected is False
    assert receipts[0]["kind"] == "estate.refresh.authorization"
    assert receipts[0]["receipt"]["payload"]["decision"] == "DENY"
    assert receipts[0]["receipt"]["payload"]["reason_codes"] == [
        "TEST_GOVERNANCE_DENY"
    ]


def test_snapshot_history_is_bounded_without_pruning_receipts(
    tmp_path: Path,
) -> None:
    service = control.Service(str(tmp_path / "series-a.sqlite3"))
    total = control.MAX_SNAPSHOT_HISTORY + 5
    for index in range(total):
        observed_at = (
            datetime.now(timezone.utc) + timedelta(seconds=index)
        ).isoformat().replace("+00:00", "Z")
        manifest = {
            "schema": control.SCHEMA_MANIFEST,
            "observed_at": observed_at,
            "valid_until": (
                datetime.now(timezone.utc)
                + timedelta(minutes=5, seconds=index)
            ).isoformat().replace("+00:00", "Z"),
            "status": "OBSERVED",
            "counts": {"index": index},
        }
        service.store.save_snapshot(manifest, service.signer.sign(manifest))
        service.store.append_receipt(
            "snapshot.test",
            {"index": index},
            service.signer,
        )

    with service.store.connect() as db:
        snapshot_count = db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        receipt_count = db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]

    assert snapshot_count == control.MAX_SNAPSHOT_HISTORY
    assert receipt_count == total
    assert service.store.latest_snapshot()["manifest"]["counts"]["index"] == total - 1


def test_background_refresh_cancels_cleanly_on_shutdown(
    tmp_path: Path, monkeypatch
) -> None:
    service = control.Service(str(tmp_path / "series-a.sqlite3"))
    monkeypatch.setenv("A11OY_SERIES_A_STARTUP_REFRESH", "1")

    async def scenario() -> None:
        entered = asyncio.Event()

        async def refresh(actor: str) -> dict[str, object]:
            assert actor == "startup"
            entered.set()
            await asyncio.Event().wait()
            return {}

        monkeypatch.setattr(service, "refresh", refresh)
        await service.start()
        await entered.wait()
        task = service.background_task
        assert task is not None
        await service.stop()
        assert task.cancelled()
        assert service.background_task is None
        assert service.started is False

    asyncio.run(scenario())


def test_startup_refresh_zero_disables_periodic_task(
    tmp_path: Path, monkeypatch
) -> None:
    service = control.Service(str(tmp_path / "series-a.sqlite3"))
    monkeypatch.setenv("A11OY_SERIES_A_STARTUP_REFRESH", "0")

    asyncio.run(service.start())

    assert service.background_task is None
    assert service.store.events_since(0)[-1]["kind"] == "estate.refresh.skipped"


def test_canonical_startup_starts_registered_refresh_once(
    tmp_path: Path, monkeypatch
) -> None:
    value = FastAPI()
    monkeypatch.setenv("A11OY_SERIES_A_STARTUP_REFRESH", "1")
    control.register(value, db_path=str(tmp_path / "series-a.sqlite3"))
    service = value.state.szl_series_a_service

    async def scenario() -> None:
        entered = asyncio.Event()

        async def refresh(actor: str) -> dict[str, object]:
            assert actor == "startup"
            entered.set()
            await asyncio.Event().wait()
            return {}

        monkeypatch.setattr(service, "refresh", refresh)
        first = await control.start_registered_service(value)
        task = service.background_task
        second = await control.start_registered_service(value)
        await entered.wait()

        assert first["state"] == "RUNNING"
        assert first["task_running"] is True
        assert second["state"] == "RUNNING"
        assert service.background_task is task
        await service.stop()

    asyncio.run(scenario())


def test_routes_are_front_moved_and_head_is_bodyless(tmp_path: Path) -> None:
    value = app(tmp_path)
    paths = [getattr(route, "path", None) for route in value.routes]
    assert paths.index("/series-a") < paths.index("/openapi.json")
    with TestClient(value) as client:
        page = client.get("/series-a")
        head = client.head("/series-a")
        status = client.get("/api/a11oy/v1/series-a/status")
    assert page.status_code == 200
    assert "Series‑A Live Control Plane" in page.text
    assert head.status_code == 200 and head.content == b""
    assert status.status_code == 200
    assert status.json()["terminal"] is True


def test_direct_refresh_is_restricted_to_the_passport_flow(
    tmp_path: Path, monkeypatch
) -> None:
    value = app(tmp_path)
    service = value.state.szl_series_a_service
    observed_evidence(service)
    collected = False

    async def collect() -> dict[str, object]:
        nonlocal collected
        collected = True
        return {}

    monkeypatch.setattr(service.collector, "collect", collect)

    with TestClient(value) as client:
        before_receipts = service.store.list_receipts()
        before_events = service.store.events_since(0)
        response = client.post(
            "/api/a11oy/v1/series-a/refresh",
            json={"actor": "browser-shortcut"},
        )
        after_receipts = service.store.list_receipts()
        after_events = service.store.events_since(0)

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "DIRECT_REFRESH_DISABLED",
        "required_flow": [
            "/api/a11oy/v1/series-a/passports/evaluate",
            "/api/a11oy/v1/series-a/passports/execute",
        ],
    }
    assert collected is False
    assert after_receipts == before_receipts
    assert after_events == before_events


def test_governed_refresh_passport_executes_once(
    tmp_path: Path, monkeypatch
) -> None:
    value = app(tmp_path)
    service = value.state.szl_series_a_service
    evidence = observed_evidence(service)
    collected = 0

    async def collect() -> dict[str, object]:
        nonlocal collected
        collected += 1
        now = datetime.now(timezone.utc)
        manifest: dict[str, object] = {
            "schema": control.SCHEMA_MANIFEST,
            "observed_at": now.isoformat().replace("+00:00", "Z"),
            "valid_until": (now + timedelta(minutes=5))
            .isoformat()
            .replace("+00:00", "Z"),
            "source_revision": "a" * 40,
            "status": "OBSERVED",
            "critical_failures": [],
            "counts": {"github_repositories": 57},
        }
        manifest["manifest_digest"] = control._sha(manifest)
        return manifest

    monkeypatch.setattr(service.collector, "collect", collect)

    with TestClient(value) as client:
        evaluated = client.post(
            "/api/a11oy/v1/series-a/passports/evaluate",
            json={
                "principal_id": "series-a-ui",
                "action": {
                    "type": "estate.refresh",
                    "target": "szl://estate/current",
                    "impact": "MODERATE",
                    "irreversible": False,
                },
                "evidence": evidence,
            },
        )
        assert evaluated.status_code == 200
        digest = evaluated.json()["passport_digest"]
        executed = client.post(
            "/api/a11oy/v1/series-a/passports/execute",
            json={"passport_digest": digest},
        )
        replay = client.post(
            "/api/a11oy/v1/series-a/passports/execute",
            json={"passport_digest": digest},
        )

    assert evaluated.json()["passport"]["decision"] == "ALLOW"
    assert executed.status_code == 200
    assert executed.json()["outcome"]["status"] == "SUCCEEDED"
    assert executed.json()["outcome"]["estate_status"] == "OBSERVED"
    assert service.store.load_passport(digest)["attempts"] == 1
    assert collected == 1
    assert replay.status_code == 409


def test_passport_blocks_unknown_evidence_and_writes_signed_or_honestly_unsigned_receipt(tmp_path: Path) -> None:
    value = app(tmp_path)
    observed_evidence(value.state.szl_series_a_service)
    with TestClient(value) as client:
        response = client.post(
            "/api/a11oy/v1/series-a/passports/evaluate",
            json={
                "principal_id": "tester",
                "action": {
                    "type": "estate.refresh",
                    "target": "szl://estate/current",
                    "impact": "MODERATE",
                    "irreversible": False,
                },
                "evidence": [
                    {
                        "evidence_id": "e1",
                        "label": "UNKNOWN",
                        "content_digest": "e" * 64,
                    }
                ],
            },
        )
        receipts = client.get("/api/a11oy/v1/series-a/receipts").json()["items"]
    assert response.status_code == 200
    body = response.json()
    assert body["passport"]["decision"] == "BLOCK"
    assert "NON_ACTIONABLE_EVIDENCE" in body["passport"]["reason_codes"]
    assert receipts[0]["envelope"]["signature_status"] in {
        "SIGNED",
        "UNSIGNED_UNAVAILABLE",
        "UNSIGNED_ERROR",
    }


def test_receipt_readback_honors_bounded_limit_without_caching(
    tmp_path: Path,
) -> None:
    value = app(tmp_path)
    service = value.state.szl_series_a_service
    appended = [
        service.store.append_receipt(
            "test.receipt",
            {"index": index},
            service.signer,
        )
        for index in range(60)
    ]

    with TestClient(value) as client:
        default = client.get("/api/a11oy/v1/series-a/receipts")
        expanded = client.get(
            "/api/a11oy/v1/series-a/receipts?limit=200"
        )
        head = client.head(
            "/api/a11oy/v1/series-a/receipts?limit=200"
        )
        duplicate = client.get(
            "/api/a11oy/v1/series-a/receipts?limit=50&limit=200"
        )
        invalid = client.get(
            "/api/a11oy/v1/series-a/receipts?limit=201"
        )
        recovered = client.get(
            "/api/a11oy/v1/series-a/receipts/"
            + appended[0]["receipt_hash"]
        )
        recovered_head = client.head(
            "/api/a11oy/v1/series-a/receipts/"
            + appended[0]["receipt_hash"]
        )
        recovered_query = client.get(
            "/api/a11oy/v1/series-a/receipts?receipt_hash="
            + appended[0]["receipt_hash"]
        )
        recovered_query_head = client.head(
            "/api/a11oy/v1/series-a/receipts?receipt_hash="
            + appended[0]["receipt_hash"]
        )
        duplicate_query = client.get(
            "/api/a11oy/v1/series-a/receipts?receipt_hash="
            + appended[0]["receipt_hash"]
            + "&receipt_hash="
            + appended[1]["receipt_hash"]
        )
        mixed_query = client.get(
            "/api/a11oy/v1/series-a/receipts?receipt_hash="
            + appended[0]["receipt_hash"]
            + "&limit=200"
        )
        missing_query = client.get(
            "/api/a11oy/v1/series-a/receipts?receipt_hash=" + ("f" * 64)
        )
        malformed_query = client.get(
            "/api/a11oy/v1/series-a/receipts?receipt_hash=not-a-hash"
        )
        missing = client.get(
            "/api/a11oy/v1/series-a/receipts/" + ("f" * 64)
        )
        malformed = client.get(
            "/api/a11oy/v1/series-a/receipts/not-a-hash"
        )

    assert default.status_code == 200
    assert default.json()["limit"] == 50
    assert len(default.json()["items"]) == 50
    assert expanded.status_code == 200
    assert expanded.headers["cache-control"] == "no-store"
    assert expanded.json()["limit"] == 200
    assert len(expanded.json()["items"]) == 60
    assert appended[0]["receipt_hash"] in {
        item["receipt_hash"] for item in expanded.json()["items"]
    }
    assert head.status_code == 200
    assert head.headers["cache-control"] == "no-store"
    assert duplicate.status_code == 400
    assert invalid.status_code == 422
    assert recovered.status_code == 200
    assert recovered.headers["cache-control"] == "no-store"
    assert recovered.json()["schema"] == (
        "szl.series-a-receipt-recovery/v1"
    )
    assert recovered.json()["item"]["receipt_hash"] == (
        appended[0]["receipt_hash"]
    )
    assert recovered.json()["storage"]["receipt_count"] == 60
    assert recovered_head.status_code == 200
    assert recovered_head.headers["cache-control"] == "no-store"
    assert recovered_query.status_code == 200
    assert recovered_query.headers["cache-control"] == "no-store"
    assert recovered_query.json() == recovered.json()
    assert recovered_query_head.status_code == 200
    assert recovered_query_head.headers["cache-control"] == "no-store"
    assert duplicate_query.status_code == 400
    assert mixed_query.status_code == 400
    assert missing_query.status_code == 404
    assert missing_query.headers["cache-control"] == "no-store"
    assert missing_query.json()["schema"] == (
        "szl.series-a-receipt-recovery-miss/v1"
    )
    assert missing_query.json()["queried_receipt_hash"] == "f" * 64
    assert missing_query.json()["storage"]["receipt_count"] == 60
    assert missing_query.json()["item"] is None
    assert malformed_query.status_code == 422
    assert missing.status_code == 404
    assert missing.headers["cache-control"] == "no-store"
    assert missing.json() == missing_query.json()
    assert malformed.status_code == 422


def test_allow_passport_is_one_attempt(tmp_path: Path) -> None:
    value = app(tmp_path)
    service = value.state.szl_series_a_service
    evidence = observed_evidence(service)
    passport = service.evaluate_passport(
        {
            "principal_id": "tester",
            "action": {
                "type": "probe.public_surface",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": evidence,
        }
    )
    digest = passport["passport_digest"]
    assert passport["passport"]["decision"] == "ALLOW"
    assert passport["passport"]["governance"]["allowed"] is True
    assert service.store.load_passport(digest)["attempts"] == 0
    service.store.begin_execution(
        digest,
        service.runtime_boot_id,
        "2026-07-28T16:00:00Z",
    )
    assert service.store.load_passport(digest)["attempts"] == 1
    assert service.store.execution_status(digest)["state"] == "PENDING"
    try:
        service.store.begin_execution(
            digest,
            service.runtime_boot_id,
            "2026-07-28T16:00:01Z",
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("second attempt was accepted")


def test_action_target_binding_fails_closed(tmp_path: Path) -> None:
    service = app(tmp_path).state.szl_series_a_service
    evidence = observed_evidence(service)
    mismatched_refresh = service.evaluate_passport(
        {
            "action": {
                "type": "estate.refresh",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": evidence,
        }
    )
    unapproved_probe = service.evaluate_passport(
        {
            "action": {
                "type": "probe.public_surface",
                "target": "https://example.com/",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": evidence,
        }
    )
    assert mismatched_refresh["passport"]["decision"] == "BLOCK"
    assert mismatched_refresh["passport"]["reason_codes"] == ["TARGET_NOT_ALLOWLISTED"]
    assert unapproved_probe["passport"]["decision"] == "BLOCK"
    assert unapproved_probe["passport"]["reason_codes"] == ["TARGET_NOT_ALLOWLISTED"]


def test_browser_claimed_observation_cannot_authorize_execution(tmp_path: Path) -> None:
    service = app(tmp_path).state.szl_series_a_service
    observed_evidence(service)
    result = service.evaluate_passport(
        {
            "action": {
                "type": "estate.refresh",
                "target": "szl://estate/current",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": [
                {
                    "evidence_id": "browser-claim",
                    "label": "OBSERVED",
                    "content_digest": "e" * 64,
                }
            ],
        }
    )
    assert result["passport"]["decision"] == "BLOCK"
    assert "SERVER_OBSERVED_EVIDENCE_REQUIRED" in result["passport"]["reason_codes"]


def test_blocked_server_snapshot_cannot_authorize_execution(tmp_path: Path) -> None:
    service = app(tmp_path).state.szl_series_a_service
    evidence = observed_evidence(service, status="BLOCKED")
    result = service.evaluate_passport(
        {
            "action": {
                "type": "estate.refresh",
                "target": "szl://estate/current",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": evidence,
        }
    )
    assert result["passport"]["decision"] == "BLOCK"
    assert (
        "OBSERVED_SERVER_EVIDENCE_REQUIRED"
        in result["passport"]["reason_codes"]
    )


def test_server_critical_failure_cannot_be_relabelled_observed(
    tmp_path: Path,
) -> None:
    service = app(tmp_path).state.szl_series_a_service
    evidence = observed_evidence(
        service,
        status="OBSERVED",
        critical_failures=["canonical_a11oy_singleton_failed"],
    )
    assert evidence[0]["label"] == "OBSERVED"

    result = service.evaluate_passport(
        {
            "action": {
                "type": "estate.refresh",
                "target": "szl://estate/current",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": evidence,
        }
    )

    assert result["passport"]["decision"] == "BLOCK"
    assert result["passport"]["reason_codes"] == [
        "BOUNDED_REVERSIBLE_ACTION",
        "CRITICAL_FAILURE_FREE_SERVER_EVIDENCE_REQUIRED",
    ]


def test_event_cursor_resumes_from_last_event_id_and_validates_range() -> None:
    resumed = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/events",
            "query_string": b"",
            "headers": [(b"last-event-id", b"12000")],
        }
    )
    delivered_event_wins = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/events",
            "query_string": b"after=12000",
            "headers": [(b"last-event-id", b"12001")],
        }
    )
    malformed = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/events",
            "query_string": b"",
            "headers": [(b"last-event-id", b"not-a-sequence")],
        }
    )

    assert control._event_cursor(resumed) == 12000
    assert control._event_cursor(delivered_event_wins) == 12001
    with pytest.raises(control.HTTPException) as error:
        control._event_cursor(malformed)
    assert error.value.status_code == 400


def test_frontend_wires_one_attempt_execution_and_live_events(tmp_path: Path) -> None:
    value = app(tmp_path)
    app_digest = control._asset_digest("app.js")
    style_digest = control._asset_digest("styles.css")
    with TestClient(value) as client:
        page = client.get("/series-a")
        script = client.get(f"/series-a/app.js?v={app_digest}")
        style = client.get(f"/series-a/styles.css?v={style_digest}")
        unversioned_script = client.get("/series-a/app.js")
    assert 'id="execute"' in page.text
    assert 'id="execution-result"' in page.text
    assert 'id="events"' in page.text
    assert "szl://estate/current" in page.text
    assert "server-signed snapshot" in page.text
    assert f'/series-a/app.js?v={app_digest}' in page.text
    assert f'/series-a/styles.css?v={style_digest}' in page.text
    assert "__APP_ASSET_DIGEST__" not in page.text
    assert "__STYLE_ASSET_DIGEST__" not in page.text
    assert hashlib.sha256(script.content).hexdigest() == app_digest
    assert hashlib.sha256(style.content).hexdigest() == style_digest
    assert script.headers["cache-control"] == "public,max-age=31536000,immutable"
    assert style.headers["cache-control"] == "public,max-age=31536000,immutable"
    assert unversioned_script.headers["cache-control"] == "no-store"
    assert 'request("/passports/execute"' in script.text
    assert 'request("/refresh"' not in script.text
    assert script.text.count('request("/passports/evaluate"') == 2
    assert script.text.count('request("/passports/execute"') == 2
    assert 'new EventSource(API + "/events")' in script.text
    assert "EVENT_KINDS.forEach" in script.text
    assert "EXECUTION_TIMEOUT_MS = 135000" in script.text
    assert "const revision = ++evaluationRevision" in script.text
    assert "revision !== evaluationRevision" in script.text
    assert 'label: "UNKNOWN"' in script.text
    assert 'selectedLabel === "OBSERVED" && currentEvidence' in script.text
    assert "recoverOutcome" in script.text
    assert "/passports/outcomes/${encodeURIComponent(passportDigest)}" in script.text
    assert "PENDING_RECONCILIATION" in script.text
    assert 'value.outcome?.status !== "SUCCEEDED"' in script.text
    assert "SERIES_A_REFRESH_FAILED" in script.text


def test_source_revision_cannot_make_mismatched_assets_immutable(
    tmp_path: Path, monkeypatch
) -> None:
    source_revision = "a" * 40
    monkeypatch.setenv("SZL_GIT_SHA", source_revision)
    value = app(tmp_path)
    with TestClient(value) as client:
        source_versioned = client.get(f"/series-a/app.js?v={source_revision}")
        content_versioned = client.get(
            f"/series-a/app.js?v={control._asset_digest('app.js')}"
        )
    assert source_versioned.headers["cache-control"] == "no-store"
    assert (
        content_versioned.headers["cache-control"]
        == "public,max-age=31536000,immutable"
    )


def test_asset_cache_digest_and_response_share_one_read(
    tmp_path: Path, monkeypatch
) -> None:
    original = control._asset_bytes
    reads = 0

    def changing_asset(name: str) -> bytes:
        nonlocal reads
        if name != "app.js":
            return original(name)
        reads += 1
        return b"first bytes" if reads == 1 else b"different bytes"

    monkeypatch.setattr(control, "_asset_bytes", changing_asset)
    expected = hashlib.sha256(b"first bytes").hexdigest()
    value = app(tmp_path)
    with TestClient(value) as client:
        response = client.get(f"/series-a/app.js?v={expected}")
    assert reads == 1
    assert response.content == b"first bytes"
    assert hashlib.sha256(response.content).hexdigest() == expected
    assert response.headers["cache-control"] == "public,max-age=31536000,immutable"


def test_execute_rechecks_governance_and_terminalizes_attempt_on_deny(
    tmp_path: Path, monkeypatch
) -> None:
    value = app(tmp_path)
    service = value.state.szl_series_a_service
    passport = service.evaluate_passport(
        {
            "principal_id": "tester",
            "action": {
                "type": "probe.public_surface",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": observed_evidence(service),
        }
    )
    digest = passport["passport_digest"]
    monkeypatch.setattr(
        service,
        "_governance_gate",
        lambda action: {
            "allowed": False,
            "decision": "DENY",
            "reason_codes": ["TEST_GOVERNANCE_DENY"],
            "colang": {"allowed": False},
            "codename_gate": {"allowed": True},
        },
    )

    with TestClient(value) as client:
        first = client.post(
            "/api/a11oy/v1/series-a/passports/execute",
            json={"passport_digest": digest},
        )
        after_first_receipts = client.get(
            "/api/a11oy/v1/series-a/receipts"
        ).json()["items"]
        after_first_events = service.store.events_since(0)
        second = client.post(
            "/api/a11oy/v1/series-a/passports/execute",
            json={"passport_digest": digest},
        )
        after_second_receipts = client.get(
            "/api/a11oy/v1/series-a/receipts"
        ).json()["items"]
        after_second_events = service.store.events_since(0)

    assert first.status_code == 403
    assert first.json()["detail"]["code"] == "GOVERNANCE_DENY"
    assert service.store.load_passport(digest)["attempts"] == 1
    assert after_first_receipts[0]["kind"] == "passport.execution-denied"
    assert after_first_receipts[0]["envelope"]["signature_status"] == "SIGNED"
    assert second.status_code == 409
    assert second.json()["detail"] == "passport attempt already consumed"
    assert after_second_receipts == after_first_receipts
    assert after_second_events == after_first_events


def test_blocked_passport_first_execute_is_terminal_and_replay_is_read_only(
    tmp_path: Path,
) -> None:
    value = app(tmp_path)
    service = value.state.szl_series_a_service
    passport = service.evaluate_passport(
        {
            "principal_id": "tester",
            "action": {
                "type": "probe.public_surface",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": [
                {
                    "evidence_id": "caller-relabel",
                    "label": "OBSERVED",
                    "content_digest": "e" * 64,
                }
            ],
        }
    )
    digest = passport["passport_digest"]
    assert passport["passport"]["decision"] == "BLOCK"

    with TestClient(value) as client:
        first = client.post(
            "/api/a11oy/v1/series-a/passports/execute",
            json={"passport_digest": digest},
        )
        after_first_receipts = client.get(
            "/api/a11oy/v1/series-a/receipts"
        ).json()["items"]
        after_first_events = service.store.events_since(0)
        second = client.post(
            "/api/a11oy/v1/series-a/passports/execute",
            json={"passport_digest": digest},
        )
        after_second_receipts = client.get(
            "/api/a11oy/v1/series-a/receipts"
        ).json()["items"]
        after_second_events = service.store.events_since(0)

    assert first.status_code == 403
    assert first.json()["detail"]["code"] == "PASSPORT_DECISION_DENY"
    assert first.json()["detail"]["reason_codes"] == ["PASSPORT_DECISION_BLOCK"]
    assert service.store.load_passport(digest)["attempts"] == 1
    assert after_first_receipts[0]["kind"] == "passport.execution-denied"
    assert second.status_code == 409
    assert after_second_receipts == after_first_receipts
    assert after_second_events == after_first_events


def test_denied_attempt_compare_and_swap_allows_one_writer(
    tmp_path: Path,
) -> None:
    service = app(tmp_path).state.szl_series_a_service
    passport = service.evaluate_passport(
        {
            "action": {
                "type": "probe.public_surface",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": observed_evidence(service),
        }
    )
    digest = passport["passport_digest"]

    def deny() -> str:
        try:
            service.store.consume_denied_attempt(
                digest,
                {
                    "passport_digest": digest,
                    "reason_codes": ["CONCURRENT_TEST_DENY"],
                },
                service.signer,
            )
        except RuntimeError:
            return "ALREADY_CONSUMED"
        return "TERMINALIZED"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: deny(), range(2)))

    assert sorted(results) == ["ALREADY_CONSUMED", "TERMINALIZED"]
    assert service.store.load_passport(digest)["attempts"] == 1
    denials = [
        item
        for item in service.store.list_receipts()
        if item["kind"] == "passport.execution-denied"
    ]
    assert len(denials) == 1


def test_successful_execution_is_recoverable_by_passport_digest(
    tmp_path: Path, monkeypatch
) -> None:
    value = app(tmp_path)
    service = value.state.szl_series_a_service
    passport = service.evaluate_passport(
        {
            "principal_id": "tester",
            "action": {
                "type": "probe.public_surface",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": observed_evidence(service),
        }
    )
    digest = passport["passport_digest"]

    async def probe(target: str) -> dict[str, object]:
        return {
            "status": "SUCCEEDED",
            "target": target,
            "http_status": 200,
            "latency_ms": 1,
        }

    monkeypatch.setattr(service, "_probe", probe)

    with TestClient(value) as client:
        missing = client.get(
            "/api/a11oy/v1/series-a/passports/outcomes/" + ("f" * 64)
        )
        executed = client.post(
            "/api/a11oy/v1/series-a/passports/execute",
            json={"passport_digest": digest},
        )
        recovered = client.get(
            f"/api/a11oy/v1/series-a/passports/outcomes/{digest}"
        )

    assert missing.status_code == 404
    assert executed.status_code == 200
    assert recovered.status_code == 200
    assert recovered.json()["outcome"] == executed.json()["outcome"]
    assert (
        recovered.json()["outcome_receipt"]["receipt_hash"]
        == executed.json()["outcome_receipt"]["receipt_hash"]
    )
    assert recovered.headers["cache-control"] == "no-store"
    assert recovered.json()["outcome"]["status"] == "SUCCEEDED"
    assert recovered.json()["outcome_receipt"]["kind"] == "passport.outcome"
    execution = service.store.execution_status(digest)
    assert execution["state"] == "COMPLETED"
    assert (
        execution["outcome_receipt_hash"]
        == recovered.json()["outcome_receipt"]["receipt_hash"]
    )


def test_start_reconciles_interrupted_execution_without_replaying_action(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "series-a.sqlite3"
    first = control.Service(str(database))
    evidence = observed_evidence(first)
    passport = first.evaluate_passport(
        {
            "principal_id": "tester",
            "action": {
                "type": "probe.public_surface",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": evidence,
        }
    )
    digest = passport["passport_digest"]
    started_at = "2026-07-28T16:00:00Z"
    first.store.begin_execution(
        digest,
        first.runtime_boot_id,
        started_at,
    )
    assert first.store.outcome_for_passport(digest) is None

    second = control.Service(str(database))
    probes = 0

    async def probe(_target: str) -> dict[str, object]:
        nonlocal probes
        probes += 1
        return {"status": "SUCCEEDED"}

    monkeypatch.setattr(second, "_probe", probe)
    monkeypatch.setenv("A11OY_SERIES_A_STARTUP_REFRESH", "0")
    asyncio.run(second.start())

    recovered = second.store.outcome_for_passport(digest)
    execution = second.store.execution_status(digest)
    assert probes == 0
    assert recovered is not None
    assert recovered["outcome"]["status"] == "FAILED"
    assert recovered["outcome"]["error_class"] == "ExecutionInterrupted"
    assert (
        recovered["outcome"]["reconciliation"]
        == "INTERRUPTED_EXECUTION_RECONCILED"
    )
    assert recovered["outcome"]["started_at"] == started_at
    assert recovered["outcome"]["previous_runtime_boot_id"] == first.runtime_boot_id
    assert "may have started or partially completed" in recovered["outcome"][
        "uncertainty"
    ]
    assert execution["state"] == "RECONCILED"
    assert (
        execution["outcome_receipt_hash"]
        == recovered["outcome_receipt"]["receipt_hash"]
    )
    assert second.store.load_passport(digest)["attempts"] == 1

    receipt_count = len(second.store.list_receipts(200))
    third = control.Service(str(database))
    monkeypatch.setattr(third, "_probe", probe)
    asyncio.run(third.start())
    assert probes == 0
    assert len(third.store.list_receipts(200)) == receipt_count
    assert (
        third.store.outcome_for_passport(digest)["outcome_receipt"][
            "receipt_hash"
        ]
        == recovered["outcome_receipt"]["receipt_hash"]
    )


def test_overlapping_runtime_does_not_reconcile_live_execution(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "series-a.sqlite3"
    first = control.Service(str(database))
    passport = first.evaluate_passport(
        {
            "principal_id": "tester",
            "action": {
                "type": "probe.public_surface",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": observed_evidence(first),
        }
    )
    digest = passport["passport_digest"]
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_probe(target: str) -> dict[str, object]:
        entered.set()
        await release.wait()
        return {
            "status": "SUCCEEDED",
            "target": target,
            "http_status": 200,
            "latency_ms": 1,
        }

    monkeypatch.setattr(first, "_probe", slow_probe)
    monkeypatch.setenv("A11OY_SERIES_A_STARTUP_REFRESH", "0")

    async def scenario() -> None:
        execution = asyncio.create_task(
            first.execute({"passport_digest": digest})
        )
        await entered.wait()
        second = control.Service(str(database))
        await second.start()
        assert second.store.execution_status(digest)["state"] == "PENDING"
        assert second.store.outcome_for_passport(digest) is None
        release.set()
        completed = await execution
        assert completed["outcome"]["status"] == "SUCCEEDED"
        assert second.store.execution_status(digest)["state"] == "COMPLETED"
        assert (
            second.store.outcome_for_passport(digest)["outcome"]["status"]
            == "SUCCEEDED"
        )
        await second.stop()

    asyncio.run(scenario())


def test_receipt_chain_links_exact_previous_hash(tmp_path: Path) -> None:
    value = app(tmp_path)
    service = value.state.szl_series_a_service
    first = service.store.append_receipt("one", {"value": 1}, service.signer)
    second = service.store.append_receipt("two", {"value": 2}, service.signer)
    assert second["receipt"]["previous_receipt_hash"] == first["receipt_hash"]
    decoded = json.loads(base64.b64decode(second["envelope"]["payload"]))
    assert decoded["previous_receipt_hash"] == first["receipt_hash"]


def test_private_reasoning_and_secret_values_are_absent(tmp_path: Path) -> None:
    source = Path(control.__file__).read_text(encoding="utf-8")
    assert "chain_of_thought" not in source
    service = app(tmp_path).state.szl_series_a_service
    value = service.evaluate_passport(
        {
            "action": {
                "type": "estate.refresh",
                "target": "szl://estate/current",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": observed_evidence(service),
        }
    )
    assert value["passport"]["private_reasoning_collected"] is False
    assert "secret_value" not in control._canonical({"secret_name": "HF_TOKEN"}).decode()
