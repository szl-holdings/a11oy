import hashlib
import importlib.util
import json
import subprocess
import sys
import threading
from dataclasses import dataclass
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from routers import platform_candidate_preview as preview


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "verify_platform_candidate_preview.py"
SPEC = importlib.util.spec_from_file_location("verify_platform_candidate_preview", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verifier
SPEC.loader.exec_module(verifier)

ORIGIN = "https://candidate.example"
REVISION = "a" * 40
ASSET_PATH = "assets/app-ABCdef12.js"


def test_isolated_cli_ignores_sibling_stdlib_shadow(tmp_path: Path):
    script = tmp_path / SCRIPT.name
    script.write_bytes(SCRIPT.read_bytes())
    (tmp_path / "argparse.py").write_text(
        "import os\nos._exit(0)\n",
        encoding="utf-8",
    )
    arguments = [
        str(script),
        "--base-url",
        "http://not-credential-free.invalid",
    ]

    shadowed = subprocess.run(
        [sys.executable, "-B", *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert shadowed.returncode == 0

    isolated = subprocess.run(
        [sys.executable, "-I", "-B", *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert isolated.returncode == 1
    assert "credential-free HTTPS origin" in isolated.stderr


def test_live_verifier_security_policy_matches_the_serving_router():
    assert verifier.CSP == preview._CSP
    for directive in ("script-src", "style-src", "img-src", "font-src"):
        value = next(
            part for part in verifier.CSP.split("; ") if part.startswith(directive + " ")
        )
        assert "'self'" not in value


@dataclass
class ResponseSpec:
    status: int
    headers: dict[str, str]
    body: bytes
    final_url: str | None = None


class FakeResponse:
    def __init__(self, url: str, spec: ResponseSpec):
        self.status = spec.status
        self._url = spec.final_url or url
        self._body = spec.body
        self._offset = 0
        self.headers = Message()
        for name, value in spec.headers.items():
            self.headers.add_header(name, value)

    def geturl(self):
        return self._url

    def getcode(self):
        return self.status

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self._body) - self._offset
        start = self._offset
        self._offset = min(len(self._body), self._offset + size)
        return self._body[start : self._offset]

    def close(self):
        return None


class FakeOpener:
    def __init__(self, responses: dict[tuple[str, str], ResponseSpec]):
        self.responses = responses
        self.calls: list[tuple[str, str, float]] = []

    def __call__(self, request, *, timeout):
        key = (request.get_method(), request.full_url)
        self.calls.append((key[0], key[1], timeout))
        if key not in self.responses:
            raise OSError(f"unexpected request: {key}")
        return FakeResponse(request.full_url, self.responses[key])


def _headers(content_type: str, size: int, digest: str) -> dict[str, str]:
    return {
        **{name: value for name, value in verifier.STATIC_HEADERS.items()},
        "Content-Type": content_type,
        "Content-Length": str(size),
        "X-SZL-Platform-Source-Revision": REVISION,
        "X-SZL-Candidate-Manifest-SHA256": digest,
    }


def _site(
    *,
    manifest_updates: dict[str, object] | None = None,
    index: bytes | None = None,
    additional_assets: dict[str, bytes] | None = None,
) -> tuple[FakeOpener, bytes, bytes, str]:
    index = index or (
        b"<!doctype html><html><body><h1>Candidate</h1>"
        b'<script src="/preview/platform-a11oy/assets/app-ABCdef12.js"></script>'
        b"</body></html>"
    )
    asset = b"globalThis.platformCandidate = true;"
    files = {
        "index.html": index,
        ASSET_PATH: asset,
    }
    files.update(additional_assets or {})
    manifest: dict[str, object] = {
        "schema": verifier.SCHEMA,
        "state": verifier.STATE,
        "source_repository": verifier.SOURCE_REPOSITORY,
        "source_revision": REVISION,
        "base_path": verifier.BASE_PATH,
        "production_ready": False,
        "runtime_api_binding": "UNAVAILABLE",
        "effectors": 0,
        "unknown_route_policy": verifier.UNKNOWN_ROUTE_POLICY,
        "reviewed_routes": list(verifier.REVIEWED_ROUTES),
        "files": [
            {
                "path": path,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
            for path, payload in sorted(files.items())
        ],
    }
    manifest.update(manifest_updates or {})
    raw_manifest = json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    manifest_digest = hashlib.sha256(raw_manifest).hexdigest()
    responses: dict[tuple[str, str], ResponseSpec] = {}

    def add_pair(path: str, body: bytes, content_type: str, status: int = 200) -> None:
        url = ORIGIN + path
        headers = _headers(content_type, len(body), manifest_digest)
        responses[("GET", url)] = ResponseSpec(status, dict(headers), body)
        responses[("HEAD", url)] = ResponseSpec(status, dict(headers), b"")

    add_pair(verifier.PREFIX + "/source.json", raw_manifest, "application/json")
    rejection = b'{"state":"METHOD_NOT_ALLOWED"}'
    rejection_headers = _headers("application/json", len(rejection), manifest_digest)
    rejection_headers["Allow"] = "GET, HEAD"
    for method in verifier.REJECTED_METHODS:
        responses[(method, ORIGIN + verifier.PREFIX + "/source.json")] = ResponseSpec(
            405, dict(rejection_headers), rejection
        )
    for path in verifier.INDEX_PATHS:
        add_pair(path, index, "text/html; charset=utf-8")
    add_pair(verifier.PREFIX + "/security-agents", index, "text/html; charset=utf-8")
    for path, payload in sorted(files.items()):
        if path == "index.html":
            continue
        suffix = "." + path.rsplit(".", 1)[1].lower()
        add_pair(
            verifier.PREFIX + "/" + path,
            payload,
            verifier.MEDIA_TYPES[suffix] + "; charset=utf-8",
        )
    add_pair(
        verifier.PREFIX + verifier.UNKNOWN_PROBE,
        b'{"state":"NOT_FOUND"}',
        "application/json",
        status=404,
    )
    return FakeOpener(responses), raw_manifest, asset, manifest_digest


def test_live_candidate_contract_passes_with_exact_bytes_and_headers():
    opener, _, _, manifest_digest = _site()
    report = verifier.verify(
        ORIGIN + "/",
        opener=opener,
        expected_source_revision=REVISION,
        expected_manifest_sha256=manifest_digest,
    )

    assert report == {
        "schema": verifier.REPORT_SCHEMA,
        "status": "PASS",
        "base_url": ORIGIN,
        "source_revision": REVISION,
        "manifest_sha256": manifest_digest,
        "verified_assets": [ASSET_PATH],
        "verified_routes": ["/", "/security-agents"],
        "verified_index_paths": [
            verifier.PREFIX,
            verifier.BASE_PATH,
            verifier.PREFIX + "/index.html",
        ],
        "unknown_route_status": 404,
        "rejected_methods": ["POST"],
    }
    assert len(opener.calls) == 15
    assert {method for method, _, _ in opener.calls} == {"GET", "HEAD", "POST"}


PRODUCT_ORIGIN = "https://a-11-oy.com"
WEBMCP_BRIDGE = PRODUCT_ORIGIN + "/.webmcp/bridge.js"
BRIDGE_CSP = verifier.CSP.replace(
    "; script-src-attr", f" {WEBMCP_BRIDGE}; script-src-attr", 1
)
PRODUCT_HTML_PATHS = (
    *verifier.INDEX_PATHS,
    *(verifier.PREFIX + route for route in verifier.REVIEWED_ROUTES if route != "/"),
)


def _product_site(monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "ORIGIN", PRODUCT_ORIGIN)
    return _site()


def test_product_html_requires_the_origin_csp(monkeypatch):
    opener, manifest, _, digest = _product_site(monkeypatch)
    report = verifier.verify(
        PRODUCT_ORIGIN,
        opener=opener,
        expected_source_revision=REVISION,
        expected_manifest_sha256=digest,
    )
    assert report["status"] == "PASS"
    assert report["manifest_sha256"] == hashlib.sha256(manifest).hexdigest()


@pytest.mark.parametrize(
    "wrong_csp",
    [
        BRIDGE_CSP,
        BRIDGE_CSP.replace(
            WEBMCP_BRIDGE,
            "https://example.com/.webmcp/bridge.js",
        ),
        BRIDGE_CSP.replace(
            WEBMCP_BRIDGE,
            WEBMCP_BRIDGE + " " + WEBMCP_BRIDGE,
        ),
        verifier.CSP + "; connect-src https://example.com",
    ],
    ids=["bridge", "foreign-bridge", "duplicate-bridge", "extra-directive"],
)
@pytest.mark.parametrize("path", PRODUCT_HTML_PATHS)
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_product_html_rejects_bridge_source_and_other_csp_mutations(
    monkeypatch, wrong_csp, path, method
):
    opener, _, _, _ = _product_site(monkeypatch)
    opener.responses[(method, ORIGIN + path)].headers[
        "content-security-policy"
    ] = wrong_csp
    with pytest.raises(verifier.VerificationError, match="invalid content-security-policy") as error:
        verifier.verify(PRODUCT_ORIGIN, opener=opener)
    assert str(error.value).startswith(f"{method} {ORIGIN + path} ")


@pytest.mark.parametrize("path", [verifier.PREFIX + "/source.json", verifier.PREFIX + "/" + ASSET_PATH])
def test_product_non_html_keeps_origin_csp(monkeypatch, path):
    opener, _, _, _ = _product_site(monkeypatch)
    opener.responses[("GET", ORIGIN + path)].headers[
        "content-security-policy"
    ] = BRIDGE_CSP
    with pytest.raises(verifier.VerificationError, match="invalid content-security-policy"):
        verifier.verify(PRODUCT_ORIGIN, opener=opener)


def test_non_product_origin_rejects_cloudflare_bridge_csp():
    opener, _, _, _ = _site()
    opener.responses[("GET", ORIGIN + verifier.BASE_PATH)].headers[
        "content-security-policy"
    ] = BRIDGE_CSP
    with pytest.raises(verifier.VerificationError, match="invalid content-security-policy"):
        verifier.verify(ORIGIN, opener=opener)


def test_product_html_still_requires_manifest_bytes(monkeypatch):
    opener, _, _, _ = _product_site(monkeypatch)
    opener.responses[("GET", ORIGIN + verifier.BASE_PATH)].body = (
        opener.responses[("GET", ORIGIN + verifier.BASE_PATH)].body.replace(
            b"Candidate", b"Candidxte"
        )
    )
    with pytest.raises(verifier.VerificationError, match="digest disagrees with source.json"):
        verifier.verify(PRODUCT_ORIGIN, opener=opener)


def test_default_opener_never_issues_a_redirect_target_request():
    target_hits: list[str] = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            target_hits.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"target")

        def log_message(self, *_args):
            return None

    target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{target.server_address[1]}/internal",
            )
            self.end_headers()

        def log_message(self, *_args):
            return None

    redirect = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    threads = [
        threading.Thread(target=server.serve_forever, daemon=True)
        for server in (target, redirect)
    ]
    for thread in threads:
        thread.start()
    try:
        observation = verifier._request(
            f"http://127.0.0.1:{redirect.server_address[1]}",
            "/probe",
            "GET",
            limit=1024,
            timeout=2,
            opener=verifier.NO_REDIRECT_OPENER.open,
        )
        assert observation.status == 302
        assert target_hits == []
    finally:
        redirect.shutdown()
        target.shutdown()
        redirect.server_close()
        target.server_close()


@pytest.mark.parametrize(
    "updates",
    [
        {"state": "LIVE"},
        {"source_revision": "0" * 40},
        {"production_ready": True},
        {"runtime_api_binding": "BOUND"},
        {"effectors": 1},
        {"reviewed_routes": ["/", "/frontier"]},
        {"unknown_route_policy": "publication_hold"},
        {"extra": "field"},
    ],
)
def test_manifest_contract_drift_fails_closed(updates):
    opener, _, _, _ = _site(manifest_updates=updates)
    with pytest.raises(verifier.VerificationError, match="source.json"):
        verifier.verify(ORIGIN, opener=opener)


def test_hashed_widget_injection_is_still_rejected():
    injected = (
        b"<!doctype html><body>Candidate"
        b'<script src="/vendor/a11oy-operator-widget.js" data-surface="a11oy"></script>'
        b"</body>"
    )
    opener, _, _, _ = _site(index=injected)
    with pytest.raises(verifier.VerificationError, match="widget injection"):
        verifier.verify(ORIGIN, opener=opener)


def test_provenance_header_drift_fails_closed():
    opener, _, _, _ = _site()
    root = ("GET", ORIGIN + verifier.BASE_PATH)
    opener.responses[root].headers["X-SZL-Candidate-Manifest-SHA256"] = "0" * 64
    with pytest.raises(verifier.VerificationError, match="digest header disagrees"):
        verifier.verify(ORIGIN, opener=opener)


def test_asset_digest_drift_fails_closed():
    opener, _, asset, _ = _site()
    path = ("GET", ORIGIN + verifier.PREFIX + "/" + ASSET_PATH)
    replacement = bytes((value + 1) % 256 for value in asset)
    assert len(replacement) == len(asset)
    opener.responses[path].body = replacement
    with pytest.raises(verifier.VerificationError, match="asset.*digest|digest disagrees"):
        verifier.verify(ORIGIN, opener=opener)


@pytest.mark.parametrize(
    "path", [verifier.PREFIX, verifier.PREFIX + "/index.html"]
)
@pytest.mark.parametrize("mutation", ["missing", "corrupt", "redirect"])
def test_every_index_url_is_live_and_digest_bound(path: str, mutation: str):
    opener, _, _, _ = _site()
    key = ("GET", ORIGIN + path)
    if mutation == "missing":
        del opener.responses[key]
        message = "GET .* failed"
    elif mutation == "corrupt":
        payload = opener.responses[key].body
        opener.responses[key].body = bytes((value + 1) % 256 for value in payload)
        message = "digest disagrees"
    else:
        opener.responses[key].status = 302
        opener.responses[key].headers["Location"] = ORIGIN + verifier.BASE_PATH
        message = "expected 200"
    with pytest.raises(verifier.VerificationError, match=message):
        verifier.verify(ORIGIN, opener=opener)


def test_every_manifest_asset_must_be_live_and_digest_bound():
    second_path = "assets/z-lazy-ZYXwvu98.js"
    second_payload = b"globalThis.lazyCandidate = true;"
    opener, _, _, manifest_digest = _site(
        additional_assets={second_path: second_payload}
    )
    report = verifier.verify(
        ORIGIN,
        opener=opener,
        expected_source_revision=REVISION,
        expected_manifest_sha256=manifest_digest,
    )
    assert report["verified_assets"] == [ASSET_PATH, second_path]

    missing, _, _, _ = _site(additional_assets={second_path: second_payload})
    del missing.responses[("GET", ORIGIN + verifier.PREFIX + "/" + second_path)]
    with pytest.raises(verifier.VerificationError, match="GET .* failed"):
        verifier.verify(ORIGIN, opener=missing)

    corrupt, _, _, _ = _site(additional_assets={second_path: second_payload})
    key = ("GET", ORIGIN + verifier.PREFIX + "/" + second_path)
    corrupt.responses[key].body = bytes(
        (value + 1) % 256 for value in corrupt.responses[key].body
    )
    with pytest.raises(verifier.VerificationError, match="digest disagrees"):
        verifier.verify(ORIGIN, opener=corrupt)


def test_unknown_route_must_be_a_candidate_owned_404():
    opener, _, _, _ = _site()
    for method in ("GET", "HEAD"):
        key = (method, ORIGIN + verifier.PREFIX + verifier.UNKNOWN_PROBE)
        opener.responses[key].status = 200
    with pytest.raises(verifier.VerificationError, match="expected 404"):
        verifier.verify(ORIGIN, opener=opener)


def test_unknown_route_must_return_the_exact_router_body_and_length():
    opener, _, _, _ = _site()
    replacement = b'{"detail":"Not Found"}'
    for method in ("GET", "HEAD"):
        key = (method, ORIGIN + verifier.PREFIX + verifier.UNKNOWN_PROBE)
        opener.responses[key].headers["Content-Length"] = str(len(replacement))
    opener.responses[
        ("GET", ORIGIN + verifier.PREFIX + verifier.UNKNOWN_PROBE)
    ].body = replacement
    with pytest.raises(verifier.VerificationError, match="exact candidate-owned 404 body"):
        verifier.verify(ORIGIN, opener=opener)

    length_drift, _, _, _ = _site()
    key = ("HEAD", ORIGIN + verifier.PREFIX + verifier.UNKNOWN_PROBE)
    length_drift.responses[key].headers["Content-Length"] = "999"
    with pytest.raises(verifier.VerificationError, match="does not match GET Content-Length"):
        verifier.verify(ORIGIN, opener=length_drift)


@pytest.mark.parametrize("method", verifier.REJECTED_METHODS)
def test_non_read_methods_must_be_candidate_owned_rejections(method):
    opener, _, _, _ = _site()
    key = (method, ORIGIN + verifier.PREFIX + "/source.json")
    opener.responses[key].status = 200
    with pytest.raises(verifier.VerificationError, match="expected 405"):
        verifier.verify(ORIGIN, opener=opener)


def test_deeply_nested_manifest_is_a_bounded_verification_failure():
    raw = b"[" * 10_000 + b"]" * 10_000
    with pytest.raises(verifier.VerificationError, match="valid UTF-8 JSON"):
        verifier._parse_manifest(raw)


def test_deeply_nested_method_rejection_is_a_bounded_verification_failure():
    opener, _, _, _ = _site()
    key = ("POST", ORIGIN + verifier.PREFIX + "/source.json")
    payload = b"[" * 10_000 + b"]" * 10_000
    opener.responses[key].body = payload
    opener.responses[key].headers["Content-Length"] = str(len(payload))
    with pytest.raises(verifier.VerificationError, match="did not return JSON"):
        verifier.verify(ORIGIN, opener=opener)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://candidate.example",
        "https://user:secret@candidate.example",
        "https://candidate.example/path",
        "https://candidate.example?query=yes",
    ],
)
def test_base_url_rejects_non_origin_or_credentialed_values(base_url):
    with pytest.raises(verifier.VerificationError, match="credential-free HTTPS origin"):
        verifier.normalize_base_url(base_url)


@pytest.mark.parametrize(
    ("revision", "digest"),
    [("0" * 40, None), (None, "0" * 64)],
)
def test_expected_placeholder_values_are_rejected(revision, digest):
    opener, _, _, _ = _site()
    with pytest.raises(verifier.VerificationError, match="expected (source|manifest)"):
        verifier.verify(
            ORIGIN,
            opener=opener,
            expected_source_revision=revision,
            expected_manifest_sha256=digest,
        )
    assert opener.calls == []


def test_expected_contract_file_is_parsed_without_execution(tmp_path: Path):
    marker = tmp_path / "executed"
    contract = tmp_path / "serve.py"
    contract.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('bad')\n"
        f"_PLATFORM_CANDIDATE_SOURCE_REVISION = {REVISION!r}\n"
        f"_PLATFORM_CANDIDATE_MANIFEST_SHA256 = {'b' * 64!r}\n",
        encoding="utf-8",
    )
    assert verifier.read_expected_contract(contract) == (REVISION, "b" * 64)
    assert not marker.exists()


