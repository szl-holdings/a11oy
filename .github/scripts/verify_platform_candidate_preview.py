#!/usr/bin/env python3
"""Fail closed when the deployed Platform preview differs from its static contract.

This probe is read-only and stdlib-only.  It follows no successful redirect, accepts
only a credential-free HTTPS origin, and binds the live HTML and every live asset to
the manifest bytes served by the same candidate route.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


PREFIX = "/preview/platform-a11oy"
BASE_PATH = PREFIX + "/"
SCHEMA = "szl.platform-static-candidate/v1"
REPORT_SCHEMA = "szl.platform-static-candidate-live-verification/v1"
STATE = "CANDIDATE_DEMO"
SOURCE_REPOSITORY = "https://github.com/szl-holdings/platform"
REVIEWED_ROUTES = ["/", "/security-agents"]
INDEX_PATHS = [PREFIX, BASE_PATH, PREFIX + "/index.html"]
UNKNOWN_ROUTE_POLICY = "not_found"
UNKNOWN_PROBE = "/__live-verification-unknown__"
# Hugging Face Envoy terminates OPTIONS before the Space application on every
# path, including nonexistent ones.  POST reaches the application and therefore
# remains the externally verifiable candidate-owned method rejection.
REJECTED_METHODS = ("POST",)

MANIFEST_LIMIT = 64 * 1024
FILE_LIMIT = 2 * 1024 * 1024
TOTAL_LIMIT = 16 * 1024 * 1024
FILE_COUNT_LIMIT = 256
ERROR_BODY_LIMIT = 64 * 1024

REVISION = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
ASSET_PATH = re.compile(
    r"assets/[A-Za-z0-9_.-]+-[A-Za-z0-9_-]{8,}\.(?:css|js)\Z"
)

CSP = (
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
PRODUCT_ORIGIN = "https://a-11-oy.com"
CLOUDFLARE_WEBMCP_BRIDGE = PRODUCT_ORIGIN + "/.webmcp/bridge.js"
_CSP_SCRIPT_END = (
    "https://szlholdings-a11oy.hf.space/preview/platform-a11oy/; script-src-attr"
)
# The apex zone's WebMCP setting appends this one script source to HTML CSP.
# Keep the Space origin, JSON, assets, and every other directive byte-exact.
# https://developers.cloudflare.com/api/resources/zones/subresources/settings/
PRODUCT_HTML_CSP = CSP.replace(
    _CSP_SCRIPT_END,
    _CSP_SCRIPT_END.replace("; script-src-attr", f" {CLOUDFLARE_WEBMCP_BRIDGE}; script-src-attr"),
    1,
)
PRODUCT_HTML_URLS = frozenset(
    PRODUCT_ORIGIN + path
    for path in (*INDEX_PATHS, *(PREFIX + route for route in REVIEWED_ROUTES if route != "/"))
)
STATIC_HEADERS = {
    "cache-control": "no-store, no-transform",
    "content-security-policy": CSP,
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-robots-tag": "noindex, nofollow, noarchive",
    "x-szl-candidate-state": STATE,
}
WIDGET_MARKERS = (
    b"a11oy-operator-widget.js",
    b'data-surface="a11oy"',
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
MEDIA_TYPES = {
    ".css": "text/css",
    ".js": "text/javascript",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


class VerificationError(RuntimeError):
    """The live preview does not satisfy the reviewed publication contract."""


class _NoRedirect(HTTPRedirectHandler):
    """Return redirects to the verifier without issuing the target request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


NO_REDIRECT_OPENER = build_opener(_NoRedirect())


@dataclass(frozen=True)
class Observation:
    method: str
    url: str
    status: int
    headers: Mapping[str, tuple[str, ...]]
    body: bytes

    def header(self, name: str) -> str:
        values = self.headers.get(name.lower(), ())
        if len(values) != 1:
            raise VerificationError(
                f"{self.method} {self.url} must return exactly one {name} header"
            )
        return values[0]


@dataclass(frozen=True)
class FileRecord:
    path: str
    sha256: str
    size: int


