#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""szl_sovereign_panel.py — Sovereign Local Model panel (Wave M, Dev 4).

GET /api/a11oy/v1/frontier/sovereign returns a public read-only status for the
configured sovereign model endpoint. The declared design uses a local Ollama
model, but this GET cannot verify who operates the responding endpoint or what
hardware, weights, or prompt wrapper it uses.

The public panel surfaces three honest read-only signals:

  1. reachability — did the configured metadata endpoint answer THIS request?
     This does not identify the host, GPU, weights, or doctrine wrapper. We use the
     guarded helper (`szl_llm_registry.sovereign_probe`, which also backs
     GET /api/a11oy/v1/llm/sovereign/health). If unavailable, we fail closed
     instead of making a direct URL request.

  2. doctrine self-test — UNAVAILABLE on this GET. Inference is a governed write,
     never an implicit side effect of a public status read. Historical answers and
     receipts, if any, must be obtained through their separately governed paths.

  3. Stage A-vs-B — declared system-prompt derivative versus roadmap LoRA.
     Served tags provide only a hint, not evidence of a prompt wrapper or weights.

The GET does not mint or reclassify any receipt. It also withholds the private
backend URL, probe diagnostics, and served-model inventory from its public JSON.

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17;
    touches no locked formula and no kernel.
  - Λ stays Conjecture 1 (advisory, never "green"/theorem). Trust ceiling 0.97.
  - Public sovereign provenance is UNKNOWN when a metadata endpoint answers and
    UNAVAILABLE when it does not. A 2xx model list cannot prove owned hardware,
    weights, or a doctrine wrapper.
  - Additive route, registered BEFORE the SPA catch-all; 0 runtime CDN.
