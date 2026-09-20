#!/usr/bin/env python3
"""Python PARC evaluator matching policy/cedar/intent-auth.cedar.

Cedar files remain the typed contract. This engine is the offline twin so
intent decisions can be tested without a Cedar CLI binary.
Forbids override permits. Missing permit is BLOCK.

Accepts both:
- inline principal/resource attributes (unit tests, bind_anatomy)
- a separate entities store keyed by principal/resource id (CLI)
"""
from __future__ import annotations

import argparse
import json
from typing import Any

READ_ACTIONS = {"ReadResource", "InvokeTool", "ExportEvidence"}
PRIVILEGED_ACTIONS = {
    "WriteResource",
    "DeployArtifact",
    "ApproveDecision",
    "SignReceipt",
    "AdministerPolicy",
}
KNOWN_ACTIONS = READ_ACTIONS | PRIVILEGED_ACTIONS


def _id_of(node: Any) -> str:
    if isinstance(node, dict):
        return str(node.get("id") or "")
    return str(node or "")


def _attrs(entity: Any, store: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(entity, dict):
        if store and entity in store:
            found = store[entity]
            return found if isinstance(found, dict) else {}
        return {}
    if "attrs" in entity and isinstance(entity["attrs"], dict):
        merged = dict(entity["attrs"])
        for key in ("tenantId", "assurance", "disabled", "requiredAssurance", "maxRisk", "allowedPurposes", "allowedEffects"):
            if key in entity and key not in merged:
                merged[key] = entity[key]
        return merged
    if store:
        ident = _id_of(entity)
        if ident in store and isinstance(store[ident], dict):
            return store[ident]
    return entity


def authorize(request: dict[str, Any], entities: dict[str, Any] | None = None) -> dict[str, Any]:
    entities = entities or {}
    principals = entities.get("principals") if isinstance(entities.get("principals"), dict) else {}
    resources = entities.get("resources") if isinstance(entities.get("resources"), dict) else {}
    principal = _attrs(request.get("principal") or {}, principals)
    resource = _attrs(request.get("resource") or {}, resources)
    context = request.get("context") if isinstance(request.get("context"), dict) else {}
    action = _id_of(request.get("action"))

    forbids: list[str] = []
    if not principal:
        forbids.append("unknown principal")
    if not resource:
        forbids.append("unknown resource")
    if action not in KNOWN_ACTIONS:
        forbids.append("unknown action")
    if principal.get("disabled") is True:
        forbids.append("principal is disabled")
    if principal and resource and str(principal.get("tenantId", "")) != str(resource.get("tenantId", "")):
        forbids.append("principal.tenantId != resource.tenantId")
    try:
        risk = int(context.get("riskScore", 0))
    except (TypeError, ValueError):
        risk = 0
        forbids.append("riskScore is not an integer")
    try:
        max_risk = int(resource.get("maxRisk", 0)) if resource else 0
    except (TypeError, ValueError):
        max_risk = 0
        forbids.append("maxRisk is not an integer")
    if resource and risk > max_risk:
        forbids.append("context.riskScore exceeds resource.maxRisk")

    purposes = set(resource.get("allowedPurposes") or [])
    effects = set(resource.get("allowedEffects") or [])
    if resource and context.get("purpose") not in purposes:
        forbids.append("purpose is not in resource.allowedPurposes")
    if resource and context.get("intendedEffect") not in effects:
        forbids.append("intendedEffect is not in resource.allowedEffects")
    if action in PRIVILEGED_ACTIONS and str(context.get("networkZone") or "") == "untrusted":
        forbids.append("privileged action from untrusted networkZone")

    if forbids:
        return {
            "outcome": "BLOCK",
            "reasons": ["cedar forbid matched"],
            "deny": forbids,
            "forbids": forbids,
            "review": [],
            "policy": "cedar.intent.v1",
            "engine": "python-twin",
            "evaluator": "python-parc",
            "action": action,
            "principal": _id_of(request.get("principal")),
            "resource": _id_of(request.get("resource")),
            "disclosure": "Default deny. This evaluator is not the Cedar CLI.",
        }

    try:
        assurance = int(principal.get("assurance", 0))
        required = int(resource.get("requiredAssurance", 0))
    except (TypeError, ValueError):
        return {
            "outcome": "BLOCK",
            "reasons": ["assurance fields are not integers"],
            "deny": ["assurance fields are not integers"],
            "forbids": [],
            "review": [],
            "policy": "cedar.intent.v1",
            "engine": "python-twin",
            "evaluator": "python-parc",
            "action": action,
            "principal": _id_of(request.get("principal")),
            "resource": _id_of(request.get("resource")),
            "disclosure": "Default deny. This evaluator is not the Cedar CLI.",
        }

    if assurance < required:
        return {
            "outcome": "BLOCK",
            "reasons": ["no permit matched; cedar denies by default", "assurance below requiredAssurance"],
            "deny": ["assurance below requiredAssurance"],
            "forbids": [],
            "review": [],
            "policy": "cedar.intent.v1",
            "engine": "python-twin",
            "evaluator": "python-parc",
            "action": action,
            "principal": _id_of(request.get("principal")),
            "resource": _id_of(request.get("resource")),
            "disclosure": "Default deny. This evaluator is not the Cedar CLI.",
        }

    if action in PRIVILEGED_ACTIONS:
        missing: list[str] = []
        if not context.get("humanApproval"):
            missing.append("humanApproval required")
        if not context.get("mfa"):
            missing.append("mfa required")
        if not str(context.get("evidenceDigest") or ""):
            missing.append("evidenceDigest required")
        if missing:
            return {
                "outcome": "BLOCK",
                "reasons": ["privileged permit did not match", *missing],
                "deny": ["high-risk action missing approval, MFA, or evidenceDigest", *missing],
                "forbids": [],
                "review": [],
                "policy": "cedar.intent.v1",
                "engine": "python-twin",
                "evaluator": "python-parc",
                "action": action,
                "principal": _id_of(request.get("principal")),
                "resource": _id_of(request.get("resource")),
                "disclosure": "Default deny. This evaluator is not the Cedar CLI.",
            }

    return {
        "outcome": "ALLOW",
        "reasons": ["cedar permit matched"],
        "deny": [],
        "forbids": [],
        "review": [],
        "policy": "cedar.intent.v1",
        "engine": "python-twin",
        "evaluator": "python-parc",
        "action": action,
        "principal": _id_of(request.get("principal")),
        "resource": _id_of(request.get("resource")),
        "disclosure": "Default deny. This evaluator is not the Cedar CLI.",
    }


def evaluate(request: dict[str, Any], entities: dict[str, Any] | None = None) -> dict[str, Any]:
    return authorize(request, entities)


def main() -> None:
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--request")
    parser.add_argument("--entities")
    args = parser.parse_args()
    if args.request:
        with open(args.request, encoding="utf-8") as handle:
            request = json.load(handle)
        entities: dict[str, Any] = {}
        if args.entities:
            with open(args.entities, encoding="utf-8") as handle:
                entities = json.load(handle)
        json.dump(authorize(request, entities), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    payload = json.load(sys.stdin)
    json.dump(authorize(payload), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
