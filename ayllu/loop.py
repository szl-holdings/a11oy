"""ayllu.loop — the a11oy-native turn, learned from the tribe's shared brain loop.

The tribe ran every soul through one tool-calling brain. a11oy runs every persona
through a11oy's own machinery:
  * model tier -> a11oy_active_flux_router.router_crossover  (ADVISORY pre-estimate)
  * model call -> injected model_complete (see ayllu.backend), which delegates to
                  a11oy's orchestrator and does the REAL routing + energy receipts
Tool dispatch (the gated a11oy_agent_loop.AgentLoop + ayllu.autonomy.gate) is a
separate, clearly-labeled follow-up and is NOT claimed as active here. This module
never fabricates an answer and never claims a wiring it doesn't have.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional


def select_tier(query_difficulty: float = 0.5) -> dict[str, Any]:
    """ADVISORY tier pre-estimate via a11oy's active-flux router.

    Advisory only: the ACTUAL model is chosen by the backend's own router
    (a11oy_code_orchestrator.route). Honest deterministic fallback (threshold 0.5)
    when the router is absent.
    """
    try:
        import a11oy_active_flux_router as _afr  # type: ignore

        cross = _afr.router_crossover(query_difficulty=float(query_difficulty))
        return {
            "route": cross.get("route"),
            "regime": cross.get("regime"),
            "role": "advisory",
            "source": "a11oy_active_flux_router",
            "detail": cross,
        }
    except Exception as exc:  # honest fallback — router not importable here
        route = "small/local" if float(query_difficulty) < 0.5 else "large/cloud"
        return {
            "route": route,
            "regime": "easy" if route == "small/local" else "hard",
            "role": "advisory",
            "source": "honest-fallback",
            "note": f"active-flux router unavailable ({str(exc)[:80]}); "
                    "deterministic 0.5 threshold used",
        }


async def run_turn(
    persona,
    prompt: str,
    *,
    model_complete: Optional[Callable[..., Awaitable[Any]]] = None,
    execute_tool: Optional[Callable[..., Awaitable[dict]]] = None,   # reserved (follow-up)
    khipu_emit: Optional[Callable[[str, dict], dict]] = None,        # reserved (follow-up)
    puriq_decide: Optional[Callable[[str, dict], dict]] = None,      # reserved (follow-up)
    difficulty: Optional[float] = None,
    two_person_attested: bool = False,
) -> dict[str, Any]:
    """Run one persona's turn.

    With a `model_complete` backend injected, this performs a DIRECT model completion
    (no tool dispatch, no state change) and reports the ACTUAL model the backend used.
    Without a backend, it is HONEST: persona + advisory tier + posture only, no answer.
    It NEVER fabricates a reply, and it does NOT claim the bounded tool-loop it isn't
    running.
    """
    diff = persona.default_difficulty if difficulty is None else float(difficulty)
    tier = select_tier(diff)
    from .model_binding import persona_binding, prompt_contract

    binding = persona_binding(persona.name)
    system = persona.system_prompt() + "\n\n" + prompt_contract(binding)

    answer: Optional[str] = None
    model: Optional[str] = None
    stub: Optional[bool] = None
    timed_out = False
    token_budget: Optional[int] = None
    timeout_s: Optional[float] = None
    energy_receipt: Any = None
    model_attestation: Any = None
    grounding: Any = None

    if model_complete is None:
        honesty = ("model backend not injected — no answer fabricated. This turn "
                   "returns the persona, the advisory model tier, and the bounded-"
                   "autonomy posture only.")
        loop_info = {
            "mode": "no-backend",
            "tool_dispatch": False,
            "note": "ayllu.autonomy.gate is AVAILABLE for any future tool dispatch but "
                    "is not invoked here — this turn runs no tools and changes no state",
        }
    else:
        # DIRECT completion. We deliberately do NOT construct a11oy_agent_loop.AgentLoop:
        # this turn dispatches no tools and changes no state, so claiming the bounded
        # tool-loop would be an overclaim. The gated AgentLoop + ayllu.autonomy.gate are
        # reserved for the tool-calling follow-up.
        loop_info = {
            "mode": "direct-completion",
            "tool_dispatch": False,
            "note": "direct model completion via a11oy's orchestrator; no tools, no state "
                    "change; a11oy_agent_loop.AgentLoop + ayllu.autonomy.gate reserved for "
                    "the tool-calling follow-up and NOT claimed as active here",
        }
        try:
            result = await model_complete(system=system, prompt=prompt,
                                          tier=tier.get("route"), persona=persona.name)
            if isinstance(result, dict):
                answer = result.get("text")
                model = result.get("model")
                stub = result.get("stub")
                timed_out = bool(result.get("timeout", False))
                token_budget = result.get("token_budget")
                timeout_s = result.get("timeout_s")
                energy_receipt = result.get("energy_receipt")
                model_attestation = result.get("model_attestation")
                grounding = result.get("grounding")
            else:
                answer = str(result)
            honesty = "answer produced by a11oy's model backend" + (
                " (clearly-labeled stub — no reachable local or credentialed remote backend)"
                if stub else "")
            if isinstance(result, dict) and result.get("honesty"):
                honesty = str(result["honesty"])
        except Exception as exc:
            honesty = (f"model backend raised: {str(exc)[:120]} "
                       "(honest — no fabricated answer)")

    binding = persona_binding(
        persona.name,
        actual_model=model,
        backend_mode=("stub" if stub else "live" if model else "unavailable"),
        model_attestation=model_attestation,
        grounding=grounding,
    )

    return {
        "persona": persona.name,
        "quechua": persona.quechua,
        "archetype": persona.archetype,
        "domain": persona.domain,
        "tier": tier,
        "tier_note": "advisory pre-estimate; the ACTUAL model was selected by a11oy's "
                     "orchestrator router — see 'model'",
        "loop": loop_info,
        "answer": answer,
        "model": model,
        "stub": stub,
        "timeout": timed_out,
        "token_budget": token_budget,
        "timeout_s": timeout_s,
        "energy_receipt": energy_receipt,
        "model_attestation": model_attestation,
        "grounding": grounding,
        "model_binding": binding,
        "honesty": honesty,
        "evidence": (grounding.get("evidence", [])
                     if isinstance(grounding, dict) else []),
    }