def read_expected_contract(path: str | Path) -> tuple[str, str]:
    """Read the two pinned preview constants without executing application code."""
    try:
        source = Path(path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as error:
        raise VerificationError("expected contract file could not be parsed") from error
    wanted = {
        "_PLATFORM_CANDIDATE_SOURCE_REVISION": None,
        "_PLATFORM_CANDIDATE_MANIFEST_SHA256": None,
    }
    seen: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for target in targets:
            if isinstance(target, ast.Name) and target.id in wanted:
                if target.id in seen:
                    raise VerificationError("expected contract file repeats a preview constant")
                seen.add(target.id)
                try:
                    wanted[target.id] = ast.literal_eval(value)
                except (TypeError, ValueError) as error:
                    raise VerificationError(
                        "expected contract file contains a dynamic preview constant"
                    ) from error
    revision = wanted["_PLATFORM_CANDIDATE_SOURCE_REVISION"]
    digest = wanted["_PLATFORM_CANDIDATE_MANIFEST_SHA256"]
    if (
        not isinstance(revision, str)
        or REVISION.fullmatch(revision) is None
        or revision == "0" * 40
    ):
        raise VerificationError("expected contract file has an invalid source revision")
    if (
        not isinstance(digest, str)
        or DIGEST.fullmatch(digest) is None
        or digest == "0" * 64
    ):
        raise VerificationError("expected contract file has an invalid manifest digest")
    return revision, digest


def normalize_base_url(value: str) -> str:
    candidate = str(value or "").strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as error:
        raise VerificationError("base URL is malformed") from error
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or ":" in parsed.hostname
    ):
        raise VerificationError("base URL must be a credential-free HTTPS origin")
    authority = parsed.hostname.lower()
    if port is not None:
        authority += f":{port}"
    return f"https://{authority}"


def _read_limited(response: Any, limit: int, label: str) -> bytes:
    try:
        payload = response.read(limit + 1)
    except Exception as error:
        raise VerificationError(f"could not read {label}: {error}") from error
    if len(payload) > limit:
        raise VerificationError(f"{label} exceeded its byte limit")
    return payload


def _request(
    base_url: str,
    path: str,
    method: str,
    *,
    limit: int,
    timeout: float,
    opener: Callable[..., Any],
) -> Observation:
    url = base_url + path
    request = Request(
        url,
        method=method,
        headers={
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.1",
            "Accept-Encoding": "identity",
            "User-Agent": "szl-platform-candidate-verifier/1",
        },
    )
    response: Any | None = None
    try:
        try:
            response = opener(request, timeout=timeout)
        except HTTPError as error:
            response = error
        except (OSError, URLError) as error:
            raise VerificationError(f"{method} {path} failed: {error}") from error

        final_url = str(response.geturl())
        if final_url != url:
            raise VerificationError(f"{method} {path} redirected to {final_url}")
        status = int(getattr(response, "status", response.getcode()))
        headers: dict[str, list[str]] = {}
        for raw_name, raw_value in response.headers.items():
            headers.setdefault(raw_name.lower(), []).append(str(raw_value).strip())
        body = _read_limited(response, limit, f"{method} {path}")
        return Observation(
            method=method,
            url=url,
            status=status,
            headers={name: tuple(values) for name, values in headers.items()},
            body=body,
        )
    except VerificationError:
        raise
    except Exception as error:
        raise VerificationError(f"{method} {path} could not be verified: {error}") from error
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass


def _content_length(observation: Observation) -> int:
    raw = observation.header("content-length")
    if re.fullmatch(r"0|[1-9][0-9]*", raw) is None:
        raise VerificationError(
            f"{observation.method} {observation.url} returned an invalid Content-Length"
        )
    return int(raw)


def _media_type(observation: Observation) -> str:
    return observation.header("content-type").split(";", 1)[0].strip().lower()


def _require_static_headers(observation: Observation) -> None:
    for name, expected in STATIC_HEADERS.items():
        if name == "content-security-policy" and observation.url in PRODUCT_HTML_URLS:
            expected = PRODUCT_HTML_CSP
        if observation.header(name) != expected:
            raise VerificationError(
                f"{observation.method} {observation.url} returned an invalid {name} header"
            )
    encodings = observation.headers.get("content-encoding", ())
    if encodings not in ((), ("identity",)):
        raise VerificationError(
            f"{observation.method} {observation.url} transformed the reviewed bytes"
        )


def _require_provenance(
    observation: Observation, *, source_revision: str, manifest_sha256: str
) -> None:
    if observation.header("x-szl-platform-source-revision") != source_revision:
        raise VerificationError(
            f"{observation.method} {observation.url} source header disagrees with source.json"
        )
    if observation.header("x-szl-candidate-manifest-sha256") != manifest_sha256:
        raise VerificationError(
            f"{observation.method} {observation.url} digest header disagrees with source.json"
        )


def _require_pair(
    get: Observation,
    head: Observation,
    *,
    status: int,
    media_type: str,
) -> None:
    for observation in (get, head):
        if observation.status != status:
            raise VerificationError(
                f"{observation.method} {observation.url} returned "
                f"{observation.status}, expected {status}"
            )
        _require_static_headers(observation)
        if _media_type(observation) != media_type:
            raise VerificationError(
                f"{observation.method} {observation.url} returned an invalid content type"
            )
    if head.body:
        raise VerificationError(f"HEAD {head.url} returned a response body")
    if _content_length(get) != len(get.body):
        raise VerificationError(f"GET {get.url} Content-Length does not match its body")
    if _content_length(head) != len(get.body):
        raise VerificationError(f"HEAD {head.url} does not match GET Content-Length")


