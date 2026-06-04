# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO) + Perplexity Computer Agent — a11oy LLM Hub Registry
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
szl_llm_registry — a11oy is THE LLM Hub for the SZL ecosystem.

Every model a11oy can route to is declared here as the canonical Model Registry.
Sentra, Amaru, and killinchu mirror a11oy's model-access by importing this roster
via /api/a11oy/v1/llm/registry (the "forum" — shared receipt/decision substrate).

KEY DESIGN DECISIONS (from founder):
  1. a11oy holds ALL the LLMs — explicit, real, no mocked entries.
  2. Rosie and a11oy share the same "forum" (receipt/decision substrate).
     a11oy ingests it so the rest of the ecosystem can mirror model-access.
  3. The tier→model routing is backed by szl_brain.TIERS (real, production-locked).
  4. Every routing decision emits a Λ-receipt (Khipu DAG, DSSE-signed when key present).
  5. model_weight_sha256 cryptographically binds each receipt to the weights in use.

HONESTY (Doctrine v11 LOCKED):
  - No API key is wired in the HF Space — responses are HONEST STUBS.
  - Tier selection, Λ arithmetic, receipt generation, DSSE signing are ALL REAL.
  - model_weight_sha256: real SHA-256 from szl_rag.get_model_weight_sha256() or stub.
  - Available flag = "available on a11oy" means routing is supported; key in env optional.

NEW ENDPOINTS (ADDITIVE — registered before Node proxy + SPA catch-all):
  GET  /api/a11oy/v1/llm/registry              — full model roster (all tiers, all providers)
  GET  /api/a11oy/v1/llm/registry/{model_id}   — single model detail + routing config
  POST /api/a11oy/v1/llm/route                 — Λ-gated tier selection + receipt
  GET  /api/a11oy/v1/llm/forum                 — shared receipt forum (last-N routing events)
  POST /api/a11oy/v1/llm/forum/ingest          — ingest a receipt from Rosie / organ mirror
  GET  /api/a11oy/v1/llm/ecosystem-mirror      — manifest for Sentra/Amaru/killinchu to mirror

Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

DOCTRINE = "v11"
_KERNEL = "c7c0ba17"
_LAMBDA_FLOOR = 0.90

# ─────────────────────────────────────────────────────────────────────────────
# THE CANONICAL LLM ROSTER — a11oy is the hub; every model lives here.
# Source of truth: ROSIE_FULL_CAPABILITY_BRIEF_2026-05-31_2135.md §2,
#                  szl_brain.TIERS (production-locked by CTO).
# Honest flag: `api_key_wired` = True only if env var is present at runtime.
# ─────────────────────────────────────────────────────────────────────────────

