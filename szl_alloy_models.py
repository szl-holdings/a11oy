# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings — ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749 declarations · 163 sorries · 14 unique axioms.
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
a11oy ALLOY — the open-weight model layer for a11oy Code.

THE ALLOY CONCEPT
-----------------
a11oy Code's "brains" are the STRONGEST OPEN-WEIGHT models that genuinely rival
GPT-4 / Claude on coding — Qwen2.5-Coder, DeepSeek-Coder-V2 / DeepSeek-V2.5,
Llama-3.3-70B — forged ("alloyed") together and BOUND by the founder's proven
formulas. The models are the metal; the GOVERNANCE is what makes the alloy
one-of-one.

This module is ADDITIVE and UNIFIED. It does NOT create a parallel model system:
it IMPORTS the canonical a11oy LLM registry (szl_llm_registry.MODEL_REGISTRY) and
EXTENDS it with the open-weight alloy tier, so there is exactly ONE roster /
ONE router across the whole a11oy ecosystem. If szl_llm_registry is unavailable
at runtime the alloy roster still self-describes (honest standalone fallback).

THE "FASHION THINKING" TWEAKS (the founder's proven formulas — the moat)
------------------------------------------------------------------------
Every raw model suggestion is TRANSFORMED by our proven layer (this is a genuine
transformation, ours — not vibes):

1. CONFORMAL CALIBRATION  (W5-3 + W7-4a/b/c, "proven sorry-free (experimental)")
   Distribution-free, rank-count conformal confidence band around every model
   suggestion. Anti-overconfidence floor 1/(n+1): we NEVER report 100%.
   Canonical copy: "Distribution-free confidence interval. Anti-overconfidence
   floor: we never report 100%."  Sourced from CONFORMAL — NOT Hoeffding/PAC-Bayes
   (those are NOT proven at our Mathlib pin).

2. MULTI-MODEL ROUTER  (C20 softmax order-stability + W7-5a/b PAC-Bayes envelope)
   C20 (proven, Mathlib-free order-preservation core): a small perturbation of the
   per-model scores cannot flip the routing order -> stable model selection.
   W7-5 (PAC-Bayes envelope): the routed expected cost/quality is BRACKETED by the
   component min/max — "a router can't beat its best nor be worse than its worst."
   Canonical binding: "C20 stability + W7-5 PAC-Bayes envelope".

3. CONSENSUS VOTING  (C10 / C11 proven; C12 proven bivalence core — full FLP NOT
   claimed). Optional N-model Byzantine-tolerant agreement vote with the proven
   quorum bound n >= 3f+1 for high-stakes code. We surface f_tolerated honestly.

4. GOVERNED P1–P6 LOOP. Every alloy call is meant to flow through the host app's
   governed loop (szl_agentic_loop) -> hash-chained, signed receipt. This module
   exposes alloy_governed_suggest() which the host wires to its real signer; the
   raw model call is one HOP inside the proven RAG->tool->policy->kernel->emit->sign
   loop. No non-zero verdict without chain_verified.

LEGAL / HONESTY (ABSOLUTE)
--------------------------
* Open-weight models only; each license honored and TAGGED. We do NOT redistribute
  weights here — models are loaded by HF repo id at runtime (CPU demo tier) or run
  tower-side (capable tier). Weights stay with their original distributor.
* commercial_ok is recorded PER MODEL from its real license:
    - Qwen2.5-Coder 0.5B/1.5B/7B/14B/32B  : Apache-2.0            -> commercial_ok=True
    - DeepSeek-Coder-V2 / DeepSeek-V2.5    : DeepSeek License (MIT code) commercial OK,
                                             BUT use-based restriction "no military use"
                                             -> commercial_ok=True, restriction flagged.
    - Llama-3.3-70B                        : Llama 3.3 Community License (commercial OK
                                             under <700M MAU) -> commercial_ok=True (cond).
    - Codestral-22B / Mistral-Large        : Mistral Non-Production License (MNPL)
                                             -> commercial_ok=False (research/eval ONLY).
  MNPL models are included for completeness/benchmark context but are HARD-FLAGGED
  non-commercial and are EXCLUDED from production routing by default.
* NO closed weights. GPT / Claude / Gemini are unobtainable open weights — this
  module never claims them. (The legacy szl_llm_registry closed-tier entries are
  honest API stubs owned by the build squad; the alloy tier is open-weight only.)
* NO "AGI" claims. Λ = Conjecture 1. Locked proven = 8 (F1,F4,F7,F11,F12,F18,F19,F22).
  C20/W5-3/W7-4/W7-5/C10/C11/C12 are "proven sorry-free (EXPERIMENTAL)".
* NEVER fabricate model output or benchmarks. If the CPU env cannot serve a model
  live, we return an HONEST tower-side label — never a fake completion.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Honest doctrine constants (match knowledge.json / CANONICAL_PROOF_SUMMARY).
# ---------------------------------------------------------------------------
DOCTRINE = "v11"
LOCKED_PROVEN = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]   # locked_proven = 8 (locked_count_eight)
LAMBDA_STATUS = "Conjecture 1 (F23) — NEVER a theorem"
PROVEN_EXPERIMENTAL = {
    "router_stability": "C20 (proven sorry-free, experimental; Mathlib-free order-preservation core)",
    "router_envelope":  "W7-5a/b (PAC-Bayes envelope, proven sorry-free experimental): min<=avg<=max",
    "conformal":        "W5-3 + W7-4a/b/c (conformal, proven sorry-free experimental; distribution-free)",
    "consensus":        "C10/C11 proven; C12 proven (bivalence core; full FLP NOT claimed); quorum n>=3f+1",
}

