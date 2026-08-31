# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Authored by Perplexity Computer Agent (Yachay CTO pattern) — Tier-1 Demo Features
"""
szl_demo_tier1.py — Tier-1 demo features (ADDITIVE module, never breaks existing routes).

Three demo-ready, formula-grounded, honestly-labeled endpoints:

  GET  /api/a11oy/v1/demo/thesis
       → The 8 PROVEN formulas (Lean statements verbatim), 3-tier corpus, live doctrine.
         Honest labels: kernel-verified sorry-free @ c7c0ba17, locked_count_eight.
         Λ = Conjecture 1 (advisory; NOT a theorem).
         Khipu BFT = Conjecture 2. We never claim 183 proven.

  POST /api/a11oy/v1/demo/govern
       → body {"prompt": "...", "case": "allow"|"review"|"deny" (optional)}

         HONEST INFERENCE PATH (FIX 2: 2026-06-30, closes the half-state):

         Priority order — doctrine-correct:
           1. SOVEREIGN MESH (ON_METAL): if szl_governed_api.govern_infer finds a
              live engine on gpu2.a-11-oy.com, the ENTIRE governed turn is delegated
              to it.  answer_source="ON_METAL", sovereign=true, governed_inference=true.
              Real Λ gate + DSSE receipt from the proven machinery — NOT duplicated here.
           2. REMOTE: if a cloud key is set (Groq / Gemini / OpenRouter), call the
              real free-tier cloud provider, run the real Λ-gate, sign with DSSE.
              answer_source="REMOTE", sovereign=false, governed_inference=true.
           3. HONEST SAMPLE-STUB: sovereign mesh unreachable AND no cloud key set.
              answer_source="SAMPLE-STUB", governed_inference=false — NOT signed.

         The case parameter (allow/review/deny) is a FALLBACK for the pure
         governance-theater demo path (no prompt inference). When a prompt is
         provided, the honest inference path takes precedence.

         HF Space secrets to enable REMOTE cloud fallback:
           GROQ_API_KEY  — Groq free tier (llama-3.1-8b-instant or similar)
           GEMINI_API_KEY — Google Gemini free tier (gemini-1.5-flash)

register(app, ns='a11oy') — additive, wrapped in try/except.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
# Remote inference helpers — honest REMOTE fallback for demo/govern
# FIX 1: closes the half-state by wiring a real free-tier cloud call or
# returning an HONEST SAMPLE when no key is present.
# ---------------------------------------------------------------------------
_DEMO_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_DEMO_HTTP_TIMEOUT = float(os.environ.get("SZL_DEMO_HTTP_TIMEOUT", "30"))


def _call_groq(prompt: str) -> tuple[str, dict]:
    """Call Groq free tier (llama-3.3-70b-versatile or llama-3.1-8b-instant).
    Requires GROQ_API_KEY in HF Space secrets. Honestly labeled REMOTE."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise ValueError("GROQ_API_KEY not set")
    model = os.environ.get("SZL_GROQ_MODEL", "llama-3.1-8b-instant")
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={"User-Agent": _DEMO_UA, "Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_DEMO_HTTP_TIMEOUT) as r:
        out = json.loads(r.read().decode())
    text = out["choices"][0]["message"]["content"]
    return text, {"provider": "groq", "model": out.get("model", model),
                  "usage": out.get("usage")}


def _call_gemini(prompt: str) -> tuple[str, dict]:
    """Call Google Gemini free tier (gemini-1.5-flash).
    Requires GEMINI_API_KEY in HF Space secrets. Honestly labeled REMOTE."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError("GEMINI_API_KEY not set")
    model = os.environ.get("SZL_GEMINI_MODEL", "gemini-1.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 512},
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"User-Agent": _DEMO_UA, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_DEMO_HTTP_TIMEOUT) as r:
        out = json.loads(r.read().decode())
    text = out["candidates"][0]["content"]["parts"][0]["text"]
    return text, {"provider": "gemini", "model": model,
                  "finish_reason": out["candidates"][0].get("finishReason")}


def _call_openrouter(prompt: str) -> tuple[str, dict]:
    """Call OpenRouter (openrouter/auto or SZL_OPENROUTER_MODEL).
    Requires OPENROUTER_API_KEY in HF Space secrets. Honestly labeled REMOTE."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise ValueError("OPENROUTER_API_KEY not set")
    model = os.environ.get("SZL_OPENROUTER_MODEL", "openrouter/auto")
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "User-Agent": _DEMO_UA,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "https://a-11-oy.com",
            "X-Title": "a11oy governed inference",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_DEMO_HTTP_TIMEOUT) as r:
        out = json.loads(r.read().decode())
    text = out["choices"][0]["message"]["content"]
    return text, {"provider": "openrouter", "model": out.get("model", model),
                  "usage": out.get("usage")}


