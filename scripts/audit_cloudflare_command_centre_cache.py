#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""GET-only product cache-policy observation. Taxonomy: supply-chain.

Provider documents are temporary inputs, never report artifacts. This observer
has no deployment, cache purge, rule update, credential or DNS write operation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from szl_provider_http import http_json  # noqa: E402

API = "https://api.cloudflare.com/client/v4"
ZONE = "a-11-oy.com"
ORIGIN = "szlholdings-a11oy.hf.space"
ASSETS = (
    "/command-centre/app.js",
    "/command-centre/style.css",
    "/command-centre/szl/szl-design-system.css",
    "/command-centre/szl/szl-console.css",
)
PHASES = (
    "http_request_cache_settings",
    "http_response_cache_settings",
    "http_response_headers_transform",
)
MAX_REQUESTS = 16
MAX_RESPONSE_BYTES = 512 * 1024
MAX_REPORT_BYTES = 512 * 1024
MAX_ROWS = 200
MAX_EXPRESSION_BYTES = 16384
REQUEST_TIMEOUT = 8.0
AUDIT_TIMEOUT = 90.0
ID_RE = re.compile(r"[0-9a-f]{32}")
FLAGS = frozenset({
    "cache_option_enabled", "cache_option_disabled",
    "cache_option_preserves_cache_control", "cache_option_overrides_cache_control",
    "request_cf_overrides_cache_rules", "request_cf_does_not_override_cache_rules",
    "cache_api_compat_flags", "cache_api_request_cf_overrides_cache_rules",
})
EXPRESSION_FIELDS = (
    "http.host", "http.request.uri.path", "http.request.uri.query",
    "http.request.full_uri", "http.request.method", "http.request.headers",
    "http.cookie", "http.response.code", "http.response.headers",
)
PUBLIC_LITERALS = frozenset({
    ZONE, ORIGIN, "GET", "HEAD", ".js", ".css", "/command-centre/",
    *ASSETS, *("https://" + host + path for host in (ZONE, ORIGIN) for path in ASSETS),
})
CACHE_HEADERS = frozenset({
    "cache-control", "cdn-cache-control", "cloudflare-cdn-cache-control",
    "surrogate-control", "expires", "pragma", "vary", "age", "etag", "last-modified",
})
TTL_MODES = frozenset({"respect_origin", "override_origin", "bypass_by_default"})
CACHE_BOOL_FIELDS = (
    "cache", "origin_cache_control", "respect_strong_etags",
    "cache_deception_armor",
    "strip_etags", "strip_set_cookie", "strip_last_modified",
)
CACHE_ACTIONS = frozenset({
    "set_cache_settings", "set_cache_control", "rewrite",
    "set_browser_cache_ttl", "set_cache_tags",
})
DURATION_DIRECTIVES = frozenset({"max-age", "s-maxage", "stale-if-error", "stale-while-revalidate"})
RESPONSE_DIRECTIVES = DURATION_DIRECTIVES | frozenset({
    "private", "no-cache", "no-store", "no-transform", "must-revalidate",
    "proxy-revalidate", "must-understand", "public", "immutable",
})


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def identifier(value):
    return value if isinstance(value, str) and ID_RE.fullmatch(value) else None


def integer(value, low=0, high=315360000):
    return value if type(value) is int and low <= value <= high else None


def enum_value(value, allowed):
    return value if isinstance(value, str) and value in allowed else None


def incomplete_projection(value):
    if isinstance(value, dict):
        if enum_value(value.get("state"), {"MALFORMED", "NOT_PROJECTED", "INVALID_OR_OVERSIZED", "TRUNCATED"}):
            return True
        return any(incomplete_projection(item) for item in value.values())
    if isinstance(value, list):
        return any(incomplete_projection(item) for item in value)
    return False


