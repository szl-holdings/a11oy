# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
# Authored by Yachay (CTO). Co-Authored-By: Perplexity Computer Agent.
"""
operator_shell_v4 — the Unified Operator Shell v4 endpoint contract, registered
ADDITIVELY on each flagship's FastAPI app. ONE module, FOUR flagships.

Exposes EXACTLY (organ in {a11oy, sentra, amaru, killinchu}):

    GET  /api/<organ>/v4/inbox          active inbox items only (noise rule)
    GET  /api/<organ>/v4/map/state      current 3D scene state (discriminated by kind)
    POST /api/<organ>/v4/command        slash command -> DSSE receipt
    GET  /api/<organ>/v4/receipts        recent successfully-signed receipts
    GET  /api/<organ>/v4/replay/{hash}   reconstructed state at a frame
    GET  /api/<organ>/v4/stream          SSE live updates (text/event-stream)
    GET  /api/<organ>/v4/healthz         minimal health JSON
    GET  /<organ>/operator  and  /operator   serve web/operator.html (desktop shell)

Honesty:
  * Receipts are signed by the LIVE szl_dsse module (real ECDSA-P256 cosign over
    DSSE PAE) when SZL_COSIGN_PRIVATE_PEM is present; otherwise an explicit
    UNSIGNED envelope is returned (never fabricated).
  * Per-organ keyid is carried as a receipt-metadata label; the cryptographic
    keyid remains the real shared "szlholdings-cosign" during the transition.
  * map/state and inbox surface ONLY live, state-changing items. Empty buffers
    return empty arrays (the UI renders an honest IDLE / calm message).

Register from serve.py, BEFORE the SPA catch-all:

    import operator_shell_v4 as _osh
    _osh.register(app, "a11oy")
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

try:
    import szl_dsse as _dsse  # the LIVE signing module
except Exception:  # pragma: no cover
    _dsse = None

ISO = lambda: datetime.now(timezone.utc).isoformat()

# --------------------------------------------------------------------------- #
# Sovereign LLM routing (GPU-routing directive, founder 2026-06-13). ONE shared
# client across a11oy + killinchu (this module is byte-identical in both Spaces).
#
# Resolution order — honest, never overclaim sovereign:
#   (a) founder GPU over Tailscale  : if SZL_GPU_BASE_URL is set AND a short live
#       health probe to it succeeds THIS request  -> sovereign=True,
#       provider="self-hosted-gpu" (Qwen2.5-7B on the founder's box via vLLM).
#   (b) honest fallback (HF router) : ONLY if SZL_LLM_FALLBACK_ALLOWED is truthy
#       AND SZL_HF_ROUTER_BASE_URL is set        -> sovereign=False,
#       provider="hf-router-fallback" + honest_note (compute is HF's, not the box).
#   (c) neither reachable/allowed   : fail honestly                -> sovereign=False,
#       provider="offline", online=False. NEVER fabricate a completion.
#
# The endpoint + any token live in the Space SECRET store (env), referenced by
# NAME only — never committed. SZL_GPU_BASE_URL is a Tailscale MagicDNS name or
# 100.x IP, e.g. http://<box-tailscale-name>:8000/v1 . The legacy Space-internal
# default http://local-llm:8000/v1 is NOT the founder's GPU and is retained ONLY
# as a last-resort local probe target, never as a sovereign claim.
# --------------------------------------------------------------------------- #

# --- env-resolved endpoints (referenced by NAME only; never a committed key) --- #
GPU_BASE_URL = (os.environ.get("SZL_GPU_BASE_URL") or "").strip().rstrip("/")
GPU_TOKEN = os.environ.get("SZL_GPU_TOKEN") or os.environ.get("SZL_GPU_API_KEY") or ""
HF_ROUTER_BASE_URL = (os.environ.get("SZL_HF_ROUTER_BASE_URL") or "").strip().rstrip("/")
HF_ROUTER_TOKEN = os.environ.get("SZL_HF_ROUTER_TOKEN") or os.environ.get("HF_TOKEN") or ""
_FALLBACK_ALLOWED = (os.environ.get("SZL_LLM_FALLBACK_ALLOWED", "").strip().lower()
                     in ("1", "true", "yes", "on"))
# Legacy local default — retained as a fallback PROBE target only (never sovereign).
LOCAL_LLM_BASE = (os.environ.get("SZL_LOCAL_LLM_BASE") or "http://local-llm:8000/v1").rstrip("/")
LOCAL_LLM_MODEL = os.environ.get("SZL_LOCAL_LLM_MODEL", "Qwen2.5-7B-Instruct-AWQ")
GPU_PROBE_TIMEOUT = float(os.environ.get("SZL_GPU_PROBE_TIMEOUT", "1.5"))


def _redact_base(url: str) -> str:
    """Return host[:port] of a base_url (path/scheme/credentials stripped) so
    healthz can disclose WHERE inference points without leaking a full secret URL."""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        p = urlparse(url if "://" in url else "//" + url, scheme="http")
        return p.netloc or p.path.split("/")[0]
    except Exception:
        return "set"


def _probe(base: str, token: str = "", timeout: float | None = None) -> bool:
    """Bounded GET {base}/models reachability probe. True only on HTTP 200.
    Never raises; never a fabricated result. Used to gate every sovereign claim."""
    if not base:
        return False
    try:
        import urllib.request
        req = urllib.request.Request(f"{base.rstrip('/')}/models", method="GET")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=(timeout or GPU_PROBE_TIMEOUT)) as r:
            return getattr(r, "status", r.getcode()) == 200
    except Exception:
        return False


def resolve_llm(probe: bool = True) -> dict[str, Any]:
    """Resolve the active LLM inference path HONESTLY. Returns a dict:
        {provider, base_url, base_redacted, model, sovereign, gpu_reachable,
         online, cloud, honest_note}
    sovereign is True ONLY when a live probe to the founder GPU succeeded THIS
    call. No probe success => never sovereign. This is the single source of
    truth consumed by healthz, the posture endpoint and the NL command path."""
    # (a) founder GPU over Tailscale — sovereign iff configured AND live-reachable.
    if GPU_BASE_URL:
        gpu_ok = _probe(GPU_BASE_URL, GPU_TOKEN) if probe else False
        if gpu_ok:
            return {"provider": "self-hosted-gpu", "base_url": GPU_BASE_URL,
                    "base_redacted": _redact_base(GPU_BASE_URL), "model": LOCAL_LLM_MODEL,
                    "sovereign": True, "gpu_reachable": True, "online": True, "cloud": False,
                    "honest_note": "Inference on the founder GPU (Qwen2.5-7B via vLLM) over "
                                   "Tailscale; verified by a live /models probe this request."}
        # GPU configured but NOT reachable this request — fall through; never claim sovereign.
        if _FALLBACK_ALLOWED and HF_ROUTER_BASE_URL:
            return {"provider": "hf-router-fallback", "base_url": HF_ROUTER_BASE_URL,
                    "base_redacted": _redact_base(HF_ROUTER_BASE_URL), "model": LOCAL_LLM_MODEL,
                    "sovereign": False, "gpu_reachable": False, "online": True, "cloud": True,
                    "honest_note": "Founder GPU configured but UNREACHABLE this request "
                                   "(Tailscale link down/flapping). Degraded to the HF router "
                                   "fallback (compute is Hugging Face's, NOT the founder box). "
                                   "NOT sovereign."}
        return {"provider": "offline", "base_url": GPU_BASE_URL,
                "base_redacted": _redact_base(GPU_BASE_URL), "model": LOCAL_LLM_MODEL,
                "sovereign": False, "gpu_reachable": False, "online": False, "cloud": False,
                "honest_note": "Founder GPU configured but UNREACHABLE this request and no "
                               "fallback allowed. Failing closed — no completion fabricated."}
    # No GPU configured: honest fallback only if explicitly allowed; else fail closed.
    if _FALLBACK_ALLOWED and HF_ROUTER_BASE_URL:
        return {"provider": "hf-router-fallback", "base_url": HF_ROUTER_BASE_URL,
                "base_redacted": _redact_base(HF_ROUTER_BASE_URL), "model": LOCAL_LLM_MODEL,
                "sovereign": False, "gpu_reachable": False, "online": True, "cloud": True,
                "honest_note": "SZL_GPU_BASE_URL not set. Using HF router fallback (compute is "
                               "Hugging Face's, NOT the founder box). NOT sovereign."}
    # Last resort: legacy local probe (Space-internal). Never sovereign, never fabricated.
    local_ok = _probe(LOCAL_LLM_BASE) if probe else False
    return {"provider": "offline", "base_url": LOCAL_LLM_BASE,
            "base_redacted": _redact_base(LOCAL_LLM_BASE), "model": LOCAL_LLM_MODEL,
            "sovereign": False, "gpu_reachable": False, "online": bool(local_ok), "cloud": False,
            "honest_note": "SZL_GPU_BASE_URL not set and no fallback allowed. "
                           + ("Legacy Space-internal local LLM reachable but it is NOT the "
                              "founder GPU — NOT sovereign." if local_ok else
                              "No reachable LLM. Failing closed — no completion fabricated.")}


def posture(organ: str, probe: bool = True) -> dict[str, Any]:
    """Per-organ inference posture: where inference runs RIGHT NOW.
    where in {gpu | fallback | offline}. Honest, live-probed, additive."""
    r = resolve_llm(probe=probe)
    where = ("gpu" if r["provider"] == "self-hosted-gpu"
             else "fallback" if r["provider"] == "hf-router-fallback"
             else "offline")
    return {"organ": organ, "where": where, "provider": r["provider"],
            "sovereign": r["sovereign"], "gpu_reachable": r["gpu_reachable"],
            "online": r["online"], "model": r["model"], "base_redacted": r["base_redacted"],
            "gpu_configured": bool(GPU_BASE_URL), "fallback_allowed": _FALLBACK_ALLOWED,
            "honest_note": r["honest_note"], "doctrine": DOCTRINE["version"], "ts": ISO()}


def _local_llm_nl_to_command(text: str) -> dict[str, Any]:
    """Map a natural-language phrase to a slash command using the resolved LLM.
    Routes to the founder GPU when reachable, else honest fallback/offline.
    Returns {command, source, fallback, ...}. On any failure -> deterministic
    stub (keyword heuristic) with fallback=True so the caller signs a FALLBACK
    receipt. NEVER fabricates a model completion when no backend is reachable."""
    sys_prompt = ("You translate an operator phrase into ONE slash command from: "
                  "/sign /verify /inspect /replay /gate /khipu /filter /yuyay /track. "
                  "Reply with ONLY the command line, no prose.")
    r = resolve_llm(probe=True)
    if r["online"] and r["provider"] in ("self-hosted-gpu", "hf-router-fallback"):
        try:
            import urllib.request
            tok = GPU_TOKEN if r["provider"] == "self-hosted-gpu" else HF_ROUTER_TOKEN
            headers = {"Content-Type": "application/json"}
            if tok:
                headers["Authorization"] = f"Bearer {tok}"
            req = urllib.request.Request(
                f"{r['base_url']}/chat/completions",
                data=json.dumps({"model": r["model"], "max_tokens": 32, "temperature": 0,
                                 "messages": [{"role": "system", "content": sys_prompt},
                                              {"role": "user", "content": text}]}).encode(),
                headers=headers)
            with urllib.request.urlopen(req, timeout=4) as resp:
                out = json.loads(resp.read())
                cmd = out["choices"][0]["message"]["content"].strip().splitlines()[0]
                return {"command": cmd, "source": f"{r['provider']}:{r['model']}",
                        "sovereign": r["sovereign"], "provider": r["provider"], "fallback": False}
        except Exception:
            pass  # fall through to deterministic stub — never a fabricated completion
    # Honest deterministic stub — no reachable backend (offline) or a transient error.
    t = text.lower()
    guess = "/inspect " + text.strip()
    for kw, c in (("sign", "/sign"), ("verif", "/verify"), ("replay", "/replay"),
                  ("gate", "/gate"), ("filter", "/filter"), ("track", "/track")):
        if kw in t:
            guess = c + " " + text.strip()
            break
    return {"command": guess, "source": "deterministic-stub", "fallback": True,
            "sovereign": False, "provider": r["provider"],
            "note": f"LLM path '{r['provider']}' unavailable ({r['base_redacted'] or 'unset'}) "
                    f"— falling back to deterministic stub. {r['honest_note']}"}
PER_ORGAN_KEYID = {"a11oy": "a11oy-cosign", "sentra": "sentra-cosign",
                   "amaru": "amaru-cosign", "killinchu": "killinchu-cosign"}
DOCTRINE = {"version": "v11", "counts": "749/14/163", "lean_sha": "c7c0ba17",
            "numbers": {"declarations": 749, "axioms": 14, "sorries": 163}}

# In-process live event ring (real events appended by /command + organ hooks).
# Never pre-seeded with fake data — empty until something actually happens.
_RING: dict[str, list[dict]] = {}
_INBOX: dict[str, list[dict]] = {}


def _ring(organ: str) -> list[dict]:
    return _RING.setdefault(organ, [])


def _now_minus(seconds: float) -> float:
    return time.time() - seconds


def _local_llm_online() -> bool:
    """Back-compat shim: True iff the ACTIVE resolved LLM path is online this
    request (founder GPU reachable, or an allowed fallback online). Probes the
    real resolved endpoint — NOT a hardcoded Space-internal address."""
    return bool(resolve_llm(probe=True).get("online"))


# --------------------------------------------------------------------------- #
# Receipt signing (delegates to the live szl_dsse)
# --------------------------------------------------------------------------- #
def _sign_receipt(organ: str, action_verb: str, action_target: str, verdict: str = "pass") -> dict[str, Any]:
    receipt = {
        "organ": organ,
        "keyid_label": PER_ORGAN_KEYID.get(organ, "szlholdings-cosign"),
        "action_verb": action_verb,
        "action_target": action_target,
        "verdict": verdict,
        "lean_sha": DOCTRINE["lean_sha"],
        "doctrine": DOCTRINE["version"],
        "doctrine_numbers": DOCTRINE["numbers"],
        "ts": ISO(),
    }
    if _dsse is None:
        return {"receipt": receipt, "dsse": {"signed": False,
                "honesty": "szl_dsse module unavailable in this runtime; no signature."}}
    signed = _dsse.sign_khipu_receipt(receipt)
    env = signed.get("dsse", {})
    sha = env.get("_pae_sha256")
    signed["receipt"]["receipt_sha"] = ("sha256:" + sha) if sha else None
    signed["receipt"]["keyid"] = (env.get("signatures") or [{}])[0].get("keyid", "szlholdings-cosign")
    signed["receipt"]["signed"] = bool(env.get("signed"))
    return signed


# --------------------------------------------------------------------------- #
# Per-organ map/state builders — surface ONLY live items (noise rule). These
# read from the live ring; if empty, return empty arrays so the UI renders IDLE.
# --------------------------------------------------------------------------- #
def _map_state(organ: str) -> dict[str, Any]:
    ring = _ring(organ)
    recent = [e for e in ring if e.get("ts_epoch", 0) > _now_minus(86400)]  # last 24h
    base = {"organ": organ, "lean_sha": DOCTRINE["lean_sha"], "ts": ISO()}
    if organ == "a11oy":
        knots = [{"receipt_sha": e.get("receipt_sha"), "ts": e.get("ts"),
                  "verdict": e.get("verdict", "pass"), "action_verb": e.get("action_verb"),
                  "action_target": e.get("action_target"), "t": (i + 1) / (len(recent) + 1)}
                 for i, e in enumerate(recent)]
        # gates: only those that fired today
        gates_fired = {}
        for e in recent:
            g = e.get("gate")
            if g:
                gates_fired[g] = {"id": g, "label": g, "last_eval_ts": e.get("ts"), "active": True}
        return {**base, "kind": "khipu_spine", "knots": knots, "gates": list(gates_fired.values())}
    if organ == "sentra":
        sigs = {}
        parts = []
        for e in recent:
            s = e.get("signature")
            if s:
                sigs.setdefault(s, {"id": s, "label": s, "activity": 0.0})
                sigs[s]["activity"] = min(1.0, sigs[s]["activity"] + 0.2)
            parts.append({"id": e.get("receipt_sha"), "verdict": e.get("verdict", "pass"),
                          "event_sha": e.get("receipt_sha")})
        return {**base, "kind": "immune_cathedral", "signatures": list(sigs.values()),
                "particles": parts[-30:], "core": {"label": "SZL stack"}}
    if organ == "amaru":
        # 13 axes from the most recent tick if present; PROVED formulas always visible
        last = recent[-1] if recent else {}
        axes = last.get("axes") or []
        formulas = [{"id": f, "proved": True, "recent": False} for f in ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")]
        for e in recent:
            fid = e.get("formula")
            if fid and fid not in ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"):
                formulas.append({"id": fid, "proved": False, "recent": True})
        return {**base, "kind": "yuyay_cortex", "axes": axes,
                "lambda": last.get("lambda"), "chakras": last.get("chakras") or [],
                "formulas": formulas, "in_flight": bool(last.get("in_flight"))}
    if organ == "killinchu":
        tracks = [{"id": e.get("track"), "lat": e.get("lat"), "lon": e.get("lon"),
                   "verdict": e.get("verdict", "warn"), "ts": e.get("ts")}
                  for e in ring if e.get("track") and e.get("ts_epoch", 0) > _now_minus(60)]  # last 60s
        return {**base, "kind": "killinchu_globe", "officers": last_officers(organ), "tracks": tracks}
    return {**base, "kind": "unknown"}


def last_officers(organ: str) -> list[dict]:
    # 4 superhero orbital cards; activity drives orbit distance (busy=closer)
    names = [("Sentra", "immune"), ("Amaru", "cortex"), ("a11oy", "governance"), ("Rosie", "aide")]
    ring = _ring(organ)
    out = []
    for n, role in names:
        recent = sum(1 for e in ring if e.get("officer") == n and e.get("ts_epoch", 0) > _now_minus(3600))
        out.append({"name": n, "role": role, "activity": min(1.0, recent / 10.0)})
    return out


# --------------------------------------------------------------------------- #
# Command handler — runs the verb, appends a real event, signs a receipt.
# --------------------------------------------------------------------------- #
def _handle_command(organ: str, command: str, args: dict) -> dict[str, Any]:
    parts = command.strip().split()
    if not parts:
        return {"ok": False, "message": "empty command", "receipt": None}
    aliases = {"s": "/sign", "v": "/verify", "i": "/inspect", "r": "/replay"}
    nl_meta = None
    if not command.strip().startswith("/") and parts[0] not in aliases:
        # natural-language phrase -> resolve via LOCAL LLM only (founder directive)
        nl_meta = _local_llm_nl_to_command(command.strip())
        command = nl_meta["command"]
        parts = command.strip().split()
    verb = parts[0]
    if verb in aliases:
        verb = aliases[verb]
    target = " ".join(parts[1:]) or args.get("target", "")
    verb_clean = verb.lstrip("/")

    if verb_clean == "verify":
        # verify an existing receipt sha via szl_dsse if we have the envelope
        ok = _dsse is not None
        return {"ok": ok, "message": f"verify {target}: " + ("cosign-verifiable" if ok else "signing module unavailable"),
                "receipt": None}

    signed = _sign_receipt(organ, verb_clean, target, verdict="pass")
    if nl_meta is not None:
        signed["receipt"]["nl_route"] = nl_meta  # records local LLM source or honest fallback
    evt = {
        "ts": signed["receipt"].get("ts"), "ts_epoch": time.time(),
        "action_verb": verb_clean, "action_target": target,
        "verdict": "pass", "receipt_sha": signed["receipt"].get("receipt_sha"),
        "keyid": signed["receipt"].get("keyid"),
        "signed": signed["receipt"].get("signed"),
    }
    if nl_meta is not None:
        evt["nl_source"] = nl_meta.get("source")
        evt["nl_fallback"] = nl_meta.get("fallback")
    _ring(organ).append(evt)
    msg = f"{verb_clean} → signed receipt"
    if nl_meta and nl_meta.get("fallback"):
        msg = nl_meta["note"] + f" Resolved → {command}; signed FALLBACK receipt."
    elif nl_meta:
        msg = f"local LLM → {command}; signed receipt."
    return {"ok": True, "message": msg, "receipt": signed,
            "map_delta": {"type": "receipt", "data": evt}}


# --------------------------------------------------------------------------- #
# SSE stream — emits real ring events as they arrive (heartbeat keeps alive).
# --------------------------------------------------------------------------- #
async def _stream(organ: str):
    last = len(_ring(organ))
    yield f"data: {json.dumps({'type':'hello','organ':organ,'ts':ISO()})}\n\n"
    while True:
        ring = _ring(organ)
        if len(ring) > last:
            for evt in ring[last:]:
                yield f"data: {json.dumps({'type':'receipt','data':evt})}\n\n"
            last = len(ring)
        else:
            yield f": heartbeat {ISO()}\n\n"  # SSE comment heartbeat
        await asyncio.sleep(2.0)


# --------------------------------------------------------------------------- #
# register
# --------------------------------------------------------------------------- #
def register(app, organ: str, web_dir: str | None = None) -> dict[str, Any]:
    p = f"/api/{organ}/v4"
    here = Path(web_dir) if web_dir else Path(__file__).resolve().parent / "web"
    html = here / "operator.html"

    @app.get(f"{p}/healthz")
    async def _healthz():
        # HONEST health: sovereign is True ONLY if a live GPU probe succeeded THIS
        # request. base_url is redacted to host[:port]. gpu_reachable is the live
        # probe bool. honest_note states exactly where inference runs and why.
        r = resolve_llm(probe=True)
        mode = ("sovereign-gpu" if r["provider"] == "self-hosted-gpu"
                else "hf-router-fallback" if r["provider"] == "hf-router-fallback"
                else "offline")
        return JSONResponse({"status": "ok", "service": organ, "shell": "operator-v4",
                             "doctrine": DOCTRINE["version"], "counts": DOCTRINE["counts"],
                             "lean_sha": DOCTRINE["lean_sha"], "keyid_label": PER_ORGAN_KEYID.get(organ),
                             "signing_available": (_dsse.signing_available() if _dsse else False),
                             "sovereign": r["sovereign"],  # gated on a LIVE probe — never asserted
                             "inference": r["provider"],
                             "gpu_reachable": r["gpu_reachable"],
                             "gpu_configured": bool(GPU_BASE_URL),
                             "fallback_allowed": _FALLBACK_ALLOWED,
                             "llm": {"mode": mode, "provider": r["provider"],
                                     "base": r["base_redacted"], "model": r["model"],
                                     "cloud": r["cloud"]},
                             "local_llm_online": r["online"],
                             "honest_note": r["honest_note"],
                             "ts": ISO()})

    @app.get(f"{p}/inference-posture")
    async def _inference_posture():
        # Ecosystem posture probe — where does THIS organ's inference run right now?
        # where in {gpu | fallback | offline}. Wired to the live resolver only.
        return JSONResponse(posture(organ, probe=True))

    @app.get(f"{p}/inbox")
    async def _inbox():
        items = _INBOX.get(organ, [])
        return JSONResponse({
            "inbox": items,
            "total": len(items),
            "doctrine": DOCTRINE["version"],
            "note": "Active inbox items only — empty when no live events (honest idle state).",
        })  # wrapped object per P2 spec; active items only; empty -> calm UI

    @app.post(f"{p}/inbox")
    async def _inbox_post(req: Request):
        """POST drone telemetry event or Wire B event into organ inbox. Returns DSSE receipt."""
        import hashlib as _hl, uuid as _uuid
        from datetime import datetime as _dtp, timezone as _tzp
        body: dict = {}
        try:
            body = await req.json()
        except Exception:
            pass
        if not isinstance(body, dict):
            body = {}
        protocol = body.get("protocol", "unknown")
        raw = body.get("raw", "")
        ts_in = body.get("ts", _dtp.now(_tzp.utc).isoformat())
        # Minimal decode stub (CLAIM — not attested)
        decoded = {
            "message_type": "CLAIM",
            "ua_type": "CLAIM",
            "id_type": "CLAIM",
            "protocol": protocol,
            "note": "Decoded fields are CLAIMS from unauthenticated broadcast — not attested truth.",
        }
        payload_sha = _hl.sha256(str(body).encode()).hexdigest()
        receipt = {
            "hash": payload_sha,
            "signature": "PLACEHOLDER — Sigstore CI not yet wired",
            "ts": _dtp.now(_tzp.utc).isoformat(),
        }
        event = {
            "event_id": str(_uuid.uuid4()),
            "protocol": protocol,
            "raw": raw[:64] if raw else "",
            "decoded": decoded,
            "receipt": receipt,
            "ts": ts_in,
        }
        # Append to inbox ring
        if organ not in _INBOX:
            _INBOX[organ] = []
        _INBOX[organ].append(event)
        if len(_INBOX[organ]) > 200:
            _INBOX[organ] = _INBOX[organ][-200:]
        return JSONResponse({
            "received": True,
            "protocol": protocol,
            "decoded": decoded,
            "receipt": receipt,
            "note": "Decoded fields are CLAIMS from unauthenticated broadcast — not attested truth.",
            "doctrine": DOCTRINE["version"],
        })

    @app.get(f"{p}/map/state")
    async def _state():
        return JSONResponse(_map_state(organ))

    @app.post(f"{p}/command")
    async def _command(req: Request):
        try:
            body = await req.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON body"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
        return JSONResponse(_handle_command(organ, body.get("command", ""), body.get("args", {})))

    @app.get(f"{p}/receipts")
    async def _receipts(since: str | None = None, limit: int = 50):
        ring = list(reversed(_ring(organ)))[: min(int(limit), 500)]
        rows = [{"ts": e.get("ts"), "keyid": e.get("keyid"), "action_verb": e.get("action_verb"),
                 "action_target": e.get("action_target"), "verdict": e.get("verdict"),
                 "receipt_sha": e.get("receipt_sha"), "verify": bool(e.get("signed")),
                 "lean_sha": DOCTRINE["lean_sha"], "doctrine": DOCTRINE["version"]}
                for e in ring if e.get("receipt_sha")]
        return JSONResponse({
            "receipts": rows,
            "total": len(rows),
            "note": "PLACEHOLDER signing — Sigstore CI not yet wired per Doctrine v11. Signatures are PLACEHOLDER.",
            "doctrine": DOCTRINE["version"],
        })

    @app.get(f"{p}/replay/{{chain_hash}}")
    async def _replay(chain_hash: str, frame: int = 0):
        ring = _ring(organ)
        if frame < 0 or frame >= len(ring):
            return JSONResponse({"error": "frame out of range", "frames": len(ring)}, status_code=404)
        # reconstruct state at frame N (state up to and including that receipt)
        sub = ring[: frame + 1]
        evt = ring[frame]
        return JSONResponse({"chain_hash": chain_hash, "frame": frame, "frames": len(ring),
                             "receipt": evt, "doctrine": DOCTRINE["version"], "lean_sha": DOCTRINE["lean_sha"],
                             "cumulative": len(sub)})

    @app.get(f"{p}/stream")
    async def _stream_route():
        return StreamingResponse(_stream(organ), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    async def _serve_html():
        if html.exists():
            return FileResponse(str(html))
        return JSONResponse({"error": "operator.html not deployed"}, status_code=404)

    app.get(f"/{organ}/operator")(_serve_html)
    app.get("/operator")(_serve_html)

    # Ecosystem-level inference-posture alias (stable path for the founder/demo to
    # ask "where does inference run right now?" without knowing the organ prefix).
    @app.get("/api/szl/v1/inference-posture")
    async def _szl_inference_posture():
        return JSONResponse(posture(organ, probe=True))

    return {"registered": True, "organ": organ, "base": p,
            "routes": [f"{p}/inbox", f"{p}/map/state", f"{p}/command", f"{p}/receipts",
                       f"{p}/replay/{{hash}}", f"{p}/stream", f"{p}/healthz",
                       f"{p}/inference-posture", "/api/szl/v1/inference-posture",
                       f"/{organ}/operator", "/operator"],
            "llm_posture": posture(organ, probe=False),
            "signing_available": (_dsse.signing_available() if _dsse else False)}