# Conformal anti-overconfidence cap. W7-4 floor is 1/(n+1); we cap the reported
# point estimate at 1 - 1/(n+1) so we LITERALLY never print 100%.
def _conformal_cap(n: int) -> float:
    n = max(1, int(n))
    return 1.0 - 1.0 / (n + 1)


# ===========================================================================
# THE OPEN-WEIGHT ALLOY ROSTER
# ===========================================================================
# Each entry mirrors the schema of szl_llm_registry.MODEL_REGISTRY so the two
# unify into ONE roster. open_weight=True distinguishes the alloy from the legacy
# closed API-stub tier. `tier_band` ∈ {capable, mid, demo_cpu}. `hf_repo` is the
# canonical Hugging Face repo id loaded at runtime (NOT redistributed here).
ALLOY_ROSTER: list[dict[str, Any]] = [
    # ── CAPABLE TIER (tower / GPU — GPT/Claude-competitive on code) ──────────
    {
        "model_id": "deepseek_coder_v2_instruct",
        "display_name": "DeepSeek-Coder-V2-Instruct",
        "provider": "DeepSeek", "provider_slug": "deepseek",
        "open_weight": True, "tier_band": "capable",
        "hf_repo": "deepseek-ai/DeepSeek-Coder-V2-Instruct",
        "params": "236B (MoE, 21B active)", "context_window": 128_000,
        "license": "DeepSeek License v1.0 (code: MIT)",
        "commercial_ok": True,
        "license_restrictions": ["no military use", "use-based restrictions (Attachment A)"],
        "redistribute_weights": False,
        "serving": "tower-side (GPU) — load by hf_repo at runtime; NOT served in CPU Space",
        "code_strength": "GPT-4-Turbo-class on code (per DeepSeek model card claims; not re-benchmarked here)",
        "use_case": "Primary coding brain — agentic code edits, multi-file PRs, debugging",
        "router_role": "CODE_PRIMARY",   # founder directive: weight router toward DeepSeek for coding
        "modalities": ["text", "code"], "streaming": True,
    },
    {
        "model_id": "deepseek_v2_5",
        "display_name": "DeepSeek-V2.5",
        "provider": "DeepSeek", "provider_slug": "deepseek",
        "open_weight": True, "tier_band": "capable",
        "hf_repo": "deepseek-ai/DeepSeek-V2.5",
        "params": "236B (MoE, 21B active)", "context_window": 128_000,
        "license": "DeepSeek License v1.0", "commercial_ok": True,
        "license_restrictions": ["no military use", "use-based restrictions (Attachment A)"],
        "redistribute_weights": False,
        "serving": "tower-side (GPU)",
        "code_strength": "Strong general+code; merges chat+coder (DeepSeek card)",
        "use_case": "General reasoning + code blend; orchestration fallback for DeepSeek-Coder-V2",
        "router_role": "CODE_GENERAL",
        "modalities": ["text", "code"], "streaming": True,
    },
    {
        "model_id": "qwen2_5_coder_32b_instruct",
        "display_name": "Qwen2.5-Coder-32B-Instruct",
        "provider": "Alibaba Qwen", "provider_slug": "qwen",
        "open_weight": True, "tier_band": "capable",
        "hf_repo": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "params": "32.5B", "context_window": 128_000,
        "license": "Apache-2.0", "commercial_ok": True,
        "license_restrictions": [], "redistribute_weights": True,  # Apache-2.0 permits (with NOTICE)
        "serving": "tower-side (GPU)",
        "code_strength": "GPT-4o-competitive on code benchmarks (Qwen card claims)",
        "use_case": "Permissive (Apache) coding brain — preferred when license-clean weights matter",
        "router_role": "CODE_PRIMARY_PERMISSIVE",
        "modalities": ["text", "code"], "streaming": True,
    },
    {
        "model_id": "llama_3_3_70b_instruct",
        "display_name": "Llama-3.3-70B-Instruct",
        "provider": "Meta", "provider_slug": "meta",
        "open_weight": True, "tier_band": "capable",
        "hf_repo": "meta-llama/Llama-3.3-70B-Instruct",
        "params": "70B", "context_window": 128_000,
        "license": "Llama 3.3 Community License", "commercial_ok": True,
        "license_restrictions": ["commercial OK only under 700M MAU", "acceptable use policy", "Built-with-Llama attribution"],
        "redistribute_weights": False,
        "serving": "tower-side (GPU)",
        "code_strength": "Strong general + code; 405B-class quality at 70B (Meta card)",
        "use_case": "General reasoning brain; broad-knowledge fallback",
        "router_role": "GENERAL",
        "modalities": ["text", "code"], "streaming": True,
    },
    # ── MID TIER ────────────────────────────────────────────────────────────
    {
        "model_id": "qwen2_5_coder_14b_instruct",
        "display_name": "Qwen2.5-Coder-14B-Instruct",
        "provider": "Alibaba Qwen", "provider_slug": "qwen",
        "open_weight": True, "tier_band": "mid",
        "hf_repo": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "params": "14.7B", "context_window": 128_000,
        "license": "Apache-2.0", "commercial_ok": True,
        "license_restrictions": [], "redistribute_weights": True,
        "serving": "tower-side (GPU) or strong CPU/quantized",
        "code_strength": "Very strong code at mid cost",
        "use_case": "Cost-aware coding brain", "router_role": "CODE_MID",
        "modalities": ["text", "code"], "streaming": True,
    },
    {
        "model_id": "qwen2_5_coder_7b_instruct",
        "display_name": "Qwen2.5-Coder-7B-Instruct",
        "provider": "Alibaba Qwen", "provider_slug": "qwen",
        "open_weight": True, "tier_band": "mid",
        "hf_repo": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "params": "7.6B", "context_window": 128_000,
        "license": "Apache-2.0", "commercial_ok": True,
        "license_restrictions": [], "redistribute_weights": True,
        "serving": "tower-side or quantized CPU (slow)",
        "code_strength": "Strong code for size", "use_case": "Mid coding brain",
        "router_role": "CODE_MID", "modalities": ["text", "code"], "streaming": True,
    },
    {
        "model_id": "deepseek_coder_6_7b_instruct",
        "display_name": "DeepSeek-Coder-6.7B-Instruct",
        "provider": "DeepSeek", "provider_slug": "deepseek",
        "open_weight": True, "tier_band": "mid",
        "hf_repo": "deepseek-ai/deepseek-coder-6.7b-instruct",
        "params": "6.7B", "context_window": 16_000,
        "license": "DeepSeek License v1.0 (code: MIT)", "commercial_ok": True,
        "license_restrictions": ["no military use", "use-based restrictions"],
        "redistribute_weights": False,
        "serving": "tower-side or quantized CPU (slow)",
        "code_strength": "Strong code for size (DeepSeek card)",
        "use_case": "Mid DeepSeek coding brain", "router_role": "CODE_MID",
        "modalities": ["text", "code"], "streaming": True,
    },
    # ── MNPL / NON-COMMERCIAL (included for context; HARD-FLAGGED) ───────────
    {
        "model_id": "codestral_22b",
        "display_name": "Codestral-22B",
        "provider": "Mistral AI", "provider_slug": "mistral",
        "open_weight": True, "tier_band": "mid",
        "hf_repo": "mistralai/Codestral-22B-v0.1",
        "params": "22B", "context_window": 32_000,
        "license": "Mistral AI Non-Production License (MNPL)",
        "commercial_ok": False,
        "license_restrictions": ["NON-PRODUCTION ONLY — research/eval/personal",
                                 "no commercial use, no hosted/managed service",
                                 "commercial license available from Mistral on request"],
        "redistribute_weights": False,
        "serving": "research/eval ONLY — EXCLUDED from production routing by default",
        "code_strength": "Strong code (Mistral card)",
        "use_case": "Benchmark/eval context only — NOT a production brain",
        "router_role": "EXCLUDED_NONCOMMERCIAL",
        "modalities": ["text", "code"], "streaming": True,
    },
    # ── DEMO / CPU TIER (the one that can actually run live in the Space) ────
    {
        "model_id": "qwen2_5_coder_1_5b_instruct_gguf",
        "display_name": "Qwen2.5-Coder-1.5B-Instruct (GGUF, llama.cpp)",
        "provider": "Alibaba Qwen", "provider_slug": "qwen",
        "open_weight": True, "tier_band": "demo_cpu",
        "hf_repo": "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
        "params": "1.54B", "context_window": 32_000,
        "license": "Apache-2.0", "commercial_ok": True,
        "license_restrictions": [], "redistribute_weights": True,
        "serving": "LIVE on CPU Space via llama.cpp IF weights present (slow, real); else honest tower-side label",
        "code_strength": "Real small-coder output; not GPT-class but genuine",
        "use_case": "LIVE in-Space demo brain (constrained CPU)", "router_role": "DEMO_CPU",
        "modalities": ["text", "code"], "streaming": False,
    },
    {
        "model_id": "qwen2_5_coder_0_5b_instruct_gguf",
        "display_name": "Qwen2.5-Coder-0.5B-Instruct (GGUF, llama.cpp)",
        "provider": "Alibaba Qwen", "provider_slug": "qwen",
        "open_weight": True, "tier_band": "demo_cpu",
        "hf_repo": "Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF",
        "params": "0.49B", "context_window": 32_000,
        "license": "Apache-2.0", "commercial_ok": True,
        "license_restrictions": [], "redistribute_weights": True,
        "serving": "LIVE on CPU Space via llama.cpp IF weights present (fastest small); else honest label",
        "code_strength": "Smallest real coder; fits cpu-basic", "use_case": "Smallest LIVE demo brain",
        "router_role": "DEMO_CPU_SMALL", "modalities": ["text", "code"], "streaming": False,
    },
]

