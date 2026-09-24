#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Strict, advisory Python evaluation of the Cedar intent contract.

This function does not execute Cedar or authenticate caller-supplied identities,
attributes, approvals, or evidence. An ALLOW is a local policy assessment only.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

READ_ACTIONS = {"ReadResource", "ExportEvidence"}
PRIVILEGED_ACTIONS = {
    "InvokeTool",
    "WriteResource",
    "DeployArtifact",
    "ApproveDecision",
    "SignReceipt",
    "AdministerPolicy",
}
KNOWN_ACTIONS = READ_ACTIONS | PRIVILEGED_ACTIONS
TRUSTED_ZONES = {"command-surface", "trusted-ci", "trusted"}
SHA256_RE = re.compile(r"(?:sha256:)?[0-9a-fA-F]{64}\Z")
MAX_LONG = 2**63 - 1
PRINCIPAL_TYPE = "A11oy::WorkloadIdentity"
RESOURCE_TYPE = "A11oy::ProtectedResource"
PRINCIPAL_FIELDS = {
    "kind": "nonempty",
    "tenantId": "nonempty",
    "assurance": "long",
    "roles": "strings",
    "disabled": "bool",
}
RESOURCE_FIELDS = {
    "kind": "nonempty",
    "tenantId": "nonempty",
    "classification": "long",
    "requiredAssurance": "long",
    "maxRisk": "long",
    "allowedPurposes": "strings",
    "allowedEffects": "strings",
    "requiresApproval": "bool",
}
CONTEXT_FIELDS = {
    "requestId": "string",
    "sessionId": "string",
    "purpose": "nonempty",
    "intendedEffect": "nonempty",
    "riskScore": "long",
    "humanApproval": "bool",
    "mfa": "bool",
    "networkZone": "nonempty",
    "evidenceDigest": "string",
    "traceId": "string",
    "timestamp": "string",
}


def _nonempty(value: Any) -> bool:
    return type(value) is str and bool(value.strip())


def _id_of(node: Any) -> str:
    return (
        node.get("id", "")
        if isinstance(node, dict) and type(node.get("id")) is str
        else ""
    )


def _validate_fields(
    value: Any, fields: dict[str, str], name: str, deny: list[str]
) -> bool:
    start = len(deny)
    if not isinstance(value, dict):
        deny.append(f"{name} must be an object")
        return False
    for field, kind in fields.items():
        item = value.get(field)
        valid = {
            "string": lambda: type(item) is str,
            "nonempty": lambda: _nonempty(item),
            "bool": lambda: type(item) is bool,
            "long": lambda: type(item) is int and 0 <= item <= MAX_LONG,
            "strings": lambda: (
                type(item) is list and all(_nonempty(entry) for entry in item)
            ),
        }[kind]()
        if not valid:
            deny.append(f"{name}.{field} must be {kind}")
    if set(value) - set(fields):
        deny.append(f"{name} contains unknown attributes")
    return len(deny) == start


def _stores(entities: Any, deny: list[str]) -> tuple[dict, dict]:
    if entities is None:
        return {}, {}
    if isinstance(entities, dict):
        if set(entities) - {"principals", "resources"}:
            deny.append("entities contains unknown collections")
        principals, resources = (
            entities.get("principals", {}),
            entities.get("resources", {}),
        )
        if not isinstance(principals, dict) or not isinstance(resources, dict):
            deny.append("entity collections must be objects")
            return {}, {}
        return principals, resources
    if isinstance(entities, list):
        stores: dict[str, dict] = {PRINCIPAL_TYPE: {}, RESOURCE_TYPE: {}}
        for entity in entities:
            uid = entity.get("uid") if isinstance(entity, dict) else None
            if (
                not isinstance(uid, dict)
                or type(uid.get("type")) is not str
                or uid.get("type") not in stores
                or not _nonempty(uid.get("id"))
            ):
                deny.append("entities contains an invalid typed identity")
                continue
            store = stores[uid["type"]]
            if uid["id"] in store:
                deny.append("entities contains a duplicate identity")
            if entity.get("parents") != []:
                deny.append(
                    "entity parents are not supported by this advisory evaluator"
                )
            store[uid["id"]] = entity.get("attrs")
        return stores[PRINCIPAL_TYPE], stores[RESOURCE_TYPE]
    deny.append("entities must be an object or Cedar entity list")
    return {}, {}


