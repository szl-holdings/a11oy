#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Audit one existing a11oy.net RUM property; explicitly disable its injection.

This maintenance controller is not an agent execution sandbox. Admission is
fixed-domain, fixed-beacon and compare-before-write. It never grants credentials,
creates properties, follows redirects, retries requests or rolls back silently.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "https://api.cloudflare.com/client/v4"
DOMAIN = "a11oy.net"
BEACON_SHA256 = "b744a5e1d0496d6c5bb239e777e2f251820e03448c51c143c3897f6ab82766dc"
MAX_BYTES = 1_048_576
MAX_PAGES = 10
REQUEST_TIMEOUT = 10
TOTAL_TIMEOUT = 120
HEX_ID = re.compile(r"[a-f0-9]{32}\Z")
HEX_HASH = re.compile(r"[a-f0-9]{64}\Z")


class Refused(RuntimeError):
    """A safe, non-provider-controlled admission failure."""


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise Refused(reason)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def identifier(value: Any) -> str:
    need(isinstance(value, str) and HEX_ID.fullmatch(value) is not None,
         "Provider identifier missing or malformed")
    return value


def strict_json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            need(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def constant(_value: str) -> None:
        raise Refused("Non-finite JSON value")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError) as exc:
        raise Refused("Malformed provider JSON") from exc


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class Client:
    def __init__(self, bearer: str) -> None:
        need(bool(bearer), "CLOUDFLARE_API_TOKEN is unavailable")
        self.bearer = bearer
        self.deadline = time.monotonic() + TOTAL_TIMEOUT
        self.events: list[dict[str, Any]] = []
        self.opener = urllib.request.build_opener(NoRedirect())

    def read_bounded(self, response: Any) -> bytes:
        parts: list[bytes] = []
        size = 0
        while True:
            need(time.monotonic() < self.deadline, "Provider observation deadline exceeded")
            # read1 performs at most one underlying read, allowing budget checks
            # between chunks instead of accumulating a slowly dripped whole body.
            part = response.read1(min(65_536, MAX_BYTES + 1 - size))
            parts.append(part)
            size += len(part)
            need(size <= MAX_BYTES, "Provider response exceeded byte limit")
            if not part:
                return b"".join(parts)

    def request(self, method: str, path: str, payload: Any = None) -> dict[str, Any]:
        need(method in {"GET", "PUT"} and path.startswith("/")
             and not path.startswith("//") and "#" not in path,
             "Unsupported provider request")
        remaining = self.deadline - time.monotonic()
        need(remaining > 0, "Provider observation deadline exceeded")
        headers = {"Authorization": f"Bearer {self.bearer}",
                   "Accept": "application/json", "User-Agent": "SZL-Proof-RUM/1.0"}
        body = None
        if payload is not None:
            body = canonical(payload)
            headers["Content-Type"] = "application/json"
        event: dict[str, Any] = {"method": method, "path_sha256": digest(path),
                                 "status": None, "body_sha256": None,
                                 "provider_error_codes": [], "retried": False}
        self.events.append(event)
        request = urllib.request.Request(API + path, data=body, headers=headers,
                                         method=method)
        try:
            with self.opener.open(request, timeout=min(REQUEST_TIMEOUT, remaining)) as response:
                event["status"] = response.status
                raw = self.read_bounded(response)
        except urllib.error.HTTPError as exc:
            event["status"] = exc.code
            try:
                raw = self.read_bounded(exc)
                event["body_sha256"] = hashlib.sha256(raw).hexdigest()
                try:
                    error = strict_json(raw)
                    if isinstance(error, dict) and isinstance(error.get("errors"), list):
                        event["provider_error_codes"] = [item["code"] for item in error["errors"]
                            if isinstance(item, dict) and type(item.get("code")) is int][:20]
                except Refused:
                    pass
            except (Refused, OSError):
                event["error_body_unavailable_or_exceeded_bounds"] = True
            raise Refused(f"Provider HTTP {exc.code}; inspect numeric codes in the receipt") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise Refused("Provider transport failed; mutation outcome may be unknown") from exc
        need(event["status"] == 200, "Unexpected provider HTTP status")
        need(len(raw) <= MAX_BYTES, "Provider response exceeded byte limit")
        event["body_sha256"] = hashlib.sha256(raw).hexdigest()
        value = strict_json(raw)
        if isinstance(value, dict) and isinstance(value.get("errors"), list):
            event["provider_error_codes"] = [item["code"] for item in value["errors"]
                if isinstance(item, dict) and type(item.get("code")) is int][:20]
        need(isinstance(value, dict) and value.get("success") is True,
             "Provider success envelope missing or false")
        return value


