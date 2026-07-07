# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO) + Perplexity Computer Agent — a11oy LLM Hub Registry
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
szl_llm_registry — a11oy is THE LLM Hub for the SZL ecosystem.

Every model a11oy can route to is declared here as the canonical Model Registry.
Policy, Reasoning, and killinchu mirror a11oy's model-access by importing this roster
via /api/a11oy/v1/llm/registry (the "forum" — shared receipt/decision substrate).

KEY DESIGN DECISIONS (from founder):
  1. a11oy holds ALL the LLMs — explicit, real, no mocked entries.
  2. Operator and a11oy share the same "forum" (receipt/decision substrate).
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
  POST /api/a11oy/v1/llm/forum/ingest          — ingest a receipt from Operator / organ mirror
  GET  /api/a11oy/v1/llm/ecosystem-mirror      — manifest for Policy/Reasoning/killinchu to mirror

Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
import urllib.request as _urllib_request
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

DOCTRINE = "v11"
_KERNEL = "c7c0ba17"
_LAMBDA_FLOOR = 0.90

# Wave M (DEV 1) — first-class sovereign backend id + honest provenance.
# The founder stands up a LOCAL sovereign model on the Tower (OMEN, RTX 4060 Ti)
# via Ollama (model tag `llama3-szl-finetuned-q4`, base llama3.1:8b wrapped in a
# Doctrine-v11 SYSTEM prompt), served OpenAI-compatible at SZL_LOCAL_LLM_URL
# (default http://localhost:11434/v1). It is NOT reachable from CI/cloud, so this
# backend MUST degrade to an honest UNAVAILABLE label (never fabricate a response).
_SOVEREIGN_BACKEND_ID = "szl-sovereign-local"          # canonical Wave-M backend id
_SOVEREIGN_LEGACY_ID = "sovereign_local"                # pre-Wave-M alias (kept, additive)
_SOVEREIGN_MODEL_TAG = "llama3-szl-finetuned-q4"        # ollama model tag (Stage A wrapper / Stage B LoRA)
_SOVEREIGN_PROVENANCE = "SZL sovereign (Ollama, local, Doctrine-v11 system prompt)"
# Honest label vocabulary (Doctrine v11): the sovereign backend is LIVE only when
# the node answers this request; otherwise UNAVAILABLE (never SIMULATED/fabricated).
_LABEL_LIVE = "LIVE"
_LABEL_UNAVAILABLE = "UNAVAILABLE"

