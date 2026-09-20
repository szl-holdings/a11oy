#!/usr/bin/env python3
"""Bind existing A11oy surfaces to Cedar intent + Rego evidence.

This is the frontier increment after the Anatomy ledger package itself.
It does not invent a second flagship. It maps:

- szl_attest chain-of-title statements -> anatomy.supplychain input
- anatomy command / route intent -> Cedar PARC request
- command-surface metadata -> requestId / traceId / evidenceDigest

Honesty:
- Does not call live /api/a11oy routes.
- Does not stamp MEASURED.
- Does not treat DSSE envelope presence as verification.
- Does not evaluate ops/szl_chain_of_title.rego here; that policy stays
  authoritative for chain-of-title. This binder only projects subjects
  that look like in-toto/SLSA into the Anatomy supply-chain auditor.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name: str, path: pathlib.Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def project_statement(statement: dict[str, Any], verification: dict[str, Any] | None = None) -> dict[str, Any]:
    """Project an in-toto statement into Anatomy Rego input."""
    return {
        "statement": statement,
        "verification": verification or {},
        "binder": "anatomy-ledger.bind_anatomy",
        "disclosure": (
            "Projection only. verified=true is accepted only when the caller "
            "already obtained it from an explicit verifier."
        ),
    }


def intent_from_command(
    *,
    principal_id: str,
    action: str,
    resource_id: str,
    purpose: str,
    intended_effect: str,
    risk_score: int,
    human_approval: bool,
    mfa: bool,
    evidence_digest: str = "",
    request_id: str = "",
    trace_id: str = "",
    tenant_id: str = "szl",
    assurance: int = 3,
    required_assurance: int = 1,
    max_risk: int = 400,
    allowed_purposes: list[str] | None = None,
    allowed_effects: list[str] | None = None,
    disabled: bool = False,
) -> dict[str, Any]:
    """Build a Cedar-shaped request from command-surface fields."""
    return {
        "principal": {
            "type": "A11oy::WorkloadIdentity",
            "id": principal_id,
            "attrs": {
                "kind": "agent",
                "tenantId": tenant_id,
                "assurance": assurance,
                "roles": ["operator"],
                "disabled": disabled,
            },
            "tenantId": tenant_id,
            "assurance": assurance,
            "disabled": disabled,
        },
        "action": {"type": "A11oy::Action", "id": action},
        "resource": {
            "type": "A11oy::ProtectedResource",
            "id": resource_id,
            "attrs": {
                "kind": "command",
                "tenantId": tenant_id,
                "classification": 2,
                "requiredAssurance": required_assurance,
                "maxRisk": max_risk,
                "allowedPurposes": allowed_purposes or [purpose],
                "allowedEffects": allowed_effects or [intended_effect],
                "requiresApproval": action not in {"ReadResource", "InvokeTool", "ExportEvidence"},
            },
            "tenantId": tenant_id,
            "requiredAssurance": required_assurance,
            "maxRisk": max_risk,
            "allowedPurposes": allowed_purposes or [purpose],
            "allowedEffects": allowed_effects or [intended_effect],
        },
        "context": {
            "requestId": request_id,
            "sessionId": "",
            "purpose": purpose,
            "intendedEffect": intended_effect,
            "riskScore": risk_score,
            "humanApproval": human_approval,
            "mfa": mfa,
            "networkZone": "command-surface",
            "evidenceDigest": evidence_digest,
            "traceId": trace_id,
            "timestamp": "",
        },
    }


def authorize_command(request: dict[str, Any]) -> dict[str, Any]:
    cedar = _load("authorize_intent", ROOT / "tools" / "authorize_intent.py")
    if hasattr(cedar, "authorize"):
        return cedar.authorize(request)
    if hasattr(cedar, "evaluate"):
        entities = {
            "principals": {
                request["principal"]["id"]: request["principal"].get("attrs")
                or {
                    "tenantId": request["principal"].get("tenantId"),
                    "assurance": request["principal"].get("assurance", 0),
                    "disabled": request["principal"].get("disabled", False),
                }
            },
            "resources": {
                request["resource"]["id"]: request["resource"].get("attrs")
                or {
                    "tenantId": request["resource"].get("tenantId"),
                    "requiredAssurance": request["resource"].get("requiredAssurance", 0),
                    "maxRisk": request["resource"].get("maxRisk", 0),
                    "allowedPurposes": request["resource"].get("allowedPurposes") or [],
                    "allowedEffects": request["resource"].get("allowedEffects") or [],
                }
            },
        }
        return cedar.evaluate(request, entities)
    raise RuntimeError("authorize_intent.py exposes neither authorize nor evaluate")


def audit_statement(statement: dict[str, Any], verification: dict[str, Any] | None = None) -> dict[str, Any]:
    twin = _load("evaluate_supply_chain", ROOT / "tools" / "evaluate_supply_chain.py")
    return twin.evaluate(project_statement(statement, verification))


def bind(
    *,
    command: dict[str, Any],
    statement: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose intent + evidence without claiming a live route ran."""
    intent = authorize_command(command)
    evidence = None
    if statement is not None:
        evidence = audit_statement(statement, verification)
    executable = intent.get("outcome") == "ALLOW" and (
        evidence is None or evidence.get("outcome") in {"ALLOW", "REVIEW"}
    )
    if intent.get("outcome") != "ALLOW":
        executable = False
    if evidence and evidence.get("outcome") == "BLOCK":
        executable = False
    context = command.get("context") if isinstance(command.get("context"), dict) else {}
    return {
        "schema": "szl.anatomy.bind.v1",
        "intent": intent,
        "evidence": evidence,
        "executable": executable,
        "requestId": context.get("requestId") or "",
        "traceId": context.get("traceId") or "",
        "surfaces": {
            "attest": "szl_attest.py",
            "anatomy_routes": "szl_anatomy_routes.py",
            "chain_of_title_policy": "ops/szl_chain_of_title.rego",
            "supply_chain_policy": "anatomy-ledger/policy/rego/supply_chain.rego",
            "cedar_policy": "anatomy-ledger/policy/cedar/intent-auth.cedar",
        },
        "disclosure": (
            "Bind is a local composition of existing contracts. It does not "
            "prove a live command-center route executed. chain-of-title Rego "
            "remains authoritative for szl_attest verdicts."
        ),
    }


def main() -> None:
    import sys

    payload = json.load(sys.stdin)
    result = bind(
        command=payload["command"],
        statement=payload.get("statement"),
        verification=payload.get("verification"),
    )
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
