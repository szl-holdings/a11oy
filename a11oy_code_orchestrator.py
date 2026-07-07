# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
# Doctrine v11 (LOCKED). v12 (v11+PURIQ) is an experimental roadmap, NOT locked. Signed: Yachay.
# Built by: Perplexity Computer Agent.
"""
a11oy.code Conversational Orchestrator - additive backend module.

This module is ADDITIVE. It is imported by serve.py and mounted under
/api/a11oy/code/* . It touches NOTHING in the existing serve.py routes, gates,
or Doctrine numbers. If imports fail at runtime, serve.py wraps the include in a
try/except so the existing Brand Orchestration Layer keeps serving.

It implements the founder directive: "make it our own ... talk to a11oy ... do
everything you can do, at Opus 4.8 level ... orchestrate the other apps ... reach
outside."

Real inference path (verified 2026-06-01): the Hugging Face Router
(https://router.huggingface.co/v1) is OpenAI-API-compatible, supports streaming
and tool-calling, and transparently fans out to Groq / Together / Fireworks /
Cerebras / DeepInfra under one HF token. We use it as the live, credentialed
backend. Direct per-provider keys (TOGETHER_API_KEY, GROQ_API_KEY, ...) are read
from the environment if present and used preferentially; if absent we fall back
to the HF Router. If NO credential is present at all, the endpoint returns an
honest 503 (NO fake keys, NO mocks - Zero-Bandaid Law).

PURIQ master formula gate (every action):
    P(x,t) = argmax_{a in A} [ Lambda(x) * Yuyay_13(a) * exp(-beta * HUKLLA(a)) * prod_i Khipu_i(a) ]
We implement puriq_decide(action, context) -> Decision as a hard conjunctive gate:
 - Yuyay_13: 13-axis wisdom score; 2 sacred axes must be >= 0.95, 7 structural
   >= 0.90, 4 introspection >= 0.85. Any axis below floor => block (T09).
 - HUKLLA: tripwire count T01..T10; exp(-beta*count) penalty; T01 (chain break)
   and a non-empty critical tripwire set => hard halt.
 - Khipu: every action emits a chain-verified receipt (sha256 hash chain). No
   non-zero score without chain_verified=true (T01).
 - Lambda: product-of-axes aggregator (matches serve.py Lambda definition
   Lambda = prod x_i^w_i), bounded [0,1], monotone.
Threshold configurable via env A11OY_PURIQ_THRESHOLD (default 0.62).

Cross-session memory (Unay organ): SQLite store of conversations + messages +
per-user memory profile. On a new session a11oy.code reloads full context. Every
memory write is Khipu-receipted.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

# ---------------------------------------------------------------------------
# Additive agentic core (NEW shared modules). Guarded so a missing module can
# never break the existing orchestrator routes (Zero-Bandaid: degrade honestly).
# ---------------------------------------------------------------------------
try:
    # Prefer the installable shared substrate; fall back to the local vendored
    # copy if the package is absent (guarded — the outer except is the final net).
    try:
        from szl_substrate import a11oy_agent_loop as _agent  # governed FSM
    except Exception:
        import a11oy_agent_loop as _agent  # governed FSM
except Exception as _exc:  # pragma: no cover
    _agent = None
    _AGENT_IMPORT_ERROR = str(_exc)
else:
    _AGENT_IMPORT_ERROR = ""
try:
    import a11oy_org_rag as _orgrag  # agentic RAG over the org
except Exception as _exc:  # pragma: no cover
    _orgrag = None
    _ORGRAG_IMPORT_ERROR = str(_exc)
else:
    _ORGRAG_IMPORT_ERROR = ""
try:
    try:  # prefer the extracted substrate package; fall back to local copy
        from szl_substrate import szl_llm_registry as _llmreg  # A11OY_CODE_LLM_KEY resolver
    except Exception:
        import szl_llm_registry as _llmreg
except Exception:  # pragma: no cover
    _llmreg = None
try:
    import a11oy_mcp_client as _mcp  # Streamable-HTTP MCP client to hatun-mcp
except Exception:  # pragma: no cover
    _mcp = None
# Proven Energy Engine wiring (additive, fail-open). The energy-budget receipt
# module lands via PR #328 (feat/energy-budget-receipt) and the energy-signal
# feed via platform PR #356; import BOTH defensively so this orchestrator keeps
# serving (and stays ast-clean / self-testable) on a tree where neither is yet
# present. When they are, every governed turn emits a Bekenstein-gated receipt
# carrying the real energy_source/window. Energy figures stay SAMPLE/ESTIMATE.
try:
    import szl_energy_budget as _energy_budget  # PR #328 receipt + Bekenstein gate
except Exception:  # pragma: no cover - absent until #328 merges; degrade honestly
    _energy_budget = None
try:
    import energy_signal as _energy_signal  # PR #356 honest power-window feed
except Exception:  # pragma: no cover - absent until #356 merges; default grid
    _energy_signal = None
# Sovereign-energy instrumentation (Lane C): reads REAL J/token + carbon from the
# on-box vLLM /metrics ONLY when the live sovereign probe shows gpu_reachable, and
# splices joules_consumed + carbon_g_co2eq into EVERY signed turn receipt — honestly
# labeled MEASURED (real fresh exporter) or ROADMAP (no meter yet -> None, never faked).
try:
    import szl_energy_sovereign as _energy_sovereign  # Lane C J/token + carbon receipt fields
except Exception:  # pragma: no cover - absent until the module merges; degrade honestly
    _energy_sovereign = None

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HF_ROUTER_BASE = os.environ.get("HF_ROUTER_BASE", "https://router.huggingface.co/v1")


def _sovereign_base_url() -> str:
    """Resolve the configured sovereign/local OpenAI-compatible base URL.

    A11OY_BRAIN_URL is the canonical primary knob for pointing a11oy Code at an
    owned sovereign node (szl-router / on-box SGLang/vLLM, see
    docs SOVEREIGN_BRAIN_RUNBOOK). A11OY_MODEL_BASE_URL is kept as an accepted
    alias for backwards compatibility. Read at runtime (env-flip law). Returns ""
    when neither is set, so callers transparently fall back to the HF Router.

    HONESTY: this returns CONFIGURED INTENT only. sovereign:true is asserted
    elsewhere ONLY after _local_endpoint_reachable() confirms the node answers —
    a set-but-unreachable brain URL never inflates the posture.
    """
    return (os.environ.get("A11OY_BRAIN_URL")
            or os.environ.get("A11OY_MODEL_BASE_URL") or "").strip()


# Honest backend classification for /healthz. The agent runs on our own GPU when
# A11OY_BRAIN_URL/A11OY_MODEL_BASE_URL points at a NON-router endpoint (sovereign
# node via SGLang/vLLM), matching a11oy_code_engine.py's adapter. Never claims
# sovereign while still routing.
def _local_endpoint_reachable(base: str, timeout: float = 2.0) -> bool:
    """Quick liveness probe of a configured local/sovereign model endpoint.

    HONESTY GATE: setting A11OY_MODEL_BASE_URL is an INTENT, not proof the GPU is
    actually serving. We only claim sovereign:true when the endpoint's OpenAI-
    compatible /models (or root) actually answers. If it's set but unreachable
    (e.g. a tailnet endpoint the Space can't reach), we honestly report a router
    fallback instead of a false sovereign banner. Pure stdlib, short timeout,
    never raises. NOTE: this reflects ENDPOINT liveness; the chat-serving path
    wiring to this endpoint is tracked separately (see #324)."""
    import urllib.request as _u
    for path in ("/models", ""):
        try:
            req = _u.Request(base.rstrip("/") + path, method="GET")
            with _u.urlopen(req, timeout=timeout) as r:  # noqa: S310 (trusted op-set base)
                if 200 <= getattr(r, "status", r.getcode()) < 500:
                    return True
        except Exception:  # noqa: BLE001 - any failure => not reachable, stay honest
            continue
    return False


def _sovereign_inference_state() -> dict:
    base = (_sovereign_base_url() or os.environ.get("HF_ROUTER_BASE")
            or "https://router.huggingface.co/v1").rstrip("/")
    gpu = (os.environ.get("A11OY_GPU_LABEL") or "").strip()
    is_local = "router.huggingface.co" not in base
    if not has_inference_credential() and not is_local:
        return {"inference": "NO-CREDENTIAL", "mode": "deterministic_stub",
                "backend": "local-deterministic", "sovereign": False, "base_url": base}
    if is_local:
        # Only claim sovereign when the configured local endpoint actually answers.
        if _local_endpoint_reachable(base):
            d = {"inference": "self-hosted-gpu", "mode": "live", "backend": "generative",
                 "sovereign": True, "base_url": base}
            if gpu:
                d["gpu"] = gpu
            return d
        # Configured for local but unreachable -> stay HONEST: we're not sovereign,
        # and the live serving path falls back to the HF Router.
        d = {"inference": "hf-router-fallback", "mode": "live", "backend": "hf-router",
             "sovereign": False, "base_url": "https://router.huggingface.co/v1",
             "configured_local_base": base,
             "honest_note": ("A11OY_MODEL_BASE_URL is set to a local endpoint but it "
                             "is not reachable from this process right now, so turns "
                             "serve via the HF Router. NOT sovereign until the local "
                             "endpoint answers (see #324).")}
        if gpu:
            d["configured_gpu_label"] = gpu
        return d
    return {"inference": "hf-router", "mode": "live", "backend": "hf-router",
            "sovereign": False, "base_url": base}


def _serving_base() -> tuple[str, bool]:
    """Return (base_url, is_local) for the ACTUAL serving call (#324).

    Local ONLY when A11OY_MODEL_BASE_URL is a non-router endpoint AND it actually
    answers right now. Otherwise the HF Router. This MIRRORS
    _sovereign_inference_state's reachability gate so the SERVING path and the
    REPORTED posture can never disagree (no overclaim): sovereign:true in healthz
    <=> turns are actually served locally here. If a local base is configured but
    unreachable (e.g. an HF Space with no GPU, or a tailnet endpoint this process
    can't reach) we honestly fall back to the router AND report sovereign:false.
    """
    base = _sovereign_base_url().rstrip("/")
    if base and "router.huggingface.co" not in base and _local_endpoint_reachable(base):
        return base, True
    return HF_ROUTER_BASE, False


def _serving_provider() -> tuple[str, str]:
    """Return (provider_label, base_url) for the ACTUAL serving path (#324).

    Derived from _serving_base so the REPORTED provider can never contradict the
    real serving call (the overclaim closed by #324): when turns are actually
    served on the box GPU -> "self-hosted-gpu" + the local base; otherwise the HF
    Router. This is the single source of truth for the per-turn `provider` label
    in route() / the streaming receipt and for the honest provider in healthz
    key_resolution. NO behaviour change to serving — label only.
    """
    base, is_local = _serving_base()
    return ("self-hosted-gpu" if is_local else "hf-router"), base


# Tier -> locally-served model tag. When serving locally (is_local True) we
# translate the router model id to the tag the on-box server (Ollama/vLLM)
# actually exposes. Env-overridable so the box can set its exact served tags
# WITHOUT a code change (the only remaining step to flip a-11-oy.com sovereign).
# The ROUTER path always keeps the original router model ids untouched.
A11OY_LOCAL_MODEL_MAP = {
    "coder": os.environ.get("A11OY_LOCAL_CODE_MODEL", "qwen2.5-coder:7b"),
    "default": os.environ.get("A11OY_LOCAL_GENERAL_MODEL", "llama3.1:8b"),
}
try:  # full-map override, e.g. A11OY_LOCAL_MODEL_MAP_JSON='{"coder":"...","default":"..."}'
    _lmm_json = os.environ.get("A11OY_LOCAL_MODEL_MAP_JSON", "").strip()
    if _lmm_json:
        _lmm_over = json.loads(_lmm_json)
        if isinstance(_lmm_over, dict):
            A11OY_LOCAL_MODEL_MAP.update({str(k): str(v) for k, v in _lmm_over.items()})
except Exception:  # noqa: BLE001 - bad override never breaks serving; keep defaults
    pass


def _map_model_for_local(model: str) -> str:
    """Map a router model id to the locally-served tag (used ONLY when is_local).

    Code/high-tier coder models -> the coder tag; everything else -> the default
    general tag. Substring match on the router id ('coder'/'code') mirrors the
    A11OY_LOCAL_MODEL_MAP keys so the box can override tags via env.
    """
    low = (model or "").lower()
    if "coder" in low or "code" in low:
        return A11OY_LOCAL_MODEL_MAP.get("coder", model)
    return A11OY_LOCAL_MODEL_MAP.get("default", model)


def _serving_base_selftest() -> dict:
    """No-live-endpoint self-test for the #324 serving resolver (Zero-Bandaid).

    Exercises the two paths reachable WITHOUT a live GPU:
      (a) A11OY_MODEL_BASE_URL unset            -> (HF_ROUTER_BASE, False)
      (b) A11OY_MODEL_BASE_URL = bogus/unreach. -> (HF_ROUTER_BASE, False)
    The local-reachable path (-> (local, True)) cannot be exercised here because
    it requires an OpenAI-compatible server actually answering; that is the box
    step. Returns a dict of results; raises AssertionError on any mismatch.
    """
    saved = os.environ.get("A11OY_MODEL_BASE_URL")
    saved_brain = os.environ.get("A11OY_BRAIN_URL")
    out = {}
    try:
        os.environ.pop("A11OY_MODEL_BASE_URL", None)
        os.environ.pop("A11OY_BRAIN_URL", None)  # hermetic: alias must not leak in
        b0, l0 = _serving_base()
        assert (b0, l0) == (HF_ROUTER_BASE, False), f"unset path: {(b0, l0)}"
        out["unset"] = [b0, l0]
        # Bogus-unreachable local URL: reserved-TEST-NET-1 IP never answers.
        os.environ["A11OY_MODEL_BASE_URL"] = "http://192.0.2.1:11434/v1"
        b1, l1 = _serving_base()
        assert (b1, l1) == (HF_ROUTER_BASE, False), f"unreachable-local path: {(b1, l1)}"
        out["bogus_local"] = [b1, l1]
        # Header honesty (#324): local => no HF bearer; mapping picks coder vs default.
        # The token-bearing local case is covered by _gpu_token_headers_selftest below.
        saved_gpu = os.environ.get("A11OY_GPU_TOKEN")
        try:
            os.environ.pop("A11OY_GPU_TOKEN", None)
            assert "Authorization" not in _inference_headers(is_local=True)
        finally:
            if saved_gpu is None:
                os.environ.pop("A11OY_GPU_TOKEN", None)
            else:
                os.environ["A11OY_GPU_TOKEN"] = saved_gpu
        assert _map_model_for_local("Qwen/Qwen2.5-Coder-32B-Instruct") == \
            A11OY_LOCAL_MODEL_MAP["coder"]
        assert _map_model_for_local("meta-llama/Llama-3.1-8B-Instruct") == \
            A11OY_LOCAL_MODEL_MAP["default"]
        out["headers_local_no_bearer"] = True
        out["gpu_token"] = _gpu_token_headers_selftest()
        out["ok"] = True
    finally:
        if saved is None:
            os.environ.pop("A11OY_MODEL_BASE_URL", None)
        else:
            os.environ["A11OY_MODEL_BASE_URL"] = saved
        if saved_brain is None:
            os.environ.pop("A11OY_BRAIN_URL", None)
        else:
            os.environ["A11OY_BRAIN_URL"] = saved_brain
    return out


def _gpu_token_headers_selftest() -> dict:
    """No-live-endpoint self-test for the #327 A11OY_GPU_TOKEN local-auth wiring.

    forge_gpu_bringup.py emits an API-KEY-PROTECTED vLLM endpoint and tells the
    operator to set that key as the a11oy Space secret A11OY_GPU_TOKEN. Proves:
      - local + A11OY_GPU_TOKEN set -> Authorization: Bearer <token> sent.
      - local + A11OY_GPU_TOKEN unset/empty -> NO auth header (Ollama/no-key).
      - router path -> unchanged (still requires + sends the HF bearer).
    Reads at runtime (token-flip law). NEVER returns the token value.
    Raises AssertionError on any mismatch.
    """
    saved = os.environ.get("A11OY_GPU_TOKEN")
    out = {}
    try:
        # (a) vLLM-with-key: token present -> Bearer sent (value never logged).
        os.environ["A11OY_GPU_TOKEN"] = "vllm-selftest-sentinel-not-a-real-key"
        h_key = _inference_headers(is_local=True)
        assert h_key.get("Authorization") == \
            "Bearer vllm-selftest-sentinel-not-a-real-key", "local+key must Bearer"
        out["local_with_key_sends_bearer"] = True
        # (b) Ollama/no-key: token absent -> no auth header at all.
        os.environ.pop("A11OY_GPU_TOKEN", None)
        h_nokey = _inference_headers(is_local=True)
        assert "Authorization" not in h_nokey, "local+no-key must NOT send auth"
        out["local_without_key_no_auth"] = True
        # (c) empty/whitespace token treated as absent (no fabricated bearer).
        os.environ["A11OY_GPU_TOKEN"] = "   "
        assert "Authorization" not in _inference_headers(is_local=True), \
            "empty token must NOT send auth"
        out["local_empty_key_no_auth"] = True
    finally:
        if saved is None:
            os.environ.pop("A11OY_GPU_TOKEN", None)
        else:
            os.environ["A11OY_GPU_TOKEN"] = saved
    return out

# Candidate Space-secret names for the HF inference credential, in priority
# order. HF Spaces sometimes save the token under a non-standard key (e.g.
# 'Token'), so we read a broad set and strip stray quotes/whitespace. This list
# mirrors serve.py's _AC_TOKEN_NAMES so BOTH the public v1/code surface and this
# orchestrator resolve the SAME secret. Server-side only; never sent to browser.
_HF_TOKEN_NAMES = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HF_ROUTER_TOKEN",
                   "HF_API_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACEHUB_API_TOKEN",
                   "Token")


def _resolve_hf_token() -> str:
    """Resolve the HF inference token at RUNTIME (read os.environ on every call).

    TOKEN-FLIP FIX: HF Space secrets pasted into the secret store must take
    effect the INSTANT they are present, with zero code change. Reading the
    token at import time froze it to its startup value, so a token set after
    process start would never be seen by has_inference_credential() and Chaski
    would stay in the deterministic stub forever. Resolving live (like
    serve.py's _ac_hf_token) closes that gap. Strips stray quotes/whitespace.
    Honest: returns "" when genuinely absent (never fabricates a key).
    """
    for _name in _HF_TOKEN_NAMES:
        _v = os.environ.get(_name)
        if _v:
            _v = _v.strip().strip('"').strip("'").strip()
            if _v:
                return _v
    return ""


# Backward-compat snapshot of the token at import (some legacy call sites and
# diagnostics still reference the module global). Runtime decisions MUST use
# _resolve_hf_token() so a later-pasted secret is honoured without a redeploy.
HF_TOKEN = _resolve_hf_token()
PURIQ_THRESHOLD = float(os.environ.get("A11OY_PURIQ_THRESHOLD", "0.62"))
PURIQ_BETA = float(os.environ.get("A11OY_PURIQ_BETA", "4.0"))
DB_PATH = os.environ.get("A11OY_CODE_DB", "/app/data/a11oy_code.db")
SANDBOX_DIR = Path(os.environ.get("A11OY_CODE_SANDBOX", "/app/data/sandbox"))
ADMIN_KEY = os.environ.get("A11OY_CODE_ADMIN_KEY", "")  # gate for /v1/keys + system overrides

# Direct provider keys (optional). If present, preferred over HF router for that provider.
PROVIDER_KEYS = {
    "together": os.environ.get("TOGETHER_API_KEY", ""),
    "groq": os.environ.get("GROQ_API_KEY", ""),
    "fireworks": os.environ.get("FIREWORKS_API_KEY", ""),
    "deepinfra": os.environ.get("DEEPINFRA_API_KEY", ""),
    "cerebras": os.environ.get("CEREBRAS_API_KEY", ""),
}

# Governed SZL service-role base URLs (in-Space these are relative; orchestrator
# proxies). Keys are the honest role names exposed to the model/UI; env-var names
# are kept internal/legacy for deployment compatibility (never user-visible).
FLAGSHIP_BASES = {
    "reasoning": os.environ.get("AMARU_BASE", ""),
    "policy": os.environ.get("SENTRA_BASE", ""),
    "operator": os.environ.get("ROSIE_BASE", ""),
    "field-node": os.environ.get("KILLINCHU_BASE", ""),
}
# Accept role aliases used in the tool enum -> canonical FLAGSHIP_BASES key.
_ROLE_ALIASES = {"governance": "reasoning", "field-node": "field-node",
                 "policy": "policy", "operator": "operator", "reasoning": "reasoning"}

# Command-bus bases for cross-app orchestration (operator_shell_v4 POST
# /api/<organ>/v4/command). Keyed by organ/app name. Empty ⇒ honest gap until
# that Space ships its base URL secret.
APP_COMMAND_BASES = {
    "killinchu": os.environ.get("KILLINCHU_BASE", ""),
    "operator": os.environ.get("ROSIE_BASE", ""),
    "policy": os.environ.get("SENTRA_BASE", ""),
    "reasoning": os.environ.get("AMARU_BASE", ""),
    "governance": os.environ.get("AMARU_BASE", ""),
}

router = APIRouter(prefix="/api/a11oy/code", tags=["a11oy.code"])

# ---------------------------------------------------------------------------
# Seven-tier model table (mirrors A11OY_CODE_ROUTER_SPEC.md §3, by Yachay-extension)
# license_class: GREEN (Apache/MIT) | AMBER (Llama/Qwen/Gemma terms) | RED (API-only)
# All model ids are real Hugging Face repo ids routable by the HF Router.
# ---------------------------------------------------------------------------

# All primaries + fallbacks below were LIVE-PROBED against the HF Router on
# 2026-06-01 and confirmed to return HTTP 200 chat completions. Models that the
# router does NOT currently serve as chat models (Mistral-Small-24B, phi-4,
# Qwen3-235B, Llama-4-Scout/Maverick, gemma-3-27b, Llama-3.2-3B) were removed
# rather than left as bandaids. See A11OY_CODE_ROUTER_SPEC for the probe log.
TIERS: dict[str, dict[str, Any]] = {
    "T0": {"name": "Trivial / cached", "primary": "meta-llama/Llama-3.1-8B-Instruct",
           "fallbacks": ["Qwen/Qwen2.5-7B-Instruct"], "license": "AMBER",
           "cost_out": 0.08, "latency_ms": 400},
    "T1": {"name": "Small fast", "primary": "Qwen/Qwen2.5-7B-Instruct",
           "fallbacks": ["meta-llama/Llama-3.1-8B-Instruct"], "license": "AMBER",
           "cost_out": 0.30, "latency_ms": 600},
    "T2": {"name": "Standard", "primary": "meta-llama/Llama-3.3-70B-Instruct",
           "fallbacks": ["deepseek-ai/DeepSeek-V3-0324", "Qwen/Qwen2.5-72B-Instruct"],
           "license": "AMBER", "cost_out": 0.79, "latency_ms": 2000},
    "T3": {"name": "Code-specialized", "primary": "Qwen/Qwen2.5-Coder-32B-Instruct",
           "fallbacks": ["Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3-0324"],
           "license": "AMBER", "cost_out": 0.90, "latency_ms": 3000},
    "T4": {"name": "Reasoning-heavy", "primary": "deepseek-ai/DeepSeek-R1",
           "fallbacks": ["deepseek-ai/DeepSeek-V3-0324", "Qwen/Qwen2.5-72B-Instruct"],
           "license": "GREEN", "cost_out": 7.00, "latency_ms": 15000},
    "T5": {"name": "Long-context", "primary": "deepseek-ai/DeepSeek-V3-0324",
           "fallbacks": ["Qwen/Qwen2.5-72B-Instruct", "meta-llama/Llama-3.1-70B-Instruct"],
           "license": "GREEN", "cost_out": 0.30, "latency_ms": 10000},
    "T6": {"name": "Multimodal", "primary": "Qwen/Qwen2.5-VL-72B-Instruct",
           "fallbacks": ["meta-llama/Llama-3.3-70B-Instruct"], "license": "AMBER",
           "cost_out": 0.60, "latency_ms": 5000},
}

# Friendly model switcher catalog exposed to the UI (id -> tier).
MODEL_CATALOG = [
    {"id": "router-auto", "label": "Router picks (recommended)", "tier": "auto", "license": "mixed"},
    {"id": "meta-llama/Llama-3.3-70B-Instruct", "label": "Llama 3.3 70B", "tier": "T2", "license": "AMBER"},
    {"id": "deepseek-ai/DeepSeek-V3-0324", "label": "DeepSeek V3 (MIT)", "tier": "T2", "license": "GREEN"},
    {"id": "deepseek-ai/DeepSeek-R1", "label": "DeepSeek R1 reasoning (MIT)", "tier": "T4", "license": "GREEN"},
    {"id": "Qwen/Qwen2.5-Coder-32B-Instruct", "label": "Qwen2.5 Coder 32B", "tier": "T3", "license": "AMBER"},
    {"id": "Qwen/Qwen2.5-72B-Instruct", "label": "Qwen2.5 72B", "tier": "T2", "license": "AMBER"},
    {"id": "Qwen/Qwen2.5-VL-72B-Instruct", "label": "Qwen2.5-VL 72B (vision)", "tier": "T6", "license": "AMBER"},
    {"id": "Qwen/Qwen2.5-7B-Instruct", "label": "Qwen2.5 7B (fast)", "tier": "T1", "license": "AMBER"},
    {"id": "meta-llama/Llama-3.1-8B-Instruct", "label": "Llama 3.1 8B (fast)", "tier": "T0", "license": "AMBER"},
]

DEFAULT_SYSTEM_PROMPT = (
    "You are a11oy.code, the SZL Holdings conversational coding orchestrator. You "
    "answer at the highest available quality using a unified open-LLM router. You "
    "can orchestrate governed SZL services (Governance, Policy, Operator, Field-Node "
    "roles) and reach outside via GitHub, Hugging Face, web search/fetch/browse, a "
    "sandboxed shell, and a sandboxed filesystem - all of which are exposed to you "
    "as tools. Every action you take is gated by PURIQ (Yuyay 13-axis wisdom + "
    "HUKLLA tripwires) and receipted on the Khipu chain. Be precise, write clear "
    "code, cite sources, refuse cleanly when a gate denies, and prefer streaming. "
    "Never fabricate tool results."
)

# ---------------------------------------------------------------------------
# Khipu receipt chain (append-only sha256 chain; Noether: receipt-state conserved)
# ---------------------------------------------------------------------------

_KHIPU_GENESIS = "0" * 64
_khipu_tip = _KHIPU_GENESIS

# Reference to the host FastAPI app, captured in attach(app), so khipu_emit can
# co-sign receipts through the REAL DSSE signer (app.state.szl_emit_signed_receipt,
# wired by szl_provenance). Stays None outside the served app (CLI/tests), in
# which case receipts are the sha256 hash-chain only — still real, just not
# ECDSA-co-signed. NEVER fabricates a signature.
_app = None  # type: ignore[var-annotated]


def _dsse_cosign(body: dict[str, Any]) -> dict[str, Any]:
    """Best-effort DSSE co-sign of a Khipu receipt via the host signer.

    Honest by construction: the signer (szl_dsse via szl_provenance) labels the
    envelope UNSIGNED when no SZL_COSIGN_PRIVATE_PEM key is present, and produces
    a real ECDSA-P256/DSSE signature when it is. Returns {} when no signer is
    wired (CLI/test) so the sha256 chain stands alone. Never raises.
    """
    if _app is None:
        return {}
    emit = getattr(getattr(_app, "state", None), "szl_emit_signed_receipt", None)
    if not callable(emit):
        return {}
    try:
        node = emit({"schema": "szl.a11oy.code_receipt/v1", "op": body.get("action"),
                     "khipu_hash": body.get("hash"), "receipt_id": body.get("receipt_id")})
        return {"dsse_digest": node.get("digest"),
                "dsse_signed": bool(node.get("signed")),
                "dsse_index": node.get("index")}
    except Exception:
        return {}  # never break the turn over a signing hiccup


def khipu_emit(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Emit a chain-verified Khipu receipt. prod_i Khipu_i(a) requires chain_verified.

    The sha256 hash-chain is the integrity backbone. When the host app's DSSE
    signer is wired (served runtime), the receipt is ALSO co-signed (real
    ECDSA-P256 when the cosign key is present, honestly UNSIGNED otherwise) and
    the dsse_* fields are attached — making the 'signed receipt' label on live
    turns genuinely true rather than aspirational.
    """
    global _khipu_tip
    ts = time.time()
    body = {
        "receipt_id": str(uuid.uuid4()),
        "action": action,
        "ts": ts,
        "prev": _khipu_tip,
        "payload": payload,
    }
    h = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    body["hash"] = h
    body["chain_verified"] = True
    _khipu_tip = h
    body.update(_dsse_cosign(body))  # additive: dsse_digest/dsse_signed if a signer is wired
    try:
        _db_write_receipt(body)
    except Exception:
        pass  # receipt persistence is best-effort; in-memory chain still verifies
    return body


# ---------------------------------------------------------------------------
# PURIQ gate: Lambda * Yuyay_13 * exp(-beta*HUKLLA) * prod Khipu_i
# ---------------------------------------------------------------------------

# 13 Yuyay axes: 2 sacred, 7 structural, 4 introspection (HUKLLA-cross-linked).
YUYAY_AXES = [
    ("integrity", "sacred", 0.95), ("non_maleficence", "sacred", 0.95),
    ("competence", "structural", 0.90), ("transparency", "structural", 0.90),
    ("provenance", "structural", 0.90), ("proportionality", "structural", 0.90),
    ("reversibility", "structural", 0.90), ("authorization", "structural", 0.90),
    ("license_compliance", "structural", 0.90),
    ("self_consistency", "introspection", 0.85), ("calibration", "introspection", 0.85),
    ("instruction_hierarchy", "introspection", 0.85), ("humility", "introspection", 0.85),
]

# Tools that change state need a higher bar + 2-person Yuyay gate.
STATE_CHANGING_TOOLS = {
    "github_open_issue", "github_open_pr", "hf_push_file", "fs_write",
    "shell_exec", "flagship_call", "drone_command",
    # NEW agentic state-changing tools (higher bar + 2-person Yuyay gate):
    "apply_patch", "app_command",
}
# Tools that must hard-fail if they would touch IP-HOLD / locked surfaces.
HARD_DENY_PATTERNS = [
    re.compile(r"a11oy#?57", re.I),        # IP-HOLD a11oy#57
    re.compile(r"GitHub\s*Actions", re.I), # never via GH Actions
    re.compile(r"secrets\.HF_TOKEN", re.I),
]


def _yuyay_score(action: str, context: dict[str, Any]) -> tuple[float, dict[str, float], list[str]]:
    """Compute 13-axis Yuyay vector. Returns (lambda_product, axes, violations)."""
    axes: dict[str, float] = {}
    violations: list[str] = []
    risk = context.get("risk", "low")
    # Sacred axes (integrity / non-maleficence) reflect the ALIGNMENT of the
    # action, not its risk level: a high-risk-but-authorized-and-clean action is
    # still maximally aligned. They only drop on an explicit alignment fault.
    sacred_base = 0.40 if context.get("alignment_fault") else 0.98
    # Structural / introspection base is sensitive to risk (proportionality etc.)
    struct_base = {"low": 0.97, "medium": 0.94, "high": 0.92, "critical": 0.91}.get(risk, 0.94)
    authorized = bool(context.get("authorized", True))
    has_provenance = bool(context.get("has_provenance", True))
    license_ok = context.get("license_class", "GREEN") in ("GREEN", "AMBER")
    two_person = bool(context.get("two_person_attested", False))
    for name, kind, floor in YUYAY_AXES:
        v = sacred_base if kind == "sacred" else struct_base
        if name == "authorization":
            v = 0.97 if authorized else 0.40
        elif name == "provenance":
            v = 0.96 if has_provenance else 0.55
        elif name == "license_compliance":
            v = 0.97 if license_ok else 0.30
        elif name == "reversibility" and action in STATE_CHANGING_TOOLS:
            # state change without a 2-person attestation dips below the structural floor
            v = 0.93 if two_person else 0.80
        elif name == "proportionality" and risk == "critical":
            v = 0.91
        axes[name] = round(v, 4)
        if v < floor:
            violations.append(f"yuyay:{name}<{floor}")
    # Lambda = prod x_i^w_i (matches serve.py); equal weights -> geometric mean.
    w = 1.0 / len(axes)
    lam = math.prod(max(v, 1e-9) ** w for v in axes.values())
    return round(lam, 4), axes, violations


def _hukla_check(action: str, context: dict[str, Any]) -> tuple[int, list[str], bool]:
    """HUKLLA tripwires T01..T10. Returns (count, fired, hard_halt)."""
    fired: list[str] = []
    hard_halt = False
    text = json.dumps(context, default=str)
    # T01 receipt-chain break
    if not context.get("chain_verified", True):
        fired.append("T01")
        hard_halt = True
    # T05 PII (very rough heuristic; the dedicated egress/immune filter owns full PII)
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text):
        fired.append("T05")
    # T06 cost ceiling
    if context.get("est_cost_usd", 0.0) > context.get("max_cost_usd", 100.0):
        fired.append("T06")
    # T08 license / hard-deny (IP-HOLD a11oy#57, GH Actions, secrets.HF_TOKEN)
    for pat in HARD_DENY_PATTERNS:
        if pat.search(text):
            fired.append("T08")
            hard_halt = True
            break
    # T09 yuyay axis below floor handled by caller (passed in context)
    if context.get("yuyay_violations"):
        fired.append("T09")
    return len(fired), fired, hard_halt


def puriq_decide(action: str, context: dict[str, Any]) -> dict[str, Any]:
    """Run the PURIQ master formula as a hard conjunctive gate.

    Returns a Decision dict {allow, score, lambda, yuyay, hukla, threshold,
    reason, khipu_receipt}.
    """
    ctx = dict(context)
    lam, axes, yviol = _yuyay_score(action, ctx)
    ctx["yuyay_violations"] = yviol
    huk_count, huk_fired, hard_halt = _hukla_check(action, ctx)
    # Yuyay_13 conjunctive: any axis below floor => factor 0.
    yuyay_factor = 0.0 if yviol else lam
    hukla_factor = math.exp(-PURIQ_BETA * huk_count)
    khipu_factor = 1.0 if ctx.get("chain_verified", True) else 0.0
    score = lam * yuyay_factor * hukla_factor * khipu_factor
    # Two-person gate for state-changing ops.
    two_person_required = action in STATE_CHANGING_TOOLS
    two_person_ok = (not two_person_required) or bool(ctx.get("two_person_attested", False))
    allow = (
        score >= PURIQ_THRESHOLD
        and not hard_halt
        and not yviol
        and two_person_ok
    )
    if hard_halt:
        reason = f"HUKLLA hard halt: {','.join(huk_fired)}"
    elif yviol:
        reason = f"Yuyay axis below floor: {','.join(yviol)}"
    elif two_person_required and not two_person_ok:
        reason = "State-changing action requires 2-person Yuyay attestation (two_person_attested=true)."
    elif score < PURIQ_THRESHOLD:
        reason = f"PURIQ score {score:.3f} < threshold {PURIQ_THRESHOLD}"
    else:
        reason = "PURIQ gate passed."
    receipt = khipu_emit("puriq.decide", {
        "action": action, "allow": allow, "score": round(score, 4),
        "lambda": lam, "hukla_fired": huk_fired, "yuyay_violations": yviol,
    })
    return {
        "allow": allow,
        "score": round(score, 4),
        "lambda": lam,
        "yuyay_axes": axes,
        "yuyay_violations": yviol,
        "hukla_count": huk_count,
        "hukla_fired": huk_fired,
        "hukla_factor": round(hukla_factor, 4),
        "two_person_required": two_person_required,
        "threshold": PURIQ_THRESHOLD,
        "reason": reason,
        "khipu_receipt": {"receipt_id": receipt["receipt_id"], "hash": receipt["hash"],
                          "chain_verified": receipt["chain_verified"]},
    }


# ---------------------------------------------------------------------------
# Yuyay-13 quality score for a *completion* (the response-quality badge).
# Lightweight, deterministic, transparent. Real model-graded eval is a gap.
# ---------------------------------------------------------------------------

def yuyay13_response_score(text: str, tool_calls: list | None, latency_ms: int) -> float:
    if not text and not tool_calls:
        return 0.0
    n = len(text or "")
    length_axis = min(1.0, n / 400.0) if n else (0.9 if tool_calls else 0.0)
    has_structure = 1.0 if re.search(r"(\n[-*0-9]|```|\$)", text or "") else 0.85
    refusal_clean = 0.7 if re.search(r"\bI cannot\b|\bI can't\b", text or "") else 1.0
    latency_axis = 1.0 if latency_ms < 4000 else (0.9 if latency_ms < 12000 else 0.8)
    cited = 1.0 if re.search(r"https?://", text or "") else 0.92
    axes = [length_axis, has_structure, refusal_clean, latency_axis, cited]
    return round(sum(axes) / len(axes), 3)


# ---------------------------------------------------------------------------
# Router: deterministic tier selection (A11OY_CODE_ROUTER_SPEC.md §4)
# ---------------------------------------------------------------------------

def classify_task(messages: list[dict[str, Any]]) -> str:
    last = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content", "")
            last = c if isinstance(c, str) else json.dumps(c)
            break
    low = last.lower()
    if any(k in low for k in ("```", "refactor", "function", "bug", "stack trace", "compile", "def ", "class ")):
        return "code"
    if any(k in low for k in ("prove", "theorem", "step by step", "reason", "why does", "derive", "math")):
        return "reasoning"
    if len(last) < 80 and last.endswith("?"):
        return "short_qa"
    return "general"


def estimate_context_tokens(messages: list[dict[str, Any]]) -> int:
    chars = sum(len(json.dumps(m.get("content", ""))) for m in messages)
    return chars // 4


def has_image(messages: list[dict[str, Any]]) -> bool:
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and part.get("type") in ("image_url", "image"):
                    return True
    return False


def route(messages: list[dict[str, Any]], model: Optional[str], governance_tier: str,
          budget: dict[str, Any] | None) -> dict[str, Any]:
    """Pure deterministic route. Emits a Khipu route receipt."""
    _provider, _ = _serving_provider()
    if model and model != "router-auto":
        tier = next((m["tier"] for m in MODEL_CATALOG if m["id"] == model), "T2")
        lic = next((m["license"] for m in MODEL_CATALOG if m["id"] == model), "AMBER")
        decision = {"tier": tier if tier != "auto" else "T2", "model": model,
                    "provider": _provider, "license_class": lic,
                    "reason": "explicit model override"}
    else:
        ctx_tokens = estimate_context_tokens(messages)
        task = classify_task(messages)
        if has_image(messages):
            tier = "T6"
        elif ctx_tokens > 128_000:
            tier = "T5"
        elif task == "code":
            tier = "T3"
        elif task == "reasoning":
            tier = "T4"
        elif task == "short_qa":
            tier = "T1"
        else:
            tier = "T2"
        # governance_tier=sovereign forces a GREEN-license tier choice.
        spec = TIERS[tier]
        chosen_model = spec["primary"]
        chosen_lic = spec["license"]
        if governance_tier == "sovereign" and chosen_lic != "GREEN":
            # walk fallbacks for a GREEN one; else hard GREEN T2 DeepSeek (MIT)
            green = next((fb for fb in spec["fallbacks"]
                          if "deepseek" in fb.lower() or "mistral" in fb.lower() or "phi" in fb.lower()), None)
            chosen_model = green or "deepseek-ai/DeepSeek-V3-0324"
            chosen_lic = "GREEN"
        decision = {"tier": tier, "model": chosen_model, "provider": _provider,
                    "license_class": chosen_lic,
                    "reason": f"task={task} ctx={ctx_tokens} gov={governance_tier}"}
    decision["fallbacks"] = TIERS.get(decision["tier"], TIERS["T2"])["fallbacks"]
    decision["khipu_receipt"] = khipu_emit("router.route", decision)["hash"]
    return decision


# ---------------------------------------------------------------------------
# Inference client (HF Router, OpenAI-compatible). Streams + non-stream.
# Bounded fallback walk: primary -> fb1 -> fb2 -> refuse.
# ---------------------------------------------------------------------------

def _inference_headers(is_local: bool = False) -> dict[str, str]:
    # Local sovereign serving (#324/#327): an on-box OpenAI-compatible server.
    # Two supported box bring-up paths (forge_gpu_bringup.py is the recommended
    # one and stands up an API-KEY-PROTECTED vLLM OpenAI endpoint, emitting the
    # key as the a11oy Space secret A11OY_GPU_TOKEN):
    #   - vLLM-with-key: A11OY_GPU_TOKEN is set -> send Authorization: Bearer
    #     <that token> so the protected endpoint accepts the call (else 401).
    #   - Ollama/no-auth: no A11OY_GPU_TOKEN -> send ONLY Content-Type.
    # We NEVER fabricate a key (Zero-Bandaid Law) and NEVER require an HF token
    # to talk to our own GPU. The token is read at RUNTIME so a later-pasted
    # Space secret works with no redeploy (token-flip law).
    if is_local:
        gpu_token = (os.environ.get("A11OY_GPU_TOKEN") or "").strip()
        if gpu_token:
            return {"Authorization": f"Bearer {gpu_token}",
                    "Content-Type": "application/json"}
        return {"Content-Type": "application/json"}
    token = _resolve_hf_token()  # runtime read so a later-pasted secret works
    if not token:
        raise HTTPException(status_code=503, detail=(
            "No inference credential present. Set HF_TOKEN (or a provider key) as a "
            "Space secret. No fake key is used (Zero-Bandaid Law)."))
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _resolve_provider_keys() -> dict[str, str]:
    """Read optional direct-provider keys at RUNTIME (token-flip parity)."""
    return {k: os.environ.get(env, "") for k, env in (
        ("together", "TOGETHER_API_KEY"), ("groq", "GROQ_API_KEY"),
        ("fireworks", "FIREWORKS_API_KEY"), ("deepinfra", "DEEPINFRA_API_KEY"),
        ("cerebras", "CEREBRAS_API_KEY"))}


def has_inference_credential() -> bool:
    """True iff a real inference credential is present (HF router or a provider key).

    Resolved at RUNTIME: the live/stub branch must flip the INSTANT a token is
    pasted into the Space secret store, with zero code change (token-flip law).
    """
    return bool(_resolve_hf_token()) or any(_resolve_provider_keys().values())


def honest_stub_text(user_msg: str, decision: dict[str, Any]) -> str:
    """Deterministic, CLEARLY-LABELED stub. NEVER a fabricated model answer.

    Emitted only when NO inference credential is present. It states plainly that
    the model text is unavailable and that routing / Lambda / receipts are the
    real, deterministic parts. It does NOT invent a code answer.
    """
    snippet = (user_msg or "").strip().replace("\n", " ")[:160]
    return (
        "**[deterministic stub \u2014 inference token not yet set]**\n\n"
        "a11oy.code received your request"
        + (f" (\u201c{snippet}\u201d)" if snippet else "")
        + f" and routed it to tier **{decision.get('tier')}** \u2192 model "
        f"`{decision.get('model')}` (license {decision.get('license_class')}). "
        "The PURIQ \u039b-gate, tier selection and the signed Khipu receipt below are "
        "REAL deterministic math. The **model completion itself is unavailable** because no "
        "inference credential is configured on this Space \u2014 so no answer is fabricated "
        "(Zero-Bandaid Law).\n\n"
        "_To enable live generation, paste a valid token into the Space secret_ `HF_TOKEN` "
        "_(Settings \u2192 Variables and secrets). Generation then goes live instantly \u2014 no redeploy._"
    )


async def _call_model_stream(client: httpx.AsyncClient, model: str, payload: dict[str, Any]
                             ) -> AsyncGenerator[bytes, None]:
    base, is_local = _serving_base()  # #324: serve local when reachable, else router
    body = dict(payload)
    body["model"] = _map_model_for_local(model) if is_local else model
    body["stream"] = True
    async with client.stream("POST", f"{base}/chat/completions",
                             headers=_inference_headers(is_local), json=body, timeout=120.0) as resp:
        if resp.status_code != 200:
            err = await resp.aread()
            raise RuntimeError(f"provider {resp.status_code}: {err[:200]!r}")
        async for line in resp.aiter_lines():
            if line:
                yield (line + "\n").encode()


async def _call_model(client: httpx.AsyncClient, model: str, payload: dict[str, Any]) -> dict[str, Any]:
    base, is_local = _serving_base()  # #324: serve local when reachable, else router
    body = dict(payload)
    body["model"] = _map_model_for_local(model) if is_local else model
    body["stream"] = False
    resp = await client.post(f"{base}/chat/completions",
                             headers=_inference_headers(is_local), json=body, timeout=120.0)
    if resp.status_code != 200:
        raise RuntimeError(f"provider {resp.status_code}: {resp.text[:200]}")
    return resp.json()


async def agent_model_complete(messages: list[dict], **kw) -> dict[str, Any]:
    """model_complete callable injected into the agent loop's FINALIZE step.

    If a real inference credential is present, calls the live model (resilient
    fallback walk). Otherwise returns the CLEARLY-LABELED deterministic stub —
    the agentic control-flow already ran for real (Zero-Bandaid Law)."""
    if not has_inference_credential():
        last = next((m.get("content") for m in reversed(messages)
                     if m.get("role") == "user"), "")
        snippet = (last if isinstance(last, str) else json.dumps(last)).strip()[:160]
        stub_text = (
            "**[deterministic stub — inference token not yet set]**\n\n"
            "The a11oy Code agent's governed control-flow (plan DAG, per-step Λ-gate, "
            "PURIQ gate, typed evidence, signed Khipu receipts) executed FOR REAL. The "
            "model-authored synthesis is unavailable because no inference credential is "
            f"configured on this Space (set the secret {_code_secret_name()}), so no answer "
            "is fabricated (Zero-Bandaid Law)."
            + (f" Request: \u201c{snippet}\u201d." if snippet else ""))
        out = {"text": stub_text, "model": "deterministic-stub", "stub": True}
        rcpt = _emit_turn_receipt(stub_text, "deterministic-stub", False, True)
        if rcpt is not None:
            out["energy_receipt"] = rcpt
        return out
    client = _get_client()
    decision = route(messages, "router-auto", "standard", None)
    payload = {"messages": messages, "max_tokens": kw.get("max_tokens", 1200),
               "temperature": kw.get("temperature", 0.4)}
    candidates = [decision["model"], *decision.get("fallbacks", [])]
    _, is_local = _serving_base()  # honest sovereign posture for the receipt
    try:
        data, model_used = await _call_model_resilient(client, candidates, payload)
        text = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "") or ""
        out = {"text": text, "model": model_used, "stub": False}
        rcpt = _emit_turn_receipt(text, model_used, is_local, False)
        if rcpt is not None:
            out["energy_receipt"] = rcpt
        return out
    except Exception as exc:
        err_text = f"[honest error: live model call failed: {str(exc)[:200]}]"
        out = {"text": err_text, "model": "error", "stub": True}
        rcpt = _emit_turn_receipt(err_text, "error", is_local, True)
        if rcpt is not None:
            out["energy_receipt"] = rcpt
        return out


def _turn_energy_provenance(is_local: bool) -> dict:
    """Honest energy provenance for one turn (SAMPLE/ESTIMATE; never measured).

    Reads the live power WINDOW from the energy-signal feed (PR #356) when it is
    importable — the off-peak clock is a real, locally-verifiable fact, while the
    wholesale stub honestly stays "grid". When the feed is absent we default to
    "grid"/"normal". joules_est is left None (no meter; see doctrine v11/v12).
    Never raises.
    """
    if _energy_signal is not None:
        try:
            return _energy_signal.energy_provenance(joules_est=None)
        except Exception:  # noqa: BLE001 - feed hiccup must never taint the turn
            pass
    return {
        "energy_source": "grid",
        "window": "normal",
        "price_signal": None,
        "joules_est": None,
        "joules_est_label": "SAMPLE/ESTIMATE",
        "signal_provider": "none (energy_signal feed not present)",
        "honest_note": "energy_signal feed unavailable; conservative default.",
    }


def _emit_turn_receipt(text: str, model_used: str, is_local: bool,
                       stub: bool) -> Optional[dict]:
    """Record a Bekenstein-gated energy-budget receipt for ONE completed turn.

    FAIL-OPEN by construction: any error here is swallowed (logged via a khipu
    receipt only) so a receipt problem can NEVER break a user turn. Binds the
    turn's output size to the F19/TH6 Bekenstein bound (output_bytes*8) and
    attaches the honest energy_source/window from the signal feed. All energy
    figures are SAMPLE/ESTIMATE. Returns the receipt dict, or None when the
    energy-budget module (PR #328) is not present / on any failure.
    """
    if _energy_budget is None:
        return None
    try:
        prov = _turn_energy_provenance(is_local)
        out_bytes = len((text or "").encode("utf-8"))
        # Lane C: splice REAL J/token energy + carbon into EVERY signed receipt. The
        # helper reads the on-box vLLM /metrics ONLY when the live sovereign probe shows
        # gpu_reachable; otherwise it returns honest ROADMAP (joules_consumed=None). It
        # NEVER raises and NEVER fabricates a number (no meter -> no number).
        energy_fields = {}
        if _energy_sovereign is not None:
            try:
                energy_fields = _energy_sovereign.energy_fields_for_receipt() or {}
            except Exception:  # noqa: BLE001 - energy probe must never break a turn
                energy_fields = {"joules_consumed": None, "carbon_g_co2eq": None,
                                 "energy_label": "ROADMAP"}
        extra = {
            "turn": True,
            "model": model_used,
            "stub": bool(stub),
            "sovereign_local": bool(is_local),
            "window": prov.get("window", "normal"),
            "signal_provider": prov.get("signal_provider", "unknown"),
            # joules_consumed + carbon_g_co2eq on every receipt (MEASURED via a live GPU
            # exporter, else honest ROADMAP/None). joules_honesty is decided by
            # szl_joules_truth, never by a flag.
            "joules_consumed": energy_fields.get("joules_consumed"),
            "carbon_g_co2eq": energy_fields.get("carbon_g_co2eq"),
            "joules_per_token": energy_fields.get("joules_per_token"),
            "carbon_g_co2eq_per_token": energy_fields.get("carbon_g_co2eq_per_token"),
            "energy_label": energy_fields.get("energy_label", "ROADMAP"),
            "joules_honesty": energy_fields.get("joules_honesty", "sample"),
        }
        receipt = _energy_budget.track_task(
            output=text or "",
            energy_source=prov.get("energy_source", "grid"),
            joules_est=0.0,  # SAMPLE: no meter wired (joules_est_label carries it)
            extra=extra,
        )
        # The Bekenstein gate is the PROVEN F19/TH6 inequality (shannon<=n*8);
        # an honest receipt is always within_bound. Flag (never raise) if not.
        if not receipt.get("within_bound", True):
            khipu_emit("energy.receipt.overclaim", {
                "task_hash": receipt.get("task_hash"),
                "output_bytes": out_bytes,
                "shannon_bits": receipt.get("shannon_bits"),
                "bound": receipt.get("bekenstein_bound_bits"),
            })
        khipu_emit("energy.receipt", {
            "task_hash": receipt.get("task_hash"),
            "output_bytes": receipt.get("output_bytes"),
            "shannon_bits": receipt.get("shannon_bits"),
            "bekenstein_bound_bits": receipt.get("bekenstein_bound_bits"),
            "within_bound": receipt.get("within_bound"),
            "energy_source": receipt.get("energy_source"),
            "window": prov.get("window", "normal"),
            "joules_est": receipt.get("joules_est"),
            "joules_est_label": receipt.get("joules_est_label"),
            # Lane C live J/token energy + carbon (MEASURED via on-box exporter / ROADMAP).
            "joules_consumed": extra.get("joules_consumed"),
            "carbon_g_co2eq": extra.get("carbon_g_co2eq"),
            "energy_label": extra.get("energy_label"),
            "joules_honesty": extra.get("joules_honesty"),
        })
        return receipt
    except Exception as exc:  # noqa: BLE001 - NEVER break a turn over a receipt
        try:
            khipu_emit("energy.receipt.error", {"error": str(exc)[:200]})
        except Exception:
            pass
        return None


def _code_secret_name() -> str:
    if _llmreg is not None:
        try:
            return _llmreg.code_llm_secret_name()
        except Exception:
            pass
    return "A11OY_CODE_LLM_KEY"


def _agent_rag_query(q: str, **kw) -> dict[str, Any]:
    """rag_query callable injected into the agent loop's RETRIEVE step."""
    if _orgrag is None:
        return {"ok": False, "i_dont_know": True,
                "honest_error": "a11oy_org_rag not importable (honest)"}
    return _orgrag.query(q, k=kw.get("k", 6), emit_receipt=khipu_emit)


async def _call_model_resilient(
    client: httpx.AsyncClient, models: list[str], payload: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    """Bounded fallback walk over [primary, *fallbacks]. Returns (response, model_used).
    On rate-limit / unavailable-model / provider errors it advances to the next
    candidate and emits a Khipu router.fallback receipt. Raises only after the
    whole chain is exhausted (honest failure, never a fake completion)."""
    last_exc: Exception | None = None
    seen: set[str] = set()
    for m in models:
        if not m or m in seen:
            continue
        seen.add(m)
        try:
            data = await _call_model(client, m, payload)
            return data, m
        except Exception as exc:  # provider 4xx/5xx, timeout, etc.
            last_exc = exc
            _METRICS["router_fallbacks_total"] = _METRICS.get("router_fallbacks_total", 0) + 1
            khipu_emit("router.fallback", {"model": m, "error": str(exc)[:200]})
            continue
    raise RuntimeError(
        f"all candidates exhausted ({list(seen)}): {last_exc}"
    )


# ---------------------------------------------------------------------------
# Tool surface (OpenAI function-calling JSONSchema). Each tool: PURIQ gate +
# HUKLLA tripwire + Khipu receipt. NO mocks - tools that need a missing
# credential return an honest error.
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "web_search", "description": "Search the public web. Proxies the Space /search endpoint.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}, "k": {"type": "integer", "default": 5}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "web_fetch", "description": "Fetch and read a public URL.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "github_read_file", "description": "Read a file from a GitHub repo via gh CLI.",
        "parameters": {"type": "object", "properties": {
            "repo": {"type": "string", "description": "owner/name"},
            "path": {"type": "string"}, "ref": {"type": "string", "default": "HEAD"}},
            "required": ["repo", "path"]}}},
    {"type": "function", "function": {
        "name": "github_open_issue", "description": "Open a GitHub issue (state-changing; needs 2-person gate).",
        "parameters": {"type": "object", "properties": {
            "repo": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}},
            "required": ["repo", "title"]}}},
    {"type": "function", "function": {
        "name": "hf_read_space", "description": "List files / read metadata of a Hugging Face Space.",
        "parameters": {"type": "object", "properties": {"repo_id": {"type": "string"}}, "required": ["repo_id"]}}},
    {"type": "function", "function": {
        "name": "flagship_call", "description": "Call a governed SZL service role (governance/policy/operator/field-node).",
        "parameters": {"type": "object", "properties": {
            "organ": {"type": "string", "enum": ["governance", "policy", "operator", "field-node"]},
            "path": {"type": "string"}, "method": {"type": "string", "default": "GET"},
            "json": {"type": "object"}}, "required": ["organ", "path"]}}},
    {"type": "function", "function": {
        "name": "shell_exec", "description": "Run an allow-listed command in a sandboxed dir (no network, 30s).",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "fs_read", "description": "Read a file from the sandboxed workspace dir.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "fs_write", "description": "Write a file to the sandboxed workspace dir (state-changing).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "drone_command", "description": "Send a command to the Killinchu drone fleet (when shipped).",
        "parameters": {"type": "object", "properties": {
            "drone_id": {"type": "string"}, "command": {"type": "string"}},
            "required": ["drone_id", "command"]}}},
    # ---- NEW agentic tools (each routed to a REAL backend; NO mocks) ----
    {"type": "function", "function": {
        "name": "repo_map", "description": "Aider-style repo map: files + symbols ranked by Λ-weighted graph centrality (a11oy_org_rag).",
        "parameters": {"type": "object", "properties": {"repo": {"type": "string"}}, "required": ["repo"]}}},
    {"type": "function", "function": {
        "name": "code_search", "description": "Agentic RAG over the whole org (FTS5 + vector + Λ re-rank + HyDE). Low support ⇒ i_dont_know.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}, "k": {"type": "integer", "default": 6},
            "repo": {"type": "string"}, "hyde": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "github_open_pr", "description": "Open a GitHub pull request (state-changing; 2-person gate).",
        "parameters": {"type": "object", "properties": {
            "repo": {"type": "string"}, "title": {"type": "string"}, "head": {"type": "string"},
            "base": {"type": "string", "default": "main"}, "body": {"type": "string"}},
            "required": ["repo", "title", "head"]}}},
    {"type": "function", "function": {
        "name": "apply_patch", "description": "Apply a unified diff to a file in the sandboxed workspace (state-changing).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "diff": {"type": "string"}}, "required": ["path", "diff"]}}},
    {"type": "function", "function": {
        "name": "run_tests", "description": "Run a test command in the constrained sandbox (python3/pytest/node). Honest boundary.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "default": "python3 -m pytest -q"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "formula_call", "description": "Call a governed formula tool on hatun-mcp (e.g. szl_lean_verify, szl_puriq_evaluate) via the MCP client.",
        "parameters": {"type": "object", "properties": {
            "tool": {"type": "string"}, "args": {"type": "object"}}, "required": ["tool"]}}},
    {"type": "function", "function": {
        "name": "khipu_verify", "description": "Verify a Khipu receipt chain hash via hatun-mcp szl_khipu_verify.",
        "parameters": {"type": "object", "properties": {"receipt_hash": {"type": "string"}}, "required": ["receipt_hash"]}}},
    {"type": "function", "function": {
        "name": "app_command", "description": "Orchestrate another SZL app via the real command bus POST /api/<organ>/v4/command.",
        "parameters": {"type": "object", "properties": {
            "app": {"type": "string", "description": "organ/app name, e.g. killinchu, operator, policy"},
            "command": {"type": "string"}, "args": {"type": "object"}}, "required": ["app", "command"]}}},
]

SHELL_ALLOWLIST = {"ls", "cat", "echo", "wc", "head", "tail", "grep", "find", "python3", "node", "sort", "uniq"}

# ---------------------------------------------------------------------------
# Sandboxed code runner for the IDE "Run" button. HONEST safety boundary:
#  - only python3 / node interpreters (no arbitrary binaries)
#  - executed inside SANDBOX_DIR with a minimal PATH, NO network reachability is
#    promised (the Space process MAY have egress; we do NOT sandbox the network
#    at the kernel level here, so we LABEL that honestly rather than claim it)
#  - 8s wall-clock timeout, output truncated
# This is a constrained-interpreter runner, NOT a hardened multi-tenant jail.
# The label returned to the UI states the boundary plainly (no fake claims).
# ---------------------------------------------------------------------------
RUN_INTERPRETERS = {
    "python": ["python3", "-I", "-S"],   # -I isolated, -S no site
    "javascript": ["node"],
    "shell": None,   # shell handled via the allow-listed _tool_shell path only
}
RUN_BOUNDARY = (
    "sandbox: isolated dir + 8s timeout + interpreter-only (python3/node). "
    "Network is NOT kernel-isolated in this Space \u2014 do not run untrusted code "
    "expecting egress containment. Honest boundary, not a hardened jail."
)


def run_code(language: str, code: str) -> dict[str, Any]:
    """Execute editor code in the constrained sandbox. Returns stdout/stderr/code.
    NO fake run: if the language is unsupported we say so honestly."""
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    lang = (language or "python").lower()
    if lang in ("text/x-csrc", "c"):
        return {"error": "C execution is not enabled in this sandbox (no compiler in image). "
                         "Honest limitation \u2014 Python and JavaScript run live.",
                "boundary": RUN_BOUNDARY, "code": None}
    if lang == "shell":
        return {"error": "Shell is restricted to the allow-listed shell_exec tool, not the Run button.",
                "boundary": RUN_BOUNDARY, "code": None}
    interp = RUN_INTERPRETERS.get(lang)
    if not interp:
        return {"error": f"unsupported language '{language}'", "boundary": RUN_BOUNDARY, "code": None}
    suffix = {"python": ".py", "javascript": ".js"}[lang]
    src = SANDBOX_DIR / f"_run_{uuid.uuid4().hex[:8]}{suffix}"
    try:
        src.write_text(code, "utf-8")
        t0 = time.time()
        out = subprocess.run(
            [*interp, str(src)], capture_output=True, text=True, timeout=8,
            cwd=str(SANDBOX_DIR),
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(SANDBOX_DIR),
                 "PYTHONIOENCODING": "utf-8"},
        )
        elapsed = int((time.time() - t0) * 1000)
        rec = khipu_emit("code.run", {"language": lang, "bytes": len(code), "exit": out.returncode})
        return {"stdout": out.stdout[:8000], "stderr": out.stderr[:4000], "code": out.returncode,
                "elapsed_ms": elapsed, "boundary": RUN_BOUNDARY,
                "khipu_hash": rec["hash"]}
    except subprocess.TimeoutExpired:
        return {"error": "timeout (8s wall-clock)", "boundary": RUN_BOUNDARY, "code": 124}
    except FileNotFoundError as exc:
        return {"error": f"interpreter not available in image: {exc}", "boundary": RUN_BOUNDARY, "code": None}
    except Exception as exc:
        return {"error": str(exc)[:400], "boundary": RUN_BOUNDARY, "code": None}
    finally:
        try:
            src.unlink(missing_ok=True)
        except Exception:
            pass


def _gate_context_for_tool(name: str, args: dict[str, Any], attested: bool) -> dict[str, Any]:
    risk = "high" if name in STATE_CHANGING_TOOLS else "low"
    if name in ("drone_command",):
        risk = "critical"
    return {
        "risk": risk,
        "authorized": True,
        "has_provenance": True,
        "license_class": "GREEN",
        "two_person_attested": attested,
        "chain_verified": True,
        "tool": name,
        "args_summary": json.dumps(args)[:300],
    }


async def execute_tool(name: str, args: dict[str, Any], client: httpx.AsyncClient,
                       two_person_attested: bool = False) -> dict[str, Any]:
    """Run a tool after a PURIQ gate. Returns {ok, result|error, gate, khipu}."""
    gate = puriq_decide(name, _gate_context_for_tool(name, args, two_person_attested))
    if not gate["allow"]:
        return {"ok": False, "error": f"PURIQ gate denied: {gate['reason']}", "gate": gate}
    try:
        result = await _dispatch_tool(name, args, client)
        rec = khipu_emit(f"tool.{name}", {"args": args, "ok": True})
        return {"ok": True, "result": result, "gate": gate,
                "khipu": {"hash": rec["hash"], "receipt_id": rec["receipt_id"]}}
    except Exception as exc:
        khipu_emit(f"tool.{name}.error", {"args": args, "error": str(exc)})
        return {"ok": False, "error": str(exc), "gate": gate}


async def _dispatch_tool(name: str, args: dict[str, Any], client: httpx.AsyncClient) -> Any:
    if name == "web_search":
        return await _tool_proxy(client, "GET", "/api/a11oy/search", params={"q": args["query"], "k": args.get("k", 5)})
    if name == "web_fetch":
        return await _tool_proxy(client, "GET", "/api/a11oy/fetch", params={"url": args["url"]})
    if name == "github_read_file":
        return _tool_github_read(args["repo"], args["path"], args.get("ref", "HEAD"))
    if name == "github_open_issue":
        return _tool_github_issue(args["repo"], args["title"], args.get("body", ""))
    if name == "hf_read_space":
        return _tool_hf_space(args["repo_id"])
    if name == "flagship_call":
        return await _tool_flagship(client, args["organ"], args["path"], args.get("method", "GET"), args.get("json"))
    if name == "shell_exec":
        return _tool_shell(args["command"])
    if name == "fs_read":
        return _tool_fs_read(args["path"])
    if name == "fs_write":
        return _tool_fs_write(args["path"], args["content"])
    if name == "drone_command":
        return await _tool_flagship(client, "field-node", f"/drones/{args['drone_id']}/command",
                                    "POST", {"command": args["command"]})
    # ---- NEW agentic tools (REAL backends) ----
    if name == "repo_map":
        return _tool_repo_map(args["repo"])
    if name == "code_search":
        return _tool_code_search(args["query"], args.get("k", 6), args.get("repo"), args.get("hyde"))
    if name == "github_open_pr":
        return _tool_github_pr(args["repo"], args["title"], args["head"],
                               args.get("base", "main"), args.get("body", ""))
    if name == "apply_patch":
        return _tool_apply_patch(args["path"], args["diff"])
    if name == "run_tests":
        return _tool_run_tests(args.get("command", "python3 -m pytest -q"))
    if name == "formula_call":
        return _tool_formula_call(args["tool"], args.get("args", {}))
    if name == "khipu_verify":
        return _tool_khipu_verify(args["receipt_hash"])
    if name == "app_command":
        return await _tool_app_command(client, args["app"], args["command"], args.get("args", {}))
    raise ValueError(f"unknown tool {name}")


# ---------------------------------------------------------------------------
# NEW agentic tool implementations. Each hits a REAL backend or returns an
# honest, labeled error/gap — NEVER a fabricated success (Zero-Bandaid Law).
# ---------------------------------------------------------------------------
def _tool_repo_map(repo: str) -> Any:
    if _orgrag is None:
        return {"error": "a11oy_org_rag module not importable in this runtime (honest)."}
    return _orgrag.repo_map(repo)


def _tool_code_search(query: str, k: int, repo: str | None, hyde: str | None) -> Any:
    if _orgrag is None:
        return {"error": "a11oy_org_rag module not importable (honest).", "i_dont_know": True}
    return _orgrag.query(query, k=k, repo=repo, hyde_text=hyde, emit_receipt=khipu_emit)


def _tool_github_pr(repo: str, title: str, head: str, base: str, body: str) -> Any:
    out = subprocess.run(
        ["gh", "pr", "create", "-R", repo, "-t", title, "-H", head, "-B", base,
         "-b", body or "Opened by a11oy.code (Chaski)"],
        capture_output=True, text=True, timeout=45, env={**os.environ})
    if out.returncode != 0:
        return {"error": out.stderr.strip()[:400],
                "hint": "gh CLI needs a github credential in the Space env to open a PR."}
    return {"created": out.stdout.strip()}


def _tool_apply_patch(path: str, diff: str) -> Any:
    """Apply a unified diff to a sandboxed file using `patch` if available, else a
    minimal pure-python fallback. State-changing; gated upstream."""
    try:
        p = _safe_sandbox_path(path)
    except Exception as exc:
        return {"error": f"path rejected: {str(exc)[:200]}"}
    p.parent.mkdir(parents=True, exist_ok=True)
    patch_file = SANDBOX_DIR / f"_patch_{uuid.uuid4().hex[:8]}.diff"
    try:
        patch_file.write_text(diff, "utf-8")
        out = subprocess.run(["patch", str(p), str(patch_file)], capture_output=True,
                             text=True, timeout=15, cwd=str(SANDBOX_DIR))
        if out.returncode == 0:
            rec = khipu_emit("tool.apply_patch", {"path": path, "bytes": len(diff)})
            return {"path": path, "applied": True, "stdout": out.stdout[:1000],
                    "khipu_hash": rec["hash"]}
        return {"path": path, "applied": False, "error": (out.stderr or out.stdout)[:600],
                "honest_note": "patch did not apply cleanly; no partial write claimed."}
    except FileNotFoundError:
        return {"error": "`patch` binary not in image (honest). Use fs_write with full "
                         "file contents instead.", "applied": False}
    except Exception as exc:
        return {"error": str(exc)[:300], "applied": False}
    finally:
        try:
            patch_file.unlink(missing_ok=True)
        except Exception:
            pass


def _tool_run_tests(command: str) -> Any:
    """Run an allow-listed test command in the sandbox (python3/pytest/node)."""
    parts = command.strip().split()
    if not parts:
        return {"error": "empty command"}
    head = parts[0]
    if head not in ("python3", "node", "pytest"):
        return {"error": f"test runner '{head}' not allow-listed (python3/pytest/node only).",
                "boundary": RUN_BOUNDARY}
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    try:
        out = subprocess.run(parts, capture_output=True, text=True, timeout=30,
                             cwd=str(SANDBOX_DIR),
                             env={"PATH": os.environ.get("PATH", ""), "HOME": str(SANDBOX_DIR)})
        rec = khipu_emit("tool.run_tests", {"command": command, "exit": out.returncode})
        return {"command": command, "exit": out.returncode, "code": out.returncode,
                "stdout": out.stdout[:6000], "stderr": out.stderr[:3000],
                "boundary": RUN_BOUNDARY, "khipu_hash": rec["hash"]}
    except subprocess.TimeoutExpired:
        return {"error": "timeout (30s)", "command": command, "boundary": RUN_BOUNDARY}
    except FileNotFoundError as exc:
        return {"error": f"runner not in image: {exc}", "boundary": RUN_BOUNDARY}


def _tool_formula_call(tool: str, args: dict[str, Any]) -> Any:
    """Call a governed formula tool on hatun-mcp via the MCP client."""
    if _mcp is None:
        return {"error": "a11oy_mcp_client not importable (honest)."}
    try:
        return _mcp.call_tool(tool, args or {})
    except Exception as exc:
        return {"error": f"hatun-mcp call '{tool}' failed: {str(exc)[:300]}",
                "honest_note": "no fabricated formula result returned."}


def _tool_khipu_verify(receipt_hash: str) -> Any:
    if _mcp is None:
        return {"error": "a11oy_mcp_client not importable (honest)."}
    try:
        return _mcp.verify_receipt(receipt_hash)
    except Exception as exc:
        return {"error": f"szl_khipu_verify failed: {str(exc)[:300]}"}


async def _tool_app_command(client: httpx.AsyncClient, app: str, command: str,
                            args: dict[str, Any]) -> Any:
    """Orchestrate another SZL app via the REAL command bus:
    POST /api/<organ>/v4/command  body {command, args}. Returns the signed DSSE
    receipt the bus emits, or an honest error if the bus base is unconfigured."""
    organ = (app or "").strip().lower()
    base = APP_COMMAND_BASES.get(organ, "")
    if not base:
        # In-Space self-call for the local organ (relative), else honest gap.
        if organ in ("a11oy", "self", ""):
            base = os.environ.get("A11OY_SELF_BASE", "http://127.0.0.1:7860")
        else:
            return {"error": f"command-bus base for app '{organ}' not configured",
                    "hint": f"set {organ.upper()}_BASE when that Space ships.",
                    "gap": True, "bus_path": f"/api/{organ}/v4/command"}
    url = f"{base}/api/{organ}/v4/command"
    try:
        resp = await client.post(url, json={"command": command, "args": args or {}}, timeout=60.0)
        rec = khipu_emit("tool.app_command", {"app": organ, "command": command,
                                              "status": resp.status_code})
        try:
            data = resp.json()
        except Exception:
            data = {"status": resp.status_code, "text": resp.text[:2000]}
        return {"app": organ, "command": command, "bus_url": url, "response": data,
                "khipu_hash": rec["hash"]}
    except Exception as exc:
        return {"error": f"command bus call failed: {str(exc)[:300]}", "bus_url": url}


async def _tool_proxy(client: httpx.AsyncClient, method: str, path: str, **kw) -> Any:
    base = os.environ.get("A11OY_SELF_BASE", "http://127.0.0.1:7860")
    resp = await client.request(method, f"{base}{path}", timeout=60.0, **kw)
    try:
        return resp.json()
    except Exception:
        return {"status": resp.status_code, "text": resp.text[:2000]}


def _tool_github_read(repo: str, path: str, ref: str) -> Any:
    out = subprocess.run(["gh", "api", f"repos/{repo}/contents/{path}", "-q", ".content"],
                         capture_output=True, text=True, timeout=30,
                         env={**os.environ})
    if out.returncode != 0:
        return {"error": out.stderr.strip()[:400], "hint": "gh CLI needs github credential in the Space env."}
    import base64
    try:
        return {"repo": repo, "path": path, "content": base64.b64decode(out.stdout).decode("utf-8", "replace")[:8000]}
    except Exception:
        return {"repo": repo, "path": path, "raw": out.stdout[:2000]}


def _tool_github_issue(repo: str, title: str, body: str) -> Any:
    out = subprocess.run(["gh", "issue", "create", "-R", repo, "-t", title, "-b", body or "Opened by a11oy.code"],
                         capture_output=True, text=True, timeout=30, env={**os.environ})
    if out.returncode != 0:
        return {"error": out.stderr.strip()[:400]}
    return {"created": out.stdout.strip()}


def _tool_hf_space(repo_id: str) -> Any:
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=_resolve_hf_token() or None)
        files = api.list_repo_files(repo_id=repo_id, repo_type="space")
        return {"repo_id": repo_id, "files": files[:200], "count": len(files)}
    except Exception as exc:
        return {"error": str(exc)[:400]}


async def _tool_flagship(client: httpx.AsyncClient, organ: str, path: str, method: str, payload: Any) -> Any:
    role = _ROLE_ALIASES.get(organ, organ)
    base = FLAGSHIP_BASES.get(role, "")
    if not base:
        return {"error": f"service role '{role}' base URL not configured",
                "hint": f"configure the '{role}' service base when that Space ships.",
                "gap": True}
    resp = await client.request(method, f"{base}{path}", json=payload, timeout=60.0)
    try:
        return resp.json()
    except Exception:
        return {"status": resp.status_code, "text": resp.text[:2000]}


def _tool_shell(command: str) -> Any:
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    parts = command.strip().split()
    if not parts or parts[0] not in SHELL_ALLOWLIST:
        return {"error": f"binary not in allow-list {sorted(SHELL_ALLOWLIST)}", "command": command}
    try:
        out = subprocess.run(parts, capture_output=True, text=True, timeout=30,
                             cwd=str(SANDBOX_DIR), env={"PATH": os.environ.get("PATH", "")})
        return {"stdout": out.stdout[:4000], "stderr": out.stderr[:1000], "code": out.returncode}
    except subprocess.TimeoutExpired:
        return {"error": "timeout (30s)", "command": command}


def _safe_sandbox_path(path: str) -> Path:
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    p = (SANDBOX_DIR / path).resolve()
    p.relative_to(SANDBOX_DIR.resolve())  # raises if traversal
    return p


def _tool_fs_read(path: str) -> Any:
    try:
        p = _safe_sandbox_path(path)
        return {"path": path, "content": p.read_text("utf-8", "replace")[:8000]}
    except Exception as exc:
        return {"error": str(exc)[:300]}


def _tool_fs_write(path: str, content: str) -> Any:
    try:
        p = _safe_sandbox_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, "utf-8")
        return {"path": path, "bytes": len(content.encode())}
    except Exception as exc:
        return {"error": str(exc)[:300]}


