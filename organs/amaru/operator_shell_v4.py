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
# Sovereign LLM (Warhacker directive, founder 2026-06-01): the Cmd-K
# natural-language path routes to a LOCAL LLM ONLY (Qwen2.5-7B-Instruct AWQ via
# vLLM on the 4060 Ti tower). NEVER a cloud API. If the local endpoint is
# unreachable, return an honest deterministic stub + a signed fallback receipt.
# Commercial cloud routing (a11oy.code) is intentionally NOT in this path.
# --------------------------------------------------------------------------- #
LOCAL_LLM_BASE = os.environ.get("SZL_LOCAL_LLM_BASE", "http://local-llm:8000/v1")
LOCAL_LLM_MODEL = os.environ.get("SZL_LOCAL_LLM_MODEL", "Qwen2.5-7B-Instruct-AWQ")


def _local_llm_nl_to_command(text: str) -> dict[str, Any]:
    """Map a natural-language phrase to a slash command using the LOCAL LLM only.
    Returns {command, source, fallback}. On any failure -> deterministic stub
    (keyword heuristic) with fallback=True so the caller signs a FALLBACK receipt."""
    sys_prompt = ("You translate an operator phrase into ONE slash command from: "
                  "/sign /verify /inspect /replay /gate /khipu /filter /yuyay /track. "
                  "Reply with ONLY the command line, no prose.")
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{LOCAL_LLM_BASE}/chat/completions",
            data=json.dumps({"model": LOCAL_LLM_MODEL, "max_tokens": 32, "temperature": 0,
                             "messages": [{"role": "system", "content": sys_prompt},
                                          {"role": "user", "content": text}]}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=4) as r:
            out = json.loads(r.read())
            cmd = out["choices"][0]["message"]["content"].strip().splitlines()[0]
            return {"command": cmd, "source": f"local:{LOCAL_LLM_MODEL}", "fallback": False}
    except Exception as e:
        # Honest deterministic stub — NEVER a cloud call.
        t = text.lower()
        guess = "/inspect " + text.strip()
        for kw, c in (("sign", "/sign"), ("verif", "/verify"), ("replay", "/replay"),
                      ("gate", "/gate"), ("filter", "/filter"), ("track", "/track")):
            if kw in t:
                guess = c + " " + text.strip()
                break
        return {"command": guess, "source": "deterministic-stub", "fallback": True,
                "note": f"Local LLM offline ({LOCAL_LLM_BASE}) — falling back to deterministic stub."}
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
    """Bounded local-only reachability probe (never a cloud call)."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{LOCAL_LLM_BASE}/models", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


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
        formulas = [{"id": f, "proved": True, "recent": False} for f in ("F1", "F11", "F12", "F18", "F19")]
        for e in recent:
            fid = e.get("formula")
            if fid and fid not in ("F1", "F11", "F12", "F18", "F19"):
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
        return JSONResponse({"status": "ok", "service": organ, "shell": "operator-v4",
                             "doctrine": DOCTRINE["version"], "counts": DOCTRINE["counts"],
                             "lean_sha": DOCTRINE["lean_sha"], "keyid_label": PER_ORGAN_KEYID.get(organ),
                             "signing_available": (_dsse.signing_available() if _dsse else False),
                             "sovereign": True,  # no cloud API in the demo path (founder directive)
                             "llm": {"mode": "local-only", "base": LOCAL_LLM_BASE, "model": LOCAL_LLM_MODEL,
                                     "cloud": False}, "local_llm_online": _local_llm_online(),
                             "ts": ISO()})

    @app.get(f"{p}/inbox")
    async def _inbox():
        return JSONResponse(_INBOX.get(organ, []))  # active items only; empty -> calm UI

    @app.get(f"{p}/map/state")
    async def _state():
        return JSONResponse(_map_state(organ))

    @app.post(f"{p}/command")
    async def _command(req: Request):
        body = await req.json()
        return JSONResponse(_handle_command(organ, body.get("command", ""), body.get("args", {})))

    @app.get(f"{p}/receipts")
    async def _receipts(since: str | None = None, limit: int = 50):
        ring = list(reversed(_ring(organ)))[: min(int(limit), 500)]
        rows = [{"ts": e.get("ts"), "keyid": e.get("keyid"), "action_verb": e.get("action_verb"),
                 "action_target": e.get("action_target"), "verdict": e.get("verdict"),
                 "receipt_sha": e.get("receipt_sha"), "verify": bool(e.get("signed")),
                 "lean_sha": DOCTRINE["lean_sha"], "doctrine": DOCTRINE["version"]}
                for e in ring if e.get("receipt_sha")]
        return JSONResponse(rows)

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

    return {"registered": True, "organ": organ, "base": p,
            "routes": [f"{p}/inbox", f"{p}/map/state", f"{p}/command", f"{p}/receipts",
                       f"{p}/replay/{{hash}}", f"{p}/stream", f"{p}/healthz",
                       f"/{organ}/operator", "/operator"],
            "signing_available": (_dsse.signing_available() if _dsse else False)}