"""
from __future__ import annotations

import datetime
from typing import Any

# Honesty-label vocabulary (doctrine v11).
UNKNOWN = "UNKNOWN"
UNAVAILABLE = "UNAVAILABLE"
MODELED = "MODELED"

# Trust ceiling — advisory, never 100% (doctrine v11).
TRUST_CEILING = 0.97

# The registry slug for the sovereign backend (Dev-1's `szl-sovereign-local`). The
# ollama model TAG the founder is standing up is `llama3-szl-finetuned-q4`
# (Stage B replaces Stage A under the SAME tag); the base is llama3.1:8b.
SOVEREIGN_BACKEND_ID = "szl-sovereign-local"
SOVEREIGN_MODEL_TAG = "llama3-szl-finetuned-q4"
DOCTRINE_SELFTEST_PROMPT = "State your doctrine in one line"

# Related routed health endpoint; the panel uses the same guarded registry helper.
DEV1_HEALTH_ROUTE = "/api/a11oy/v1/llm/sovereign/health"

# Machine-readable reasons distinguish an unset endpoint, an unreachable node,
# and a failed guarded helper without guessing which configuration exists.
REASON_ENV_UNSET = "SZL_LOCAL_LLM_URL_UNSET"          # no Tower targeted at all
REASON_NODE_UNREACHABLE = "NODE_UNREACHABLE_THIS_REQUEST"  # env set, node silent
REASON_PROBE_UNAVAILABLE = "GUARDED_PROBE_UNAVAILABLE"  # helper failed; no direct fallback
REASON_NONE = None                                     # reachable — no reason needed

# How the probed base URL was chosen (env vs the localhost fallback default).
BASE_FROM_ENV = "env:SZL_LOCAL_LLM_URL"
BASE_FROM_DEFAULT = "default:localhost (SZL_LOCAL_LLM_URL unset)"


def unavailable_reason(reachable: bool, env_present: bool) -> str | None:
    """Honest, machine-readable reason code for a non-live sovereign.

    reachable=True  -> None (nothing to explain; the node answered THIS request).
    env unset       -> REASON_ENV_UNSET (env gap: the estate never named a Tower;
                       the probe fell back to the localhost default and was refused).
    env set, silent -> REASON_NODE_UNREACHABLE (Tower down / not routable from here).
    """
    if reachable:
        return REASON_NONE
    return REASON_ENV_UNSET if not env_present else REASON_NODE_UNREACHABLE


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 1. Reachability + served-model probe — REAL, never fabricated.
#    Use the guarded registry helper. Do not fall back to an unguarded URL fetch.
# ---------------------------------------------------------------------------

def _probe_reachability() -> dict[str, Any]:
    """Return an honest reachability report for the local sovereign node.

    {reachable, models, base_url, env_present, api_style, via, dependency, note}
    reachable is True ONLY when the node answered a real 2xx JSON THIS request.
    """
    out: dict[str, Any] = {
        "reachable": False,
        "models": [],
        "base_url": None,
        "env_present": False,
        "api_style": None,
        "via": None,
        "dependency": None,
        "note": "",
        "base_url_source": None,
        "unavailable_reason": REASON_ENV_UNSET,
    }
    # Preferred path: Dev-1's registry helper. It is the SAME code that backs the
    # routed GET /api/a11oy/v1/llm/sovereign/health, so this panel and that endpoint
    # agree by construction (no second, drifting probe).
    try:
        import szl_llm_registry as _reg  # local import (in Dockerfile COPY set)
        probe = _reg.sovereign_probe()
        out["reachable"] = bool(probe.get("live"))
        out["models"] = list(probe.get("models") or [])
        out["base_url"] = probe.get("base_url")
        out["env_present"] = bool(probe.get("env_present"))
        out["api_style"] = probe.get("api_style")
        out["via"] = "szl_llm_registry.sovereign_probe (backs %s)" % DEV1_HEALTH_ROUTE
        out["dependency"] = "resolved: szl_llm_registry present in this runtime"
        out["note"] = str(probe.get("note") or "")
        out["base_url_source"] = BASE_FROM_ENV if out["env_present"] else BASE_FROM_DEFAULT
        out["unavailable_reason"] = unavailable_reason(out["reachable"], out["env_present"])
        return out
    except Exception:  # noqa: BLE001 — no unguarded fallback or diagnostic disclosure
        out["env_present"] = None  # cannot distinguish unset from configured here
        out["unavailable_reason"] = REASON_PROBE_UNAVAILABLE
        out["note"] = "guarded sovereign probe unavailable; status UNAVAILABLE."
        return out


# ---------------------------------------------------------------------------
# 2. Doctrine self-test — not run by a public GET.
# ---------------------------------------------------------------------------

def _doctrine_selftest() -> dict[str, Any]:
    """Describe the self-test without generating or changing inference state."""
    return {
        "prompt": DOCTRINE_SELFTEST_PROMPT,
        "backend_id": SOVEREIGN_BACKEND_ID,
        "model_tag": SOVEREIGN_MODEL_TAG,
        "label": UNAVAILABLE,
        "answer": None,
        "live": False,
        "note": "NOT RUN on public GET; no generation or answer claimed.",
    }


# ---------------------------------------------------------------------------
# 3. Stage A-vs-B — structural declarations plus an unverified tag hint.
# ---------------------------------------------------------------------------

def _stage_status(reach: dict[str, Any]) -> dict[str, Any]:
    """Return Stage A/B declarations plus an unverified served-tag hint."""
    models = [str(m).lower() for m in (reach.get("models") or [])]
    reachable = bool(reach.get("reachable"))
    # A served tag never attests the underlying prompt wrapper or weights.
    if not reachable:
        active = "UNKNOWN"
        active_note = "node unreachable — cannot observe the served tag; stage UNKNOWN (honest)."
    elif any(SOVEREIGN_MODEL_TAG.lower() in m or "finetuned" in m for m in models):
        active = "STAGE_B_TAG_PRESENT"
        active_note = ("the finetuned tag (%s) is served live — the node presents Stage B's "
                       "tag; whether real LoRA weights back it is a Dev-3 deliverable." % SOVEREIGN_MODEL_TAG)
    elif any("llama3" in m for m in models):
        active = "STAGE_A_TAG_PRESENT"
        active_note = ("a base llama3 tag is served; this is only a Stage A hint. "
                       "The prompt wrapper and weights are not verified by a model-list GET.")
    else:
        active = "UNKNOWN"
        active_note = ("node live but served tags do not match the expected sovereign tags; "
                       "stage UNKNOWN (honest).")
    return {
        "label": MODELED,
        "active_stage": active,
        "active_note": active_note,
        "served_models_live": [],  # public status never exports private inventory
        "stage_a": {
            "id": "A",
            "name": "system-prompt derivative (DECLARED)",
            "what": ("Declared design: base llama3.1:8b wrapped with a Doctrine-v11 "
                     "SYSTEM prompt via Ollama; this GET does not verify that wrapper."),
            "status": "DECLARED (not verified by this metadata probe)",
        },
        "stage_b": {
            "id": "B",
            "name": "real LoRA fine-tune (LATER)",
            "what": ("4-bit QLoRA fine-tune of llama3.1:8b on the founder's corpus, exported to "
                     "GGUF + an Ollama ADAPTER so Stage B replaces Stage A under the SAME tag "
                     "(%s). Planned in Dev 3's feat/stage-b-lora pipeline." % SOVEREIGN_MODEL_TAG),
            "status": "ROADMAP (Dev 3 — feat/stage-b-lora)",
        },
        "same_tag_swap": ("Stage B replaces Stage A under the SAME ollama tag (%s), so this panel "
                          "and the router need no change when the founder swaps in real weights."
                          % SOVEREIGN_MODEL_TAG),
    }


# ---------------------------------------------------------------------------
# Payload assembly
# ---------------------------------------------------------------------------

def _doctrine_block() -> dict[str, Any]:
    return {
        "locked_proven": 8,
        "locked_set": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
        "kernel_commit": "c7c0ba17",
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
        "note": ("additive sovereign-status surface; touches no locked formula and no "
                 "kernel; introduces no theorem, no green/1.0, no proof of Λ. Degrades "
                 "to honest UNAVAILABLE when the guarded endpoint is unreachable."),
    }


def build_payload() -> dict[str, Any]:
    """Compose a public status-only snapshot without inference or a new receipt."""
    reach = _probe_reachability()
    reachable = bool(reach.get("reachable"))
    selftest = _doctrine_selftest()
    stage = _stage_status(reach)

    top_label = UNKNOWN if reachable else UNAVAILABLE
    reason = reach.get("unavailable_reason") if not reachable else REASON_NONE
    reason_text = {
        REASON_ENV_UNSET: ("SZL_LOCAL_LLM_URL is not set in this runtime, so no Tower was "
                           "named; the probe fell back to the localhost default and was "
                           "refused. This is an ENVIRONMENT GAP, not a failed node and not "
                           "a code fault. Configuring a reachable endpoint can establish "
                           "metadata reachability, not sovereign ownership or GPU proof."),
        REASON_NODE_UNREACHABLE: ("SZL_LOCAL_LLM_URL is set but the node did not answer this "
                                  "request (Tower down, or not routable from this runtime). "
                                  "Honest UNAVAILABLE — no status or answer is fabricated."),
        REASON_PROBE_UNAVAILABLE: ("The guarded metadata probe is unavailable in this runtime. "
                                    "No direct fallback or inference was attempted."),
    }.get(reason)

    snapshot: dict[str, Any] = {
        "ok": True,
        "endpoint": "frontier/sovereign",
        "service": "a11oy.frontier.sovereign",
        "title": "Sovereign Local Model — read-only status and Stage A/B context",
        "label": top_label,
        "claim": top_label,
        "what": ("Read-only status of the configured model metadata endpoint. A response "
                 "does not prove an owned GPU, model weights, or the declared doctrine "
                 "wrapper; no inference or receipt is produced by this GET."),
        "backend_id": SOVEREIGN_BACKEND_ID,
        "model_tag": SOVEREIGN_MODEL_TAG,
        "endpoint_reachable": reachable,
        "label_basis": "Metadata reachability only; sovereign provenance remains unverified.",
        "gpu_verified": False,
        "weights_verified": False,
        "doctrine_wrapper_verified": False,
        "ownership_proof": UNAVAILABLE,
        "sovereign": {
            "reachable": reachable,
            "model": SOVEREIGN_BACKEND_ID,
            "label": top_label,
            "gpu_verified": False,
            "ownership_proof": UNAVAILABLE,
            "env_present": reach.get("env_present"),
            "unavailable_reason": reason,
            "unavailable_reason_text": reason_text,
        },
        "unavailable_reason": reason,
        "unavailable_reason_text": reason_text,
        "doctrine_selftest": selftest,
        "receipt_status": {
            "label": UNAVAILABLE,
            "receipt_minted": False,
            "note": ("Public GET does not mint a receipt. Existing receipts, if any, "
                     "are neither read nor reclassified here."),
        },
        "stage": stage,
        "dev1_health_route": DEV1_HEALTH_ROUTE,
        "doctrine": _doctrine_block(),
        "labels_legend": {
            UNKNOWN: "metadata endpoint reachable; owner, GPU, and weights not verified",
            UNAVAILABLE: "metadata endpoint was not reachable or guarded probe unavailable",
            MODELED: "structural/definitional description — not a live measurement",
        },
        "timestamp_utc": _now_iso(),
    }
    return snapshot


def rollup_signal() -> dict[str, Any]:
    """Compact {reachable, model, label} for the GET /api/a11oy/healthz rollup (Wave L).

    Guarded + honest: on any failure returns reachable=False + UNAVAILABLE (never fakes
    a reachable node). It exposes no served-model tag or private URL.
    """
    try:
        reach = _probe_reachability()
        reachable = bool(reach.get("reachable"))
        return {
            "reachable": reachable,
            "model": SOVEREIGN_BACKEND_ID,
            "label": UNKNOWN if reachable else UNAVAILABLE,
            "gpu_verified": False,
            "ownership_proof": UNAVAILABLE,
            "unavailable_reason": (reach.get("unavailable_reason")
                                   if not reachable else REASON_NONE),
        }
    except Exception as exc:  # noqa: BLE001 — never crash the health path; honest UNAVAILABLE
        return {"reachable": False, "model": SOVEREIGN_BACKEND_ID, "label": UNAVAILABLE,
                "gpu_verified": False, "ownership_proof": UNAVAILABLE,
                "unavailable_reason": REASON_NODE_UNREACHABLE,
                "error": type(exc).__name__}


def handle() -> dict[str, Any]:
    """GET /frontier/sovereign handler used by FastAPI and __main__."""
    try:
        return build_payload()
    except Exception as exc:  # never 500: honest degraded response, never fabricated
        return {
            "ok": False,
            "endpoint": "frontier/sovereign",
            "label": UNAVAILABLE,
            "endpoint_reachable": False,
            "gpu_verified": False,
            "ownership_proof": UNAVAILABLE,
            "unavailable_reason": REASON_NODE_UNREACHABLE,
            "error": type(exc).__name__,
            "doctrine": "v11: sovereign surface unavailable; no fabricated status/answer emitted.",
            "timestamp_utc": _now_iso(),
        }


# ---------------------------------------------------------------------------
# FastAPI router registration — mirrors szl_frontier_zkinfer.register() exactly.
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the sovereign panel endpoint on the FastAPI ``app``. Returns a status string."""
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/frontier"

    @app.get(f"{base}/sovereign")
    async def _frontier_sovereign():
        """Sovereign local model status, with no inference or receipt on GET."""
        return JSONResponse(handle())

    return "frontier-sovereign-wired:1"