# ---------------------------------------------------------------------------
# SQLite memory store (Unay organ). Conversations + messages + profiles + keys
# + receipts. Every write Khipu-receipted.
# ---------------------------------------------------------------------------

def _db() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(_db()) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations(
              id TEXT PRIMARY KEY, user_id TEXT, title TEXT, system_prompt TEXT,
              created REAL, updated REAL);
            CREATE TABLE IF NOT EXISTS messages(
              id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT, role TEXT,
              content TEXT, model TEXT, tier TEXT, latency_ms INTEGER, cost_usd REAL,
              yuyay13 REAL, khipu_hash TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS profiles(
              user_id TEXT PRIMARY KEY, prefs TEXT, projects TEXT, doctrine_state TEXT, updated REAL);
            CREATE TABLE IF NOT EXISTS api_keys(
              key TEXT PRIMARY KEY, owner TEXT, created REAL, rpm INTEGER, active INTEGER);
            CREATE TABLE IF NOT EXISTS receipts(
              hash TEXT PRIMARY KEY, receipt_id TEXT, action TEXT, ts REAL, body TEXT);
            """
        )
        c.commit()


def _db_write_receipt(body: dict[str, Any]) -> None:
    with closing(_db()) as c:
        c.execute("INSERT OR IGNORE INTO receipts(hash,receipt_id,action,ts,body) VALUES(?,?,?,?,?)",
                  (body["hash"], body["receipt_id"], body["action"], body["ts"], json.dumps(body, default=str)))
        c.commit()


def mem_upsert_conversation(conv_id: str, user_id: str, title: str, system_prompt: str) -> None:
    now = time.time()
    with closing(_db()) as c:
        c.execute(
            "INSERT INTO conversations(id,user_id,title,system_prompt,created,updated) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title, "
            "system_prompt=excluded.system_prompt, updated=excluded.updated",
            (conv_id, user_id, title, system_prompt, now, now))
        c.commit()
    khipu_emit("memory.conversation.upsert", {"conversation_id": conv_id, "user_id": user_id})


def mem_add_message(conv_id: str, role: str, content: str, **meta) -> None:
    with closing(_db()) as c:
        c.execute(
            "INSERT INTO messages(conversation_id,role,content,model,tier,latency_ms,cost_usd,"
            "yuyay13,khipu_hash,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (conv_id, role, content, meta.get("model"), meta.get("tier"), meta.get("latency_ms"),
             meta.get("cost_usd"), meta.get("yuyay13"), meta.get("khipu_hash"), time.time()))
        c.execute("UPDATE conversations SET updated=? WHERE id=?", (time.time(), conv_id))
        c.commit()
    khipu_emit("memory.message.add", {"conversation_id": conv_id, "role": role, "len": len(content)})


def mem_get_conversation(conv_id: str) -> dict[str, Any]:
    with closing(_db()) as c:
        conv = c.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
        msgs = c.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (conv_id,)).fetchall()
    return {"conversation": dict(conv) if conv else None, "messages": [dict(m) for m in msgs]}


def mem_list_conversations(user_id: str) -> list[dict[str, Any]]:
    with closing(_db()) as c:
        rows = c.execute("SELECT id,title,updated FROM conversations WHERE user_id=? ORDER BY updated DESC LIMIT 100",
                         (user_id,)).fetchall()
    return [dict(r) for r in rows]


def mem_get_profile(user_id: str) -> dict[str, Any]:
    with closing(_db()) as c:
        row = c.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        return {"user_id": user_id, "prefs": {}, "projects": [], "doctrine_state": "v12"}
    return {"user_id": user_id, "prefs": json.loads(row["prefs"] or "{}"),
            "projects": json.loads(row["projects"] or "[]"), "doctrine_state": row["doctrine_state"]}


def mem_set_profile(user_id: str, prefs: dict, projects: list, doctrine_state: str) -> None:
    with closing(_db()) as c:
        c.execute("INSERT INTO profiles(user_id,prefs,projects,doctrine_state,updated) VALUES(?,?,?,?,?) "
                  "ON CONFLICT(user_id) DO UPDATE SET prefs=excluded.prefs, projects=excluded.projects, "
                  "doctrine_state=excluded.doctrine_state, updated=excluded.updated",
                  (user_id, json.dumps(prefs), json.dumps(projects), doctrine_state, time.time()))
        c.commit()
    khipu_emit("memory.profile.set", {"user_id": user_id})


# ---------------------------------------------------------------------------
# Prometheus metrics (minimal text exposition)
# ---------------------------------------------------------------------------

_METRICS = {"requests_total": 0, "tokens_out_total": 0, "tool_calls_total": 0,
            "gate_denied_total": 0, "errors_total": 0}


def _metrics_text() -> str:
    lines = ["# a11oy.code orchestrator metrics (Prometheus exposition)"]
    for k, v in _METRICS.items():
        lines.append(f"a11oy_code_{k} {v}")
    lines.append(f"a11oy_code_khipu_chain_tip_present {1 if _khipu_tip != _KHIPU_GENESIS else 0}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Shared HTTP client
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient()
    return _client


# ===========================================================================
# ENDPOINTS
# ===========================================================================

async def _safe_body(request: Request) -> tuple[Any, Optional[JSONResponse]]:
    """Parse a JSON request body, tolerating empty/malformed/over-nested input.

    Returns (body_dict, error_response). On a parse failure the caller returns
    error_response (a graceful 400) instead of letting request.json() raise — an
    unguarded raise becomes an opaque HTTP 500, which is both a poor judge/demo
    experience and an error-shape leak. An empty body parses to {}. QA-hardened
    (mirrors serve.py::_safe_json_body). Doctrine v11 (LOCKED); v12 (v11+PURIQ) roadmap.
    """
    try:
        raw = await request.body()
    except Exception:
        return None, JSONResponse({"error": "could not read request body"}, status_code=400)
    if not raw:
        return {}, None
    try:
        parsed = await request.json()
    except Exception:
        return None, JSONResponse({"error": "invalid JSON body"}, status_code=400)
    # A JSON array or scalar parses without raising, but every caller does
    # body.get(...) — an unguarded .get() on a non-dict would 500. Reject any
    # non-object body with a graceful 400 so the error path stays 4xx, never 5xx.
    if not isinstance(parsed, dict):
        return None, JSONResponse(
            {"error": "request body must be a JSON object"}, status_code=400)
    return parsed, None


def _honest_key_resolution() -> dict:
    """key_resolution that can never contradict the actual serving path (#324).

    Start from the registry's view (router credential resolution), then — when
    _serving_base() reports we are genuinely serving LOCAL on the box GPU —
    OVERRIDE the cosmetic hf-router/HF_TOKEN claim so the reported provider,
    base_url and env_used honestly match where turns are served. Mirrors the
    existing key_resolution shape (wired, provider, base_url, env_used,
    key_present, honest_note). When serving via the router we leave the registry
    result untouched. Never logs/returns a token value.
    """
    base = (_llmreg.resolve_code_llm_key() if _llmreg is not None
            else {"wired": has_inference_credential()})
    local_base, is_local = _serving_base()
    if not is_local:
        return base
    gpu_token = (os.environ.get("A11OY_GPU_TOKEN") or "").strip()
    key_present = bool(gpu_token)
    out = dict(base)
    out.update({
        "wired": True,
        "provider": "self-hosted-gpu",
        "base_url": local_base,
        "env_used": "A11OY_GPU_TOKEN" if key_present else "none (local Ollama, no key)",
        "key_present": key_present,
        "honest_note": ("Serving locally on the box GPU (#324): provider reflects the "
                        "actual local serving path, not the HF Router. "
                        + ("Authenticated via A11OY_GPU_TOKEN (vLLM)."
                           if key_present
                           else "No key required (local Ollama / no-auth endpoint).")),
    })
    return out


@router.get("/healthz")
async def code_healthz() -> JSONResponse:
    _sov = _sovereign_inference_state()
    return JSONResponse({
        "status": "ok", "component": "a11oy.code orchestrator",
        "doctrine": "v11",
        "doctrine_state": "LOCKED",
        "doctrine_roadmap": "v12 (v11+PURIQ) — experimental, not locked",
        "inference": _sov["inference"],
        "mode": _sov["mode"],
        "backend": _sov["backend"],
        "sovereign": _sov["sovereign"],
        **({"gpu": _sov["gpu"]} if _sov.get("gpu") else {}),
        "tiers": list(TIERS.keys()), "tools": [t["function"]["name"] for t in TOOL_SCHEMAS],
        "puriq_threshold": PURIQ_THRESHOLD, "memory": "sqlite", "signed": "Yachay",
        "ide": "/api/a11oy/code/ide", "run": "/api/a11oy/code/run",
        "token_secret": _code_secret_name(),
        "token_secret_fallbacks": ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
                                   "DEEPSEEK_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "HF_TOKEN"],
        "agentic": _agent is not None,
        "org_rag": _orgrag is not None,
        "mcp_client": _mcp is not None,
        "key_resolution": _honest_key_resolution(),
        "built_by": "Perplexity Computer Agent",
    })


@router.get("/models")
async def code_models() -> JSONResponse:
    return JSONResponse({"object": "list", "data": MODEL_CATALOG, "tiers": TIERS})


@router.get("/tools")
async def code_tools() -> JSONResponse:
    return JSONResponse({"tools": TOOL_SCHEMAS,
                         "state_changing": sorted(STATE_CHANGING_TOOLS)})


@router.get("/metrics")
async def code_metrics() -> PlainTextResponse:
    return PlainTextResponse(_metrics_text(), media_type="text/plain; version=0.0.4")


# ===========================================================================
# AGENTIC RAG ENDPOINTS (a11oy_org_rag) — for the UI + the agent's RETRIEVE step.
# ===========================================================================
@router.post("/rag/index")
async def rag_index(request: Request) -> JSONResponse:
    """Build/refresh the org graph + FTS5/vector index. Receipted. Honest error
    if a11oy_org_rag is unavailable or no GitHub credential is present."""
    if _orgrag is None:
        return JSONResponse({"ok": False, "error": f"a11oy_org_rag not importable: {_ORGRAG_IMPORT_ERROR}"},
                            status_code=503)
    body, _err = await _safe_body(request)
    if _err is not None:
        return _err
    repos = body.get("repos")
    out = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _orgrag.build_index(repos=repos, emit_receipt=khipu_emit))
    return JSONResponse(out, status_code=200 if out.get("ok") else 502)


@router.post("/rag/query")
async def rag_query(request: Request) -> JSONResponse:
    """Two-stage Λ-weighted agentic RAG query (HyDE + FTS5/vector + graph re-rank).
    Low support ⇒ i_dont_know (never fabricates)."""
    if _orgrag is None:
        return JSONResponse({"ok": False, "i_dont_know": True,
                             "error": "a11oy_org_rag not importable"}, status_code=503)
    body, _err = await _safe_body(request)
    if _err is not None:
        return _err
    q = body.get("query") or body.get("q", "")
    if not q:
        return JSONResponse({"ok": False, "error": "missing 'query'"}, status_code=400)
    out = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _orgrag.query(q, k=body.get("k", 6), repo=body.get("repo"),
                                    hyde_text=body.get("hyde"), emit_receipt=khipu_emit))
    return JSONResponse(out)


@router.get("/rag/graph")
async def rag_graph() -> JSONResponse:
    """Org graph (nodes/edges) for the 3D UI. Honest empty state if not built."""
    if _orgrag is None:
        return JSONResponse({"built": False, "nodes": [], "edges": [],
                             "error": "a11oy_org_rag not importable"}, status_code=503)
    return JSONResponse(_orgrag.graph_dict())


@router.get("/rag/status")
async def rag_status() -> JSONResponse:
    if _orgrag is None:
        return JSONResponse({"ok": False, "error": "a11oy_org_rag not importable"}, status_code=503)
    return JSONResponse(_orgrag.status())


@router.get("/rag/corpus")
async def rag_corpus() -> JSONResponse:
    """The SEVEN-category SZL corpus manifest (founder mandate) + live build_state.
    Single source of truth for WHICH sources a11oy Code indexes and HOW it cites
    them (corpus category + gh:<repo>|hf:<space> source + path + sha256)."""
    if _orgrag is None:
        return JSONResponse({"ok": False, "error": "a11oy_org_rag not importable"}, status_code=503)
    return JSONResponse({"ok": True, "corpus": _orgrag.corpus_manifest(),
                         "build_state": _orgrag.build_state()})


@router.post("/rag/refresh")
async def rag_refresh(request: Request) -> JSONResponse:
    """Operational corpus build/refresh (founder mandate). Lays down a REAL, labeled
    SEED index synchronously (so the agent is never empty) and ingests the FULL
    seven-category corpus on a receipted background tick — pulling live via the
    GitHub Contents/Trees API + the HF Spaces file API. ``{"background": false}``
    runs the full ingest synchronously (CLI/cron). Never claims a fake 'full'."""
    if _orgrag is None:
        return JSONResponse({"ok": False, "error": f"a11oy_org_rag not importable: {_ORGRAG_IMPORT_ERROR}"},
                            status_code=503)
    body, _err = await _safe_body(request)
    if _err is not None:
        return _err
    background = bool(body.get("background", True))
    if background:
        # start_background_build returns immediately with the seed + in-flight phase.
        out = _orgrag.start_background_build(emit_receipt=khipu_emit, seed_first=True)
    else:
        out = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _orgrag.refresh_tick(emit_receipt=khipu_emit, background=False))
    return JSONResponse(out, status_code=200 if out.get("ok") else 502)


@router.post("/rag/seed")
async def rag_seed() -> JSONResponse:
    """Build ONLY the labeled SEED index synchronously (small real subset of each
    of the seven corpus categories). Honest error if no corpus file is reachable."""
    if _orgrag is None:
        return JSONResponse({"ok": False, "error": "a11oy_org_rag not importable"}, status_code=503)
    out = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _orgrag.build_seed_index(emit_receipt=khipu_emit))
    return JSONResponse(out, status_code=200 if out.get("ok") else 502)


# ===========================================================================
# AGENT ENDPOINTS (a11oy_agent_loop) — status + a non-chat run/stream surface
# the UI can call directly. The primary agentic surface is POST /chat/stream
# with {"agentic": true}; these add an explicit, named agent API.
# ===========================================================================
@router.get("/agent/status")
async def agent_status() -> JSONResponse:
    """Agent availability + guard configuration + recent Reflexion lessons."""
    if _agent is None:
        return JSONResponse({"available": False, "error": f"a11oy_agent_loop not importable: {_AGENT_IMPORT_ERROR}"},
                            status_code=503)
    return JSONResponse({
        "available": True,
        "surface_name": "Chaski",
        "states": [_agent.S_INTAKE, _agent.S_PLAN, _agent.S_RETRIEVE, _agent.S_ACT,
                   _agent.S_OBSERVE, _agent.S_VERIFY, _agent.S_REFLECT,
                   _agent.S_FINALIZE, _agent.S_HALT],
        "evidence_kinds": list(_agent.EVIDENCE_KINDS),
        "guards": {"max_steps": _agent.MAX_STEPS,
                   "max_reflect_depth": _agent.MAX_REFLECT_DEPTH,
                   "lambda_floor": _agent.LAMBDA_FLOOR},
        "mode": "live" if has_inference_credential() else "deterministic_stub",
        "token_secret": _code_secret_name(),
        "recent_reflections": _agent.recent_reflections(limit=10),
    })


@router.post("/agent/run")
async def agent_run(request: Request) -> JSONResponse:
    """Run the governed FSM once and return the FULL machine-readable trace
    (every step's state, Λ, gate decision, evidence, Khipu hash). Non-streaming."""
    if _agent is None:
        return JSONResponse({"ok": False, "error": "a11oy_agent_loop not importable"}, status_code=503)
    body, _err = await _safe_body(request)
    if _err is not None:
        return _err
    task = body.get("task") or body.get("message", "")
    if not task:
        return JSONResponse({"ok": False, "error": "missing 'task'"}, status_code=400)
    client = _get_client()
    result = await _agent.run_agent(
        task, history=body.get("history", []),
        khipu_emit=khipu_emit, puriq_decide=puriq_decide,
        execute_tool=(lambda n, a, **kw: execute_tool(n, a, client, **kw)),
        model_complete=agent_model_complete, rag_query=_agent_rag_query,
        two_person_attested=bool(body.get("two_person_attested", False)))
    return JSONResponse(result)


@router.post("/agent/stream")
async def agent_stream(request: Request):
    """Stream the governed FSM step-by-step as SSE `agent_step` events, then a
    final `done` event. Same envelope the agentic /chat/stream emits, but a
    dedicated agent surface for the UI."""
    if _agent is None:
        raise HTTPException(status_code=503, detail="a11oy_agent_loop not importable")
    body, _err = await _safe_body(request)
    if _err is not None:
        return _err
    task = body.get("task") or body.get("message", "")
    two_person = bool(body.get("two_person_attested", False))
    history = body.get("history", [])
    client = _get_client()

    async def gen() -> AsyncGenerator[bytes, None]:
        def sse(event: str, data: dict) -> bytes:
            return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()
        if not task:
            yield sse("error", {"error": "missing 'task'"})
            return
        _q: list[tuple[str, dict]] = []
        result = await _agent.run_agent(
            task, history=history,
            khipu_emit=khipu_emit, puriq_decide=puriq_decide,
            execute_tool=(lambda n, a, **kw: execute_tool(n, a, client, **kw)),
            model_complete=agent_model_complete, rag_query=_agent_rag_query,
            two_person_attested=two_person,
            emit=lambda ev, d: _q.append((ev, d)))
        for ev, d in _q:
            yield sse(ev, d)
            await asyncio.sleep(0)
        yield sse("done", {"ok": result.get("ok"), "final_state": result.get("final_state"),
                           "answer": result.get("answer"), "stub": result.get("stub"),
                           "i_dont_know": result.get("i_dont_know"),
                           "step_count": result.get("step_count"),
                           "khipu_hash": result.get("khipu_hash"),
                           "chain_verified": result.get("chain_verified", True),
                           "guards": result.get("guards")})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# IDE page (full-screen coding assistant). Self-contained HTML with vendored
# CodeMirror (0 runtime CDN). Served from a sibling file so it can be edited
# without touching this module.
# ---------------------------------------------------------------------------
_IDE_HTML_PATH = Path(__file__).with_name("a11oy_code_ide.html")


@router.get("/ide")
async def code_ide():
    """Serve the full IDE-style Code tab page (streaming chat + editor + run +
    receipts). 0 runtime CDN \u2014 all assets inlined."""
    try:
        html = _IDE_HTML_PATH.read_text("utf-8")
    except Exception as exc:  # honest failure, never a fake page
        return PlainTextResponse(
            f"a11oy.code IDE page not found on this Space ({exc}). "
            "The orchestrator API is live at /api/a11oy/code/* regardless.",
            status_code=404)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)


@router.post("/run")
async def code_run(request: Request) -> JSONResponse:
    """Execute editor code in the constrained sandbox. Honest safety boundary is
    returned in the response (see RUN_BOUNDARY). PURIQ-gated + Khipu-receipted."""
    body, _err = await _safe_body(request)
    if _err is not None:
        return _err
    language = body.get("language", "python")
    code = body.get("code", "")
    if not isinstance(code, str) or not code.strip():
        return JSONResponse({"error": "empty code", "boundary": RUN_BOUNDARY, "code": None})
    # Gate the run as a sandboxed exec action.
    gate = puriq_decide("shell_exec", _gate_context_for_tool("shell_exec", {"run": language}, attested=True))
    if not gate["allow"]:
        _METRICS["gate_denied_total"] += 1
        return JSONResponse({"error": f"PURIQ gate denied: {gate['reason']}",
                             "boundary": RUN_BOUNDARY, "code": None})
    result = await asyncio.get_event_loop().run_in_executor(None, run_code, language, code)
    result["gate"] = {"allow": gate["allow"], "score": gate["score"], "lambda": gate["lambda"]}
    return JSONResponse(result)


@router.post("/kernel/{run_id}/exec")
async def kernel_exec(run_id: str, request: Request) -> JSONResponse:
    """Persistent sandboxed governed kernel — execute an ALREADY-GATED cell in the
    long-lived per-run_id worker whose globals() persist across cells (DEFER-2).

    Delegates to a11oy_governed_kernel.GovernedKernel.exec_cell (one worker process
    per run_id; rlimits + network-disable preamble + isolated interpreter). The hard
    security screen runs in the PURIQ gate below BEFORE the cell ever reaches the
    worker. Returns {output, receipt_hash, rlimit_status}.

    PROVE wire: after each exec a signed Khipu receipt is emitted and recorded into
    the UNIFIED LEDGER (organ="a11oy-kernel") via szl_lake_ingest.record_receipt —
    fire-and-forget, never blocks/raises. Energy is honestly UNAVAILABLE (this Space
    has no NVML meter on the kernel path; joules are never fabricated)."""
    body, _err = await _safe_body(request)
    if _err is not None:
        return _err
    code = body.get("code", "")
    if not isinstance(code, str) or not code.strip():
        return JSONResponse({"error": "empty code", "output": None,
                             "receipt_hash": None, "rlimit_status": None})
    # PURIQ-gate the cell as a sandboxed exec action (same bar as /run).
    gate = puriq_decide("shell_exec",
                        _gate_context_for_tool("shell_exec", {"kernel": run_id}, attested=True))
    if not gate["allow"]:
        _METRICS["gate_denied_total"] += 1
        return JSONResponse({"error": f"PURIQ gate denied: {gate['reason']}",
                             "output": None, "receipt_hash": None, "rlimit_status": None})

    # Delegate to the persistent worker (blocking IO → run in the default executor).
    try:
        import a11oy_governed_kernel as _gk
    except Exception as exc:  # honest degrade — module absent
        return JSONResponse({"error": f"governed kernel unavailable: {exc!r}",
                             "output": None, "receipt_hash": None, "rlimit_status": None},
                            status_code=503)
    kernel = _gk.get_kernel(run_id, create=True)
    result = await asyncio.get_event_loop().run_in_executor(None, kernel.exec_cell, code)

    rlimit_status = {
        "isolation": result.get("isolation"),
        "degraded": bool(result.get("degraded", False)),
        "timeout": bool(result.get("timeout", False)),
        "wall_s": result.get("wall_s"),
        "limits": kernel.status().get("limits"),
    }
    output = {
        "ok": result.get("ok"),
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "new_or_changed": result.get("new_or_changed"),
        "vars": result.get("vars"),
    }
    energy = {"joules": None, "label": "UNAVAILABLE",
              "note": "kernel exec joules NOT measured (no NVML on this path) — not fabricated"}

    # Emit a chain-verified (DSSE-cosigned when a signer is wired) Khipu receipt.
    rec = khipu_emit("kernel.exec", {
        "run_id": run_id,
        "ok": result.get("ok"),
        "degraded": rlimit_status["degraded"],
        "timeout": rlimit_status["timeout"],
        "wall_s": result.get("wall_s"),
        "isolation": result.get("isolation"),
        "new_or_changed": result.get("new_or_changed"),
        "stdout_sha256": hashlib.sha256((result.get("stdout") or "").encode()).hexdigest(),
        "energy": energy,
        "gate": {"allow": gate["allow"], "score": gate["score"], "lambda": gate["lambda"]},
    })
    receipt_hash = rec.get("hash")

    # ── UNIFIED LEDGER WIRE-UP (organ="a11oy-kernel") ───────────────────────────
    # Record the signed kernel-exec receipt into the unified receipt ledger. Mirrors
    # szl_governed_api's govern/infer ledger wire. Fully guarded + non-blocking — a
    # ledger/dataset hiccup must NEVER affect the kernel exec response.
    if isinstance(rec, dict):
        try:
            import szl_lake_ingest as _lake
            _rec = dict(rec)
            _rec["energy"] = energy
            _lake.record_receipt(_rec, organ="a11oy-kernel")
        except Exception as _lake_e:  # pragma: no cover
            print(f"[a11oy.code] kernel exec ledger record skipped (non-fatal): {_lake_e!r}",
                  file=sys.stderr)

    return JSONResponse({
        "run_id": run_id,
        "output": output,
        "receipt_hash": receipt_hash,
        "rlimit_status": rlimit_status,
        "energy": energy,
        "gate": {"allow": gate["allow"], "score": gate["score"], "lambda": gate["lambda"]},
    })


@router.post("/v1/router")
async def v1_router(request: Request) -> JSONResponse:
    """7-tier router. Returns OpenAI-compatible response + Khipu receipt."""
    body, _err = await _safe_body(request)
    if _err is not None:
        return _err
    messages = body.get("messages", [])
    model = body.get("model")
    governance_tier = body.get("governance_tier", "standard")
    decision = route(messages, model, governance_tier, body.get("budget"))
    _METRICS["requests_total"] += 1
    client = _get_client()
    chain = [decision["model"], *decision["fallbacks"], "DEGRADE"]
    last_err = None
    t0 = time.time()
    for m in chain:
        if m == "DEGRADE":
            _METRICS["errors_total"] += 1
            return JSONResponse({"error": "all providers failed", "last_error": str(last_err),
                                 "route": decision}, status_code=502)
        try:
            payload = {"messages": messages, "max_tokens": body.get("max_tokens", 1024),
                       "temperature": body.get("temperature", 0.7)}
            if body.get("tools"):
                payload["tools"] = body["tools"]
                payload["tool_choice"] = body.get("tool_choice", "auto")
            data = await _call_model(client, m, payload)
            latency_ms = int((time.time() - t0) * 1000)
            text = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content") or ""
            tcs = (data.get("choices", [{}])[0].get("message", {}) or {}).get("tool_calls")
            y13 = yuyay13_response_score(text, tcs, latency_ms)
            rec = khipu_emit("router.completion", {"model": m, "tier": decision["tier"],
                                                   "latency_ms": latency_ms, "yuyay13": y13})
            data["a11oy"] = {"tier": decision["tier"], "model": m,
                             "provider": decision.get("provider", _serving_provider()[0]),
                             "license_class": decision["license_class"], "latency_ms": latency_ms,
                             "yuyay13": y13,
                             "khipu_receipt": {"hash": rec["hash"], "chain_verified": True,
                                               "route_reason": decision["reason"]}}
            return JSONResponse(data)
        except Exception as exc:
            last_err = exc
            khipu_emit("router.fallback", {"model": m, "error": str(exc)[:200]})
            continue
    return JSONResponse({"error": "unreachable"}, status_code=500)


def _check_api_key(authorization: Optional[str]) -> Optional[str]:
    """Validate a public API key for /v1/chat/completions. Returns owner or None."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    key = authorization.split(" ", 1)[1].strip()
    _tok = _resolve_hf_token()
    if _tok and key == _tok:
        return "internal"
    with closing(_db()) as c:
        row = c.execute("SELECT owner,active FROM api_keys WHERE key=?", (key,)).fetchone()
    if row and row["active"]:
        return row["owner"]
    return None


@router.post("/v1/chat/completions")
async def v1_chat_completions(request: Request, authorization: Optional[str] = Header(None)):
    """OpenAI-compatible public endpoint. SSE for stream=true; JSON otherwise.

    External SDKs (openai-python/js) can point base_url here. Rate-limited per key.
    """
    owner = _check_api_key(authorization)
    if owner is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key. Issue one via /v1/keys (admin).")
    body, _err = await _safe_body(request)
    if _err is not None:
        return _err
    messages = body.get("messages", [])
    model = body.get("model", "router-auto")
    stream = bool(body.get("stream", False))
    governance_tier = body.get("governance_tier", "standard")
    decision = route(messages, model if model != "gpt-4" else "router-auto", governance_tier, body.get("budget"))
    _METRICS["requests_total"] += 1
    client = _get_client()
    payload = {"messages": messages, "max_tokens": body.get("max_tokens", 1024),
               "temperature": body.get("temperature", 0.7)}
    if body.get("tools"):
        payload["tools"] = body["tools"]
        payload["tool_choice"] = body.get("tool_choice", "auto")

    if not stream:
        try:
            data = await _call_model(client, decision["model"], payload)
            data.setdefault("a11oy", {}).update({"tier": decision["tier"], "model": decision["model"],
                                                 "license_class": decision["license_class"]})
            return JSONResponse(data)
        except Exception as exc:
            _METRICS["errors_total"] += 1
            raise HTTPException(status_code=502, detail=str(exc))

    async def gen() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in _call_model_stream(client, decision["model"], payload):
                yield chunk
        except Exception as exc:
            _METRICS["errors_total"] += 1
            yield f'data: {{"error": {json.dumps(str(exc))}}}\n\n'.encode()
        yield b"data: [DONE]\n\n"

    # API stream is line-delimited SSE (OpenAI style).
    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/chat/stream")
async def chat_stream(request: Request):
    """Browser SSE chat endpoint with full orchestration: PURIQ gate, tool loop,
    badges. Emits SSE events: route, token, tool_call, tool_result, done.
    """
    body, _err = await _safe_body(request)
    if _err is not None:
        return _err
    conv_id = body.get("conversation_id") or str(uuid.uuid4())
    user_id = body.get("user_id", "founder")
    model = body.get("model") or "router-auto"
    # `tools` may be a bool, the string "auto"/"none", or omitted. Default: enabled.
    _tools_flag = body.get("tools", body.get("enable_tools", "auto"))
    enable_tools = _tools_flag not in (False, "none", "off", None)
    two_person = bool(body.get("two_person_attested", False))
    governance_tier = body.get("governance_tier", "standard")
    # Agentic mode: run the governed FSM (plan/retrieve/act/observe/verify/
    # reflect/finalize) instead of the single-shot tool loop. Default OFF so the
    # existing chat behavior is byte-for-byte unchanged unless explicitly asked.
    agentic = bool(body.get("agentic", False)) and _agent is not None

    # ------------------------------------------------------------------
    # Message contract: the browser tab POSTs an OpenAI-style `messages`
    # array (system + prior turns + current user turn, with optional
    # multimodal image_url parts). Older callers may POST a singular
    # `message` string + `system_prompt`. Accept BOTH. The `messages`
    # array is authoritative when present, so the visible conversation
    # always reaches the model (fixes the empty-history tool spiral).
    # ------------------------------------------------------------------
    incoming = body.get("messages")
    system_prompt = body.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
    if isinstance(incoming, list) and incoming:
        history = []
        sys_seen = False
        for m in incoming:
            role = m.get("role")
            if role == "system":
                sys_seen = True
                system_prompt = (
                    m.get("content") if isinstance(m.get("content"), str) else system_prompt
                )
            history.append({"role": role, "content": m.get("content")})
        if not sys_seen:
            history.insert(0, {"role": "system", "content": system_prompt})
        # Derive a human-readable title + the last user turn for memory.
        last_user = next(
            (m.get("content") for m in reversed(incoming) if m.get("role") == "user"), ""
        )
        user_msg = last_user if isinstance(last_user, str) else json.dumps(last_user)
    else:
        # Legacy singular-message contract: rebuild history from stored memory.
        user_msg = body.get("message", "")
        prior = mem_get_conversation(conv_id)
        history = [{"role": "system", "content": system_prompt}]
        for m in prior["messages"]:
            if m["role"] in ("user", "assistant"):
                history.append({"role": m["role"], "content": m["content"]})
        if body.get("content_parts"):
            history.append({"role": "user", "content": body["content_parts"]})
        else:
            history.append({"role": "user", "content": user_msg})

    mem_upsert_conversation(conv_id, user_id, (user_msg or "conversation")[:60], system_prompt)
    mem_add_message(conv_id, "user", user_msg if user_msg else "[multimodal]")
    _METRICS["requests_total"] += 1

    decision = route(history, model, governance_tier, body.get("budget"))
    client = _get_client()

    async def gen() -> AsyncGenerator[bytes, None]:
        def sse(event: str, data: dict) -> bytes:
            return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()

        # R0 honesty: reflect the ACTUAL serving target so route/done telemetry is
        # truthful. When serving locally (reachability-gated by _serving_base, so
        # it can never overclaim) report the on-box served tag — not the logical
        # router id — plus a sovereign/served_locally flag.
        _serve_base, _serve_local = _serving_base()
        # R-RESILIENCE/R-FREEPOWER provenance: report WHO served + the REAL base_url +
        # an energy_source field on EVERY turn (honest plumbing; "grid" today, real
        # value once a stranded-energy node comes online). served_by stays coarse
        # (local-gpu / hf-router); a future LiteLLM proxy can refine to tier-A/B/C/D.
        _served_by = "local-gpu" if _serve_local else "hf-router"
        _energy_source = "grid"
        _route_model = _map_model_for_local(decision["model"]) if _serve_local else decision["model"]
        yield sse("route", {"conversation_id": conv_id, "tier": decision["tier"],
                            "model": _route_model, "license_class": decision["license_class"],
                            "reason": decision["reason"],
                            "served_locally": _serve_local, "sovereign": _serve_local,
                            "served_by": _served_by, "base_url": _serve_base,
                            "energy_source": _energy_source})
        t0 = time.time()

        # ----------------------------------------------------------------
        # AGENTIC BRANCH (agentic=true): run the governed FSM. EVERY step is
        # Λ-gated + PURIQ-gated + Khipu-receipted FOR REAL, regardless of whether
        # a model credential is present. Each transition is streamed as an
        # `agent_step` SSE event for the UI; the final synthesis streams as
        # `token` events and a `done` event — identical envelope to normal chat.
        # ----------------------------------------------------------------
        if agentic:
            _queue: list[tuple[str, dict]] = []
            def _agent_emit(event: str, data: dict) -> None:
                _queue.append((event, data))
            try:
                result = await _agent.run_agent(
                    user_msg, history=history,
                    khipu_emit=khipu_emit, puriq_decide=puriq_decide,
                    execute_tool=(lambda n, a, **kw: execute_tool(n, a, client, **kw)),
                    model_complete=agent_model_complete, rag_query=_agent_rag_query,
                    two_person_attested=two_person, emit=_agent_emit)
            except Exception as exc:
                yield sse("error", {"error": f"agent loop failed: {str(exc)[:300]}"})
                return
            # Drain buffered step events (the loop ran to completion synchronously).
            for ev, data in _queue:
                yield sse(ev, data)
                await asyncio.sleep(0)
            answer = result.get("answer") or (
                f"[agent halted: {result.get('halt_reason')}]" if not result.get("ok") else "")
            for word in re.findall(r"\S+\s*", answer):
                yield sse("token", {"text": word})
                await asyncio.sleep(0)
            latency_ms = int((time.time() - t0) * 1000)
            y13 = yuyay13_response_score(answer, None, latency_ms)
            # R0 honesty: a locally-served agentic turn is served by the on-box tag
            # (and costs nothing). Only remap when we actually served local AND the
            # finalize step wasn't the no-credential deterministic stub.
            _ag_local = _serve_local and not result.get("stub")
            _ag_model = _map_model_for_local(result.get("model")) if _ag_local else result.get("model")
            mem_add_message(conv_id, "assistant", answer, model=_ag_model,
                            tier=decision["tier"], latency_ms=latency_ms, cost_usd=0.0,
                            yuyay13=y13, khipu_hash=result.get("khipu_hash"))
            yield sse("done", {"conversation_id": conv_id, "tier": decision["tier"],
                               "model": _ag_model, "license_class": decision["license_class"],
                               "latency_ms": latency_ms, "cost_usd": 0.0, "yuyay13": y13,
                               "khipu_hash": result.get("khipu_hash"),
                               "chain_verified": result.get("chain_verified", True),
                               "mode": "agentic", "agentic": True,
                               "served_locally": _ag_local, "sovereign": _ag_local,
                               "served_by": ("local-gpu" if _ag_local else "hf-router"),
                               "base_url": _serve_base, "energy_source": _energy_source,
                               "final_state": result.get("final_state"),
                               "step_count": result.get("step_count"),
                               "i_dont_know": result.get("i_dont_know"),
                               "reflect_depth": result.get("reflect_depth"),
                               "stub": result.get("stub"),
                               "grounded_evidence": result.get("grounded_evidence"),
                               "guards": result.get("guards")})
            return

        # ----------------------------------------------------------------
        # HONEST-STUB BRANCH: if there is NO inference credential, do NOT
        # error out and do NOT fabricate. Stream a clearly-labeled stub plus
        # the real signed receipt, then finish cleanly. This keeps the tab
        # fully operational (routing + Lambda + receipt) while being honest
        # that the model text is unavailable until a token is pasted.
        # ----------------------------------------------------------------
        if not has_inference_credential():
            stub = honest_stub_text(user_msg, decision)
            for word in re.findall(r"\S+\s*", stub):
                yield sse("token", {"text": word})
                await asyncio.sleep(0)
            latency_ms = int((time.time() - t0) * 1000)
            y13 = yuyay13_response_score(stub, None, latency_ms)
            rec = khipu_emit("chat.completion.stub", {
                "conversation_id": conv_id, "model": decision["model"],
                "tier": decision["tier"], "mode": "deterministic_stub", "yuyay13": y13})
            mem_add_message(conv_id, "assistant", stub, model=decision["model"],
                            tier=decision["tier"], latency_ms=latency_ms, cost_usd=0.0,
                            yuyay13=y13, khipu_hash=rec["hash"])
            yield sse("done", {"conversation_id": conv_id, "tier": decision["tier"],
                               "model": decision["model"], "license_class": decision["license_class"],
                               "latency_ms": latency_ms, "cost_usd": 0.0, "yuyay13": y13,
                               "khipu_hash": rec["hash"], "chain_verified": True,
                               "mode": "deterministic_stub"})
            return

        payload = {"messages": history, "max_tokens": body.get("max_tokens", 1500),
                   "temperature": body.get("temperature", 0.7)}
        if enable_tools:
            payload["tools"] = TOOL_SCHEMAS
            payload["tool_choice"] = "auto"

        # Step 1: non-stream call to detect tool calls (tool-calling rarely streams cleanly).
        # Walk primary -> fallbacks on provider error / rate limit (resilience).
        collected_text = ""
        tool_round = 0
        model_used = decision["model"]
        candidates = [decision["model"], *decision.get("fallbacks", [])]
        try:
            while tool_round < 4:
                data, model_used = await _call_model_resilient(client, candidates, payload)
                msg = data.get("choices", [{}])[0].get("message", {}) or {}
                tcs = msg.get("tool_calls")
                if tcs:
                    # Normalize tool_calls so the echoed assistant turn ALWAYS carries
                    # a valid JSON-object `arguments` string. Some providers reject a
                    # subsequent request if a prior tool_call has arguments=null
                    # ("expected object, but got null"). This guarantees schema-valid
                    # round-trips without faking anything.
                    norm_tcs = []
                    for tc in tcs:
                        fnobj = tc.get("function", {}) or {}
                        raw_args = fnobj.get("arguments")
                        if not isinstance(raw_args, str) or not raw_args.strip():
                            raw_args = "{}"
                        norm_tcs.append({
                            "id": tc.get("id") or fnobj.get("name", "tool"),
                            "type": tc.get("type", "function"),
                            "function": {"name": fnobj.get("name"), "arguments": raw_args},
                        })
                    payload["messages"].append({"role": "assistant", "content": msg.get("content") or "",
                                                "tool_calls": norm_tcs})
                    for tc in norm_tcs:
                        fn = tc["function"]["name"]
                        try:
                            fargs = json.loads(tc["function"].get("arguments") or "{}")
                            if not isinstance(fargs, dict):
                                fargs = {}
                        except Exception:
                            fargs = {}
                        yield sse("tool_call", {"name": fn, "arguments": fargs})
                        _METRICS["tool_calls_total"] += 1
                        res = await execute_tool(fn, fargs, client, two_person_attested=two_person)
                        if not res["ok"]:
                            _METRICS["gate_denied_total"] += 1
                        yield sse("tool_result", {"name": fn, "ok": res["ok"],
                                                  "result": res.get("result"), "error": res.get("error"),
                                                  "gate": {"allow": res["gate"]["allow"],
                                                           "score": res["gate"]["score"],
                                                           "reason": res["gate"]["reason"]}})
                        payload["messages"].append({"role": "tool", "tool_call_id": tc.get("id", fn),
                                                    "content": json.dumps(res.get("result") or {"error": res.get("error")})[:6000]})
                    tool_round += 1
                    continue
                else:
                    collected_text = msg.get("content") or ""
                    break
            # Step 2: stream the final text token-by-token for UX.
            if collected_text:
                # We already have the final text; stream it in word chunks.
                for word in re.findall(r"\S+\s*", collected_text):
                    yield sse("token", {"text": word})
                    await asyncio.sleep(0)
            latency_ms = int((time.time() - t0) * 1000)
            y13 = yuyay13_response_score(collected_text, None, latency_ms)
            # R0 honesty: a locally-served turn is served by the on-box tag and
            # costs nothing — report BOTH truthfully (no router id, no estimated
            # cost). The router path keeps its real id + estimated cost.
            served_model = _map_model_for_local(model_used) if _serve_local else model_used
            cost = 0.0 if _serve_local else round(
                len(collected_text) / 4 / 1_000_000 * TIERS.get(decision["tier"], TIERS["T2"])["cost_out"], 6)
            rec = khipu_emit("chat.completion", {"conversation_id": conv_id, "model": served_model,
                                                 "tier": decision["tier"], "latency_ms": latency_ms, "yuyay13": y13})
            mem_add_message(conv_id, "assistant", collected_text, model=served_model,
                            tier=decision["tier"], latency_ms=latency_ms, cost_usd=cost,
                            yuyay13=y13, khipu_hash=rec["hash"])
            _METRICS["tokens_out_total"] += len(collected_text) // 4
            yield sse("done", {"conversation_id": conv_id, "tier": decision["tier"],
                               "model": served_model, "license_class": decision["license_class"],
                               "latency_ms": latency_ms, "cost_usd": cost, "yuyay13": y13,
                               "khipu_hash": rec["hash"], "chain_verified": True,
                               "served_locally": _serve_local, "sovereign": _serve_local,
                               "served_by": _served_by, "base_url": _serve_base,
                               "energy_source": _energy_source,
                               "dsse_digest": rec.get("dsse_digest"),
                               "dsse_signed": rec.get("dsse_signed")})
        except Exception as exc:
            _METRICS["errors_total"] += 1
            yield sse("error", {"error": str(exc)})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---- Memory endpoints ----

@router.get("/conversations")
async def list_convs(user_id: str = "founder") -> JSONResponse:
    return JSONResponse({"conversations": mem_list_conversations(user_id)})


@router.get("/conversations/{conv_id}")
async def get_conv(conv_id: str) -> JSONResponse:
    return JSONResponse(mem_get_conversation(conv_id))


@router.get("/profile/{user_id}")
async def get_profile(user_id: str) -> JSONResponse:
    return JSONResponse(mem_get_profile(user_id))


@router.post("/profile/{user_id}")
async def set_profile(user_id: str, request: Request) -> JSONResponse:
    b, _err = await _safe_body(request)
    if _err is not None:
        return _err
    mem_set_profile(user_id, b.get("prefs", {}), b.get("projects", []), b.get("doctrine_state", "v12"))
    return JSONResponse({"ok": True})


@router.get("/conversations/{conv_id}/export")
async def export_conv(conv_id: str, fmt: str = "markdown"):
    data = mem_get_conversation(conv_id)
    if fmt == "json":
        return JSONResponse(data)
    conv = data["conversation"] or {}
    md = [f"# a11oy.code conversation: {conv.get('title','')}", ""]
    for m in data["messages"]:
        who = "You" if m["role"] == "user" else "a11oy.code"
        md.append(f"**{who}**" + (f" · `{m['model']}` · {m['tier']} · {m['latency_ms']}ms · Yuyay-13 {m['yuyay13']}" if m["role"] == "assistant" and m.get("model") else ""))
        md.append("")
        md.append(m["content"] or "")
        md.append("")
    return PlainTextResponse("\n".join(md), media_type="text/markdown")


# ---- Public API key issuance (admin-gated) ----

@router.post("/v1/keys")
async def issue_key(request: Request, authorization: Optional[str] = Header(None)) -> JSONResponse:
    if not ADMIN_KEY or not authorization or authorization.split(" ")[-1] != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="admin key required (set A11OY_CODE_ADMIN_KEY).")
    b, _err = await _safe_body(request)
    if _err is not None:
        return _err
    key = "a11oy-" + secrets.token_urlsafe(24)
    with closing(_db()) as c:
        c.execute("INSERT INTO api_keys(key,owner,created,rpm,active) VALUES(?,?,?,?,1)",
                  (key, b.get("owner", "external"), time.time(), b.get("rpm", 60)))
        c.commit()
    khipu_emit("apikey.issue", {"owner": b.get("owner", "external")})
    return JSONResponse({"api_key": key, "owner": b.get("owner", "external"),
                         "base_url": "/api/a11oy/code/v1", "rpm": b.get("rpm", 60)})


# ---- Voice: STT via Whisper on HF Inference (free tier when available) ----

@router.post("/voice/stt")
async def voice_stt(file: UploadFile = File(...)) -> JSONResponse:
    _tok = _resolve_hf_token()
    if not _tok:
        return JSONResponse({"error": "STT requires HF_TOKEN for Whisper inference (no fake key)."},
                            status_code=503)
    audio = await file.read()
    client = _get_client()
    url = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"
    try:
        resp = await client.post(url, headers={"Authorization": f"Bearer {_tok}"},
                                 content=audio, timeout=120.0)
        if resp.status_code != 200:
            return JSONResponse({"error": f"whisper {resp.status_code}: {resp.text[:200]}"}, status_code=502)
        out = resp.json()
        khipu_emit("voice.stt", {"bytes": len(audio)})
        return JSONResponse({"text": out.get("text", ""), "model": "openai/whisper-large-v3"})
    except Exception as exc:
        return JSONResponse({"error": str(exc)[:300]}, status_code=502)


# TTS note: NVIDIA Riva (NIM) and Coqui TTS both require credentials/self-host we
# do not have in this Space. The UI uses the browser Web Speech API
# (speechSynthesis) for speaker-out (zero-credential, works offline). Server-side
# Riva/Coqui is documented as a gap in the GAP CHECK - NO fake key is configured.


def attach(app) -> None:
    """Called by serve.py to mount this router additively."""
    global _app
    _app = app  # capture host app so khipu_emit can DSSE-co-sign via app.state
    init_db()
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    app.include_router(router)
    print("[a11oy.code] orchestrator mounted at /api/a11oy/code/* (Doctrine v11 LOCKED; v12 PURIQ roadmap)", file=sys.stderr)


def _receipt_wiring_selftest() -> dict:
    """No-server self-test for the live energy-budget receipt wiring (Phase 1.3).

    Proves, WITHOUT a model call or a server, that:
      - _turn_energy_provenance never raises and always carries the SAMPLE label
        and an energy_source (defaults honestly to "grid" when the feed is absent).
      - _emit_turn_receipt is FAIL-OPEN: returns None (never raises) when the
        energy-budget module (#328) is absent, and a within_bound receipt when it
        is present. A receipt error can NEVER break a turn.
    Returns a dict of results; raises AssertionError only on a wiring mismatch.
    """
    out: dict = {"energy_budget_present": _energy_budget is not None,
                 "energy_signal_present": _energy_signal is not None}

    # (a) provenance is always honest + labeled, regardless of feed presence.
    prov = _turn_energy_provenance(is_local=False)
    assert "energy_source" in prov and prov["energy_source"], prov
    assert prov.get("joules_est_label") == "SAMPLE/ESTIMATE", prov
    assert prov.get("joules_est") is None, "no meter -> joules_est must be None"
    out["provenance_honest_labeled"] = True

    # (b) emit is fail-open: with the module ABSENT it returns None; with it
    #     present it returns a within_bound SAMPLE receipt. Either way: no raise.
    rcpt = _emit_turn_receipt("hello energy engine", "selftest-model",
                              is_local=False, stub=True)
    if _energy_budget is None:
        assert rcpt is None, "must degrade to None when #328 module is absent"
        out["fail_open_without_module"] = True
    else:
        assert rcpt is not None and rcpt.get("within_bound") is True, rcpt
        assert "SAMPLE/ESTIMATE" in rcpt.get("joules_est_label", ""), rcpt
        assert rcpt.get("bekenstein_bound_bits") == len(
            "hello energy engine".encode("utf-8")) * 8, rcpt
        out["emits_within_bound_receipt"] = True

    # (c) a receipt-layer error must NOT propagate (simulate by feeding a value
    #     that would explode if track_task were called unguarded).
    try:
        _emit_turn_receipt(None, "x", is_local=True, stub=False)  # None text ok
        out["fail_open_on_bad_input"] = True
    except Exception as exc:  # pragma: no cover - this is the bug we forbid
        raise AssertionError(f"receipt wiring must be fail-open, raised: {exc}")

    out["ok"] = True
    return out


if __name__ == "__main__":  # pragma: no cover - dev self-test for the #324 rewire
    print("[#324 serving-path self-test]", _serving_base_selftest())
    print("[#327 gpu-token self-test]", _gpu_token_headers_selftest())
    print("[phase-1.3 receipt-wiring self-test]", _receipt_wiring_selftest())