def result_object(value: dict[str, Any]) -> dict[str, Any]:
    result = value.get("result")
    need(isinstance(result, dict), "Provider object result missing")
    return result


def admit_zone(zone: dict[str, Any], expected: tuple[str, str] | None = None) -> tuple[str, str]:
    need(zone.get("name") == DOMAIN and zone.get("status") == "active",
         "The exact a11oy.net zone is not active")
    zone_id = identifier(zone.get("id"))
    account = zone.get("account")
    need(isinstance(account, dict), "Zone account binding missing")
    account_id = identifier(account.get("id"))
    if expected is not None:
        need((zone_id, account_id) == expected, "Zone or account changed before mutation")
    return zone_id, account_id


def beacon_digest(site: dict[str, Any]) -> str | None:
    token = site.get("site_token")
    if not isinstance(token, str) or HEX_ID.fullmatch(token) is None:
        return None
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def admit_site(site: dict[str, Any], zone_id: str, site_id: str | None = None) -> str:
    tag = identifier(site.get("site_tag"))
    if site_id is not None:
        need(tag == site_id, "RUM property identity changed")
    ruleset = site.get("ruleset")
    need(isinstance(ruleset, dict) and ruleset.get("zone_name") == DOMAIN
         and ruleset.get("zone_tag") == zone_id, "RUM property zone/domain binding differs")
    need(beacon_digest(site) == BEACON_SHA256, "RUM property beacon differs from public witness")
    need(type(site.get("auto_install")) is bool, "RUM auto_install is unavailable")
    return tag


