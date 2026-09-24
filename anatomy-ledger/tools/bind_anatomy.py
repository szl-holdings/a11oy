#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
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

import hashlib
import json
import pathlib
import re
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name: str, path: pathlib.Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


INTENT_EVALUATOR = _load("authorize_intent", ROOT / "tools" / "authorize_intent.py")
EVIDENCE_EVALUATOR = _load(
    "evaluate_supply_chain", ROOT / "tools" / "evaluate_supply_chain.py"
)


def project_statement(
    statement: dict[str, Any], verification: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Project an in-toto statement into Anatomy Rego input."""
    return {
        "statement": statement,
        "verification": {"verified": False},
        "binder": "anatomy-ledger.bind_anatomy",
        "disclosure": (
            "Projection only. Caller verification claims are untrusted and "
            "cannot establish cryptographic verification."
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
                "allowedPurposes": [purpose]
                if allowed_purposes is None
                else allowed_purposes,
                "allowedEffects": [intended_effect]
                if allowed_effects is None
                else allowed_effects,
                "requiresApproval": action not in {"ReadResource", "ExportEvidence"},
            },
            "tenantId": tenant_id,
            "requiredAssurance": required_assurance,
            "maxRisk": max_risk,
            "allowedPurposes": [purpose]
            if allowed_purposes is None
            else allowed_purposes,
            "allowedEffects": [intended_effect]
            if allowed_effects is None
            else allowed_effects,
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
    return INTENT_EVALUATOR.authorize(request)


def audit_statement(
    statement: dict[str, Any], verification: dict[str, Any] | None = None
) -> dict[str, Any]:
    return EVIDENCE_EVALUATOR.evaluate(project_statement(statement, verification))


def statement_digest(statement: dict[str, Any]) -> str:
    """Bind the entire statement, not an unrelated artifact subject digest.

    Canonicalization here is sorted-key, compact JSON with UTF-8 characters;
    this is a local format contract, not a claim of RFC 8785 canonicalization.
    """
    if not isinstance(statement, dict):
        raise ValueError("statement must be an object")
    encoded = json.dumps(
        statement,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _evidence_binding(statement: Any, expected: Any) -> dict[str, Any]:
    reasons = []
    actual = ""
    if not isinstance(statement, dict):
        reasons.append("evidence statement is required")
    else:
        try:
            actual = statement_digest(statement)
        except (TypeError, ValueError, RecursionError):
            reasons.append("evidence statement is not valid JSON")
    if type(expected) is not str or not re.fullmatch(
        r"(?:sha256:)?[0-9a-fA-F]{64}", expected
    ):
        reasons.append("context.evidenceDigest must be a SHA-256 digest")
        expected = ""
    if actual and expected and expected.removeprefix("sha256:").lower() != actual:
        reasons.append("context.evidenceDigest does not bind this statement")
    return {
        "valid": not reasons,
        "expectedDigest": expected,
        "statementDigest": actual,
        "algorithm": "sha256-sorted-compact-json-v1",
        "reasons": reasons,
    }


def bind(
    *,
    command: dict[str, Any],
    statement: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose advisory evaluations; this function can never authorize execution."""
    intent = authorize_command(command)
    evidence = None
    if statement is not None:
        evidence = audit_statement(statement, verification)
    context = command.get("context") if isinstance(command, dict) else None
    context = context if isinstance(context, dict) else {}
    binding = _evidence_binding(statement, context.get("evidenceDigest"))
    policy_eligible = bool(
        intent.get("outcome") == "ALLOW"
        and binding["valid"]
        and evidence
        and evidence.get("outcome") == "ALLOW"
        and evidence.get("verified") is True
    )
    return {
        "schema": "szl.anatomy.bind.v1",
        "intent": intent,
        "evidence": evidence,
        "executable": False,
        "evaluationOnly": True,
        "policyEligible": policy_eligible,
        "evidenceBinding": binding,
        "executionAuthority": "none",
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
            "Local advisory composition only; executable is always false. "
            "Caller verification and identity claims are untrusted. Missing, "
            "REVIEW, or mismatched evidence cannot establish policy eligibility. "
            "No trusted command execution integration is installed."
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
