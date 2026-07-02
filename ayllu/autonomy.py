"""ayllu.autonomy — a11oy's bounded-autonomy gate for ayllu personas.

This is the single most important adaptation from the tribe. The tribe's souls carry
a "fully agentic, no sandbox, execute don't narrate" mandate. a11oy REJECTS that. Every
ayllu action passes this fail-closed gate:

  * a state-changing action is DENIED unless two-person attested;
  * if a Λ score is supplied and falls below the advisory floor, it is DENIED;
  * read-only / non-state-changing actions are allowed.

The gate mirrors the discipline of a11oy_agent_loop.AgentLoop's local PURIQ gate so
that behaviour is consistent whether or not the full orchestrator is wired in.
"""
from __future__ import annotations

from typing import Any, Optional

LAMBDA_FLOOR_DEFAULT = 0.90


def gate(
    action: str,
    *,
    state_changing: bool,
    persona: Any = None,
    two_person_attested: bool = False,
    lambda_score: Optional[float] = None,
    lambda_floor: float = LAMBDA_FLOOR_DEFAULT,
) -> dict[str, Any]:
    reasons: list[str] = []
    advisories: list[str] = []
    allow = True

    # Hard, fail-closed gate: state-changing actions need two-person attestation.
    # This is the BINDING guard — it never silently passes.
    if state_changing and not two_person_attested:
        allow = False
        reasons.append("state-changing action requires two-person attestation "
                       "(a11oy fail-closed law)")

    # Λ floor is ADVISORY (matching a11oy's org-Λ advisory-floor surface): a supplied
    # score below the floor denies; an ABSENT score on a state-change is not silently
    # treated as a pass — it is annotated so the claim stays honest.
    lambda_checked = lambda_score is not None
    if lambda_checked and float(lambda_score) < float(lambda_floor):
        allow = False
        reasons.append(f"Λ={float(lambda_score):.3f} < floor {float(lambda_floor):.2f} "
                       "— FAIL-CLOSED")
    elif state_changing and not lambda_checked:
        advisories.append(f"Λ advisory floor {float(lambda_floor):.2f} UNCHECKED "
                          "(no score supplied); attestation is the binding gate")

    if reasons:
        reason = "; ".join(reasons)
    elif advisories:
        reason = "allowed (attestation satisfied); " + "; ".join(advisories)
    else:
        reason = "allowed (non-state-changing, or attested with Λ ≥ floor)"

    return {
        "action": action,
        "allow": allow,
        "state_changing": bool(state_changing),
        "two_person_attested": bool(two_person_attested),
        "lambda_checked": lambda_checked,
        "lambda_floor": float(lambda_floor),
        "persona": getattr(persona, "name", None),
        "reason": reason,
        "advisories": advisories,
        "law": "a11oy bounded-autonomy — attestation is the binding fail-closed gate; "
               "the Λ floor is advisory; the tribe's unbounded 'always execute' mandate "
               "is NOT in force",
    }
