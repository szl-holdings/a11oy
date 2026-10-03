#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Audit or update one source-bound a11oy.net response-header rule.

This supply-chain maintenance controller reuses the proof RUM admission and
transport bounds. It is not an agent execution sandbox. Comparison before a
write is not atomic provider CAS. No entrypoint creation, whole-ruleset
replacement, DNS/origin/RUM change, retry, redirect or silent rollback exists.
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

try:
    from scripts import proof_cloudflare_rum as common
except ModuleNotFoundError:  # Direct script invocation from the native workflow.
    import proof_cloudflare_rum as common

DOMAIN = "a11oy.net"
PHASE = "http_response_headers_transform"
RULE_REF = "a11oy_net_canonical_security_headers"
PROOF_REVISION = "03cca1dc1fe40cfa6642922881103c6040de8c79"
HEADERS_SHA256 = "8793a1bdfbbd87d0da962efc2bb2a23367fb1415d64463691bbe88dd3e347b4c"
POLICY = Path(__file__).resolve().parents[1] / "ops" / "proof-security-headers.json"
HEADERS = frozenset({"content-security-policy", "strict-transport-security",
    "referrer-policy", "x-content-type-options", "x-frame-options",
    "permissions-policy", "cross-origin-opener-policy", "cross-origin-resource-policy"})
ID = r"[a-f0-9]{32}"
Refused, need = common.Refused, common.need
canonical, digest, identifier = common.canonical, common.digest, common.identifier
write_new = common.write_new


def load_policy(path: Path = POLICY) -> dict[str, Any]:
    raw = path.read_bytes()
    need(len(raw) <= 32_768, "Policy exceeds byte bound")
    return validate_policy(common.strict_json(raw))


def validate_policy(value: Any) -> dict[str, Any]:
    need(isinstance(value, dict) and set(value) == {"SPDX-License-Identifier", "copyright", "schema", "domain",
         "source_repository", "source_revision", "source_path", "source_sha256",
         "source_text", "rule"}, "Unexpected policy structure")
    need(value["SPDX-License-Identifier"] == "Apache-2.0"
         and value["copyright"] == "(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173",
         "Policy license metadata differs")
    need(value["schema"] == "szl.cloudflare.proof-headers-policy/v1"
         and value["domain"] == DOMAIN
         and value["source_repository"] == "szl-holdings/a11oy-net"
         and value["source_revision"] == PROOF_REVISION
         and value["source_path"] == "_headers"
         and value["source_sha256"] == HEADERS_SHA256, "Policy source binding differs")
    text = value["source_text"]
    need(isinstance(text, str) and hashlib.sha256(text.encode("utf-8")).hexdigest()
         == HEADERS_SHA256, "Canonical header source bytes differ")
    lines = text.splitlines()
    need(lines and lines[0] == "/*" and len(lines) == 9, "Unexpected canonical header layout")
    parsed = {}
    for line in lines[1:]:
        need(line.startswith("  ") and ":" in line, "Malformed canonical header")
        name, content = line.strip().split(":", 1)
        name, content = name.lower(), content.strip()
        need(name not in parsed and name in HEADERS and content
             and "\r" not in content and "\n" not in content, "Invalid canonical header")
        parsed[name] = {"operation": "set", "value": content}
    rule = value["rule"]
    need(isinstance(rule, dict) and set(rule) == {"ref", "description", "expression",
         "action", "action_parameters", "enabled"}, "Unexpected desired rule fields")
    need(rule["ref"] == RULE_REF and rule["expression"] == '(http.host eq "a11oy.net")'
         and rule["action"] == "rewrite" and rule["enabled"] is True
         and isinstance(rule["description"], str) and PROOF_REVISION in rule["description"]
         and rule["action_parameters"] == {"headers": parsed} and set(parsed) == HEADERS,
         "Desired rule differs from the exact canonical policy")
    return value


def allowed_request(method: str, path: str) -> bool:
    if method == "GET":
        return (path == "/zones?name=a11oy.net&status=active&per_page=50"
                or re.fullmatch(rf"/accounts/{ID}", path) is not None
                or re.fullmatch(rf"/zones/{ID}", path) is not None
                or re.fullmatch(rf"/zones/{ID}/rulesets/phases/{PHASE}/entrypoint", path) is not None)
    if method == "POST":
        return re.fullmatch(rf"/zones/{ID}/rulesets/{ID}/rules", path) is not None
    if method == "PATCH":
        return re.fullmatch(rf"/zones/{ID}/rulesets/{ID}/rules/{ID}", path) is not None
    return False


