# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Verify the transitive startup seam covered by the register-guard exemption.

The real registration chain runs against a temporary SQLite store, with sibling
surfaces isolated. No deployed service, authority, signing key or network is used.
"""

import ast
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "/api/a11oy/v1/series-a/execution-observations"
LINKS = (
    ("serve.py", None, "routers", "frontier_reads", "register"),
    ("routers/frontier_reads.py", "register", "routers", "series_a_control_plane", "register"),
    ("routers/series_a_control_plane.py", "register", "observer_runtime", "register_from_service", None),
    ("observer_runtime.py", "register_from_service", None, "register", None),
)


def registration_link(path, scope_name, module, symbol, member):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    scope = tree if scope_name is None else next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == scope_name
    )
    imported = None
    bound = symbol
    if module is not None:
        imports = [
            (node, alias)
            for node in ast.walk(scope)
            if isinstance(node, ast.ImportFrom) and node.module == module and node.level == 0
            for alias in node.names if alias.name == symbol
        ]
        assert len(imports) == 1, f"{path}: missing or duplicate {module}.{symbol} import"
        imported, alias = imports[0]
        bound = alias.asname or alias.name
    expected = f"{bound}.{member}" if member else bound
    calls = [node for node in ast.walk(scope)
             if isinstance(node, ast.Call) and ast.unparse(node.func) == expected]
    assert len(calls) == 1, f"{path}: missing or duplicate {expected} call"
    call = calls[0]
    assert call.args and isinstance(call.args[0], ast.Name) and call.args[0].id == "app"
    return imported, call


@pytest.mark.parametrize("link", LINKS, ids=["serve", "frontier", "series-a", "observer"])
def test_every_registration_link_remains_connected(link):
    registration_link(*link)


@pytest.fixture
def composed_app(tmp_path, monkeypatch):
    from fastapi import FastAPI

    import a11oy_signing_key
    import routers
    from routers import series_a_control_plane

    for name in ("A11OY_EXECUTION_AUTHORITY_FILE", "A11OY_STATE_STORE",
                 "A11OY_REQUIRE_PERSISTENT_STORAGE", "A11OY_SERIES_A_REQUIRE_MOUNT",
                 "GDW_DURABLE_STORAGE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("A11OY_SERIES_A_DB", str(tmp_path / "series-a.sqlite3"))
    monkeypatch.setenv("A11OY_SERIES_A_SQLITE_JOURNAL", "DELETE")
    monkeypatch.setenv("A11OY_SERIES_A_STARTUP_REFRESH", "0")
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", "registration-fixture-operator")
    monkeypatch.setenv("A11OY_CODE_TENANT", "registration-fixture-tenant")
    monkeypatch.setattr(a11oy_signing_key, "load_signing_key",
                        lambda: (None, "", "unavailable", "fixture has no signing authority"))
    monkeypatch.setattr(series_a_control_plane.a11oy_state_store, "local_path", lambda name: None)
    monkeypatch.setitem(sys.modules, "serve", SimpleNamespace(
        _A11OY_FORECAST={}, _A11OY_CAPS=[], _a11oy_build_chain=lambda n: {"depth": n}))
    for sibling in ("frontier_now_control_plane", "atelier_frontier", "hf_tooling_evidence"):
        monkeypatch.setattr(routers, sibling,
                            SimpleNamespace(register=lambda *a, **k: {"ok": True}), raising=False)
    app = FastAPI()

    @app.get("/{path:path}")
    def fallback(path: str):
        return {"fallback": path}

    # Execute the actual entrypoint import and invocation without importing the
    # entire deployed process. Removing any downstream link loses the routes.
    imported, call = registration_link(*LINKS[0])
    seam = ast.fix_missing_locations(ast.Module(body=[imported, ast.Expr(value=call)], type_ignores=[]))
    exec(compile(seam, "serve.py:frontier-registration", "exec"), {"app": app})
    return app, tmp_path


def observation_routes(app):
    return [route for route in app.routes if getattr(route, "path", "").startswith(PREFIX)]


def test_composed_startup_registers_once_before_catchall(composed_app):
    import observer_runtime as observer
    from routers import series_a_control_plane

    app, _ = composed_app
    subject = app.state.szl_execution_observer
    assert subject.service is app.state.szl_series_a_service
    assert subject.pins is None
    expected = {
        observer.PREFIX + "/challenge": {"POST"},
        observer.PREFIX + "/run": {"POST"},
        observer.PREFIX + "/cancel/{nonce}": {"POST"},
        observer.PREFIX + "/exports/{nonce}": {"GET", "HEAD"},
    }
    routes = observation_routes(app)
    assert len(routes) == len(expected)
    assert {route.path: route.methods for route in routes} == expected
    fallback_index = next(i for i, route in enumerate(app.routes) if route.path == "/{path:path}")
    assert all(app.routes.index(route) < fallback_index for route in routes)
    first_ids = [id(route) for route in routes]
    assert series_a_control_plane.register(app)["state"] == "ALREADY_REGISTERED"
    with pytest.raises(observer.ObserverBlocked, match="OBSERVATION_SERVICE_ALREADY_REGISTERED"):
        observer.register_from_service(app)
    assert [id(route) for route in observation_routes(app)] == first_ids
    assert app.state.szl_execution_observer is subject


def test_composed_observer_gets_do_not_sign_write_or_execute(composed_app, monkeypatch):
    from fastapi.testclient import TestClient

    app, directory = composed_app
    subject = app.state.szl_execution_observer
    effects = []

    def forbidden(*args, **kwargs):
        effects.append("unexpected effect")
        raise AssertionError("GET must not invoke an execution or signing path")

    for method in ("challenge", "run", "cancel", "_sign", "_fixed_adapters"):
        monkeypatch.setattr(subject, method, forbidden)
    monkeypatch.setattr(subject.service.signer, "sign", forbidden)
    monkeypatch.setattr(subject.service.store, "append_event", forbidden)

    def files():
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in directory.iterdir() if path.is_file()}

    before = files()
    client = TestClient(app)
    headers = {"authorization": "Bearer registration-fixture-operator",
               "x-a11oy-tenant": "registration-fixture-tenant"}
    response = client.get(PREFIX + "/exports/absent", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"] == "OBSERVATION_EXPORT_UNAVAILABLE"
    assert response.headers["cache-control"] == "no-store"
    for route in ("/challenge", "/run", "/cancel/absent"):
        response = client.get(PREFIX + route, headers=headers)
        # A GET-only SPA catch-all may answer the unmatched method. Either way,
        # the registered POST handler must not execute for a GET.
        assert response.status_code in (200, 405)
        if response.status_code == 200:
            assert response.json() == {"fallback": (PREFIX + route).lstrip("/")}
    assert effects == []
    assert files() == before
    assert subject._challenges == {} and subject._exports == {}
    assert subject.service.started is False
