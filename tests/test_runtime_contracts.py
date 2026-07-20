# SPDX-License-Identifier: Apache-2.0
"""Focused fail-closed tests for szl_runtime_contracts."""

import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.testclient import TestClient

import szl_runtime_contracts as contracts


class _GoodStore:
    backend = "sqlite"

    @staticmethod
    def verify():
        return True, 3, -1


class _BrokenStore:
    backend = "sqlite"

    @staticmethod
    def verify():
        return False, 3, 2


class _MemoryStore:
    backend = "memory"

    @staticmethod
    def verify():
        return True, 1, -1


def _app_with_catchall():
    app = FastAPI()

    @app.get("/.well-known/security.txt")
    async def security_txt():
        return PlainTextResponse("Contact: mailto:security@example.invalid")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        return HTMLResponse(f"<html><body>{full_path}</body></html>")

    contracts.register(app)
    return app


def test_registration_is_idempotent_and_routes_beat_existing_spa_catchall():
    app = _app_with_catchall()
    again = contracts.register(app)
    assert again == {"registered": False, "reason": "already_registered"}

    client = TestClient(app)
    for path in (
        "/api/livez",
        "/api/readyz",
        "/api/build-info",
        "/api/a11oy/v1/otel/status",
    ):
        response = client.get(path)
        assert response.headers["content-type"].startswith("application/json")
        assert response.headers["cache-control"] == "no-store"


def test_livez_proves_process_only():
    client = TestClient(_app_with_catchall())
    response = client.get("/api/livez")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "LIVE"
    assert body["process"]["pid"] > 0
    assert "dependency" not in body
    assert body["receipt_minted"] is False


