"""ayllu.backend — the LIVE model backend for ayllu, via a11oy's OWN orchestrator.

Honest wiring: ayllu never talks to a provider directly. It delegates to
`a11oy_code_orchestrator.agent_model_complete`, which owns model routing (route()),
resilient fallback, and per-completion energy receipts, and which returns a
CLEARLY-LABELED deterministic stub (never a fabricated answer) when neither a
reachable local endpoint nor a credentialed remote provider is available. The
live/stub decision is a11oy's, resolved at RUNTIME with no redeploy.

Each turn is wrapped in an a11oy OTel span (szl_observability.span) when present.
Everything here is guarded: if a11oy's modules are absent, model_complete returns an
honest stub dict — it NEVER fabricates an answer and NEVER claims a wiring it lacks.
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import Any, Optional


def _span(name: str, **attrs: Any):
    """a11oy OTel span if present, else a silent no-op context manager (honest)."""
    try:
        import szl_observability as _obs  # type: ignore

        return _obs.span(name, **attrs)
    except Exception:
        return contextlib.nullcontext()


def backend_status() -> dict[str, Any]:
    """Side-effect-free, honest snapshot of what the model backend can do NOW."""
    orch = None
    orch_err: Optional[str] = None
    try:
        import a11oy_code_orchestrator as _o  # type: ignore

        orch = _o
    except Exception as exc:
        orch_err = str(exc)[:160]

    has_cred = False
    local_ready = False
    backend_ready = False
    cred_checked = False
    if orch is not None:
        try:
            has_cred = bool(orch._resolve_hf_token()) or any(
                orch._resolve_provider_keys().values())
            _base, local_ready = orch._serving_base()
            readiness = getattr(orch, "inference_backend_ready", None)
            backend_ready = bool(readiness() if callable(readiness)
                                 else orch.has_inference_credential() or local_ready)
            cred_checked = True
        except Exception:
            cred_checked = False

    if orch is None:
        mode = "unavailable"
    elif not cred_checked:
        mode = "unknown"
    elif backend_ready:
        mode = "live"
    else:
        mode = "stub"

    return {
        "orchestrator_available": orch is not None,
        "orchestrator_error": orch_err,
        "credential_checked": cred_checked,
        "has_credential": has_cred,
        "local_backend_ready": local_ready,
        "backend_ready": backend_ready,
        "mode": mode,
        "note": {
            "unavailable": "a11oy_code_orchestrator not importable — ask/council return "
                           "an honest stub.",
            "unknown": "orchestrator present but credential state could not be read.",
            "live": ("real model answers via a11oy routing + receipts; source is a "
                     "reachable local backend or a credentialed remote provider. "
                     "Outputs remain unverified model text."),
            "stub": ("no reachable local backend or remote inference credential — "
                     "clearly-labeled deterministic stub, no fabrication."),
        }.get(mode, ""),
        "backend": "a11oy_code_orchestrator.agent_model_complete",
    }


async def model_complete(
    system: str,
    prompt: str,
    tier: Optional[str] = None,
    *,
    persona: Optional[str] = None,
    max_tokens: int = 1000,
    temperature: float = 0.4,
    timeout_s: float = 45.0,
    **_ignored: Any,
) -> dict[str, Any]:
    """Adapter matching ayllu.loop.run_turn's model_complete contract.

    Returns {text, model, stub[, energy_receipt]}. Delegates to a11oy's orchestrator;
    on ANY failure returns an honest stub (stub=True) — never a fabricated answer. The
    `tier` argument is advisory only: the orchestrator selects the actual model itself.
    """
    messages = [
        {"role": "system", "content": system or ""},
        {"role": "user", "content": prompt or ""},
    ]
    with _span("ayllu.turn", persona=persona or "", tier_advisory=tier or ""):
        try:
            import a11oy_code_orchestrator as _o  # type: ignore
        except Exception as exc:
            return {
                "text": f"[honest: a11oy_code_orchestrator unavailable "
                        f"({str(exc)[:120]}); no model backend, no fabricated answer]",
                "model": "unavailable",
                "stub": True,
            }
        bounded_tokens = max(1, min(int(max_tokens), 2048))
        bounded_timeout = max(0.1, min(float(timeout_s), 120.0))
        try:
            result = await asyncio.wait_for(
                _o.agent_model_complete(
                    messages, max_tokens=bounded_tokens, temperature=temperature),
                timeout=bounded_timeout,
            )
        except asyncio.TimeoutError:
            return {
                "text": None,
                "model": "timeout",
                "stub": True,
                "timeout": True,
                "token_budget": bounded_tokens,
                "timeout_s": bounded_timeout,
                "honesty": (
                    f"model turn exceeded the {bounded_timeout:g}s deadline; "
                    "the request was cancelled and no answer was fabricated"
                ),
            }
        except Exception as exc:
            return {
                "text": None,
                "model": "error",
                "stub": True,
                "timeout": False,
                "token_budget": bounded_tokens,
                "timeout_s": bounded_timeout,
                "honesty": (
                    f"agent_model_complete raised: {str(exc)[:160]}; "
                    "no answer was fabricated"
                ),
            }
        if not isinstance(result, dict):
            return {
                "text": None,
                "model": "unknown",
                "stub": True,
                "timeout": False,
                "token_budget": bounded_tokens,
                "timeout_s": bounded_timeout,
                "honesty": "model backend returned a non-contract value; no answer was used",
            }
        return {
            "text": result.get("text", ""),
            "model": result.get("model"),
            "stub": bool(result.get("stub")),
            "timeout": bool(result.get("timeout", False)),
            "token_budget": bounded_tokens,
            "timeout_s": bounded_timeout,
            "honesty": result.get("honesty"),
            "energy_receipt": result.get("energy_receipt"),
        }