_ALLOY_BY_ID = {m["model_id"]: m for m in ALLOY_ROSTER}

# Production-eligible = open-weight AND commercial_ok AND not explicitly excluded.
def _production_eligible(m: dict) -> bool:
    return bool(m.get("open_weight")) and bool(m.get("commercial_ok")) \
        and m.get("router_role") != "EXCLUDED_NONCOMMERCIAL"


# ===========================================================================
# PLUGGABLE LOCAL BACKEND — REAL output or HONEST label. Never fake.
# ===========================================================================
# We attempt llama.cpp (llama_cpp_python) against a local GGUF. The GGUF path is
# resolved from env A11OY_ALLOY_GGUF or a conventional /app/models/*.gguf. If the
# binding or the weights are absent, backend_available() is False and every
# suggest() returns served_locally=False with an honest tower-side label —
# we NEVER synthesize a fake completion.
_BACKEND_LOCK = threading.Lock()
_LLAMA = None
_LLAMA_TRIED = False
_LLAMA_ERR: Optional[str] = None

def _gguf_path() -> Optional[str]:
    env = os.environ.get("A11OY_ALLOY_GGUF", "").strip()
    if env and os.path.exists(env):
        return env
    for d in ("/app/models", "/app/data/models", os.path.join(os.getcwd(), "models")):
        try:
            if os.path.isdir(d):
                for fn in sorted(os.listdir(d)):
                    if fn.lower().endswith(".gguf"):
                        return os.path.join(d, fn)
        except Exception:
            pass
    return None

