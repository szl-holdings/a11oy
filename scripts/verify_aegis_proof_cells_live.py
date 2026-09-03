#!/usr/bin/env python3
"""Verify the exact source-bound Aegis Proof Cells deployment.

Read-only verifier. It performs bounded HEAD/GET requests, follows no redirects,
writes only the requested local JSON report, and never mutates GitHub, Hugging
Face, Cloudflare, DNS, credentials, cases, or security tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

MAX_BYTES = 2_000_000
USER_AGENT = "SZL-Aegis-Proof-Cells-Verifier/1.0"

ASSETS = (
    "/static/3d/aegis-proof-cells.html",
    "/static/3d/aegis-proof-cells/app.mjs",
    "/static/3d/aegis-proof-cells/styles.css",
    "/static/3d/aegis-proof-cells/registry.json",
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def _request(origin: str, path: str, method: str) -> dict[str, Any]:
    url = urllib.parse.urljoin(origin.rstrip("/") + "/", path.lstrip("/"))
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )
    started = time.monotonic()
    try:
        with OPENER.open(request, timeout=20) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError("response exceeded verifier byte limit")
            return {
                "url": url,
                "method": method,
                "status": int(response.status),
                "headers": {key.lower(): value for key, value in response.headers.items()},
                "body": body,
                "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_BYTES + 1)
        return {
            "url": url,
            "method": method,
            "status": int(exc.code),
            "headers": {key.lower(): value for key, value in exc.headers.items()},
            "body": body[:MAX_BYTES],
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
            "error": f"HTTPError: {exc.reason}",
        }
    except Exception as exc:  # bounded transport errors are evidence
        return {
            "url": url,
            "method": method,
            "status": None,
            "headers": {},
            "body": b"",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _decode_json(result: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(result["body"].decode("utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _source_revision(payload: dict[str, Any]) -> str | None:
    candidates = (
        payload.get("git_sha"),
        payload.get("source_revision"),
        payload.get("revision"),
        payload.get("sha"),
        (payload.get("build") or {}).get("git_sha") if isinstance(payload.get("build"), dict) else None,
        (payload.get("build") or {}).get("revision") if isinstance(payload.get("build"), dict) else None,
    )
    for candidate in candidates:
        if isinstance(candidate, str) and len(candidate) == 40:
            return candidate.lower()
    return None


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def verify_once(origin: str, source_sha: str) -> dict[str, Any]:
    source_sha = source_sha.lower()
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    build_get = _request(origin, "/api/build-info", "GET")
    build_head = _request(origin, "/api/build-info", "HEAD")
    build_payload = _decode_json(build_get)
    observed_sha = _source_revision(build_payload)
    if build_get["status"] != 200:
        failures.append("build-info GET is not HTTP 200")
    if build_head["status"] != 200:
        failures.append("build-info HEAD is not HTTP 200")
    if build_head["body"]:
        failures.append("build-info HEAD returned a response body")
    if observed_sha != source_sha:
        failures.append(f"runtime source mismatch: expected {source_sha}, observed {observed_sha}")
    checks.append(
        {
            "path": "/api/build-info",
            "get_status": build_get["status"],
            "head_status": build_head["status"],
            "source_revision": observed_sha,
            "source_matches": observed_sha == source_sha,
        }
    )

    bodies: dict[str, bytes] = {}
    for path in ASSETS:
        get_result = _request(origin, path, "GET")
        head_result = _request(origin, path, "HEAD")
        bodies[path] = get_result["body"]
        if get_result["status"] != 200:
            failures.append(f"{path} GET is not HTTP 200")
        if head_result["status"] != 200:
            failures.append(f"{path} HEAD is not HTTP 200")
        if head_result["body"]:
            failures.append(f"{path} HEAD returned a response body")
        if not get_result["body"]:
            failures.append(f"{path} GET returned an empty body")
        checks.append(
            {
                "path": path,
                "get_status": get_result["status"],
                "head_status": head_result["status"],
                "bytes": len(get_result["body"]),
                "sha256": _sha256(get_result["body"]),
                "content_type": get_result["headers"].get("content-type"),
            }
        )

    html = bodies[ASSETS[0]].decode("utf-8", errors="replace")
    js = bodies[ASSETS[1]].decode("utf-8", errors="replace")
    css = bodies[ASSETS[2]].decode("utf-8", errors="replace")
    registry = _decode_json({"body": bodies[ASSETS[3]]})

    required_html = (
        'data-szl-public-experience-v3="true"',
        'data-aegis-proof-cells="v1"',
        "Aegis Proof Cells",
        "No affiliation with Bricklayer AI",
        "/static/3d/aegis-proof-cells/registry.json",
    )
    for token in required_html:
        if token not in html:
            failures.append(f"page marker missing: {token}")

    if "https://" in js or "http://" in js:
        failures.append("runtime JavaScript contains an external URL")
    for token in (
        "CROSS_TENANT_SCOPE",
        "PROHIBITED_ACTION",
        "HUMAN_APPROVAL_REQUIRED",
        "external_writes",
        "DISABLED",
        "effectors",
    ):
        if token not in js:
            failures.append(f"runtime JavaScript policy marker missing: {token}")
    for token in ("min-height: 48px", "prefers-reduced-motion", "overflow-x: hidden"):
        if token not in css:
            failures.append(f"responsive/accessibility marker missing: {token}")

    boundary = registry.get("bricklayer_boundary") if isinstance(registry, dict) else {}
    authority = registry.get("authority") if isinstance(registry, dict) else {}
    cells = registry.get("proof_cells") if isinstance(registry, dict) else None
    capsules = registry.get("procedure_capsules") if isinstance(registry, dict) else None

    if registry.get("schema") != "szl.aegis-proof-cells.registry/v1":
        failures.append("registry schema mismatch")
    if not isinstance(boundary, dict) or boundary.get("classification") != "REFERENCE_ONLY_CLEAN_ROOM":
        failures.append("Bricklayer clean-room classification missing")
    if boundary.get("source_code_copied") is not False:
        failures.append("registry does not explicitly reject Bricklayer source copying")
    if boundary.get("affiliation") != "NONE":
        failures.append("registry affiliation boundary mismatch")
    if not isinstance(cells, list) or len(cells) != 11:
        failures.append("registry must contain exactly 11 proof cells")
    if not isinstance(capsules, list) or len(capsules) < 6:
        failures.append("registry must contain at least six procedure capsules")
    if not isinstance(authority, dict) or authority.get("external_writes") != "DISABLED":
        failures.append("external writes are not explicitly disabled")
    if authority.get("effectors") != []:
        failures.append("effectors must be empty")
    if authority.get("cross_tenant_access") != "DENIED":
        failures.append("cross-tenant access must be denied")
    if authority.get("offensive_intrusion") != "DENIED":
        failures.append("offensive intrusion must be denied")

    return {
        "schema": "szl.aegis-proof-cells.live-proof/v1",
        "status": "PASS" if not failures else "FAIL",
        "ok": not failures,
        "origin": origin,
        "source_sha": source_sha,
        "observed_source_sha": observed_sha,
        "checks": checks,
        "registry": {
            "proof_cell_count": len(cells) if isinstance(cells, list) else None,
            "procedure_capsule_count": len(capsules) if isinstance(capsules, list) else None,
            "clean_room_classification": boundary.get("classification") if isinstance(boundary, dict) else None,
            "source_code_copied": boundary.get("source_code_copied") if isinstance(boundary, dict) else None,
            "effectors": len(authority.get("effectors", [])) if isinstance(authority, dict) and isinstance(authority.get("effectors"), list) else None,
        },
        "authority": {
            "external_writes": authority.get("external_writes") if isinstance(authority, dict) else None,
            "cross_tenant_access": authority.get("cross_tenant_access") if isinstance(authority, dict) else None,
            "offensive_intrusion": authority.get("offensive_intrusion") if isinstance(authority, dict) else None,
        },
        "failures": failures,
    }


def verify(origin: str, source_sha: str, attempts: int, retry_seconds: int) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for attempt in range(1, max(1, attempts) + 1):
        last = verify_once(origin, source_sha)
        last["attempt"] = attempt
        if last["ok"]:
            return last
        if attempt < attempts:
            time.sleep(max(0, retry_seconds))
    return last


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--retry-seconds", type=int, default=0)
    args = parser.parse_args()

    report = verify(
        origin=args.origin,
        source_sha=args.source_sha,
        attempts=args.attempts,
        retry_seconds=args.retry_seconds,
    )
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "ok": report["ok"], "failures": report["failures"]}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
