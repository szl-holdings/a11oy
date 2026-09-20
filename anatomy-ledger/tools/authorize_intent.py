#!/usr/bin/env python3
"""Fail-closed PARC evaluator matching policy/cedar/intent-auth.cedar."""
from __future__ import annotations

import argparse
import json
from typing import Any

LOW_ACTIONS = {"ReadResource", "InvokeTool", "ExportEvidence"}
HIGH_ACTIONS = {
    "WriteResource",
    "DeployArtifact",
    "ApproveDecision",
    "SignReceipt",
    "AdministerPolicy",
}
KNOWN_ACTIONS = LOW_ACTIONS | HIGH_ACTIONS


def _id_of(node: Any) -> str:
    if isinstance(node, dict):
        return str(node.get("id") or "")
    return str(node or "")


def evaluate(request: dict[str, Any], entities: dict[str, Any] | None = None) -> dict[str, Any]:
    entities = entities or {}
    principal_id = _id_of(request.get("principal"))
    action_id = _id_of(request.get("action"))
    resource_id = _id_of(request.get("resource"))
    context = request.get("context") if isinstance(request.get("context"), dict) else {}
    principal = entities.get("principals", {}).get(principal_id, {})
    resource = entities.get("resources", {}).get(resource_id, {})
    deny: list[str] = []
    if not principal:
        deny.append("unknown principal")
    if not resource:
        deny.append("unknown resource")
    if action_id not in KNOWN_ACTIONS:
        deny.append("unknown action")
    if principal.get("disabled") is True:
        deny.append("principal is disabled")
    if principal and resource and principal.get("tenantId") != resource.get("tenantId"):
        deny.append("tenant mismatch")
    try:
        risk = int(context.get("riskScore", 10**9))
    except (TypeError, ValueError):
        risk = 10**9
        deny.append("riskScore is not an integer")
    if resource and risk > int(resource.get("maxRisk", -1)):
        deny.append("risk exceeds resource.maxRisk")
    purpose = str(context.get("purpose") or "")
    effect = str(context.get("intendedEffect") or "")
    if resource and purpose not in set(resource.get("allowedPurposes") or []):
        deny.append("purpose is not allowed")
    if resource and effect not in set(resource.get("allowedEffects") or []):
        deny.append("intendedEffect is not allowed")
    assurance_ok = int(principal.get("assurance", -1)) >= int(
        resource.get("requiredAssurance", 10**9)
    )
    high_ok = (
        context.get("humanApproval") is True
        and context.get("mfa") is True
        and str(context.get("evidenceDigest") or "") != ""
    )
    permit = (
        not deny
        and assurance_ok
        and ((action_id in LOW_ACTIONS) or (action_id in HIGH_ACTIONS and high_ok))
    )
    if not permit and not deny:
        if not assurance_ok:
            deny.append("assurance below requiredAssurance")
        elif action_id in HIGH_ACTIONS and not high_ok:
            deny.append("high-risk action missing approval, MFA, or evidenceDigest")
        else:
            deny.append("no permit policy matched")
    return {
        "outcome": "ALLOW" if permit and not deny else "BLOCK",
        "deny": deny,
        "review": [],
        "action": action_id,
        "principal": principal_id,
        "resource": resource_id,
        "evaluator": "python-parc",
        "disclosure": "Default deny. This evaluator is not the Cedar CLI.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--entities", required=True)
    args = parser.parse_args()
    with open(args.request, encoding="utf-8") as handle:
        request = json.load(handle)
    with open(args.entities, encoding="utf-8") as handle:
        entities = json.load(handle)
    print(json.dumps(evaluate(request, entities), indent=2))


if __name__ == "__main__":
    main()
