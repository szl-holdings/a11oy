#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Frontier Now read-projection and responsive-surface regression tests."""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routers import frontier_now_control_plane as frontier_now
from routers import series_a_control_plane as series_a


def _stamp(offset_seconds: int = 0) -> str:
    value = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _app(tmp_path: Path, monkeypatch) -> FastAPI:
    monkeypatch.setenv("A11OY_SERIES_A_STARTUP_REFRESH", "0")
    monkeypatch.setenv("A11OY_OBSERVE_GITHUB_MAIN", "0")
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    value = FastAPI()
    series_a.register(value, db_path=str(tmp_path / "series-a.sqlite3"))
    frontier_now.register(value)
    return value


def _seed_observed(value: FastAPI) -> str:
    service = value.state.szl_series_a_service
    manifest = {
        "schema": series_a.SCHEMA_MANIFEST,
        "observed_at": _stamp(),
        "valid_until": _stamp(300),
        "source_revision": "a" * 40,
        "organization": "szl-holdings",
        "huggingface_organization": "SZLHOLDINGS",
        "status": "OBSERVED",
        "critical_failures": [],
        "github": {
            "state": "OBSERVED",
            "value": {
                "repository_count": 58,
                "open_pull_request_count": 15,
                "pagination_complete": True,
                "repositories": [
                    {
                        "name": "not-exposed-by-frontier-now",
                        "visibility": "private",
                    }
                ],
            },
            "detail": {"authenticated": True},
        },
        "huggingface": {
            "state": "PARTIAL",
            "value": {
                "categories": {
                    "models": {"state": "OBSERVED", "count": 16, "items": [{"id": "private-model-name"}]},
                    "datasets": {"state": "OBSERVED", "count": 27, "items": []},
                    "spaces": {"state": "OBSERVED", "count": 26, "items": []},
                    "collections": {"state": "OBSERVED", "count": 3, "items": []},
                    "buckets": {"state": "UNAVAILABLE"},
                    "kernels": {"state": "UNAVAILABLE"},
                },
                "canonical_present": True,
                "forbidden_clones_present": [],
                "singleton_ok": True,
            },
            "detail": {"authenticated": True, "errors": {}},
        },
        "counts": {
            "github_repositories": 58,
            "github_open_pull_requests": 15,
            "models": 16,
            "datasets": 27,
            "spaces": 26,
            "collections": 3,
            "buckets": None,
            "kernels": None,
        },
        "claim": "CURRENT_OBSERVATION_NOT_ETERNAL_TRUTH",
        "counterfactual_label": "MODELED",
        "private_reasoning_collected": False,
    }
    return service.store.save_snapshot(
        manifest,
        {"signature_status": "UNAVAILABLE", "reason": "test fixture"},
    )


def test_summary_projects_observation_without_inventing_runtime_parity(
    tmp_path: Path, monkeypatch
) -> None:
    value = _app(tmp_path, monkeypatch)
    digest = _seed_observed(value)

    with TestClient(value) as client:
        response = client.get("/api/a11oy/v1/frontier-now/summary")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["schema"] == frontier_now.SCHEMA_SUMMARY
    assert payload["operating_mode"] == "OBSERVE_ONLY"
    assert payload["observation"]["state"] == "OBSERVED"
    assert payload["observation"]["manifest_digest"] == digest
    assert payload["counts"]["github_repositories"] == 58
    assert payload["counts"]["models"] == 16
    assert payload["last_known_counts"]["state"] == "OBSERVED"
    assert payload["identity"] == {
        "runtime_reported_source_revision": "a" * 40,
        "github_default_branch_revision": None,
        "huggingface_repository_revision": None,
        "runtime_artifact_digest": None,
        "equivalence_state": "UNAVAILABLE",
        "reason": "ESTATE_MANIFEST_DOES_NOT_BIND_SOURCE_TO_HF_OVERLAY_AND_RUNTIME_ARTIFACT",
    }
    assert payload["claim_gate"]["state"] == "FAILED_CLOSED"
    assert payload["claim_gate"]["public_claim_status"] == "HELD"
    assert payload["enforcement"]["effectors"] == []
    assert payload["enforcement"]["external_writes"] == "DISABLED"
    assert payload["private_reasoning_collected"] is False


