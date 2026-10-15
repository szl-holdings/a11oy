#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Fail-closed browser witness for the two Platform candidate preview routes.

The witness has two fixed public origins and performs only browser-initiated GETs.
Every document and asset response must equal the source-controlled candidate bundle.
The product origin additionally has one narrowly pinned Cloudflare Speed Brain request;
that request is reported as provider-owned and is never treated as product behavior.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = ROOT / "console" / "preview" / "platform-a11oy"
PRODUCT_ORIGIN = "https://a-11-oy.com"
SPACE_ORIGIN = "https://szlholdings-a11oy.hf.space"
ALLOWED_ORIGINS = (PRODUCT_ORIGIN, SPACE_ORIGIN)
PREFIX = "/preview/platform-a11oy"
BASE_PATH = PREFIX + "/"
REVIEWED_ROUTES = {
    "/": "A source-bound interface preview with explicit evidence limits",
    "/security-agents": "AI Security Operations",
}
SCHEMA = "szl.platform-static-candidate/v1"
STATE = "CANDIDATE_DEMO"
SOURCE_REPOSITORY = "https://github.com/szl-holdings/platform"
REPORT_SCHEMA = "szl.platform-static-candidate-browser-witness/v1"

REVISION = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
ASSET_PATH = re.compile(
    r"assets/[A-Za-z0-9_.-]+-[A-Za-z0-9_-]{8,}\.(?:css|js)\Z"
)
MANIFEST_KEYS = {
    "schema",
    "state",
    "source_repository",
    "source_revision",
    "base_path",
    "production_ready",
    "runtime_api_binding",
    "effectors",
    "unknown_route_policy",
    "reviewed_routes",
    "files",
}
MEDIA_TYPES = {".css": "text/css", ".js": "text/javascript"}
CANDIDATE_CONTENT_TYPES = {
    "text/html": "text/html; charset=utf-8",
    "text/css": "text/css; charset=utf-8",
    "text/javascript": "text/javascript; charset=utf-8",
}

CANONICAL_CSP = (
    "default-src 'none'; "
    "script-src https://a-11-oy.com/preview/platform-a11oy/ "
    "https://szlholdings-a11oy.hf.space/preview/platform-a11oy/; "
    "script-src-attr 'none'; "
    "style-src 'unsafe-inline' https://a-11-oy.com/preview/platform-a11oy/ "
    "https://szlholdings-a11oy.hf.space/preview/platform-a11oy/; "
    "img-src data:; "
    "font-src 'none'; "
    "connect-src 'none'; "
    "media-src 'none'; "
    "frame-src 'none'; "
    "child-src 'none'; "
    "worker-src 'none'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "manifest-src 'none'; "
    "frame-ancestors 'self' https://huggingface.co https://*.hf.space "
    "https://*.huggingface.co"
)
PRODUCT_EDGE_SCRIPT_SOURCE = PRODUCT_ORIGIN + "/.webmcp/bridge.js"
STATIC_HEADERS = {
    "cache-control": "no-store, no-transform",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-robots-tag": "noindex, nofollow, noarchive",
    "x-szl-candidate-state": STATE,
}

EDGE_SPECULATION_PATH = "/cdn-cgi/speculation"
EDGE_SPECULATION_URL = PRODUCT_ORIGIN + EDGE_SPECULATION_PATH
EDGE_SPECULATION_HEADER = '"/cdn-cgi/speculation"'
EDGE_SPECULATION_MEDIA_TYPE = "application/speculationrules+json"
EDGE_SPECULATION_BODY = (
    b'{"tag":"cf-speed-brain","prefetch":[{"eagerness":"conservative",'
    b'"source":"document","where":{"and":[{"href_matches":"/*",'
    b'"relative_to":"document"}]}}]}'
)
EDGE_SPECULATION_SIZE = 151
EDGE_SPECULATION_SHA256 = (
    "4d958f26d792adc0b7c79e26bb5264ff3ae27f6f32c1f67cbdcbe8b765b7f9fb"
)
EDGE_SPECULATION_SCHEMA = {
    "tag": "cf-speed-brain",
    "prefetch": [
        {
            "eagerness": "conservative",
            "source": "document",
            "where": {
                "and": [
                    {"href_matches": "/*", "relative_to": "document"},
                ]
            },
        }
    ],
}
if (
    len(EDGE_SPECULATION_BODY) != EDGE_SPECULATION_SIZE
    or hashlib.sha256(EDGE_SPECULATION_BODY).hexdigest() != EDGE_SPECULATION_SHA256
):
    raise RuntimeError("pinned provider speculation body disagrees with its digest")

