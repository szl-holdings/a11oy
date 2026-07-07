# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Author: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
# Change-class: ADDITIVE — Doctrine v11 LOCKED 749/14/163 UNCHANGED.
"""
szl_bridge — the Cross-Harness Receipt Bridge.

    "Bring your own harness. We sign the truth."

Hermes Agent (Nous Research, ChatML <tool_call> envelope) and OpenClaw
(SOUL.md + tool events) users point at this bridge and gain a signed Khipu
receipt chain for free — without changing their harness code.

Endpoints (all ADDITIVE; registered BEFORE the SPA catch-all + Node proxy):
    POST /api/a11oy/v4/bridge/hermes      — Hermes <tool_call> JSON (+ optional
                                            <think> block + outcome) -> receipt
    POST /api/a11oy/v4/bridge/openclaw    — SOUL.md hash + tool event + outcome
    GET  /api/a11oy/v4/bridge/receipt/{id}— public retrieval (NO auth by design)
    GET  /bridge                          — HTML landing page + curl examples

Every tool call is SCHEMA-STRICT (szl_bridge_schemas): a call whose name is
unknown or whose arguments fail validation FAILS-CLOSED with a
``kind:"schema_mismatch"`` Khipu receipt (Sentra deny-by-default).

Hybrid reasoning receipts: when a request carries a ``<think>`` block we sign
TWO receipts —
    kind:"deliberation" — hash(user_prompt) + reasoning_text + DSSE signature
                          (auditors verify the reasoning chain WITHOUT user data)
    kind:"action"       — the actual tool call / response (may be private)

Receipts are appended to the public, hash-chained Khipu ledger
(szl_receipt_substrate) and DSSE-signed via szl_dsse (real ECDSA-P256 cosign
when SZL_COSIGN_PRIVATE_PEM is present in the Space; honest UNSIGNED otherwise).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

# ── Live Space modules (graceful import so unit tests / partial envs still load).
try:  # public hash-chained ledger (same chain served by /api/a11oy/v1/ledger/{id})
    import szl_receipt_substrate as _ledger
except Exception:  # noqa: BLE001
    _ledger = None

# POC (szl-substrate extraction): prefer the shared package as the single source
# of truth; fall back to the local vendored copy so nothing breaks if the package
# is not installed in this runtime. See szl-holdings/szl-substrate MIGRATION.md.
try:  # real ECDSA-P256 DSSE signer
    from szl_substrate import szl_dsse as _dsse  # single source of truth
except Exception:  # noqa: BLE001
    try:
        import szl_dsse as _dsse  # fall back to local vendored copy
    except Exception:  # noqa: BLE001
        _dsse = None

import szl_bridge_schemas as _schemas

DOCTRINE_V = "11"
DOCTRINE_LOCKED = "749/14/163"
LUTAR_ANCHOR = "lutar-lean:749/14/163@bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5"
# Neuro citation — the Hickok conduction-aphasia wedge (forward-model grounding).
NEURO_CITATION = (
    "Hickok G. (2012) Computational neuroanatomy of speech production. "
    "Nat Rev Neurosci 13(2):135-145. doi:10.1038/nrn3158"
)
PUBLIC_BASE = "https://szlholdings-a11oy.hf.space"

_IM_BLOCK_RE = re.compile(
    r"<\|im_start\|>(?P<role>\w[\w-]*)\s*\n(?P<body>.*?)<\|im_end\|>",
    re.DOTALL,
)
_THINK_RE = re.compile(r"<think>(?P<t>.*?)</think>", re.DOTALL)
_TOOLCALL_RE = re.compile(r"<tool_call>\s*(?P<j>\{.*?\})\s*</tool_call>", re.DOTALL)


# ═══════════════════════════════════════════════════════════════════════════
# Receipt minting — append to the public Khipu chain + DSSE-sign.
# ═══════════════════════════════════════════════════════════════════════════

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _dsse_sign(payload: dict[str, Any]) -> dict[str, Any]:
    if _dsse is not None:
        try:
            return _dsse.sign_payload(payload, _dsse.KHIPU_PAYLOAD_TYPE)
        except Exception as e:  # noqa: BLE001
            return {"_error": f"DSSE sign failed: {type(e).__name__}: {e}", "signatures": []}
    # Honest UNSIGNED fallback.
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    import base64
    return {
        "payloadType": "application/vnd.szl.khipu+json",
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [],
        "_dsse": "DSSEv1",
        "_unsigned": True,
        "_note": "szl_dsse unavailable; receipt is UNSIGNED (honest).",
        "_payload_sha256": hashlib.sha256(body).hexdigest(),
    }


def mint_receipt(kind: str, actor_id: str, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Append a hash-chained Khipu receipt to the public ledger and DSSE-sign it.

    Returns {receipt_id, signed_url, doctrine_v, lutar_anchor, neuro_citation,
             kind, dsse, signed, chain}.
    """
    full_payload = {
        "kind": kind,
        "doctrine_v": DOCTRINE_V,
        "doctrine_locked": DOCTRINE_LOCKED,
        "lutar_anchor": LUTAR_ANCHOR,
        "ts_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **payload,
    }
    # Append to the public hash-chained ledger (real SHA3-256 chain).
    if _ledger is not None:
        rec = _ledger.append_receipt(actor_id, tool_name, full_payload)
        receipt_id = rec["receipt_id"]
        chain_link = {
            "sequence": rec["sequence"],
            "merkle_root": rec["merkle_root"],
            "prev_receipt_hash": rec["prev_receipt_hash"],
            "payload_hash": rec["payload_hash"],
        }
    else:  # fallback: deterministic id from payload (no shared chain available)
        receipt_id = "or-" + _sha256(json.dumps(full_payload, sort_keys=True))[:20]
        chain_link = {"note": "ledger module unavailable; id derived from payload hash"}

    dsse = _dsse_sign(full_payload)
    signed = bool(dsse.get("signatures"))
    return {
        "receipt_id": receipt_id,
        "signed_url": f"{PUBLIC_BASE}/api/a11oy/v4/bridge/receipt/{receipt_id}",
        "doctrine_v": DOCTRINE_V,
        "lutar_anchor": LUTAR_ANCHOR,
        "neuro_citation": NEURO_CITATION,
        "kind": kind,
        "dsse": dsse,
        "signed": signed,
        "chain": chain_link,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ChatML envelope parsing (Hermes format).
# ═══════════════════════════════════════════════════════════════════════════

def parse_chatml(text: str) -> dict[str, Any]:
    """Parse a Hermes ChatML transcript into structured turns + extracted
    <think> blocks + <tool_call> JSON objects from the assistant turn(s)."""
    turns: list[dict[str, str]] = []
    for m in _IM_BLOCK_RE.finditer(text or ""):
        turns.append({"role": m.group("role"), "content": m.group("body").strip()})
    think_blocks: list[str] = [t.strip() for t in _THINK_RE.findall(text or "")]
    tool_calls: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    for m in _TOOLCALL_RE.finditer(text or ""):
        raw = m.group("j")
        try:
            tool_calls.append(json.loads(raw))
        except Exception as e:  # noqa: BLE001
            parse_errors.append(f"invalid <tool_call> JSON: {type(e).__name__}: {e}")
    return {
        "turns": turns,
        "think_blocks": think_blocks,
        "tool_calls": tool_calls,
        "parse_errors": parse_errors,
    }


def build_chatml(system: str, user: str, think: str, tool_call: dict[str, Any]) -> str:
    """Render a Hermes ChatML transcript with a <think> + <tool_call> assistant turn."""
    tc = json.dumps(tool_call, separators=(",", ":"))
    parts = []
    if system:
        parts.append(f"<|im_start|>system\n{system}\n<|im_end|>")
    if user:
        parts.append(f"<|im_start|>user\n{user}\n<|im_end|>")
    assistant = "<|im_start|>assistant\n"
    if think:
        assistant += f"<think>{think}</think>\n"
    assistant += f"<tool_call>{tc}</tool_call>\n<|im_end|>"
    parts.append(assistant)
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# Hybrid reasoning receipts — sign deliberation SEPARATELY from action.
# ═══════════════════════════════════════════════════════════════════════════

def sign_hybrid(
    actor_id: str,
    user_prompt: str | None,
    reasoning_text: str | None,
    action_tool: str,
    action_payload: dict[str, Any],
) -> dict[str, Any]:
    """When a <think> block is present, mint TWO separately-signed receipts:

      * kind:"deliberation" — hash(user_prompt) + reasoning_text + DSSE sig.
        Contains NO raw user data beyond the reasoning text the agent emitted,
        so auditors can verify the reasoning chain without the user's prompt.
      * kind:"action"       — the actual tool call / response (may be private).

    Returns {action: <receipt>, deliberation: <receipt>|None}.
    """
    deliberation = None
    if reasoning_text and reasoning_text.strip():
        deliberation = mint_receipt(
            kind="deliberation",
            actor_id=actor_id,
            tool_name="bridge.deliberation",
            payload={
                "user_prompt_sha256": _sha256(user_prompt or ""),
                "reasoning_text": reasoning_text.strip(),
                "reasoning_sha256": _sha256(reasoning_text.strip()),
                "privacy": "deliberation contains hash(user_prompt) + reasoning only; "
                           "no raw user data — publishable to a transparency log.",
            },
        )
    action = mint_receipt(
        kind="action",
        actor_id=actor_id,
        tool_name=action_tool,
        payload={
            **action_payload,
            **({"deliberation_receipt_id": deliberation["receipt_id"]} if deliberation else {}),
        },
    )
    return {"action": action, "deliberation": deliberation}


# ═══════════════════════════════════════════════════════════════════════════
# Schema-strict gate — fails-CLOSED with a schema_mismatch receipt.
# ═══════════════════════════════════════════════════════════════════════════

def enforce_schema(actor_id: str, name: str, arguments: Any, harness: str) -> dict[str, Any] | None:
    """Validate (name, arguments). On failure mint a schema_mismatch receipt and
    return it (caller must reject with HTTP 422). On success return None."""
    verdict = _schemas.validate_tool_call(name, arguments)
    if verdict["valid"]:
        return None
    return mint_receipt(
        kind="schema_mismatch",
        actor_id=actor_id,
        tool_name=f"bridge.{harness}.schema_mismatch",
        payload={
            "harness": harness,
            "tool_name": name,
            "decision": "deny",
            "fail_mode": "fail-closed",
            "schema_errors": verdict["errors"],
            "schema_dialect": verdict["dialect"],
            "registered_tools": _schemas.registered_tools(),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI router.
# ═══════════════════════════════════════════════════════════════════════════

router = APIRouter()


@router.post("/api/a11oy/v4/bridge/hermes")
async def bridge_hermes(request: Request) -> JSONResponse:
    """Accept a Hermes tool-call JSON (+ optional <think> + outcome).

    Body may be either:
      * {"name": "...", "arguments": {...}, "think": "...", "outcome": {...}}
      * {"chatml": "<|im_start|>...<tool_call>{...}</tool_call>..."}  (full ChatML)
    """
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be a JSON object"}, status_code=400)

    actor_id = str(body.get("actor_id") or "hermes-agent")
    think = body.get("think")
    user_prompt = body.get("user_prompt") or body.get("prompt")
    outcome = body.get("outcome")

    # Path 1: full ChatML transcript supplied.
    if isinstance(body.get("chatml"), str):
        parsed = parse_chatml(body["chatml"])
        if parsed["parse_errors"]:
            rec = mint_receipt("schema_mismatch", actor_id, "bridge.hermes.chatml_parse",
                               {"harness": "hermes", "decision": "deny",
                                "fail_mode": "fail-closed", "errors": parsed["parse_errors"]})
            return JSONResponse({"error": "chatml parse failed", "schema_mismatch": True,
                                 **{k: rec[k] for k in ("receipt_id", "signed_url")}},
                                status_code=422)
        if not parsed["tool_calls"]:
            return JSONResponse({"error": "no <tool_call> found in chatml"}, status_code=400)
        tc = parsed["tool_calls"][0]
        if think is None and parsed["think_blocks"]:
            think = "\n".join(parsed["think_blocks"])
        if user_prompt is None:
            user_prompt = next((t["content"] for t in parsed["turns"] if t["role"] == "user"), None)
    else:
        # Path 2: a single tool-call object.
        tc = body.get("tool_call") if isinstance(body.get("tool_call"), dict) else body

    name = tc.get("name")
    arguments = tc.get("arguments", {})
    if not isinstance(name, str):
        return JSONResponse({"error": "tool call missing string 'name'"}, status_code=400)

    # Schema-strict — fail-CLOSED.
    mismatch = enforce_schema(actor_id, name, arguments, "hermes")
    if mismatch is not None:
        return JSONResponse(
            {"error": "schema_mismatch", "schema_mismatch": True,
             "tool_name": name, "receipt_id": mismatch["receipt_id"],
             "signed_url": mismatch["signed_url"], "doctrine_v": DOCTRINE_V,
             "lutar_anchor": LUTAR_ANCHOR, "neuro_citation": NEURO_CITATION,
             },
            status_code=422,
        )

    hybrid = sign_hybrid(
        actor_id=actor_id,
        user_prompt=user_prompt,
        reasoning_text=think if isinstance(think, str) else None,
        action_tool=f"hermes.{name}",
        action_payload={"harness": "hermes", "tool_name": name, "arguments": arguments,
                        "outcome": outcome},
    )
    action = hybrid["action"]
    resp = {
        "receipt_id": action["receipt_id"],
        "signed_url": action["signed_url"],
        "doctrine_v": DOCTRINE_V,
        "lutar_anchor": LUTAR_ANCHOR,
        "neuro_citation": NEURO_CITATION,
        "kind": "action",
        "signed": action["signed"],
    }
    if hybrid["deliberation"] is not None:
        resp["deliberation_receipt_id"] = hybrid["deliberation"]["receipt_id"]
        resp["deliberation_signed_url"] = hybrid["deliberation"]["signed_url"]
    return JSONResponse(resp)


@router.post("/api/a11oy/v4/bridge/openclaw")
async def bridge_openclaw(request: Request) -> JSONResponse:
    """Accept an OpenClaw event: SOUL.md hash + tool event + outcome.

    Body: {"soul_hash": "...", "event": {"name": "...", "arguments": {...}},
           "think": "...", "outcome": {...}, "agent_id": "..."}
    """
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be a JSON object"}, status_code=400)

    soul_hash = body.get("soul_hash")
    if not isinstance(soul_hash, str) or not soul_hash:
        return JSONResponse({"error": "field 'soul_hash' (string) is required"}, status_code=400)
    event = body.get("event")
    if not isinstance(event, dict):
        return JSONResponse({"error": "field 'event' (object) is required"}, status_code=400)

    actor_id = str(body.get("agent_id") or "openclaw-agent")
    think = body.get("think")
    user_prompt = body.get("user_prompt") or body.get("prompt")
    outcome = body.get("outcome")

    name = event.get("name")
    arguments = event.get("arguments", {})
    # OpenClaw events may carry a bare event with no tool name -> channel_ingress.
    if not isinstance(name, str) or not name:
        rec = mint_receipt(
            kind="channel_ingress",
            actor_id=actor_id,
            tool_name="openclaw.event",
            payload={"harness": "openclaw", "soul_hash": soul_hash,
                     "event": event, "outcome": outcome},
        )
        return JSONResponse({
            "receipt_id": rec["receipt_id"], "signed_url": rec["signed_url"],
            "doctrine_v": DOCTRINE_V, "lutar_anchor": LUTAR_ANCHOR,
            "neuro_citation": NEURO_CITATION, "kind": "channel_ingress",
            "signed": rec["signed"],
        })

    # Named tool event -> schema-strict, fail-CLOSED.
    mismatch = enforce_schema(actor_id, name, arguments, "openclaw")
    if mismatch is not None:
        return JSONResponse(
            {"error": "schema_mismatch", "schema_mismatch": True, "tool_name": name,
             "receipt_id": mismatch["receipt_id"], "signed_url": mismatch["signed_url"],
             "doctrine_v": DOCTRINE_V, "lutar_anchor": LUTAR_ANCHOR,
             "neuro_citation": NEURO_CITATION},
            status_code=422,
        )

    hybrid = sign_hybrid(
        actor_id=actor_id,
        user_prompt=user_prompt,
        reasoning_text=think if isinstance(think, str) else None,
        action_tool=f"openclaw.{name}",
        action_payload={"harness": "openclaw", "soul_hash": soul_hash,
                        "tool_name": name, "arguments": arguments, "outcome": outcome},
    )
    action = hybrid["action"]
    resp = {
        "receipt_id": action["receipt_id"],
        "signed_url": action["signed_url"],
        "doctrine_v": DOCTRINE_V,
        "lutar_anchor": LUTAR_ANCHOR,
        "neuro_citation": NEURO_CITATION,
        "kind": "action",
        "signed": action["signed"],
    }
    if hybrid["deliberation"] is not None:
        resp["deliberation_receipt_id"] = hybrid["deliberation"]["receipt_id"]
        resp["deliberation_signed_url"] = hybrid["deliberation"]["signed_url"]
    return JSONResponse(resp)


@router.get("/api/a11oy/v4/bridge/receipt/{receipt_id}")
async def bridge_receipt(receipt_id: str) -> JSONResponse:
    """Public receipt retrieval — NO auth (receipts are public by design)."""
    if _ledger is None:
        return JSONResponse({"error": "ledger module unavailable"}, status_code=503)
    with _ledger._LEDGER_LOCK:  # noqa: SLF001 — shared in-process chain
        chain = list(_ledger._LEDGER)
    for r in chain:
        if r["receipt_id"] == receipt_id or r["merkle_root"] == receipt_id:
            return JSONResponse({
                "receipt": r,
                "public": True,
                "doctrine_v": DOCTRINE_V,
                "lutar_anchor": LUTAR_ANCHOR,
                "neuro_citation": NEURO_CITATION,
                "verify_hint": "POST /api/a11oy/v1/verify with {ledger:[...]} to check the chain.",
            })
    return JSONResponse({"error": "receipt not found", "receipt_id": receipt_id}, status_code=404)


_BRIDGE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>a11oy — Cross-Harness Receipt Bridge</title>
<style>
  :root{--bg:#0b0d10;--fg:#e6edf3;--mut:#9aa7b2;--acc:#7ee787;--card:#11151a;--bd:#222b34}
  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
    font:16px/1.6 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial}
  .wrap{max-width:900px;margin:0 auto;padding:48px 20px 80px}
  h1{font-size:2.2rem;margin:0 0 6px}.tag{color:var(--acc);font-weight:600}
  .sub{color:var(--mut);font-size:1.05rem;margin:0 0 28px}
  .card{background:var(--card);border:1px solid var(--bd);border-radius:12px;
    padding:20px 22px;margin:18px 0}
  h2{font-size:1.2rem;margin:0 0 10px}code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  pre{background:#06080a;border:1px solid var(--bd);border-radius:8px;padding:14px 16px;
    overflow-x:auto;font-size:13.5px;color:#cdd9e5}
  .pill{display:inline-block;background:#0d2818;color:var(--acc);border:1px solid #1c4a30;
    border-radius:999px;padding:2px 10px;font-size:12px;margin:2px 4px 2px 0}
  a{color:var(--acc)}.foot{color:var(--mut);font-size:13px;margin-top:30px}
  ul{margin:6px 0 0 0;padding-left:20px;color:var(--mut)}li{margin:3px 0}
</style></head><body><div class="wrap">
<h1>Cross-Harness Receipt Bridge</h1>
<p class="sub"><span class="tag">Bring your own harness. We sign the truth.</span></p>
<p>Point your <b>Hermes Agent</b> (Nous Research) or <b>OpenClaw</b> agent at this
bridge and every tool call gains a tamper-evident, DSSE-signed Khipu receipt on a
public hash-chained ledger — without changing your harness code. Schema-strict:
every tool call validates against a registered JSON&nbsp;Schema&nbsp;2020-12 schema
or the request <b>fails-CLOSED</b> with a <code>schema_mismatch</code> receipt.</p>
<p>
<span class="pill">Doctrine v11 LOCKED 749/14/163</span>
<span class="pill">DSSE / cosign ECDSA-P256</span>
<span class="pill">JSON Schema 2020-12</span>
<span class="pill">hybrid reasoning receipts</span>
</p>

<div class="card"><h2>Hermes (ChatML &lt;tool_call&gt;)</h2>
<pre>curl -X POST __BASE__/api/a11oy/v4/bridge/hermes \\
  -H 'content-type: application/json' \\
  -d '{"name":"search","arguments":{"q":"test"},
       "think":"User wants a web search; pick the search tool.",
       "outcome":{"status":"ok","hits":3}}'</pre>
<p style="color:var(--mut);font-size:14px">Returns
<code>{receipt_id, signed_url, doctrine_v:"11", lutar_anchor, neuro_citation}</code>.
A <code>&lt;think&gt;</code> block mints a separately-signed
<code>kind:"deliberation"</code> receipt so auditors can verify the reasoning
chain without seeing user data. Full ChatML transcripts accepted via
<code>{"chatml":"&lt;|im_start|&gt;...&lt;/tool_call&gt;..."}</code>.</p></div>

<div class="card"><h2>OpenClaw (SOUL.md + tool event)</h2>
<pre>curl -X POST __BASE__/api/a11oy/v4/bridge/openclaw \\
  -H 'content-type: application/json' \\
  -d '{"soul_hash":"abc123",
       "event":{"name":"write_file","arguments":{"path":"/tmp/x","content":"hi"}},
       "outcome":{"status":"ok"}}'</pre></div>

<div class="card"><h2>Retrieve a receipt (public, no auth)</h2>
<pre>curl __BASE__/api/a11oy/v4/bridge/receipt/&lt;receipt_id&gt;</pre></div>

<div class="card"><h2>Registered tool schemas</h2>
<ul>__TOOLS__</ul>
<p style="color:var(--mut);font-size:14px">Any other tool name, or arguments that
violate the schema (<code>additionalProperties:false</code>, required fields,
types, bounds), fails-CLOSED.</p></div>

<p class="foot">Hermes Function Calling:
<a href="https://github.com/nousresearch/hermes-agent">nousresearch/hermes-agent</a> ·
<a href="https://huggingface.co/datasets/NousResearch/hermes-function-calling-v1">hermes-function-calling-v1</a> ·
OpenClaw: <a href="https://github.com/openclaw/openclaw">openclaw/openclaw</a> ·
Λ-anchor: <a href="https://github.com/szl-holdings/lutar-lean">lutar-lean 749/14/163</a> ·
neuro-grounding: Hickok (2012) <a href="https://doi.org/10.1038/nrn3158">doi:10.1038/nrn3158</a>.
Λ is Conjecture 1 (NOT a theorem; 163 sorries). SZL Holdings · Apache-2.0.</p>
</div></body></html>"""


@router.get("/bridge")
async def bridge_page() -> HTMLResponse:
    tools_li = "".join(
        f"<li><code>{name}</code> — {_schemas.get_schema(name).get('description','')}</li>"
        for name in _schemas.registered_tools()
    )
    html = _BRIDGE_HTML.replace("__BASE__", PUBLIC_BASE).replace("__TOOLS__", tools_li)
    return HTMLResponse(html)


def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Attach the Cross-Harness Receipt Bridge router. ADDITIVE — registered
    BEFORE the SPA catch-all + generic Node proxy so /bridge and
    /api/a11oy/v4/bridge/* resolve LOCALLY. Touches no existing route."""
    app.include_router(router)
    return (
        "a11oy.v4.bridge mounted: POST /api/a11oy/v4/bridge/{hermes,openclaw}, "
        "GET /api/a11oy/v4/bridge/receipt/{id}, GET /bridge "
        f"(schemas={len(_schemas.registered_tools())}, doctrine=v{DOCTRINE_V} {DOCTRINE_LOCKED})"
    )


def attach(app: FastAPI) -> str:
    return register(app, ns="a11oy")