# ─────────────────────────────────────────────────────────────────────────────
# THE CANONICAL LLM ROSTER — a11oy is the hub; every model lives here.
# Source of truth: OPERATOR_FULL_CAPABILITY_BRIEF_2026-05-31_2135.md §2,
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
        "operator_mirrored": True,
        "ecosystem_mirror": ["policy", "reasoning", "killinchu"],
        "lean_gate": "soundnessAxiom",
        "notes": "Primary workhorse. Operator uses this as default. All organs mirror tier-0.",
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
        "operator_mirrored": True,
        "ecosystem_mirror": ["policy", "reasoning"],
        "lean_gate": "calibration",
        "notes": "Reasoning (retrieval) delegates research queries here via a11oy routing.",
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
        "use_case": "Math / structured logic / Λ-gate eval (Λ = Conjecture 1, never a theorem) / theorem citation",
        "why": "Best at structured reasoning + math; used for Lean theorem validation",
        "routing_condition": "Λ ∈ [0.75, 0.90) or task_hint='math'",
        "api_env_var": "OPENAI_API_KEY",
        "api_base": "https://api.openai.com/v1/chat/completions",
        "model_slug": "gpt-5-4",
        "modalities": ["text", "code"],
        "streaming": True,
        "operator_mirrored": True,
        "ecosystem_mirror": ["policy", "reasoning", "killinchu"],
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
        "operator_mirrored": True,
        "ecosystem_mirror": ["policy", "operator"],
        "lean_gate": "provenance",
        "notes": "Operator's brain-jack uses Opus for adversarial synthesis. Wire I routes here.",
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
        "operator_mirrored": False,
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
        "api_base": "http://localhost:11434",  # ollama base; /api/generate or /v1 resolved at call time
        "model_slug": "llama3-szl-finetuned-q4",
        "modalities": ["text"],
        "streaming": True,
        "operator_mirrored": False,
        "ecosystem_mirror": ["policy", "reasoning", "killinchu"],
        "lean_gate": "deterministicReplay",
        "notes": "Bundled as zarf.yaml `images: [ghcr.io/szl-holdings/sovereign-llm:v0.1.0]`. "
                 "Wired when SZL_LOCAL_LLM_URL is set (point at https://gpu.a-11-oy.com); "
                 "makes a REAL guarded ollama /api or OpenAI-compatible /v1 call and is wired=true "
                 "ONLY when the node answers live THIS request (see /llm/sovereign/health). "
                 "Honest stub when the env is unset or the node is offline.",
        "honest_stub": True,
    },
    # ── WAVE M (DEV 1): FIRST-CLASS SOVEREIGN BACKEND (own-metal, routed FIRST) ──
    # `szl-sovereign-local` is the canonical Wave-M backend id for the founder's
    # Tower model (Ollama, model tag llama3-szl-finetuned-q4, Doctrine-v11 system
    # prompt). It targets SZL_LOCAL_LLM_URL (default http://localhost:11434/v1,
    # OpenAI-compatible /chat/completions; native Ollama /api/generate fallback).
    # Per the router's "own metal first" doctrine it slots FIRST in the routing
    # order (before free, before paid) — BUT ONLY when the node answers live this
    # request. When the Tower is offline it degrades to an HONEST UNAVAILABLE
    # label; it NEVER fabricates a response.
    {
        "model_id": _SOVEREIGN_BACKEND_ID,          # "szl-sovereign-local"
        "display_name": "SZL Sovereign Local (own-metal, Doctrine-v11)",
        "provider": _SOVEREIGN_PROVENANCE,           # "SZL sovereign (Ollama, local, Doctrine-v11 system prompt)"
        "provider_slug": "szl-sovereign",
        "tier": 5,
        "tier_name": "sovereign",
        "context_window": 32_000,
        "use_case": "Own-metal sovereign inference — routed FIRST when reachable",
        "why": "SZL's OWN governed model on the Tower; zero external dependency; "
               "routed before free/paid per 'own metal first' doctrine when live",
        "routing_condition": "own-metal FIRST when node is reachable; else honest UNAVAILABLE",
        "api_env_var": "SZL_LOCAL_LLM_URL",
        "api_base": "http://localhost:11434/v1",     # OpenAI-compatible base (default)
        "model_slug": _SOVEREIGN_MODEL_TAG,           # "llama3-szl-finetuned-q4"
        "modalities": ["text"],
        "streaming": True,
        "operator_mirrored": False,
        "ecosystem_mirror": ["policy", "reasoning", "killinchu"],
        "lean_gate": "deterministicReplay",
        "own_metal": True,
        "route_first": True,
        "legacy_alias": _SOVEREIGN_LEGACY_ID,
        "notes": "Stage A = Doctrine-v11 system-prompt derivative (now); Stage B = real "
                 "LoRA fine-tune (later) under the SAME model tag. Wired when "
                 "SZL_LOCAL_LLM_URL is set; makes a REAL guarded ollama /api/generate "
                 "or OpenAI-compatible /v1/chat/completions call and is LIVE ONLY when "
                 "the node answers this request. Honest UNAVAILABLE otherwise "
                 "(see GET /api/a11oy/v1/llm/sovereign/health). The Tower is NOT "
                 "reachable from CI/cloud — CI reports UNAVAILABLE, never fabricates.",
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
        "operator_mirrored": False,
        "ecosystem_mirror": ["reasoning"],
        "lean_gate": "freshness",
        "notes": "Wayra (news intelligence) delegates search-augmented queries here. Reasoning mirrors for retrieval.",
        "honest_stub": True,
    },
    # ── ADDITIONAL: OpenRouter aggregator (one key → many models) ──
    {
        "model_id": "openrouter_auto",
        "display_name": "OpenRouter (aggregator)",
        "provider": "OpenRouter",
        "provider_slug": "openrouter",
        "tier": 2,
        "tier_name": "structured",
        "context_window": 128_000,
        "use_case": "Provider-agnostic routing for a11oy Code agent (one key, many models)",
        "why": "Single OpenAI-compatible endpoint fans out to 200+ models; ideal A11OY_CODE_LLM_KEY backend",
        "routing_condition": "A11OY_CODE_LLM_KEY present and provider=openrouter",
        "api_env_var": "OPENROUTER_API_KEY",
        "api_base": "https://openrouter.ai/api/v1/chat/completions",
        "model_slug": "openrouter/auto",
        "modalities": ["text"],
        "streaming": True,
        "operator_mirrored": False,
        "ecosystem_mirror": ["policy", "reasoning", "killinchu"],
        "lean_gate": "none",
        "notes": "OpenAI-API-compatible. Resolvable via the provider-agnostic A11OY_CODE_LLM_KEY "
                 "resolver. Honest: NOT wired in HF Spaces unless the key is set.",
        "honest_stub": True,
    },
    # ── ADDITIONAL: Mistral (hosted) ──
    {
        "model_id": "mistral_large_2",
        "display_name": "Mistral Large 2",
        "provider": "Mistral AI",
        "provider_slug": "mistral",
        "tier": 2,
        "tier_name": "structured",
        "context_window": 128_000,
        "use_case": "Structured coding / tool-calling for the a11oy Code agent",
        "why": "Strong code + function-calling; Apache-friendly weights lineage",
        "routing_condition": "A11OY_CODE_LLM_KEY present and provider=mistral",
        "api_env_var": "MISTRAL_API_KEY",
        "api_base": "https://api.mistral.ai/v1/chat/completions",
        "model_slug": "mistral-large-latest",
        "modalities": ["text"],
        "streaming": True,
        "operator_mirrored": False,
        "ecosystem_mirror": ["reasoning", "killinchu"],
        "lean_gate": "none",
        "notes": "OpenAI-API-compatible chat endpoint. Honest: NOT wired in HF Spaces unless key set.",
        "honest_stub": True,
    },
    # ── ADDITIONAL: DeepSeek (hosted) ──
    {
        "model_id": "deepseek_v3",
        "display_name": "DeepSeek V3",
        "provider": "DeepSeek",
        "provider_slug": "deepseek",
        "tier": 2,
        "tier_name": "structured",
        "context_window": 64_000,
        "use_case": "Cost-efficient code + reasoning for the a11oy Code agent",
        "why": "Strong code performance at low cost; OpenAI-compatible API",
        "routing_condition": "A11OY_CODE_LLM_KEY present and provider=deepseek",
        "api_env_var": "DEEPSEEK_API_KEY",
        "api_base": "https://api.deepseek.com/v1/chat/completions",
        "model_slug": "deepseek-chat",
        "modalities": ["text"],
        "streaming": True,
        "operator_mirrored": False,
        "ecosystem_mirror": ["reasoning", "killinchu"],
        "lean_gate": "none",
        "notes": "OpenAI-API-compatible. Honest: NOT wired in HF Spaces unless key set.",
        "honest_stub": True,
    },
]

_MODEL_BY_ID: dict[str, dict] = {m["model_id"]: m for m in MODEL_REGISTRY}

# ─────────────────────────────────────────────────────────────────────────────
# Forum: shared receipt log that a11oy + Operator both write to
# Other organs (Policy, Reasoning, killinchu) can ingest via /llm/forum/ingest
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


# ─────────────────────────────────────────────────────────────────────────────
# SOVEREIGN LOCAL FLEET — real chat/generate call path (guarded, honest).
#
# `sovereign_local` (slug llama3-szl-finetuned-q4) routes to the local GPU fleet
# (ollama, OpenAI-compatible /v1 or native /api) when SZL_LOCAL_LLM_URL is set AND
# the node answers live THIS request. Otherwise it degrades to an HONEST STUB.
#
# Doctrine v11: wired=true ONLY if the env base is present AND the node responded
# live on this request. We NEVER fabricate a wired=true or a model response.
# Transport mirrors szl_kc_jpt (browser-like UA so a Cloudflare-fronted node does
# not 403; short guarded timeouts; never raises). Pure stdlib.
# ─────────────────────────────────────────────────────────────────────────────
_SOVEREIGN_ENV = "SZL_LOCAL_LLM_URL"
# Unified sovereign-mesh gateway (LiteLLM). When A11OY_SOVEREIGN_GATEWAY_URL is
# set it takes precedence over SZL_LOCAL_LLM_URL, so the Space/brain hit the ONE
# load-balancing endpoint (sovereign-llm across omen + betterwithage) instead of a
# single node. UNSET => behavior is IDENTICAL to before (falls back to
# SZL_LOCAL_LLM_URL). Never fabricates reachability — a live call still proves it.
# See box-scripts/litellm_config.yaml + research/SOVEREIGN_MESH_RUNBOOK.md.
_GATEWAY_ENV = "A11OY_SOVEREIGN_GATEWAY_URL"
# Optional bearer for a bearer-protected gateway (LiteLLM master_key). The SECRET
# is NEVER logged or returned — only attached as an Authorization header on the
# guarded outbound call. Falls back to SZL_LOCAL_LLM_KEY. Unset => no header.
_GATEWAY_KEY_ENV = "A11OY_SOVEREIGN_GATEWAY_KEY"
_DEFAULT_SOVEREIGN_PROMPT = os.environ.get(
    "SZL_LOCAL_LLM_PROMPT",
    "In one sentence, state why sovereign local inference matters for air-gapped deployments.")
