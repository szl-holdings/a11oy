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
import hashlib
import json
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

    profile_runtime = None
    if orch is not None:
        try:
            profile_status = getattr(orch, "forge_profile_runtime_status", None)
            profile_runtime = profile_status() if callable(profile_status) else None
        except Exception:
            profile_runtime = None

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
        "forge_profiles": profile_runtime,
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
        profile = None
        try:
            from .model_binding import persona_binding

            profile = persona_binding(persona or "")["primary_profile"]
        except Exception:
            profile = None

        grounding = None
        if profile == "BrainNavigator-v1":
            try:
                grounding = await asyncio.to_thread(
                    _o.agent_rag_context, prompt or "", k=6)
            except Exception as exc:
                grounding = {
                    "schema": "szl.brain.navigator-context/v1",
                    "state": "ABSTAIN_RETRIEVAL_ERROR",
                    "ready": False,
                    "content_access": "HANDLES_ONLY",
                    "handles": [],
                    "evidence": [],
                    "honesty": f"Brain retrieval raised {type(exc).__name__}; no grounding fabricated",
                }
            if not grounding.get("ready"):
                attestation = None
                try:
                    attestation = await asyncio.to_thread(
                        _o.attest_local_model, profile)
                except Exception:
                    pass
                return {
                    "text": None,
                    "model": ((attestation or {}).get("expected_model") or "khipu-unavailable"),
                    "stub": True,
                    "timeout": False,
                    "token_budget": bounded_tokens,
                    "timeout_s": bounded_timeout,
                    "honesty": (grounding.get("honesty") or
                                "no Brain evidence cleared the retrieval gate; abstaining"),
                    "grounding": grounding,
                    "model_attestation": attestation,
                }
            messages[1]["content"] = (
                (prompt or "")
                + "\n\nCANDIDATE_HANDLES_JSON (controller-provided; no node content):\n"
                + json.dumps(grounding["handles"], sort_keys=True,
                             separators=(",", ":"), ensure_ascii=False)
                + "\nReturn a retrieval plan using only offered nodeId values. "
                  "If none supports the query, return ABSTAIN with zero citations."
            )
            grounding["augmented_prompt_sha256"] = hashlib.sha256(
                messages[1]["content"].encode("utf-8")).hexdigest()
        try:
            result = await asyncio.wait_for(
                _o.agent_model_complete(
                    messages, max_tokens=bounded_tokens, temperature=temperature,
                    local_profile=profile),
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
        answer = result.get("text", "")
        if profile == "BrainNavigator-v1" and grounding is not None:
            citation_state = "NOT_DECLARED_UNSTRUCTURED_OUTPUT"
            cited_node_ids: list[str] = []
            citation_error = None
            if isinstance(answer, str):
                candidate = answer.strip()
                if candidate.startswith("```") and candidate.endswith("```"):
                    candidate = candidate[3:-3].strip()
                    if candidate.lower().startswith("json"):
                        candidate = candidate[4:].lstrip()
                try:
                    parsed_answer = json.loads(candidate)
                except (TypeError, ValueError):
                    parsed_answer = None
                if isinstance(parsed_answer, dict):
                    declared = (
                        parsed_answer.get("citedNodeIds")
                        if "citedNodeIds" in parsed_answer
                        else parsed_answer.get("cited_node_ids")
                        if "cited_node_ids" in parsed_answer
                        else None
                    )
                    if declared is not None:
                        if (not isinstance(declared, list)
                                or any(not isinstance(item, str) or not item
                                       for item in declared)):
                            citation_state = "INVALID_CITATION_CONTRACT"
                            citation_error = "cited node IDs must be a list of non-empty strings"
                        else:
                            cited_node_ids = list(dict.fromkeys(declared))
                            offered = {
                                row.get("nodeId") for row in grounding.get("handles", [])
                                if isinstance(row, dict) and isinstance(row.get("nodeId"), str)
                            }
                            unknown = sorted(set(cited_node_ids) - offered)
                            if unknown:
                                citation_state = "UNKNOWN_CITATION_REFUSED"
                                citation_error = (
                                    "model cited node IDs outside the controller-offered handle set"
                                )
                            else:
                                citation_state = "CITATIONS_WITHIN_OFFERED_HANDLES"
            grounding["citation_validation"] = {
                "state": citation_state,
                "cited_node_ids": cited_node_ids,
                "cited_node_ids_sha256": hashlib.sha256(json.dumps(
                    cited_node_ids, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False
                ).encode("utf-8")).hexdigest(),
            }
            if citation_error:
                grounding["citation_validation"]["honesty"] = citation_error
                rejected_output_sha256 = (
                    hashlib.sha256(answer.encode("utf-8")).hexdigest()
                    if isinstance(answer, str) else None
                )
                grounding["rejected_model_output_sha256"] = rejected_output_sha256
                return {
                    "text": None,
                    "model": result.get("model"),
                    "stub": True,
                    "timeout": bool(result.get("timeout", False)),
                    "token_budget": bounded_tokens,
                    "timeout_s": bounded_timeout,
                    "honesty": citation_error + "; no ungrounded model text returned",
                    "raw_model_output_sha256": rejected_output_sha256,
                    "energy_receipt": result.get("energy_receipt"),
                    "model_attestation": result.get("model_attestation"),
                    "grounding": grounding,
                }
        return {
            "text": answer,
            "model": result.get("model"),
            "stub": bool(result.get("stub")),
            "timeout": bool(result.get("timeout", False)),
            "token_budget": bounded_tokens,
            "timeout_s": bounded_timeout,
            "honesty": result.get("honesty"),
            "energy_receipt": result.get("energy_receipt"),
            "model_attestation": result.get("model_attestation"),
            "grounding": grounding,
        }