EDGE_BRIDGE_MARKER = b".webmcp/bridge.js"
MANIFEST_LIMIT = 64 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
TOTAL_RESPONSE_BYTES = 16 * 1024 * 1024
FILE_COUNT_LIMIT = 256


class WitnessError(RuntimeError):
    """The browser observation departed from the fixed candidate contract."""


@dataclass(frozen=True)
class FileBinding:
    path: str
    body: bytes
    sha256: str
    size: int
    media_type: str


@dataclass(frozen=True)
class CandidateContract:
    source_revision: str
    manifest_sha256: str
    index: FileBinding
    assets: Mapping[str, FileBinding]


@dataclass(frozen=True)
class RequestObservation:
    method: str
    url: str
    resource_type: str


@dataclass(frozen=True)
class ResponseObservation:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes


@dataclass(frozen=True)
class Exchange:
    request: RequestObservation
    response: ResponseObservation


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WitnessError(f"JSON contains duplicate field {key!r}")
        result[key] = value
    return result


def _strict_json(body: bytes, label: str) -> Any:
    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
    except WitnessError:
        raise
    except (UnicodeDecodeError, RecursionError, ValueError) as error:
        raise WitnessError(f"{label} is not valid UTF-8 JSON") from error


def read_expected_contract(path: Path) -> tuple[str, str]:
    """Read the two immutable candidate pins without importing application code."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeError) as error:
        raise WitnessError("expected contract file could not be parsed") from error
    wanted = {
        "_PLATFORM_CANDIDATE_SOURCE_REVISION": None,
        "_PLATFORM_CANDIDATE_MANIFEST_SHA256": None,
    }
    seen: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id in wanted:
                if target.id in seen:
                    raise WitnessError("expected contract file repeats a preview constant")
                seen.add(target.id)
                try:
                    wanted[target.id] = ast.literal_eval(node.value)
                except (TypeError, ValueError) as error:
                    raise WitnessError(
                        "expected contract file contains a dynamic preview constant"
                    ) from error
    revision = wanted["_PLATFORM_CANDIDATE_SOURCE_REVISION"]
    digest = wanted["_PLATFORM_CANDIDATE_MANIFEST_SHA256"]
    if not isinstance(revision, str) or REVISION.fullmatch(revision) is None:
        raise WitnessError("expected source revision is invalid")
    if not isinstance(digest, str) or DIGEST.fullmatch(digest) is None:
        raise WitnessError("expected manifest digest is invalid")
    return revision, digest


def load_contract(
    bundle_root: Path,
    *,
    expected_source_revision: str,
    expected_manifest_sha256: str,
) -> CandidateContract:
    """Bind the live witness to exact source-controlled manifest and file bytes."""
    if REVISION.fullmatch(expected_source_revision) is None:
        raise WitnessError("expected source revision is invalid")
    if DIGEST.fullmatch(expected_manifest_sha256) is None:
        raise WitnessError("expected manifest digest is invalid")
    manifest_path = bundle_root / "source.json"
    try:
        if manifest_path.stat().st_size > MANIFEST_LIMIT:
            raise WitnessError("candidate source.json exceeded its byte limit")
        manifest_body = manifest_path.read_bytes()
    except OSError as error:
        raise WitnessError("candidate source.json could not be read") from error
    if len(manifest_body) > MANIFEST_LIMIT:
        raise WitnessError("candidate source.json exceeded its byte limit")
    if _sha256(manifest_body) != expected_manifest_sha256:
        raise WitnessError("candidate source.json differs from the pinned manifest digest")
    manifest = _strict_json(manifest_body, "candidate source.json")
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        raise WitnessError("candidate source.json fields do not match the schema")
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("state") != STATE
        or manifest.get("source_repository") != SOURCE_REPOSITORY
        or manifest.get("source_revision") != expected_source_revision
        or manifest.get("base_path") != BASE_PATH
        or manifest.get("production_ready") is not False
        or manifest.get("runtime_api_binding") != "UNAVAILABLE"
        or type(manifest.get("effectors")) is not int
        or manifest.get("effectors") != 0
        or manifest.get("unknown_route_policy") != "not_found"
        or manifest.get("reviewed_routes") != list(REVIEWED_ROUTES)
    ):
        raise WitnessError("candidate source.json contract is invalid")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not 2 <= len(rows) <= FILE_COUNT_LIMIT:
        raise WitnessError("candidate source.json has no closed file inventory")

    records: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    total_size = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size"}:
            raise WitnessError("candidate source.json has an invalid file record")
        relative = row.get("path")
        digest = row.get("sha256")
        size = row.get("size")
        if (
            not isinstance(relative, str)
            or (relative != "index.html" and ASSET_PATH.fullmatch(relative) is None)
            or relative in seen
            or not isinstance(digest, str)
            or DIGEST.fullmatch(digest) is None
            or type(size) is not int
            or not 0 <= size <= MAX_RESPONSE_BYTES
        ):
            raise WitnessError("candidate source.json has an invalid file record")
        seen.add(relative)
        total_size += size
        if total_size > TOTAL_RESPONSE_BYTES:
            raise WitnessError("candidate file inventory exceeds the aggregate byte limit")
        records.append((relative, digest, size))

    bindings: dict[str, FileBinding] = {}
    resolved_root = bundle_root.resolve()
    for relative, digest, size in records:
        file_path = (bundle_root / relative).resolve()
        try:
            file_path.relative_to(resolved_root)
            with file_path.open("rb") as source:
                body = source.read(size + 1)
        except (OSError, ValueError) as error:
            raise WitnessError("candidate file inventory escapes or is unreadable") from error
        if len(body) != size or _sha256(body) != digest:
            raise WitnessError(f"candidate file {relative!r} differs from source.json")
        if EDGE_BRIDGE_MARKER in body.lower():
            raise WitnessError(f"candidate file {relative!r} references the edge bridge")
        suffix = Path(relative).suffix.lower()
        media_type = "text/html" if relative == "index.html" else MEDIA_TYPES.get(suffix)
        if media_type is None:
            raise WitnessError("candidate file has an unsupported media type")
        bindings[relative] = FileBinding(relative, body, digest, size, media_type)
    try:
        index = bindings.pop("index.html")
    except KeyError as error:
        raise WitnessError("candidate source.json does not declare index.html") from error
    return CandidateContract(
        source_revision=expected_source_revision,
        manifest_sha256=expected_manifest_sha256,
        index=index,
        assets=dict(sorted(bindings.items())),
    )


def _header_values(
    headers: Sequence[tuple[str, str]], name: str
) -> tuple[str, ...]:
    lowered = name.lower()
    return tuple(value.strip() for key, value in headers if key.lower() == lowered)


def _one_header(headers: Sequence[tuple[str, str]], name: str) -> str:
    values = _header_values(headers, name)
    if len(values) != 1:
        raise WitnessError(f"response must contain exactly one {name} header")
    return values[0]


def _require_candidate_headers(
    origin: str,
    binding: FileBinding,
    response: ResponseObservation,
    contract: CandidateContract,
) -> None:
    for name, expected in STATIC_HEADERS.items():
        if _one_header(response.headers, name) != expected:
            raise WitnessError(f"candidate response has an invalid {name} header")
    if _one_header(response.headers, "content-security-policy") != CANONICAL_CSP:
        raise WitnessError("candidate response has an invalid content-security-policy header")
    if _one_header(response.headers, "content-type") != CANDIDATE_CONTENT_TYPES[
        binding.media_type
    ]:
        raise WitnessError("candidate response has an invalid content-type header")
    if _one_header(response.headers, "content-length") != str(binding.size):
        raise WitnessError("candidate response has an invalid content-length header")
    if _one_header(response.headers, "x-szl-platform-source-revision") != contract.source_revision:
        raise WitnessError("candidate response source provenance is invalid")
    if _one_header(response.headers, "x-szl-candidate-manifest-sha256") != contract.manifest_sha256:
        raise WitnessError("candidate response manifest provenance is invalid")
    encodings = _header_values(response.headers, "content-encoding")
    if encodings not in ((), ("identity",)):
        raise WitnessError("candidate response bytes were content-encoded")
    speculation = _header_values(response.headers, "speculation-rules")
    expected_speculation = (
        (EDGE_SPECULATION_HEADER,) if origin == PRODUCT_ORIGIN else ()
    )
    if speculation != expected_speculation:
        raise WitnessError("candidate response has an invalid speculation-rules header")


def _require_candidate_response(
    origin: str,
    binding: FileBinding,
    response: ResponseObservation,
    contract: CandidateContract,
) -> None:
    if response.status != 200:
        raise WitnessError("candidate response status is not 200")
    if len(response.body) > MAX_RESPONSE_BYTES:
        raise WitnessError("candidate response exceeded its byte limit")
    if response.body != binding.body or _sha256(response.body) != binding.sha256:
        raise WitnessError("candidate response bytes differ from the manifest binding")
    _require_candidate_headers(origin, binding, response, contract)


def _require_edge_response(response: ResponseObservation) -> None:
    if response.status != 200:
        raise WitnessError("provider speculation response status is not 200")
    if _one_header(response.headers, "content-type") != EDGE_SPECULATION_MEDIA_TYPE:
        raise WitnessError("provider speculation response content type is invalid")
    if _one_header(response.headers, "content-length") != str(EDGE_SPECULATION_SIZE):
        raise WitnessError("provider speculation response content length is invalid")
    if _one_header(response.headers, "speculation-rules") != EDGE_SPECULATION_HEADER:
        raise WitnessError("provider speculation response header is invalid")
    if _header_values(response.headers, "content-encoding") not in ((), ("identity",)):
        raise WitnessError("provider speculation response bytes were content-encoded")
    if (
        len(response.body) != EDGE_SPECULATION_SIZE
        or _sha256(response.body) != EDGE_SPECULATION_SHA256
        or response.body != EDGE_SPECULATION_BODY
    ):
        raise WitnessError("provider speculation response bytes are invalid")
    if _strict_json(response.body, "provider speculation response") != EDGE_SPECULATION_SCHEMA:
        raise WitnessError("provider speculation response schema is invalid")


def _require_declared_response_size(
    kind: str,
    binding: FileBinding | None,
    response: Any,
    headers: Sequence[tuple[str, str]],
) -> None:
    """Check the already-buffered response before copying its body into Python.

    Playwright route.fetch buffers internally; this is a contract validation,
    not a transport-level memory cap. Fixed URLs and the fetch timeout bound the
    witness scope, and exact file lengths and digests gate browser execution.
    """
    if response.status != 200:
        raise WitnessError("browser response status is not 200")
    expected = EDGE_SPECULATION_SIZE if kind == "provider_edge_speculation" else None
    if expected is None:
        if binding is None:
            raise WitnessError("candidate response has no file binding")
        expected = binding.size
    if _one_header(headers, "content-length") != str(expected):
        raise WitnessError("browser response has an invalid pre-body content length")


def _route_url(origin: str, route: str) -> str:
    return origin + (BASE_PATH if route == "/" else PREFIX + route)


def classify_request(
    contract: CandidateContract,
    *,
    origin: str,
    route: str,
    request: RequestObservation,
) -> tuple[str, FileBinding | None]:
    """Classify one exact browser GET; all URL variants fail closed."""
    if origin not in ALLOWED_ORIGINS or route not in REVIEWED_ROUTES:
        raise WitnessError("origin or reviewed route is outside the fixed witness scope")
    if request.method != "GET":
        raise WitnessError("browser attempted a non-GET request")
    if request.url == _route_url(origin, route):
        if request.resource_type != "document":
            raise WitnessError("candidate document request has an invalid resource type")
        return "candidate_document", contract.index
    for relative, binding in contract.assets.items():
        if request.url == origin + PREFIX + "/" + relative:
            expected_type = "stylesheet" if binding.media_type == "text/css" else "script"
            if request.resource_type != expected_type:
                raise WitnessError("candidate asset request has an invalid resource type")
            return "candidate_asset", binding
    if request.url == EDGE_SPECULATION_URL and origin == PRODUCT_ORIGIN:
        if request.resource_type != "other":
            raise WitnessError("provider speculation request has an invalid resource type")
        return "provider_edge_speculation", None
    raise WitnessError("browser attempted an undeclared request")


def validate_exchange(
    contract: CandidateContract,
    *,
    origin: str,
    route: str,
    exchange: Exchange,
) -> tuple[str, str | None]:
    kind, binding = classify_request(
        contract, origin=origin, route=route, request=exchange.request
    )
    if kind == "provider_edge_speculation":
        _require_edge_response(exchange.response)
        return kind, None
    assert binding is not None
    _require_candidate_response(origin, binding, exchange.response, contract)
    return kind, binding.path


def validate_route_trace(
    contract: CandidateContract,
    *,
    origin: str,
    route: str,
    exchanges: Sequence[Exchange],
) -> dict[str, Any]:
    """Validate a complete per-navigation trace and return secret-free evidence."""
    counts = {
        "candidate_document": 0,
        "candidate_asset": 0,
        "provider_edge_speculation": 0,
    }
    urls: set[str] = set()
    assets: list[str] = []
    for exchange in exchanges:
        if exchange.request.url in urls:
            raise WitnessError("browser repeated a request during one navigation")
        urls.add(exchange.request.url)
        kind, asset = validate_exchange(
            contract, origin=origin, route=route, exchange=exchange
        )
        counts[kind] += 1
        if asset is not None and asset != "index.html":
            assets.append(asset)
    if counts["candidate_document"] != 1:
        raise WitnessError("navigation did not fetch exactly one candidate document")
    expected_edge_count = 1 if origin == PRODUCT_ORIGIN else 0
    if counts["provider_edge_speculation"] != expected_edge_count:
        raise WitnessError("navigation has an invalid provider speculation request count")
    return {
        "route": route,
        "document_sha256": contract.index.sha256,
        "candidate_assets": sorted(assets),
        "provider_edge_requests": counts["provider_edge_speculation"],
        "provider_edge_ownership": (
            "PROVIDER_OWNED" if expected_edge_count else "NOT_PRESENT"
        ),
        "request_count": len(exchanges),
    }


def validate_origin_traces(
    contract: CandidateContract,
    *,
    origin: str,
    traces: Mapping[str, Sequence[Exchange]],
) -> dict[str, Any]:
    if set(traces) != set(REVIEWED_ROUTES):
        raise WitnessError("origin trace does not contain both reviewed routes")
    route_reports = []
    observed_assets: set[str] = set()
    for route in REVIEWED_ROUTES:
        route_report = validate_route_trace(
            contract, origin=origin, route=route, exchanges=traces[route]
        )
        route_reports.append(route_report)
        observed_assets.update(route_report["candidate_assets"])
    if observed_assets != set(contract.assets):
        raise WitnessError("reviewed routes did not exercise the complete manifest asset set")
    return {
        "origin": origin,
        "routes": route_reports,
        "verified_assets": sorted(observed_assets),
        "provider_edge_csp": "NOT_PRESENT",
        "provider_edge_speculation": (
            "cloudflare-speed-brain-exact" if origin == PRODUCT_ORIGIN else "NOT_PRESENT"
        ),
    }


def _playwright_headers(response: Any) -> tuple[tuple[str, str], ...]:
    return tuple(
        (str(item["name"]), str(item["value"]))
        for item in response.headers_array
    )


def _browser_trace(
    browser: Any,
    contract: CandidateContract,
    *,
    origin: str,
    route_path: str,
    timeout_ms: int,
) -> tuple[list[Exchange], dict[str, Any]]:
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        color_scheme="dark",
        reduced_motion="reduce",
        locale="en-US",
        service_workers="block",
    )
    exchanges: list[Exchange] = []
    violations: list[str] = []
    page_errors: list[str] = []
    console_problems: list[str] = []
    seen_urls: set[str] = set()

    def guard(route: Any) -> None:
        request = route.request
        observation = RequestObservation(
            method=request.method,
            url=request.url,
            resource_type=request.resource_type,
        )
        try:
            kind, binding = classify_request(
                contract, origin=origin, route=route_path, request=observation
            )
            if observation.url in seen_urls:
                raise WitnessError("browser repeated a request during one navigation")
            seen_urls.add(observation.url)
            response = route.fetch(max_redirects=0, timeout=timeout_ms)
            headers = _playwright_headers(response)
            _require_declared_response_size(kind, binding, response, headers)
            body = response.body()
            exchange = Exchange(
                request=observation,
                response=ResponseObservation(
                    status=response.status,
                    headers=headers,
                    body=body,
                ),
            )
            validate_exchange(
                contract, origin=origin, route=route_path, exchange=exchange
            )
            exchanges.append(exchange)
            route.fulfill(response=response, body=body)
        except Exception as error:  # The final trace reports only stable error classes.
            violations.append(type(error).__name__)
            try:
                route.abort("blockedbyclient")
            except Exception:
                pass

    try:
        context.route("**/*", guard)
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(type(error).__name__))
        page.on(
            "console",
            lambda message: console_problems.append("console-problem")
            if message.type in {"warning", "error"}
            else None,
        )
        response = page.goto(
            _route_url(origin, route_path),
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )
        if response is None or response.status != 200:
            raise WitnessError("candidate browser navigation failed")
        page.locator("[data-testid='candidate-boundary']").wait_for(
            state="visible", timeout=timeout_ms
        )
        page.locator("body[data-screenshot-ready='true']").wait_for(
            state="attached", timeout=timeout_ms
        )
        page.wait_for_timeout(500)
        heading = page.locator("h1").first.text_content(timeout=timeout_ms)
        if heading is None or " ".join(heading.split()) != REVIEWED_ROUTES[route_path]:
            raise WitnessError("candidate route heading is invalid")
        script_sources = page.locator("script[src]").evaluate_all(
            "nodes => nodes.map(node => node.src)"
        )
        if any(
            not isinstance(source, str)
            or not source.startswith(origin + PREFIX + "/assets/")
            or source == PRODUCT_EDGE_SCRIPT_SOURCE
            for source in script_sources
        ):
            raise WitnessError("candidate DOM contains an undeclared script source")
        if violations:
            raise WitnessError("browser attempted a blocked request")
        if page_errors or console_problems:
            raise WitnessError("candidate emitted a browser problem")
        route_report = validate_route_trace(
            contract, origin=origin, route=route_path, exchanges=exchanges
        )
        route_report["heading"] = REVIEWED_ROUTES[route_path]
        route_report["browser_errors"] = 0
        return exchanges, route_report
    finally:
        context.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origin",
        action="append",
        choices=ALLOWED_ORIGINS,
        help="Fixed origin to witness; repeat for both (default: both)",
    )
    parser.add_argument("--bundle-root", type=Path, default=BUNDLE_ROOT)
    parser.add_argument("--expected-contract-file", type=Path, default=ROOT / "serve.py")
    parser.add_argument(
        "--output", type=Path, default=Path("platform-candidate-browser-witness.json")
    )
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    origins = tuple(arguments.origin or ALLOWED_ORIGINS)
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "status": "FAIL",
        "candidate_state": STATE,
        "production_ready": False,
        "runtime_api_binding": "UNAVAILABLE",
        "effectors": 0,
        "origins": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        if len(origins) != len(ALLOWED_ORIGINS) or set(origins) != set(ALLOWED_ORIGINS):
            raise WitnessError("origin list must contain exactly both fixed origins")
        if not 1_000 <= arguments.timeout_ms <= 120_000:
            raise WitnessError("timeout must be between 1000 and 120000 milliseconds")
        expected_revision, expected_manifest = read_expected_contract(
            arguments.expected_contract_file
        )
        contract = load_contract(
            arguments.bundle_root,
            expected_source_revision=expected_revision,
            expected_manifest_sha256=expected_manifest,
        )
        report["source_revision"] = contract.source_revision
        report["manifest_sha256"] = contract.manifest_sha256

        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            launch: dict[str, Any] = {"headless": True}
            executable_path = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH", "").strip()
            if executable_path:
                launch["executable_path"] = executable_path
            proxy_server = (
                os.environ.get("HTTPS_PROXY", "").strip()
                or os.environ.get("https_proxy", "").strip()
            )
            if proxy_server:
                launch["proxy"] = {"server": proxy_server}
            browser = playwright.chromium.launch(**launch)
            try:
                report["browser"] = {"engine": "chromium", "version": browser.version}
                for origin in origins:
                    traces: dict[str, Sequence[Exchange]] = {}
                    live_route_reports: list[dict[str, Any]] = []
                    for route_path in REVIEWED_ROUTES:
                        trace, route_report = _browser_trace(
                            browser,
                            contract,
                            origin=origin,
                            route_path=route_path,
                            timeout_ms=arguments.timeout_ms,
                        )
                        traces[route_path] = trace
                        live_route_reports.append(route_report)
                    origin_report = validate_origin_traces(
                        contract, origin=origin, traces=traces
                    )
                    origin_report["routes"] = live_route_reports
                    report["origins"].append(origin_report)
            finally:
                browser.close()
        report["status"] = "PASS"
    except Exception as error:
        report["error_class"] = type(error).__name__
        report["error_code"] = (
            str(error)
            if isinstance(error, WitnessError) and len(str(error)) <= 160
            else "BROWSER_WITNESS_FAILED"
        )
    finally:
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run())
