#!/usr/bin/env python3
"""Deploy and prove the www-only Cloudflare canonical redirect.

The canonical product front door is served independently at ``a-11-oy.com``.
This controller has no authority to proxy or replace that apex. It may only:

1. remove the exact legacy apex-root Worker route when that route is owned by
   the known retired SZL worker;
2. deploy the inert www-only redirect Worker;
3. bind ``www.a-11-oy.com/*`` to that Worker; and
4. prove a literal 301 with exact path/query preservation while the apex still
   returns HTTP 200 without the retired edge marker.

Unknown route ownership, an apex wildcard, absent credentials, provider errors,
or failed public readback all fail closed. Token values are never persisted.
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
SCRIPT_NAME = "szl-a11oy-www-redirect-v2"
RETIRED_SCRIPT_NAME = "szl-a11oy-product-root-v1"
KNOWN_SCRIPT_NAMES = frozenset({SCRIPT_NAME, RETIRED_SCRIPT_NAME})
ZONE_NAME = "a-11-oy.com"
WWW_ROUTE = "www.a-11-oy.com/*"
LEGACY_APEX_ROUTE = "a-11-oy.com/"
FORBIDDEN_APEX_WILDCARD = "a-11-oy.com/*"
EDGE_MARKER = "a11oy-www-redirect-v2"
RETIRED_EDGE_MARKER = "a11oy-product-root-v1"
PROBE_PATH = "/__szl_www_redirect_probe__"
PROBE_QUERY = "contract=v2"


class EdgeError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Expose the redirect response instead of following it."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):  # type: ignore[no-untyped-def]
        return None


def token() -> str:
    return (
        os.environ.get("CLOUDFLARE_API_TOKEN")
        or os.environ.get("CF_API_TOKEN")
        or os.environ.get("CLOUDFLARE_TOKEN")
        or ""
    ).strip()


def request_json(
    method: str,
    path: str,
    *,
    bearer: str,
    payload: Any | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body = None
    request_headers = {
        "Authorization": f"Bearer {bearer}",
        "Accept": "application/json",
    }
    if headers:
        request_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        API + path,
        data=body,
        method=method,
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")[:4000]
        raise EdgeError(f"Cloudflare HTTP {exc.code}: {text}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise EdgeError(f"Cloudflare request failed: {exc}") from exc
    if value.get("success") is not True:
        raise EdgeError(
            "Cloudflare rejected request: "
            + json.dumps(value.get("errors") or value, sort_keys=True)[:4000]
        )
    return value


def multipart_module(source: bytes) -> tuple[bytes, str]:
    boundary = "----szl" + secrets.token_hex(16)
    metadata = json.dumps(
        {"main_module": "worker.mjs", "compatibility_date": "2026-09-01"},
        separators=(",", ":"),
    ).encode()
    chunks = [
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="metadata"\r\n'
            "Content-Type: application/json\r\n\r\n"
        ).encode(),
        metadata,
        b"\r\n",
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="worker.mjs"; filename="worker.mjs"\r\n'
            "Content-Type: application/javascript+module\r\n\r\n"
        ).encode(),
        source,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(chunks), boundary


def upload_worker(account_id: str, bearer: str, worker: Path) -> dict[str, Any]:
    body, boundary = multipart_module(worker.read_bytes())
    request = urllib.request.Request(
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
        with urllib.request.urlopen(request, timeout=60) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")[:4000]
        raise EdgeError(f"Worker upload HTTP {exc.code}: {text}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise EdgeError(f"Worker upload failed: {exc}") from exc
    if value.get("success") is not True:
        raise EdgeError(
            "Worker upload rejected: "
            + json.dumps(value.get("errors") or value, sort_keys=True)[:4000]
        )
    return value


def route_plan(current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return an exact bounded plan or reject ambiguous route ownership."""
    by_pattern = {str(row.get("pattern")): row for row in current}
    wildcard = by_pattern.get(FORBIDDEN_APEX_WILDCARD)
    if wildcard is not None:
        raise EdgeError(
            "APEX_WILDCARD_CONFLICT: "
            f"{FORBIDDEN_APEX_WILDCARD} is owned by {wildcard.get('script')!r}"
        )

    plan: list[dict[str, Any]] = []
    legacy = by_pattern.get(LEGACY_APEX_ROUTE)
    if legacy is not None:
        legacy_script = legacy.get("script")
        legacy_id = legacy.get("id")
        if legacy_script not in KNOWN_SCRIPT_NAMES or not legacy_id:
            raise EdgeError(
                "APEX_ROUTE_CONFLICT: "
                f"{LEGACY_APEX_ROUTE} is owned by {legacy_script!r}"
            )
        plan.append(
            {
                "action": "delete-known-legacy-apex-route",
                "pattern": LEGACY_APEX_ROUTE,
                "route_id": str(legacy_id),
                "script": str(legacy_script),
            }
        )

    www = by_pattern.get(WWW_ROUTE)
    if www is None:
        plan.append(
            {
                "action": "create-www-route",
                "pattern": WWW_ROUTE,
                "script": SCRIPT_NAME,
            }
        )
    else:
        www_script = www.get("script")
        www_id = www.get("id")
        if www_script not in KNOWN_SCRIPT_NAMES or not www_id:
            raise EdgeError(
                f"WWW_ROUTE_CONFLICT: {WWW_ROUTE} is owned by {www_script!r}"
            )
        plan.append(
            {
                "action": "update-www-route",
                "pattern": WWW_ROUTE,
                "route_id": str(www_id),
                "from_script": str(www_script),
                "script": SCRIPT_NAME,
            }
        )
    return plan