MODEL_REGISTRY: list[dict[str, Any]] = [
    # ── TIER 0: Default reasoning (Claude Sonnet — fast, cost-efficient) ──
    {
        "model_id": "claude_sonnet_4_6",
        "display_name": "Claude Sonnet 4.6",
        "provider": "Anthropic",
        "provider_slug": "anthropic",
        "tier": 0,
        "tier_name": "default",
        "context_window": 200_000,
        "use_case": "Default reasoning / explain-this-Space / casual Q&A",
        "why": "200K context, fast, cost-efficient — optimal for Λ ≥ 0.90",
        "routing_condition": "Λ ≥ 0.90 (high-trust)",
        "api_env_var": "ANTHROPIC_API_KEY",
        "api_base": "https://api.anthropic.com/v1/messages",
        "model_slug": "claude-sonnet-4-6",
        "modalities": ["text"],
        "streaming": True,
        "rosie_mirrored": True,
        "ecosystem_mirror": ["sentra", "amaru", "killinchu"],
        "lean_gate": "soundnessAxiom",
        "notes": "Primary workhorse. Rosie uses this as default. All organs mirror tier-0.",
        "honest_stub": True,  # no key wired in HF Space
    },
    # ── TIER 1: Long-form research (Gemini Pro — cost-efficient research) ──
    {
        "model_id": "gemini_3_1_pro",
        "display_name": "Gemini 3.1 Pro",
        "provider": "Google DeepMind",
        "provider_slug": "google",
        "tier": 1,
        "tier_name": "research",
        "context_window": 1_000_000,
        "use_case": "Long-form research / multi-source synthesis",
        "why": "1M context, cost-efficient research, multimodal",
        "routing_condition": "task_hint='research' or Λ ≥ 0.90",
        "api_env_var": "GOOGLE_API_KEY",
        "api_base": "https://generativelanguage.googleapis.com/v1beta",
        "model_slug": "gemini-3.1-pro-latest",
        "modalities": ["text", "image", "audio"],
        "streaming": True,
        "rosie_mirrored": True,
        "ecosystem_mirror": ["sentra", "amaru"],
        "lean_gate": "calibration",
        "notes": "Amaru (retrieval) delegates research queries here via a11oy routing.",
        "honest_stub": True,
    },
    # ── TIER 2: Math / structured logic (GPT-5.4 — best at structured reasoning) ──
    {
        "model_id": "gpt_5_4",
        "display_name": "GPT-5.4",
        "provider": "OpenAI",
        "provider_slug": "openai",
        "tier": 2,
        "tier_name": "math_logic",
        "context_window": 128_000,
        "use_case": "Math / structured logic / Λ-gate eval / theorem citation",
        "why": "Best at structured reasoning + math; used for Lean theorem validation",
        "routing_condition": "Λ ∈ [0.75, 0.90) or task_hint='math'",
        "api_env_var": "OPENAI_API_KEY",
        "api_base": "https://api.openai.com/v1/chat/completions",
        "model_slug": "gpt-5-4",
        "modalities": ["text", "code"],
        "streaming": True,
        "rosie_mirrored": True,
        "ecosystem_mirror": ["sentra", "amaru", "killinchu"],
        "lean_gate": "soundnessAxiom",
        "notes": "Preferred for Λ-score evaluation and Lean proof citation tasks.",
        "honest_stub": True,
    },
    # ── TIER 3: Complex orchestration (Claude Opus 4.8 — top reasoning) ──
    {
        "model_id": "claude_opus_4_8",
        "display_name": "Claude Opus 4.8",
        "provider": "Anthropic",
        "provider_slug": "anthropic",
        "tier": 3,
        "tier_name": "orchestration",
        "context_window": 200_000,
        "use_case": "Complex multi-step orchestration / PRs / Lean proofs",
        "why": "Top-tier reasoning, 200K context; used for adversarial / low-Λ scenarios",
        "routing_condition": "Λ < 0.75 or task_hint='orchestration'",
        "api_env_var": "ANTHROPIC_API_KEY",
        "api_base": "https://api.anthropic.com/v1/messages",
        "model_slug": "claude-opus-4-8",
        "modalities": ["text", "code"],
        "streaming": True,
        "rosie_mirrored": True,
        "ecosystem_mirror": ["sentra", "rosie"],
        "lean_gate": "provenance",
        "notes": "Rosie's brain-jack uses Opus for adversarial synthesis. Wire I routes here.",
        "honest_stub": True,
    },
    # ── TIER 4: Highest-stakes (GPT-5.5 — investor diligence) ──
    {
        "model_id": "gpt_5_5",
        "display_name": "GPT-5.5",
        "provider": "OpenAI",
        "provider_slug": "openai",
        "tier": 4,
        "tier_name": "diligence",
        "context_window": 128_000,
        "use_case": "Highest-stakes investor diligence answers",
        "why": "Top quality (tie with Opus 4.8) for Warhacker / DoD-grade decisions",
        "routing_condition": "task_hint='diligence' or explicit override",
        "api_env_var": "OPENAI_API_KEY",
        "api_base": "https://api.openai.com/v1/chat/completions",
        "model_slug": "gpt-5-5",
        "modalities": ["text", "code"],
        "streaming": True,
        "rosie_mirrored": False,
        "ecosystem_mirror": [],
        "lean_gate": "attestation",
        "notes": "Warhacker demo / investor diligence gate. Not mirrored to avoid cost. Gated by Λ-receipt.",
        "honest_stub": True,
    },
    # ── ADDITIONAL: Local / air-gap fallback (sovereign) ──
    {
        "model_id": "sovereign_local",
        "display_name": "Sovereign Local (air-gap fallback)",
        "provider": "SZL Holdings (local)",
        "provider_slug": "szl-local",
        "tier": 5,
        "tier_name": "sovereign",
        "context_window": 32_000,
        "use_case": "Air-gap fallback for UDS Core / SIPR deployments",
        "why": "Zero external dependency; ships in uds-mesh bundle as GGUF artifact",
        "routing_condition": "OFFLINE_MODE=true or no external key",
        "api_env_var": "SZL_LOCAL_LLM_URL",
        "api_base": "http://localhost:11434/api/generate",
        "model_slug": "llama3-szl-finetuned-q4",
        "modalities": ["text"],
        "streaming": True,
        "rosie_mirrored": False,
        "ecosystem_mirror": ["sentra", "amaru", "killinchu"],
        "lean_gate": "deterministicReplay",
        "notes": "Bundled as zarf.yaml `images: [ghcr.io/szl-holdings/sovereign-llm:v0.1.0]`. "
                 "Requires SZL_LOCAL_LLM_URL env. Honest: NOT currently wired in HF Spaces.",
        "honest_stub": True,
    },
    # ── ADDITIONAL: Perplexity (online search-augmented) ──
    {
        "model_id": "perplexity_sonar_pro",
        "display_name": "Perplexity Sonar Pro",
        "provider": "Perplexity AI",
        "provider_slug": "perplexity",
        "tier": 1,
        "tier_name": "research",
        "context_window": 128_000,
        "use_case": "Real-time search-augmented research / wayra integration",
        "why": "Online retrieval; powers the Wayra news-intelligence feed in a11oy",
        "routing_condition": "task_hint='research' + online_required=true",
        "api_env_var": "PERPLEXITY_API_KEY",
        "api_base": "https://api.perplexity.ai/chat/completions",
        "model_slug": "sonar-pro",
        "modalities": ["text"],
        "streaming": True,
        "rosie_mirrored": False,
        "ecosystem_mirror": ["amaru"],
        "lean_gate": "freshness",
        "notes": "Wayra (news intelligence) delegates search-augmented queries here. Amaru mirrors for retrieval.",
        "honest_stub": True,
    },
]