class Client(common.Client):
    def __init__(self, bearer: str) -> None:
        # Reject the raw environment value before any header construction. Some
        # HTTP validators include the offending header value in ValueError.
        need(isinstance(bearer, str) and all(33 <= ord(char) <= 126 for char in bearer),
             "Provider authentication contains unsupported characters")
        super().__init__(bearer)

    def request(self, method: str, path: str, payload: Any = None) -> dict[str, Any]:
        need(allowed_request(method, path), "Unsupported proof-header provider request")
        remaining = self.deadline - time.monotonic()
        need(remaining > 0, "Provider observation deadline exceeded")
        headers = {"Authorization": f"Bearer {self.bearer}", "Accept": "application/json",
                   "User-Agent": "SZL-Proof-Headers/1.0"}
        body = None
        if payload is not None:
            body = canonical(payload)
            need(len(body) <= 32_768, "Mutation body exceeds byte bound")
            headers["Content-Type"] = "application/json"
        event = {"method": method, "path_sha256": digest(path), "status": None,
                 "body_sha256": None, "provider_error_codes": [], "retried": False}
        self.events.append(event)
        try:
            request = urllib.request.Request(common.API + path, data=body, headers=headers, method=method)
            with self.opener.open(request, timeout=min(common.REQUEST_TIMEOUT, remaining)) as response:
                event["status"] = response.status
                raw = self.read_bounded(response)
        except urllib.error.HTTPError as exc:
            event["status"] = exc.code
            try:
                raw = self.read_bounded(exc)
                event["body_sha256"] = hashlib.sha256(raw).hexdigest()
                error = common.strict_json(raw)
                if isinstance(error, dict) and isinstance(error.get("errors"), list):
                    event["provider_error_codes"] = [item["code"] for item in error["errors"]
                        if isinstance(item, dict) and type(item.get("code")) is int][:20]
            except (Refused, OSError):
                event["error_body_unavailable_or_exceeded_bounds"] = True
            raise Refused(f"Provider HTTP {exc.code}; inspect numeric codes in receipt") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise Refused("Provider transport failed; mutation outcome may be unknown") from exc
        except ValueError:
            # Suppress the raw exception chain as well as its message; it may
            # include authentication material rejected by an HTTP validator.
            raise Refused("Provider transport input was rejected; mutation outcome may be unknown") from None
        need(event["status"] == 200 or (method != "GET" and event["status"] == 201),
             "Unexpected provider HTTP status")
        event["body_sha256"] = hashlib.sha256(raw).hexdigest()
        value = common.strict_json(raw)
        need(isinstance(value, dict) and value.get("success") is True,
             "Provider success envelope missing or false")
        return value


def admit_ruleset(value: Any, expected_id: str | None = None) -> tuple[str, list[dict[str, Any]]]:
    need(isinstance(value, dict) and value.get("kind") == "zone" and value.get("phase") == PHASE,
         "The existing response-header zone entrypoint is unavailable or differs")
    ruleset_id = identifier(value.get("id"))
    need(expected_id is None or ruleset_id == expected_id, "Entrypoint identity changed")
    rules = value.get("rules")
    need(isinstance(rules, list) and len(rules) <= 100, "Rules list is missing or excessive")
    ids = set()
    for rule in rules:
        need(isinstance(rule, dict), "Malformed provider rule")
        rule_id = identifier(rule.get("id"))
        need(rule_id not in ids, "Duplicate provider rule identity")
        ids.add(rule_id)
    return ruleset_id, rules


def rule_definition(rule: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in rule.items() if key not in {"id", "version", "last_updated"}}


