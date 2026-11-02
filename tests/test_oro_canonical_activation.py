# SPDX-License-Identifier: Apache-2.0
"""Focused evidence for canonical ORO route, image, and storage ownership."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.requests import Request

import a11oy_state_store as state_store
import oro.api as oro_api
from oro.api import (
    ORORuntime,
    OROWriteUnavailable,
    mount_oro,
    mount_oro_before_catchalls,
)
from oro.auth import BearerTokenAuthorizer, OROAuthorizationError
from oro.canonical import require_production_environment
from tests import image_layout


ROOT = Path(__file__).resolve().parents[1]


def _request(
    path: str,
    *,
    method: str = "GET",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": headers or [],
            "client": ("test", 1),
            "server": ("test", 80),
        }
    )


def _development_runtime(monkeypatch, db_path: Path) -> ORORuntime:
    monkeypatch.setenv("SZL_ORO_ENV", "development")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(db_path))
    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")
    monkeypatch.setenv("SZL_ORO_ALLOW_DEVELOPMENT_AUTH", "1")
    return ORORuntime()


def test_root_image_projects_oro_package_and_schemas() -> None:
    layout = image_layout.installed_layout(ROOT)
    assert layout["oro/api.py"] == "oro/api.py"
    assert layout["schemas/oro/v1/plan.schema.json"] == "schemas/oro/v1/plan.schema.json"
    assert layout["schemas/oro/v1/barrier-receipt.schema.json"] == (
        "schemas/oro/v1/barrier-receipt.schema.json"
    )


def test_canonical_environment_defaults_to_production_and_rejects_weaker_mode() -> None:
    environment: dict[str, str] = {}
    assert require_production_environment(environment) == "production"
    assert environment == {"SZL_ORO_ENV": "production"}

    assert require_production_environment({"SZL_ORO_ENV": " PRODUCTION "}) == "production"
    with pytest.raises(oro_api.OROStateError, match="requires SZL_ORO_ENV=production"):
        require_production_environment({"SZL_ORO_ENV": "development"})

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "SZL_ORO_ENV=production" in dockerfile
    source = (ROOT / "serve.py").read_text(encoding="utf-8")
    admission = source.index("_require_canonical_oro_environment()")
    api_import = source.index("from oro.api import", admission)
    assert admission < api_import


def test_state_store_registers_oro_without_exposing_a_path(monkeypatch, tmp_path: Path) -> None:
    spec = next(item for item in state_store.STORES if item.label == "oro")
    assert (spec.kind, spec.local, spec.legacy_env, spec.legacy_default) == (
        "sqlite",
        "oro/oro.sqlite3",
        "SZL_ORO_DB_PATH",
        "oro.sqlite",
    )
    store = state_store.StateStore(
        settings=state_store.Settings(
            root=tmp_path / "state",
            bucket="test-bucket",
            dataset="test-dataset",
            legacy_root=tmp_path / "legacy",
        ),
        objects=None,
    )
    store.role = state_store.ROLE_WRITER
    monkeypatch.setattr(state_store, "_ACTIVE", store)
    public = state_store.status()
    assert "oro" in public["stores"]
    assert str(tmp_path) not in str(public)


def test_v2_blocked_storage_creates_no_oro_database(monkeypatch, tmp_path: Path) -> None:
    managed = tmp_path / "state" / "oro" / "oro.sqlite3"
    legacy = tmp_path / "legacy.sqlite"
    monkeypatch.setenv("A11OY_STATE_STORE", "v2")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(legacy))
    monkeypatch.setattr(state_store, "writable", lambda: False)
    monkeypatch.setattr(state_store, "local_path", lambda label: managed)
    monkeypatch.setattr(
        state_store,
        "status",
        lambda: {"mode": state_store.MODE_FENCED, "role": state_store.ROLE_BLOCKED},
    )

    runtime = ORORuntime()
    status, body = runtime.readiness()
    assert runtime.service is None
    assert status == 503
    assert body["state_store"] == {
        "required": True,
        "writable": False,
        "mode": state_store.MODE_FENCED,
        "role": state_store.ROLE_BLOCKED,
    }
    assert not managed.exists()
    assert not legacy.exists()


def test_v2_writer_path_wins_over_legacy_environment(monkeypatch, tmp_path: Path) -> None:
    managed = tmp_path / "state" / "oro" / "oro.sqlite3"
    legacy = tmp_path / "legacy.sqlite"
    monkeypatch.setenv("A11OY_STATE_STORE", "v2")
    monkeypatch.setattr(state_store, "writable", lambda: True)
    monkeypatch.setattr(state_store, "local_path", lambda label: managed)
    monkeypatch.setattr(
        state_store,
        "status",
        lambda: {"mode": state_store.MODE_FENCED, "role": state_store.ROLE_WRITER},
    )

    runtime = _development_runtime(monkeypatch, legacy)
    try:
        assert runtime.store is not None
        assert runtime.store.path == managed
        assert managed.is_file()
        assert not legacy.exists()
        assert runtime.readiness()[0] == 200
    finally:
        runtime.close()


def test_standalone_path_remains_valid_when_v2_is_disabled(monkeypatch, tmp_path: Path) -> None:
    standalone = tmp_path / "standalone.sqlite"
    monkeypatch.delenv("A11OY_STATE_STORE", raising=False)
    runtime = _development_runtime(monkeypatch, standalone)
    try:
        assert runtime.store is not None
        assert runtime.store.path == standalone
        assert standalone.is_file()
    finally:
        runtime.close()


def test_valid_authorizer_cannot_write_without_production_signer(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("A11OY_STATE_STORE", raising=False)
    monkeypatch.setenv("SZL_ORO_ENV", "production")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str((tmp_path / "production.sqlite").resolve()))
    monkeypatch.setattr(oro_api, "signer_from_environment", lambda production: None)
    monkeypatch.setattr(
        oro_api,
        "authorizer_from_environment",
        lambda production: BearerTokenAuthorizer.development(),
    )
    runtime = ORORuntime()
    application = FastAPI()
    mount_oro(application, runtime=runtime)
    request = _request(
        "/api/a11oy/v1/oro/plans",
        method="POST",
        headers=[
            (
                b"authorization",
                b"Bearer oro-development-explicit-authorization-token",
            )
        ],
    )
    try:
        assert runtime.readiness()[0] == 503
        with pytest.raises(OROWriteUnavailable):
            runtime.authorize_write(request)
        assert OROWriteUnavailable in application.exception_handlers
        assert runtime.store is not None
        assert runtime.store.counts()["plans"] == 0
    finally:
        runtime.close()


def test_invalid_authorization_is_rejected_before_readiness_work(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("A11OY_STATE_STORE", raising=False)
    runtime = _development_runtime(monkeypatch, tmp_path / "authorization-order.sqlite")
    readiness_calls = 0

    def readiness() -> tuple[int, dict[str, object]]:
        nonlocal readiness_calls
        readiness_calls += 1
        return 200, {}

    monkeypatch.setattr(runtime, "readiness", readiness)
    request = _request(
        "/api/a11oy/v1/oro/plans",
        method="POST",
        headers=[(b"authorization", b"Bearer invalid-token")],
    )
    try:
        with pytest.raises(OROAuthorizationError, match="invalid"):
            runtime.authorize_write(request)
        assert readiness_calls == 0
    finally:
        runtime.close()


def test_canonical_routes_are_owned_before_both_catchalls(
    monkeypatch, tmp_path: Path, request
) -> None:
    application = FastAPI()

    @application.api_route(
        "/api/a11oy/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    )
    async def api_catchall(path: str):
        return {"path": path}

    @application.get("/{full_path:path}")
    async def spa_catchall(full_path: str):
        return {"path": full_path}

    monkeypatch.delenv("A11OY_STATE_STORE", raising=False)
    runtime = _development_runtime(monkeypatch, tmp_path / "canonical.sqlite")
    request.addfinalizer(runtime.close)
    mount_oro_before_catchalls(application, runtime=runtime)
    routes = list(application.router.routes)
    api_catchall = next(
        index
        for index, route in enumerate(routes)
        if getattr(route, "path", None) == "/api/a11oy/{path:path}"
    )
    spa_catchall = next(
        index
        for index, route in enumerate(routes)
        if getattr(route, "path", None) == "/{full_path:path}"
    )
    oro_leaves = []
    for index, entry in enumerate(routes):
        nested = getattr(entry, "original_router", None)
        leaves = getattr(nested, "routes", ()) if nested is not None else (entry,)
        for leaf in leaves:
            if getattr(getattr(leaf, "endpoint", None), "__module__", "") == "oro.api":
                oro_leaves.append((index, leaf))

    core_paths = (
        "/oro",
        "/oro/v5",
        "/api/a11oy/v1/oro/healthz",
        "/api/a11oy/v1/oro/readyz",
        "/api/a11oy/v1/oro/contract",
    )
    for path in core_paths:
        owned = [
            (index, route) for index, route in oro_leaves if getattr(route, "path", None) == path
        ]
        assert len(owned) == 1
        index, route = owned[0]
        assert route.endpoint.__module__ == "oro.api"
        assert index < spa_catchall
        if path.startswith("/api/"):
            assert index < api_catchall

    plan_routes = [
        (index, route) for index, route in oro_leaves
        if getattr(route, "path", None) == "/api/a11oy/v1/oro/plans"
    ]
    assert {method for _, route in plan_routes for method in route.methods} >= {"GET", "POST"}
    assert all(route.endpoint.__module__ == "oro.api" for _, route in plan_routes)
    assert all(index < api_catchall for index, _ in plan_routes)


def test_canonical_source_reserves_unknown_oro_paths_from_node() -> None:
    source = (ROOT / "serve.py").read_text(encoding="utf-8")
    assert 'if path == "v1/oro" or path.startswith(_LOCAL_ONLY_A11OY_PREFIXES):' in source
    assert '"v1/oro/",  # ORO namespace must never fall through to Node' in source
    assert "mount_oro_before_catchalls as _mount_oro_before_catchalls" in source
