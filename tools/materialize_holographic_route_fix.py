#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one source block, observed {source.count(old)}"
        )
    return source.replace(old, new, 1)


def patch_module() -> None:
    path = ROOT / "szl3d_holographic.py"
    source = path.read_text(encoding="utf-8")
    old = '''    async def _serve_3d(path: str):
        f = _safe_resolve(base, path)
        if f is None:
            return JSONResponse({"error": "3d asset not found", "path": path}, status_code=404)
        ct = _CT.get(f.suffix.lower())
        if ct is None:
            return JSONResponse({"error": "3d asset type not allowlisted", "path": path}, status_code=404)
        # Vendored libs are immutable; toolkit/surfaces change during dev -> shorter cache.
        immutable = "/vendor/" in ("/" + path)
        cache = "public, max-age=31536000, immutable" if immutable else "public, max-age=300"
        return Response(content=f.read_bytes(), media_type=ct, headers={"Cache-Control": cache})

    app.add_api_route("/static/3d/{path:path}", _serve_3d, methods=["GET"], include_in_schema=False)
    registered.append("GET /static/3d/{path}")
'''
    new = '''    def _resolve_3d(path: str):
        f = _safe_resolve(base, path)
        if f is None:
            return None, JSONResponse(
                {"error": "3d asset not found", "path": path}, status_code=404
            )
        ct = _CT.get(f.suffix.lower())
        if ct is None:
            return None, JSONResponse(
                {"error": "3d asset type not allowlisted", "path": path},
                status_code=404,
            )
        # Vendored libs are immutable; toolkit/surfaces change during dev -> shorter cache.
        immutable = "/vendor/" in ("/" + path)
        cache = (
            "public, max-age=31536000, immutable"
            if immutable
            else "public, max-age=300"
        )
        return (f, ct, cache), None

    async def _serve_3d(path: str):
        asset, error = _resolve_3d(path)
        if error is not None:
            return error
        f, ct, cache = asset
        return Response(
            content=f.read_bytes(),
            media_type=ct,
            headers={"Cache-Control": cache},
        )

    async def _head_3d(path: str):
        asset, error = _resolve_3d(path)
        if error is not None:
            return error
        _f, ct, cache = asset
        return Response(
            status_code=200,
            media_type=ct,
            headers={"Cache-Control": cache},
        )

    def _front_move(path: str) -> None:
        """Put exact module routes ahead of any pre-existing SPA catch-all."""
        router = getattr(app, "router", None)
        routes = getattr(router, "routes", None)
        if not isinstance(routes, list):
            return
        matches = [route for route in routes if getattr(route, "path", None) == path]
        if not matches:
            return
        match_ids = {id(route) for route in matches}
        routes[:] = matches + [route for route in routes if id(route) not in match_ids]

    static_path = "/static/3d/{path:path}"
    app.add_api_route(
        static_path, _serve_3d, methods=["GET"], include_in_schema=False
    )
    app.add_api_route(
        static_path, _head_3d, methods=["HEAD"], include_in_schema=False
    )
    _front_move(static_path)
    registered.append("GET,HEAD /static/3d/{path}")
'''
    source = replace_once(source, old, new, "static route")

    old_shell = '''    for route in ("/holographic", f"/{ns}/holographic"):
        app.add_api_route(route, _shell, methods=["GET"], include_in_schema=False)
        registered.append(f"GET {route}")
'''
    new_shell = '''    for route in ("/holographic", f"/{ns}/holographic"):
        app.add_api_route(route, _shell, methods=["GET"], include_in_schema=False)
        _front_move(route)
        registered.append(f"GET {route}")
'''
    source = replace_once(source, old_shell, new_shell, "shell routes")

    old_api = '''    for prefix in (f"/api/{ns}/v1/holographic", "/v1/holographic"):
        app.add_api_route(f"{prefix}/info", _info, methods=["GET"], include_in_schema=False)
        app.add_api_route(f"{prefix}/brain/evidence", _brain_evidence, methods=["GET"], include_in_schema=False)
'''
    new_api = '''    for prefix in (f"/api/{ns}/v1/holographic", "/v1/holographic"):
        info_path = f"{prefix}/info"
        evidence_path = f"{prefix}/brain/evidence"
        app.add_api_route(info_path, _info, methods=["GET"], include_in_schema=False)
        app.add_api_route(
            evidence_path,
            _brain_evidence,
            methods=["GET"],
            include_in_schema=False,
        )
        _front_move(info_path)
        _front_move(evidence_path)
'''
    source = replace_once(source, old_api, new_api, "holographic API routes")

    source = source.replace(
        "registered BEFORE the SPA/proxy catch-all (call this early in serve.py, like the\n"
        "    other in-image vendor routes). Never crashes the app — caller wraps in try/except.",
        "front-inserted ahead of any pre-existing SPA/proxy catch-all, so registration\n"
        "    order cannot shadow static or shell routes. Never crashes the app — caller wraps in try/except.",
        1,
    )
    path.write_text(source, encoding="utf-8")


