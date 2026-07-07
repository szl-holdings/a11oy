#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""szl_sovereign_panel.py — Sovereign Local Model panel (Wave M, Dev 4).

GET /api/a11oy/v1/frontier/sovereign returns the operator-facing status of the
founder's LOCAL sovereign model — the llama3-based, Doctrine-v11-wrapped model the
founder is standing up on the Tower (OMEN, RTX 4060 Ti) via Ollama, served
OpenAI-compatible at ``SZL_LOCAL_LLM_URL`` (default http://localhost:11434/v1).

The panel surfaces FOUR honest signals, and NEVER fabricates a live one:

  1. reachability — is the local sovereign endpoint reachable RIGHT NOW? The Tower is
     NOT reachable from CI/cloud, so from a Space/CI run this MUST degrade to an
     honest UNAVAILABLE (never a fabricated "reachable"). We prefer Dev-1's routed
     health helper (`szl_llm_registry.sovereign_probe`, which also backs Dev-1's
     GET /api/a11oy/v1/llm/sovereign/health); if that module is not present yet we
     probe SZL_LOCAL_LLM_URL directly and record the dependency honestly.

  2. doctrine self-test — asks the local model "State your doctrine in one line" and
     shows the model's REAL answer WHEN the node is reachable; otherwise an honest
     UNAVAILABLE (the intended prompt + backend id are still recorded — no answer is
     invented). Backed by `szl_llm_registry.sovereign_generate`.

  3. Stage A-vs-B — Stage A is the system-prompt derivative running NOW (a
     Doctrine-v11 SYSTEM prompt wrapped around base llama3.1:8b); Stage B is the real
     LoRA fine-tune on the founder's corpus (later — Dev 3's `feat/stage-b-lora`
     pipeline). We report which stage the LIVE node's served model tag indicates,
     honestly UNKNOWN when the node is unreachable.

  4. a signed receipt of the check — a DSSE envelope over the assembled panel
     snapshot (REAL ECDSA-P256 in-Space when the cosign key is present, honest
     UNSIGNED-LOCAL otherwise — never a fabricated signature). This is the "receipt
     of the check" — the check ran and its result is attested, even when the answer
     is UNAVAILABLE.

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17;
    touches no locked formula and no kernel.
  - Λ stays Conjecture 1 (advisory, never "green"/theorem). Trust ceiling 0.97.
  - Honest labels ONLY: LIVE-SOVEREIGN when the node answered live THIS request;
    UNAVAILABLE when it did not (Tower down / SZL_LOCAL_LLM_URL unset). No label is
    ever upgraded and no answer is fabricated (Zero-Bandaid Law).
  - Additive route, registered BEFORE the SPA catch-all; 0 runtime CDN.