def test_observed_github_drift_holds_claim_gate(
    tmp_path: Path, monkeypatch
) -> None:
    value = _app(tmp_path, monkeypatch)
    _seed_observed(value)
    drifted = "c" * 40
    monkeypatch.setattr(
        frontier_now, "_observe_github_default_branch", lambda: drifted
    )

    with TestClient(value) as client:
        payload = client.get("/api/a11oy/v1/frontier-now/summary").json()

    identity = payload["identity"]
    assert identity["runtime_reported_source_revision"] == "a" * 40
    assert identity["github_default_branch_revision"] == drifted
    assert identity["huggingface_repository_revision"] is None
    assert identity["runtime_artifact_digest"] is None
    assert identity["equivalence_state"] == "DRIFT"
    assert identity["reason"] == (
        "GITHUB_DEFAULT_BRANCH_DRIFTS_FROM_RUNTIME_REPORTED_REVISION"
    )
    assert payload["claim_gate"]["state"] == "FAILED_CLOSED"
    assert payload["claim_gate"]["public_claim_status"] == "HELD"
    parity = next(
        item for item in payload["frontiers"] if item["id"] == "source-runtime-parity"
    )
    assert parity["state"] == "DRIFT"
    assert parity["source"] == "public-github-main"
    assert payload["enforcement"]["external_writes"] == "DISABLED"


def test_receipt_read_failure_isolated_from_manifest_and_inventory(
    tmp_path: Path, monkeypatch
) -> None:
    value = _app(tmp_path, monkeypatch)
    _seed_observed(value)
    service = value.state.szl_series_a_service
    calls = 0

    def fail_receipts(_limit: int = 8):
        nonlocal calls
        calls += 1
        raise RuntimeError("receipt store unavailable")

    monkeypatch.setattr(service.store, "list_receipts", fail_receipts)

    with TestClient(value) as client:
        summary = client.get("/api/a11oy/v1/frontier-now/summary")
        inventory = client.get("/api/a11oy/v1/frontier-now/inventory")

    assert summary.status_code == 200
    assert summary.json()["observation"]["state"] == "OBSERVED"
    assert summary.json()["proof_rail_state"] == "UNAVAILABLE"
    assert summary.json()["proof_rail"] == []
    assert inventory.status_code == 200
    assert inventory.json()["observation_state"] == "OBSERVED"
    assert calls == 1