def expression_summary(value):
    """Keep fixed public literals and field names; never retain expressions."""
    try:
        encoded = value.encode("utf-8") if isinstance(value, str) else b""
    except UnicodeError:
        return {"state": "INVALID_OR_OVERSIZED"}
    if not isinstance(value, str) or len(encoded) > MAX_EXPRESSION_BYTES:
        return {"state": "INVALID_OR_OVERSIZED"}
    literals = []
    for quoted in re.findall(r'"(?:[^"\\]|\\.)*"', value):
        try:
            literal = json.loads(quoted)
        except ValueError:
            continue
        if literal in PUBLIC_LITERALS:
            literals.append(literal)
    return {
        "state": "REDACTED_NOT_EVALUATED",
        "sha256": digest(value),
        "bytes": len(value.encode("utf-8")),
        "constant_true": value.strip() == "true",
        "fields_seen": [field for field in EXPRESSION_FIELDS if field in value],
        "fixed_public_literals_seen": sorted(set(literals)),
    }


def cache_directives(value):
    """Only standard directive names and bounded numeric TTLs may leave memory."""
    if not isinstance(value, str) or len(value) > MAX_EXPRESSION_BYTES:
        return {"state": "NOT_PROJECTED"}
    projected = {}
    omitted = 0
    for component in value.split(",")[:64]:
        name, separator, argument = component.strip().lower().partition("=")
        if name in {"no-store", "no-cache", "private", "public", "must-revalidate",
                    "proxy-revalidate", "no-transform", "immutable"} and not separator:
            projected[name] = True
        elif name in {"max-age", "s-maxage", "stale-while-revalidate", "stale-if-error"}:
            if separator and re.fullmatch(r"[0-9]{1,9}", argument):
                projected[name] = int(argument)
            else:
                omitted += 1
        else:
            omitted += 1
    return {"directives": projected, "unprojected_components": omitted,
            "input_truncated": len(value.split(",")) > 64}


def ttl_summary(value):
    if not isinstance(value, dict):
        return {"state": "NOT_PROJECTED"}
    out = {}
    if "mode" in value:
        mode = enum_value(value["mode"], TTL_MODES)
        if mode is None:
            out["state"] = "MALFORMED"
        else:
            out["mode"] = mode
    default = integer(value.get("default"), -1)
    if default is not None:
        out["default"] = default
    elif "default" in value:
        out["state"] = "MALFORMED"
    rows = value.get("status_code_ttl")
    if "status_code_ttl" in value and not isinstance(rows, list):
        out["state"] = "MALFORMED"
    if isinstance(rows, list):
        out["status_code_ttl"] = []
        for row in rows[:20]:
            if not isinstance(row, dict):
                out["state"] = "MALFORMED"
                continue
            item = {"value": integer(row.get("value"), -1)}
            if item["value"] is None:
                out["state"] = "MALFORMED"
            selectors = {key for key in ("status_code", "status_code_range") if key in row}
            if len(selectors) != 1:
                out["state"] = "MALFORMED"
            if "status_code_range" in row:
                ranges = row["status_code_range"]
                if not isinstance(ranges, dict):
                    out["state"] = "MALFORMED"
                else:
                    safe_range = {key: ranges[key] for key in ("from", "to")
                                  if integer(ranges.get(key), 100, 599) is not None}
                    if (not safe_range or any(key in ranges and key not in safe_range for key in ("from", "to"))
                            or safe_range.get("from", 100) > safe_range.get("to", 599)):
                        out["state"] = "MALFORMED"
                    item["status_code_range"] = safe_range
            if "status_code" in row:
                status = integer(row["status_code"], 100, 599)
                if status is None:
                    out["state"] = "MALFORMED"
                else:
                    item["status_code"] = status
            out["status_code_ttl"].append(item)
        out["status_rows_omitted"] = max(0, len(rows) - 20)
        if len(rows) > 20:
            out["state"] = "TRUNCATED"
    return out


