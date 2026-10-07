#!/usr/bin/env python3
"""Deploy and prove the bounded Cloudflare edge for the A11oy product domain.

The controller has authority over exactly two Worker routes:

* ``a-11-oy.com/*`` reverse-proxies to the fixed public
  ``SZLHOLDINGS/a11oy`` Space origin while preserving the visitor-facing host;
* ``www.a-11-oy.com/*`` returns a path/query-preserving 301 to the apex.

Worker Routes receive traffic only through Cloudflare-proxied DNS records. This
controller may therefore change one field—``proxied``—on the existing exact
A/AAAA/CNAME records for the apex and www hosts. It never creates or deletes DNS
records, never changes record names, types, content, TTLs, comments, tags, or
settings, and rolls back every proxy-state change if public proof fails.

When the web records are already proxied, a missing exact route may be created
only with a content-addressed Worker script whose account-wide name is absent
or has exact source bytes. A new upload uses a create-only precondition, and
the source is read back before any route write. Existing routes are not changed.
Failed public proof rolls
back only newly created routes; an uncertain provider outcome is reported as
UNKNOWN. Foreign or ambiguous provider state fails closed. Credentials and
full provider IDs are never written to the receipt.
"""
from __future__ import annotations

import argparse
import hashlib
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
SCRIPT_NAME = "szl-a11oy-product-edge-v3"
PROXIED_SCRIPT_PREFIX = "szl-a11oy-product-edge-v4-"
RETIRED_ROOT_SCRIPT = "szl-a11oy-product-root-v1"
RETIRED_WWW_SCRIPT = "szl-a11oy-www-redirect-v2"
KNOWN_SCRIPT_NAMES = frozenset(
    {SCRIPT_NAME, RETIRED_ROOT_SCRIPT, RETIRED_WWW_SCRIPT}
)
ZONE_NAME = "a-11-oy.com"
APEX_ROUTE = "a-11-oy.com/*"
WWW_ROUTE = "www.a-11-oy.com/*"
LEGACY_APEX_ROOT_ROUTE = "a-11-oy.com/"
DESIRED_ROUTES = (APEX_ROUTE, WWW_ROUTE)
WEB_HOSTS = (ZONE_NAME, f"www.{ZONE_NAME}")
WEB_RECORD_TYPES = frozenset({"A", "AAAA", "CNAME"})
EDGE_MARKER = "a11oy-product-edge-v3"
WWW_PROBE_PATH = "/__szl_edge_probe__/path"
WWW_PROBE_QUERY = "contract=v3&preserve=yes"


class EdgeError(RuntimeError):
    """Fail-closed provider or public-proof error."""


class DnsMutationError(EdgeError):
    """DNS activation failed after one or more bounded mutations."""

    def __init__(
        self,
        message: str,
        *,
        results: list[dict[str, Any]],
        rollback: list[dict[str, Any]],
    ) -> None:
        super().__init__(message)
        self.results = results
        self.rollback = rollback


class RouteMutationError(EdgeError):
    """A route write may have taken effect without an acknowledgement."""

    def __init__(
        self,
        message: str,
        *,
        results: list[dict[str, Any]],
        attempted: dict[str, Any],
        request_sent: bool = True,
    ) -> None:
        super().__init__(message)
        self.results = results
        self.attempted = attempted
        self.request_sent = request_sent


def immutable_script_name(worker: Path) -> str:
    """Never replace a script that may already serve live traffic."""
    return PROXIED_SCRIPT_PREFIX + hashlib.sha256(worker.read_bytes()).hexdigest()[:16]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Expose 3xx responses instead of following them."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):  # type: ignore[no-untyped-def]
        return None


def token() -> str:
    return (
        os.environ.get("CLOUDFLARE_API_TOKEN")
        or os.environ.get("CF_API_TOKEN")
        or os.environ.get("CLOUDFLARE_TOKEN")
        or os.environ.get("CF_TOKEN")
        or os.environ.get("CLOUDFLARE_WORKERS_API_TOKEN")
        or ""
    ).strip()


def _safe_error(error: BaseException, bearer: str) -> str:
    try:
        text = str(error)
    except Exception:
        text = "<unprintable>"
    if bearer:
        text = text.replace(bearer, "<redacted>")
    return " ".join(text.split())[:4000] or "<empty>"


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
        {"main_module": "worker.mjs", "compatibility_date": "2026-09-03"},
        separators=(",", ":"),
    ).encode("utf-8")
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


