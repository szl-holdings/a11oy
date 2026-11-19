#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Trust policy, owner authorization grants, and the consequential-action gate.

The core invariant of the Proof-to-Discovery doctrine is enforced here:

    No consequential action may be authorized solely by a model-generated
    claim or an unverified evidence record.

Acting requires (1) every blocking obligation PROVEN, (2) no obligation
REFUTED anywhere in the graph, and (3) a currently valid owner authorization
grant that is a real Ed25519 signature by a registered owner key naming this
decision and action. Remove any leg and the gate answers False.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import ed25519
from .records import parse_instant
from .graph import Evaluation, ObligationGraph, VERDICT_PROVEN


@dataclass(frozen=True)
class TrustPolicy:
    """Registered signer keys and the experiment-portfolio weights."""

    witness_keys: frozenset[str]
    owner_keys: frozenset[str]
    cost_weight: float = 1.0
    risk_weight: float = 1.0


def _grant_binding(grant_fields: dict) -> bytes:
    return json.dumps(grant_fields, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class AuthorizationGrant:
    """An owner directive authorizing one action on one decision."""

    grant_id: str
    decision_id: str
    action: str
    granted_at: str
    expires_at: str
    signer_key: str
    signature: str

    def binding_bytes(self) -> bytes:
        return _grant_binding(
            {
                "grant_id": self.grant_id,
                "decision_id": self.decision_id,
                "action": self.action,
                "granted_at": self.granted_at,
                "expires_at": self.expires_at,
            }
        )

    @classmethod
    def build(
        cls,
        *,
        grant_id: str,
        decision_id: str,
        action: str,
        granted_at: str,
        expires_at: str,
        owner_seed: bytes,
    ) -> "AuthorizationGrant":
        """Construct an honestly signed grant (used by fixtures and the demo)."""
        grant = cls(
            grant_id=grant_id,
            decision_id=decision_id,
            action=action,
            granted_at=granted_at,
            expires_at=expires_at,
            signer_key=ed25519.public_key(owner_seed).hex(),
            signature="",
        )
        signature = ed25519.sign(owner_seed, grant.binding_bytes()).hex()
        return cls(
            grant_id=grant_id,
            decision_id=decision_id,
            action=action,
            granted_at=granted_at,
            expires_at=expires_at,
            signer_key=grant.signer_key,
            signature=signature,
        )


def check_grant(
    grant: AuthorizationGrant | None,
    *,
    policy: TrustPolicy,
    decision_id: str,
    action: str,
    evaluated_at: str,
) -> tuple[bool, list[str]]:
    """Fail-closed grant validation. Returns (valid, reasons)."""
    if grant is None:
        return False, ["no authorization grant presented"]
    reasons: list[str] = []
    if grant.decision_id != decision_id:
        reasons.append(f"grant names decision {grant.decision_id!r}, not {decision_id!r}")
    if grant.action != action:
        reasons.append(f"grant authorizes action {grant.action!r}, not {action!r}")
    if grant.signer_key not in policy.owner_keys:
        reasons.append("grant signer is not a registered owner key")
    try:
        if not ed25519.verify(
            bytes.fromhex(grant.signer_key), grant.binding_bytes(), bytes.fromhex(grant.signature)
        ):
            reasons.append("grant signature does not verify")
        now = parse_instant(evaluated_at)
        granted = parse_instant(grant.granted_at)
        expires = parse_instant(grant.expires_at)
        if now < granted:
            reasons.append("grant is not yet in force")
        if now > expires:
            reasons.append("grant has expired")
    except ValueError:
        reasons.append("grant has malformed keys or instants")
    return (not reasons), reasons


@dataclass(frozen=True)
class ActionDecision:
    """The gate's answer to: may the operator act now, and why or why not."""

    may_act: bool
    action: str
    reasons: tuple[str, ...]


def evaluate_action(
    *,
    graph: ObligationGraph,
    evaluation: Evaluation,
    grant: AuthorizationGrant | None,
    policy: TrustPolicy,
    action: str,
    evaluated_at: str,
) -> ActionDecision:
    """Apply the core invariant. All three legs must hold to act."""
    reasons: list[str] = []
    unresolved = [
        item.obligation_id
        for item in evaluation.verdicts.values()
        if item.blocking and item.verdict != VERDICT_PROVEN
    ]
    if unresolved:
        reasons.append(
            "blocking obligations are not PROVEN, so action is refused regardless of "
            "authorization: " + ", ".join(sorted(unresolved))
        )
    refuted = evaluation.refuted()
    if refuted:
        reasons.append("evidence REFUTES obligations, so action is refused: " + ", ".join(refuted))
    grant_ok, grant_reasons = check_grant(
        grant, policy=policy, decision_id=graph.decision_id, action=action, evaluated_at=evaluated_at
    )
    reasons.extend(grant_reasons)
    if grant_ok and not unresolved and not refuted:
        reasons.append(
            "all blocking obligations PROVEN, none REFUTED, and a valid unexpired owner grant "
            f"authorizes {action!r}"
        )
        return ActionDecision(True, action, tuple(reasons))
    return ActionDecision(False, action, tuple(reasons))