def response_directive_summary(name, value):
    """Project documented Cache Response Rules directives, never qualifiers."""
    if not isinstance(value, dict):
        return {"state": "MALFORMED"}
    operation = enum_value(value.get("operation"), {"set", "remove"})
    out = {"state": "OBSERVED" if operation else "MALFORMED", "operation": operation}
    if "cloudflare_only" in value:
        if type(value["cloudflare_only"]) is bool:
            out["cloudflare_only"] = value["cloudflare_only"]
        else:
            out["state"] = "MALFORMED"
    if name in DURATION_DIRECTIVES and ("value" in value or operation == "set"):
        duration = integer(value.get("value"))
        if duration is None:
            out["state"] = "MALFORMED"
        else:
            out["value"] = duration
    if "qualifiers" in value:
        qualifiers = value["qualifiers"]
        out["qualifiers"] = "PRESENT_REDACTED"
        if isinstance(qualifiers, list) and all(isinstance(item, str) for item in qualifiers):
            out["qualifier_count"] = len(qualifiers)
        else:
            out["state"] = "MALFORMED"
    return out


def parameters_summary(value):
    if not isinstance(value, dict):
        return {"state": "NOT_PROJECTED"}
    out = {}
    for key in CACHE_BOOL_FIELDS:
        if type(value.get(key)) is bool:
            out[key] = value[key]
        elif key in value:
            out["state"] = "MALFORMED"
    directives = {name: response_directive_summary(name, value[name])
                  for name in sorted(RESPONSE_DIRECTIVES) if name in value}
    if directives:
        out["cache_control_directives"] = directives
    for key in ("edge_ttl", "browser_ttl"):
        if key in value:
            out[key] = ttl_summary(value[key])
    if "cache_key" in value:
        # Custom keys may contain cookie/header values and private hostnames.
        out["custom_cache_key"] = "PRESENT_REDACTED"
    headers = value.get("headers")
    if "headers" in value and not isinstance(headers, dict):
        out["state"] = "MALFORMED"
    if isinstance(headers, dict):
        out["cache_response_headers"] = {}
        for name, settings in headers.items():
            if not isinstance(name, str) or name.lower() not in CACHE_HEADERS:
                continue
            if not isinstance(settings, dict):
                out["cache_response_headers"][name.lower()] = {"state": "MALFORMED"}
                continue
            operation = enum_value(settings.get("operation"), {"set", "add", "remove"})
            item = {"operation": operation}
            if operation is None:
                item["state"] = "MALFORMED"
            if name.lower() in {"cache-control", "cdn-cache-control",
                                "cloudflare-cdn-cache-control", "surrogate-control"}:
                if "value" in settings:
                    item["value"] = cache_directives(settings["value"])
            elif "value" in settings:
                item["value"] = "REDACTED"
            if "expression" in settings:
                item["expression"] = expression_summary(settings["expression"])
            out["cache_response_headers"][name.lower()] = item
        out["other_header_names_omitted"] = sum(
            1 for name in headers if not isinstance(name, str) or name.lower() not in CACHE_HEADERS)
    return out


def rules_summary(document, phase):
    if not isinstance(document, dict) or document.get("phase") != phase:
        return {"state": "MALFORMED", "reason": "PHASE_IDENTITY_MISMATCH"}
    rows = document.get("rules")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows[:MAX_ROWS]):
        return {"state": "MALFORMED", "reason": "RULE_LIST_INVALID"}
    projected = []
    for index, row in enumerate(rows[:MAX_ROWS]):
        params = parameters_summary(row.get("action_parameters", {}))
        if (phase == "http_response_headers_transform" and not params.get("cache_response_headers")
                and not incomplete_projection(params)):
            continue
        if row.get("action") == "set_cache_tags":
            params["cache_tags"] = "PRESENT_REDACTED"
        projected.append({
            "position": index,
            "id": identifier(row.get("id")),
            "enabled": row.get("enabled") if type(row.get("enabled")) is bool else None,
            "action": enum_value(row.get("action"), CACHE_ACTIONS) or "OTHER",
            "expression": expression_summary(row.get("expression")),
            "parameters": params,
        })
    return {
        "state": ("TRUNCATED" if len(rows) > MAX_ROWS else "PARTIAL" if
                  incomplete_projection(projected) or any(
                      item["action"] == "OTHER" for item in projected) else "OBSERVED"),
        "id": identifier(document.get("id")), "phase": phase,
        "rules_observed": len(rows), "rules_projected": projected,
        "rows_omitted": max(0, len(rows) - MAX_ROWS),
        "matching": "NOT_EVALUATED",
    }