def upload_worker(
    account_id: str,
    bearer: str,
    worker: Path,
    *,
    script_name: str = SCRIPT_NAME,
    create_only: bool = False,
) -> dict[str, Any]:
    body, boundary = multipart_module(worker.read_bytes())
    headers = {
        "Authorization": f"Bearer {bearer}",
        "Accept": "application/json",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    if create_only:
        # A concurrent account writer must not turn this PUT into replacement.
        headers["If-None-Match"] = "*"
    request = urllib.request.Request(
        f"{API}/accounts/{account_id}/workers/scripts/{script_name}",
        data=body,
        method="PUT",
        headers=headers,
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


def inspect_worker_script(
    account_id: str, bearer: str, script_name: str, expected_source: bytes
) -> str:
    """Prove an account-level name is absent or already has exact source bytes."""
    value = request_json(
        "GET", f"/accounts/{account_id}/workers/scripts", bearer=bearer
    )
    info = value.get("result_info") or {}
    try:
        pages = int(info.get("total_pages") or 1)
    except (TypeError, ValueError):
        raise EdgeError("INVALID_WORKER_SCRIPT_PAGINATION") from None
    if pages != 1:
        raise EdgeError("AMBIGUOUS_WORKER_SCRIPT_PAGINATION")
    rows = value.get("result")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise EdgeError("INVALID_WORKER_SCRIPT_LIST")
    names = [row.get("id") for row in rows]
    if any(not isinstance(name, str) or not name for name in names):
        raise EdgeError("INVALID_WORKER_SCRIPT_NAME")
    if len(names) != len(set(names)):
        raise EdgeError("DUPLICATE_WORKER_SCRIPT_NAME")
    if script_name not in names:
        return "absent"

    request = urllib.request.Request(
        f"{API}/accounts/{account_id}/workers/scripts/{script_name}/content/v2",
        method="GET",
        headers={"Authorization": f"Bearer {bearer}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            actual = response.read(len(expected_source) + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise EdgeError("WORKER_SCRIPT_READBACK_UNAVAILABLE") from exc
    if actual != expected_source:
        raise EdgeError("WORKER_SCRIPT_NAME_COLLISION")
    return "identical"


def _routes_by_pattern(current: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_pattern: dict[str, dict[str, Any]] = {}
    for row in current:
        pattern = str(row.get("pattern") or "")
        if not pattern:
            continue
        if pattern in by_pattern:
            raise EdgeError(f"DUPLICATE_ROUTE_PATTERN: {pattern}")
        by_pattern[pattern] = row
    return by_pattern


def route_plan(
    current: list[dict[str, Any]],
    *,
    dns_is_proxied: bool,
    script_name: str = SCRIPT_NAME,
    allow_proxied_create: bool = False,
) -> list[dict[str, Any]]:
    """Return a bounded route plan without replacing live foreign traffic."""
    by_pattern = _routes_by_pattern(current)
    plan: list[dict[str, Any]] = []

    if dns_is_proxied and allow_proxied_create:
        desired = [by_pattern.get(pattern) for pattern in DESIRED_ROUTES]
        missing = any(row is None for row in desired)
        if missing:
            # A catch-all route must not be installed over another live Worker.
            # The dedicated script name is content-addressed so uploading it
            # cannot change any existing route's runtime.
            if not script_name.startswith(PROXIED_SCRIPT_PREFIX):
                raise EdgeError("PROXIED_CUTOVER_REQUIRES_IMMUTABLE_SCRIPT")
            # Cloudflare route wildcards can match more than their literal host
            # text suggests; refuse every other route in this exact zone.
            overlapping = [
                pattern for pattern in by_pattern if pattern not in DESIRED_ROUTES
            ]
            if overlapping:
                raise EdgeError("OVERLAPPING_LIVE_ROUTE: " + ", ".join(sorted(overlapping)))
            for row in desired:
                if row is not None and row.get("script") not in {
                    script_name,
                    SCRIPT_NAME,
                }:
                    raise EdgeError("MIXED_LIVE_ROUTE_OWNERSHIP")
        elif all(row is not None and row.get("script") == SCRIPT_NAME for row in desired):
            # An already working v3 installation is a strict no-op.
            script_name = SCRIPT_NAME

    legacy = by_pattern.get(LEGACY_APEX_ROOT_ROUTE)
    if legacy is not None:
        script = legacy.get("script")
        route_id = legacy.get("id")
        if script not in KNOWN_SCRIPT_NAMES or not route_id:
            raise EdgeError(
                "LEGACY_APEX_ROUTE_CONFLICT: "
                f"{LEGACY_APEX_ROOT_ROUTE} is owned by {script!r}"
            )
        if dns_is_proxied:
            raise EdgeError(
                "LIVE_ROUTE_MUTATION_BLOCKED: a known legacy apex-root route "
                "exists while DNS is already proxied"
            )
        plan.append(
            {
                "action": "delete-known-legacy-apex-root",
                "pattern": LEGACY_APEX_ROOT_ROUTE,
                "route_id": str(route_id),
                "script": str(script),
            }
        )

    for role, pattern in (("apex", APEX_ROUTE), ("www", WWW_ROUTE)):
        existing = by_pattern.get(pattern)
        if existing is None:
            if dns_is_proxied and not allow_proxied_create:
                raise EdgeError(
                    f"LIVE_ROUTE_MUTATION_BLOCKED: {pattern} is missing while "
                    "DNS is already proxied"
                )
            plan.append(
                {
                    "action": f"create-{role}-route",
                    "pattern": pattern,
                    "script": script_name,
                }
            )
            continue

        script = existing.get("script")
        route_id = existing.get("id")
        if script not in KNOWN_SCRIPT_NAMES | {script_name} or not route_id:
            raise EdgeError(
                f"{role.upper()}_ROUTE_CONFLICT: {pattern} is owned by {script!r}"
            )
        if script == script_name or (
            dns_is_proxied and allow_proxied_create and script == SCRIPT_NAME
        ):
            plan.append(
                {
                    "action": f"verify-{role}-route",
                    "pattern": pattern,
                    "route_id": str(route_id),
                    "script": str(script),
                }
            )
            continue
        if dns_is_proxied:
            raise EdgeError(
                f"LIVE_ROUTE_MUTATION_BLOCKED: {pattern} is owned by the "
                f"different {script!r} script while DNS is already proxied"
            )
        plan.append(
            {
                "action": f"update-{role}-route",
                "pattern": pattern,
                "route_id": str(route_id),
                "from_script": str(script),
                "script": script_name,
            }
        )
    return plan


def apply_route_plan(
    zone_id: str,
    bearer: str,
    plan: list[dict[str, Any]],
    *,
    dry_run: bool,
    expected_routes: list[dict[str, Any]] | None = None,
    guard_live_create: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in plan:
        action = item["action"]
        if action.startswith("verify-"):
            results.append({**item, "state": "already-current"})
            continue
        if dry_run:
            results.append({**item, "state": "would-apply"})
            continue

        if action == "delete-known-legacy-apex-root":
            try:
                value = request_json(
                    "DELETE",
                    f"/zones/{zone_id}/workers/routes/{item['route_id']}",
                    bearer=bearer,
                )
            except EdgeError as exc:
                raise RouteMutationError(
                    str(exc), results=results, attempted=item
                ) from exc
            results.append(
                {**item, "state": "deleted", "provider_result": value.get("result")}
            )
            continue

        payload = {"pattern": item["pattern"], "script": item["script"]}
        if guard_live_create and action.startswith("create-"):
            if expected_routes is None:
                raise EdgeError("LIVE_ROUTE_BASELINE_MISSING")
            try:
                observed = fetch_routes(zone_id, bearer)
            except EdgeError as exc:
                raise RouteMutationError(
                    "ROUTE_PREFLIGHT_UNAVAILABLE: " + str(exc),
                    results=results,
                    attempted=item,
                    request_sent=False,
                ) from exc
            if (
                route_snapshot(observed) != route_snapshot(expected_routes)
                or any(row.get("pattern") == item["pattern"] for row in observed)
            ):
                raise RouteMutationError(
                    "ROUTE_STATE_DRIFT_BEFORE_WRITE",
                    results=results,
                    attempted=item,
                    request_sent=False,
                )
        try:
            if action.startswith("update-"):
                value = request_json(
                    "PUT",
                    f"/zones/{zone_id}/workers/routes/{item['route_id']}",
                    bearer=bearer,
                    payload=payload,
                )
                state = "updated"
            elif action.startswith("create-"):
                value = request_json(
                    "POST",
                    f"/zones/{zone_id}/workers/routes",
                    bearer=bearer,
                    payload=payload,
                )
                state = "created"
            else:  # pragma: no cover - route_plan owns this enum
                raise EdgeError(f"unsupported route-plan action: {action}")
        except EdgeError as exc:
            raise RouteMutationError(
                str(exc), results=results, attempted=item
            ) from exc
        result = value.get("result") or {}
        if action.startswith("create-") and not result.get("id"):
            raise RouteMutationError(
                "ROUTE_CREATE_ACK_WITHOUT_ID",
                results=results,
                attempted=item,
            )
        results.append(
            {
                **item,
                "state": state,
                "provider_route_id": str(result.get("id") or item.get("route_id") or ""),
                "provider_script": result.get("script") or SCRIPT_NAME,
            }
        )
        if guard_live_create and action.startswith("create-"):
            assert expected_routes is not None
            expected_routes.append(
                {
                    "id": str(result["id"]),
                    "pattern": item["pattern"],
                    "script": item["script"],
                }
            )
    return results


def fetch_routes(zone_id: str, bearer: str) -> list[dict[str, Any]]:
    value = request_json(
        "GET", f"/zones/{zone_id}/workers/routes", bearer=bearer
    )
    info = value.get("result_info") or {}
    try:
        pages = int(info.get("total_pages") or 1)
    except (TypeError, ValueError):
        raise EdgeError("INVALID_WORKER_ROUTE_PAGINATION") from None
    if pages != 1:
        raise EdgeError("AMBIGUOUS_WORKER_ROUTE_PAGINATION")
    rows = value.get("result")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise EdgeError("INVALID_WORKER_ROUTE_RESULT")
    return rows


def route_snapshot(routes: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return sorted(
        (
            str(row.get("id") or ""),
            str(row.get("pattern") or ""),
            str(row.get("script") or ""),
        )
        for row in routes
    )


def verify_desired_routes(
    zone_id: str, bearer: str, plan: list[dict[str, Any]]
) -> None:
    by_pattern = _routes_by_pattern(fetch_routes(zone_id, bearer))
    for item in plan:
        if item["pattern"] not in DESIRED_ROUTES:
            continue
        current = by_pattern.get(item["pattern"])
        if not current or current.get("script") != item["script"] or not current.get("id"):
            raise EdgeError("ROUTE_POSTCONDITION_FAILED: " + item["pattern"])


def rollback_created_routes(
    zone_id: str, bearer: str, results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Delete only the exact routes created by this cutover, with readback."""
    rollback: list[dict[str, Any]] = []
    for item in reversed(results):
        if item.get("state") != "created":
            continue
        route_id = str(item.get("provider_route_id") or "")
        if item.get("pattern") not in DESIRED_ROUTES or not route_id:
            rollback.append({**item, "state": "rollback-unknown"})
            continue
        try:
            matches = [
                row
                for row in fetch_routes(zone_id, bearer)
                if row.get("pattern") == item["pattern"]
            ]
            if not matches:
                rollback.append({**item, "state": "already-absent"})
                continue
            if (
                len(matches) != 1
                or str(matches[0].get("id") or "") != route_id
                or matches[0].get("script") != item["script"]
            ):
                rollback.append({**item, "state": "rollback-unknown"})
                continue
            try:
                request_json(
                    "DELETE",
                    f"/zones/{zone_id}/workers/routes/{route_id}",
                    bearer=bearer,
                )
            except EdgeError:
                # A lost DELETE acknowledgement is resolved by fresh readback.
                pass
            remaining = [
                row
                for row in fetch_routes(zone_id, bearer)
                if row.get("pattern") == item["pattern"]
            ]
            rollback.append(
                {
                    **item,
                    "state": "restored-absent" if not remaining else "rollback-failed",
                }
            )
        except EdgeError:
            rollback.append({**item, "state": "rollback-unknown"})
    return rollback


def _normalize_dns_name(value: Any) -> str:
    return str(value or "").strip().rstrip(".").lower()


def fetch_dns_records(zone_id: str, bearer: str) -> list[dict[str, Any]]:
    """Read exact apex/www records without broad zone mutation authority."""
    records: list[dict[str, Any]] = []
    for host in WEB_HOSTS:
        query = urllib.parse.urlencode(
            {"name": host, "page": 1, "per_page": 100, "match": "all"}
        )
        value = request_json(
            "GET",
            f"/zones/{zone_id}/dns_records?{query}",
            bearer=bearer,
        )
        info = value.get("result_info") or {}
        try:
            total_pages = int(info.get("total_pages") or 1)
        except (TypeError, ValueError):
            raise EdgeError(f"INVALID_DNS_PAGINATION: {host}") from None
        if total_pages != 1:
            raise EdgeError(
                f"AMBIGUOUS_DNS_PAGINATION: {host} spans {total_pages} pages"
            )
        result = value.get("result") or []
        if not isinstance(result, list):
            raise EdgeError(f"INVALID_DNS_RESULT: {host}")
        records.extend(row for row in result if isinstance(row, dict))
    return records


def dns_proxy_plan(
    current: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """Select only exact proxiable web records and require one coherent state."""
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for host in WEB_HOSTS:
        rows = [
            row
            for row in current
            if _normalize_dns_name(row.get("name")) == host
            and str(row.get("type") or "").upper() in WEB_RECORD_TYPES
        ]
        if not rows:
            raise EdgeError(f"MISSING_WEB_DNS_RECORD: {host}")

        record_types = {str(row.get("type") or "").upper() for row in rows}
        if "CNAME" in record_types and len(rows) != 1:
            raise EdgeError(
                f"AMBIGUOUS_WEB_DNS_RECORDS: {host} mixes CNAME with other records"
            )

        for row in rows:
            record_id = str(row.get("id") or "")
            record_type = str(row.get("type") or "").upper()
            proxied = row.get("proxied")
            if not record_id or record_id in seen_ids:
                raise EdgeError(f"INVALID_OR_DUPLICATE_DNS_RECORD_ID: {host}")
            seen_ids.add(record_id)
            if row.get("proxiable") is not True:
                raise EdgeError(
                    f"NON_PROXIABLE_WEB_DNS_RECORD: {host} {record_type}"
                )
            if not isinstance(proxied, bool):
                raise EdgeError(
                    f"UNKNOWN_DNS_PROXY_STATE: {host} {record_type}"
                )
            selected.append(
                {
                    "record_id": record_id,
                    "host": host,
                    "type": record_type,
                    "prior_proxied": proxied,
                    "action": "verify-proxied" if proxied else "enable-proxy",
                }
            )

    states = {bool(item["prior_proxied"]) for item in selected}
    if len(states) != 1:
        raise EdgeError(
            "MIXED_DNS_PROXY_STATE: apex/www web records must be uniformly "
            "proxied or uniformly DNS-only before cutover"
        )
    return selected, states == {True}


def apply_dns_proxy_plan(
    zone_id: str,
    bearer: str,
    plan: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Enable only the proxy flag; rollback partial activation on any error."""
    results: list[dict[str, Any]] = []
    try:
        for item in plan:
            action = item["action"]
            if action == "verify-proxied":
                results.append({**item, "state": "already-proxied"})
                continue
            if action != "enable-proxy":
                raise EdgeError(f"unsupported DNS plan action: {action}")
            if dry_run:
                results.append({**item, "state": "would-enable-proxy"})
                continue

            value = request_json(
                "PATCH",
                f"/zones/{zone_id}/dns_records/{item['record_id']}",
                bearer=bearer,
                payload={"proxied": True},
            )
            result = value.get("result") or {}
            if result.get("proxied") is not True:
                raise EdgeError(
                    f"DNS_PROXY_ENABLE_NOT_CONFIRMED: {item['host']} {item['type']}"
                )
            applied = {**item, "state": "enabled"}
            results.append(applied)
            if result.get("name") and _normalize_dns_name(result.get("name")) != item["host"]:
                raise EdgeError(
                    f"DNS_RECORD_IDENTITY_DRIFT: {item['host']} name changed"
                )
            if result.get("type") and str(result.get("type")).upper() != item["type"]:
                raise EdgeError(
                    f"DNS_RECORD_IDENTITY_DRIFT: {item['host']} type changed"
                )
    except EdgeError as exc:
        rollback = rollback_dns_proxy_plan(zone_id, bearer, results)
        raise DnsMutationError(
            f"DNS_PROXY_ACTIVATION_FAILED: {exc}",
            results=results,
            rollback=rollback,
        ) from exc
    return results


def rollback_dns_proxy_plan(
    zone_id: str,
    bearer: str,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Restore only records this execution changed from DNS-only to proxied."""
    rollback: list[dict[str, Any]] = []
    for item in reversed(results):
        if item.get("state") != "enabled":
            continue
        try:
            value = request_json(
                "PATCH",
                f"/zones/{zone_id}/dns_records/{item['record_id']}",
                bearer=bearer,
                payload={"proxied": False},
            )
            result = value.get("result") or {}
            if result.get("proxied") is not False:
                raise EdgeError(
                    f"DNS_PROXY_ROLLBACK_NOT_CONFIRMED: {item['host']} {item['type']}"
                )
            rollback.append({**item, "state": "restored-dns-only"})
        except EdgeError as exc:
            rollback.append(
                {
                    **item,
                    "state": "rollback-failed",
                    "error": _safe_error(exc, bearer),
                }
            )
    return rollback


def _public_provider_item(item: dict[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    for key in (
        "action",
        "pattern",
        "script",
        "from_script",
        "state",
        "host",
        "type",
        "prior_proxied",
        "provider_script",
        "error",
    ):
        if key in item:
            public[key] = item[key]
    provider_id = str(
        item.get("provider_route_id")
        or item.get("route_id")
        or item.get("record_id")
        or ""
    )
    if provider_id:
        public["provider_id_suffix"] = provider_id[-6:]
    return public


def _public_provider_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_public_provider_item(item) for item in items]


def _rollback_succeeded(
    dns_results: list[dict[str, Any]],
    rollback: list[dict[str, Any]],
) -> bool:
    changed = sum(item.get("state") == "enabled" for item in dns_results)
    restored = sum(item.get("state") == "restored-dns-only" for item in rollback)
    failed = any(item.get("state") == "rollback-failed" for item in rollback)
    return changed > 0 and restored == changed and not failed


def _observation(url: str, *, follow_redirects: bool = True) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "SZL-product-edge-proof/4.0",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
        },
    )
    opener = (
        urllib.request.build_opener()
        if follow_redirects
        else urllib.request.build_opener(NoRedirect())
    )
    try:
        with opener.open(request, timeout=30) as response:
            body = response.read(131072)
            return {
                "status": response.status,
                "location": response.headers.get("location"),
                "edge": response.headers.get("x-szl-edge"),
                "alias": response.headers.get("x-szl-edge-alias"),
                "content_type": response.headers.get("content-type"),
                "final_url": response.geturl(),
                "body": body.decode("utf-8", "replace"),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(32768)
        return {
            "status": exc.code,
            "location": exc.headers.get("location"),
            "edge": exc.headers.get("x-szl-edge"),
            "alias": exc.headers.get("x-szl-edge-alias"),
            "content_type": exc.headers.get("content-type"),
            "final_url": exc.geturl(),
            "body": body.decode("utf-8", "replace"),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "status": None,
            "location": None,
            "edge": None,
            "alias": None,
            "content_type": None,
            "final_url": None,
            "body": "",
            "error": type(exc).__name__,
        }


def _public_summary(observation: dict[str, Any]) -> dict[str, Any]:
    """Return only bounded, non-content public evidence for the receipt."""
    return {
        key: observation.get(key)
        for key in ("status", "location", "edge", "alias", "content_type", "final_url", "error")
        if observation.get(key) is not None
    }


def public_probe(attempts: int = 24) -> dict[str, Any]:
    www_source = f"https://www.{ZONE_NAME}{WWW_PROBE_PATH}?{WWW_PROBE_QUERY}"
    www_expected = f"https://{ZONE_NAME}{WWW_PROBE_PATH}?{WWW_PROBE_QUERY}"
    root_url = f"https://{ZONE_NAME}/?__szl_edge_probe__=v3"
    honest_url = f"https://{ZONE_NAME}/api/a11oy/v1/honest?__szl_edge_probe__=v3"
    last: dict[str, Any] = {}

    spectral_url = f"https://{ZONE_NAME}/spectral?__szl_edge_probe__=v3"
    controller_url = f"https://{ZONE_NAME}/controller?__szl_edge_probe__=v3"

    for attempt in range(1, attempts + 1):
        www = _observation(www_source, follow_redirects=False)
        root = _observation(root_url)
        honest = _observation(honest_url)
        spectral = _observation(spectral_url)
        controller = _observation(controller_url)

        root_body = str(root.get("body") or "").lower()
        root_ok = (
            root.get("status") == 200
            and root.get("edge") == EDGE_MARKER
            and ("a11oy" in root_body or "szl" in root_body)
        )

        honest_json: dict[str, Any] = {}
        try:
            parsed = json.loads(str(honest.get("body") or ""))
            if isinstance(parsed, dict):
                honest_json = parsed
        except json.JSONDecodeError:
            honest_json = {}
        honest_ok = (
            honest.get("status") == 200
            and honest.get("edge") == EDGE_MARKER
            and honest_json.get("organ") == "a11oy"
            and honest_json.get("locked_formula_count") == 8
        )

        spectral_ok = (
            spectral.get("status") == 200
            and spectral.get("edge") == EDGE_MARKER
            and spectral.get("alias")
            == "/spectral->/static/3d/holographic.html"
            and "text/html" in str(spectral.get("content_type") or "")
        )
        controller_json: dict[str, Any] = {}
        try:
            parsed = json.loads(str(controller.get("body") or ""))
            if isinstance(parsed, dict):
                controller_json = parsed
        except json.JSONDecodeError:
            controller_json = {}
        controller_ok = (
            controller.get("status") == 200
            and controller.get("edge") == EDGE_MARKER
            and controller.get("alias") == "/controller->/api/a11oy/v1/honest"
            and controller_json.get("organ") == "a11oy"
            and controller_json.get("locked_formula_count") == 8
        )

        www_ok = (
            www.get("status") == 301
            and www.get("location") == www_expected
            and www.get("edge") == EDGE_MARKER
        )

        last = {
            "attempt": attempt,
            "root": _public_summary(root),
            "root_verified": root_ok,
            "honest": _public_summary(honest),
            "honest_contract": {
                "organ": honest_json.get("organ"),
                "locked_formula_count": honest_json.get("locked_formula_count"),
            },
            "honest_verified": honest_ok,
            "spectral": _public_summary(spectral),
            "spectral_verified": spectral_ok,
            "controller": _public_summary(controller),
            "controller_verified": controller_ok,
            "www": _public_summary(www),
            "www_expected_location": www_expected,
            "www_verified": www_ok,
        }
        if root_ok and honest_ok and www_ok and spectral_ok and controller_ok:
            return last
        time.sleep(min(5, attempt))

    raise EdgeError("PUBLIC_PROBE_FAILED: " + json.dumps(last, sort_keys=True))


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, default=DEFAULT_WORKER)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report: dict[str, Any] = {
        "schema": "szl.cloudflare-product-edge/v4",
        "zone": ZONE_NAME,
        "origin": "SZLHOLDINGS/a11oy",
        "script": SCRIPT_NAME,
        "desired_routes": list(DESIRED_ROUTES),
        "web_hosts": list(WEB_HOSTS),
        "dry_run": args.dry_run,
        "status": "BLOCKED",
        "token_recorded": False,
        "apex_proxy_authorized": True,
        "dns_proxy_cutover_authorized": True,
        "dns_mutated": False,
        "dns_rollback_succeeded": None,
    }
    bearer = token()
    if not bearer:
        report["status"] = "UNAVAILABLE"
        report["error"] = "No supported Cloudflare API token secret is configured."
        write_report(args.report, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    zone_id = ""
    dns_results: list[dict[str, Any]] = []
    try:
        verify = request_json(
            "GET",
            "/user/tokens/verify",
            bearer=bearer,
        ).get("result") or {}
        report["token_status"] = verify.get("status")
        if verify.get("status") != "active":
            raise EdgeError("Cloudflare API token is not active")

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

        dns_current = fetch_dns_records(zone_id, bearer)
        dns_plan, dns_is_proxied = dns_proxy_plan(dns_current)
        report["dns_initially_proxied"] = dns_is_proxied
        report["dns_plan"] = _public_provider_items(dns_plan)

        routes_current = fetch_routes(zone_id, bearer)
        proxied_script = immutable_script_name(args.worker)
        target_script = proxied_script if dns_is_proxied else SCRIPT_NAME
        route_actions = route_plan(
            routes_current,
            dns_is_proxied=dns_is_proxied,
            script_name=target_script,
            allow_proxied_create=True,
        )
        report["route_plan"] = _public_provider_items(route_actions)
        live_creates = dns_is_proxied and any(
            item["action"].startswith("create-") for item in route_actions
        )
        if dns_is_proxied and any(
            item["script"] == proxied_script for item in route_actions
        ):
            report["script"] = proxied_script
        upload_needed = live_creates or not dns_is_proxied
        upload_script = proxied_script if live_creates else SCRIPT_NAME
        script_state = None
        if upload_needed:
            script_state = inspect_worker_script(
                account_id, bearer, upload_script, args.worker.read_bytes()
            )
            report["worker_script_preflight"] = script_state

        if not args.dry_run:
            if live_creates:
                # Re-read both provider surfaces before the first live write.
                current_dns_plan, still_proxied = dns_proxy_plan(
                    fetch_dns_records(zone_id, bearer)
                )
                if (
                    not still_proxied
                    or current_dns_plan != dns_plan
                    or route_snapshot(fetch_routes(zone_id, bearer))
                    != route_snapshot(routes_current)
                ):
                    raise EdgeError("PROVIDER_STATE_DRIFT_BEFORE_CUTOVER")
            if upload_needed:
                if script_state == "absent":
                    try:
                        upload_worker(
                            account_id, bearer, args.worker,
                            script_name=upload_script, create_only=True,
                        )
                    except EdgeError:
                        report["status"] = "UNKNOWN"
                        report["worker_upload_outcome"] = "UNKNOWN"
                        raise
                    report["worker_upload_outcome"] = "uploaded"
                else:
                    report["worker_upload_outcome"] = "skipped-identical"
                try:
                    verified_script = inspect_worker_script(
                        account_id, bearer, upload_script, args.worker.read_bytes()
                    )
                except EdgeError:
                    report["status"] = "UNKNOWN"
                    raise
                if verified_script != "identical":
                    report["status"] = "UNKNOWN"
                    raise EdgeError("WORKER_SCRIPT_READBACK_NOT_IDENTICAL")
            if live_creates:
                if route_snapshot(fetch_routes(zone_id, bearer)) != route_snapshot(
                    routes_current
                ):
                    raise EdgeError("ROUTE_STATE_DRIFT_AFTER_WORKER_UPLOAD")
        try:
            route_results = apply_route_plan(
                zone_id,
                bearer,
                route_actions,
                dry_run=args.dry_run,
                expected_routes=list(routes_current) if live_creates else None,
                guard_live_create=live_creates and not args.dry_run,
            )
        except RouteMutationError as exc:
            if not dns_is_proxied:
                raise
            # A matching post-error route could belong to a concurrent writer.
            # Never infer authorship from pattern/script or delete it on rollback.
            route_results = list(exc.results)
            rollback = rollback_created_routes(zone_id, bearer, route_results)
            report["route_results"] = _public_provider_items(route_results)
            report["route_attempted"] = _public_provider_item(exc.attempted)
            report["route_write_request_sent"] = exc.request_sent
            report["route_rollback"] = _public_provider_items(rollback)
            report["status"] = "UNKNOWN"
            raise EdgeError("ROUTE_WRITE_FAILED: " + str(exc)) from exc
        report["route_results"] = _public_provider_items(route_results)

        dns_results = apply_dns_proxy_plan(
            zone_id,
            bearer,
            dns_plan,
            dry_run=args.dry_run,
        )
        report["dns_results"] = _public_provider_items(dns_results)
        report["dns_mutated"] = any(
            item.get("state") == "enabled" for item in dns_results
        )

        if args.dry_run:
            report["probe"] = {"status": "SKIPPED_DRY_RUN"}
            report["status"] = "VALIDATED"
        else:
            try:
                report["probe"] = public_probe()
                verify_desired_routes(zone_id, bearer, route_actions)
            except EdgeError as exc:
                rollback = rollback_dns_proxy_plan(zone_id, bearer, dns_results)
                report["dns_rollback"] = _public_provider_items(rollback)
                if dns_is_proxied:
                    route_rollback = rollback_created_routes(
                        zone_id, bearer, route_results
                    )
                    report["route_rollback"] = _public_provider_items(route_rollback)
                    if route_rollback:
                        report["status"] = (
                            "ROLLED_BACK"
                            if all(
                                row["state"] in {"restored-absent", "already-absent"}
                                for row in route_rollback
                            )
                            else "ROLLBACK_FAILED"
                        )
                if report["dns_mutated"]:
                    report["dns_rollback_succeeded"] = _rollback_succeeded(
                        dns_results,
                        rollback,
                    )
                    report["status"] = (
                        "ROLLED_BACK"
                        if report["dns_rollback_succeeded"]
                        else "ROLLBACK_FAILED"
                    )
                report["error"] = _safe_error(exc, bearer)
                write_report(args.report, report)
                print(json.dumps(report, indent=2, sort_keys=True))
                return 1
            report["status"] = "LIVE"
    except DnsMutationError as exc:
        report["dns_results"] = _public_provider_items(exc.results)
        report["dns_mutated"] = any(
            item.get("state") == "enabled" for item in exc.results
        )
        report["dns_rollback"] = _public_provider_items(exc.rollback)
        if report["dns_mutated"]:
            report["dns_rollback_succeeded"] = _rollback_succeeded(
                exc.results,
                exc.rollback,
            )
            report["status"] = (
                "ROLLED_BACK"
                if report["dns_rollback_succeeded"]
                else "ROLLBACK_FAILED"
            )
        else:
            report["dns_rollback_succeeded"] = None
            report["status"] = "BLOCKED"
        report["error"] = _safe_error(exc, bearer)
        write_report(args.report, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1
    except EdgeError as exc:
        report["error"] = _safe_error(exc, bearer)
        write_report(args.report, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1

    write_report(args.report, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
