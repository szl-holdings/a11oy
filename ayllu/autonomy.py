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
    allow = True

    if state_changing and not two_person_attested:
        allow = False
        reasons.append("state-changing action requires two-person attestation "
                       "(a11oy fail-closed law)")

    if lambda_score is not None and float(lambda_score) < float(lambda_floor):
        allow = False
        reasons.append(f"Λ={float(lambda_score):.3f} < floor {float(lambda_floor):.2f} "
                       "— FAIL-CLOSED")

    return {
        "action": action,
        "allow": allow,
        "state_changing": bool(state_changing),
        "two_person_attested": bool(two_person_attested),
        "persona": getattr(persona, "name", None),
        "reason": "; ".join(reasons) if reasons
                  else "allowed (non-state-changing, or attested with Λ ≥ floor)",
        "law": "a11oy bounded-autonomy — the tribe's unbounded 'always execute' "
               "mandate is NOT in force",
    }
