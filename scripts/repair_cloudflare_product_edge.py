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

Live route changes are allowed only while all selected web records are
unproxied. When they are already proxied, both desired routes must already be
owned by the current SZL Worker and the route plan becomes a no-op. Foreign or
ambiguous provider state fails closed. Credentials and full provider IDs are
never written to the receipt.
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
SCRIPT_NAME = "szl-a11oy-product-edge-v3"
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
) -> list[dict[str, Any]]:
    """Return a bounded route plan without changing live foreign traffic."""
    by_pattern = _routes_by_pattern(current)
    plan: list[dict[str, Any]] = []

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
            if dns_is_proxied:
                raise EdgeError(
                    f"LIVE_ROUTE_MUTATION_BLOCKED: {pattern} is missing while "
                    "DNS is already proxied"
                )
            plan.append(
                {
                    "action": f"create-{role}-route",
                    "pattern": pattern,
                    "script": SCRIPT_NAME,
                }
            )
            continue

        script = existing.get("script")
        route_id = existing.get("id")
        if script not in KNOWN_SCRIPT_NAMES or not route_id:
            raise EdgeError(
                f"{role.upper()}_ROUTE_CONFLICT: {pattern} is owned by {script!r}"
            )
        if script == SCRIPT_NAME:
            plan.append(
                {
                    "action": f"verify-{role}-route",
                    "pattern": pattern,
                    "route_id": str(route_id),
                    "script": SCRIPT_NAME,
                }
            )
            continue
        if dns_is_proxied:
            raise EdgeError(
                f"LIVE_ROUTE_MUTATION_BLOCKED: {pattern} is owned by the "
                f"retired {script!r} script while DNS is already proxied"
            )
        plan.append(
            {
                "action": f"update-{role}-route",
                "pattern": pattern,
                "route_id": str(route_id),
                "from_script": str(script),
                "script": SCRIPT_NAME,
            }
        )
    return plan


def apply_route_plan(
    zone_id: str,
    bearer: str,
    plan: list[dict[str, Any]],
    *,
    dry_run: bool,
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
            value = request_json(
                "DELETE",
                f"/zones/{zone_id}/workers/routes/{item['route_id']}",
                bearer=bearer,
            )
            results.append(
                {**item, "state": "deleted", "provider_result": value.get("result")}
            )
            continue

        payload = {"pattern": item["pattern"], "script": SCRIPT_NAME}
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
        result = value.get("result") or {}
        results.append(
            {
                **item,
                "state": state,
                "provider_route_id": str(result.get("id") or item.get("route_id") or ""),
                "provider_script": result.get("script") or SCRIPT_NAME,
            }
        )
    return results


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
            "content_type": exc.headers.get("content-type"),
            "final_url": exc.geturl(),
            "body": body.decode("utf-8", "replace"),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "status": None,
            "location": None,
            "edge": None,
            "content_type": None,
            "final_url": None,
            "body": "",
            "error": type(exc).__name__,
        }


def _public_summary(observation: dict[str, Any]) -> dict[str, Any]:
    """Return only bounded, non-content public evidence for the receipt."""
    return {
        key: observation.get(key)
        for key in ("status", "location", "edge", "content_type", "final_url", "error")
        if observation.get(key) is not None
    }


def public_probe(attempts: int = 24) -> dict[str, Any]:
    www_source = f"https://www.{ZONE_NAME}{WWW_PROBE_PATH}?{WWW_PROBE_QUERY}"
    www_expected = f"https://{ZONE_NAME}{WWW_PROBE_PATH}?{WWW_PROBE_QUERY}"
    root_url = f"https://{ZONE_NAME}/?__szl_edge_probe__=v3"
    honest_url = f"https://{ZONE_NAME}/api/a11oy/v1/honest?__szl_edge_probe__=v3"
    last: dict[str, Any] = {}

    for attempt in range(1, attempts + 1):
        www = _observation(www_source, follow_redirects=False)
        root = _observation(root_url)
        honest = _observation(honest_url)

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
            "www": _public_summary(www),
            "www_expected_location": www_expected,
            "www_verified": www_ok,
        }
        if root_ok and honest_ok and www_ok:
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

        routes_current = request_json(
            "GET",
            f"/zones/{zone_id}/workers/routes",
            bearer=bearer,
        ).get("result") or []
        route_actions = route_plan(
            routes_current,
            dns_is_proxied=dns_is_proxied,
        )
        report["route_plan"] = _public_provider_items(route_actions)

        if not args.dry_run:
            upload_worker(account_id, bearer, args.worker)
        route_results = apply_route_plan(
            zone_id,
            bearer,
            route_actions,
            dry_run=args.dry_run,
        )
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
            except EdgeError as exc:
                rollback = rollback_dns_proxy_plan(zone_id, bearer, dns_results)
                report["dns_rollback"] = _public_provider_items(rollback)
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