def choose_rule(rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    selected = None
    for rule in rules:
        parameters = rule.get("action_parameters", {})
        need(isinstance(parameters, dict), "Malformed rule action parameters")
        headers = parameters.get("headers", {})
        need(isinstance(headers, dict) and all(isinstance(name, str) for name in headers),
             "Malformed response header map")
        names = {name.lower() for name in headers}
        if rule.get("ref") != RULE_REF:
            need(not (names & HEADERS), "Another rule writes protected headers; operator review required")
            continue
        need(selected is None, "Managed rule ref is ambiguous")
        need(set(rule) <= {"id", "version", "last_updated", "ref", "description", "expression",
             "action", "action_parameters", "enabled"}
             and rule.get("expression") == '(http.host eq "a11oy.net")'
             and rule.get("action") == "rewrite" and type(rule.get("enabled")) is bool
             and set(parameters) == {"headers"} and names <= HEADERS and len(names) == len(headers),
             "Managed rule has mixed fields or another domain scope")
        for header in headers.values():
            need(isinstance(header, dict) and set(header) == {"operation", "value"}
                 and header["operation"] == "set" and isinstance(header["value"], str),
                 "Managed rule has a mixed header operation")
        selected = rule
    return selected


def safe_settings(value: dict[str, Any]) -> dict[str, Any]:
    return {"ruleset_sha256": digest(value), "phase": PHASE, "kind": "zone",
            "rules": [{"id_sha256": digest(rule["id"]), "definition_sha256": digest(rule),
                       "is_managed_ref": rule.get("ref") == RULE_REF}
                      for rule in value["rules"]]}


def preservation(before: dict[str, Any], after: dict[str, Any], desired: dict[str, Any],
                 previous: dict[str, Any] | None) -> None:
    admit_ruleset(after, before["id"])
    old_rules = before["rules"]
    new_rules = after["rules"]
    target = choose_rule(new_rules)
    need(target is not None and rule_definition(target) == desired, "Managed rule readback differs")
    expected_count = len(old_rules) + int(previous is None)
    need(len(new_rules) == expected_count, "Rule cardinality changed unexpectedly")
    old_other = [rule for rule in old_rules if rule is not previous]
    new_other = [rule for rule in new_rules if rule.get("ref") != RULE_REF]
    need(old_other == new_other, "Other rules or their order changed")
    old_position = next((i for i, rule in enumerate(old_rules) if rule is previous), len(old_rules))
    need(new_rules[old_position] is target, "Managed rule position changed")
    need(previous is None or target["id"] == previous["id"], "Managed rule identity changed")
    old_fields = {k: v for k, v in before.items() if k not in {"rules", "version", "last_updated"}}
    new_fields = {k: v for k, v in after.items() if k not in {"rules", "version", "last_updated"}}
    need(old_fields == new_fields, "Entrypoint settings changed outside the managed rule")


def mutation_envelope(report: dict[str, Any], desired: dict[str, Any]) -> dict[str, Any]:
    previous = digest({"source_revision": report["source_revision"], "domain": DOMAIN,
                       "before_settings_sha256": report.get("before_settings_sha256")})
    chain = []
    for event in report["provider_events"]:
        link = {"previous_event_sha256": previous, "event": event}
        previous = digest(link)
        chain.append(dict(link, event_sha256=previous))
    payload = {"schema": "szl.cloudflare.proof-headers-mutation/v1", "domain": DOMAIN,
        "source_revision": report["source_revision"], "proof_source_revision": PROOF_REVISION,
        "before_settings_sha256": report.get("before_settings_sha256"),
        "operation": report.get("operation"), "desired_rule": desired,
        "write_attempts": report["write_attempts"], "state": report["state"],
        "mutation_outcome": report["mutation_outcome"], "provider_event_chain": chain,
        "previous_event_sha256": previous}
    raw = canonical(payload)
    return {"payloadType": "application/vnd.szl.cloudflare.proof-headers-mutation+json",
        "payload": base64.b64encode(raw).decode("ascii"), "signatures": [],
        "signature_status": "UNSIGNED", "payload_sha256": hashlib.sha256(raw).hexdigest(),
        "identity_or_third_party_authenticity_verified": False}


def operate(client: Client, mode: str, expected_hash: str, out: Path,
            source_revision: str, policy: dict[str, Any]) -> dict[str, Any]:
    need(mode in {"audit", "apply"}, "Unsupported operation mode")
    need(re.fullmatch(r"[a-f0-9]{40}", source_revision) is not None, "Exact controller source required")
    need(mode == "audit" or common.HEX_HASH.fullmatch(expected_hash) is not None,
         "Apply requires the prior exact settings SHA-256")
    policy = validate_policy(policy)
    desired = policy["rule"]
    report = {"schema": "szl.cloudflare.proof-headers/v1", "domain": DOMAIN, "mode": mode,
        "observed_at": datetime.now(timezone.utc).isoformat(), "source_revision": source_revision,
        "proof_source_revision": PROOF_REVISION, "proof_source_binding": "IMMUTABLE_CACHED_SOURCE",
        "proof_current_protected_head": "UNKNOWN", "policy_sha256": digest(policy),
        "state": "BLOCKED", "write_attempts": 0, "mutation_outcome": "NOT_ATTEMPTED",
        "provider_events": client.events, "token_recorded": False,
        "provider_atomic_compare_and_swap": "UNKNOWN", "admission": "COMPARE_BEFORE_WRITE",
        "public_eight_header_acceptance": "NOT_CHECKED"}
    try:
        zones = client.request("GET", "/zones?name=a11oy.net&status=active&per_page=50").get("result")
        need(isinstance(zones, list) and len(zones) == 1 and isinstance(zones[0], dict),
             "Exact active proof zone missing or ambiguous")
        zone_id, account_id = common.admit_zone(zones[0])
        account = common.result_object(client.request("GET", f"/accounts/{account_id}"))
        need(account.get("id") == account_id, "Account detail differs from proof zone binding")
        path = f"/zones/{zone_id}/rulesets/phases/{PHASE}/entrypoint"
        before = common.result_object(client.request("GET", path))
        ruleset_id, rules = admit_ruleset(before)
        choose_rule(rules)
        settings_hash = digest(before)
        report.update({"before_settings_sha256": settings_hash, "before_settings": safe_settings(before),
                       "zone_sha256": digest(zone_id), "account_sha256": digest(account_id),
                       "ruleset_sha256": digest(ruleset_id)})
        write_new(out / "before-settings.json", report["before_settings"])
        if mode == "audit":
            report["state"] = "AUDITED_READ_ONLY"
            return report
        need(settings_hash == expected_hash, "Current ruleset differs from prior audit")
        zone = common.result_object(client.request("GET", f"/zones/{zone_id}"))
        common.admit_zone(zone, (zone_id, account_id))
        last = common.result_object(client.request("GET", path))
        admit_ruleset(last, ruleset_id)
        previous = choose_rule(last["rules"])
        need(digest(last) == expected_hash, "Ruleset changed immediately before mutation")
        if previous is not None and rule_definition(previous) == desired:
            report["state"] = "ALREADY_EXACT_READ_ONLY"
            return report
        method = "PATCH" if previous is not None else "POST"
        target_path = f"/zones/{zone_id}/rulesets/{ruleset_id}/rules"
        if previous is not None:
            target_path += f"/{identifier(previous['id'])}"
        report["operation"] = "UPDATE_ONE_RULE" if previous is not None else "APPEND_ONE_RULE"
        write_new(out / "pre-write-admission.json", {"source_revision": source_revision,
            "proof_source_revision": PROOF_REVISION, "domain": DOMAIN,
            "settings_sha256": expected_hash, "rule_sha256": digest(desired),
            "method": method, "target_path_sha256": digest(target_path),
            "admission": "COMPARE_BEFORE_WRITE", "provider_atomic_compare_and_swap": "UNKNOWN"})
        report["write_attempts"] = 1
        report["mutation_outcome"] = "UNKNOWN_AFTER_SUBMISSION_ATTEMPT"
        update = common.result_object(client.request(method, target_path, copy.deepcopy(desired)))
        report["mutation_outcome"] = "PROVIDER_RESPONSE_OBSERVED_FINAL_STATE_UNVERIFIED"
        preservation(last, update, desired, previous)
        after = common.result_object(client.request("GET", path))
        preservation(last, after, desired, previous)
        report.update({"state": "APPLIED_SETTINGS_READBACK_VERIFIED",
            "mutation_outcome": "VERIFIED_ONE_RULE_AND_OTHER_RULE_PRESERVATION",
            "after_settings_sha256": digest(after), "after_settings": safe_settings(after),
            "other_rules_preserved": True})
        return report
    except (Refused, OSError) as exc:
        report["error"] = str(exc) if isinstance(exc, Refused) else "Artifact durability unavailable"
        if (report["write_attempts"] and client.events[-1].get("method") in {"POST", "PATCH"}
                and type(client.events[-1].get("status")) is int
                and 400 <= client.events[-1]["status"] < 500):
            report["mutation_outcome"] = "PROVIDER_REJECTED_WRITE_HTTP_4XX"
        return report
    finally:
        # A post-submission artifact failure must never become a zero-write
        # preflight receipt. Retain operation history even when durability fails.
        try:
            if report["write_attempts"]:
                write_new(out / "mutation-unsigned-dsse.json", mutation_envelope(report, desired))
        except OSError:
            report.update({"state": "BLOCKED", "artifact_error": "Mutation envelope durability unavailable"})
        try:
            write_new(out / "receipt.json", report)
        except OSError:
            report.update({"state": "BLOCKED", "artifact_error": "Receipt durability unavailable"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("audit", "apply"), default="audit")
    parser.add_argument("--expected-settings-sha256", default="")
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=False)
    source = os.environ.get("GITHUB_SHA", "UNAVAILABLE")
    try:
        policy = load_policy()
        need(os.environ.get("GITHUB_REPOSITORY") == "szl-holdings/a11oy"
             and os.environ.get("GITHUB_REF") == "refs/heads/main",
             "Only the canonical protected-main workflow may observe or apply provider state")
        client = Client(os.environ.get("CLOUDFLARE_API_TOKEN", ""))
    except (Refused, OSError) as exc:
        report = {"schema": "szl.cloudflare.proof-headers/v1", "domain": DOMAIN,
            "source_revision": source, "state": "BLOCKED", "mode": args.mode,
            "write_attempts": 0, "mutation_outcome": "NOT_ATTEMPTED", "token_recorded": False,
            "error": str(exc) if isinstance(exc, Refused) else "Local policy or artifact I/O unavailable"}
        write_new(args.output_directory / "receipt.json", report)
    else:
        report = operate(client, args.mode, args.expected_settings_sha256,
                         args.output_directory, source, policy)
    print(json.dumps({key: report.get(key) for key in
        ("state", "domain", "write_attempts", "before_settings_sha256")}))
    return int(report["state"] == "BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