def _entity(
    node: Any,
    expected_type: str,
    store: dict,
    use_store: bool,
    fields: dict[str, str],
    name: str,
    deny: list[str],
) -> dict:
    if not isinstance(node, dict):
        deny.append(f"{name} must be a typed identity object")
        return {}
    if node.get("type") != expected_type or not _nonempty(node.get("id")):
        deny.append(f"{name} has an unknown type or empty identity")
    if use_store:
        attrs = store.get(_id_of(node))
        if attrs is None:
            deny.append(f"unknown {name}")
        if "attrs" in node and node["attrs"] != attrs:
            deny.append(f"{name} inline attributes disagree with entity store")
    else:
        attrs = node.get("attrs")
    if not _validate_fields(attrs, fields, name, deny):
        return {}
    for key in set(node) - {"id", "type", "attrs"}:
        # Compatibility aliases may repeat attributes, but may never override them.
        if (
            key not in fields
            or type(node[key]) is not type(attrs.get(key))
            or node[key] != attrs.get(key)
        ):
            deny.append(f"{name}.{key} conflicts with its attributes")
    return attrs


def _result(request: dict, deny: list[str]) -> dict[str, Any]:
    return {
        "outcome": "BLOCK" if deny else "ALLOW",
        "reasons": ["default deny: invalid input or policy condition failed"]
        if deny
        else ["local advisory policy conditions satisfied"],
        "deny": deny,
        "forbids": deny,
        "review": [],
        "policy": "cedar.intent.v1",
        "engine": "python-advisory",
        "evaluator": "python-parc",
        "action": _id_of(request.get("action")),
        "principal": _id_of(request.get("principal")),
        "resource": _id_of(request.get("resource")),
        "evaluationOnly": True,
        "executable": False,
        "policyEligible": not deny,
        "cedarExecuted": False,
        "identityAuthenticated": False,
        "disclosure": "Python advisory evaluation only. Caller attributes and approvals are untrusted; no execution authority is granted.",
    }


def authorize(request: Any, entities: Any = None) -> dict[str, Any]:
    deny: list[str] = []
    if not isinstance(request, dict):
        return _result({}, ["request must be an object"])
    if set(request) - {"principal", "action", "resource", "context"}:
        deny.append("request contains unknown fields")
    principals, resources = _stores(entities, deny)
    principal = _entity(
        request.get("principal"),
        PRINCIPAL_TYPE,
        principals,
        entities is not None,
        PRINCIPAL_FIELDS,
        "principal",
        deny,
    )
    resource = _entity(
        request.get("resource"),
        RESOURCE_TYPE,
        resources,
        entities is not None,
        RESOURCE_FIELDS,
        "resource",
        deny,
    )
    context = request.get("context")
    _validate_fields(context, CONTEXT_FIELDS, "context", deny)
    action_node = request.get("action")
    action = _id_of(action_node)
    if (
        not isinstance(action_node, dict)
        or action_node.get("type") != "A11oy::Action"
        or set(action_node) != {"id", "type"}
        or action not in KNOWN_ACTIONS
    ):
        deny.append("unknown action or action type")
    if deny:
        return _result(request, deny)
    if principal["disabled"]:
        deny.append("principal is disabled")
    if principal["tenantId"] != resource["tenantId"]:
        deny.append("principal.tenantId != resource.tenantId")
    if context["riskScore"] > resource["maxRisk"]:
        deny.append("context.riskScore exceeds resource.maxRisk")
    if principal["assurance"] < resource["requiredAssurance"]:
        deny.append("assurance below requiredAssurance")
    if context["purpose"] not in resource["allowedPurposes"]:
        deny.append("purpose is not in resource.allowedPurposes")
    if context["intendedEffect"] not in resource["allowedEffects"]:
        deny.append("intendedEffect is not in resource.allowedEffects")
    if context["evidenceDigest"] and not SHA256_RE.fullmatch(context["evidenceDigest"]):
        deny.append("evidenceDigest must be a SHA-256 digest")
    if action in PRIVILEGED_ACTIONS or resource["requiresApproval"]:
        if context["networkZone"] not in TRUSTED_ZONES:
            deny.append("approval-required action from untrusted networkZone")
        if context["humanApproval"] is not True:
            deny.append("humanApproval required")
        if context["mfa"] is not True:
            deny.append("mfa required")
        if not context["evidenceDigest"]:
            deny.append("evidenceDigest required")
    return _result(request, deny)


def evaluate(request: Any, entities: Any = None) -> dict[str, Any]:
    return authorize(request, entities)


def main() -> None:
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--request")
    parser.add_argument("--entities")
    args = parser.parse_args()
    with open(args.request, encoding="utf-8") if args.request else sys.stdin as handle:
        request = json.load(handle)
    entities = None
    if args.entities:
        with open(args.entities, encoding="utf-8") as handle:
            entities = json.load(handle)
    json.dump(authorize(request, entities), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