def choose_site(client: Client, account_id: str, zone_id: str) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    all_ids: set[str] = set()
    pages = None
    total_count = None
    per_page = None
    for page in range(1, MAX_PAGES + 1):
        value = client.request("GET", f"/accounts/{account_id}/rum/site_info/list?per_page=50&page={page}")
        sites, info = value.get("result"), value.get("result_info")
        need(isinstance(sites, list) and isinstance(info, dict), "RUM list or pagination missing")
        total = info.get("total_pages")
        need(type(total) is int and 1 <= total <= MAX_PAGES and info.get("page") == page,
             "RUM list pagination is incomplete or excessive")
        if pages is None:
            pages = total
            total_count, per_page = info.get("total_count"), info.get("per_page")
            need(type(total_count) is int and 0 <= total_count <= MAX_PAGES * 50
                 and type(per_page) is int and 1 <= per_page <= 50,
                 "RUM list cardinality is missing or excessive")
            need(pages == max(1, (total_count + per_page - 1) // per_page),
                 "RUM list page count differs from declared cardinality")
        need(total == pages, "RUM pagination changed during observation")
        need(info.get("total_count") == total_count and info.get("per_page") == per_page
             and info.get("count") == len(sites)
             and len(sites) == min(per_page, max(0, total_count - (page - 1) * per_page)),
             "RUM page content does not cover the declared complete list")
        for site in sites:
            need(isinstance(site, dict), "Malformed RUM property entry")
            tag = identifier(site.get("site_tag"))
            need(tag not in all_ids, "Duplicated RUM property across pages")
            all_ids.add(tag)
            binding = site.get("ruleset") or {}
            need(isinstance(binding, dict), "Malformed RUM ruleset")
            if (binding.get("zone_tag") == zone_id or binding.get("zone_name") == DOMAIN
                    or beacon_digest(site) == BEACON_SHA256):
                candidates.append(site)
        if page == pages:
            break
    need(len(all_ids) == total_count, "RUM list observation was incomplete")
    need(len(candidates) == 1, "RUM target is missing or ambiguous")
    admit_site(candidates[0], zone_id)
    return candidates[0]


def safe_settings(site: dict[str, Any]) -> dict[str, Any]:
    """Project documented values; hash identifiers, snippet and unknown fields."""
    safe_keys = {"auto_install", "created", "rules", "ruleset", "enabled", "host",
                 "inclusive", "is_paused", "paths", "priority", "zone_name", "lite"}
    def project(value: Any) -> Any:
        if isinstance(value, dict):
            result = {}
            unknown = {}
            for key, item in value.items():
                if key in {"site_token", "site_tag", "zone_tag", "id", "snippet"}:
                    result[key + "_sha256"] = digest(item)
                elif key in safe_keys:
                    result[key] = project(item)
                else:
                    unknown[key] = item
            if unknown:
                result["undocumented_fields_sha256"] = digest(unknown)
            return result
        if isinstance(value, list):
            return [project(item) for item in value]
        return value
    return project(site)


def write_new(path: Path, value: Any) -> None:
    with path.open("xb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def mutation_envelope(report: dict[str, Any]) -> dict[str, Any]:
    previous = digest({"source_revision": report["source_revision"], "domain": DOMAIN,
                       "before_settings_sha256": report.get("before_settings_sha256")})
    chain = []
    for event in report["provider_events"]:
        link = {"previous_event_sha256": previous, "event": event}
        previous = digest(link)
        chain.append(dict(link, event_sha256=previous))
    payload = {"schema": "szl.cloudflare.rum-mutation/v1", "domain": DOMAIN,
               "source_revision": report["source_revision"], "previous_event_sha256": previous,
               "before_settings_sha256": report.get("before_settings_sha256"),
               "operation": "DISABLE_EXISTING_PROPERTY_AUTO_INSTALL",
               "payload": {"auto_install": False}, "put_attempts": report["put_attempts"],
               "state": report["state"], "mutation_outcome": report["mutation_outcome"],
               "provider_event_chain": chain}
    raw = canonical(payload)
    return {"payloadType": "application/vnd.szl.cloudflare.rum-mutation+json",
            "payload": base64.b64encode(raw).decode("ascii"), "signatures": [],
            "signature_status": "UNSIGNED", "payload_sha256": hashlib.sha256(raw).hexdigest(),
            "identity_or_third_party_authenticity_verified": False}


def operate(client: Client, mode: str, expected_hash: str, out: Path,
            source_revision: str) -> dict[str, Any]:
    need(mode in {"audit", "apply"}, "Unsupported operation mode")
    need(re.fullmatch(r"[a-f0-9]{40}", source_revision) is not None,
         "An exact source revision is required")
    need(mode == "audit" or HEX_HASH.fullmatch(expected_hash) is not None,
         "Apply requires the prior exact settings SHA-256")
    report: dict[str, Any] = {"schema": "szl.cloudflare.proof-rum/v1", "mode": mode,
        "observed_at": datetime.now(timezone.utc).isoformat(), "domain": DOMAIN,
        "source_revision": source_revision, "state": "FAILED", "put_attempts": 0,
        "mutation_outcome": "NOT_ATTEMPTED",
        "token_recorded": False, "full27_served_parity": "NOT_CHECKED",
        "provider_events": client.events, "api_compare_and_swap_supported": False}
    try:
        zones = client.request("GET", "/zones?name=a11oy.net&status=active&per_page=50").get("result")
        need(isinstance(zones, list) and len(zones) == 1 and isinstance(zones[0], dict),
             "Exact active zone is missing or ambiguous")
        zone_id, account_id = admit_zone(zones[0])
        account = result_object(client.request("GET", f"/accounts/{account_id}"))
        need(account.get("id") == account_id, "Account detail does not match active zone")
        selected = choose_site(client, account_id, zone_id)
        site_id = admit_site(selected, zone_id)
        path = f"/accounts/{account_id}/rum/site_info/{site_id}"
        before = result_object(client.request("GET", path))
        admit_site(before, zone_id, site_id)
        before_hash = digest(before)
        safe_before = safe_settings(before)
        bearer = getattr(client, "bearer", "")
        need(not bearer or bearer.encode("utf-8") not in canonical(safe_before),
             "Settings projection unexpectedly contains authentication material")
        report.update({"before_settings_sha256": before_hash,
                       "before_settings": safe_before,
                       "zone_sha256": digest(zone_id), "account_sha256": digest(account_id),
                       "site_sha256": digest(site_id), "public_beacon_sha256": BEACON_SHA256,
                       "rollback_single_field": {"auto_install": before["auto_install"]}})
        write_new(out / "before-settings.json", report["before_settings"])
        if mode == "audit":
            report["state"] = "AUDITED_READ_ONLY"
            return report
        need(before_hash == expected_hash, "Current settings differ from prior audit")
        current_zone = result_object(client.request("GET", f"/zones/{zone_id}"))
        admit_zone(current_zone, (zone_id, account_id))
        last = result_object(client.request("GET", path))
        admit_site(last, zone_id, site_id)
        need(digest(last) == expected_hash, "Settings changed before mutation")
        if last["auto_install"] is False:
            report["state"] = "ALREADY_DISABLED_READ_ONLY"
            return report
        # The exclusive receipt is durable before the only possible state write.
        write_new(out / "pre-write-admission.json", {"source_revision": source_revision,
            "domain": DOMAIN, "settings_sha256": expected_hash,
            "site_sha256": digest(site_id), "payload": {"auto_install": False}})
        report["put_attempts"] = 1
        report["mutation_outcome"] = "UNKNOWN_AFTER_SUBMISSION_ATTEMPT"
        update = result_object(client.request("PUT", path, {"auto_install": False}))
        report["mutation_outcome"] = "PROVIDER_SUCCESS_RESPONSE_OBSERVED; FINAL_STATE_UNVERIFIED"
        expected_after = copy.deepcopy(last)
        expected_after["auto_install"] = False
        need(digest(update) == digest(expected_after), "Mutation response changed other settings")
        after = result_object(client.request("GET", path))
        need(digest(after) == digest(expected_after), "Readback did not preserve all other settings")
        report.update({"state": "APPLIED_SETTINGS_READBACK_VERIFIED",
            "mutation_outcome": "VERIFIED_ONLY_AUTO_INSTALL_DISABLED",
            "after_settings_sha256": digest(after), "after_settings": safe_settings(after),
            "only_auto_install_changed": True})
        return report
    except Refused as exc:
        report["error"] = str(exc)
        if (report["put_attempts"] and client.events[-1].get("method") == "PUT"
                and type(client.events[-1].get("status")) is int
                and 400 <= client.events[-1]["status"] < 500):
            report["mutation_outcome"] = "PROVIDER_REJECTED_WRITE_HTTP_4XX"
        return report
    finally:
        if report["put_attempts"]:
            write_new(out / "mutation-unsigned-dsse.json", mutation_envelope(report))
        write_new(out / "receipt.json", report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("audit", "apply"), default="audit")
    parser.add_argument("--expected-settings-sha256", default="")
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=False)
    source = os.environ.get("GITHUB_SHA", "UNAVAILABLE")
    try:
        client = Client(os.environ.get("CLOUDFLARE_API_TOKEN", "").strip())
        result = operate(client, args.mode, args.expected_settings_sha256,
                         args.output_directory, source)
    except Refused as exc:
        result = {"schema": "szl.cloudflare.proof-rum/v1", "domain": DOMAIN,
                  "state": "FAILED", "mode": args.mode, "source_revision": source,
                  "put_attempts": 0, "mutation_outcome": "NOT_ATTEMPTED",
                  "token_recorded": False, "error": str(exc)}
        write_new(args.output_directory / "receipt.json", result)
    print(json.dumps({"state": result["state"], "domain": DOMAIN,
                      "put_attempts": result["put_attempts"],
                      "before_settings_sha256": result.get("before_settings_sha256")}))
    return int(result["state"] == "FAILED")


if __name__ == "__main__":
    raise SystemExit(main())