def apply_route_plan(
    zone_id: str,
    bearer: str,
    plan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in plan:
        action = item["action"]
        if action == "delete-known-legacy-apex-route":
            value = request_json(
                "DELETE",
                f"/zones/{zone_id}/workers/routes/{item['route_id']}",
                bearer=bearer,
            )
            results.append(
                {
                    **item,
                    "state": "deleted",
                    "provider_result": value.get("result"),
                }
            )
            continue

        payload = {"pattern": WWW_ROUTE, "script": SCRIPT_NAME}
        if action == "update-www-route":
            value = request_json(
                "PUT",
                f"/zones/{zone_id}/workers/routes/{item['route_id']}",
                bearer=bearer,
                payload=payload,
            )
            state = "updated"
        elif action == "create-www-route":
            value = request_json(
                "POST",
                f"/zones/{zone_id}/workers/routes",
                bearer=bearer,
                payload=payload,
            )
            state = "created"
        else:  # pragma: no cover - route_plan owns this enum
            raise EdgeError(f"unsupported route-plan action: {action}")
        result = value.get("result") or {}
        results.append(
            {
                **item,
                "state": state,
                "provider_route_id": result.get("id"),
                "provider_script": result.get("script") or SCRIPT_NAME,
            }
        )
    return results


def _redirect_observation(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "SZL-www-redirect-proof/2.0",
            "Cache-Control": "no-cache",
        },
    )
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            return {
                "status": response.status,
                "location": response.headers.get("location"),
                "edge": response.headers.get("x-szl-edge"),
                "final_url": response.geturl(),
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "location": exc.headers.get("location"),
            "edge": exc.headers.get("x-szl-edge"),
            "final_url": exc.geturl(),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "status": None,
            "location": None,
            "edge": None,
            "final_url": None,
            "error": type(exc).__name__,
        }


def _apex_observation() -> dict[str, Any]:
    url = f"https://{ZONE_NAME}/"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "SZL-www-redirect-proof/2.0",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(65536).decode("utf-8", "replace")
            return {
                "status": response.status,
                "edge": response.headers.get("x-szl-edge"),
                "final_url": response.geturl(),
                "body_has_szl": "szl" in body.lower(),
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "edge": exc.headers.get("x-szl-edge"),
            "final_url": exc.geturl(),
            "body_has_szl": False,
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "status": None,
            "edge": None,
            "final_url": None,
            "body_has_szl": False,
            "error": type(exc).__name__,
        }


def public_probe(attempts: int = 18) -> dict[str, Any]:
    source = f"https://www.{ZONE_NAME}{PROBE_PATH}?{PROBE_QUERY}"
    expected = f"https://{ZONE_NAME}{PROBE_PATH}?{PROBE_QUERY}"
    last: dict[str, Any] = {}
    for attempt in range(1, attempts + 1):
        www = _redirect_observation(source)
        apex = _apex_observation()
        www_ok = (
            www.get("status") == 301
            and www.get("location") == expected
            and www.get("edge") == EDGE_MARKER
        )
        apex_ok = (
            apex.get("status") == 200
            and apex.get("body_has_szl") is True
            and apex.get("edge") != RETIRED_EDGE_MARKER
        )
        last = {
            "attempt": attempt,
            "www": www,
            "www_expected_location": expected,
            "www_verified": www_ok,
            "apex": apex,
            "apex_verified": apex_ok,
        }
        if www_ok and apex_ok:
            return last
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
        "schema": "szl.cloudflare-www-redirect/v2",
        "zone": ZONE_NAME,
        "script": SCRIPT_NAME,
        "desired_routes": [WWW_ROUTE],
        "retired_route": LEGACY_APEX_ROUTE,
        "dry_run": args.dry_run,
        "status": "BLOCKED",
        "token_recorded": False,
        "apex_proxy_authorized": False,
    }
    bearer = token()
    if not bearer:
        report["status"] = "UNAVAILABLE"
        report["error"] = "No supported Cloudflare API token secret is configured."
        write_report(args.report, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    try:
        zones = request_json(
            "GET",
            "/zones?"
            + urllib.parse.urlencode(
                {"name": ZONE_NAME, "status": "active", "per_page": 50}
            ),
            bearer=bearer,
        ).get("result") or []
        if len(zones) != 1:
            raise EdgeError(
                f"Expected exactly one active {ZONE_NAME} zone, found {len(zones)}"
            )
        zone = zones[0]
        zone_id = str(zone["id"])
        account_id = str((zone.get("account") or {}).get("id") or "")
        if not account_id:
            raise EdgeError("The active zone did not expose an account id")
        report["zone_id_suffix"] = zone_id[-6:]
        report["account_id_suffix"] = account_id[-6:]

        current = request_json(
            "GET",
            f"/zones/{zone_id}/workers/routes",
            bearer=bearer,
        ).get("result") or []
        plan = route_plan(current)
        report["route_plan"] = plan
        if args.dry_run:
            report["status"] = "VALIDATED"
            report["probe"] = {"status": "SKIPPED_DRY_RUN"}
        else:
            upload_worker(account_id, bearer, args.worker)
            report["route_results"] = apply_route_plan(zone_id, bearer, plan)
            report["probe"] = public_probe()
            report["status"] = "LIVE"
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