def page_rules_summary(rows):
    projected, incomplete = [], False
    for row in rows:
        if not isinstance(row, dict):
            return {"state": "MALFORMED", "reason": "PAGE_RULE_INVALID"}
        action_rows = row.get("actions")
        if not isinstance(action_rows, list):
            incomplete = True
            continue
        incomplete |= len(action_rows) > 64
        actions = []
        for item in action_rows[:64]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                incomplete = True
                continue
            kind, value = item["id"], item.get("value")
            if kind in {"cache_level", "browser_cache_ttl", "edge_cache_ttl",
                        "cache_on_cookie", "bypass_cache_on_cookie", "cache_key_fields",
                        "origin_cache_control", "disable_apps", "disable_performance"}:
                safe = "REDACTED"
                if kind in {"browser_cache_ttl", "edge_cache_ttl"}:
                    safe = integer(value)
                elif kind == "cache_level":
                    safe = enum_value(value, {"bypass", "basic", "simplified", "aggressive", "cache_everything"})
                elif kind == "origin_cache_control":
                    safe = enum_value(value, {"on", "off"})
                incomplete |= safe is None
                actions.append({"id": kind, "value": safe})
        if not actions:
            continue
        targets = []
        target_rows = row.get("targets")
        if not isinstance(target_rows, list):
            incomplete = True
            target_rows = []
        incomplete |= len(target_rows) > 16
        for target in target_rows[:16]:
            constraint = target.get("constraint") if isinstance(target, dict) else None
            if isinstance(constraint, dict):
                targets.append(expression_summary(constraint.get("value")))
            else:
                incomplete = True
        status = enum_value(row.get("status"), {"active", "disabled"})
        incomplete |= status is None or incomplete_projection(targets)
        projected.append({
            "id": identifier(row.get("id")),
            "status": status or "UNKNOWN",
            "priority": integer(row.get("priority"), 0, 100000),
            "target_patterns": targets, "actions": actions,
        })
    return {"state": "PARTIAL" if incomplete else "OBSERVED", "rules_observed": len(rows),
            "rules_projected": projected, "matching": "NOT_EVALUATED"}


def worker_summary(value):
    if not isinstance(value, dict):
        return {"state": "MALFORMED", "reason": "WORKER_SETTINGS_INVALID"}
    date = value.get("compatibility_date")
    date = date if isinstance(date, str) and re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", date) else None
    flags = value.get("compatibility_flags")
    flags = flags if isinstance(flags, list) else []
    out = {
        "state": "OBSERVED", "compatibility_date": date,
        "cache_compatibility_flags": sorted({flag for flag in flags if isinstance(flag, str) and flag in FLAGS}),
        "other_compatibility_flags_omitted": sum(not isinstance(flag, str) or flag not in FLAGS for flag in flags),
        "worker_cache": {"state": "NOT_REPORTED"},
        "entrypoint_cache_overrides": {"state": "NOT_REPORTED"},
        "bindings": "NOT_RETAINED",
        "export_names": "NOT_RETAINED",
        "source_bytes": "NOT_READ",
    }
    if "cache_options" in value:
        cache = value["cache_options"]
        projected = {"state": "PRESENT"}
        if not isinstance(cache, dict) or type(cache.get("enabled")) is not bool:
            projected["state"] = "MALFORMED"
        else:
            projected["enabled"] = cache["enabled"]
        if isinstance(cache, dict) and "cross_version_cache" in cache:
            if type(cache["cross_version_cache"]) is bool:
                projected["cross_version_cache"] = cache["cross_version_cache"]
            else:
                projected["state"] = "MALFORMED"
        out["worker_cache"] = projected
    if "exports" in value:
        exports = value["exports"]
        projected = {"state": "PRESENT", "worker_entries": 0,
                     "enabled": 0, "disabled": 0, "not_reported": 0,
                     "other_exports_omitted": 0}
        if not isinstance(exports, dict):
            projected["state"] = "MALFORMED"
        elif len(exports) > MAX_ROWS:
            projected = {"state": "TRUNCATED", "reason": "EXPORT_ROW_BOUND"}
        else:
            for entry in exports.values():
                if not isinstance(entry, dict) or not isinstance(entry.get("type"), str):
                    projected["state"] = "MALFORMED"
                    continue
                if entry["type"] != "worker":
                    projected["other_exports_omitted"] += 1
                    continue
                projected["worker_entries"] += 1
                if "cache" not in entry:
                    projected["not_reported"] += 1
                elif isinstance(entry["cache"], dict) and type(entry["cache"].get("enabled")) is bool:
                    projected["enabled" if entry["cache"]["enabled"] else "disabled"] += 1
                else:
                    projected["state"] = "MALFORMED"
        out["entrypoint_cache_overrides"] = projected
    if incomplete_projection(out):
        out["state"] = "PARTIAL"
    return out


