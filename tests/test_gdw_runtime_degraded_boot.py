"""A storage fault at boot degrades the service; it never exits the process.

2026-10-04..06: gdw_runtime.main() re-raised a storage integrity failure, so
the Space exited before serve.py and crash-looped for about 41 hours. These
tests pin the new contract: BLOCKED is recorded, serve.py still runs, GDW write
routes answer 503 + Retry-After, readiness answers 503 with the reason, and
liveness stays 200.
"""

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import gdw_runtime
import szl_be_hardening
from routers import gdw_frontier
from tests.test_gdw_frontier import headers, make_app, payload

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    monkeypatch.setattr(
        gdw_runtime, "_STATE", json.loads(json.dumps(gdw_runtime._STATE))
    )
    gdw_runtime._STATE.update(startup_state="NOT_RUN", blocked=None, error=None)


def _block(message="GDW SQLite integrity check failed: Page 362: never used"):
    return gdw_runtime._record_blocked(
        gdw_runtime.GDWRuntimeError(message), phase="storage_preparation"
    )


# ---- main(): degrade, then serve -------------------------------------------
def test_prepare_failure_records_blocked_and_still_serves(monkeypatch):
    served = []
    monkeypatch.setattr(gdw_runtime.durable_storage, "enabled", lambda *a, **k: False)

    def failing_prepare():
        raise gdw_runtime.GDWRuntimeError(
            "GDW SQLite integrity check failed: *** in database main ***"
        )

    def fake_serve():
        served.append(gdw_runtime.runtime_health())

    monkeypatch.setattr(gdw_runtime, "prepare_runtime", failing_prepare)
    monkeypatch.setattr(gdw_runtime, "_serve", fake_serve)

    assert gdw_runtime.main() == 0

    assert len(served) == 1, "serve.py must run exactly once even when storage fails"
    state = served[0]
    assert state["startup_state"] == "BLOCKED"
    assert state["blocked"]["reason"] == "GDW_STORAGE_BLOCKED"
    assert state["blocked"]["error_class"] == "GDWRuntimeError"
    assert "integrity check failed" in state["blocked"]["error"]
    assert state["drain"]["last_outcome"] == "STORAGE_BLOCKED"
    assert state["drain"]["running"] is False
    block = gdw_runtime.storage_block()
    assert block["startup_state"] == "BLOCKED"
    assert block["retry_after_seconds"] == gdw_runtime.STORAGE_BLOCKED_RETRY_AFTER_SECONDS


def test_healthy_boot_is_unchanged(monkeypatch):
    served = []
    monkeypatch.setattr(gdw_runtime.durable_storage, "enabled", lambda *a, **k: False)
    monkeypatch.delenv("GDW_OUTBOX_ENABLED", raising=False)

    def ready_prepare():
        with gdw_runtime._STATE_LOCK:
            gdw_runtime._STATE.update(startup_state="READY", blocked=None)
        return {}

    monkeypatch.setattr(gdw_runtime, "prepare_runtime", ready_prepare)
    monkeypatch.setattr(gdw_runtime, "_serve", lambda: served.append(True))

    assert gdw_runtime.main() == 0
    assert served == [True]
    assert gdw_runtime.storage_block() is None
    assert gdw_runtime.runtime_health()["drain"]["last_outcome"] == "DISABLED"


def test_outbox_misconfiguration_degrades_instead_of_exiting(monkeypatch):
    served = []
    monkeypatch.setattr(gdw_runtime.durable_storage, "enabled", lambda *a, **k: False)
    monkeypatch.setattr(gdw_runtime, "prepare_runtime", lambda: {})
    monkeypatch.setattr(gdw_runtime, "_serve", lambda: served.append(True))
    monkeypatch.setenv("GDW_OUTBOX_INTERVAL_SECONDS", "not-a-number")

    assert gdw_runtime.main() == 0
    assert served == [True]
    assert gdw_runtime.storage_block()["phase"] == "outbox_supervisor"


def test_durable_activation_failure_degrades_and_closes_coordinator(monkeypatch):
    calls = []
    coordinator = types.ModuleType("gdw_durable_startup")

    def activate():
        calls.append("activate")
        raise RuntimeError("RUNTIME_INSTALLED_SOURCE_UNQUALIFIED")

    coordinator.activate = activate
    coordinator.close = lambda: calls.append("close")
    monkeypatch.setitem(sys.modules, "gdw_durable_startup", coordinator)
    monkeypatch.setattr(gdw_runtime.durable_storage, "enabled", lambda *a, **k: True)
    monkeypatch.setattr(
        gdw_runtime, "prepare_runtime", lambda: pytest.fail("must not prepare")
    )
    monkeypatch.setattr(gdw_runtime, "_serve", lambda: calls.append("serve"))

    assert gdw_runtime.main() == 0
    assert calls == ["activate", "serve", "close"]
    assert gdw_runtime.storage_block()["error"] == "RUNTIME_INSTALLED_SOURCE_UNQUALIFIED"