def test_inventory_exposes_capability_state_and_counts_not_asset_names(
    tmp_path: Path, monkeypatch
) -> None:
    value = _app(tmp_path, monkeypatch)
    _seed_observed(value)

    with TestClient(value) as client:
        response = client.get(
            "/api/a11oy/v1/frontier-now/inventory?provider=huggingface&limit=10"
        )
        invalid = client.get(
            "/api/a11oy/v1/frontier-now/inventory?provider=unknown"
        )
        duplicate = client.get(
            "/api/a11oy/v1/frontier-now/inventory?limit=1&limit=2"
        )
        oversized = client.get(
            "/api/a11oy/v1/frontier-now/inventory?limit=51"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == frontier_now.SCHEMA_INVENTORY
    assert payload["provider"] == "huggingface"
    assert payload["manifest_digest"] is not None
    assert payload["observation_state"] == "OBSERVED"
    assert payload["total"] == 6
    assert payload["asset_names_exposed"] is False
    assert {item["capability"] for item in payload["items"]} == {
        "models",
        "datasets",
        "spaces",
        "collections",
        "buckets",
        "kernels",
    }
    states = {item["capability"]: item for item in payload["items"]}
    assert states["models"]["count"] == 16
    assert states["models"]["scope"] == "AUTHENTICATED_SCOPE_REDACTED"
    assert states["buckets"]["state"] == "UNAVAILABLE"
    assert states["buckets"]["count"] is None
    encoded = json.dumps(payload, sort_keys=True)
    assert "not-exposed-by-frontier-now" not in encoded
    assert "private-model-name" not in encoded
    assert "GITHUB_TOKEN" not in encoded and "HF_TOKEN" not in encoded
    assert invalid.status_code == 422
    assert duplicate.status_code == 400
    assert oversized.status_code == 422


def test_missing_series_a_service_is_terminal_json_not_spa_html() -> None:
    value = FastAPI()
    frontier_now.register(value)

    with TestClient(value) as client:
        summary = client.get("/api/a11oy/v1/frontier-now/summary")
        inventory = client.get("/api/a11oy/v1/frontier-now/inventory")

    assert summary.status_code == 200
    assert summary.headers["content-type"].startswith("application/json")
    assert summary.json()["observation"]["state"] == "UNAVAILABLE"
    assert summary.json()["enforcement"]["state"] == "FAILED_CLOSED"
    assert inventory.status_code == 200
    assert all(item["state"] == "UNAVAILABLE" for item in inventory.json()["items"])


def test_stale_snapshot_cannot_retain_observed_capabilities_or_current_counts(
    tmp_path: Path, monkeypatch
) -> None:
    value = _app(tmp_path, monkeypatch)
    service = value.state.szl_series_a_service
    _seed_observed(value)
    latest = service.store.latest_snapshot()
    manifest = dict(latest["manifest"])
    manifest["observed_at"] = _stamp(1)
    manifest["valid_until"] = _stamp(-300)
    service.store.save_snapshot(
        manifest,
        {"signature_status": "UNAVAILABLE", "reason": "stale fixture"},
    )

    with TestClient(value) as client:
        summary = client.get("/api/a11oy/v1/frontier-now/summary").json()
        inventory = client.get("/api/a11oy/v1/frontier-now/inventory").json()

    assert summary["observation"]["state"] == "STALE"
    assert all(value is None for value in summary["counts"].values())
    assert summary["last_known_counts"]["values"]["models"] == 16
    assert inventory["observation_state"] == "STALE"
    assert {item["state"] for item in inventory["items"]} <= {
        "STALE",
        "UNAVAILABLE",
    }
    assert all(item["count"] is None for item in inventory["items"])


def test_snapshot_disappearing_between_status_and_read_fails_closed() -> None:
    class VanishingStore:
        def latest_snapshot(self):
            return None

        def list_receipts(self, _limit=8):
            return []

    class VanishingService:
        store = VanishingStore()

        @staticmethod
        def latest_status():
            return {
                "state": "OBSERVED",
                "manifest_digest": "f" * 64,
                "counts": {"github_repositories": 58},
            }

    value = FastAPI()
    value.state.szl_series_a_service = VanishingService()
    frontier_now.register(value)

    with TestClient(value) as client:
        payload = client.get("/api/a11oy/v1/frontier-now/summary").json()

    assert payload["observation"]["state"] == "UNAVAILABLE"
    assert payload["observation"]["manifest_digest"] is None
    assert payload["enforcement"]["state"] == "FAILED_CLOSED"
    assert payload["counts"] == {}


def test_manifest_payload_must_rehash_to_its_persisted_digest() -> None:
    class CorruptStore:
        @staticmethod
        def latest_snapshot():
            return {
                "digest": "f" * 64,
                "manifest": {"status": "OBSERVED", "counts": {"models": 16}},
            }

        @staticmethod
        def list_receipts(_limit=8):
            return []

    class CorruptService:
        store = CorruptStore()

        @staticmethod
        def latest_status():
            return {"state": "OBSERVED", "manifest_digest": "f" * 64}

    value = FastAPI()
    value.state.szl_series_a_service = CorruptService()
    frontier_now.register(value)

    with TestClient(value) as client:
        payload = client.get("/api/a11oy/v1/frontier-now/summary").json()

    assert payload["observation"]["state"] == "UNAVAILABLE"
    assert payload["observation"]["reason"] == "MANIFEST_DIGEST_MISMATCH"
    assert payload["enforcement"]["state"] == "FAILED_CLOSED"
    assert payload["counts"] == {}


def test_get_and_head_are_body_safe_and_side_effect_free(
    tmp_path: Path, monkeypatch
) -> None:
    value = _app(tmp_path, monkeypatch)
    digest = _seed_observed(value)
    service = value.state.szl_series_a_service

    with TestClient(value) as client:
        before_storage = service.store.storage_status()
        before_events = service.store.events_since(0)
        before_snapshot = service.store.latest_snapshot()

        responses = [
            client.get("/frontier-now"),
            client.head("/frontier-now"),
            client.get("/now"),
            client.head("/api/a11oy/v1/frontier-now/summary"),
            client.get("/api/a11oy/v1/frontier-now/summary"),
            client.head("/api/a11oy/v1/frontier-now/inventory"),
            client.get("/api/a11oy/v1/frontier-now/inventory"),
        ]

        after_storage = service.store.storage_status()
        after_events = service.store.events_since(0)
        after_snapshot = service.store.latest_snapshot()

    assert all(response.status_code == 200 for response in responses)
    assert responses[1].content == b""
    assert responses[3].content == b""
    assert responses[5].content == b""
    assert before_storage == after_storage
    assert before_events == after_events
    assert before_snapshot["digest"] == digest == after_snapshot["digest"]


def test_page_assets_are_version_bound_accessible_and_zero_cdn(
    tmp_path: Path, monkeypatch
) -> None:
    value = _app(tmp_path, monkeypatch)
    _seed_observed(value)
    app_digest = frontier_now._asset_digest("app.js")
    style_digest = frontier_now._asset_digest("styles.css")

    with TestClient(value) as client:
        page = client.get("/frontier-now")
        alias = client.get("/now")
        script = client.get(f"/frontier-now/app.js?v={app_digest}")
        style = client.get(f"/frontier-now/styles.css?v={style_digest}")
        unversioned = client.get("/frontier-now/app.js")
        post = client.post("/api/a11oy/v1/frontier-now/summary", json={})

    assert page.status_code == 200 and alias.status_code == 200
    assert page.text == alias.text
    assert "A11oy Frontier NOW" in page.text
    assert 'class="skip-link"' in page.text
    assert 'content="noindex,nofollow"' in page.text
    assert f"/frontier-now/app.js?v={app_digest}" in page.text
    assert f"/frontier-now/styles.css?v={style_digest}" in page.text
    assert "onclick=" not in page.text.lower()
    assert "https://" not in page.text and "http://" not in page.text
    csp = page.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "script-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "form-action 'none'" in csp
    assert "permissions-policy" in page.headers
    assert page.headers["x-content-type-options"] == "nosniff"
    assert script.headers["cache-control"] == "public,max-age=31536000,immutable"
    assert style.headers["cache-control"] == "public,max-age=31536000,immutable"
    assert unversioned.headers["cache-control"] == "no-store"
    assert "AbortController" in script.text
    assert "Promise.allSettled" in script.text
    assert "INVENTORY_MAX_PAGES" in script.text
    assert 'cache: "no-store"' in script.text
    assert "textContent" in script.text
    assert "prefers-reduced-motion" in style.text
    assert "@media (max-width: 560px)" in style.text
    assert re.search(
        r"\.boundary-note\s*\{[^}]*overflow-wrap:\s*anywhere;",
        style.text,
        re.DOTALL,
    )
    assert "rgba(184, 243, 75" not in style.text
    assert "rgba(110, 231, 242" not in style.text
    assert "latest complete census" not in page.text
    assert 'class="graph-node unavailable" id="runtime-source-node"' in page.text
    assert "IMMUTABLE RECEIPT METADATA" not in page.text
    assert post.status_code == 405


def test_trailing_slash_aliases_resolve_before_any_catchall(
    tmp_path: Path, monkeypatch
) -> None:
    value = _app(tmp_path, monkeypatch)
    _seed_observed(value)

    with TestClient(value) as client:
        page = client.get("/frontier-now/")
        alias = client.get("/now/")
        summary = client.get("/api/a11oy/v1/frontier-now/summary/")
        inventory = client.get("/api/a11oy/v1/frontier-now/inventory/")

    assert page.status_code == 200 and "A11oy Frontier NOW" in page.text
    assert alias.status_code == 200 and alias.headers["content-type"].startswith("text/html")
    assert summary.status_code == 200
    assert summary.headers["content-type"].startswith("application/json")
    assert inventory.status_code == 200
    assert inventory.headers["content-type"].startswith("application/json")


def test_page_head_fails_when_a_packaged_dependency_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    value = _app(tmp_path, monkeypatch)
    original = frontier_now._asset_bytes

    def missing_script(name: str) -> bytes:
        if name == "app.js":
            raise HTTPException(status_code=404, detail="asset missing: app.js")
        return original(name)

    monkeypatch.setattr(frontier_now, "_asset_bytes", missing_script)
    with TestClient(value) as client:
        get_response = client.get("/frontier-now")
        head_response = client.head("/frontier-now")

    assert get_response.status_code == 404
    assert head_response.status_code == 404


def test_routes_are_front_moved_before_framework_and_spa_catchalls(
    tmp_path: Path, monkeypatch
) -> None:
    value = _app(tmp_path, monkeypatch)

    @value.get("/{full_path:path}")
    async def spa(full_path: str) -> dict[str, str]:
        return {"full_path": full_path}

    paths = [getattr(route, "path", None) for route in value.router.routes]
    catchall = paths.index("/{full_path:path}")
    for path in (
        "/frontier-now",
        "/frontier-now/",
        "/now",
        "/now/",
        "/api/a11oy/v1/frontier-now/summary",
        "/api/a11oy/v1/frontier-now/summary/",
        "/api/a11oy/v1/frontier-now/inventory",
        "/api/a11oy/v1/frontier-now/inventory/",
    ):
        assert paths.index(path) < catchall
        assert paths.index(path) < paths.index("/openapi.json")


def test_second_registration_requires_and_preserves_the_complete_owned_surface(
    tmp_path: Path, monkeypatch
) -> None:
    value = _app(tmp_path, monkeypatch)
    second = frontier_now.register(value)

    assert second["state"] == "ALREADY_REGISTERED"
    assert len(second["routes"]) == 12
    paths = [getattr(route, "path", None) for route in value.router.routes]
    assert len([path for path in paths if path in second["routes"]]) == 12


def test_partial_or_foreign_route_registration_fails_closed() -> None:
    partial = FastAPI()

    @partial.get("/api/a11oy/v1/frontier-now/summary")
    async def partial_summary() -> dict[str, bool]:
        return {"foreign": True}

    foreign = FastAPI()

    @foreign.get("/now")
    async def foreign_now() -> dict[str, bool]:
        return {"foreign": True}

    with pytest.raises(RuntimeError, match="FRONTIER_NOW_ROUTE_COLLISION"):
        frontier_now.register(partial)
    with pytest.raises(RuntimeError, match="FRONTIER_NOW_ROUTE_COLLISION"):
        frontier_now.register(foreign)
