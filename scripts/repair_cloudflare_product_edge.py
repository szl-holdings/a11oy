#!/usr/bin/env python3
"""Deploy the fail-closed Cloudflare adapter for the A11oy product root.

The controller never logs or persists the API token. It resolves the exact
active zone, deploys one named module worker, adds only the exact apex-root
route plus the www redirect route, and proves the public root response carries
the managed edge marker. Existing conflicting exact routes are never replaced.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API = "https://api.cloudflare.com/client/v4"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKER = ROOT / "cloudflare" / "a11oy-product-root-worker.mjs"
SCRIPT_NAME = "szl-a11oy-product-root-v1"
ZONE_NAME = "a-11-oy.com"
ROUTES = ("a-11-oy.com/", "www.a-11-oy.com/*")
EDGE_MARKER = "a11oy-product-root-v1"


class EdgeError(RuntimeError):
    pass


def token() -> str:
    return (
        os.environ.get("CLOUDFLARE_API_TOKEN")
        or os.environ.get("CF_API_TOKEN")
        or os.environ.get("CLOUDFLARE_TOKEN")
        or ""
    ).strip()


def request_json(method: str, path: str, *, bearer: str, payload: Any | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    body = None
    req_headers = {"Authorization": f"Bearer {bearer}", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=body, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")[:4000]
        raise EdgeError(f"Cloudflare HTTP {exc.code}: {text}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise EdgeError(f"Cloudflare request failed: {exc}") from exc
    if value.get("success") is not True:
        raise EdgeError("Cloudflare rejected request: " + json.dumps(value.get("errors") or value, sort_keys=True)[:4000])
    return value


def multipart_module(source: bytes) -> tuple[bytes, str]:
    boundary = "----szl" + secrets.token_hex(16)
    metadata = json.dumps({"main_module": "worker.mjs", "compatibility_date": "2026-09-01"}, separators=(",", ":")).encode()
    chunks = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"metadata\"\r\nContent-Type: application/json\r\n\r\n".encode(),
        metadata,
        b"\r\n",
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"worker.mjs\"; filename=\"worker.mjs\"\r\nContent-Type: application/javascript+module\r\n\r\n".encode(),
        source,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(chunks), boundary


def upload_worker(account_id: str, bearer: str, worker: Path) -> dict[str, Any]:
    source = worker.read_bytes()
    body, boundary = multipart_module(source)
    req = urllib.request.Request(
        f"{API}/accounts/{account_id}/workers/scripts/{SCRIPT_NAME}",
        data=body,
        method="PUT",
        headers={
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")[:4000]
        raise EdgeError(f"Worker upload HTTP {exc.code}: {text}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise EdgeError(f"Worker upload failed: {exc}") from exc
    if value.get("success") is not True:
        raise EdgeError("Worker upload rejected: " + json.dumps(value.get("errors") or value, sort_keys=True)[:4000])
    return value


def upsert_routes(zone_id: str, bearer: str, *, dry_run: bool) -> list[dict[str, Any]]:
    current = request_json("GET", f"/zones/{zone_id}/workers/routes", bearer=bearer).get("result") or []
    by_pattern = {str(row.get("pattern")): row for row in current}
    results = []
    for pattern in ROUTES:
        existing = by_pattern.get(pattern)
        existing_script = (existing or {}).get("script")
        if existing and existing_script not in {None, SCRIPT_NAME}:
            raise EdgeError(f"ROUTE_CONFLICT: {pattern} is owned by {existing_script!r}")
        if dry_run:
            results.append({"pattern": pattern, "action": "would-update" if existing else "would-create", "script": SCRIPT_NAME})
            continue
        payload = {"pattern": pattern, "script": SCRIPT_NAME}
        if existing:
            route_id = existing.get("id")
            value = request_json("PUT", f"/zones/{zone_id}/workers/routes/{route_id}", bearer=bearer, payload=payload)
            action = "updated"
        else:
            value = request_json("POST", f"/zones/{zone_id}/workers/routes", bearer=bearer, payload=payload)
            action = "created"
        row = value.get("result") or {}
        results.append({"pattern": pattern, "action": action, "route_id": row.get("id"), "script": row.get("script") or SCRIPT_NAME})
    return results


def public_probe(attempts: int = 18) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for attempt in range(1, attempts + 1):
        url = f"https://{ZONE_NAME}/"
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "SZL-edge-proof/1.0", "Cache-Control": "no-cache"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read(65536).decode("utf-8", "replace")
                last = {
                    "attempt": attempt,
                    "status": response.status,
                    "edge": response.headers.get("x-szl-edge"),
                    "server": response.headers.get("server"),
                    "body_has_a11oy": "a11oy" in body.lower(),
                }
                if response.status == 200 and last["edge"] == EDGE_MARKER and last["body_has_a11oy"]:
                    return last
        except urllib.error.HTTPError as exc:
            last = {"attempt": attempt, "status": exc.code, "edge": exc.headers.get("x-szl-edge"), "error": "HTTP"}
        except (urllib.error.URLError, TimeoutError) as exc:
            last = {"attempt": attempt, "status": None, "edge": None, "error": str(exc)}
        time.sleep(min(5, attempt))
    raise EdgeError("PUBLIC_PROBE_FAILED: " + json.dumps(last, sort_keys=True))


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, default=DEFAULT_WORKER)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report: dict[str, Any] = {
        "schema": "szl.cloudflare-product-edge/v1",
        "zone": ZONE_NAME,
        "script": SCRIPT_NAME,
        "routes": list(ROUTES),
        "dry_run": args.dry_run,
        "status": "BLOCKED",
        "token_recorded": False,
    }
    bearer = token()
    if not bearer:
        report["status"] = "UNAVAILABLE"
        report["error"] = "No supported Cloudflare API token secret is configured."
        write_report(args.report, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    try:
        zones = request_json("GET", "/zones?" + urllib.parse.urlencode({"name": ZONE_NAME, "status": "active", "per_page": 50}), bearer=bearer).get("result") or []
        if len(zones) != 1:
            raise EdgeError(f"Expected exactly one active {ZONE_NAME} zone, found {len(zones)}")
        zone = zones[0]
        zone_id = str(zone["id"])
        account_id = str((zone.get("account") or {}).get("id") or "")
        if not account_id:
            raise EdgeError("The active zone did not expose an account id")
        report["zone_id_suffix"] = zone_id[-6:]
        report["account_id_suffix"] = account_id[-6:]
        if not args.dry_run:
            upload_worker(account_id, bearer, args.worker)
        report["route_results"] = upsert_routes(zone_id, bearer, dry_run=args.dry_run)
        report["probe"] = {"status": "SKIPPED_DRY_RUN"} if args.dry_run else public_probe()
        report["status"] = "VALIDATED" if args.dry_run else "LIVE"
    except EdgeError as exc:
        report["error"] = str(exc)
        write_report(args.report, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1

    write_report(args.report, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