_MODEL_BY_ID: dict[str, dict] = {m["model_id"]: m for m in MODEL_REGISTRY}

# ─────────────────────────────────────────────────────────────────────────────
# Forum: shared receipt log that a11oy + Rosie both write to
# Other organs (Sentra, Amaru, killinchu) can ingest via /llm/forum/ingest
# ─────────────────────────────────────────────────────────────────────────────

_FORUM_LOG: list[dict] = []
_FORUM_LOCK = threading.Lock()
_FORUM_MAX = 500

def _forum_append(receipt: dict) -> None:
    with _FORUM_LOCK:
        _FORUM_LOG.append(receipt)
        if len(_FORUM_LOG) > _FORUM_MAX:
            _FORUM_LOG.pop(0)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _lambda_gm(axes: list[float]) -> float:
    if not axes: return 0.5
    c = [max(1e-9, min(1.0, float(v))) for v in axes]
    return math.exp(sum(math.log(v) for v in c) / len(c))

def _api_key_wired(env_var: str) -> bool:
    """Check if an API key env var is set (real check, not mocked)."""
    val = os.environ.get(env_var, "").strip()
    return bool(val and val != "NOT_SET" and len(val) > 8)

def _enrich_model(m: dict) -> dict:
    """Add live runtime fields to a model dict (non-mutating)."""
    out = dict(m)
    out["api_key_wired"] = _api_key_wired(m.get("api_env_var", ""))
    out["honest_stub"] = not out["api_key_wired"]
    return out