def _require_method_rejection(observation: Observation) -> None:
    if observation.status != 405:
        raise VerificationError(
            f"{observation.method} {observation.url} returned "
            f"{observation.status}, expected 405"
        )
    _require_static_headers(observation)
    if _media_type(observation) != "application/json":
        raise VerificationError(
            f"{observation.method} {observation.url} returned an invalid content type"
        )
    if {item.strip() for item in observation.header("allow").split(",")} != {
        "GET",
        "HEAD",
    }:
        raise VerificationError(
            f"{observation.method} {observation.url} returned an invalid Allow header"
        )
    if _content_length(observation) != len(observation.body):
        raise VerificationError(
            f"{observation.method} {observation.url} Content-Length does not match its body"
        )
    try:
        document = json.loads(observation.body)
    except (UnicodeDecodeError, RecursionError, ValueError) as error:
        raise VerificationError(
            f"{observation.method} {observation.url} did not return JSON"
        ) from error
    if document != {"state": "METHOD_NOT_ALLOWED"}:
        raise VerificationError(
            f"{observation.method} {observation.url} returned an invalid rejection body"
        )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise VerificationError(f"source.json contains duplicate field {key!r}")
        document[key] = value
    return document


def _parse_manifest(raw: bytes) -> tuple[Mapping[str, Any], dict[str, FileRecord]]:
    try:
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except VerificationError:
        raise
    except (UnicodeDecodeError, RecursionError, ValueError) as error:
        raise VerificationError("source.json is not valid UTF-8 JSON") from error
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        raise VerificationError("source.json fields do not match the candidate schema")

    revision = manifest.get("source_revision")
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("state") != STATE
        or manifest.get("source_repository") != SOURCE_REPOSITORY
        or not isinstance(revision, str)
        or REVISION.fullmatch(revision) is None
        or revision == "0" * 40
        or manifest.get("base_path") != BASE_PATH
        or manifest.get("production_ready") is not False
        or manifest.get("runtime_api_binding") != "UNAVAILABLE"
        or type(manifest.get("effectors")) is not int
        or manifest.get("effectors") != 0
        or manifest.get("reviewed_routes") != REVIEWED_ROUTES
        or manifest.get("unknown_route_policy") != UNKNOWN_ROUTE_POLICY
    ):
        raise VerificationError("source.json candidate contract mismatch")

    rows = manifest.get("files")
    if not isinstance(rows, list) or not 2 <= len(rows) <= FILE_COUNT_LIMIT:
        raise VerificationError("source.json must declare index.html and at least one asset")
    records: dict[str, FileRecord] = {}
    total_size = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size"}:
            raise VerificationError("source.json contains an invalid file record")
        path = row.get("path")
        digest = row.get("sha256")
        size = row.get("size")
        if (
            not isinstance(path, str)
            or (path != "index.html" and ASSET_PATH.fullmatch(path) is None)
            or path in records
            or not isinstance(digest, str)
            or DIGEST.fullmatch(digest) is None
            or type(size) is not int
            or not 0 <= size <= FILE_LIMIT
        ):
            raise VerificationError("source.json contains an invalid file record")
        total_size += size
        if total_size > TOTAL_LIMIT:
            raise VerificationError("source.json file inventory exceeds the byte limit")
        records[path] = FileRecord(path=path, sha256=digest, size=size)
    if "index.html" not in records:
        raise VerificationError("source.json does not declare index.html")
    return manifest, records


def _require_record(payload: bytes, record: FileRecord, label: str) -> None:
    if len(payload) != record.size:
        raise VerificationError(f"{label} size disagrees with source.json")
    if hashlib.sha256(payload).hexdigest() != record.sha256:
        raise VerificationError(f"{label} digest disagrees with source.json")


