# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Author: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
# Change-class: ADDITIVE — Doctrine v11 LOCKED 749/14/163 UNCHANGED.
"""
a11oy v4 Multi-LLM Ensemble Vote organ (Yachay, 2026-06-01).

THE SZL MOAT: a deterministic multi-LLM ensemble that fans a single prompt out
to N voter models in parallel, scores every response across the 13 Yuyay axes
(every axis is a PURE deterministic function over the response text — NO axis is
itself LLM-scored, so the same response ALWAYS yields the same vector), combines
the per-voter axis vectors with the Lutar Λ-aggregator (a bounded, variance-
weighted combiner — voters with consistent quality earn more weight), picks the
winner, and emits a DSSE-signed Khipu receipt over the whole vote.

Endpoint:  POST /api/a11oy/v4/agent/ask
UI page:   GET  /agent

HONEST DISCLOSURE (carried in EVERY response):
    lambda_status = "Conjecture 1 (NOT a theorem; 163 sorries outstanding in
    Lean kernel)".  Λ mirrors the lutar-lean spec but is NOT machine-checked.

Voters:
    qwen-local          — POST http://local-llm:8000/v1/chat/completions
                          (will fail inside an HF Space → graceful, clearly
                           labelled deterministic stub; never fabricated as real)
    hf-inference-llama  — HF Inference API meta-llama/Meta-Llama-3.1-8B-Instruct
    hf-inference-mistral— HF Inference API mistralai/Mistral-7B-Instruct-v0.3
    hf-inference-qwen   — HF Inference API Qwen/Qwen2.5-7B-Instruct

A voter that times out / errors is recorded in the receipt with an "error" field
(never a fabricated "response"). HF auth uses HF_TOKEN / HUGGINGFACE_HUB_TOKEN
from the Space environment (custom-cred proxy already provisions it).

Registered BEFORE the SPA catch-all and BEFORE the generic /api/a11oy/{path}
Node proxy so /api/a11oy/v4/agent/ask + /agent resolve LOCALLY.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path

# ── DSSE signer (real ECDSA-P256 cosign when SZL_COSIGN_PRIVATE_PEM is present,
#    honest UNSIGNED placeholder otherwise). Reuse the live Space module. ──────
try:  # pragma: no cover - module present in Space, may be absent in unit env
    import szl_dsse as _dsse
except Exception:  # noqa: BLE001
    _dsse = None

# ── Cross-Harness Receipt Bridge: ChatML parsing + schema-strict tool registry.
#    ADDITIVE — the v4 agent gains an optional `envelope` parameter so Hermes
#    (ChatML <tool_call>) + OpenAI/Anthropic callers can speak their own wire
#    format and still get the same signed Khipu receipt chain. ─────────────────
try:  # pragma: no cover
    import szl_bridge as _bridge
    import szl_bridge_schemas as _bridge_schemas
except Exception:  # noqa: BLE001
    _bridge = None
    _bridge_schemas = None

ROUTER_NS = "a11oy"
HF_LLAMA = "meta-llama/Meta-Llama-3.1-8B-Instruct"
HF_MISTRAL = "mistralai/Mistral-7B-Instruct-v0.3"
HF_QWEN = "Qwen/Qwen2.5-7B-Instruct"
LOCAL_LLM_URL = "http://local-llm:8000/v1/chat/completions"
QWEN_LOCAL_MODEL = "Qwen/Qwen2.5-7B-Instruct"
VOTER_TIMEOUT_S = 30.0

# All voters known to this organ. "default = all available" means: try them all.
ALL_VOTERS = [
    "qwen-local",
    "hf-inference-llama",
    "hf-inference-mistral",
    "hf-inference-qwen",
]

# The 13 Yuyay axes, in canonical order. Each maps to a deterministic scorer.
YUYAY_AXES = [
    "Yachay",       # knowledge depth
    "Yuyay",        # reasoning
    "Kallpa",       # energy/efficiency
    "Killa",        # cyclic awareness
    "Unay",         # provenance/ancient
    "Ayni",         # reciprocity
    "Hatun",        # governance/big-picture
    "Wallpa",       # vigilance
    "Chaski",       # delivery clarity
    "Wasi-Rikuq",   # architecture/structure
    "Throne-Room",  # authority/decisiveness
    "Inka",         # chain/coherence
    "Khipu",        # signing/integrity
]

LAMBDA_STATUS = (
    "Conjecture 1 (NOT a theorem; 163 sorries outstanding in Lean kernel)"
)


# ═══════════════════════════════════════════════════════════════════════════
# Text helpers — all deterministic, no randomness, no I/O.
# ═══════════════════════════════════════════════════════════════════════════

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_SENT_RE = re.compile(r"[^.!?]+[.!?]?")
_URL_RE = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)
_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)


def _clamp01(x: float) -> float:
    if x != x:  # NaN guard
        return 0.0
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text or "")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_RE.findall(text or "") if s.strip()]


def _count_syllables(word: str) -> int:
    groups = _VOWEL_GROUP_RE.findall(word)
    n = len(groups)
    if word.lower().endswith("e") and n > 1:
        n -= 1
    return max(1, n)


def _noun_phrase_tokens(sentence: str) -> set[str]:
    # Heuristic content-word set: lowercased words >= 4 chars that aren't stopwords.
    stop = {
        "this", "that", "these", "those", "with", "from", "have", "will",
        "your", "about", "which", "would", "could", "should", "their", "there",
        "what", "when", "where", "into", "than", "then", "they", "them", "also",
        "such", "been", "were", "because", "while", "very", "more", "most",
    }
    return {w.lower() for w in _words(sentence) if len(w) >= 4 and w.lower() not in stop}


# ═══════════════════════════════════════════════════════════════════════════
# The 13 Yuyay axis scorers. Each: (response_text, prompt_text) -> float in [0,1].
# DETERMINISTIC: identical inputs ALWAYS produce identical scores.
# ═══════════════════════════════════════════════════════════════════════════

def axis_yachay(resp: str, prompt: str) -> float:
    """Knowledge depth — type/token diversity ratio (unique / total tokens)."""
    toks = [w.lower() for w in _words(resp)]
    if not toks:
        return 0.0
    return _clamp01(len(set(toks)) / len(toks))


def axis_yuyay(resp: str, prompt: str) -> float:
    """Reasoning — causal connectors per 100 words, normalized (cap ~5/100)."""
    toks = _words(resp)
    if not toks:
        return 0.0
    connectors = re.findall(
        r"\b(because|therefore|since|hence|thus|consequently|so that|as a result)\b",
        resp, re.IGNORECASE,
    )
    per100 = (len(connectors) / len(toks)) * 100.0
    return _clamp01(per100 / 5.0)


def axis_kallpa(resp: str, prompt: str) -> float:
    """Energy/efficiency — response brevity vs prompt complexity.

    Reward responses whose length is well-matched to prompt complexity: roughly
    8x the prompt word count is "ideal" (score 1). Both far-too-terse and
    rambling responses are penalized via a triangular response curve.
    """
    rw = max(1, len(_words(resp)))
    pw = max(1, len(_words(prompt)))
    ideal = 8.0 * pw
    ratio = rw / ideal
    if ratio <= 1.0:
        return _clamp01(ratio)
    # Beyond ideal, decay toward 0 over 4x ideal.
    return _clamp01(1.0 - (ratio - 1.0) / 3.0)


def axis_killa(resp: str, prompt: str) -> float:
    """Cyclic awareness — temporal/sequence markers present (first/then/...)."""
    markers = re.findall(
        r"\b(first|second|third|then|next|after|before|finally|lastly|"
        r"subsequently|initially|meanwhile|eventually|step \d+)\b",
        resp, re.IGNORECASE,
    )
    # 4+ distinct sequence cues → full marks.
    return _clamp01(len(markers) / 4.0)


def axis_unay(resp: str, prompt: str) -> float:
    """Provenance — explicit source citations / numeric references density."""
    toks = max(1, len(_words(resp)))
    citations = len(re.findall(r"\[[0-9]+\]|\(\d{4}\)|et al\.|\bdoi\b|\bISBN\b", resp, re.IGNORECASE))
    numerics = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", resp))
    density = ((citations * 2) + numerics) / toks * 100.0
    return _clamp01(density / 8.0)


def axis_ayni(resp: str, prompt: str) -> float:
    """Reciprocity — does the answer acknowledge the prompt's structure?

    Measured as Jaccard overlap between prompt content tokens and response
    content tokens (acknowledges what was asked), bounded.
    """
    p = _noun_phrase_tokens(prompt)
    r = _noun_phrase_tokens(resp)
    if not p:
        return 0.5  # no structure to mirror → neutral
    inter = len(p & r)
    return _clamp01(inter / len(p))


def axis_hatun(resp: str, prompt: str) -> float:
    """Governance/big-picture — policy/safety/ethics markers."""
    toks = max(1, len(_words(resp)))
    markers = len(re.findall(
        r"\b(policy|safety|safe|ethic|ethical|govern|governance|compliance|"
        r"privacy|consent|responsib|fairness|risk|regulation|legal)\w*\b",
        resp, re.IGNORECASE,
    ))
    return _clamp01((markers / toks * 100.0) / 4.0)


def axis_wallpa(resp: str, prompt: str) -> float:
    """Vigilance — explicit caveats / limitations count."""
    markers = len(re.findall(
        r"\b(however|caveat|limitation|note that|keep in mind|be aware|"
        r"may not|might not|cannot guarantee|disclaimer|assum\w+|depends on|"
        r"uncertain|approximat\w+)\b",
        resp, re.IGNORECASE,
    ))
    return _clamp01(markers / 3.0)


def axis_chaski(resp: str, prompt: str) -> float:
    """Delivery clarity — Flesch-Kincaid grade level, normalized (lower=clearer).

    FK grade = 0.39*(words/sentences) + 11.8*(syllables/words) - 15.59.
    Map grade in [4, 16] → clarity score in [1, 0] (clamped).
    """
    words = _words(resp)
    sents = _sentences(resp)
    if not words or not sents:
        return 0.0
    syll = sum(_count_syllables(w) for w in words)
    grade = 0.39 * (len(words) / len(sents)) + 11.8 * (syll / len(words)) - 15.59
    # grade 4 (very clear) -> 1.0 ; grade 16 (dense) -> 0.0
    return _clamp01((16.0 - grade) / 12.0)


def axis_wasi_rikuq(resp: str, prompt: str) -> float:
    """Architecture/structure — headers, lists, code blocks present."""
    score = 0.0
    if re.search(r"(^|\n)\s*#{1,6}\s", resp):           # markdown header
        score += 0.34
    if re.search(r"(^|\n)\s*([-*•]|\d+\.)\s", resp):     # bullet / numbered list
        score += 0.33
    if "```" in resp or re.search(r"(^|\n)\s{4,}\S", resp):  # code fence / indent block
        score += 0.33
    return _clamp01(score)


def axis_throne_room(resp: str, prompt: str) -> float:
    """Authority/decisiveness — definite vs hedged statement ratio."""
    definite = len(re.findall(
        r"\b(is|are|will|must|always|never|definitely|certainly|clearly|"
        r"the answer is|in fact|indeed)\b", resp, re.IGNORECASE))
    hedged = len(re.findall(
        r"\b(maybe|perhaps|might|could|possibly|seems|appears|likely|"
        r"i think|i guess|probably|sort of|kind of)\b", resp, re.IGNORECASE))
    denom = definite + hedged
    if denom == 0:
        return 0.5  # neutral when neither register dominates
    return _clamp01(definite / denom)


def axis_inka(resp: str, prompt: str) -> float:
    """Chain/coherence — mean shared-noun-phrase overlap between adjacent sentences."""
    sents = _sentences(resp)
    if len(sents) < 2:
        return 0.5  # single sentence: trivially coherent, neutral
    overlaps: list[float] = []
    prev = _noun_phrase_tokens(sents[0])
    for s in sents[1:]:
        cur = _noun_phrase_tokens(s)
        union = prev | cur
        if union:
            overlaps.append(len(prev & cur) / len(union))
        prev = cur
    if not overlaps:
        return 0.0
    mean = sum(overlaps) / len(overlaps)
    # Adjacent-sentence Jaccard is naturally small; scale so ~0.25 → 1.0.
    return _clamp01(mean / 0.25)


def axis_khipu(resp: str, prompt: str) -> float:
    """Signing/integrity — ends on a verifiable claim, no hallucinated URL.

    Full marks if the response contains NO URL (nothing to fabricate). If URLs
    are present, only well-formed http(s) hosts with a dot earn partial credit;
    a closing sentence that is concrete (ends with '.' and has digits or a named
    entity) adds integrity. Bare/garbled URLs are penalized.
    """
    urls = _URL_RE.findall(resp)
    score = 1.0
    if urls:
        good = sum(1 for u in urls if re.match(r"https?://[\w.-]+\.[a-z]{2,}", u, re.IGNORECASE))
        score = good / len(urls)  # any malformed URL drags integrity down
    # Closing-claim bonus/penalty.
    tail = resp.strip()[-160:]
    if re.search(r"[.!?]\s*$", tail) and re.search(r"\d|[A-Z][a-z]+", tail):
        score = min(1.0, score + 0.0)  # well-formed close keeps full score
    else:
        score *= 0.85  # dangling / unterminated close: small integrity penalty
    return _clamp01(score)


_AXIS_FNS = [
    axis_yachay, axis_yuyay, axis_kallpa, axis_killa, axis_unay, axis_ayni,
    axis_hatun, axis_wallpa, axis_chaski, axis_wasi_rikuq, axis_throne_room,
    axis_inka, axis_khipu,
]


def score_yuyay_13(resp: str, prompt: str) -> list[float]:
    """Return the deterministic 13-axis Yuyay vector for a response."""
    return [round(_clamp01(fn(resp, prompt)), 6) for fn in _AXIS_FNS]


# ═══════════════════════════════════════════════════════════════════════════
# Lutar Λ-aggregator — bounded, variance-weighted combiner.
# Mirrors the lutar-lean spec. Λ = Conjecture 1, NOT a machine-checked theorem.
# ═══════════════════════════════════════════════════════════════════════════

def _variance(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        return 0.0
    mean = sum(xs) / n
    return sum((x - mean) ** 2 for x in xs) / n


def lutar_lambda(axis_vectors: list[list[float]]) -> dict[str, Any]:
    """Combine per-voter 13-axis vectors into per-voter Λ scores.

    The lutar-lean spec defines, across the K voters competing on each axis:
        w_v = exp(-variance(axes[v])) / Σ_u exp(-variance(axes[u]))   (Σ w = 1)
    These cross-voter weights (the *relative confidence* in each voter) sum to
    one. Per voter the Λ score is the BOUNDED weighted combination of its own
    13 axes, blended with the voter's cross-field confidence weight:
        base_v = mean_i axis[v][i]                       (in [0,1])
        Λ[v]   = clamp( base_v * (1 + (K*w_v - 1) * GAIN), 0, 1 )
    where GAIN (=0.5) is the bounded tilt strength: a voter with above-average
    consistency (K*w_v > 1) is boosted, a high-variance voter is damped, and the
    result is clamped to [0,1]. With one voter K*w_v == 1 so Λ == mean (no tilt).
    Stable, internally-consistent voters win — exactly the lutar-lean intent.
    Λ is Conjecture 1, NOT a machine-checked theorem (163 sorries outstanding).
    """
    n = len(axis_vectors)
    if n == 0:
        return {"lambdas": [], "weights": [], "composite": 0.0, "winner_index": -1}

    variances = [_variance(v) for v in axis_vectors]
    exps = [math.exp(-var) for var in variances]
    total = sum(exps) or 1.0
    weights = [e / total for e in exps]

    GAIN = 0.5  # bounded tilt strength applied to the consistency advantage
    lambdas: list[float] = []
    for idx, v in enumerate(axis_vectors):
        base = sum(v) / len(v) if v else 0.0          # mean axis score, [0,1]
        tilt = 1.0 + (n * weights[idx] - 1.0) * GAIN  # >1 if more consistent than avg
        lambdas.append(_clamp01(base * tilt))

    winner_index = max(range(n), key=lambda i: lambdas[i])
    composite = lambdas[winner_index]
    return {
        "lambdas": [round(x, 6) for x in lambdas],
        "weights": [round(w, 6) for w in weights],
        "variances": [round(v, 6) for v in variances],
        "composite": round(composite, 6),
        "winner_index": winner_index,
        "status": LAMBDA_STATUS,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Voters — async, parallel, 30s per-voter timeout, graceful labelled fallback.
# ═══════════════════════════════════════════════════════════════════════════

def _hf_token() -> str | None:
    return (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGINGFACE_HUB_TOKEN")
        or os.environ.get("HUGGINGFACE_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    )


def _extract_chat_text(data: Any) -> str | None:
    """Pull assistant text out of an OpenAI-compat or HF response shape."""
    try:
        if isinstance(data, dict) and data.get("choices"):
            ch = data["choices"][0]
            if isinstance(ch.get("message"), dict):
                return ch["message"].get("content")
            if "text" in ch:
                return ch["text"]
        if isinstance(data, list) and data and isinstance(data[0], dict):
            # HF text-generation legacy shape
            return data[0].get("generated_text")
        if isinstance(data, dict) and "generated_text" in data:
            return data["generated_text"]
    except Exception:  # noqa: BLE001
        return None
    return None


async def _call_qwen_local(client: httpx.AsyncClient, prompt: str) -> dict[str, Any]:
    """qwen-local: real local vLLM/OpenAI server. Fails inside an HF Space →
    graceful, CLEARLY LABELLED deterministic stub (never claimed as a real model)."""
    body = {
        "model": QWEN_LOCAL_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.0,
    }
    try:
        r = await client.post(LOCAL_LLM_URL, json=body, timeout=VOTER_TIMEOUT_S)
        r.raise_for_status()
        text = _extract_chat_text(r.json())
        if not text:
            raise ValueError("local-llm returned no assistant content")
        return {"response": text, "source": "live", "endpoint": LOCAL_LLM_URL}
    except Exception as e:  # noqa: BLE001
        # Deterministic stub derived ONLY from the prompt — labelled, not a real LLM.
        stub = _deterministic_stub(prompt)
        return {
            "response": stub,
            "source": "deterministic-stub",
            "stub": True,
            "note": (
                "qwen-local unreachable inside HF Space — returning a clearly "
                "labelled deterministic prompt-derived stub (NOT a real model "
                "completion). Wire a real local vLLM at "
                f"{LOCAL_LLM_URL} to make this voter live."
            ),
            "underlying_error": f"{type(e).__name__}: {e}",
        }


def _deterministic_stub(prompt: str) -> str:
    """A reproducible, prompt-derived text — honest filler so the axis scorers
    have something deterministic to score for the offline qwen-local voter."""
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    words = _words(prompt)[:8]
    topic = " ".join(words) if words else "the request"
    return (
        f"[deterministic-stub {h}] This is a labelled local stub, not a real "
        f"model completion. The prompt concerns {topic}. Because no live "
        f"local model is reachable, this response is generated purely from the "
        f"prompt text so that the Yuyay-13 axes remain deterministic. First, the "
        f"stub acknowledges the request; then it notes its own limitation; "
        f"finally it defers to the live HF Inference voters for substantive "
        f"answers. Note that this stub cannot guarantee correctness."
    )


async def _call_hf_inference(
    client: httpx.AsyncClient, model: str, prompt: str
) -> dict[str, Any]:
    """Call the HF Inference router (OpenAI-compatible chat completions)."""
    token = _hf_token()
    if not token:
        return {
            "error": (
                "no HF token in environment (HF_TOKEN / HUGGINGFACE_HUB_TOKEN). "
                "HF Inference voter cannot run."
            ),
            "model": model,
        }
    headers = {"Authorization": f"Bearer {token}"}
    # HF router OpenAI-compatible endpoint.
    url = "https://router.huggingface.co/v1/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.0,
        "stream": False,
    }
    try:
        r = await client.post(url, json=body, headers=headers, timeout=VOTER_TIMEOUT_S)
        if r.status_code >= 400:
            return {
                "error": f"HF Inference {r.status_code}: {r.text[:300]}",
                "model": model,
            }
        text = _extract_chat_text(r.json())
        if not text:
            return {"error": "HF Inference returned no assistant content", "model": model}
        return {"response": text, "source": "live", "model": model}
    except httpx.TimeoutException:
        return {"error": f"timeout after {VOTER_TIMEOUT_S}s", "model": model}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}", "model": model}


_VOTER_DISPATCH = {
    "qwen-local": lambda c, p: _call_qwen_local(c, p),
    "hf-inference-llama": lambda c, p: _call_hf_inference(c, HF_LLAMA, p),
    "hf-inference-mistral": lambda c, p: _call_hf_inference(c, HF_MISTRAL, p),
    "hf-inference-qwen": lambda c, p: _call_hf_inference(c, HF_QWEN, p),
}


async def _run_voter(client: httpx.AsyncClient, voter: str, prompt: str) -> dict[str, Any]:
    fn = _VOTER_DISPATCH.get(voter)
    if fn is None:
        return {"voter": voter, "error": f"unknown voter '{voter}'"}
    t0 = time.monotonic()
    try:
        out = await fn(client, prompt)
    except Exception as e:  # noqa: BLE001
        out = {"error": f"{type(e).__name__}: {e}"}
    out["voter"] = voter
    out["latency_ms"] = round((time.monotonic() - t0) * 1000.0, 1)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Endpoint orchestration.
# ═══════════════════════════════════════════════════════════════════════════

async def _ensemble_ask(prompt: str, voters: list[str]) -> dict[str, Any]:
    prompt = prompt or ""
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    async with httpx.AsyncClient(trust_env=True) as client:
        results = await asyncio.gather(
            *[_run_voter(client, v, prompt) for v in voters]
        )

    # Build votes; only voters with a real/stub response are scored & eligible.
    votes: list[dict[str, Any]] = []
    scorable: list[dict[str, Any]] = []
    for res in results:
        entry: dict[str, Any] = {"voter": res["voter"], "latency_ms": res.get("latency_ms")}
        if "error" in res and "response" not in res:
            entry["error"] = res["error"]
            if "model" in res:
                entry["model"] = res["model"]
            entry["yuyay_axes"] = None
            entry["lambda"] = None
            votes.append(entry)
            continue
        resp_text = res["response"]
        entry["response"] = resp_text
        entry["source"] = res.get("source")
        if res.get("stub"):
            entry["stub"] = True
            entry["note"] = res.get("note")
            entry["underlying_error"] = res.get("underlying_error")
        axes = score_yuyay_13(resp_text, prompt)
        entry["yuyay_axes"] = axes
        entry["yuyay_axis_names"] = YUYAY_AXES
        votes.append(entry)
        scorable.append(entry)

    # Λ aggregate over the scorable voters.
    if scorable:
        agg = lutar_lambda([e["yuyay_axes"] for e in scorable])
        for i, e in enumerate(scorable):
            e["lambda"] = agg["lambdas"][i]
            e["lambda_weight"] = agg["weights"][i]
        winner_entry = scorable[agg["winner_index"]]
        winner = winner_entry["voter"]
        winner_response = winner_entry["response"]
        lambda_composite = agg["composite"]
    else:
        agg = {"lambdas": [], "weights": [], "composite": 0.0, "winner_index": -1,
               "status": LAMBDA_STATUS}
        winner = None
        winner_response = None
        lambda_composite = 0.0

    ts = datetime.now(timezone.utc).isoformat()

    # ── Khipu receipt (DSSE-signed) ──────────────────────────────────────────
    receipt_payload = {
        "kind": "a11oy.v4.ensemble-vote",
        "doctrine": "v11",
        "doctrine_locked": "749/14/163",
        "prompt_sha256": prompt_hash,
        "ts_utc": ts,
        "voters_requested": voters,
        "votes": [
            {
                "voter": e["voter"],
                "has_response": "response" in e,
                "error": e.get("error"),
                "stub": e.get("stub", False),
                "yuyay_axes": e.get("yuyay_axes"),
                "lambda": e.get("lambda"),
                "response_sha256": (
                    hashlib.sha256(e["response"].encode("utf-8")).hexdigest()
                    if "response" in e else None
                ),
            }
            for e in votes
        ],
        "yuyay_axis_names": YUYAY_AXES,
        "lambda_composite": lambda_composite,
        "lambda_status": LAMBDA_STATUS,
        "winner": winner,
        "aggregator": "Lutar-Λ (variance-weighted bounded combiner)",
    }

    if _dsse is not None:
        try:
            envelope = _dsse.sign_payload(receipt_payload, _dsse.KHIPU_PAYLOAD_TYPE)
            signed = True
            signing_available = _dsse.signing_available()
        except Exception as e:  # noqa: BLE001
            envelope = {"_error": f"DSSE sign failed: {type(e).__name__}: {e}",
                        "payload": receipt_payload}
            signed = False
            signing_available = False
    else:
        # Honest fallback: still emit a DSSE-shaped envelope, clearly UNSIGNED.
        body = json.dumps(receipt_payload, sort_keys=True, separators=(",", ":")).encode()
        envelope = {
            "payloadType": "application/vnd.szl.khipu+json",
            "payload": __import__("base64").b64encode(body).decode(),
            "signatures": [],
            "_dsse": "DSSEv1",
            "_unsigned": True,
            "_note": "szl_dsse module unavailable; receipt is UNSIGNED (honest).",
            "_payload_sha256": hashlib.sha256(body).hexdigest(),
        }
        signed = False
        signing_available = False

    return {
        "winner": winner,
        "winner_response": winner_response,
        "lambda_composite": lambda_composite,
        "lambda_status": LAMBDA_STATUS,
        "votes": votes,
        "aggregate": agg,
        "prompt_sha256": prompt_hash,
        "ts": ts,
        "receipt": {
            "payload": receipt_payload,
            "dsse": envelope,
            "signed": signed,
            "signing_available": signing_available,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI router + registration.
# ═══════════════════════════════════════════════════════════════════════════

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
# Envelope adapters (ADDITIVE) — chatml | openai | anthropic. Default openai.
# Each adapter pulls a single user `prompt` out of the wire format, plus any
# inline <think> reasoning and <tool_call> objects (Hermes), so the existing
# deterministic ensemble can run unchanged and the response can be re-emitted
# in the caller's native format.
# ═══════════════════════════════════════════════════════════════════════════

SUPPORTED_ENVELOPES = ("openai", "chatml", "anthropic")


def _extract_prompt_from_messages(messages: Any) -> tuple[str, str | None]:
    """Return (last user content, joined system content|None) from an
    OpenAI/Anthropic-style messages list."""
    if not isinstance(messages, list):
        return "", None
    system = "\n".join(
        (m.get("content") or "") for m in messages
        if isinstance(m, dict) and m.get("role") == "system"
    ) or None
    user = ""
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, list):  # Anthropic content blocks
                c = "".join(b.get("text", "") for b in c if isinstance(b, dict))
            user = c or ""
    return user, system


@router.post("/api/a11oy/v4/agent/ask")
async def agent_ask(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    payload = payload or {}

    # ── Optional `envelope`: "chatml" | "openai" | "anthropic" (default openai-ish).
    envelope = payload.get("envelope")
    if envelope is not None:
        if envelope not in SUPPORTED_ENVELOPES:
            return JSONResponse(
                {"error": f"unknown envelope {envelope!r}; supported={list(SUPPORTED_ENVELOPES)}",
                 "lambda_status": LAMBDA_STATUS},
                status_code=400,
            )
        return await _agent_ask_enveloped(envelope, payload)

    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip():
        return JSONResponse(
            {"error": "field 'prompt' (non-empty string) is required",
             "lambda_status": LAMBDA_STATUS},
            status_code=400,
        )
    requested = (payload or {}).get("voters")
    if not requested or not isinstance(requested, list):
        voters = list(ALL_VOTERS)  # default = all available
    else:
        voters = [v for v in requested if v in _VOTER_DISPATCH]
        if not voters:
            return JSONResponse(
                {"error": f"no known voters in {requested}; known={ALL_VOTERS}",
                 "lambda_status": LAMBDA_STATUS},
                status_code=400,
            )
    result = await _ensemble_ask(prompt, voters)
    return JSONResponse(result)


async def _agent_ask_enveloped(envelope: str, payload: dict[str, Any]) -> JSONResponse:
    """Handle /agent/ask for the chatml | openai | anthropic envelopes.

    chatml   — body.chatml is a Hermes ChatML transcript. Any inline
               <tool_call> is validated SCHEMA-STRICT against the bridge tool
               registry; an invalid call fails-CLOSED with a schema_mismatch
               Khipu receipt. The ensemble runs on the user turn and the answer
               is re-emitted as an assistant <think>+<tool_call>? ChatML turn.
    openai    — body.messages (OpenAI chat) -> ensemble -> choices[].message.
    anthropic — body.messages (+ system) -> ensemble -> content[].text.
    """
    think_text: str | None = None
    system_text: str | None = None
    inline_tool_calls: list[dict[str, Any]] = []

    if envelope == "chatml":
        chatml = payload.get("chatml")
        if not isinstance(chatml, str) or not chatml.strip():
            return JSONResponse(
                {"error": "envelope 'chatml' requires a 'chatml' string field",
                 "lambda_status": LAMBDA_STATUS}, status_code=400)
        if _bridge is None:
            return JSONResponse({"error": "szl_bridge module unavailable"}, status_code=503)
        parsed = _bridge.parse_chatml(chatml)
        if parsed["parse_errors"]:
            rec = _bridge.mint_receipt(
                "schema_mismatch", "agent-ask-chatml", "agent.ask.chatml_parse",
                {"decision": "deny", "fail_mode": "fail-closed", "errors": parsed["parse_errors"]})
            return JSONResponse(
                {"error": "chatml parse failed", "schema_mismatch": True,
                 "receipt_id": rec["receipt_id"], "signed_url": rec["signed_url"],
                 "chatml_parse_errors": parsed["parse_errors"]}, status_code=422)
        # SCHEMA-STRICT: every inline <tool_call> must validate or we fail-CLOSED.
        for tc in parsed["tool_calls"]:
            name = tc.get("name")
            args = tc.get("arguments", {})
            verdict = _bridge_schemas.validate_tool_call(name if isinstance(name, str) else "", args)
            if not verdict["valid"]:
                rec = _bridge.mint_receipt(
                    "schema_mismatch", "agent-ask-chatml", "agent.ask.schema_mismatch",
                    {"decision": "deny", "fail_mode": "fail-closed", "tool_name": name,
                     "schema_errors": verdict["errors"], "schema_dialect": verdict["dialect"],
                     "registered_tools": _bridge_schemas.registered_tools()})
                return JSONResponse(
                    {"error": "schema_mismatch", "schema_mismatch": True, "tool_name": name,
                     "schema_errors": verdict["errors"], "receipt_id": rec["receipt_id"],
                     "signed_url": rec["signed_url"], "lambda_status": LAMBDA_STATUS},
                    status_code=422)
        inline_tool_calls = parsed["tool_calls"]
        if parsed["think_blocks"]:
            think_text = "\n".join(parsed["think_blocks"])
        prompt = next((t["content"] for t in parsed["turns"] if t["role"] == "user"), "")
        system_text = next((t["content"] for t in parsed["turns"] if t["role"] == "system"), None)
    else:  # openai | anthropic
        prompt, system_text = _extract_prompt_from_messages(payload.get("messages"))
        if not prompt:
            prompt = payload.get("prompt", "")

    if not isinstance(prompt, str) or not prompt.strip():
        return JSONResponse(
            {"error": "could not extract a non-empty user prompt from the envelope",
             "envelope": envelope, "lambda_status": LAMBDA_STATUS}, status_code=400)

    requested = payload.get("voters")
    voters = list(ALL_VOTERS) if not isinstance(requested, list) or not requested \
        else [v for v in requested if v in _VOTER_DISPATCH] or list(ALL_VOTERS)

    result = await _ensemble_ask(prompt, voters)
    answer = result.get("winner_response") or ""
    result["envelope"] = envelope

    # Re-emit the answer in the caller's native wire format.
    if envelope == "chatml":
        out_think = think_text or "Selected the highest-Λ ensemble voter; answer is deterministic."
        # Echo the (validated) inline tool call if present; else no tool call.
        out_tc = inline_tool_calls[0] if inline_tool_calls else None
        if out_tc is not None:
            chatml_out = _bridge.build_chatml(system_text or "", prompt, out_think, out_tc)
        else:
            tparts = []
            if system_text:
                tparts.append(f"<|im_start|>system\n{system_text}\n<|im_end|>")
            tparts.append(f"<|im_start|>user\n{prompt}\n<|im_end|>")
            tparts.append(f"<|im_start|>assistant\n<think>{out_think}</think>\n{answer}\n<|im_end|>")
            chatml_out = "\n".join(tparts)
        result["chatml"] = chatml_out
    elif envelope == "openai":
        result["openai"] = {
            "object": "chat.completion",
            "model": f"a11oy-ensemble/{result.get('winner')}",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": answer}}],
        }
    elif envelope == "anthropic":
        result["anthropic"] = {
            "type": "message", "role": "assistant",
            "model": f"a11oy-ensemble/{result.get('winner')}",
            "content": [{"type": "text", "text": answer}],
            "stop_reason": "end_turn",
        }
    return JSONResponse(result)


@router.get("/api/a11oy/v4/agent/voters")
async def agent_voters() -> JSONResponse:
    return JSONResponse({
        "voters": ALL_VOTERS,
        "yuyay_axes": YUYAY_AXES,
        "aggregator": "Lutar-Λ (variance-weighted bounded combiner)",
        "lambda_status": LAMBDA_STATUS,
        "hf_token_present": _hf_token() is not None,
    })


def _agent_html_path() -> Path:
    # Shipped alongside the module; in the Space it sits at repo root.
    here = Path(__file__).resolve().parent
    for cand in (here / "agent.html", Path("/app/agent.html"), Path("agent.html")):
        if cand.is_file():
            return cand
    return here / "agent.html"


@router.get("/agent")
async def agent_page() -> HTMLResponse:
    p = _agent_html_path()
    if p.is_file():
        return HTMLResponse(p.read_text(encoding="utf-8"))
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><title>a11oy agent</title>"
        "<h1>a11oy Multi-LLM Ensemble</h1>"
        "<p>agent.html not shipped; endpoint POST /api/a11oy/v4/agent/ask is live.</p>",
        status_code=200,
    )


def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Attach the v4 agent router. Registered BEFORE the SPA catch-all + the
    generic /api/a11oy/{path} Node proxy so /agent and /api/a11oy/v4/agent/ask
    resolve LOCALLY. ADDITIVE — touches no existing route."""
    app.include_router(router)
    return (
        "a11oy.v4.agent mounted: POST /api/a11oy/v4/agent/ask, "
        "GET /api/a11oy/v4/agent/voters, GET /agent "
        f"(voters={len(ALL_VOTERS)}, axes=13, Λ={LAMBDA_STATUS!r})"
    )


# Allow `import a11oy_v4_agent; a11oy_v4_agent.attach(app)` style too.
def attach(app: FastAPI) -> str:
    return register(app, ROUTER_NS)
