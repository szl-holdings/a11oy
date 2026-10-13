import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from routers import platform_candidate_preview as preview


REVISION = "a" * 40
PREFIX = preview.PREFIX
ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "console" / "preview" / "platform-a11oy"


def _manifest(files: dict[str, bytes], **updates) -> dict[str, object]:
    document: dict[str, object] = {
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
    document.update(updates)
    return document


def _write_bundle(root: Path, **manifest_updates) -> tuple[dict[str, bytes], str]:
    files = {
        "index.html": (
            b"<!doctype html><title>Candidate</title>"
            b"<h1>A11oy public candidate</h1>"
            b"<p>PUBLICATION HOLD</p>"
            b'<link rel="icon" href="data:image/svg+xml,%3Csvg/%3E">'
            b'<link rel="stylesheet" href="/preview/platform-a11oy/assets/app-ABCdef12.css">'
            b'<script src="/preview/platform-a11oy/assets/app-ABCdef12.js"></script>'
        ),
        "assets/app-ABCdef12.css": b"body{color:#fff}",
        "assets/app-ABCdef12.js": (
            b'import("./route-ZYXwvu98.js");globalThis.candidate=true;'
        ),
        "assets/route-ZYXwvu98.js": b'export{candidate}from"./app-ABCdef12.js";',
    }
    for relative, payload in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    raw = json.dumps(
        _manifest(files, **manifest_updates), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    (root / "source.json").write_bytes(raw)
    return files, hashlib.sha256(raw).hexdigest()


def _rewrite_manifest(
    root: Path, files: dict[str, bytes], **manifest_updates
) -> str:
    raw = json.dumps(
        _manifest(files, **manifest_updates), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    (root / "source.json").write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _app(root: Path, manifest_digest: str, revision: str = REVISION) -> FastAPI:
    app = FastAPI()
    preview.register(
        app,
        root,
        expected_source_revision=revision,
        expected_manifest_sha256=manifest_digest,
    )
    return app


def _assert_security_headers(response, state: str = preview.STATE) -> None:
    assert response.headers["x-szl-candidate-state"] == state
    assert response.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    csp = response.headers["content-security-policy"]
    assert csp == preview._CSP
    for directive in ("script-src", "style-src", "img-src", "font-src"):
        value = next(part for part in csp.split("; ") if part.startswith(directive + " "))
        assert "'self'" not in value
    assert "script-src https://a-11-oy.com/preview/platform-a11oy/" in csp
    assert "https://szlholdings-a11oy.hf.space/preview/platform-a11oy/" in csp
    assert "img-src data:" in csp
    assert "font-src 'none'" in csp
    assert "connect-src 'none'" in csp
    assert "form-action 'none'" in csp
    assert response.headers["permissions-policy"].startswith("camera=()")


def test_get_head_parity_and_cache_boundaries(tmp_path: Path) -> None:
    files, manifest_digest = _write_bundle(tmp_path)
    client = TestClient(_app(tmp_path, manifest_digest))

    cases = (
        (PREFIX, 200, files["index.html"], "text/html"),
        (PREFIX + "/", 200, files["index.html"], "text/html"),
        (PREFIX + "/security-agents", 200, files["index.html"], "text/html"),
        (PREFIX + "/unreviewed-route", 404, None, "application/json"),
        (
            PREFIX + "/assets/app-ABCdef12.js",
            200,
            files["assets/app-ABCdef12.js"],
            "text/javascript",
        ),
        (
            PREFIX + "/assets/route-ZYXwvu98.js",
            200,
            files["assets/route-ZYXwvu98.js"],
            "text/javascript",
        ),
        (PREFIX + "/source.json", 200, (tmp_path / "source.json").read_bytes(), "application/json"),
        (PREFIX + "/assets/missing.js", 404, None, "application/json"),
    )
    for path, status, expected_payload, media_type in cases:
        get = client.get(path)
        head = client.head(path)
        assert get.status_code == head.status_code == status, path
        assert head.content == b"", path
        assert head.headers["content-length"] == get.headers["content-length"], path
        for name in (
            "cache-control",
            "content-security-policy",
            "permissions-policy",
            "referrer-policy",
            "x-content-type-options",
            "x-robots-tag",
            "x-szl-candidate-state",
            "x-szl-platform-source-revision",
            "x-szl-candidate-manifest-sha256",
        ):
            assert head.headers.get(name) == get.headers.get(name), (path, name)
        assert get.headers["content-type"].startswith(media_type), path
        _assert_security_headers(get)
        assert get.headers["x-szl-platform-source-revision"] == REVISION
        assert get.headers["x-szl-candidate-manifest-sha256"] == manifest_digest
        if expected_payload is not None:
            assert get.content == expected_payload, path

    for path in (
        PREFIX,
        PREFIX + "/source.json",
        PREFIX + "/assets/app-ABCdef12.js",
        PREFIX + "/assets/route-ZYXwvu98.js",
    ):
        assert client.get(path).headers["cache-control"] == "no-store, no-transform"


@pytest.mark.parametrize(
    "method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT", "PROPFIND"]
)
def test_mutating_methods_are_not_registered(tmp_path: Path, method: str) -> None:
    _, manifest_digest = _write_bundle(tmp_path)
    response = TestClient(_app(tmp_path, manifest_digest)).request(method, PREFIX)
    assert response.status_code == 405
    assert {item.strip() for item in response.headers["allow"].split(",")} == {"GET", "HEAD"}
    assert response.json() == {"state": "METHOD_NOT_ALLOWED"}
    _assert_security_headers(response)


def test_startup_bound_bundle_is_immutable_after_disk_removal(tmp_path: Path) -> None:
    _, digest = _write_bundle(tmp_path)
    client = TestClient(_app(tmp_path, digest))
    (tmp_path / "source.json").unlink()

    response = client.get(PREFIX)
    assert response.status_code == 200
    assert response.headers["x-szl-platform-source-revision"] == REVISION
    assert response.headers["x-szl-candidate-manifest-sha256"] == digest


def test_absent_or_invalid_bundle_fails_closed_without_provenance(tmp_path: Path) -> None:
    _, digest = _write_bundle(tmp_path)
    (tmp_path / "source.json").unlink()
    client = TestClient(_app(tmp_path, digest))

    for method in ("get", "head"):
        response = getattr(client, method)(PREFIX)
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store, no-transform"
        assert "x-szl-platform-source-revision" not in response.headers
        assert "x-szl-candidate-manifest-sha256" not in response.headers
        _assert_security_headers(response, "UNAVAILABLE")
        if method == "head":
            assert response.content == b""
        else:
            assert response.json()["state"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "updates",
    [
        {"schema": "wrong"},
        {"base_path": "/wrong/"},
        {"source_revision": "b" * 40},
        {"production_ready": True},
        {"runtime_api_binding": "REAL"},
        {"effectors": 1},
        {"reviewed_routes": ["/", "/frontier"]},
        {"unknown_route_policy": "serve_everything"},
        {"unexpected": True},
    ],
)
def test_manifest_contract_mismatch_fails_closed(tmp_path: Path, updates) -> None:
    _, digest = _write_bundle(tmp_path, **updates)
    response = TestClient(_app(tmp_path, digest)).get(PREFIX)
    assert response.status_code == 503
    _assert_security_headers(response, "UNAVAILABLE")


def test_malformed_and_oversized_manifests_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "malformed"
    root.mkdir()
    raw = b"{not-json"
    (root / "source.json").write_bytes(raw)
    response = TestClient(_app(root, hashlib.sha256(raw).hexdigest())).get(PREFIX)
    assert response.status_code == 503

    root = tmp_path / "oversized"
    root.mkdir()
    raw = b"{" + b" " * preview.MANIFEST_LIMIT + b"}"
    (root / "source.json").write_bytes(raw)
    response = TestClient(_app(root, hashlib.sha256(raw).hexdigest())).get(PREFIX)
    assert response.status_code == 503


def test_missing_undeclared_size_and_digest_mismatches_fail_closed(tmp_path: Path) -> None:
    scenarios = []

    missing = tmp_path / "missing"
    _, digest = _write_bundle(missing)
    (missing / "assets/app-ABCdef12.js").unlink()
    scenarios.append((missing, digest))

    undeclared = tmp_path / "undeclared"
    _, digest = _write_bundle(undeclared)
    (undeclared / "undeclared.txt").write_text("extra", encoding="utf-8")
    scenarios.append((undeclared, digest))

    size_mismatch = tmp_path / "size"
    _, digest = _write_bundle(size_mismatch)
    (size_mismatch / "index.html").write_bytes(b"different-size")
    scenarios.append((size_mismatch, digest))

    hash_mismatch = tmp_path / "hash"
    files, digest = _write_bundle(hash_mismatch)
    original = files["assets/route-ZYXwvu98.js"]
    replacement = bytes((byte + 1) % 256 for byte in original)
    assert len(replacement) == len(original)
    (hash_mismatch / "assets/route-ZYXwvu98.js").write_bytes(replacement)
    scenarios.append((hash_mismatch, digest))

    for root, expected_digest in scenarios:
        response = TestClient(_app(root, expected_digest)).get(PREFIX)
        assert response.status_code == 503, root.name
        _assert_security_headers(response, "UNAVAILABLE")


def test_duplicate_and_oversized_file_records_fail_closed(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate"
    files, _ = _write_bundle(duplicate)
    document = _manifest(files)
    document["files"].append(document["files"][0].copy())
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    (duplicate / "source.json").write_bytes(raw)
    response = TestClient(_app(duplicate, hashlib.sha256(raw).hexdigest())).get(PREFIX)
    assert response.status_code == 503

    oversized = tmp_path / "oversized-file"
    files, _ = _write_bundle(oversized)
    document = _manifest(files)
    document["files"][0]["size"] = preview.FILE_LIMIT + 1
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    (oversized / "source.json").write_bytes(raw)
    response = TestClient(_app(oversized, hashlib.sha256(raw).hexdigest())).get(PREFIX)
    assert response.status_code == 503


@pytest.mark.parametrize(
    "relative",
    [
        "build.env",
        "assets/app-ABCdef12.js.map",
        "assets/unfingerprinted.js",
        "assets/image-ABCdef12.svg",
    ],
)
def test_unapproved_candidate_file_types_fail_closed(
    tmp_path: Path, relative: str
) -> None:
    files, _ = _write_bundle(tmp_path)
    payload = b"not public"
    files[relative] = payload
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    digest = _rewrite_manifest(tmp_path, files)
    assert TestClient(_app(tmp_path, digest)).get(PREFIX).status_code == 503


def test_undeclared_resources_fail_closed(tmp_path: Path) -> None:
    undeclared = tmp_path / "undeclared-reference"
    files, _ = _write_bundle(undeclared)
    files["index.html"] += (
        b'<script src="/preview/platform-a11oy/assets/missing-ABCDEFGH.js"></script>'
    )
    (undeclared / "index.html").write_bytes(files["index.html"])
    digest = _rewrite_manifest(undeclared, files)
    assert TestClient(_app(undeclared, digest)).get(PREFIX).status_code == 503


def test_lazy_manifest_asset_remains_exactly_digest_bound(tmp_path: Path) -> None:
    files, _ = _write_bundle(tmp_path)
    lazy_path = "assets/lazy-QWERty12.js"
    lazy_payload = b"globalThis.lazyCandidate=true;"
    files[lazy_path] = lazy_payload
    (tmp_path / lazy_path).write_bytes(lazy_payload)
    digest = _rewrite_manifest(tmp_path, files)
    client = TestClient(_app(tmp_path, digest))
    assert client.get(PREFIX).status_code == 200
    response = client.get(PREFIX + "/" + lazy_path)
    assert response.status_code == 200
    assert response.content == lazy_payload

    replacement = b"globalThis.lazyCandidate=false;"
    assert len(replacement) == len(lazy_payload) + 1
    (tmp_path / lazy_path).write_bytes(replacement)
    assert TestClient(_app(tmp_path, digest)).get(PREFIX).status_code == 503


def test_duplicate_manifest_fields_fail_closed(tmp_path: Path) -> None:
    _, _ = _write_bundle(tmp_path)
    manifest_path = tmp_path / "source.json"
    raw = manifest_path.read_bytes().replace(
        b'"state":"CANDIDATE_DEMO"',
        b'"state":"CANDIDATE_DEMO","state":"CANDIDATE_DEMO"',
        1,
    )
    manifest_path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    assert TestClient(_app(tmp_path, digest)).get(PREFIX).status_code == 503


@pytest.mark.parametrize(
    ("target", "addition"),
    [
        (
            "index.html",
            b'<meta http-equiv="refresh" content="0;url=https://example.invalid">',
        ),
        (
            "assets/app-ABCdef12.css",
            b'@import "data:text/css,body%7Bcolor:red%7D";',
        ),
        (
            "index.html",
            b'<style>body{background:u\\72l("/api/a11oy/v1/honest")}</style>',
        ),
        (
            "index.html",
            b'<main style="background:u\\72l(&quot;/api/a11oy/v1/honest&quot;)"></main>',
        ),
    ],
)
def test_unreviewed_browser_loading_mechanisms_fail_closed(
    tmp_path: Path, target: str, addition: bytes
) -> None:
    files, _ = _write_bundle(tmp_path)
    files[target] += addition
    (tmp_path / target).write_bytes(files[target])
    digest = _rewrite_manifest(tmp_path, files)
    assert TestClient(_app(tmp_path, digest)).get(PREFIX).status_code == 503


@pytest.mark.parametrize(
    "addition",
    [
        b'<link rel="prefetch" href="/api/a11oy/v1/honest">',
        b'<link rel="preconnect" href="https://example.invalid">',
        b'<svg><image href="/api/a11oy/v1/honest"></image></svg>',
        b'<svg><use href="/api/a11oy/v1/honest#node"></use></svg>',
        b'<svg><filter><feImage href="/api/a11oy/v1/honest"></feImage></filter></svg>',
        b'<body background="/api/a11oy/v1/honest"></body>',
        b'<table background="/api/a11oy/v1/honest"></table>',
        b'<iframe srcdoc="&lt;img src=/api/a11oy/v1/honest&gt;"></iframe>',
        b'<link rel="preload" imagesrcset="/api/a11oy/v1/honest 1x" href="/safe">',
    ],
)
def test_unreviewed_html_fetch_primitives_fail_closed(
    tmp_path: Path, addition: bytes
) -> None:
    files, _ = _write_bundle(tmp_path)
    files["index.html"] += addition
    (tmp_path / "index.html").write_bytes(files["index.html"])
    digest = _rewrite_manifest(tmp_path, files)
    assert TestClient(_app(tmp_path, digest)).get(PREFIX).status_code == 503


@pytest.mark.parametrize(
    "addition",
    [
        (
            b'<script src="/api/a11oy/v1/honest" '
            b'SRC="/preview/platform-a11oy/assets/app-ABCdef12.js"></script>'
        ),
        (
            b'<link rel="prefetch" REL="stylesheet" '
            b'href="/preview/platform-a11oy/assets/app-ABCdef12.css">'
        ),
    ],
)
def test_duplicate_html_attributes_fail_closed(
    tmp_path: Path, addition: bytes
) -> None:
    files, _ = _write_bundle(tmp_path)
    files["index.html"] += addition
    (tmp_path / "index.html").write_bytes(files["index.html"])
    digest = _rewrite_manifest(tmp_path, files)
    assert TestClient(_app(tmp_path, digest)).get(PREFIX).status_code == 503


@pytest.mark.parametrize(
    "addition",
    [
        br'@\69mport "/preview/platform-a11oy/assets/route-ZYXwvu98.js";',
        br'@i/**/mport "/preview/platform-a11oy/assets/route-ZYXwvu98.js";',
        br'body{background:u\72l("/api/a11oy/v1/honest")}',
        br'body{background:u/**/rl("/api/a11oy/v1/honest")}',
        br'body{background:image\2d set("/api/a11oy/v1/honest")}',
    ],
)
def test_escaped_or_split_css_fetch_primitives_fail_closed(
    tmp_path: Path, addition: bytes
) -> None:
    files, _ = _write_bundle(tmp_path)
    target = "assets/app-ABCdef12.css"
    files[target] += addition
    (tmp_path / target).write_bytes(files[target])
    digest = _rewrite_manifest(tmp_path, files)
    assert TestClient(_app(tmp_path, digest)).get(PREFIX).status_code == 503


def test_non_fetching_css_escapes_remain_allowed(tmp_path: Path) -> None:
    files, _ = _write_bundle(tmp_path)
    target = "assets/app-ABCdef12.css"
    files[target] += br'.hover\:visible{display:block}'
    (tmp_path / target).write_bytes(files[target])
    digest = _rewrite_manifest(tmp_path, files)
    assert TestClient(_app(tmp_path, digest)).get(PREFIX).status_code == 200


@pytest.mark.parametrize(
    ("revision", "digest"),
    [
        ("0" * 40, None),
        (None, "0" * 64),
    ],
)
def test_placeholder_contract_values_never_activate(
    tmp_path: Path, revision: str | None, digest: str | None
) -> None:
    _, actual_digest = _write_bundle(tmp_path)
    responder = preview.create_responder(
        tmp_path,
        expected_source_revision=revision or REVISION,
        expected_manifest_sha256=digest or actual_digest,
    )
    response = responder("", head=False)
    assert response.status_code == 503
    assert "x-szl-platform-source-revision" not in response.headers


@pytest.mark.parametrize(
    "reference",
    [
        "https://example.invalid/app.js",
        "/assets/app-ABCdef12.js",
        "../assets/app-ABCdef12.js",
    ],
)
def test_resource_references_cannot_escape_preview(
    tmp_path: Path, reference: str
) -> None:
    files, _ = _write_bundle(tmp_path)
    files["index.html"] = (
        b"<!doctype html><title>Candidate</title><script src=\""
        + reference.encode()
        + b'\"></script>'
    )
    (tmp_path / "index.html").write_bytes(files["index.html"])
    digest = _rewrite_manifest(tmp_path, files)
    assert TestClient(_app(tmp_path, digest)).get(PREFIX).status_code == 503


@pytest.mark.parametrize("reference", ["http://[", "//["])
def test_malformed_resource_urls_degrade_only_the_preview(
    tmp_path: Path, reference: str
) -> None:
    files, _ = _write_bundle(tmp_path)
    files["index.html"] = (
        b'<!doctype html><title>Candidate</title><script src="'
        + reference.encode("utf-8")
        + b'"></script>'
    )
    (tmp_path / "index.html").write_bytes(files["index.html"])
    digest = _rewrite_manifest(tmp_path, files)
    response = TestClient(_app(tmp_path, digest)).get(PREFIX)
    assert response.status_code == 503
    _assert_security_headers(response, "UNAVAILABLE")


def test_inventory_entry_and_depth_bounds_fail_closed(tmp_path: Path, monkeypatch) -> None:
    entry_root = tmp_path / "entries"
    _, digest = _write_bundle(entry_root)
    monkeypatch.setattr(preview, "INVENTORY_ENTRY_LIMIT", 2)
    assert TestClient(_app(entry_root, digest)).get(PREFIX).status_code == 503

    depth_root = tmp_path / "depth"
    _, digest = _write_bundle(depth_root)
    monkeypatch.setattr(preview, "INVENTORY_ENTRY_LIMIT", 512)
    monkeypatch.setattr(preview, "DIRECTORY_DEPTH_LIMIT", 0)
    assert TestClient(_app(depth_root, digest)).get(PREFIX).status_code == 503


def test_bundle_validation_runs_once_at_registration(tmp_path: Path, monkeypatch) -> None:
    _, digest = _write_bundle(tmp_path)
    original = preview.load_bundle
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(preview, "load_bundle", counted)
    client = TestClient(_app(tmp_path, digest))
    for _ in range(5):
        assert client.get(PREFIX).status_code == 200
    assert calls == 1


@pytest.mark.parametrize("outside", [False, True])
def test_symlinks_are_rejected(tmp_path: Path, outside: bool) -> None:
    root = tmp_path / "candidate"
    _, digest = _write_bundle(root)
    target = tmp_path / "outside.js" if outside else root / "assets/plain.js"
    if outside:
        target.write_text("outside", encoding="utf-8")
    link = root / "assets/link.js"
    link.symlink_to(target)
    response = TestClient(_app(root, digest)).get(PREFIX)
    assert response.status_code == 503


def test_fifo_manifest_cannot_block_candidate_registration(tmp_path: Path) -> None:
    root = tmp_path / "fifo-candidate"
    root.mkdir()
    try:
        os.mkfifo(root / "source.json")
    except (AttributeError, NotImplementedError, OSError) as error:
        pytest.skip(f"FIFOs unavailable: {error}")

    program = f"""
from pathlib import Path
from routers import platform_candidate_preview as preview
responder = preview.create_responder(
    Path({str(root)!r}),
    expected_source_revision={'a' * 40!r},
    expected_manifest_sha256={'b' * 64!r},
)
assert responder('', head=False).status_code == 503
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", program],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_cyclic_root_symlink_does_not_prevent_app_startup(tmp_path: Path) -> None:
    root = tmp_path / "candidate-loop"
    try:
        root.symlink_to(root.name, target_is_directory=True)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")

    app = _app(root, "b" * 64)
    response = TestClient(app).get(PREFIX)
    assert response.status_code == 503
    assert response.json()["state"] == "UNAVAILABLE"
    _assert_security_headers(response, "UNAVAILABLE")


def test_cyclic_configured_root_does_not_break_unrelated_spa_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    import serve

    root = tmp_path / "configured-candidate-loop"
    try:
        root.symlink_to(root.name, target_is_directory=True)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")

    monkeypatch.setattr(serve, "_PLATFORM_CANDIDATE_ROOT", root)
    response = asyncio.run(
        serve.spa_fallback("unrelated-platform-candidate-cycle-regression")
    )
    assert response.status_code == 200
    assert response.headers["x-szl-route-state"] == "SPA_FALLBACK"

    malformed = asyncio.run(serve.spa_fallback("nul\x00path"))
    assert malformed.status_code == 404


@pytest.mark.parametrize(
    "candidate_path",
    [
        "../serve.py",
        "assets/../../serve.py",
        "assets\\..\\serve.py",
        "%2e%2e/serve.py",
        "%252e%252e/serve.py",
        "assets%2f..%2fserve.py",
        "nul\x00byte",
        "double//slash",
    ],
)
def test_traversal_and_encoded_paths_return_404(tmp_path: Path, candidate_path: str) -> None:
    _, digest = _write_bundle(tmp_path)
    responder = preview.create_responder(
        tmp_path,
        expected_source_revision=REVISION,
        expected_manifest_sha256=digest,
    )
    response = responder(candidate_path, head=False)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store, no-transform"
    assert candidate_path.encode("utf-8") not in response.body


def test_request_path_and_not_found_response_are_bounded(tmp_path: Path) -> None:
    _, digest = _write_bundle(tmp_path)
    responder = preview.create_responder(
        tmp_path,
        expected_source_revision=REVISION,
        expected_manifest_sha256=digest,
    )
    response = responder("x" * 1_000_000, head=False)
    assert response.status_code == 404
    assert len(response.body) < 256
    assert json.loads(response.body) == {"state": "NOT_FOUND"}


def test_registration_is_idempotent_and_detects_collisions(tmp_path: Path) -> None:
    _, digest = _write_bundle(tmp_path)
    app = _app(tmp_path, digest)
    again = preview.register(
        app,
        tmp_path,
        expected_source_revision=REVISION,
        expected_manifest_sha256=digest,
    )
    assert again == {"module": "routers.platform_candidate_preview", "routes": 4, "read_only": True}

    conflicting = FastAPI()

    @conflicting.get(PREFIX)
    async def existing():
        return {"state": "existing"}

    with pytest.raises(RuntimeError, match="route collision"):
        preview.register(
            conflicting,
            tmp_path,
            expected_source_revision=REVISION,
            expected_manifest_sha256=digest,
        )

    nested = FastAPI()

    @nested.get(PREFIX + "/private-admin")
    async def private_admin():
        return {"state": "private"}

    with pytest.raises(RuntimeError, match="route collision"):
        preview.register(
            nested,
            tmp_path,
            expected_source_revision=REVISION,
            expected_manifest_sha256=digest,
        )


def test_registration_preserves_existing_order_and_precedes_all_prior_routes(
    tmp_path: Path,
) -> None:
    _, digest = _write_bundle(tmp_path)
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"state": "ok"}

    @app.get("/{full_path:path}")
    async def fallback(full_path: str):
        return {"fallback": full_path}

    preview.register(
        app,
        tmp_path,
        expected_source_revision=REVISION,
        expected_manifest_sha256=digest,
    )
    paths = [getattr(route, "path", None) for route in app.routes]
    assert paths.index(PREFIX) < paths.index("/health")
    assert paths.index("/health") < paths.index("/{full_path:path}")
    response = TestClient(app).get(PREFIX + "/security-agents")
    assert response.status_code == 200
    assert response.headers["x-szl-candidate-state"] == preview.STATE


def test_preview_precedes_source_and_asset_shaped_dynamic_routes(tmp_path: Path) -> None:
    files, digest = _write_bundle(tmp_path)
    app = FastAPI()

    @app.get("/preview/{surface}/source.json")
    async def dynamic_source(surface: str):
        return {"shadow": surface}

    @app.get("/preview/{surface}/assets/{asset:path}")
    async def dynamic_asset(surface: str, asset: str):
        return {"shadow": surface, "asset": asset}

    @app.post("/preview/{surface}/source.json")
    async def dynamic_mutation(surface: str):
        return {"mutated": surface}

    preview.register(
        app,
        tmp_path,
        expected_source_revision=REVISION,
        expected_manifest_sha256=digest,
    )
    client = TestClient(app)
    source = client.get(PREFIX + "/source.json")
    asset = client.get(PREFIX + "/assets/app-ABCdef12.js")
    assert source.content == (tmp_path / "source.json").read_bytes()
    assert asset.content == files["assets/app-ABCdef12.js"]
    assert source.headers["x-szl-candidate-state"] == preview.STATE
    assert asset.headers["x-szl-candidate-state"] == preview.STATE
    rejected = client.post(PREFIX + "/source.json")
    assert rejected.status_code == 405
    assert rejected.json() == {"state": "METHOD_NOT_ALLOWED"}
    assert rejected.headers["x-szl-candidate-state"] == preview.STATE


def test_preview_rejects_websockets_before_prior_dynamic_routes(tmp_path: Path) -> None:
    _, digest = _write_bundle(tmp_path)
    app = FastAPI()

    @app.websocket("/preview/{surface}/{candidate_path:path}")
    async def dynamic_websocket(websocket, surface: str, candidate_path: str):
        await websocket.accept()
        await websocket.send_json({"shadow": surface, "path": candidate_path})

    preview.register(
        app,
        tmp_path,
        expected_source_revision=REVISION,
        expected_manifest_sha256=digest,
    )

    with TestClient(app) as client:
        for path in (PREFIX, PREFIX + "/source.json"):
            with pytest.raises(WebSocketDisconnect) as rejected:
                with client.websocket_connect(path):
                    pass
            assert rejected.value.code == 1008


def test_real_app_routes_preview_before_spa_and_leaves_root_and_api_owned() -> None:
    import serve

    paths = [getattr(route, "path", None) for route in serve.app.routes]
    assert paths.index(PREFIX) < paths.index("/{full_path:path}")
    assert paths.index(PREFIX + "/{candidate_path:path}") < paths.index("/{full_path:path}")

    client = TestClient(serve.app)
    preview_response = client.get(PREFIX)
    assert preview_response.status_code == 200
    assert preview_response.content == (CANDIDATE / "index.html").read_bytes()
    assert (
        preview_response.headers["x-szl-platform-source-revision"]
        == serve._PLATFORM_CANDIDATE_SOURCE_REVISION
    )
    assert (
        preview_response.headers["x-szl-candidate-manifest-sha256"]
        == serve._PLATFORM_CANDIDATE_MANIFEST_SHA256
    )
    _assert_security_headers(preview_response)

    rejected_options = client.options(PREFIX)
    assert rejected_options.status_code == 405
    assert rejected_options.headers["allow"] == "GET, HEAD"
    assert rejected_options.json() == {"state": "METHOD_NOT_ALLOWED"}
    _assert_security_headers(rejected_options)

    root = client.get("/")
    honest = client.get("/api/a11oy/v1/honest")
    assert root.status_code == 200
    assert honest.status_code == 200
    assert "x-szl-candidate-state" not in root.headers
    assert "x-szl-candidate-state" not in honest.headers

    bypass = client.get("/preview//platform-a11oy/")
    assert bypass.status_code == 404
    assert bypass.headers["cache-control"] == "no-store"
    assert "x-szl-candidate-state" not in bypass.headers

    # TestClient normalizes these spellings onto the owning preview router.  A
    # normalized request is safe only when it carries the candidate contract.
    for normalized in (
        "/preview/platform-a11oy/../platform-a11oy/source.json",
        "/preview%2Fplatform-a11oy/source.json",
    ):
        response = client.get(normalized)
        assert response.status_code == 200
        assert response.content == (CANDIDATE / "source.json").read_bytes()
        _assert_security_headers(response)


def test_checked_in_candidate_manifest_binds_every_served_file() -> None:
    import serve

    bundle = preview.load_bundle(
        CANDIDATE,
        expected_source_revision=serve._PLATFORM_CANDIDATE_SOURCE_REVISION,
        expected_manifest_sha256=serve._PLATFORM_CANDIDATE_MANIFEST_SHA256,
    )
    assert tuple(bundle.reviewed_routes) == preview.REVIEWED_ROUTES
    assert b"/preview/platform-a11oy/assets/" in bundle.payloads["index.html"]
    combined = b"\n".join(bundle.payloads.values())
    assert b"sourceMappingURL=" not in combined
    assert b"/api/graphql" not in combined
    assert b"graphql-ws" not in combined
    assert b"FrontierIntelligence" not in combined
    assert b"opengraph.jpg" not in combined