def test_readyz_fails_closed_without_observed_khipu(monkeypatch):
    monkeypatch.setattr(
        contracts,
        "_verify_khipu_store",
        lambda app: {
            "state": "UNKNOWN",
            "source": "test",
            "blocking": True,
        },
    )
    client = TestClient(_app_with_catchall())
    response = client.get("/api/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "NOT_READY"
    assert body["ready"] is False
    assert "khipu" in body["blocking_components"]


def test_readyz_accepts_intact_durable_chain_and_reports_degraded_preflight(monkeypatch):
    monkeypatch.setattr(
        contracts,
        "_boot_preflight",
        lambda: {
            "state": "DEGRADED",
            "source": "test",
            "subsystem_count": 4,
            "blocking": False,
        },
    )
    app = _app_with_catchall()
    app.state.be_khipu = _GoodStore()
    response = TestClient(app).get("/api/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY"
    assert body["components"]["khipu"]["chain_intact"] is True
    assert body["components"]["khipu"]["durable"] is True
    assert body["components"]["boot_preflight"]["state"] == "DEGRADED"


def test_readyz_refuses_broken_or_memory_only_chain(monkeypatch):
    monkeypatch.setattr(
        contracts,
        "_boot_preflight",
        lambda: {"state": "LIVE", "source": "test", "blocking": False},
    )
    for store in (_BrokenStore(), _MemoryStore()):
        app = _app_with_catchall()
        app.state.be_khipu = store
        response = TestClient(app).get("/api/readyz")
        assert response.status_code == 503
        assert response.json()["components"]["khipu"]["blocking"] is True


def test_readyz_refuses_intact_registry_without_durable_store(monkeypatch):
    import szl_khipu_verify

    monkeypatch.setattr(
        szl_khipu_verify,
        "list_organs",
        lambda: {"organs": [{"organ": "test", "links_intact": True}]},
    )
    monkeypatch.setattr(
        contracts,
        "_boot_preflight",
        lambda: {"state": "LIVE", "source": "test", "blocking": False},
    )

    response = TestClient(_app_with_catchall()).get("/api/readyz")
    assert response.status_code == 503
    khipu = response.json()["components"]["khipu"]
    assert khipu["state"] == "NOT_READY"
    assert khipu["chains_intact"] is True
    assert khipu["durable"] is False
    assert khipu["blocking"] is True


def test_build_info_uses_allowlisted_sha_and_never_emits_environment(monkeypatch):
    sha = "a" * 40
    monkeypatch.setenv("GITHUB_SHA", sha)
    monkeypatch.setenv("A11OY_VERSION", "2.1.0-test")
    monkeypatch.setenv("SECRET_TOKEN", "must-not-appear")
    body = TestClient(_app_with_catchall()).get("/api/build-info").json()
    rendered = str(body)
    assert body["build"]["revision"] == sha
    assert body["build"]["revision_source"] == "env:GITHUB_SHA"
    assert body["build"]["version"] == "2.1.0-test"
    assert "must-not-appear" not in rendered
    assert "SECRET_TOKEN" not in rendered


def test_build_info_is_captured_once_and_get_never_spawns_git(monkeypatch):
    calls = []

    for name in contracts._ENV_SHA_NAMES:
        monkeypatch.delenv(name, raising=False)

    def fake_git(args):
        calls.append(tuple(args))
        if args == ["rev-parse", "HEAD"]:
            return type("Result", (), {"returncode": 0, "stdout": "b" * 40})()
        return type("Result", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(contracts, "_safe_git", fake_git)
    app = _app_with_catchall()
    startup_calls = list(calls)
    assert startup_calls == [("rev-parse", "HEAD"), ("status", "--porcelain", "--untracked-files=normal")]

    client = TestClient(app)
    first = client.get("/api/build-info").json()
    second = client.get("/api/build-info").json()
    assert first["build"] == second["build"]
    assert calls == startup_calls


def test_otel_separates_in_process_exporter_and_collector():
    app = _app_with_catchall()
    body = TestClient(app).get("/api/a11oy/v1/otel/status").json()
    assert body["in_process"]["state"] == "UNAVAILABLE"
    assert body["exporter"]["state"] == "UNAVAILABLE"
    assert body["collector"]["state"] == "UNAVAILABLE"
    assert body["receipt_minted"] is False

    app._vsp_otel_installed = True
    app._vsp_otel_exporter = "otlp-grpc:configured:0123456789abcdef"
    app._vsp_otel_endpoint_policy = {
        "state": "CONFIGURED",
        "fingerprint": "0123456789abcdef",
    }
    body = TestClient(app).get("/api/a11oy/v1/otel/status").json()
    assert body["in_process"]["state"] == "LIVE"
    assert body["exporter"]["state"] == "CONFIGURED_UNVERIFIED"
    assert body["exporter"]["delivery_asserted"] is False
    assert body["collector"]["state"] == "UNKNOWN"

    app.state.otel_collector_evidence = {
        "reachable": True,
        "observed_at_unix": time.time(),
    }
    body = TestClient(app).get("/api/a11oy/v1/otel/status").json()
    assert body["collector"]["state"] == "REACHABLE"
    assert body["collector"]["evidence"] == "FRESH_PROBE"
    assert body["status"] == "LIVE"


def test_soft_404_guard_blocks_only_unknown_file_like_spa_fallbacks():
    client = TestClient(_app_with_catchall())

    navigation = client.get("/holographic/brainquery")
    assert navigation.status_code == 200
    assert navigation.headers["content-type"].startswith("text/html")

    unknown_file = client.get("/assets/missing.js")
    assert unknown_file.status_code == 404
    assert unknown_file.json()["status"] == "NOT_FOUND"

    unknown_discovery = client.get("/.well-known/unknown")
    assert unknown_discovery.status_code == 404
    assert unknown_discovery.headers["content-type"].startswith("application/json")

    known_discovery = client.get("/.well-known/security.txt")
    assert known_discovery.status_code == 200
    assert known_discovery.headers["content-type"].startswith("text/plain")


def test_stale_collector_probe_never_becomes_live():
    app = _app_with_catchall()
    app._vsp_otel_installed = True
    app._vsp_otel_exporter = "otlp-grpc:configured:0123456789abcdef"
    app.state.otel_collector_evidence = {
        "reachable": True,
        "observed_at_unix": time.time() - 600,
    }
    body = TestClient(app).get("/api/a11oy/v1/otel/status").json()
    assert body["collector"]["state"] == "UNKNOWN"
    assert body["collector"]["evidence"] == "STALE_OR_INVALID_PROBE"
    assert body["status"] == "DEGRADED"