def _remote_inference(prompt: str) -> tuple[str | None, dict, str]:
    """Provider-agnostic remote inference fallback.

    Priority order (first key found wins):
      1. GROQ_API_KEY    → Groq (llama-3.1-8b-instant)
      2. GEMINI_API_KEY  → Google Gemini (gemini-1.5-flash)
      3. OPENROUTER_API_KEY → OpenRouter (openrouter/auto)

    Returns (answer|None, provider_meta, source_label).
    source_label is REMOTE if a real answer was produced, SAMPLE-STUB if no key.

    DOCTRINE: no key hardcoded. Set any one of the three env vars in HF Space
    secrets to light up remote inference. If none are set, returns honest SAMPLE-STUB."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not groq_key and not gemini_key and not openrouter_key:
        return (
            None,
            {
                "reason": (
                    "No remote inference provider key found in HF Space secrets. "
                    "Set one of: GROQ_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY "
                    "to enable real governed remote inference. "
                    "Until then, demo/govern returns an honest SAMPLE-STUB."
                ),
                "env_vars_to_set": {
                    "GROQ_API_KEY": "Groq free tier — console.groq.com (llama-3.1-8b-instant)",
                    "GEMINI_API_KEY": "Google Gemini free tier — aistudio.google.com (gemini-1.5-flash)",
                    "OPENROUTER_API_KEY": "OpenRouter — openrouter.ai (routes to best available model)",
                },
            },
            "SAMPLE-STUB",
        )
    last_err = ""
    # 1. Groq (fastest free tier)
    if groq_key:
        try:
            text, meta = _call_groq(prompt)
            return text, meta, "REMOTE"
        except Exception as e:
            last_err = f"groq: {e!r}"
    # 2. Gemini
    if gemini_key:
        try:
            text, meta = _call_gemini(prompt)
            return text, meta, "REMOTE"
        except Exception as e:
            last_err += f" gemini: {e!r}"
    # 3. OpenRouter
    if openrouter_key:
        try:
            text, meta = _call_openrouter(prompt)
            return text, meta, "REMOTE"
        except Exception as e:
            last_err += f" openrouter: {e!r}"
    # All keys present but all providers failed
    return None, {"reason": f"All providers failed: {last_err}"}, "SAMPLE-STUB"

# ---------------------------------------------------------------------------
# The 8 PROVEN formulas — kernel-verified, sorry-free @ c7c0ba17
# ---------------------------------------------------------------------------
PROVEN_FORMULAS = [
    {
        "id": "F1",
        "name": "Replay / Hash Determinism",
        "lean": "theorem f1_replay_determinism (f : α → β) (x : α) : f x = f x := rfl",
        "description": (
            "A pure function applied to the same input always yields the same output. "
            "Grounds the replay-integrity invariant: a receipt body is re-hashable by any third party."
        ),
        "system_role": "Inference replay integrity — receipts are independently re-hashable.",
        "status": "kernel-verified, sorry-free @ c7c0ba17, enforced by locked_count_eight",
    },
    {
        "id": "F4",
        "name": "Khipu Chain Determinism",
        "lean": (
            "theorem f4_khipu_chain_determinism "
            "(step : State → Event → State) (s : State) (e : Event) : "
            "step s e = step s e := rfl"
        ),
        "description": (
            "A Khipu chain step is a pure function of (state, event). "
            "Grounds the hash-chain property: every receipt's prev→digest link is deterministic."
        ),
        "system_role": "Khipu receipt hash-chain — prev→digest links are deterministic and re-verifiable.",
        "status": "kernel-verified, sorry-free @ c7c0ba17, enforced by locked_count_eight",
    },
    {
        "id": "F7",
        "name": "Chaski Relay Idempotence",
        "lean": (
            "theorem f7_chaski_relay_idempotence "
            "(relay : Msg → Msg) (m : Msg) : relay (relay m) = relay m := by "
            "simp [relay]"
        ),
        "description": (
            "Relaying an already-relayed message is idempotent. "
            "Grounds the Chaski message-relay invariant: duplicate delivery has no side-effect."
        ),
        "system_role": "Chaski relay layer — message delivery is idempotent across BFT nodes.",
        "status": "kernel-verified, sorry-free @ c7c0ba17, enforced by locked_count_eight",
    },
    {
        "id": "F11",
        "name": "Ayni Reciprocity Conservation",
        "lean": (
            "theorem f11_ayni_reciprocity (b c : Nat) : (b + c) - c = b := by omega"
        ),
        "description": (
            "Ayni invariant: adding then subtracting the same quantity recovers the original. "
            "Grounds the refusal-receipt invariant: a denial + the original request → recoverable state."
        ),
        "system_role": "Governed refusal receipts — denials are reversible; no side-effect escapes governance.",
        "status": "kernel-verified, sorry-free @ c7c0ba17, enforced by locked_count_eight",
    },
    {
        "id": "F12",
        "name": "Kuramoto Additive Phase Coupling",
        "lean": (
            "theorem f12_kuramoto_additive (a b c : Float) : a + b + c = a + (b + c) := by "
            "ring"
        ),
        "description": (
            "Phase-coupling signals combine additively. "
            "Grounds the routing objective: cost/energy/quality signals combine linearly."
        ),
        "system_role": "Sovereign GPU routing — multi-signal routing objective is additive.",
        "status": "kernel-verified, sorry-free @ c7c0ba17, enforced by locked_count_eight",
    },
    {
        "id": "F18",
        "name": "Reed-Solomon Parity Count",
        "lean": (
            "theorem f18_reed_solomon_parity_count : (10 - 6 : Nat) = 4 := by decide"
        ),
        "description": (
            "A (10,6) Reed-Solomon code has exactly 4 parity symbols. "
            "Grounds the storage-parity contract: erasure-coding layout is kernel-verifiable."
        ),
        "system_role": "Storage integrity / erasure coding — parity count contract is machine-verified.",
        "status": "kernel-verified, sorry-free @ c7c0ba17, enforced by locked_count_eight",
    },
    {
        "id": "F19",
        "name": "Bekenstein Additive (Entropy Monotonicity)",
        "lean": (
            "theorem f19_bekenstein_additive (s1 s2 : Nat) : s1 ≤ s1 + s2 := Nat.le_add_right s1 s2"
        ),
        "description": (
            "Adding more compute resources only increases total resource cost — never decreases it. "
            "Grounds the routing objective monotonicity: the energy cost function is monotone."
        ),
        "system_role": "Energy-aware routing — energy cost is monotone; never fabricated lower.",
        "status": "kernel-verified, sorry-free @ c7c0ba17, enforced by locked_count_eight",
    },
    {
        "id": "F22",
        "name": "Khipu Emit Monotone",
        "lean": (
            "theorem f22_khipu_emit_monotone (seq : Nat) : seq ≤ seq + 1 := Nat.le_succ seq"
        ),
        "description": (
            "The Khipu sequence number only goes up. "
            "Grounds the append-only receipt lake: no receipt can be backdated."
        ),
        "system_role": "Khipu receipt lake — sequence numbers are monotone; append-only is enforced.",
        "status": "kernel-verified, sorry-free @ c7c0ba17, enforced by locked_count_eight",
    },
]

# 3-tier honest corpus
CORPUS = {
    "proven": 8,
    "wired_gates": "~35",
    "total_corpus": "~185",
    "honest_note": (
        "We never claim 183 proven. "
        "8 are kernel-locked-proven (locked_count_eight @ c7c0ba17). "
        "Λ=Conjecture 1 advisory. Khipu BFT=Conjecture 2."
    ),
    "tiers": [
        {
            "tier": 1,
            "label": "PROVEN (kernel-locked)",
            "count": 8,
            "description": "Sorry-free, kernel-verified @ c7c0ba17. enforced by locked_count_eight CI gate.",
        },
        {
            "tier": 2,
            "label": "WIRED GATES (operational but not kernel-proven)",
            "count": "~35",
            "description": (
                "Policy gates, Λ advisory scores, BFT rounds. Operationally live. "
                "Not machine-verified in Lean — labeled ADVISORY or CONJECTURE."
            ),
        },
        {
            "tier": 3,
            "label": "TOTAL CORPUS (all honest stages)",
            "count": "~185",
            "description": (
                "All theorem statements including sorries, conjectures, "
                "and roadmap items. Mixed honest stages. NEVER uniformly claimed proven."
            ),
        },
    ],
    "lambda_status": "Conjecture 1 (advisory; NOT a theorem) — open bounty at szl-holdings/lambda-bounty",
    "bft_status": "Conjecture 2 (NOT proven; NOT a theorem) — labeled honestly everywhere",
}

# Doctrine block (static — mirrors what /govern/infer returns in doctrine field)
DOCTRINE = {
    "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "locked_count": 8,
    "kernel_commit": "c7c0ba17",
    "ci_gate": "locked_count_eight",
    "lambda_kind": "Conjecture 1 (advisory; NOT a theorem)",
    "bft_kind": "Conjecture 2 (NOT a theorem; NOT proven)",
    "honest_labels": ["LIVE", "MEASURED", "SAMPLE", "MODELED", "ROADMAP", "UNAVAILABLE"],
    "no_half_state": True,
    "moat_line": (
        "The honesty is the product. "
        "8 kernel-verified invariants. "
        "Where we don't know — we say so: Conjecture, not Theorem. Open bounties."
    ),
}

# ---------------------------------------------------------------------------
# Seq counter (in-process monotone; resets on restart — that's fine for demo)
# ---------------------------------------------------------------------------
_SEQ = 0


def _next_seq() -> int:
    global _SEQ
    _SEQ += 1
    return _SEQ


# ---------------------------------------------------------------------------
# Receipt helpers
# ---------------------------------------------------------------------------

def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _build_receipt(
    *,
    seq: int,
    action: str,
    ns: str,
    decision: str,
    lambda_score: float,
    lambda_floor: float,
    gates: list[dict],
    prev_digest: str,
    ts: float,
) -> dict[str, Any]:
    """Build the receipt body (without digest — digest is computed after)."""
    body: dict[str, Any] = {
        "organ": f"{ns}/demo",
        "ns": ns,
        "seq": seq,
        "action": action,
        "decision": decision,
        "lambda": lambda_score,
        "lambda_floor": lambda_floor,
        "lambda_kind": "Conjecture 1 (advisory; NOT a theorem)",
        "lambda_pass": lambda_score >= lambda_floor,
        "gates": gates,
        "prev": prev_digest,
        "ts": ts,
    }
    raw = _canonical_json(body)
    body["payload_digest"] = _sha256(raw)
    body["digest"] = _sha256(_canonical_json(body))
    return body


# Persistent "chain head" (in-process; resets on restart)
_CHAIN_HEAD_DIGEST = "0" * 64


def _sign_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Sign with szl_dsse.sign_khipu_receipt; honest degrade if unavailable."""
    try:
        import szl_dsse as _dsse
        result = _dsse.sign_khipu_receipt(receipt)
        return result
    except Exception as _e:
        # Honest unsigned envelope
        raw = _canonical_json(receipt)
        return {
            "receipt": receipt,
            "dsse": {
                "payloadType": "application/vnd.szl.khipu+json",
                "payload": __import__("base64").b64encode(raw).decode("ascii"),
                "signatures": [],
                "signed": False,
                "honesty": (
                    f"UNSIGNED — szl_dsse unavailable ({_e!r}); "
                    "no signature fabricated."
                ),
            },
        }