def write_runtime_test() -> None:
    path = ROOT / "tests" / "test_holographic_static_route_runtime.py"
    path.write_text(
        '''from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import szl3d_holographic as holographic


def _app_with_preexisting_catchall(monkeypatch, tmp_path: Path) -> FastAPI:
    page = tmp_path / "holographic.html"
    page.write_text(
        "<!doctype html><title>A11oy Holographic Operations</title>"
        "<main>The estate, observed—not assumed.</main>",
        encoding="utf-8",
    )
    monkeypatch.setattr(holographic, "_base_dir", lambda: tmp_path)

    app = FastAPI()

    @app.get("/{full_path:path}")
    async def spa_catchall(full_path: str):
        return JSONResponse({"status": "NOT_FOUND", "path": full_path}, status_code=404)

    holographic.register(app, ns="a11oy")
    return app


def _route_indexes(app: FastAPI, path: str) -> list[int]:
    return [
        index
        for index, route in enumerate(app.routes)
        if getattr(route, "path", None) == path
    ]


def _methods(app: FastAPI, path: str) -> set[str]:
    return {
        method
        for route in app.routes
        if getattr(route, "path", None) == path
        for method in getattr(route, "methods", set())
    }


def test_static_get_and_head_beat_a_preexisting_spa_catchall(
    monkeypatch, tmp_path: Path
) -> None:
    app = _app_with_preexisting_catchall(monkeypatch, tmp_path)
    client = TestClient(app)

    static_path = "/static/3d/{path:path}"
    catchall_path = "/{full_path:path}"
    assert {"GET", "HEAD"}.issubset(_methods(app, static_path))
    assert max(_route_indexes(app, static_path)) < min(_route_indexes(app, catchall_path))

    get_response = client.get("/static/3d/holographic.html")
    head_response = client.head("/static/3d/holographic.html")
    assert get_response.status_code == 200
    assert "A11oy Holographic Operations" in get_response.text
    assert "The estate, observed—not assumed." in get_response.text
    assert get_response.headers["cache-control"] == "public, max-age=300"
    assert head_response.status_code == 200
    assert head_response.content == b""
    assert head_response.headers["cache-control"] == "public, max-age=300"


def test_shell_and_info_routes_also_beat_the_spa_catchall(
    monkeypatch, tmp_path: Path
) -> None:
    app = _app_with_preexisting_catchall(monkeypatch, tmp_path)
    client = TestClient(app)

    shell = client.get("/holographic")
    alias = client.get("/a11oy/holographic")
    info = client.get("/api/a11oy/v1/holographic/info")
    assert shell.status_code == 200
    assert alias.status_code == 200
    assert "A11oy Holographic Operations" in shell.text
    assert "A11oy Holographic Operations" in alias.text
    assert info.status_code == 200
    assert info.json()["capability"] == "Shared szl3d 3D toolkit + holographic shell"


def test_missing_and_traversal_assets_remain_fail_closed(
    monkeypatch, tmp_path: Path
) -> None:
    client = TestClient(_app_with_preexisting_catchall(monkeypatch, tmp_path))
    for route in (
        "/static/3d/missing.js",
        "/static/3d/../serve.py",
        "/static/3d/not-allowlisted.bin",
    ):
        response = client.get(route)
        assert response.status_code == 404
''',
        encoding="utf-8",
    )


def update_operational_contract() -> None:
    path = ROOT / "tests" / "test_operational_route_contracts.py"
    source = path.read_text(encoding="utf-8")
    replacement = '''def test_permanent_sync_uses_the_reusable_source_bound_authority() -> None:
    workflow = (ROOT / ".github" / "workflows" / "hf-sync.yml").read_text(
        encoding="utf-8"
    )
    for required in (
        "uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@9aa36ed914e88bdef2873b26c022e0cecb1e6ec8",
        "ref: ${{ github.sha }}",
        "source-revision-variable: SZL_GIT_SHA",
        "source-revision-probe-path: /api/build-info",
        ".github/scripts/verify_canonical_a11oy.py",
        "/api/livez",
        "/api/build-info",
        "/api/a11oy/v1/brain/capabilities",
        "/api/a11oy/v1/readiness/tab-matrix?view=summary",
        "/static/3d/holographic.html",
        "needs: deploy",
        "RELOCK_ISSUE: \"1043\"",
        "Trigger strict post-deployment GitHub/HF parity",
    ):
        assert required in workflow

    for forbidden in (
        "add_space_variable(",
        "duplicate_repo(",
        "create_repo(",
        "delete_repo(",
        "update_repo_settings(",
        "restart_space(",
        "request_space_hardware(",
        "set_space_hardware(",
    ):
        assert forbidden not in workflow


'''
    pattern = re.compile(
        r"def test_permanent_sync_binds_source_and_relocks_live_routes\(\) -> None:\n"
        r".*?\n\ndef test_capability_source_has_no_mutation_route",
        re.DOTALL,
    )
    updated, count = pattern.subn(
        replacement + "def test_capability_source_has_no_mutation_route",
        source,
        count=1,
    )
    if count != 1:
        raise RuntimeError("expected operational workflow test block was not replaced")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    patch_module()
    write_runtime_test()
    update_operational_contract()


if __name__ == "__main__":
    main()