def verify(
    base_url: str,
    *,
    timeout: float = 20.0,
    opener: Callable[..., Any] = NO_REDIRECT_OPENER.open,
    expected_source_revision: str | None = None,
    expected_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    """Verify the live candidate and return a compact, source-bound report."""
    origin = normalize_base_url(base_url)
    if not isinstance(timeout, (int, float)) or not 0 < float(timeout) <= 120:
        raise VerificationError("timeout must be greater than zero and at most 120 seconds")
    if expected_source_revision is not None and (
        not isinstance(expected_source_revision, str)
        or REVISION.fullmatch(expected_source_revision) is None
        or expected_source_revision == "0" * 40
    ):
        raise VerificationError("expected source revision must be an exact lowercase SHA-1")
    if expected_manifest_sha256 is not None and (
        not isinstance(expected_manifest_sha256, str)
        or DIGEST.fullmatch(expected_manifest_sha256) is None
        or expected_manifest_sha256 == "0" * 64
    ):
        raise VerificationError("expected manifest digest must be an exact lowercase SHA-256")

    source_path = PREFIX + "/source.json"
    source_get = _request(
        origin, source_path, "GET", limit=MANIFEST_LIMIT, timeout=timeout, opener=opener
    )
    source_head = _request(
        origin, source_path, "HEAD", limit=0, timeout=timeout, opener=opener
    )
    _require_pair(
        source_get,
        source_head,
        status=200,
        media_type="application/json",
    )
    manifest, records = _parse_manifest(source_get.body)
    source_revision = str(manifest["source_revision"])
    manifest_sha256 = hashlib.sha256(source_get.body).hexdigest()
    if expected_source_revision is not None and source_revision != expected_source_revision:
        raise VerificationError("source.json does not match the expected Platform revision")
    if expected_manifest_sha256 is not None and manifest_sha256 != expected_manifest_sha256:
        raise VerificationError("source.json does not match the expected manifest digest")

    observations = [source_get, source_head]
    for method in REJECTED_METHODS:
        rejected = _request(
            origin,
            source_path,
            method,
            limit=ERROR_BODY_LIMIT,
            timeout=timeout,
            opener=opener,
        )
        _require_method_rejection(rejected)
        observations.append(rejected)
    index_record = records["index.html"]
    reviewed_paths = [
        *INDEX_PATHS,
        *(PREFIX + route for route in REVIEWED_ROUTES if route != "/"),
    ]
    for path in reviewed_paths:
        get = _request(origin, path, "GET", limit=FILE_LIMIT, timeout=timeout, opener=opener)
        head = _request(origin, path, "HEAD", limit=0, timeout=timeout, opener=opener)
        _require_pair(get, head, status=200, media_type="text/html")
        _require_record(get.body, index_record, f"GET {path}")
        lowered = get.body.lower()
        if any(marker in lowered for marker in WIDGET_MARKERS):
            raise VerificationError(f"GET {path} contains operator-widget injection")
        observations.extend((get, head))

    verified_assets: list[str] = []
    for relative, asset in sorted(records.items()):
        if relative == "index.html":
            continue
        suffix = "." + asset.path.rsplit(".", 1)[1].lower()
        asset_path = PREFIX + "/" + asset.path
        asset_get = _request(
            origin, asset_path, "GET", limit=FILE_LIMIT, timeout=timeout, opener=opener
        )
        asset_head = _request(
            origin, asset_path, "HEAD", limit=0, timeout=timeout, opener=opener
        )
        _require_pair(asset_get, asset_head, status=200, media_type=MEDIA_TYPES[suffix])
        _require_record(asset_get.body, asset, f"GET {asset_path}")
        observations.extend((asset_get, asset_head))
        verified_assets.append(asset.path)

    unknown_path = PREFIX + UNKNOWN_PROBE
    unknown_get = _request(
        origin, unknown_path, "GET", limit=ERROR_BODY_LIMIT, timeout=timeout, opener=opener
    )
    unknown_head = _request(
        origin, unknown_path, "HEAD", limit=0, timeout=timeout, opener=opener
    )
    _require_pair(unknown_get, unknown_head, status=404, media_type="application/json")
    expected_unknown = b'{"state":"NOT_FOUND"}'
    if unknown_get.body != expected_unknown:
        raise VerificationError(
            f"GET {unknown_get.url} did not return the exact candidate-owned 404 body"
        )
    observations.extend((unknown_get, unknown_head))

    for observation in observations:
        _require_provenance(
            observation,
            source_revision=source_revision,
            manifest_sha256=manifest_sha256,
        )

    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS",
        "base_url": origin,
        "source_revision": source_revision,
        "manifest_sha256": manifest_sha256,
        "verified_assets": verified_assets,
        "verified_routes": REVIEWED_ROUTES,
        "verified_index_paths": INDEX_PATHS,
        "unknown_route_status": 404,
        "rejected_methods": list(REJECTED_METHODS),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Credential-free HTTPS origin")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--expected-source-revision")
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument(
        "--expected-contract-file",
        help="Python source containing the pinned preview revision and digest constants",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        expected_source_revision = arguments.expected_source_revision
        expected_manifest_sha256 = arguments.expected_manifest_sha256
        if arguments.expected_contract_file:
            if expected_source_revision is not None or expected_manifest_sha256 is not None:
                raise VerificationError(
                    "expected contract file cannot be combined with explicit expected values"
                )
            expected_source_revision, expected_manifest_sha256 = read_expected_contract(
                arguments.expected_contract_file
            )
        report = verify(
            arguments.base_url,
            timeout=arguments.timeout,
            expected_source_revision=expected_source_revision,
            expected_manifest_sha256=expected_manifest_sha256,
        )
    except VerificationError as error:
        print(f"platform candidate verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
