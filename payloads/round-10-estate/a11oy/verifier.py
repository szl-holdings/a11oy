"""a11oy.verifier — OfflineVerifier.

Verifies a GovernedAction/v1 envelope with no network access.

Verdict law:
  * Signature invalid or payload mutated        -> FAIL_SIGNATURE (tamper)
  * Any evidence obligation unsatisfied         -> INCOMPLETE, never PASS
  * IRREVERSIBLE + ALLOW without human approval -> FAIL_POLICY
  * Service-account posing as human approver    -> FAIL_POLICY
  * Otherwise                                   -> PASS
Missing evidence is INCOMPLETE — an auditor's answer, not an accusation.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field

from .receipts import Signer, pae, decode_statement


@dataclass
class Verdict:
    status: str  # PASS | INCOMPLETE | FAIL_SIGNATURE | FAIL_POLICY | FAIL_MALFORMED
    reasons: list[str] = field(default_factory=list)
    action_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict:
        return {"status": self.status, "reasons": self.reasons, "action_id": self.action_id}


class OfflineVerifier:
    def __init__(self, signer: Signer):
        self.signer = signer

    def verify(self, envelope: dict, evidence_resolver=None) -> Verdict:
        reasons: list[str] = []

        # 1. Structure
        try:
            payload = base64.b64decode(envelope["payload"])
            statement = decode_statement(envelope)
            predicate = statement["predicate"]
        except Exception as e:
            return Verdict("FAIL_MALFORMED", [f"envelope does not decode: {e}"])

        action_id = predicate.get("action", {}).get("id")

        # 2. Signature over PAE — any tampering with the payload breaks this.
        sigs = envelope.get("signatures", [])
        if not sigs:
            return Verdict("FAIL_SIGNATURE", ["no signatures on envelope"], action_id)
        sig = base64.b64decode(sigs[0]["sig"])
        if not self.signer.verify(pae(envelope["payloadType"], payload), sig):
            return Verdict("FAIL_SIGNATURE",
                           ["signature does not verify — payload tampered or wrong key"], action_id)
        reasons.append("signature verifies (scheme: %s)" % sigs[0].get("scheme", "UNKNOWN"))

        # 3. Evidence completeness — missing evidence is INCOMPLETE, never PASS.
        evidence = predicate.get("evidence", {})
        obligations = evidence.get("obligations", [])
        unsatisfied = [o.get("id", "?") for o in obligations if not o.get("satisfied")]
        if evidence_resolver is not None:
            for o in obligations:
                if o.get("satisfied") and not evidence_resolver(o):
                    unsatisfied.append(o.get("id", "?") + " (artifact missing at verify time)")
        if unsatisfied:
            return Verdict("INCOMPLETE",
                           reasons + [f"unsatisfied evidence obligations: {', '.join(unsatisfied)}"],
                           action_id)
        if evidence.get("completeness") != "COMPLETE":
            return Verdict("INCOMPLETE",
                           reasons + ["evidence.completeness is not COMPLETE"], action_id)
        reasons.append("all evidence obligations satisfied")

        # 4. Approval law for irreversible actions.
        action = predicate.get("action", {})
        authority = predicate.get("authority", {})
        approval = predicate.get("approval")
        if action.get("side_effect_class") == "IRREVERSIBLE" and authority.get("outcome") in ("ALLOW", "EXECUTED"):
            if not approval:
                return Verdict("FAIL_POLICY",
                               reasons + ["IRREVERSIBLE action executed without approval record"], action_id)
            principal = approval.get("principal", {})
            if principal.get("is_service_account") is True:
                return Verdict("FAIL_POLICY",
                               reasons + ["approval principal is a service account — Art. 12(3)(d) violation"],
                               action_id)
            if not principal.get("id"):
                return Verdict("FAIL_POLICY",
                               reasons + ["approval principal has no identity"], action_id)
            reasons.append(f"human approval recorded: {principal['id']}")

        return Verdict("PASS", reasons, action_id)