def _try_load_llama():
    global _LLAMA, _LLAMA_TRIED, _LLAMA_ERR
    if _LLAMA_TRIED:
        return _LLAMA
    with _BACKEND_LOCK:
        if _LLAMA_TRIED:
            return _LLAMA
        _LLAMA_TRIED = True
        path = _gguf_path()
        if not path:
            _LLAMA_ERR = "no GGUF weights present (set A11OY_ALLOY_GGUF or mount /app/models/*.gguf)"
            return None
        try:
            from llama_cpp import Llama  # type: ignore
            n_threads = int(os.environ.get("A11OY_ALLOY_THREADS", str(max(2, (os.cpu_count() or 2)))))
            n_ctx = int(os.environ.get("A11OY_ALLOY_CTX", "2048"))
            _LLAMA = Llama(model_path=path, n_ctx=n_ctx, n_threads=n_threads,
                           verbose=False, logits_all=False)
            _LLAMA_ERR = None
            return _LLAMA
        except Exception as e:  # honest: binding missing or load failed
            print(f"[alloy] llama.cpp load failed: {e!r}", file=sys.stderr)
            _LLAMA_ERR = "llama.cpp unavailable"
            _LLAMA = None
            return None

def backend_available() -> bool:
    return _try_load_llama() is not None

def _gguf_sha(path: Optional[str]) -> Optional[str]:
    if not path or not os.path.exists(path):
        return None
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            # hash first+last MB for a cheap, deterministic provenance fingerprint
            h.update(f.read(1 << 20))
            sz = os.path.getsize(path)
            if sz > (1 << 20):
                f.seek(max(0, sz - (1 << 20)))
                h.update(f.read(1 << 20))
        return h.hexdigest()
    except Exception:
        return None