class AuditClient:
    def __init__(self, bearer, *, transport=None, clock=None):
        self.bearer = bearer
        self.transport = transport or http_json
        self.clock = clock or time.monotonic
        self.deadline = self.clock() + AUDIT_TIMEOUT
        self.requests = 0
        self.zone_id = self.account_id = self.worker = None

    def read(self, kind):
        if kind == "zone":
            path = "/zones?name=a-11-oy.com&status=active&per_page=50&page=1"
        elif not self.zone_id:
            return {"state": "UNAVAILABLE", "reason": "ZONE_NOT_VERIFIED"}
        elif kind == "routes":
            path = f"/zones/{self.zone_id}/workers/routes"
        elif kind == "rulesets":
            path = f"/zones/{self.zone_id}/rulesets?per_page=50"
        elif kind in PHASES:
            path = f"/zones/{self.zone_id}/rulesets/phases/{kind}/entrypoint"
        elif kind == "page_rules":
            path = f"/zones/{self.zone_id}/pagerules?status=active"
        elif kind in {"browser_cache_ttl", "cache_level"}:
            path = f"/zones/{self.zone_id}/settings/{kind}"
        elif kind == "worker" and self.worker and self.account_id:
            path = f"/accounts/{self.account_id}/workers/scripts/{self.worker}/settings"
        else:
            return {"state": "UNAVAILABLE", "reason": "ENDPOINT_NOT_ALLOWED"}
        remaining = self.deadline - self.clock()
        if self.requests >= MAX_REQUESTS or remaining <= 0:
            return {"state": "UNAVAILABLE", "reason": "AUDIT_BUDGET_EXHAUSTED"}
        self.requests += 1
        try:
            document, error = self.transport(
                API + path, method="GET", body=None,
                headers={"Authorization": "Bearer " + self.bearer, "Accept": "application/json"},
                timeout=min(REQUEST_TIMEOUT, remaining), max_response_bytes=MAX_RESPONSE_BYTES,
                max_redirects=0, allow_private=False, success_status=200,
            )
        except Exception:
            return {"state": "UNAVAILABLE", "reason": "TRANSPORT_FAILURE"}
        if error:
            states = {"HTTP_STATUS:401": "UNAUTHENTICATED", "HTTP_STATUS:403": "FORBIDDEN",
                      "HTTP_STATUS:404": "NOT_FOUND_UNCONFIRMED", "HTTP_STATUS:429": "RATE_LIMITED",
                      "RESPONSE_TOO_LARGE": "TRUNCATED", "TIMEOUT": "TIMEOUT"}
            return {"state": states.get(error, "UNAVAILABLE") if isinstance(error, str) else "UNAVAILABLE"}
        if not isinstance(document, dict) or document.get("success") is not True or "result" not in document:
            return {"state": "UNAVAILABLE", "reason": "INVALID_PROVIDER_ENVELOPE"}
        return {"state": "OBSERVED", "result": document["result"],
                "result_info": document.get("result_info")}