# ---------------------------------------------------------------------------
# Self-test — honest labels, no upgrade, degrades to UNAVAILABLE, sources cited.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json
    import sys as _sys

    print("=" * 72)
    print("szl_sovereign_panel — self-test (honest labels; UNAVAILABLE when Tower down)")
    print("=" * 72)

    p = build_payload()
    blob = _json.dumps(p)

    # 1) status never promotes metadata reachability to sovereign provenance.
    assert p["ok"] is True
    assert p["label"] in (UNKNOWN, UNAVAILABLE)
    assert p["label"] == p["claim"]
    assert p["backend_id"] == SOVEREIGN_BACKEND_ID
    assert p["model_tag"] == SOVEREIGN_MODEL_TAG
    sov = p["sovereign"]
    assert set(("reachable", "model", "label")) <= set(sov)
    assert isinstance(sov["reachable"], bool)
    assert (sov["label"] == UNKNOWN) == (sov["reachable"] is True)
    assert p["gpu_verified"] is False and p["ownership_proof"] == UNAVAILABLE
    print(f"[1] top label={p['label']}, reachable={sov['reachable']} (consistent, not fabricated)  OK")

    # 2) doctrine self-test is never run from a status GET.
    st = p["doctrine_selftest"]
    assert st["prompt"] == DOCTRINE_SELFTEST_PROMPT
    assert st["label"] == UNAVAILABLE and st["answer"] is None and st["live"] is False
    print("[2] doctrine self-test not run on GET; no answer fabricated  OK")

    # 3) Stage A/B present + honest active stage; UNKNOWN when unreachable.
    stg = p["stage"]
    assert stg["stage_a"]["id"] == "A" and stg["stage_b"]["id"] == "B"
    if not sov["reachable"]:
        assert stg["active_stage"] == "UNKNOWN"
    print(f"[3] Stage A/B present; active_stage={stg['active_stage']}  OK")

    # 4) doctrine: locked-8 exact, adds nothing, Λ Conjecture 1, trust 0.97 not 100%.
    d = p["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[4] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    # 5) no new receipt on a read; this does not alter any historical receipt.
    assert "signed_receipt" not in p
    assert p["receipt_status"]["receipt_minted"] is False
    print("[5] no receipt minted by GET; historical receipts unassessed  OK")

    # 6) rollup signal shape {reachable, model, label}, honest + consistent.
    r = rollup_signal()
    assert set(("reachable", "model", "label")) <= set(r)
    assert (r["label"] == UNKNOWN) == (r["reachable"] is True)
    print(f"[6] healthz rollup signal {{'reachable':{r['reachable']}, 'label':'{r['label']}'}}  OK")

    # 7) no VERIFIED/green-1.0 top state; trust never 100%.
    assert "VERIFIED" not in {p["label"], p["claim"]}
    assert d["trust_ceiling"] < 1.0
    print("[7] no VERIFIED/green-1.0 top state; trust never 100%  OK")

    print("\n--- payload keys ---")
    for k in p:
        print(f"  - {k}")
    print("\nok:true checks:7")
    _sys.exit(0)