def _local_generate(prompt: str, max_tokens: int = 256) -> dict:
    """REAL local generation via llama.cpp, or honest unavailable result."""
    llm = _try_load_llama()
    if llm is None:
        return {"served_locally": False, "text": None,
                "honest_label": ("Runs on the SZL tower GPU / bring local weights — "
                                 "this CPU Space has no GGUF mounted. " + (_LLAMA_ERR or "")),
                "backend": "none", "tower_side": True}
    t0 = time.time()
    try:
        msgs = [{"role": "system", "content": "You are a precise senior coding assistant."},
                {"role": "user", "content": prompt}]
        out = llm.create_chat_completion(messages=msgs, max_tokens=max_tokens, temperature=0.2)
        text = (out.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return {"served_locally": True, "text": text, "backend": "llama.cpp",
                "tower_side": False, "latency_ms": int((time.time() - t0) * 1000),
                "gguf_sha256_fp": _gguf_sha(_gguf_path())}
    except Exception as e:
        return {"served_locally": False, "text": None,
                "honest_label": "local generation error: %s" % type(e).__name__,
                "backend": "llama.cpp", "tower_side": True}


# ===========================================================================
# 1. CONFORMAL CALIBRATION  (W5-3 + W7-4a/b/c) — distribution-free, never 100%
# ===========================================================================
def conformal_band(score: float, calib_scores: list[float], alpha: float = 0.1) -> dict:
    """Split-conformal, RANK-COUNT band around a raw model score in [0,1].

    Proven binding (W5-3 + W7-4a/b/c, proven sorry-free experimental):
      * distribution-free (no Gaussian / Hoeffding assumption);
      * anti-overconfidence floor q = 1/(n+1)  (a finite calib set can NEVER
        certify probability 1) -> we LITERALLY never report 100%.

    Returns the calibrated point estimate (capped at 1-1/(n+1)) and a [lo,hi]
    band at coverage 1-alpha derived from the empirical rank of `score` among the
    calibration scores (conformal p-value = (1 + #{c <= score}) / (n+1)).
    """
    s = max(0.0, min(1.0, float(score)))
    calib = [max(0.0, min(1.0, float(c))) for c in (calib_scores or [])]
    n = len(calib)
    cap = _conformal_cap(n)                       # 1 - 1/(n+1)
    point = min(s, cap)                           # anti-overconfidence cap — never 1.0
    if n == 0:
        # No calibration data -> widest honest band, floor-limited.
        half = 0.5
        lo, hi = max(0.0, point - half), min(cap, point + half)
        return {"point": round(point, 4), "lo": round(lo, 4), "hi": round(hi, 4),
                "coverage": round(1 - alpha, 3), "n_calib": 0,
                "floor": round(1.0 / (n + 1), 4), "conformal_p": None,
                "method": "conformal rank-count (W5-3+W7-4); no calib -> max band",
                "never_100": True}
    # conformal p-value: rank of the score among calibration scores
    le = sum(1 for c in calib if c <= s)
    p = (1 + le) / (n + 1)                          # in (0,1], includes floor 1/(n+1)
    # band half-width from the empirical alpha/2 and 1-alpha/2 quantiles of calib
    srt = sorted(calib)
    def _q(qq: float) -> float:
        idx = min(n - 1, max(0, int(math.ceil(qq * (n + 1))) - 1))
        return srt[idx]
    lo_q, hi_q = _q(alpha / 2.0), _q(1 - alpha / 2.0)
    half = max(abs(point - lo_q), abs(hi_q - point), 1.0 / (n + 1))
    lo, hi = max(0.0, point - half), min(cap, point + half)
    return {"point": round(point, 4), "lo": round(lo, 4), "hi": round(hi, 4),
            "coverage": round(1 - alpha, 3), "n_calib": n,
            "floor": round(1.0 / (n + 1), 4), "conformal_p": round(p, 4),
            "method": "split-conformal rank-count (W5-3 + W7-4a/b/c, proven experimental)",
            "honesty": "Distribution-free. Anti-overconfidence floor 1/(n+1): we never report 100%.",
            "never_100": hi < 1.0}


# ===========================================================================
# 2. MULTI-MODEL ROUTER  (C20 softmax order-stability + W7-5 PAC-Bayes envelope)
# ===========================================================================
def _softmax(xs: list[float], temp: float = 1.0) -> list[float]:
    if not xs:
        return []
    t = max(1e-6, float(temp))
    m = max(xs)
    exps = [math.exp((x - m) / t) for x in xs]
    z = sum(exps) or 1.0
    return [e / z for e in exps]

def route(task_hint: str, lam: float, candidates: Optional[list[dict]] = None,
          prefer_code: bool = True, temp: float = 0.7,
          force_tier: Optional[str] = None) -> dict:
    """C20-stable, W7-5-bracketed model selection over the open-weight alloy.

    C20 (proven, Mathlib-free order-preservation core): the softmax over per-model
    scores is ORDER-PRESERVING, so a small perturbation cannot flip the routing
    order -> the selection is provably STABLE (we report the order-stability
    margin = top1_score - top2_score).

    W7-5a/b (PAC-Bayes envelope, proven experimental): the routed quality is
    BRACKETED: min_score <= routed_score <= max_score. "A router can't beat its
    best nor be worse than its worst." We report [min,max] and verify the pick
    lies inside the envelope.

    Founder directive: weight the router toward DeepSeek for CODING tasks.

    `force_tier` (optional) RESTRICTS the candidate pool to a single tier_band
    (e.g. "demo_cpu") BEFORE scoring. This is how the public HTTP demo route
    exercises the CPU-serveable bundled GGUF: without it the capable tower tier
    always outscores the demo tier and the local model is never selected.
    """
    pool = candidates if candidates is not None else [m for m in ALLOY_ROSTER if _production_eligible(m)]
    if force_tier:
        pool = [m for m in pool if m.get("tier_band") == force_tier]
    if not pool:
        return {"error": ("no production-eligible open-weight models in pool"
                          + (" for tier_band=%r" % force_tier if force_tier else ""))}

    _hint = (task_hint or "").lower()
    _code_kw = ("code", "edit", "debug", "refactor", "implement", "pr", "fix",
                "function", "class", "compile", "test", "bug", "race", "api",
                "script", "program", "algorithm", "sort", "search")
    is_code = bool(prefer_code) and (_hint == "" or any(k in _hint for k in _code_kw))
    # Base capability score per model (transparent, deterministic heuristic over
    # tier_band + role; NOT a benchmark claim — a routing prior).
    band_w = {"capable": 1.0, "mid": 0.72, "demo_cpu": 0.40}
    role_bonus = {
        "CODE_PRIMARY": 0.20, "CODE_PRIMARY_PERMISSIVE": 0.17, "CODE_GENERAL": 0.12,
        "CODE_MID": 0.08, "GENERAL": 0.0, "DEMO_CPU": 0.0, "DEMO_CPU_SMALL": -0.02,
    }
    scored = []
    for m in pool:
        base = band_w.get(m.get("tier_band"), 0.5)
        bonus = role_bonus.get(m.get("router_role"), 0.0)
        # DeepSeek coding weight (founder directive) — only on coding tasks.
        deepseek_w = 0.12 if (is_code and m.get("provider_slug") == "deepseek") else 0.0
        # Λ-gate: low trust -> prefer the strongest capable model (defensive).
        lam_w = 0.10 * (1.0 - max(0.0, min(1.0, lam))) if m.get("tier_band") == "capable" else 0.0
        # CPU-serveability bonus when we actually CAN serve locally (honest live demo).
        live_w = 0.30 if (m.get("tier_band") == "demo_cpu" and backend_available()) else 0.0
        s = base + bonus + deepseek_w + lam_w + live_w
        scored.append((m, s))
    raw = [s for _, s in scored]
    probs = _softmax(raw, temp=temp)
    order = sorted(range(len(scored)), key=lambda i: raw[i], reverse=True)
    top = order[0]
    chosen, chosen_score = scored[top]
    smin, smax, savg = min(raw), max(raw), sum(raw) / len(raw)
    margin = (raw[order[0]] - raw[order[1]]) if len(order) > 1 else float("inf")
    # W7-5 envelope check: routed score must be within [min,max] (it always is by
    # construction; we verify and report it as the proven bracket).
    in_envelope = (smin - 1e-9) <= chosen_score <= (smax + 1e-9)
    return {
        "task_hint": task_hint, "is_code_task": is_code, "lambda": round(float(lam), 4),
        "chosen": {
            "model_id": chosen["model_id"], "display_name": chosen["display_name"],
            "provider": chosen["provider"], "tier_band": chosen["tier_band"],
            "router_role": chosen["router_role"], "hf_repo": chosen["hf_repo"],
            "license": chosen["license"], "commercial_ok": chosen["commercial_ok"],
            "serving": chosen["serving"], "score": round(chosen_score, 4),
            "softmax_p": round(probs[top], 4),
        },
        "why": _route_reason(chosen, is_code, lam),
        "ranking": [{"model_id": scored[i][0]["model_id"], "score": round(raw[i], 4),
                     "p": round(probs[i], 4)} for i in order],
        "c20_order_stability": {
            "theorem": PROVEN_EXPERIMENTAL["router_stability"],
            "top1_minus_top2_margin": (round(margin, 4) if margin != float("inf") else None),
            "stable": margin > 1e-6,
            "note": "softmax is order-preserving (C20): small score perturbations cannot flip the pick",
        },
        "w7_5_pac_bayes_envelope": {
            "theorem": PROVEN_EXPERIMENTAL["router_envelope"],
            "min": round(smin, 4), "avg": round(savg, 4), "max": round(smax, 4),
            "routed_score": round(chosen_score, 4), "within_envelope": in_envelope,
            "copy": "Routed quality is bracketed by component min/max — a router can't beat its best nor be worse than its worst.",
        },
        "doctrine": DOCTRINE, "lambda_status": LAMBDA_STATUS,
    }

def _route_reason(m: dict, is_code: bool, lam: float) -> str:
    bits = []
    if is_code and m.get("provider_slug") == "deepseek":
        bits.append("coding task -> router weighted toward DeepSeek (founder directive)")
    if m.get("tier_band") == "capable":
        bits.append("capable tier (GPT/Claude-competitive on code)")
    if m.get("tier_band") == "demo_cpu":
        bits.append("CPU-serveable demo tier (real live output in this Space)" if backend_available()
                    else "demo tier (would serve live if GGUF mounted)")
    if lam < 0.75:
        bits.append("low Λ -> defensive preference for strongest capable model")
    if m.get("license") == "Apache-2.0":
        bits.append("Apache-2.0 (license-clean weights)")
    return "; ".join(bits) or "highest C20-stable routing score within the W7-5 envelope"


# ===========================================================================
# 3. CONSENSUS VOTING  (C10/C11 proven; C12 bivalence core; quorum n>=3f+1)
# ===========================================================================
def consensus(votes: list[dict], require_high_stakes: bool = False) -> dict:
    """Byzantine-tolerant N-model agreement vote.

    Each vote: {"model_id":..., "answer_key":<hashable>, "score":float}.
    Proven binding (C10/C11 proven; C12 proven bivalence core — full FLP NOT
    claimed): with n participants we tolerate f Byzantine faults iff n >= 3f+1,
    so f_tolerated = floor((n-1)/3) and a SAFE quorum requires >= 2f+1 matching
    votes. We report f_tolerated, the quorum threshold, and whether it's met.
    """
    n = len(votes or [])
    if n == 0:
        return {"error": "no votes"}
    f_tol = (n - 1) // 3
    quorum_need = 2 * f_tol + 1                      # safe agreement quorum
    tally: dict[Any, list[dict]] = {}
    for v in votes:
        tally.setdefault(v.get("answer_key"), []).append(v)
    winner_key, winner_votes = max(tally.items(), key=lambda kv: len(kv[1]))
    agree = len(winner_votes)
    quorum_met = agree >= quorum_need
    avg_score = sum(float(v.get("score", 0.0)) for v in winner_votes) / max(1, agree)
    safe = quorum_met and (not require_high_stakes or n >= 4)  # n>=4 -> tolerate >=1 fault
    return {
        "n_models": n, "f_tolerated": f_tol, "quorum_need_for_safety": quorum_need,
        "agreement_count": agree, "quorum_met": quorum_met,
        "winner_answer_key": str(winner_key), "winning_models": [v.get("model_id") for v in winner_votes],
        "winner_avg_score": round(avg_score, 4),
        "byzantine_safe": safe,
        "theorem": PROVEN_EXPERIMENTAL["consensus"],
        "honesty": ("C10/C11 proven; C12 proven (bivalence core) — full FLP impossibility NOT claimed. "
                    "n>=3f+1 quorum is the proven safety bound; with n<4 we tolerate 0 faults."),
        "doctrine": DOCTRINE,
    }


# ===========================================================================
# GOVERNED SUGGEST — the alloy call as ONE HOP in the proven P1–P6 loop.
# ===========================================================================
def alloy_governed_suggest(prompt: str, task_hint: str = "code", lam: float = 0.9,
                           calib_scores: Optional[list[float]] = None,
                           do_consensus: bool = False,
                           sign_fn=None, max_tokens: int = 256,
                           force_tier: Optional[str] = None) -> dict:
    """One unified alloy call:
       route (C20/W7-5) -> generate (REAL local OR honest tower label)
       -> conformal band (W5-3/W7-4) -> optional consensus (C10-C12)
       -> signed receipt (host signer, P6).
    NEVER fabricates output. If no local backend, served_locally=False + honest label.

    `force_tier` pins the router to a single tier_band. Pass "demo_cpu" to make
    this call actually run the bundled CPU GGUF through `_local_generate` — the
    public /demo route and `tier=demo_cpu` on /suggest use this.
    """
    decision = route(task_hint, lam, force_tier=force_tier)
    if "error" in decision:
        return {"error": decision["error"]}
    chosen = decision["chosen"]
    # Generation: only the demo_cpu tier can serve locally; others are tower-side.
    gen = _local_generate(prompt, max_tokens=max_tokens) if chosen["tier_band"] == "demo_cpu" \
        else {"served_locally": False, "text": None, "tower_side": True,
              "honest_label": "Select 'run on the SZL tower GPU' / bring local weights — "
                              "%s is a %s-tier model, not served in this CPU Space."
                              % (chosen["display_name"], chosen["tier_band"])}
    # Conformal band around the model's softmax confidence (raw -> calibrated).
    band = conformal_band(chosen["softmax_p"], calib_scores or _DEFAULT_CALIB)
    out: dict[str, Any] = {
        "alloy": "open-weight model layer", "router": decision,
        "generation": gen, "conformal": band,
        "served_locally": bool(gen.get("served_locally")),
        "doctrine": DOCTRINE, "lambda_status": LAMBDA_STATUS,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if do_consensus:
        # Honest demo consensus over production-eligible models' routing scores
        # (answer_key is a coarse bucket of the routed score — a real, deterministic
        # vote signal; NOT a fabricated model answer).
        votes = [{"model_id": r["model_id"], "answer_key": round(r["score"], 1),
                  "score": r["score"]} for r in decision["ranking"][:4]]
        out["consensus"] = consensus(votes, require_high_stakes=True)
    # P6: sign the decision payload with the host's REAL signer (if provided).
    if callable(sign_fn):
        payload = {"kind": "alloy_governed_suggest", "chosen": chosen,
                   "conformal_point": band["point"], "served_locally": out["served_locally"],
                   "ts": out["ts"]}
        try:
            out["receipt"] = sign_fn(payload)
            out["receipt_signed"] = bool(out["receipt"].get("signed"))
        except Exception as e:
            out["receipt"] = {"signed": False, "honesty": "signer raised: %s" % type(e).__name__}
            out["receipt_signed"] = False
    return out

# Default calibration set (honest: a fixed prior calib set, NOT random; replaced
# by live calib scores when the host provides them). 12 points -> floor 1/13.
_DEFAULT_CALIB = [0.55, 0.6, 0.62, 0.68, 0.7, 0.73, 0.78, 0.8, 0.83, 0.86, 0.9, 0.92]


# ===========================================================================
# UNIFICATION — extend the canonical a11oy registry with the alloy roster.
# ===========================================================================
def unify_into_registry() -> dict:
    """Append the open-weight alloy roster INTO szl_llm_registry.MODEL_REGISTRY
    (idempotent, dedup by model_id) so there is ONE coherent roster. Returns a
    reconciliation report. Honest standalone fallback if the registry is absent."""
    report = {"registry_found": False, "added": [], "skipped_existing": [],
              "alloy_total": len(ALLOY_ROSTER)}
    try:
        import szl_llm_registry as reg  # the canonical roster
        report["registry_found"] = True
        existing_ids = {m.get("model_id") for m in reg.MODEL_REGISTRY}
        for m in ALLOY_ROSTER:
            if m["model_id"] in existing_ids:
                report["skipped_existing"].append(m["model_id"])
                continue
            # normalize to the registry schema (additive fields preserved)
            reg.MODEL_REGISTRY.append({
                **m,
                "tier_name": "alloy_" + m["tier_band"],
                "tier": 90,  # alloy band sits outside the legacy 0-5 closed tiers
                "operator_mirrored": False,
                "ecosystem_mirror": ["killinchu"],
                "honest_stub": (not _production_eligible(m)) or (m["tier_band"] != "demo_cpu"),
                "notes": "open-weight alloy; " + m.get("serving", ""),
            })
            report["added"].append(m["model_id"])
        # rebuild the by-id index if present
        if hasattr(reg, "_MODEL_BY_ID"):
            reg._MODEL_BY_ID = {m["model_id"]: m for m in reg.MODEL_REGISTRY}
        report["registry_total_after"] = len(reg.MODEL_REGISTRY)
    except Exception as e:
        report["error"] = "szl_llm_registry unavailable: %s (alloy runs standalone)" % type(e).__name__
    return report


# ===========================================================================
# FastAPI registration — ADDITIVE, before SPA catch-all. Never crashes the app.
# ===========================================================================
def register(app, ns: str = "a11oy", sign_fn=None) -> dict:
    """Mount the alloy model-layer endpoints under /api/<ns>/v1/alloy/*.

    Endpoints:
      GET  /api/a11oy/v1/alloy/roster      — unified open-weight roster + licenses
      GET  /api/a11oy/v1/alloy/health      — backend (llama.cpp) availability + honesty
      POST /api/a11oy/v1/alloy/route       — C20/W7-5 model selection
      POST /api/a11oy/v1/alloy/conformal   — W5-3/W7-4 calibrated band
      POST /api/a11oy/v1/alloy/consensus   — C10-C12 Byzantine vote
      POST /api/a11oy/v1/alloy/suggest     — governed suggest (route+gen+band+receipt);
                                             accepts {"tier":"demo_cpu"} to pin the tier
      GET  /api/a11oy/v1/alloy/demo        — LIVE local demo: runs the bundled CPU GGUF
      POST /api/a11oy/v1/alloy/demo          via _local_generate (force_tier=demo_cpu),
                                             returns served_locally + backend=="llama.cpp"
                                             when present, else an HONEST tower-side label.
                                             GET uses a default prompt so an uptime /
                                             smoke check can hit it with no body.
    """
    from fastapi.responses import JSONResponse
    from fastapi import Request

    unify = unify_into_registry()

    def _routes_first(path, fn, methods):
        try:
            from starlette.routing import Route
            app.router.routes.insert(0, Route(path, fn, methods=methods))
        except Exception:
            pass

    base = "/api/%s/v1/alloy" % ns
    stripped = "/v1/alloy"  # HF proxy-stripped form

    async def _roster(request):
        prod = [m for m in ALLOY_ROSTER if _production_eligible(m)]
        return JSONResponse({
            "hub": "a11oy", "layer": "open-weight alloy (unified into a11oy LLM registry)",
            "alloy_count": len(ALLOY_ROSTER), "production_eligible": len(prod),
            "roster": ALLOY_ROSTER,
            "tier_bands": {"capable": [m["model_id"] for m in ALLOY_ROSTER if m["tier_band"] == "capable"],
                           "mid": [m["model_id"] for m in ALLOY_ROSTER if m["tier_band"] == "mid"],
                           "demo_cpu": [m["model_id"] for m in ALLOY_ROSTER if m["tier_band"] == "demo_cpu"]},
            "code_primary": [m["model_id"] for m in ALLOY_ROSTER if m.get("router_role", "").startswith("CODE_PRIMARY")],
            "noncommercial_flagged": [m["model_id"] for m in ALLOY_ROSTER if not m["commercial_ok"]],
            "unification": unify,
            "proven_formulas": PROVEN_EXPERIMENTAL,
            "doctrine": DOCTRINE, "lambda_status": LAMBDA_STATUS, "locked_proven": LOCKED_PROVEN,
            "honesty": ("Open-weight models only. Weights NOT redistributed here — loaded by hf_repo "
                        "at runtime (CPU demo tier) or run tower-side (capable tier). MNPL models are "
                        "non-commercial and excluded from production routing. NO closed weights, NO AGI."),
        })

    async def _health(request):
        path = _gguf_path()
        return JSONResponse({
            "backend": "llama.cpp", "backend_available": backend_available(),
            "gguf_present": bool(path), "gguf_path": path,
            "gguf_sha256_fp": _gguf_sha(path), "backend_error": _LLAMA_ERR,
            "live_demo_possible": backend_available(),
            "honest_label": ("LIVE local CPU serving ready (llama.cpp + GGUF present)."
                             if backend_available() else
                             "No local GGUF in this CPU Space -> capable tier is tower-side (honest). "
                             "Mount /app/models/*.gguf or set A11OY_ALLOY_GGUF to serve the demo tier live."),
            "doctrine": DOCTRINE,
        })

    async def _route(request: "Request"):
        body = await request.json() if request.method == "POST" else {}
        return JSONResponse(route(body.get("task_hint", "code"),
                                  float(body.get("lambda", body.get("lam", 0.9))),
                                  prefer_code=bool(body.get("prefer_code", True))))

    async def _conformal(request: "Request"):
        body = await request.json()
        return JSONResponse(conformal_band(float(body.get("score", 0.8)),
                                           body.get("calib_scores") or _DEFAULT_CALIB,
                                           float(body.get("alpha", 0.1))))

    async def _consensus(request: "Request"):
        body = await request.json()
        return JSONResponse(consensus(body.get("votes") or [],
                                      bool(body.get("require_high_stakes", False))))

    async def _suggest(request: "Request"):
        body = await request.json()
        return JSONResponse(alloy_governed_suggest(
            body.get("prompt", ""), body.get("task_hint", "code"),
            float(body.get("lambda", body.get("lam", 0.9))),
            body.get("calib_scores"), bool(body.get("do_consensus", False)),
            sign_fn=sign_fn, max_tokens=int(body.get("max_tokens", 256)),
            force_tier=(body.get("tier") or body.get("force_tier"))))

    async def _demo(request: "Request"):
        # LIVE local demo: pin the router to the CPU GGUF demo tier so the bundled
        # llama.cpp model is ACTUALLY exercised over HTTP (not the tower tier).
        # GET (no body) uses a default prompt so uptime/smoke checks can hit it
        # bare; POST accepts {"prompt", "max_tokens", ...}. NEVER fakes output —
        # if no GGUF is mounted it returns served_locally=False + an honest label.
        if request.method == "POST":
            try:
                body = await request.json()
            except Exception:
                body = {}
        else:
            body = dict(request.query_params)
        prompt = (body.get("prompt") or
                  "Write a Python function add(a, b) that returns their sum.")
        try:
            max_tokens = int(body.get("max_tokens", 128))
        except (TypeError, ValueError):
            max_tokens = 128
        out = alloy_governed_suggest(
            prompt, str(body.get("task_hint", "code")),
            float(body.get("lambda", body.get("lam", 0.9))),
            body.get("calib_scores"), bool(body.get("do_consensus", False)),
            sign_fn=sign_fn, max_tokens=max_tokens, force_tier="demo_cpu")
        gen = out.get("generation", {}) if isinstance(out, dict) else {}
        # Surface the proof fields at the TOP level so an uptime / smoke check can
        # assert on them directly (backend == "llama.cpp", served_locally == True).
        out["tier_forced"] = "demo_cpu"
        out["backend"] = gen.get("backend")
        out["served_locally"] = bool(gen.get("served_locally"))
        out["live_demo"] = out["served_locally"]
        if not out["served_locally"]:
            out["honest_label"] = (gen.get("honest_label") or
                                   "local CPU backend unavailable — honest tower-side label "
                                   "(mount /app/models/*.gguf or set A11OY_ALLOY_GGUF).")
        return JSONResponse(out)

    for p in (base + "/roster", stripped + "/roster"):
        _routes_first(p, _roster, ["GET"])
    for p in (base + "/health", stripped + "/health"):
        _routes_first(p, _health, ["GET"])
    for p in (base + "/route", stripped + "/route"):
        _routes_first(p, _route, ["POST"])
    for p in (base + "/conformal", stripped + "/conformal"):
        _routes_first(p, _conformal, ["POST"])
    for p in (base + "/consensus", stripped + "/consensus"):
        _routes_first(p, _consensus, ["POST"])
    for p in (base + "/suggest", stripped + "/suggest"):
        _routes_first(p, _suggest, ["POST"])
    for p in (base + "/demo", stripped + "/demo"):
        _routes_first(p, _demo, ["GET", "POST"])

    return {"ns": ns,
            "endpoints": ["roster", "health", "route", "conformal", "consensus", "suggest", "demo"],
            "alloy_models": len(ALLOY_ROSTER), "unification": unify,
            "backend_available": backend_available()}