def test_real_entrypoint_process_survives_missing_mount(tmp_path):
    """The actual entrypoint, a real contract failure, a real process."""

    env = dict(os.environ)
    env.update(
        GDW_REQUIRE_PERSISTENT_STORAGE="1",
        GDW_REQUIRED_MOUNT=str(tmp_path / "not-a-mount"),
        GDW_DB_PATH=str(tmp_path / "not-a-mount" / "gdw.sqlite3"),
        GDW_PROOF_DIR=str(tmp_path / "not-a-mount" / "proofs"),
        GDW_RECEIPT_PROJECTION_DIR=str(tmp_path / "not-a-mount" / "receipts"),
        GDW_SQLITE_JOURNAL="DELETE",
        PYTHONDONTWRITEBYTECODE="1",
    )
    env.pop("GDW_DURABLE_STORAGE", None)
    program = (
        "import json, gdw_runtime\n"
        "def _serve():\n"
        "    print('SERVING ' + json.dumps(gdw_runtime.storage_block(), sort_keys=True))\n"
        "gdw_runtime._serve = _serve\n"
        "raise SystemExit(gdw_runtime.main())\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    line = next(line for line in result.stdout.splitlines() if line.startswith("SERVING "))
    block = json.loads(line[len("SERVING "):])
    assert block["startup_state"] == "BLOCKED"
    assert "storage mount is not attached" in block["error"]
    assert "storage BLOCKED; serving degraded" in result.stderr


# ---- HTTP: liveness 200, readiness 503, GDW writes 503 + Retry-After -------
@pytest.fixture
def degraded_client(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    szl_be_hardening.harden(app, organ="a11oy", khipu_path=str(tmp_path / "khipu.sqlite3"))
    with TestClient(app) as client:
        yield client, tmp_path


def test_liveness_stays_up_and_readiness_reports_block(degraded_client):
    client, _tmp = degraded_client
    assert client.get("/readyz").status_code == 200  # healthy before the fault
    _block()

    live = client.get("/healthz")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert client.head("/healthz").status_code == 200

    for path in ("/readyz", "/api/a11oy/v1/readyz"):
        ready = client.get(path)
        assert ready.status_code == 503, path
        body = ready.json()
        assert body["status"] == "degraded"
        assert body["blocked_reason"] == "GDW_STORAGE_BLOCKED"
        assert body["storage"]["startup_state"] == "BLOCKED"
        assert "Page 362: never used" in body["storage"]["error"]
        assert ready.headers["Retry-After"] == str(
            gdw_runtime.STORAGE_BLOCKED_RETRY_AFTER_SECONDS
        )


def test_gdw_write_routes_return_503_with_retry_after(degraded_client):
    client, tmp_path = degraded_client
    _block()

    response = client.post(
        "/api/a11oy/v1/gdw/step", json=payload(), headers=headers("blocked-1")
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == str(
        gdw_runtime.STORAGE_BLOCKED_RETRY_AFTER_SECONDS
    )
    detail = response.json()["detail"]
    assert detail["reason"] == "GDW_STORAGE_BLOCKED"
    assert detail["startup_state"] == "BLOCKED"
    assert detail["error_class"] == "GDWRuntimeError"
    assert detail["readiness"] == "/readyz"
    # The refused write never opened (or created) the store.
    assert not (tmp_path / "gdw.sqlite3").exists()

    # Authentication is still checked first.
    anonymous = client.post(
        "/api/a11oy/v1/gdw/step", json=payload(), headers={"X-Request-Id": "anon"}
    )
    assert anonymous.status_code == 401


def test_gdw_health_names_the_block(degraded_client):
    client, _tmp = degraded_client
    _block()
    body = client.get("/api/a11oy/v1/gdw/healthz").json()
    assert body["write_ready"] is False
    assert "RUNTIME_STORAGE_BLOCKED" in body["write_blockers"]
    assert body["persistence"]["startup_state"] == "BLOCKED"
    assert body["persistence"]["blocked"]["reason"] == "GDW_STORAGE_BLOCKED"


def test_require_write_ready_carries_retry_after_through_envelope(degraded_client):
    client, _tmp = degraded_client
    _block()
    with pytest.raises(gdw_frontier.HTTPException) as raised:
        gdw_frontier._require_write_ready("a11oy")
    assert raised.value.status_code == 503
    assert raised.value.headers["Retry-After"] == str(
        gdw_runtime.STORAGE_BLOCKED_RETRY_AFTER_SECONDS
    )
    assert raised.value.detail["reason"] == "GDW_STORAGE_BLOCKED"


def test_not_run_is_not_a_block(degraded_client):
    client, _tmp = degraded_client
    assert gdw_runtime.storage_block() is None
    assert client.get("/readyz").status_code == 200
    assert "RUNTIME_STORAGE_BLOCKED" not in client.get(
        "/api/a11oy/v1/gdw/healthz"
    ).json()["write_blockers"]


def test_assembled_app_readiness_and_liveness_under_block():
    """serve.py's own /api/a11oy/readyz reads the same BLOCKED state."""

    import serve

    client = TestClient(serve.app, raise_server_exceptions=False)
    root_before = client.get("/").status_code
    _block()
    ready = client.get("/api/a11oy/readyz")
    assert ready.status_code == 503
    assert ready.json()["blocked_reason"] == "GDW_STORAGE_BLOCKED"
    assert ready.json()["status"] == "not_ready"
    assert ready.headers["Retry-After"]
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 503
    assert client.get("/").status_code == root_before