def collection(observation, *, completion=None):
    if observation["state"] != "OBSERVED":
        return observation
    rows, info = observation["result"], observation.get("result_info")
    if not isinstance(rows, list):
        return {"state": "MALFORMED", "reason": "COLLECTION_INVALID"}
    if len(rows) > MAX_ROWS:
        return {"state": "TRUNCATED", "reason": "ROW_BOUND"}
    # Rulesets use cursor pagination; discovery uses page pagination. Missing
    # completion evidence cannot establish absence of an entry point.
    if completion == "cursor" and (
        not isinstance(info, dict) or not isinstance(info.get("cursors"), dict)
    ):
        return {"state": "UNAVAILABLE", "reason": "PAGINATION_COMPLETENESS_UNVERIFIED"}
    if completion == "page" and (
        not isinstance(info, dict) or not all(key in info for key in ("page", "total_pages", "total_count"))
    ):
        return {"state": "UNAVAILABLE", "reason": "PAGINATION_COMPLETENESS_UNVERIFIED"}
    if info is not None:
        if not isinstance(info, dict):
            return {"state": "MALFORMED", "reason": "PAGINATION_INVALID"}
        if "cursors" in info:
            cursors = info["cursors"]
            if not isinstance(cursors, dict):
                return {"state": "MALFORMED", "reason": "PAGINATION_INVALID"}
            after = cursors.get("after")
            if after is not None and not isinstance(after, str):
                return {"state": "MALFORMED", "reason": "PAGINATION_INVALID"}
            if after:
                return {"state": "TRUNCATED", "reason": "ADDITIONAL_PAGES_NOT_READ"}
        if info.get("has_more") is True:
            return {"state": "TRUNCATED", "reason": "ADDITIONAL_PAGES_NOT_READ"}
        for key in ("page", "total_pages", "count", "total_count", "per_page"):
            if key in info and integer(info[key], 0, 1000000) is None:
                return {"state": "MALFORMED", "reason": "PAGINATION_INVALID"}
        if info.get("page", 1) != 1 or info.get("total_pages", 1) > 1 or info.get("total_count", len(rows)) > len(rows):
            return {"state": "TRUNCATED", "reason": "ADDITIONAL_PAGES_NOT_READ"}
        if (("count" in info and info["count"] != len(rows))
                or ("total_count" in info and info["total_count"] < len(rows))):
            return {"state": "MALFORMED", "reason": "PAGINATION_COUNT_MISMATCH"}
    return {"state": "OBSERVED", "rows": rows}


def route_observations(collection_result, expected):
    if collection_result["state"] != "OBSERVED":
        return dict(collection_result), dict(collection_result)
    rows = collection_result["rows"]
    apex = [row for row in rows if isinstance(row, dict) and row.get("pattern") == ZONE + "/*"]
    safe_patterns = {
        ZONE + "/*", "www." + ZONE + "/*", ZONE + "/api/a11oy/v1/*",
        ZONE + "/v1/*", ZONE + "/api/v2/*", "api." + ZONE + "/v1/evidence-snapshot",
        "atlas." + ZONE + "/*",
    }
    counts = {
        "routes_observed": len(rows), "apex_bindings": len(apex),
        "malformed_routes": sum(not isinstance(row, dict) or not isinstance(row.get("pattern"), str) for row in rows),
        "unrecognized_patterns": sum(not isinstance(row, dict) or enum_value(row.get("pattern"), safe_patterns) is None for row in rows),
    }
    owner = enum_value(apex[0].get("script"), {expected, "szl-a11oy-product-edge-v3"}) if len(apex) == 1 else None
    reason = ("MALFORMED_ROUTE_METADATA" if counts["malformed_routes"] else
              "APEX_ROUTE_MISSING" if not apex else "APEX_ROUTE_AMBIGUOUS" if len(apex) != 1 else
              "APEX_WORKER_NOT_ALLOWLISTED" if owner is None else None)
    if reason:
        refused = {"state": "UNAVAILABLE", "reason": reason, **counts}
        return dict(refused), dict(refused)
    identity = {"state": "OBSERVED", "pattern": ZONE + "/*", "script": owner,
                "binding_evidence": "EXACT_APEX_METADATA_ONLY", **counts}
    # A known script's metadata is safe to read; unknown routes still prevent
    # claiming that the four asset requests are handled by that script.
    if counts["unrecognized_patterns"]:
        coverage = {"state": "UNAVAILABLE", "reason": "UNRECOGNIZED_ROUTE_PATTERNS", **counts}
    else:
        coverage = {"state": "OBSERVED", "pattern": ZONE + "/*", "script": owner,
                    "binding_evidence": "ROUTE_METADATA_ONLY", **counts}
    return identity, coverage


