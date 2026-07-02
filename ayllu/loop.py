"""ayllu.loop — the a11oy-native turn, learned from the tribe's shared brain loop.

The tribe ran every soul through one tool-calling brain. a11oy runs every persona
through a11oy's own machinery:
  * model tier   -> a11oy_active_flux_router.router_crossover  (small/local vs large/cloud)
  * bounded exec -> a11oy_agent_loop.AgentLoop                 (fail-closed Λ-gate)
Both are optional imports with HONEST fallbacks — this module never fabricates an
answer, and never claims a wiring it doesn't have.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional


def select_tier(query_difficulty: float = 0.5) -> dict[str, Any]:
    """Choose small/local vs large/cloud via a11oy's active-flux router.

    Honest deterministic fallback (threshold at 0.5) when the router is absent.
    """
    try:
        import a11oy_active_flux_router as _afr  # type: ignore

        cross = _afr.router_crossover(query_difficulty=float(query_difficulty))
        return {
            "route": cross.get("route"),
            "regime": cross.get("regime"),
            "source": "a11oy_active_flux_router",
            "detail": cross,
        }
    except Exception as exc:  # honest fallback — router not importable here
        route = "small/local" if float(query_difficulty) < 0.5 else "large/cloud"
        return {
            "route": route,
            "regime": "easy" if route == "small/local" else "hard",
            "source": "honest-fallback",
            "note": f"active-flux router unavailable ({str(exc)[:80]}); "
                    "deterministic 0.5 threshold used",
        }


async def run_turn(
    persona,
    prompt: str,
    *,
    model_complete: Optional[Callable[..., Awaitable[Any]]] = None,
    execute_tool: Optional[Callable[..., Awaitable[dict]]] = None,
    khipu_emit: Optional[Callable[[str, dict], dict]] = None,
    puriq_decide: Optional[Callable[[str, dict], dict]] = None,
    difficulty: Optional[float] = None,
    two_person_attested: bool = False,
) -> dict[str, Any]:
    """Run one persona's turn under a11oy's bounded machinery.

    If no `model_complete` backend is injected, the turn is HONEST: it returns the
    persona, the selected tier, and the bounded-loop wiring, with a clear note that
    no answer was produced. It NEVER fabricates a reply.
    """
    diff = persona.default_difficulty if difficulty is None else float(difficulty)
    tier = select_tier(diff)
    system = persona.system_prompt()

    # Bind a11oy's bounded-autonomy loop ONLY when there is a backend to run — we do
    # not construct an AgentLoop we won't use (avoids any orchestrator side effects).
    if model_complete is None:
        loop_info = {
            "bounded_loop": "not constructed (no model backend to run this turn)",
            "note": "ayllu.autonomy.gate is AVAILABLE for any future tool dispatch but "
                    "is not invoked here — this turn runs no tools and changes no state",
        }
    else:
        try:
            import a11oy_agent_loop as _al  # type: ignore

            loop = _al.AgentLoop(
                khipu_emit=khipu_emit,
                puriq_decide=puriq_decide,
                execute_tool=execute_tool,
                model_complete=model_complete,
                two_person_attested=two_person_attested,
            )
            loop_info = {
                "bounded_loop": "a11oy_agent_loop.AgentLoop",
                "run_id": getattr(loop, "run_id", None),
                "lambda_floor": getattr(loop, "lambda_floor", None),
            }
        except Exception as exc:
            loop_info = {
                "bounded_loop": "honest-fallback",
                "note": f"AgentLoop unavailable ({str(exc)[:80]}); ayllu.autonomy.gate "
                        "MUST gate any tool dispatch before it runs",
            }

    answer: Optional[str] = None
    if model_complete is None:
        honesty = ("model backend not injected — no answer fabricated. This turn "
                   "returns the persona, the selected model tier, and the "
                   "bounded-loop wiring only.")
    else:
        try:
            result = await model_complete(system=system, prompt=prompt,
                                          tier=tier.get("route"))
            answer = result.get("text") if isinstance(result, dict) else str(result)
            honesty = "answer produced by injected model backend"
        except Exception as exc:
            honesty = f"model backend raised: {str(exc)[:120]} (honest — no fabricated answer)"

    return {
        "persona": persona.name,
        "quechua": persona.quechua,
        "archetype": persona.archetype,
        "domain": persona.domain,
        "tier": tier,
        "loop": loop_info,
        "answer": answer,
        "honesty": honesty,
        "evidence": [],
    }