"""
from __future__ import annotations

import datetime
import hashlib
from typing import Any

# Honesty-label vocabulary (doctrine v11) — tests grep these exact strings.
LIVE_SOVEREIGN = "LIVE-SOVEREIGN"
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

# Dev-1's routed health endpoint (this panel is a READER of it; if Dev-1's PR is not
# merged yet we fall back to the registry helper / a direct probe and say so).
DEV1_HEALTH_ROUTE = "/api/a11oy/v1/llm/sovereign/health"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha256_hex(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 1. Reachability + served-model probe — REAL, never fabricated.
#    Prefer Dev-1's registry helper (`sovereign_probe`, which also backs the routed
#    GET /llm/sovereign/health); else probe SZL_LOCAL_LLM_URL directly + note the dep.
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
        return out
    except Exception as exc:  # noqa: BLE001 — Dev-1 module absent → honest direct fallback
        out["dependency"] = (
            "PENDING: szl_llm_registry.sovereign_probe unavailable (%s). Dev-1's "
            "%s not merged in this runtime — falling back to a DIRECT probe of "
            "SZL_LOCAL_LLM_URL and reporting honestly." % (type(exc).__name__, DEV1_HEALTH_ROUTE)
        )
    # Direct fallback: probe SZL_LOCAL_LLM_URL ourselves (pure stdlib, short timeout,
    # never raises, never fabricates reachable=True).
    import json as _json
    import os as _os
    import urllib.request as _rq

    base = (_os.environ.get("SZL_LOCAL_LLM_URL", "") or "").strip().rstrip("/")
    out["base_url"] = base or None
    out["env_present"] = bool(base)
    out["via"] = "direct SZL_LOCAL_LLM_URL probe (Dev-1 helper absent)"
    if not base:
        out["note"] = ("SZL_LOCAL_LLM_URL not set — sovereign node is an HONEST STUB; "
                       "reachability UNAVAILABLE (never fabricated).")
        return out
    # The env default is …/v1 (OpenAI-compatible); ollama's native /api/tags lives at
    # the host root, so strip a trailing /v1 for the native probe.
    root = base[:-3].rstrip("/") if base.endswith("/v1") else base
    for url, kind, key, itemkey in (
        (root + "/api/tags", "ollama /api", "models", "name"),
        (base + "/models", "openai /v1", "data", "id"),
        (root + "/v1/models", "openai /v1", "data", "id"),
    ):
        try:
            req = _rq.Request(url, method="GET", headers={"Accept": "application/json"})
            with _rq.urlopen(req, timeout=4.0) as r:  # noqa: S310
                if not (200 <= int(getattr(r, "status", 200) or 200) < 300):
                    continue
                doc = _json.loads(r.read().decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001 — unreachable/timeout → try next / honest UNAVAILABLE
            continue
        if isinstance(doc, dict) and isinstance(doc.get(key), list):
            names = [str(m.get(itemkey)) for m in doc[key]
                     if isinstance(m, dict) and m.get(itemkey)]
            out["reachable"] = True
            out["models"] = names
            out["api_style"] = kind
            out["note"] = "node live (%s) — model list real THIS request (direct probe)." % kind
            return out
    out["note"] = ("SZL_LOCAL_LLM_URL set but node did not respond live this request "
                   "(direct probe) — honest UNAVAILABLE, never fabricated.")
    return out


# ---------------------------------------------------------------------------
# 2. Doctrine self-test — REAL local answer when reachable, else honest UNAVAILABLE.
# ---------------------------------------------------------------------------

def _doctrine_selftest(reachable: bool) -> dict[str, Any]:
    """Ask the local model to state its doctrine in one line. Shows the REAL answer
    only when the node answered live THIS request; otherwise honest UNAVAILABLE with
    the intended prompt + backend id recorded (no invented answer)."""
    st: dict[str, Any] = {
        "prompt": DOCTRINE_SELFTEST_PROMPT,
        "backend_id": SOVEREIGN_BACKEND_ID,
        "model_tag": SOVEREIGN_MODEL_TAG,
        "label": UNAVAILABLE,
        "answer": None,
        "live": False,
        "note": "",
    }
    if not reachable:
        st["note"] = ("local sovereign node not reachable this request — doctrine "
                      "self-test UNAVAILABLE (Tower down / CI cannot reach the Tower). "
                      "No answer fabricated.")
        return st
    try:
        import szl_llm_registry as _reg  # local import (in Dockerfile COPY set)
        gen = _reg.sovereign_generate(DOCTRINE_SELFTEST_PROMPT)
    except Exception as exc:  # noqa: BLE001 — helper absent → honest UNAVAILABLE
        st["note"] = ("doctrine self-test could not run (szl_llm_registry absent: %s) — "
                      "honest UNAVAILABLE." % type(exc).__name__)
        return st
    if gen.get("live") and isinstance(gen.get("text"), str) and gen["text"].strip():
        answer = gen["text"].strip()
        st.update({
            "label": LIVE_SOVEREIGN,
            "answer": answer,
            "live": True,
            "model_served": gen.get("model"),
            "api_style": gen.get("api_style"),
            "answer_sha256": _sha256_hex(answer.encode("utf-8")),
            "note": "REAL local generation THIS request (%s)." % (gen.get("api_style") or "local"),
        })
        return st
    st["note"] = ("node did not generate live this request — honest UNAVAILABLE "
                  "(no fabricated doctrine line). %s" % (gen.get("note") or ""))
    return st


# ---------------------------------------------------------------------------
# 3. Stage A-vs-B — structural + a LIVE-derived stage hint (honest UNKNOWN when down).
# ---------------------------------------------------------------------------

def _stage_status(reach: dict[str, Any]) -> dict[str, Any]:
    """Stage A = system-prompt derivative (now); Stage B = real LoRA fine-tune (later,
    Dev 3). We derive a stage HINT from the live node's served tags, honestly UNKNOWN
    when the node is unreachable. Definitional fields never claim a live measurement."""
    models = [str(m).lower() for m in (reach.get("models") or [])]
    reachable = bool(reach.get("reachable"))
    # If the finetuned tag is being served live, the node is at least presenting Stage B's
    # tag; a plain base tag indicates Stage A (system-prompt wrapper). Honest, tag-based hint.
    if not reachable:
        active = "UNKNOWN"
        active_note = "node unreachable — cannot observe the served tag; stage UNKNOWN (honest)."
    elif any(SOVEREIGN_MODEL_TAG.lower() in m or "finetuned" in m for m in models):
        active = "STAGE_B_TAG_PRESENT"
        active_note = ("the finetuned tag (%s) is served live — the node presents Stage B's "
                       "tag; whether real LoRA weights back it is a Dev-3 deliverable." % SOVEREIGN_MODEL_TAG)
    elif any("llama3" in m for m in models):
        active = "STAGE_A"
        active_note = ("a base llama3 tag is served live and the finetuned tag is NOT — Stage A "
                       "(Doctrine-v11 system-prompt derivative over base llama3.1:8b).")
    else:
        active = "UNKNOWN"
        active_note = ("node live but served tags do not match the expected sovereign tags; "
                       "stage UNKNOWN (honest).")
    return {
        "label": MODELED,
        "active_stage": active,
        "active_note": active_note,
        "served_models_live": reach.get("models") or [],
        "stage_a": {
            "id": "A",
            "name": "system-prompt derivative (NOW)",
            "what": ("base llama3.1:8b wrapped with a Doctrine-v11 SYSTEM prompt via Ollama; "
                     "no weight change — behavior comes from the system prompt."),
            "status": "LIVE-WHEN-REACHABLE",
        },
        "stage_b": {
            "id": "B",
            "name": "real LoRA fine-tune (LATER)",
            "what": ("4-bit QLoRA fine-tune of llama3.1:8b on the founder's corpus, exported to "
                     "GGUF + an Ollama ADAPTER so Stage B replaces Stage A under the SAME tag "
                     "(%s). Delivered by Dev 3's feat/stage-b-lora pipeline." % SOVEREIGN_MODEL_TAG),
            "status": "ROADMAP (Dev 3 — feat/stage-b-lora)",
        },
        "same_tag_swap": ("Stage B replaces Stage A under the SAME ollama tag (%s), so this panel "
                          "and the router need no change when the founder swaps in real weights."
                          % SOVEREIGN_MODEL_TAG),
    }


# ---------------------------------------------------------------------------
# 4. Signed receipt of the check — REAL DSSE in-Space, honest UNSIGNED-LOCAL else.
# ---------------------------------------------------------------------------

def _sign_receipt(snapshot: dict[str, Any]) -> dict[str, Any]:
    """DSSE envelope over the panel snapshot (the "receipt of the check"). REAL
    ECDSA-P256 when the cosign key is present in the runtime, honest UNSIGNED-LOCAL
    otherwise — never a fabricated signature."""
    receipt_body = {
        "kind": "sovereign_panel_check",
        "backend_id": SOVEREIGN_BACKEND_ID,
        "model_tag": SOVEREIGN_MODEL_TAG,
        "reachable": snapshot.get("sovereign", {}).get("reachable"),
        "label": snapshot.get("label"),
        "doctrine_selftest_label": snapshot.get("doctrine_selftest", {}).get("label"),
        "active_stage": snapshot.get("stage", {}).get("active_stage"),
        "checked_at": snapshot.get("timestamp_utc"),
    }
    try:
        import szl_dsse as _dsse  # local import (in Dockerfile COPY set)
        env = _dsse.sign_payload(receipt_body, payload_type="application/vnd.szl.sovereign-check+json")
        signed = bool(env.get("signed"))
        return {
            "receipt": receipt_body,
            "dsse": env,
            "signed": signed,
            "sign_mode": "DSSE-LIVE" if signed else "UNSIGNED-LOCAL",
            "signer_fingerprint": (_dsse.public_key_fingerprint()
                                   if hasattr(_dsse, "public_key_fingerprint") else None),
            "note": ("REAL ECDSA-P256 DSSE over the check snapshot."
                     if signed else
                     "UNSIGNED-LOCAL — no cosign private key in this runtime; receipt "
                     "explicitly unsigned (never fabricated)."),
        }
    except Exception as exc:  # noqa: BLE001 — signer absent → honest self-hash, never faked sig
        return {
            "receipt": receipt_body,
            "dsse": None,
            "signed": False,
            "sign_mode": "UNSIGNED-LOCAL",
            "content_sha256": _sha256_hex(repr(sorted(receipt_body.items())).encode("utf-8")),
            "note": ("DSSE signer unavailable (%s) — receipt is UNSIGNED-LOCAL with a plain "
                     "content hash; no signature fabricated." % type(exc).__name__),
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
                 "to honest UNAVAILABLE when the Tower is unreachable — never fabricated."),
    }


def build_payload() -> dict[str, Any]:
    """Compose the sovereign panel snapshot + sign a receipt of the check.

    ORDER MATTERS: probe first, self-test gated on reachability, stage derived from the
    probe, THEN sign the assembled snapshot so the receipt attests exactly what was seen.
    """
    reach = _probe_reachability()
    reachable = bool(reach.get("reachable"))
    selftest = _doctrine_selftest(reachable)
    stage = _stage_status(reach)

    top_label = LIVE_SOVEREIGN if reachable else UNAVAILABLE
    # A served-model label for the healthz rollup + the panel header (honest).
    live_models = reach.get("models") or []
    model_label = (live_models[0] if (reachable and live_models) else SOVEREIGN_MODEL_TAG)

    snapshot: dict[str, Any] = {
        "ok": True,
        "endpoint": "frontier/sovereign",
        "service": "a11oy.frontier.sovereign",
        "title": "Sovereign Local Model — status, doctrine self-test, Stage A/B, signed receipt",
        "label": top_label,
        "claim": top_label,
        "what": ("operator status of the founder's LOCAL sovereign model (Ollama on the Tower, "
                 "Doctrine-v11 system prompt over base llama3.1:8b; model tag %s). The Tower is "
                 "NOT reachable from CI/cloud, so this degrades to honest UNAVAILABLE off-Tower — "
                 "never a fabricated 'reachable' or a fabricated doctrine line." % SOVEREIGN_MODEL_TAG),
        "backend_id": SOVEREIGN_BACKEND_ID,
        "model_tag": SOVEREIGN_MODEL_TAG,
        "sovereign": {
            "reachable": reachable,
            "model": model_label,
            "label": top_label,
            "base_url": reach.get("base_url"),
            "env_present": reach.get("env_present"),
            "api_style": reach.get("api_style"),
            "models_live": live_models,
            "via": reach.get("via"),
            "dependency": reach.get("dependency"),
            "note": reach.get("note"),
        },
        "doctrine_selftest": selftest,
        "stage": stage,
        "dev1_health_route": DEV1_HEALTH_ROUTE,
        "doctrine": _doctrine_block(),
        "labels_legend": {
            LIVE_SOVEREIGN: "the local sovereign node answered live THIS request — real, not fabricated",
            UNAVAILABLE: "the local node was not reachable this request (Tower down / off-Tower / unset) — honest, never faked",
            MODELED: "structural/definitional description — not a live measurement",
        },
        "timestamp_utc": _now_iso(),
    }
    # Sign a receipt of the check (over the assembled snapshot). Attaches to the payload.
    snapshot["signed_receipt"] = _sign_receipt(snapshot)
    return snapshot


def rollup_signal() -> dict[str, Any]:
    """Compact {reachable, model, label} for the GET /api/a11oy/healthz rollup (Wave L).

    Guarded + honest: on any failure returns reachable=False + UNAVAILABLE (never fakes
    a reachable node). Cheap — one short probe, no generation.
    """
    try:
        reach = _probe_reachability()
        reachable = bool(reach.get("reachable"))
        live_models = reach.get("models") or []
        return {
            "reachable": reachable,
            "model": (live_models[0] if (reachable and live_models) else SOVEREIGN_MODEL_TAG),
            "label": LIVE_SOVEREIGN if reachable else UNAVAILABLE,
        }
    except Exception as exc:  # noqa: BLE001 — never crash the health path; honest UNAVAILABLE
        return {"reachable": False, "model": SOVEREIGN_MODEL_TAG, "label": UNAVAILABLE,
                "error": f"{type(exc).__name__}: {exc}"}


def handle() -> dict[str, Any]:
    """GET /frontier/sovereign handler used by FastAPI and __main__."""
    try:
        return build_payload()
    except Exception as exc:  # never 500: honest degraded response, never fabricated
        return {
            "ok": False,
            "endpoint": "frontier/sovereign",
            "label": UNAVAILABLE,
            "error": str(exc),
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
        """Sovereign local model status + doctrine self-test + Stage A/B + signed receipt."""
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

    # 1) shape + honest top label. Off-Tower (CI) MUST be UNAVAILABLE, never fabricated live.
    assert p["ok"] is True
    assert p["label"] in (LIVE_SOVEREIGN, UNAVAILABLE)
    assert p["label"] == p["claim"]
    assert p["backend_id"] == SOVEREIGN_BACKEND_ID
    assert p["model_tag"] == SOVEREIGN_MODEL_TAG
    sov = p["sovereign"]
    assert set(("reachable", "model", "label")) <= set(sov)
    assert isinstance(sov["reachable"], bool)
    # label MUST be consistent with reachability (no faked reachable=True).
    assert (sov["label"] == LIVE_SOVEREIGN) == (sov["reachable"] is True)
    print(f"[1] top label={p['label']}, reachable={sov['reachable']} (consistent, not fabricated)  OK")

    # 2) doctrine self-test: real answer ONLY when reachable; else honest UNAVAILABLE + no answer.
    st = p["doctrine_selftest"]
    assert st["prompt"] == DOCTRINE_SELFTEST_PROMPT
    if sov["reachable"]:
        assert st["label"] == LIVE_SOVEREIGN and isinstance(st["answer"], str) and st["answer"].strip()
    else:
        assert st["label"] == UNAVAILABLE and st["answer"] is None
    print(f"[2] doctrine self-test label={st['label']}, answer_present={st['answer'] is not None} "
          "(no fabrication when down)  OK")

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

    # 5) signed receipt of the check present + honest sign mode (never a faked signature).
    sr = p["signed_receipt"]
    assert sr["sign_mode"] in ("DSSE-LIVE", "UNSIGNED-LOCAL")
    assert isinstance(sr["receipt"], dict) and sr["receipt"]["backend_id"] == SOVEREIGN_BACKEND_ID
    if sr["sign_mode"] == "UNSIGNED-LOCAL":
        # unsigned envelope must NOT carry a fabricated signature
        env = sr.get("dsse") or {}
        assert not env.get("signatures")
    print(f"[5] signed receipt present; sign_mode={sr['sign_mode']} (no fabricated signature)  OK")

    # 6) rollup signal shape {reachable, model, label}, honest + consistent.
    r = rollup_signal()
    assert set(("reachable", "model", "label")) <= set(r)
    assert (r["label"] == LIVE_SOVEREIGN) == (r["reachable"] is True)
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