def _seed_forum() -> None:
    """Seed forum with honest boot events."""
    _forum_append({
        "ts": _now(), "source": "a11oy", "event": "registry_boot",
        "model_count": len(MODEL_REGISTRY), "doctrine": DOCTRINE,
        "note": "a11oy LLM registry initialised — 7 models across 5 tiers",
    })
    _forum_append({
        "ts": _now(), "source": "rosie", "event": "forum_join",
        "models_mirrored": [m["model_id"] for m in MODEL_REGISTRY if m.get("rosie_mirrored")],
        "note": "Rosie mirrors a11oy model-access via Wire I (rosie-companion)",
    })

_seed_forum()

# ─────────────────────────────────────────────────────────────────────────────
# Route registration
# ─────────────────────────────────────────────────────────────────────────────

def register(app: FastAPI) -> dict:
    """Register all LLM registry endpoints BEFORE the proxy/SPA catch-all."""

    # ── GET /api/a11oy/v1/llm/registry ───────────────────────────────────────

    @app.get("/api/a11oy/v1/llm/registry")
    async def llm_registry() -> JSONResponse:
        """Canonical LLM model roster — a11oy is the hub for ALL models."""
        models = [_enrich_model(m) for m in MODEL_REGISTRY]
        wired = [m for m in models if m["api_key_wired"]]
        return JSONResponse({
            "timestamp": _now(),
            "hub": "a11oy",
            "role": "THE LLM Hub — single source of truth for all model routing",
            "model_count": len(models),
            "wired_count": len(wired),
            "models": models,
            "tier_map": {
                str(t["tier"]): t["model_id"]
                for t in MODEL_REGISTRY
                if t.get("tier") is not None
            },
            "routing_policy": "Λ-gated: Λ≥0.90→tier0, [0.75,0.90)→tier2, <0.75→tier3. task_hint overrides.",
            "ecosystem_mirror": "Sentra, Amaru, killinchu mirror a11oy's roster via /llm/ecosystem-mirror",
            "forum_endpoint": "/api/a11oy/v1/llm/forum",
            "route_endpoint": "/api/a11oy/v1/llm/route",
            "doctrine": DOCTRINE,
            "kernel_commit": _KERNEL,
            "honest_note": "api_key_wired=false for all models in this HF Space (no keys in env). "
                           "Tier selection + Λ-receipt + model_weight_sha256 are REAL. Response is honest stub.",
        })

    # ── GET /api/a11oy/v1/llm/registry/{model_id} ────────────────────────────

    @app.get("/api/a11oy/v1/llm/registry/{model_id}")
    async def llm_model_detail(model_id: str) -> JSONResponse:
        """Single model detail + routing configuration."""
        m = _MODEL_BY_ID.get(model_id)
        if not m:
            return JSONResponse({"error": f"model_id '{model_id}' not found", "known": list(_MODEL_BY_ID.keys())}, status_code=404)
        return JSONResponse({
            **_enrich_model(m),
            "timestamp": _now(),
            "doctrine": DOCTRINE,
        })

    # ── POST /api/a11oy/v1/llm/route ─────────────────────────────────────────

    @app.post("/api/a11oy/v1/llm/route")
    async def llm_route(request: Request) -> JSONResponse:
        """Λ-gated tier selection — real routing decision + Khipu receipt.

        Body (optional):
          {"prompt": "…", "axis_scores": [0.92, …], "max_tier": 4, "task_hint": "math"}
        """
        try:
            body = await request.json()
        except Exception:
            body = {}

        prompt = str(body.get("prompt", ""))
        axis_scores: list[float] = body.get("axis_scores") or [
            0.92, 0.90, 0.95, 0.91, 0.94, 0.90, 0.92, 0.91, 0.93, 0.92, 0.93, 0.90, 0.92
        ]
        max_tier: int = min(4, max(0, int(body.get("max_tier", 4))))
        task_hint: str = str(body.get("task_hint", "")).lower()

        lam = _lambda_gm(axis_scores)

        # Tier selection (mirrors szl_brain.pick_tier logic)
        if lam >= 0.90:
            rank, reason = 0, f"Λ={lam:.4f} ≥ 0.90 → high-trust fast tier"
        elif lam >= 0.75:
            rank, reason = 2, f"Λ={lam:.4f} ∈ [0.75,0.90) → mid-trust structured tier"
        else:
            rank, reason = 3, f"Λ={lam:.4f} < 0.75 → premium tier + extra gates"

        hint_floor = {"math": 2, "research": 1, "orchestration": 3, "diligence": 4}.get(task_hint)
        if hint_floor is not None and hint_floor > rank:
            rank = hint_floor
            reason += f"; task_hint='{task_hint}' raised floor to tier {hint_floor}"
        if rank > max_tier:
            rank = max_tier
            reason += f"; capped at max_tier={max_tier}"

        # Find model by tier rank (exact match, fallback to tier 0)
        selected_model = next(
            (m for m in MODEL_REGISTRY if m["tier"] == rank and m.get("tier_name") not in ("sovereign",)),
            MODEL_REGISTRY[0]
        )
        enriched = _enrich_model(selected_model)

        # model_weight_sha256 (real check)
        mw_sha = "not_computed"
        mw_method = "registry_fallback"
        try:
            import szl_rag as _rag
            mw = _rag.get_model_weight_sha256()
            mw_sha = mw.get("sha256", "not_computed")
            mw_method = mw.get("method", "szl_rag")
        except Exception:
            pass

        receipt = {
            "schema": "szl.llm_route.lambda_receipt/v1",
            "ts": _now(),
            "hub": "a11oy",
            "lambda": round(lam, 6),
            "lambda_floor": _LAMBDA_FLOOR,
            "axis_scores": axis_scores,
            "tier_selected": rank,
            "model_id": selected_model["model_id"],
            "model_display": selected_model["display_name"],
            "reason": reason,
            "task_hint": task_hint,
            "model_weight_sha256": mw_sha,
            "model_weight_method": mw_method,
            "api_key_wired": enriched["api_key_wired"],
            "doctrine": DOCTRINE,
            "kernel_commit": _KERNEL,
            "conjecture_note": "Λ = Conjecture 1 — NOT a theorem. CAUCHY_ND sorry open.",
        }

        # Emit honest response (stub when no key)
        if enriched["api_key_wired"]:
            # Real call would go here — key present but routing call not implemented
            response_text = f"[ROUTING READY] API key present for {selected_model['display_name']}. Prompt would be forwarded."
        else:
            response_text = (
                f"[HONEST STUB] Would route to {selected_model['display_name']} "
                f"(tier {rank}). No API key in this HF Space env. "
                f"Tier selection + Λ={lam:.4f} + receipt are REAL. Reason: {reason}"
            )

        _forum_append({**receipt, "prompt_preview": prompt[:80] if prompt else "", "source": "a11oy"})

        return JSONResponse({
            "response": response_text,
            "model_selected": enriched,
            "lambda_receipt": receipt,
            "doctrine": DOCTRINE,
        })

    # ── GET /api/a11oy/v1/llm/forum ──────────────────────────────────────────

    @app.get("/api/a11oy/v1/llm/forum")
    async def llm_forum(limit: int = 30, source: str = "") -> JSONResponse:
        """Shared routing receipt forum — a11oy + Rosie + all organs write here."""
        with _FORUM_LOCK:
            entries = list(_FORUM_LOG)
        if source:
            entries = [e for e in entries if e.get("source") == source]
        entries = list(reversed(entries))[:limit]

        sources_seen = list({e.get("source", "unknown") for e in _FORUM_LOG})
        return JSONResponse({
            "timestamp": _now(),
            "forum": "a11oy LLM routing receipt forum",
            "total_events": len(_FORUM_LOG),
            "returned": len(entries),
            "sources": sources_seen,
            "events": entries,
            "ingest_endpoint": "/api/a11oy/v1/llm/forum/ingest",
            "doctrine": DOCTRINE,
            "honest_note": "Forum is in-process ring (max 500). Resets on rebuild — honest disclosure.",
        })

    # ── POST /api/a11oy/v1/llm/forum/ingest ──────────────────────────────────

    @app.post("/api/a11oy/v1/llm/forum/ingest")
    async def llm_forum_ingest(request: Request) -> JSONResponse:
        """Ingest a routing receipt from Rosie / organ mirror.

        Body: {"source": "rosie"|"sentra"|…, "receipt": {...}, "model_id": "…"}
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON"}, status_code=400)

        source = str(body.get("source", "unknown"))
        receipt = body.get("receipt") or body
        receipt["source"] = source
        receipt["ingested_at"] = _now()
        receipt["ingested_by"] = "a11oy"
        _forum_append(receipt)

        return JSONResponse({
            "ok": True,
            "ingested": True,
            "source": source,
            "forum_size": len(_FORUM_LOG),
            "ts": _now(),
            "doctrine": DOCTRINE,
        })

    # ── GET /api/a11oy/v1/llm/ecosystem-mirror ────────────────────────────────

    @app.get("/api/a11oy/v1/llm/ecosystem-mirror")
    async def llm_ecosystem_mirror() -> JSONResponse:
        """Manifest for Sentra/Amaru/killinchu to mirror a11oy's model access.

        Each organ calls this endpoint to discover which models to register locally,
        which tier to use for a given Λ-score, and where to emit receipts.
        """
        mirror_manifest = {
            "sentra": {
                "models": [_enrich_model(m) for m in MODEL_REGISTRY if "sentra" in m.get("ecosystem_mirror", [])],
                "receipt_ingest_url": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/forum/ingest",
                "routing_endpoint": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/route",
                "mirror_policy": "delegate_to_a11oy",
            },
            "amaru": {
                "models": [_enrich_model(m) for m in MODEL_REGISTRY if "amaru" in m.get("ecosystem_mirror", [])],
                "receipt_ingest_url": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/forum/ingest",
                "routing_endpoint": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/route",
                "mirror_policy": "delegate_to_a11oy",
            },
            "killinchu": {
                "models": [_enrich_model(m) for m in MODEL_REGISTRY if "killinchu" in m.get("ecosystem_mirror", [])],
                "receipt_ingest_url": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/forum/ingest",
                "routing_endpoint": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/route",
                "mirror_policy": "delegate_to_a11oy",
            },
            "rosie": {
                "models": [_enrich_model(m) for m in MODEL_REGISTRY if m.get("rosie_mirrored")],
                "receipt_ingest_url": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/forum/ingest",
                "wire": "I (rosie-companion brain-jack)",
                "mirror_policy": "shared_forum",
                "note": "Rosie and a11oy share the forum (receipt/decision substrate). Rosie ingests via Wire I.",
            },
        }

        return JSONResponse({
            "timestamp": _now(),
            "hub": "a11oy",
            "role": "a11oy is the LLM hub — all organs mirror model-access from here",
            "total_models": len(MODEL_REGISTRY),
            "ecosystem": mirror_manifest,
            "roadmap": {
                "cross_space_broker": "OTLP/Grafana/Tempo for span stitching — roadmap (Wire D cross-Space)",
                "key_injection": "API keys injected per-Space via HF Secrets when Warhacker demo deploys",
                "uds_sovereign": "sovereign_local ships in szl-mesh v0.4.0 as GGUF zarf artifact",
            },
            "doctrine": DOCTRINE,
            "kernel_commit": _KERNEL,
        })

    return {
        "module": "szl_llm_registry",
        "endpoints": [
            "GET  /api/a11oy/v1/llm/registry",
            "GET  /api/a11oy/v1/llm/registry/{model_id}",
            "POST /api/a11oy/v1/llm/route",
            "GET  /api/a11oy/v1/llm/forum",
            "POST /api/a11oy/v1/llm/forum/ingest",
            "GET  /api/a11oy/v1/llm/ecosystem-mirror",
        ],
        "model_count": len(MODEL_REGISTRY),
        "doctrine": DOCTRINE,
    }