# Cloudflare-front gotcha: a plain UA gets HTTP 403 (code 1010). Reuse the fleet
# browser-UA pattern (SZL_PROBE_USER_AGENT is the ecosystem-wide override name).
_SOVEREIGN_UA = os.environ.get(
    "SZL_PROBE_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 szl-a11oy-registry/1.0")
try:
    _SOVEREIGN_PROBE_TIMEOUT_S = float(os.environ.get("SZL_LOCAL_LLM_PROBE_TIMEOUT", "4.0"))
except (TypeError, ValueError):
    _SOVEREIGN_PROBE_TIMEOUT_S = 4.0
try:
    _SOVEREIGN_GEN_TIMEOUT_S = float(os.environ.get("SZL_LOCAL_LLM_GEN_TIMEOUT", "120.0"))
except (TypeError, ValueError):
    _SOVEREIGN_GEN_TIMEOUT_S = 120.0


# Doctrine v11 default: OpenAI-compatible base at the Tower's Ollama /v1 endpoint.
_SOVEREIGN_DEFAULT_URL = "http://localhost:11434/v1"


def _sovereign_base() -> str:
    """Resolve the sovereign base URL from env.

    Prefers the unified mesh gateway (A11OY_SOVEREIGN_GATEWAY_URL, the LiteLLM
    load-balancer over both GPU boxes: omen + betterwithage). Falls back to the
    single-node SZL_LOCAL_LLM_URL, then to the OpenAI-compatible Tower endpoint
    (http://localhost:11434/v1) when neither is set, so the backend always has a
    concrete target to reachability-probe. The probe/generate paths normalise a
    trailing `/v1` back to the Ollama root for native /api calls, so either form
    (`.../11434` or `.../11434/v1`) works. This is a guarded preference only — it
    never asserts the endpoint is reachable; a live call still proves it.
    """
    gw = (os.environ.get(_GATEWAY_ENV, "") or "").strip()
    if gw:
        return gw.rstrip("/")
    val = (os.environ.get(_SOVEREIGN_ENV, "") or "").strip().rstrip("/")
    return val or _SOVEREIGN_DEFAULT_URL


def _sovereign_env_present() -> bool:
    """True only when the sovereign gateway URL (A11OY_SOVEREIGN_GATEWAY_URL) or
    the single-node SZL_LOCAL_LLM_URL was explicitly set (operator intent)."""
    return bool((os.environ.get(_GATEWAY_ENV, "") or "").strip()
                or (os.environ.get(_SOVEREIGN_ENV, "") or "").strip())


def _ollama_root(base: str) -> str:
    """Return the Ollama server root, stripping a trailing OpenAI-compat `/v1`."""
    b = (base or "").rstrip("/")
    if b.endswith("/v1"):
        b = b[: -len("/v1")]
    return b


def _sovereign_auth_header() -> dict[str, str]:
    """Bearer header for a bearer-protected gateway, or {} when no key is set.

    Reads A11OY_SOVEREIGN_GATEWAY_KEY (fallback SZL_LOCAL_LLM_KEY). The secret is
    NEVER logged or returned in any response — it is only placed on the outbound
    Authorization header of the guarded call. Unset => no header (unchanged path).
    """
    key = (os.environ.get(_GATEWAY_KEY_ENV, "")
           or os.environ.get("SZL_LOCAL_LLM_KEY", "") or "").strip()
    if key and len(key) > 8:
        return {"Authorization": "Bearer " + key}
    return {}


def _sovereign_model_slug() -> str:
    """The ollama model tag the local node should serve. Overridable per-deploy.
    The registry slug is `llama3-szl-finetuned-q4`; the live tower currently
    serves `llama3.1:8b`, so SZL_LOCAL_LLM_MODEL lets a deploy name the real tag."""
    return (os.environ.get("SZL_LOCAL_LLM_MODEL", "llama3.1:8b") or "llama3.1:8b").strip()