@pytest.mark.parametrize(
    "source",
    [
        "_PLATFORM_CANDIDATE_SOURCE_REVISION = 'short'\n"
        "_PLATFORM_CANDIDATE_MANIFEST_SHA256 = 'b' * 64\n",
        f"_PLATFORM_CANDIDATE_SOURCE_REVISION = {'0' * 40!r}\n"
        f"_PLATFORM_CANDIDATE_MANIFEST_SHA256 = {'b' * 64!r}\n",
        f"_PLATFORM_CANDIDATE_SOURCE_REVISION = {REVISION!r}\n"
        "_PLATFORM_CANDIDATE_MANIFEST_SHA256 = make_digest()\n",
        f"_PLATFORM_CANDIDATE_SOURCE_REVISION = {REVISION!r}\n"
        f"_PLATFORM_CANDIDATE_SOURCE_REVISION = {REVISION!r}\n"
        f"_PLATFORM_CANDIDATE_MANIFEST_SHA256 = {'b' * 64!r}\n",
        "_PLATFORM_CANDIDATE_SOURCE_REVISION = None\n"
        f"_PLATFORM_CANDIDATE_SOURCE_REVISION = {REVISION!r}\n"
        f"_PLATFORM_CANDIDATE_MANIFEST_SHA256 = {'b' * 64!r}\n",
    ],
)
def test_expected_contract_file_rejects_invalid_or_dynamic_values(
    tmp_path: Path, source: str
):
    contract = tmp_path / "serve.py"
    contract.write_text(source, encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="expected contract file"):
        verifier.read_expected_contract(contract)