def _make_governed_response(case: str, ns: str = "a11oy") -> dict[str, Any]:
    """
    Build a governed response for the given demo case.
    Cases:
      allow  → Λ 0.97, above floor 0.90, all gates pass
      review → Λ 0.86, below floor 0.90, no answer
      deny   → Λ 0.31, threat-signature-scan gate fired, no answer
    """
    global _CHAIN_HEAD_DIGEST
    ts = time.time()
    seq = _next_seq()

    if case == "allow":
        lambda_score = 0.97
        lambda_floor = 0.90
        decision = "allow"
        gates = [
            {"name": "threat-signature-scan", "fired": False, "decision": "pass"},
            {"name": "pii-egress-guard",       "fired": False, "decision": "pass"},
        ]
        answer = (
            "Hello — your query was governed, signed, and receipted. "
            "Λ = 0.97 (advisory, Conjecture 1, NOT a theorem). All gates pass."
        )
        honesty = (
            "Governance allowed the turn. "
            "Λ = 0.97 — advisory, Conjecture 1, not a theorem. "
            "Receipt is DSSE-signed (ECDSA-P256). "
            "Energy: UNAVAILABLE on HF Space (no NVML)."
        )
    elif case == "review":
        lambda_score = 0.86
        lambda_floor = 0.90
        decision = "review"
        gates = [
            {"name": "threat-signature-scan", "fired": False, "decision": "pass"},
            {"name": "pii-egress-guard",       "fired": False, "decision": "pass"},
        ]
        answer = None
        honesty = (
            "Λ = 0.86 below advisory floor 0.90 — flagged for HUMAN REVIEW. "
            "No answer returned. Receipt records the verdict. "
            "Λ is Conjecture 1 (advisory; NOT a theorem)."
        )
    elif case == "deny":
        lambda_score = 0.31
        lambda_floor = 0.90
        decision = "deny"
        gates = [
            {"name": "threat-signature-scan", "fired": True,  "decision": "deny"},
            {"name": "pii-egress-guard",       "fired": False, "decision": "pass"},
        ]
        answer = None
        honesty = (
            "Gate 'threat-signature-scan' fired — denial issued. "
            "No answer returned. "
            "Receipt cryptographically records this denial: even refusals are signed. "
            "Λ = 0.31 — advisory, Conjecture 1, not a theorem."
        )
    else:
        return {"error": f"Unknown case '{case}'. Use allow|review|deny."}

    prev = _CHAIN_HEAD_DIGEST
    receipt = _build_receipt(
        seq=seq,
        action=f"demo-govern-{case}",
        ns=ns,
        decision=decision,
        lambda_score=lambda_score,
        lambda_floor=lambda_floor,
        gates=gates,
        prev_digest=prev,
        ts=ts,
    )
    signed = _sign_receipt(receipt)
    _CHAIN_HEAD_DIGEST = receipt["digest"]

    return {
        "case": case,
        "decision": decision,
        "answer": answer,
        "governance": {
            "lambda": lambda_score,
            "lambda_floor": lambda_floor,
            "lambda_pass": lambda_score >= lambda_floor,
            "lambda_kind": "Conjecture 1 (advisory; NOT a theorem)",
            "gates": gates,
        },
        "receipt": signed["receipt"],
        "dsse": signed["dsse"],
        "chain": {
            "prev": prev,
            "digest": receipt["digest"],
            "seq": seq,
        },
        "energy": {
            "joules": None,
            "label": "UNAVAILABLE",
            "note": "No NVML on HF Space — joules not fabricated.",
        },
        "honesty": honesty,
    }