def audit(bearer, *, transport=None, clock=None):
    report = {
        "schema": "szl.cloudflare-command-centre-cache-observation/v1",
        "state": "UNAVAILABLE", "mode": "READ_ONLY", "started_at": utc_now(),
        "scope": {"zone": ZONE, "origin": ORIGIN, "assets": list(ASSETS)},
        "provider_write_capability": False, "effective_policy": "NOT_EVALUATED",
        "atomic_snapshot": False, "freshness": "COLLECTION_TIME_ONLY",
        "limits": {"requests": MAX_REQUESTS, "request_seconds": REQUEST_TIMEOUT,
                   "audit_seconds": AUDIT_TIMEOUT, "response_bytes": MAX_RESPONSE_BYTES,
                   "rows_per_collection": MAX_ROWS, "pages_per_collection": 1},
        "observations": {},
    }
    if not isinstance(bearer, str) or not bearer.strip():
        report["reason"] = "CREDENTIAL_UNAVAILABLE"
        report["provider_get_requests"] = 0
        report["finished_at"] = utc_now()
        return report
    client = AuditClient(bearer.strip(), transport=transport, clock=clock)
    observations = report["observations"]
    zone = collection(client.read("zone"), completion="page")
    observations["zone"] = {key: value for key, value in zone.items() if key != "rows"}
    if zone["state"] == "OBSERVED":
        rows = zone["rows"]
        selected = rows[0] if len(rows) == 1 and isinstance(rows[0], dict) else {}
        account = selected.get("account", {})
        zid = identifier(selected.get("id"))
        aid = identifier(account.get("id")) if isinstance(account, dict) else None
        if selected.get("name") != ZONE or selected.get("status") != "active" or not zid or not aid:
            observations["zone"] = {"state": "UNAVAILABLE", "reason": "ZONE_IDENTITY_UNVERIFIED"}
        else:
            client.zone_id, client.account_id = zid, aid
            observations["zone"] = {"state": "OBSERVED", "name": ZONE, "status": "active",
                                    "zone_id_suffix": zid[-6:], "account_id_suffix": aid[-6:]}
    if client.zone_id:
        source = (ROOT / "cloudflare/a11oy-product-root-worker.mjs").read_bytes()
        source_sha = hashlib.sha256(source).hexdigest()
        expected = "szl-a11oy-product-edge-v4-" + source_sha[:16]
        routes = collection(client.read("routes"))
        identity, coverage = route_observations(routes, expected)
        if identity["state"] == "OBSERVED":
            identity["local_worker_sha256"] = source_sha
        observations["worker_apex_identity"] = identity
        observations["worker_route"] = coverage
        owner = identity.get("script") if identity["state"] == "OBSERVED" else None
        client.worker = owner
        inventory = collection(client.read("rulesets"), completion="cursor")
        phases_present = None
        if inventory["state"] == "OBSERVED":
            if all(isinstance(row, dict) and isinstance(row.get("phase"), str)
                   and isinstance(row.get("kind"), str) for row in inventory["rows"]):
                phases_present = {row["phase"] for row in inventory["rows"] if row["kind"] == "zone"}
            else:
                inventory = {"state": "MALFORMED", "reason": "RULESET_INDEX_INVALID"}
        observations["ruleset_index"] = {key: value for key, value in inventory.items() if key != "rows"}
        for phase in PHASES:
            result = client.read(phase)
            if result["state"] == "OBSERVED":
                observations[phase] = rules_summary(result["result"], phase)
            elif result["state"] == "NOT_FOUND_UNCONFIRMED" and phases_present is not None and phase not in phases_present:
                observations[phase] = {"state": "ABSENT", "basis": "COMPLETE_ZONE_RULESET_INDEX_AND_404"}
            else:
                observations[phase] = result
        pages = collection(client.read("page_rules"))
        observations["page_rules"] = page_rules_summary(pages["rows"]) if pages["state"] == "OBSERVED" else pages
        for setting in ("browser_cache_ttl", "cache_level"):
            result = client.read(setting)
            if result["state"] == "OBSERVED":
                item = result["result"]
                value = item.get("value") if isinstance(item, dict) and item.get("id") == setting else None
                valid = (integer(value) is not None if setting == "browser_cache_ttl"
                         else enum_value(value, {"basic", "simplified", "aggressive"}) is not None)
                observations[setting] = {"state": "OBSERVED", "value": value} if valid else {"state": "MALFORMED"}
            else:
                observations[setting] = result
        if owner:
            settings = client.read("worker")
            observations["worker_settings"] = worker_summary(settings["result"]) if settings["state"] == "OBSERVED" else settings
            final_routes = collection(client.read("routes"))
            final_identity, final_coverage = route_observations(final_routes, expected)
            same_apex = final_identity.get("script") == owner and final_identity["state"] == "OBSERVED"
            observations["route_recheck"] = (
                {"state": "OBSERVED", "same_owner": True} if same_apex and final_coverage["state"] == "OBSERVED"
                else {**final_coverage, "state": "UNAVAILABLE", "same_apex_binding": same_apex,
                      "reason": final_coverage.get("reason", "APEX_BINDING_CHANGED" if same_apex is False and final_identity["state"] == "OBSERVED" else "ROUTE_RECHECK_FAILED")})
        else:
            observations["worker_settings"] = {"state": "UNAVAILABLE", "reason": "OWNED_WORKER_NOT_VERIFIED"}
        report["state"] = "OBSERVED" if all(
            row["state"] in {"OBSERVED", "ABSENT"} for row in observations.values()) else "PARTIAL"
    report["provider_get_requests"] = client.requests
    report["finished_at"] = utc_now()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if os.environ.get("GITHUB_ACTIONS") == "true" and (
        os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_REPOSITORY") != "szl-holdings/a11oy"
    ):
        print("READ_ONLY_AUDIT_REFUSED_UNPROTECTED_CONTEXT")
        return 2
    bearer = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    try:
        report = audit(bearer)
        revision = os.environ.get("GITHUB_SHA", "")
        report["audit_source_revision"] = revision if re.fullmatch(r"[0-9a-f]{40}", revision) else None
        encoded = (json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(encoded) > MAX_REPORT_BYTES or (bearer and bearer.encode("utf-8") in encoded):
            print("READ_ONLY_AUDIT_PROJECTION_REFUSED")
            return 2
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("xb") as output:
            output.write(encoded)
        print(json.dumps({"state": report["state"], "provider_get_requests": report["provider_get_requests"],
                          "provider_write_capability": False, "effective_policy": "NOT_EVALUATED"}))
        return 0 if report["state"] == "OBSERVED" else 2
    except Exception:
        # Provider exceptions, local paths and raw documents never become logs.
        print("READ_ONLY_AUDIT_UNAVAILABLE")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
