import hashlib
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_khipu_demo_nav
import a11oy_nav_wireup
import a11oy_quant_signals_nav
import a11oy_waqay_nav
import a11oy_willay_nav
import a11oy_yupay_nav
from routers import platform_candidate_preview as preview


REVISION = "b" * 40


def _write_candidate(root: Path) -> tuple[bytes, str]:
    index = (
        b"<!doctype html><html><head>"
        b'<link rel="stylesheet" href="/preview/platform-a11oy/assets/app-ABCdef12.css">'
        b'<script src="/preview/platform-a11oy/assets/app-ABCdef12.js"></script>'
        b"</head><body>"
        # These are deliberate legacy-injector anchors. A transformed response
        # would differ from the manifest-bound bytes even when its status is 200.
        b'<div class="nav-group"></div><div class="side-foot"></div>'
        b'["frontier","\\u25c8","Frontier Pipeline"]'
        b"</body></html>"
    )
    files = {
        "index.html": index,
        "assets/app-ABCdef12.css": b"body{color:#fff}",
        "assets/app-ABCdef12.js": b"globalThis.candidate=true;",
    }
    for relative, payload in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    manifest = {
        "schema": preview.SCHEMA,
        "state": preview.STATE,
        "source_repository": preview.SOURCE_REPOSITORY,
        "source_revision": REVISION,
        "base_path": preview.BASE_PATH,
        "production_ready": False,
        "runtime_api_binding": "UNAVAILABLE",
        "effectors": 0,
        "unknown_route_policy": preview.UNKNOWN_ROUTE_POLICY,
        "reviewed_routes": list(preview.REVIEWED_ROUTES),
        "files": [
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
            for relative, payload in sorted(files.items())
        ],
    }
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    (root / "source.json").write_bytes(raw)
    return index, hashlib.sha256(raw).hexdigest()


def test_candidate_no_transform_survives_assembled_nav_middleware_stack(
    tmp_path: Path,
) -> None:
    index, manifest_digest = _write_candidate(tmp_path)
    app = FastAPI()
    preview.register(
        app,
        tmp_path,
        expected_source_revision=REVISION,
        expected_manifest_sha256=manifest_digest,
    )

    # These six injectors are all active in serve.app and historically consumed
    # every HTML body, including the intentionally empty body of a HEAD response.
    for factory in (
        a11oy_quant_signals_nav._make_injector,
        a11oy_khipu_demo_nav._make_injector,
        a11oy_yupay_nav._make_injector,
        a11oy_waqay_nav._make_injector,
        a11oy_willay_nav._make_injector,
        a11oy_nav_wireup._make_injector,
    ):
        app.add_middleware(factory())

    client = TestClient(app)
    get = client.get(preview.PREFIX)
    head = client.head(preview.PREFIX)

    assert get.status_code == head.status_code == 200
    assert get.content == index
    assert hashlib.sha256(get.content).hexdigest() == hashlib.sha256(index).hexdigest()
    assert head.content == b""
    assert get.headers["content-length"] == str(len(index))
    assert head.headers["content-length"] == str(len(index))
    assert get.headers["cache-control"] == "no-store, no-transform"
    assert head.headers["cache-control"] == "no-store, no-transform"
    assert get.headers["x-szl-candidate-manifest-sha256"] == manifest_digest
    assert head.headers["x-szl-candidate-manifest-sha256"] == manifest_digest


def test_full_serve_stack_preserves_active_candidate_get_and_head(
    tmp_path: Path, monkeypatch
) -> None:
    """Exercise the active candidate through every middleware in serve.app."""
    index, manifest_digest = _write_candidate(tmp_path)
    responder = preview.create_responder(
        tmp_path,
        expected_source_revision=REVISION,
        expected_manifest_sha256=manifest_digest,
    )

    import serve

    endpoints = [
        route.endpoint
        for route in serve.app.routes
        if getattr(route, "name", "")
        in {"platform_candidate_preview_root", "platform_candidate_preview_path"}
    ]
    assert len(endpoints) == 2
    for endpoint in endpoints:
        monkeypatch.setattr(endpoint, "_responder", responder)

    client = TestClient(serve.app)
    for path in (preview.PREFIX, preview.PREFIX + "/", preview.PREFIX + "/security-agents"):
        get = client.get(path)
        head = client.head(path)

        assert get.status_code == head.status_code == 200
        assert get.content == index
        assert head.content == b""
        assert get.headers["content-length"] == str(len(index))
        assert head.headers["content-length"] == str(len(index))
        assert get.headers["cache-control"] == "no-store, no-transform"
        assert head.headers["cache-control"] == "no-store, no-transform"
        assert get.headers["x-szl-candidate-manifest-sha256"] == manifest_digest
        assert head.headers["x-szl-candidate-manifest-sha256"] == manifest_digest