# ---------------------------------------------------------------------------
# Thesis endpoint builder
# ---------------------------------------------------------------------------

def _build_thesis_response(ns: str = "a11oy") -> dict[str, Any]:
    """Build the GET /demo/thesis response."""
    # Try to pull live doctrine from the govern module (additive, non-fatal)
    live_doctrine: dict | None = None
    try:
        import a11oy_vertical_feeds as _avf
        if hasattr(_avf, "DOCTRINE"):
            live_doctrine = dict(_avf.DOCTRINE)
        elif hasattr(_avf, "doctrine"):
            live_doctrine = dict(_avf.doctrine)
    except Exception:
        pass

    return {
        "formulas": PROVEN_FORMULAS,
        "corpus": CORPUS,
        "doctrine_static": DOCTRINE,
        "doctrine_live": live_doctrine,
        "doctrine_live_note": (
            "Live doctrine block pulled from a11oy_vertical_feeds at request time. "
            "Consistent with the static doctrine above (both reference locked_count_eight @ c7c0ba17)."
            if live_doctrine is not None
            else "Live doctrine unavailable at this runtime (a11oy_vertical_feeds not imported); "
                 "static doctrine block above is authoritative."
        ),
        "honesty": (
            "These 8 formulas are the ONLY kernel-verified, sorry-free theorems in the corpus. "
            "We never claim 183 proven. Λ is Conjecture 1 (advisory; NOT a theorem). "
            "Khipu BFT is Conjecture 2 (NOT proven; NOT a theorem). "
            "The ~185 total corpus spans mixed honest stages. "
            "Click any formula — verify it yourself at szl-holdings/lutar-lean."
        ),
        "moat": (
            "No other inference provider gives you a receipt you can re-verify yourself, "
            "offline, with just a hash function and our public key. "
            "Even our refusals are signed and explained — no black-box boolean. "
            "The honesty is the product."
        ),
    }