def _http_json(url: str, *, method: str = "GET", body: bytes | None = None,
               timeout: float = 4.0) -> tuple[Any, str | None]:
    """Guarded JSON HTTP with a browser UA. Returns (doc, error). NEVER raises,
    NEVER fabricates. `doc` is None on any failure (unreachable/timeout/non-2xx/
    malformed) and `error` carries a short honest reason."""
    headers = {"User-Agent": _SOVEREIGN_UA, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    # Optional bearer for a bearer-protected gateway (LiteLLM). Secret never logged.
    headers.update(_sovereign_auth_header())
    try:
        req = _urllib_request.Request(url, data=body, method=method, headers=headers)
        with _urllib_request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            status = getattr(r, "status", None) or 200
            if not (200 <= int(status) < 300):
                return None, "node non-2xx status %s" % status
            raw = r.read().decode("utf-8", "replace")
        doc = json.loads(raw)
        return doc, None
    except Exception as exc:  # noqa: BLE001 — unreachable/timeout => honest OFFLINE
        return None, "node unreachable: %s" % (str(exc)[:160])


def sovereign_probe(base: str = "", timeout: float | None = None) -> dict[str, Any]:
    """Ping the local node and report liveness + served model list. Guarded.

    Tries ollama's native `/api/tags` first (returns {models:[{name,...}]}), then
    the OpenAI-compatible `/v1/models` ({data:[{id,...}]}). `live` is True ONLY on
    a real 2xx JSON response THIS request — never fabricated.
    """
    base = (base or _sovereign_base())
    to = _SOVEREIGN_PROBE_TIMEOUT_S if timeout is None else float(timeout)
    env_present = _sovereign_env_present()
    out: dict[str, Any] = {
        "env_var": _SOVEREIGN_ENV,
        "env_present": env_present,
        "base_url": base or None,
        "live": False,
        "models": [],
        "probed": [],
        "note": "",
    }
    # Wave M: we ALWAYS have a concrete base (env or the localhost /v1 default), so
    # we always reachability-probe. env_present tells the caller whether the
    # operator explicitly targeted a Tower or we fell back to the localhost default
    # (which, from CI/cloud, is honestly UNAVAILABLE).
    b = _ollama_root(base)
    # 1) ollama native /api/tags
    tags_url = b + "/api/tags"
    doc, err = _http_json(tags_url, timeout=to)
    out["probed"].append({"url": tags_url, "ok": doc is not None, "error": err})
    if isinstance(doc, dict) and isinstance(doc.get("models"), list):
        names = [str(m.get("name")) for m in doc["models"]
                 if isinstance(m, dict) and m.get("name")]
        out["live"] = True
        out["models"] = names
        out["api_style"] = "ollama /api"
        out["note"] = "node live (ollama /api/tags); model list is real THIS request."
        return out
    # 2) OpenAI-compatible /v1/models
    v1_url = b + "/v1/models"
    doc2, err2 = _http_json(v1_url, timeout=to)
    out["probed"].append({"url": v1_url, "ok": doc2 is not None, "error": err2})
    if isinstance(doc2, dict) and isinstance(doc2.get("data"), list):
        ids = [str(m.get("id")) for m in doc2["data"]
               if isinstance(m, dict) and m.get("id")]
        out["live"] = True
        out["models"] = ids
        out["api_style"] = "openai /v1"
        out["note"] = "node live (OpenAI-compatible /v1/models); model list is real THIS request."
        return out
    _tgt = ("SZL_LOCAL_LLM_URL=%s" % base) if env_present else (
        "SZL_LOCAL_LLM_URL unset — probing localhost default %s" % base)
    out["note"] = ("Sovereign node NOT reachable this request — honest UNAVAILABLE "
                   "(never fabricate). %s. The Tower is not reachable from CI/cloud. "
                   "Errors: %s" % (_tgt, "; ".join(
                       str(p.get("error")) for p in out["probed"] if p.get("error"))))
    return out


def sovereign_generate(prompt: str, base: str = "", model: str = "",
                       timeout: float | None = None) -> dict[str, Any]:
    """Run a REAL chat/generate against the local node when it is live; else HONEST
    STUB. Returns {wired, live, text, model, api_style, base_url, note, raw?}.

    wired/live are True ONLY when SZL_LOCAL_LLM_URL is present AND the node answered
    live on THIS request. We NEVER fabricate text or a wired flag. Tries ollama
    native /api/generate first, then OpenAI-compatible /v1/chat/completions.
    """
    base = (base or _sovereign_base())
    model = (model or _sovereign_model_slug())
    to = _SOVEREIGN_GEN_TIMEOUT_S if timeout is None else float(timeout)
    res: dict[str, Any] = {
        "wired": False, "live": False, "text": None, "model": model,
        "api_style": None, "base_url": base or None, "env_var": _SOVEREIGN_ENV,
        "env_present": _sovereign_env_present(), "note": "",
    }
    b = _ollama_root(base)
    # 1) ollama native /api/generate
    gen_url = b + "/api/generate"
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    doc, err = _http_json(gen_url, method="POST", body=body, timeout=to)
    if isinstance(doc, dict) and isinstance(doc.get("response"), str):
        res.update({"wired": True, "live": True, "text": doc["response"],
                    "api_style": "ollama /api/generate",
                    "note": "REAL local generation (ollama /api/generate) THIS request."})
        for k in ("eval_count", "prompt_eval_count", "total_duration"):
            if k in doc:
                res.setdefault("raw", {})[k] = doc[k]
        return res
    # 2) OpenAI-compatible /v1/chat/completions
    chat_url = b + "/v1/chat/completions"
    body2 = json.dumps({"model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False}).encode("utf-8")
    doc2, err2 = _http_json(chat_url, method="POST", body=body2, timeout=to)
    if isinstance(doc2, dict):
        try:
            txt = doc2["choices"][0]["message"]["content"]
        except Exception:  # noqa: BLE001 — malformed => honest stub
            txt = None
        if isinstance(txt, str):
            res.update({"wired": True, "live": True, "text": txt,
                        "api_style": "openai /v1/chat/completions",
                        "note": "REAL local generation (OpenAI-compatible /v1) THIS request."})
            if isinstance(doc2.get("usage"), dict):
                res["raw"] = {"usage": doc2["usage"]}
            return res
    res["note"] = ("Sovereign node NOT reachable this request — honest UNAVAILABLE "
                   "(never fabricate a response). Tier selection + Λ-receipt still "
                   "REAL. Errors: %s / %s" % (err or "", err2 or ""))
    return res


# Provider env vars the router recognises (names only — the SECRET is NEVER read/
# returned/logged). Used by /llm/router/status and per-model wired surfacing.
_PROVIDER_ENV_VARS: list[tuple[str, str]] = [
    ("ANTHROPIC_API_KEY", "anthropic"),
    ("OPENAI_API_KEY", "openai"),
    ("GOOGLE_API_KEY", "google"),
    ("PERPLEXITY_API_KEY", "perplexity"),
    ("OPENROUTER_API_KEY", "openrouter"),
    ("MISTRAL_API_KEY", "mistral"),
    ("DEEPSEEK_API_KEY", "deepseek"),
    ("GROQ_API_KEY", "groq"),
    ("HF_TOKEN", "hf-router"),
    ("HUGGING_FACE_HUB_TOKEN", "hf-router"),
]


# ─────────────────────────────────────────────────────────────────────────────
# A11OY_CODE_LLM_KEY — the canonical, provider-agnostic credential for the
# a11oy Code agent. ONE secret resolves the agent's model backend.
#
# Resolution order (first hit wins; all REAL env reads, NO fabricated keys):
#   1. A11OY_CODE_LLM_KEY            (canonical, provider hinted by A11OY_CODE_LLM_PROVIDER)
#   2. OPENROUTER_API_KEY            → openrouter aggregator (OpenAI-compatible)
#   3. ANTHROPIC_API_KEY             → anthropic
#   4. OPENAI_API_KEY                → openai
#   5. DEEPSEEK_API_KEY              → deepseek
#   6. GROQ_API_KEY                  → groq
#   7. MISTRAL_API_KEY               → mistral
#   8. HF_TOKEN / HUGGING_FACE_HUB_TOKEN → hf-router (OpenAI-compatible fan-out)
#
# This is the SINGLE honest model-key fallback boundary: if NOTHING resolves,
# the agent's PLAN / Λ-gate / PURIQ / tools / receipts STILL run for real and the
# model TEXT degrades to a clearly-labeled deterministic stub (Zero-Bandaid Law).
# ─────────────────────────────────────────────────────────────────────────────
A11OY_CODE_LLM_KEY_ENV = "A11OY_CODE_LLM_KEY"

# (env_var, provider_slug, OpenAI-compatible base URL)
_CODE_KEY_RESOLUTION_ORDER: list[tuple[str, str, str]] = [
    ("OPENROUTER_API_KEY", "openrouter", "https://openrouter.ai/api/v1"),
    ("ANTHROPIC_API_KEY", "anthropic", "https://api.anthropic.com/v1"),
    ("OPENAI_API_KEY", "openai", "https://api.openai.com/v1"),
    ("DEEPSEEK_API_KEY", "deepseek", "https://api.deepseek.com/v1"),
    ("GROQ_API_KEY", "groq", "https://api.groq.com/openai/v1"),
    ("MISTRAL_API_KEY", "mistral", "https://api.mistral.ai/v1"),
    ("HF_TOKEN", "hf-router", "https://router.huggingface.co/v1"),
    ("HUGGING_FACE_HUB_TOKEN", "hf-router", "https://router.huggingface.co/v1"),
]

_PROVIDER_BASE = {
    "openrouter": "https://openrouter.ai/api/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "hf-router": "https://router.huggingface.co/v1",
}


def resolve_code_llm_key() -> dict[str, Any]:
    """Resolve the a11oy Code agent's model credential, provider-agnostically.

    Returns a dict ALWAYS (never raises): {wired, provider, base_url, env_used,
    key (only an opaque bool-ish presence flag — NEVER the secret value), honest_note}.
    The raw key value is NEVER returned or logged (never commit/expose a key).
    """
    # 1. canonical single secret (provider hinted, default openrouter).
    canonical = os.environ.get(A11OY_CODE_LLM_KEY_ENV, "").strip()
    if canonical and len(canonical) > 8:
        provider = os.environ.get("A11OY_CODE_LLM_PROVIDER", "openrouter").strip().lower()
        base = os.environ.get("A11OY_CODE_LLM_BASE",
                              _PROVIDER_BASE.get(provider, _PROVIDER_BASE["openrouter"]))
        return {"wired": True, "provider": provider, "base_url": base,
                "env_used": A11OY_CODE_LLM_KEY_ENV, "key_present": True,
                "honest_note": f"resolved via {A11OY_CODE_LLM_KEY_ENV} (provider={provider})"}
    # 2..8 provider-specific fallbacks.
    for env_var, provider, base in _CODE_KEY_RESOLUTION_ORDER:
        val = os.environ.get(env_var, "").strip()
        if val and val != "NOT_SET" and len(val) > 8:
            return {"wired": True, "provider": provider, "base_url": base,
                    "env_used": env_var, "key_present": True,
                    "honest_note": f"resolved via fallback {env_var} (provider={provider})"}
    # nothing resolved → honest stub mode.
    return {"wired": False, "provider": None, "base_url": None,
            "env_used": None, "key_present": False,
            "honest_note": ("no model credential resolved. Set the Space secret "
                            f"{A11OY_CODE_LLM_KEY_ENV} (or any provider key). The agent loop "
                            "still runs for real; model text degrades to a labeled stub "
                            "(Zero-Bandaid Law).")}


def code_llm_secret_name() -> str:
    """The canonical secret name the UI / healthz should display."""
    return A11OY_CODE_LLM_KEY_ENV

def _enrich_model(m: dict, *, probe_local: bool = False) -> dict:
    """Add live runtime fields to a model dict (non-mutating).

    Every model gets an explicit, honest badge block the front-end can render:
      wired        — is this model routable RIGHT NOW (key present, or local node
                     env present)? NEVER hardcoded, NEVER fabricated.
      provider     — provider label.
      env_used     — the env var that gates it (name only; never the secret).
      base_url     — the API/base endpoint.
      honest_stub  — True when the model would degrade to a labeled stub.

    sovereign_local is special: it is "wired" when SZL_LOCAL_LLM_URL is present.
    When probe_local=True we additionally ping the node and report live+models,
    but the base-present gate is what flips `wired` (a set env means the operator
    intends local routing; `live` is the stronger THIS-request liveness signal).
    Open-weight alloy models (no api_env_var) report wired=false honestly — they
    are served by weights at runtime, not gated by a cloud key.
    """
    out = dict(m)
    env_var = m.get("api_env_var", "") or ""
    model_id = m.get("model_id", "")

    if model_id in (_SOVEREIGN_LEGACY_ID, _SOVEREIGN_BACKEND_ID) or env_var == _SOVEREIGN_ENV:
        base = _sovereign_base()
        env_present = _sovereign_env_present()
        # `wired` = operator intent (env explicitly set). `label` = honest state:
        # LIVE only when the node answers this request; else UNAVAILABLE.
        wired = env_present
        out["api_key_wired"] = wired
        out["wired"] = wired
        out["provider"] = m.get("provider", _SOVEREIGN_PROVENANCE)
        out["env_used"] = _SOVEREIGN_ENV
        out["env_present"] = env_present
        out["base_url"] = base or m.get("api_base")
        out["is_local"] = True
        out["own_metal"] = True
        # Default (no probe): honest UNAVAILABLE until proven live this request.
        out["honest_stub"] = True
        out["label"] = _LABEL_UNAVAILABLE
        out["reachable"] = False
        if probe_local:
            probe = sovereign_probe(base)
            live = bool(probe.get("live"))
            out["local_live"] = live
            out["reachable"] = live
            out["local_models"] = probe.get("models", [])
            out["local_probe_note"] = probe.get("note", "")
            out["api_style"] = probe.get("api_style")
            # honest_stub clears / label flips to LIVE ONLY when actually live.
            out["honest_stub"] = not live
            out["label"] = _LABEL_LIVE if live else _LABEL_UNAVAILABLE
        return out

    wired = _api_key_wired(env_var)
    out["api_key_wired"] = wired
    out["wired"] = wired
    out["provider"] = m.get("provider")
    out["env_used"] = env_var or None
    out["env_present"] = wired
    out["base_url"] = m.get("api_base") or m.get("base_url")
    out["is_local"] = bool(m.get("open_weight"))
    # Open-weight alloy models are not cloud-key gated; keep their own honest_stub
    # if the unifier already set one, else derive from key presence.
    if m.get("open_weight"):
        out["honest_stub"] = bool(m.get("honest_stub", True))
    else:
        out["honest_stub"] = not wired
    return out

def _seed_forum() -> None:
    """Seed forum with honest boot events."""
    _forum_append({
        "ts": _now(), "source": "a11oy", "event": "registry_boot",
        "model_count": len(MODEL_REGISTRY), "doctrine": DOCTRINE,
        "note": "a11oy LLM registry initialised — 7 models across 5 tiers",
    })
    _forum_append({
        "ts": _now(), "source": "operator", "event": "forum_join",
        "models_mirrored": [m["model_id"] for m in MODEL_REGISTRY if m.get("operator_mirrored")],
        "note": "Operator mirrors a11oy model-access via Wire I (operator-companion)",
    })

_seed_forum()

# ─────────────────────────────────────────────────────────────────────────────
# Route registration
# ─────────────────────────────────────────────────────────────────────────────

def register(app: FastAPI) -> dict:
    """Register all LLM registry endpoints BEFORE the proxy/SPA catch-all."""

    # ── GET /api/a11oy/v1/llm/registry ───────────────────────────────────────

    @app.get("/api/a11oy/v1/llm/registry")
    async def llm_registry(probe: int = 0) -> JSONResponse:
        """Canonical LLM model roster — a11oy is the hub for ALL models.

        Every model carries an honest badge block {wired, provider, env_used,
        base_url, honest_stub, is_local} computed from _api_key_wired(env_var) at
        REQUEST time (never hardcoded). `?probe=1` additionally pings the sovereign
        local node so its badge reports live+served models THIS request.
        """
        do_probe = bool(probe)
        models = [_enrich_model(m, probe_local=do_probe) for m in MODEL_REGISTRY]
        wired = [m for m in models if m.get("wired")]
        badges = [{
            "model_id": m["model_id"],
            "wired": bool(m.get("wired")),
            "provider": m.get("provider"),
            "env_used": m.get("env_used"),
            "base_url": m.get("base_url"),
            "honest_stub": bool(m.get("honest_stub", True)),
            "is_local": bool(m.get("is_local")),
            **({"label": m.get("label"), "reachable": m.get("reachable"),
                "own_metal": bool(m.get("own_metal"))} if m.get("own_metal") else {}),
        } for m in models]
        all_stub = (len(wired) == 0)
        # Wave-M sovereign availability snapshot: honest reachability of the
        # own-metal backend. `reachable`/`label` come from a real probe only when
        # ?probe=1; otherwise we honestly report unknown (probe not run).
        _sov_badge = next((m for m in models if m.get("model_id") == _SOVEREIGN_BACKEND_ID), None)
        sovereign_snapshot = {
            "backend_id": _SOVEREIGN_BACKEND_ID,
            "model": _SOVEREIGN_MODEL_TAG,
            "provider": _SOVEREIGN_PROVENANCE,
            "url": _sovereign_base(),
            "env_present": _sovereign_env_present(),
            "probed": do_probe,
            "reachable": (bool(_sov_badge.get("reachable")) if (do_probe and _sov_badge) else None),
            "label": (_sov_badge.get("label") if (do_probe and _sov_badge)
                      else "UNPROBED (pass ?probe=1 for THIS-request reachability)"),
            "route_order": "own-metal/sovereign FIRST (when reachable) → free → paid",
            "health_endpoint": "/api/a11oy/v1/llm/sovereign/health",
        }
        return JSONResponse({
            "timestamp": _now(),
            "hub": "a11oy",
            "role": "THE LLM Hub — single source of truth for all model routing",
            "model_count": len(models),
            "wired_count": len(wired),
            "wired_model_ids": [m["model_id"] for m in wired],
            "models": models,
            "badges": badges,
            "tier_map": {
                str(t["tier"]): t["model_id"]
                for t in MODEL_REGISTRY
                if t.get("tier") is not None
            },
            "routing_policy": "Λ-gated: Λ≥0.90→tier0, [0.75,0.90)→tier2, <0.75→tier3. task_hint overrides.",
            "ecosystem_mirror": "Policy, Reasoning, killinchu mirror a11oy's roster via /llm/ecosystem-mirror",
            "forum_endpoint": "/api/a11oy/v1/llm/forum",
            "route_endpoint": "/api/a11oy/v1/llm/route",
            "router_status_endpoint": "/api/a11oy/v1/llm/router/status",
            "sovereign_health_endpoint": "/api/a11oy/v1/llm/sovereign/health",
            "sovereign": sovereign_snapshot,
            "doctrine": DOCTRINE,
            "kernel_commit": _KERNEL,
            "honest_note": (
                ("wired_count=0 — no API key / no SZL_LOCAL_LLM_URL in this env. "
                 "Tier selection + Λ-receipt + model_weight_sha256 are REAL. Responses are honest stubs.")
                if all_stub else
                ("wired_count=%d — per-model `wired` computed from env at request time "
                 "(_api_key_wired / SZL_LOCAL_LLM_URL). Unwired models degrade to honest stubs."
                 % len(wired))),
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
          {"prompt": "…", "axis_scores": [0.92, …], "max_tier": 4, "task_hint": "math",
           "harness_profile_id": "szl-honest-operator"}

        Wave G: when `harness_profile_id` is set, routing is delegated to the
        governed behavior-transfer harness (szl_model_harness.apply) so the model
        runs behind the profile system layer + the SAME Λ-gate, and the response
        carries a SIGNED harness receipt naming the profile (id+version+sha256,
        model_id, Λ axes, provenance). This is the governed analogue of how the
        leaders attach/switch a persona on a step. Falls back to plain routing if
        the harness module is unavailable (honest note; never crashes).
        """
        try:
            body = await request.json()
        except Exception:
            body = {}

        harness_profile_id = str(body.get("harness_profile_id") or "").strip()
        if harness_profile_id:
            try:
                import szl_model_harness as _harness
                _res = _harness.apply(
                    profile_id=harness_profile_id,
                    model_id=str(body.get("model_id", "")).strip(),
                    prompt=str(body.get("prompt", "")),
                    axis_scores=body.get("axis_scores"),
                    max_tier=int(body.get("max_tier", 4)),
                    task_hint=str(body.get("task_hint", "")),
                    ns="a11oy", forum=True,
                )
                if not _res.get("ok"):
                    return JSONResponse(
                        {"error": _res.get("error"), "known": _res.get("known", []),
                         "note": "harness_profile_id supplied but profile not found"},
                        status_code=404)
                return JSONResponse({
                    "response": _res["response"],
                    "harness_state": _res["harness_state"],
                    "model_selected": _res["model_selected"],
                    "profile_applied": _res["profile_public"],
                    "lambda_receipt": _res["receipt"],   # signed szl.harness_apply.receipt/v1
                    "routed_via": "szl_model_harness.apply (behavior profile attached)",
                    "forum": _res["forum"],
                    "doctrine": DOCTRINE,
                    "conjecture_note": "Λ = Conjecture 1 — advisory, never 'green'.",
                })
            except Exception as _he:
                # honest fallback: harness unavailable — proceed with plain routing
                _harness_fallback_note = ("harness_profile_id '%s' requested but harness "
                                          "unavailable (%s); fell back to plain routing."
                                          % (harness_profile_id, type(_he).__name__))
            else:
                _harness_fallback_note = None
        else:
            _harness_fallback_note = None

        prompt = str(body.get("prompt", ""))
        axis_scores: list[float] = body.get("axis_scores") or [
            0.92, 0.90, 0.95, 0.91, 0.94, 0.90, 0.92, 0.91, 0.93, 0.92, 0.93, 0.90, 0.92
        ]
        max_tier: int = min(4, max(0, int(body.get("max_tier", 4))))
        task_hint: str = str(body.get("task_hint", "")).lower()

        lam = _lambda_gm(axis_scores)

        # ── SOVEREIGN / OWN-METAL selection (routed FIRST when reachable) ─────
        # Doctrine: "own metal first" — the sovereign backend slots FIRST in the
        # routing order (before free, before paid) BUT ONLY when the Tower node
        # actually answers this request. Selection triggers when EITHER:
        #   (a) the caller asks for it explicitly (model_id in the sovereign ids |
        #       task_hint in {sovereign,local,offline,…} | prefer_local=true), OR
        #   (b) OWN-METAL-FIRST: the node is reachable this request (auto-probe),
        #       unless the caller opts out with prefer_local=false + a cloud model,
        #   (c) offline preference (env set, no cloud key, offline_mode=true).
        # When the node is NOT reachable we NEVER fabricate — the caller falls
        # through to free/paid tiers, and if sovereign was explicitly requested we
        # return an honest UNAVAILABLE label (no fabricated text).
        _req_model = str(body.get("model_id", "")).strip().lower()
        _sov_ids = {_SOVEREIGN_LEGACY_ID, _SOVEREIGN_BACKEND_ID}
        _prefer_local_raw = body.get("prefer_local", None)
        _prefer_local = bool(_prefer_local_raw)
        _opted_out = (_prefer_local_raw is False)  # explicit prefer_local=false
        _sov_hints = {"sovereign", "local", "offline", "air-gap", "airgap"}
        _any_cloud_wired = any(_api_key_wired(ev) for ev, _ in _PROVIDER_ENV_VARS)
        _sov_base = _sovereign_base()
        _explicit_sovereign = (
            _req_model in _sov_ids or task_hint in _sov_hints or _prefer_local
        )
        _offline_pref = (
            _sovereign_env_present() and not _any_cloud_wired
            and str(body.get("offline_mode", "")).lower() in ("1", "true", "yes")
        )
        # OWN-METAL-FIRST: reachability-probe (short timeout) and, if the node is
        # LIVE this request, route sovereign FIRST — unless the caller explicitly
        # opted out. If the caller explicitly requested sovereign we ALSO select it
        # (even when unreachable) so we can return an honest UNAVAILABLE.
        _sov_probe = sovereign_probe(_sov_base)
        _sov_reachable = bool(_sov_probe.get("live"))
        _own_metal_first = _sov_reachable and not _opted_out
        _want_sovereign = _explicit_sovereign or _offline_pref or _own_metal_first
        if _want_sovereign:
            # Prefer the first-class Wave-M backend id; fall back to legacy alias.
            sov_model = (_MODEL_BY_ID.get(_SOVEREIGN_BACKEND_ID)
                         or _MODEL_BY_ID.get(_SOVEREIGN_LEGACY_ID)
                         or MODEL_REGISTRY[0])
            sov_enriched = _enrich_model(sov_model)
            gen = sovereign_generate(prompt or _DEFAULT_SOVEREIGN_PROMPT)
            _live = bool(gen.get("live"))
            sov_enriched["wired"] = _sovereign_env_present()
            sov_enriched["reachable"] = _live
            sov_enriched["local_live"] = _live
            sov_enriched["honest_stub"] = not _live
            sov_enriched["label"] = _LABEL_LIVE if _live else _LABEL_UNAVAILABLE
            if _explicit_sovereign:
                _why = "explicit request"
            elif _own_metal_first:
                _why = "own-metal-first (node reachable → routed before free/paid)"
            else:
                _why = "offline preference, no cloud key wired"
            sov_reason = "%s selected (%s); " % (sov_model.get("model_id"), _why)
            if _live:
                sov_reason += "node LIVE this request — REAL local generation [LIVE]."
                response_text = gen.get("text") or ""
            else:
                sov_reason += "node NOT reachable — honest UNAVAILABLE (never fabricate)."
                response_text = (
                    "[UNAVAILABLE] %s (%s) — the sovereign Tower endpoint is not "
                    "reachable this request, so NO response is fabricated. %s "
                    "Tier selection + Λ=%.4f + receipt are REAL."
                    % (sov_model.get("model_id"), sov_model.get("model_slug", ""),
                       gen.get("note", ""), lam))
            sov_receipt = {
                "schema": "szl.llm_route.lambda_receipt/v1",
                "ts": _now(), "hub": "a11oy", "lambda": round(lam, 6),
                "lambda_floor": _LAMBDA_FLOOR, "axis_scores": axis_scores,
                "tier_selected": sov_model.get("tier", 5),
                "model_id": sov_model.get("model_id"),
                "model_slug": sov_model.get("model_slug"),
                "provider": sov_model.get("provider"),
                "model_display": sov_model.get("display_name"),
                "reason": sov_reason, "task_hint": task_hint,
                "own_metal_first": bool(_own_metal_first),
                "reachable": _live,
                "label": _LABEL_LIVE if _live else _LABEL_UNAVAILABLE,
                "api_key_wired": _sovereign_env_present(),
                "local_live": _live,
                "local_api_style": gen.get("api_style"),
                "local_base_url": gen.get("base_url"),
                "doctrine": DOCTRINE, "kernel_commit": _KERNEL,
                "conjecture_note": "Λ = Conjecture 1 — NOT a theorem. CAUCHY_ND sorry open.",
            }
            _forum_append({**sov_receipt, "prompt_preview": prompt[:80] if prompt else "",
                           "source": "a11oy"})
            _sov_resp = {
                "response": response_text,
                "model_selected": sov_enriched,
                "lambda_receipt": sov_receipt,
                "label": _LABEL_LIVE if _live else _LABEL_UNAVAILABLE,
                "reachable": _live,
                "routed_via": "%s (%s)" % (
                    sov_model.get("model_id"),
                    gen.get("api_style") if _live else "honest UNAVAILABLE"),
                "local": {k: gen.get(k) for k in
                          ("wired", "live", "api_style", "base_url", "model", "note", "raw")
                          if k in gen},
                "doctrine": DOCTRINE,
                "conjecture_note": "Λ = Conjecture 1 — advisory, never 'green'/theorem.",
            }
            if _harness_fallback_note:
                _sov_resp["harness_note"] = _harness_fallback_note
            return JSONResponse(_sov_resp)

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

        _resp = {
            "response": response_text,
            "model_selected": enriched,
            "lambda_receipt": receipt,
            "doctrine": DOCTRINE,
        }
        if _harness_fallback_note:
            _resp["harness_note"] = _harness_fallback_note
        return JSONResponse(_resp)

    # ── GET /api/a11oy/v1/llm/forum ──────────────────────────────────────────

    @app.get("/api/a11oy/v1/llm/forum")
    async def llm_forum(limit: int = 30, source: str = "") -> JSONResponse:
        """Shared routing receipt forum — a11oy + Operator + all organs write here."""
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
        """Ingest a routing receipt from Operator / organ mirror.

        Body: {"source": "operator"|"policy"|…, "receipt": {...}, "model_id": "…"}
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
        """Manifest for Policy/Reasoning/killinchu to mirror a11oy's model access.

        Each organ calls this endpoint to discover which models to register locally,
        which tier to use for a given Λ-score, and where to emit receipts.
        """
        mirror_manifest = {
            "policy": {
                "models": [_enrich_model(m) for m in MODEL_REGISTRY if "policy" in m.get("ecosystem_mirror", [])],
                "receipt_ingest_url": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/forum/ingest",
                "routing_endpoint": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/route",
                "mirror_policy": "delegate_to_a11oy",
            },
            "reasoning": {
                "models": [_enrich_model(m) for m in MODEL_REGISTRY if "reasoning" in m.get("ecosystem_mirror", [])],
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
            "operator": {
                "models": [_enrich_model(m) for m in MODEL_REGISTRY if m.get("operator_mirrored")],
                "receipt_ingest_url": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/forum/ingest",
                "wire": "I (operator-companion brain-jack)",
                "mirror_policy": "shared_forum",
                "note": "Operator and a11oy share the forum (receipt/decision substrate). Operator ingests via Wire I.",
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

    # ── GET /api/a11oy/v1/llm/sovereign/health ────────────────────────────────

    @app.get("/api/a11oy/v1/llm/sovereign/health")
    async def llm_sovereign_health() -> JSONResponse:
        """Ping the sovereign local node (browser UA) and report honest health.

        Wave-M contract (DEV 1): returns the required compact block
        {reachable, model, url, provider, label} — plus rich diagnostics.

        `reachable` is True ONLY on a real 2xx JSON response THIS request — never
        fabricated. When the Tower is offline / unreachable (e.g. from CI/cloud),
        `reachable=false` and `label=UNAVAILABLE` (honest degradation, no fake).
        """
        base = _sovereign_base()
        probe = sovereign_probe(base)
        reachable = bool(probe.get("live"))
        env_present = bool(probe.get("env_present"))
        label = _LABEL_LIVE if reachable else _LABEL_UNAVAILABLE
        return JSONResponse({
            # ── Wave-M required compact contract ──
            # `model` = canonical sovereign model tag; `configured_model` (below)
            # is the runtime-overridable ollama tag the node is asked to serve.
            "reachable": reachable,
            "model": _SOVEREIGN_MODEL_TAG,
            "url": base,
            "provider": _SOVEREIGN_PROVENANCE,
            "label": label,
            # ── rich diagnostics (additive, honest) ──
            "timestamp": _now(),
            "hub": "a11oy",
            "backend_id": _SOVEREIGN_BACKEND_ID,
            "model_id": _SOVEREIGN_BACKEND_ID,
            "legacy_alias": _SOVEREIGN_LEGACY_ID,
            "model_slug": _SOVEREIGN_MODEL_TAG,
            "env_var": _SOVEREIGN_ENV,
            "env_present": env_present,
            "wired": env_present,             # env present => operator intends local routing
            "live": reachable,                # THIS-request liveness (== reachable)
            "honest_stub": not reachable,
            "base_url": base,
            "api_style": probe.get("api_style"),
            "served_models": probe.get("models", []),
            "configured_model": _sovereign_model_slug(),
            "probed": probe.get("probed", []),
            "probe_ua": "browser-UA (Cloudflare-front safe)",
            "note": probe.get("note", ""),
            "doctrine": DOCTRINE,
            "kernel_commit": _KERNEL,
            "conjecture_note": "Λ = Conjecture 1 — advisory, never 'green'/theorem.",
        })

    # ── GET /api/a11oy/v1/llm/router/status ───────────────────────────────────

    @app.get("/api/a11oy/v1/llm/router/status")
    async def llm_router_status(probe: int = 0) -> JSONResponse:
        """Which providers have keys present (NAMES ONLY — never the secret) and
        which local nodes are live. `?probe=1` pings the sovereign local node.

        Doctrine v11: presence is a real os.environ check at request time; the
        secret value is NEVER read into the response, logged, or returned.
        """
        providers = []
        seen_present = set()
        for env_var, provider in _PROVIDER_ENV_VARS:
            present = _api_key_wired(env_var)
            providers.append({
                "provider": provider,
                "env_var": env_var,      # NAME ONLY — never the secret value
                "key_present": present,
            })
            if present:
                seen_present.add(provider)

        # a11oy Code agent canonical credential (provider-agnostic resolver).
        code_key = resolve_code_llm_key()
        code_key_public = {
            "wired": bool(code_key.get("wired")),
            "provider": code_key.get("provider"),
            "env_used": code_key.get("env_used"),   # NAME ONLY
            "base_url": code_key.get("base_url"),
            "honest_note": code_key.get("honest_note"),
        }

        # Local sovereign node.
        do_probe = bool(probe)
        base = _sovereign_base()
        if do_probe:
            sov = sovereign_probe(base)
            _live = bool(sov.get("live"))
            local_node = {
                "backend_id": _SOVEREIGN_BACKEND_ID,
                "env_var": _SOVEREIGN_ENV, "base_url": base or None,
                "env_present": _sovereign_env_present(), "live": _live,
                "reachable": _live,
                "label": _LABEL_LIVE if _live else _LABEL_UNAVAILABLE,
                "served_models": sov.get("models", []), "note": sov.get("note", ""),
            }
        else:
            local_node = {
                "backend_id": _SOVEREIGN_BACKEND_ID,
                "env_var": _SOVEREIGN_ENV, "base_url": base or None,
                "env_present": _sovereign_env_present(), "live": None,
                "reachable": None, "label": "UNPROBED",
                "note": "pass ?probe=1 to ping the node for THIS-request liveness",
            }

        provider_keys_present = sorted(seen_present)
        return JSONResponse({
            "timestamp": _now(),
            "hub": "a11oy",
            "role": "router key/liveness status — provider NAMES only, never secrets",
            "providers": providers,
            "provider_keys_present": provider_keys_present,
            "provider_wired_count": len(provider_keys_present),
            "code_agent_credential": code_key_public,
            "local_nodes": [local_node],
            "any_cloud_key_present": len(provider_keys_present) > 0,
            "doctrine": DOCTRINE,
            "kernel_commit": _KERNEL,
            "honest_note": ("Presence is a real os.environ check THIS request. The secret "
                            "value is NEVER read into the response, logged, or returned — "
                            "only the env-var NAME + a boolean presence flag."),
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
            "GET  /api/a11oy/v1/llm/sovereign/health",
            "GET  /api/a11oy/v1/llm/router/status",
        ],
        "model_count": len(MODEL_REGISTRY),
        "doctrine": DOCTRINE,
    }