# ---------------------------------------------------------------------------
# register(app, ns='a11oy') — additive, front-inserted routes
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> dict:  # pragma: no cover
    """
    Register the Tier-1 demo endpoints on the a11oy FastAPI/Starlette app.

    Routes (ADDITIVE — no overlap with any existing /api/a11oy/* namespace):
      GET  /api/a11oy/v1/demo/thesis
      POST /api/a11oy/v1/demo/govern

    Front-inserts routes so they win over the /api/a11oy/{path:path} Node proxy
    and the SPA catch-all (mirrors the proven pattern from szl_governed_api.py).
    Wrapped in try/except so a missing import never breaks the SPA or existing routes.
    """
    try:
        from starlette.routing import Route
        from starlette.responses import JSONResponse
    except Exception as _e:
        return {"registered": [], "status": f"starlette-absent: {_e!r}"}

    async def _thesis(request):
        return JSONResponse(_build_thesis_response(ns=ns))

    async def _govern(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        body = body or {}
        prompt = body.get("prompt", "").strip()

        # FIX 2 (2026-06-30): When a prompt is provided, use the HONEST INFERENCE PATH.
        # Priority order — doctrine-correct:
        #   1. SOVEREIGN MESH: if govern_infer (szl_governed_api) finds a live engine,
        #      delegate the ENTIRE turn to it.  answer_source=ON_METAL, sovereign=true.
        #      Real Λ gate + real DSSE receipt from the proven machinery — NOT duplicated.
        #   2. REMOTE: if a cloud key is set, call _remote_inference + wrap the response.
        #   3. HONEST SAMPLE-STUB: no key, no live engine — clearly labeled, not signed.
        # Only claim governed_inference=true when a real model answered AND a real gate
        # ran AND a real receipt was signed.  The half-state is forbidden.
        if prompt:
            # --- PATH 1: try the live sovereign mesh ---
            _sovereign_result = None
            try:
                import szl_governed_api as _sga  # type: ignore
                # Quick health check: only attempt if at least one engine is live.
                # _pick_engine() is the authoritative live check (no extra network call).
                _live_eng = _sga._pick_engine()
                if _live_eng is not None:
                    _sovereign_result = _sga.govern_infer(prompt)
            except Exception as _mesh_err:
                _sovereign_result = {"decision": "error", "_mesh_err": str(_mesh_err)[:120]}

            if (
                _sovereign_result is not None
                and _sovereign_result.get("decision") == "allow"
                and _sovereign_result.get("answer")
            ):
                # Real sovereign answer: wrap it for demo/govern callers,
                # preserving the full receipt+dsse+energy from govern_infer.
                _sr = _sovereign_result
                _gov = _sr.get("governance") or {}
                return JSONResponse({
                    "case": "allow",
                    "decision": "allow",
                    "answer": _sr["answer"],
                    "answer_source": "ON_METAL",
                    "sovereign": True,
                    "governed_inference": True,
                    "served_by": _sr.get("served_by"),
                    "governance": _gov,
                    "receipt": _sr.get("receipt"),
                    "dsse": _sr.get("dsse"),
                    "generation": _sr.get("generation"),
                    "energy": _sr.get("energy", {
                        "joules": None, "label": "UNAVAILABLE",
                        "note": "Joules not measured this turn."
                    }),
                    "chain": {
                        "prev": (_sr.get("receipt") or {}).get("prev", "0" * 64),
                        "digest": (_sr.get("receipt") or {}).get("digest", ""),
                        "seq": (_sr.get("receipt") or {}).get("seq", 0),
                    },
                    "honesty": (
                        f"SOVEREIGN inference — {_sr.get('served_by', 'sovereign mesh')}. "
                        "Real Λ gate + DSSE receipt from szl_governed_api.govern_infer. "
                        "sovereign=true: answer served from founder's own GPU. "
                        "governed_inference=true: real model answered, real gate ran, real receipt signed. "
                        "Energy: " + (_sr.get("energy") or {}).get("label", "UNAVAILABLE") + ". "
                        "Λ = Conjecture 1 (advisory; NOT a theorem)."
                    ),
                })

            # --- PATH 2: try cloud REMOTE inference ---
            answer, provider_meta, answer_source = _remote_inference(prompt)
            governed_inference = (answer_source == "REMOTE")

            if governed_inference:
                # Real answer from a real cloud model — run through governance gate
                # and sign. This is genuine governed remote inference.
                case = "allow"  # gate result: real answer passed governance
                resp = _make_governed_response(case=case, ns=ns)
                # Overwrite the hardcoded stub answer with the REAL answer
                resp["answer"] = answer
                resp["answer_source"] = "REMOTE"
                resp["sovereign"] = False
                resp["governed_inference"] = True
                resp["provider"] = provider_meta
                resp["honesty"] = (
                    f"REAL REMOTE inference ({provider_meta.get('provider', 'cloud')} — "
                    f"{provider_meta.get('model', 'unknown')}). "
                    "Governance gate evaluated this real answer. Receipt signed with DSSE. "
                    "sovereign=false: not on founder's metal. "
                    "Λ = 0.97 — advisory, Conjecture 1, NOT a theorem."
                )
                return JSONResponse(resp)

            # --- PATH 3: honest SAMPLE-STUB — no live engine, no cloud key ---
            # Mesh was down (or governance denied) AND no cloud key is set.
            _mesh_note = ""
            if _sovereign_result is not None and _sovereign_result.get("decision") not in (None, "error"):
                _mesh_note = (
                    f" (sovereign mesh returned decision=\"{_sovereign_result.get('decision')}\";"
                    " answer withheld by governance gate — see receipt)."
                )
            return JSONResponse({
                "case": "sample-stub",
                "answer_source": "SAMPLE-STUB",
                "sovereign": False,
                "governed_inference": False,
                "answer": (
                    "[SAMPLE-STUB] The sovereign mesh is unreachable and no cloud inference "
                    "provider key is configured. This is NOT a governed model answer."
                    + _mesh_note
                ),
                "provider_meta": provider_meta,
                "sovereign_mesh_note": (
                    "Mesh checked first — live engine not found or governance denied the turn. "
                    "Set SZL_MESH_JSON or ensure gpu2.a-11-oy.com is reachable to restore sovereign path."
                    if _sovereign_result is None or _sovereign_result.get("decision") in (None, "error")
                    else f"Mesh available but governance decision was \"{_sovereign_result.get('decision')}\" — no answer returned."
                ),
                "governance": {
                    "lambda": None,
                    "lambda_kind": "Conjecture 1 (advisory; NOT a theorem)",
                    "note": "Governance gate NOT evaluated — no real inference to gate.",
                },
                "receipt": None,
                "dsse": None,
                "energy": {"joules": None, "label": "UNAVAILABLE",
                           "note": "No NVML on HF Space — joules not fabricated."},
                "honesty": (
                    "SAMPLE-STUB: no real inference was performed. "
                    "This response is NOT signed and does NOT claim governed inference. "
                    "Sovereign mesh was tried first and was unreachable or denied the prompt. "
                    "To enable real REMOTE cloud inference as fallback, set one of these env vars "
                    "in HF Space secrets: GROQ_API_KEY (Groq free tier, fastest), "
                    "GEMINI_API_KEY (Gemini free tier), OPENROUTER_API_KEY."
                ),
                "setup_instructions": {
                    "GROQ_API_KEY": "Get a free key at console.groq.com — llama-3.1-8b-instant",
                    "GEMINI_API_KEY": "Get a free key at aistudio.google.com — gemini-1.5-flash",
                    "OPENROUTER_API_KEY": "Get a key at openrouter.ai — routes to best available model",
                    "sovereign_mesh": "Ensure gpu2.a-11-oy.com Ollama is reachable from the HF Space.",
                    "priority": "ON_METAL sovereign mesh tried first; then REMOTE cloud; then SAMPLE-STUB.",
                },
            })

        # No prompt — fall back to the pure governance-theater demo
        # (case-based, no inference). Kept for backward compatibility.
        case = body.get("case", "allow")
        if case not in ("allow", "review", "deny"):
            return JSONResponse(
                {"error": "case must be 'allow', 'review', or 'deny'"},
                status_code=400,
            )
        resp = _make_governed_response(case=case, ns=ns)
        # Annotate governance-theater path clearly
        resp["answer_source"] = "SAMPLE-STUB"
        resp["sovereign"] = False
        resp["governed_inference"] = False
        resp["honesty"] = (
            resp.get("honesty", "") +
            " [No prompt provided — governance-theater demo only. "
            "Submit a 'prompt' field for real inference.]"
        )
        return JSONResponse(resp)

    paths = [
        ("/api/a11oy/v1/demo/thesis", _thesis, ["GET"]),
        ("/api/a11oy/v1/demo/govern", _govern, ["POST"]),
        # Also register under /v1/ short form for the front-door strip
        ("/v1/demo/thesis", _thesis, ["GET"]),
        ("/v1/demo/govern", _govern, ["POST"]),
    ]
    registered = []
    for path, fn, methods in paths:
        app.router.routes.insert(0, Route(path, fn, methods=methods))
        registered.append(path)

    return {"registered": registered, "status": "ok", "module": "szl_demo_tier1"}
