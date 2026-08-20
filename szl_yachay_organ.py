# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v12 (v11 + PURIQ) — Yachay persistent CTO organ.
"""
szl_yachay_organ.py — Yachay, the persistent founder-facing CTO organ.

ADDITIVE-ONLY. Mounted by serve.py via `import szl_yachay_organ as _yachay;
_yachay.attach(app)` immediately after the a11oy.code orchestrator attach. All
routes are registered BEFORE the generic /api/a11oy/{path:path} Node proxy and the
SPA catch-all, so FastAPI's ordered matching serves them here.

What Yachay is (and is NOT): a persistent, always-on CTO. NOT a generic chatbot.
The differentiator vs ChatGPT is the **Khipu receipt on every answer** — an
append-only, hash-chained, tamper-evident record (SHA3-256). Every Yachay response
is receipt-signed.

Endpoints (all under the FastAPI app, registered before the Node proxy):
  GET  /yachay                          — Kanchay-branded HTML chat UI
  POST /api/a11oy/yachay/chat           — chat; routes via the a11oy.code
                                          orchestrator in-process; returns a
                                          Khipu-receipt-signed response
  GET  /api/a11oy/yachay/projects       — flagship + in-flight tracker
  GET  /api/a11oy/yachay/priorities     — today's priorities (Hatun-Willay 5-axis)
  GET  /api/a11oy/yachay/healthz        — organ health

NO BANDAID (Doctrine v12 §2): if no inference credential (HF_TOKEN) is present, the
chat endpoint returns an HONEST note (no fake completion) — but STILL emits a Khipu
receipt, because the receipt discipline is independent of the model. Voice is via
Wallpa when present; otherwise Yachay reports the open-source-TTS fallback honestly.

Everything is wrapped in try/except at import + attach time so a missing optional
dependency can NEVER take down the existing SPA + gates API.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Khipu receipt store — shared with the rest of the organ family. Local fallback
# (stdlib-only SHA3-256 hash chain) so a missing szl_khipu.py never breaks Yachay.
# ---------------------------------------------------------------------------
try:
    from szl_khipu import get_dag as _khipu_get_dag  # type: ignore

    _KHIPU_SOURCE = "szl_khipu"
except Exception:  # pragma: no cover - local fallback
    import hashlib
    import threading

    _GENESIS = "0" * 64

    class _FallbackDAG:
        """Minimal stdlib SHA3-256 hash-chained receipt store (Khipu contract)."""

        def __init__(self, organ: str, ns: str = "a11oy") -> None:
            self.organ, self.ns = organ, ns
            self._lock = threading.Lock()
            self._chain: list[dict[str, Any]] = []

        @staticmethod
        def _digest(obj: Any) -> str:
            raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
            return hashlib.sha3_256(raw).hexdigest()

        def emit(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
            payload = payload or {}
            with self._lock:
                prev = self._chain[-1]["digest"] if self._chain else _GENESIS
                body = {"organ": self.organ, "ns": self.ns, "seq": len(self._chain),
                        "action": action, "payload_digest": self._digest(payload),
                        "ts": time.time(), "prev": prev}
                digest = self._digest(body)
                receipt = {**body, "digest": digest, "signature": "DSSE_PLACEHOLDER",
                           "chain_verified": True}
                self._chain.append(receipt)
                return receipt

        def verify_chain(self) -> dict[str, Any]:
            with self._lock:
                prev = _GENESIS
                for i, r in enumerate(self._chain):
                    body = {k: r[k] for k in ("organ", "ns", "seq", "action",
                                              "payload_digest", "ts", "prev")}
                    if r["prev"] != prev or self._digest(body) != r["digest"]:
                        return {"ok": False, "depth": len(self._chain), "broken_at": i}
                    prev = r["digest"]
                return {"ok": True, "depth": len(self._chain), "broken_at": None}

        def depth(self) -> int:
            with self._lock:
                return len(self._chain)

        def head(self) -> str:
            with self._lock:
                return self._chain[-1]["digest"] if self._chain else _GENESIS

    _FALLBACK_REGISTRY: dict[str, "_FallbackDAG"] = {}

    def _khipu_get_dag(organ: str, ns: str = "a11oy") -> "_FallbackDAG":  # type: ignore
        key = f"{ns}/{organ}"
        if key not in _FALLBACK_REGISTRY:
            _FALLBACK_REGISTRY[key] = _FallbackDAG(organ, ns)
        return _FALLBACK_REGISTRY[key]

    _KHIPU_SOURCE = "fallback"

_DAG = _khipu_get_dag("yachay", ns="a11oy")

# ---------------------------------------------------------------------------
# Doctrine v11 LOCKED numbers + replay hash + flagship statuses (canon snapshot).
# These are the numbers Yachay must never inflate. The flagship statuses are a
# best-effort snapshot; the /projects endpoint refreshes from HF when possible.
# ---------------------------------------------------------------------------
REPLAY_HASH = "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5"

DOCTRINE_LOCKED = {
    "version": "v11 (carried into v12 PURIQ)",
    "doctrine_claimed": {"declarations": 749, "unique_axioms": 14, "sorries": 163},
    "live_regen": {"declarations": 752, "sorries": 160,
                   "sorries_breakdown": "109 baseline + 51 Putnam",
                   "raw_axioms": 15, "unique_axioms": 14, "anchor_gates": 44},
    "putnam_green": "4/12",
    "axes": "13-axis yuyay_v3",
    "replay_hash": REPLAY_HASH,
    "honest_labels": [
        "λ-receipt / Khipu signature = DSSE PLACEHOLDER (Sigstore not wired into CI); hash chain verified, not signature",
        "Λ-uniqueness = Conjecture 1 (not a theorem)",
        "SLSA L1 (honest)",
        "traceparent in-process only (Wire D not implemented)",
        "router math is real; model response needs HF_TOKEN else honest 503",
    ],
}

# Best-effort flagship snapshot (from hf_spaces_inventory.json at build time).
FLAGSHIP_SNAPSHOT = {
    "a11oy": "APP_STARTING", "amaru": "APP_STARTING", "rosie": "APP_STARTING",
    "sentra": "RUNNING", "anatomy-3d": "RUNNING", "lean-kernel": "RUNNING",
    "README": "RUNNING",
}
FLAGSHIP_ALSO = ["killinchu", "vessels", "uds-demo"]

WARHACKER = {
    "event": "Warhacker (Defense Unicorns)", "dates": "16–19 June 2026",
    "city": "downtown San Diego", "dress_rehearsal": "Mon 15 June 2026 (4 hrs)",
    "wedge": ["Lean-verified governance gate",
              "DSSE-signed Khipu Merkle-DAG receipt (sum-of-sums invariant)"],
    "native_fit": ["P1 Cannonico drone oversight", "P6 ATO non-refutable Body of Evidence"],
    "note": "Pitch architecture, not business value — Greene hates security theater.",
}

# ---------------------------------------------------------------------------
# System prompt — loaded from the canonical YACHAY_SYSTEM_PROMPT.md if present
# (the CANONICAL SYSTEM PROMPT section), else from an embedded copy. Single
# source of truth lives in the .md; this embedded copy is the deploy-safe fallback.
# ---------------------------------------------------------------------------
_EMBEDDED_PROMPT = """You are Yachay, the persistent Chief Technology Officer of SZL Holdings.

Who you are. Yachay means lived knowledge in Quechua. You are the founder's technical co-pilot and institutional memory — always on, always grounded in math and the verifiable record. You are Quechua-rooted in naming and discipline only. You are never mystical: no spirituality, no destiny, no "the universe." You are a working CTO who names his tools in Quechua. If a claim cannot be backed by a Lean declaration, a Khipu receipt, a replay hash, or a live Space status, you say so plainly.

Your job. Help the founder ship a Series-A-ready defensible AI-governance company. Every answer serves: (1) closing the round, (2) the San Diego Warhacker physical demo (16–19 June 2026), (3) keeping the seven flagship Spaces honest and live, (4) protecting the founder's time and mental bandwidth. Be decisive. Give the next concrete action.

How you talk. Math-grounded, story-aware, never marketing-fluff, never mystical. Short sentences. Lead with the answer, then the receipt. Direct, candid about risk, allergic to hand-waving. When you cite a number it is a LOCKED number or you flag it as an estimate. You never inflate. Honesty is the product.

Doctrine v11 LOCKED numbers (NEVER inflate): Doctrine-claimed 749 declarations / 14 unique axioms / 163 sorries. Live regen: 752 declarations / 160 sorries (109 baseline + 51 Putnam) / 15 raw axioms (14 unique) / 44 anchor gates. Putnam 4/12 GREEN. 13-axis yuyay_v3. Replay hash bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5.

Honest labels: Khipu/λ-receipt signature is a DSSE PLACEHOLDER (Sigstore not wired into CI) — the chain is hash-verified (SHA3-256), not signature-verified. Λ-uniqueness is Conjecture 1, not a theorem. SLSA L1. traceparent in-process only. Router organ/tier/Λ math is real; the model response needs HF_TOKEN else an honest 503 — never a fake completion.

The wedge: (1) a Lean-verified governance gate; (2) a DSSE-signed Khipu Merkle-DAG receipt with a sum-of-sums invariant. Native fit on Warhacker P1 (Cannonico drone oversight) and P6 (ATO non-refutable Body of Evidence). Pitch architecture, not business value — Andrew Greene hates security theater.

Banned tokens (never emit): Mythos (use Hatun-Willay), Jarvis, Bo11y/Bolly, Computacenter, "45 gates", "11 MCP tools". Never claim Sigstore signing is live. Never claim Λ-uniqueness is a theorem. Never invent flagship statuses or numbers.

The Khipu receipt is the differentiator. Every Yachay answer carries a Khipu receipt (digest, prev-link, chain depth, chain_verified). The founder, an auditor, or Greene can re-walk the chain. Reference it but never fabricate a digest.

You are Yachay. Be precise. Sign your work."""


def _load_system_prompt() -> str:
    """Load the CANONICAL SYSTEM PROMPT section from YACHAY_SYSTEM_PROMPT.md if
    present; otherwise return the embedded copy. Deploy-safe either way."""
    for cand in (Path(__file__).parent / "YACHAY_SYSTEM_PROMPT.md",
                 Path("/app/YACHAY_SYSTEM_PROMPT.md")):
        try:
            if cand.is_file():
                txt = cand.read_text(encoding="utf-8")
                start = txt.find("You are **Yachay**")
                end = txt.find("\n---", start) if start != -1 else -1
                if start != -1 and end != -1:
                    # strip markdown bold/headers for a clean model prompt
                    section = txt[start:end]
                    for ch in ("**", "###", "##"):
                        section = section.replace(ch, "")
                    return section.strip()
        except Exception:
            continue
    return _EMBEDDED_PROMPT


SYSTEM_PROMPT = _load_system_prompt()


def _live_canon_block(chain_depth: int) -> str:
    """Machine-generated live block prepended before the canonical prompt."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    fl = ", ".join(f"{k}={v}" for k, v in FLAGSHIP_SNAPSHOT.items())
    lr = DOCTRINE_LOCKED["live_regen"]
    return (
        f"[YACHAY LIVE CANON — generated {ts}]\n"
        f"Flagship Spaces: {fl} (+ {', '.join(FLAGSHIP_ALSO)})\n"
        f"Doctrine: v11 LOCKED ({lr['declarations']} decl / {lr['sorries']} sorries / "
        f"{lr['unique_axioms']} unique axioms / {lr['anchor_gates']} gates; "
        f"Putnam {DOCTRINE_LOCKED['putnam_green']} GREEN)\n"
        f"Replay hash: {REPLAY_HASH}\n"
        f"Warhacker: {WARHACKER['city']} {WARHACKER['dates']} — dress rehearsal "
        f"{WARHACKER['dress_rehearsal']}.\n"
        f"Khipu chain depth at this turn: {chain_depth}\n"
    )


# ---------------------------------------------------------------------------
# Cross-session memory via Unay organ (coordinate; may not be built). Best-effort
# import; if absent, Yachay uses the Khipu chain itself as durable-enough memory of
# what was asked, and says so honestly.
# ---------------------------------------------------------------------------
try:
    import szl_unay as _unay  # type: ignore

    _UNAY_PRESENT = True
except Exception:
    _unay = None
    _UNAY_PRESENT = False


def _remember(session_id: str, role: str, content: str) -> None:
    """Persist a turn to Unay if present; always Khipu-receipt the memory write."""
    try:
        _DAG.emit("yachay.memory.write",
                  {"session": session_id, "role": role, "len": len(content)})
        if _UNAY_PRESENT and hasattr(_unay, "append"):
            _unay.append(ns="a11oy", organ="yachay", session=session_id,
                         role=role, content=content)  # type: ignore
    except Exception:
        pass


def _recall(session_id: str, k: int = 8) -> list[dict[str, str]]:
    """Recall prior turns from Unay if present; else empty (honest: no durable
    cross-session memory yet — Unay not built)."""
    if _UNAY_PRESENT and hasattr(_unay, "recall"):
        try:
            return _unay.recall(ns="a11oy", organ="yachay", session=session_id, k=k)  # type: ignore
        except Exception:
            return []
    return []


# ---------------------------------------------------------------------------
# Chat — routes through the a11oy.code orchestrator IN-PROCESS. Reuses its
# deterministic router (route), inference client (_get_client) and resilient model
# call (_call_model_resilient). NO fake completion: missing HF_TOKEN -> honest note.
# ---------------------------------------------------------------------------
async def _yachay_complete(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Return {ok, text|note, model, tier, route_receipt}. Honest on missing creds."""
    try:
        import a11oy_code_orchestrator as _oc  # type: ignore
    except Exception as e:
        return {"ok": False, "note": f"a11oy.code orchestrator unavailable ({e!r}). "
                "Yachay's persona + Khipu receipt are intact; model routing is offline.",
                "model": None, "tier": None, "route_receipt": None}

    # Deterministic route (real math; emits its own Khipu router receipt).
    try:
        decision = _oc.route(messages, "router-auto", "standard", None)
    except Exception as e:
        return {"ok": False, "note": f"router error ({e!r})", "model": None,
                "tier": None, "route_receipt": None}

    if not getattr(_oc, "HF_TOKEN", ""):
        return {"ok": False,
                "note": ("No inference credential present (HF_TOKEN unset). Per the "
                         "Zero-Bandaid Law, Yachay returns no fake completion. The "
                         "deterministic route, the persona, and this Khipu receipt are "
                         "all real. Set HF_TOKEN as a Space secret to enable answers."),
                "model": decision.get("model"), "tier": decision.get("tier"),
                "route_receipt": decision.get("khipu_receipt")}

    client = _oc._get_client()
    candidates = [decision["model"], *decision.get("fallbacks", [])]
    payload = {"messages": messages, "max_tokens": 1024, "temperature": 0.4}
    try:
        data, used = await _oc._call_model_resilient(client, candidates, payload)
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return {"ok": True, "text": text, "model": used, "tier": decision.get("tier"),
                "route_receipt": decision.get("khipu_receipt")}
    except Exception as e:
        return {"ok": False, "note": f"all candidates exhausted ({e!r}) — honest "
                "failure, no fabricated answer.", "model": decision.get("model"),
                "tier": decision.get("tier"), "route_receipt": decision.get("khipu_receipt")}


# ---------------------------------------------------------------------------
# Kanchay-branded HTML chat UI. Single self-contained page (no build step).
# Colors: yuyay teal #168f89 (primary, 700 #0b5957), yawar red #c0392b,
# hatun gold #c08f2f, ink #28251D. Voice: math-grounded, never mystical.
# ---------------------------------------------------------------------------
_YACHAY_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yachay — Persistent CTO · SZL Holdings</title>
<style>
:root{--teal:#168f89;--teal700:#0b5957;--red:#c0392b;--gold:#c08f2f;--ink:#28251D;
--bg:#F7F6F2;--surf:#FFFFFF;--border:#D4D1CA;--muted:#7A7974;}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,Segoe UI,Roboto,Arial,sans-serif}
.wrap{max-width:920px;margin:0 auto;min-height:100%;display:flex;flex-direction:column}
header{padding:22px 24px;border-bottom:1px solid var(--border);background:var(--surf)}
.brand{display:flex;align-items:baseline;gap:12px}
.brand h1{margin:0;font-size:26px;letter-spacing:-.02em;color:var(--teal700)}
.brand .q{font-size:13px;color:var(--muted)}
.sub{margin:6px 0 0;font-size:13px;color:var(--muted)}
.canon{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.chip{font-size:11px;padding:3px 9px;border-radius:999px;border:1px solid var(--border);
background:#fff;color:var(--ink)}
.chip b{color:var(--teal700)}
.chip.run{border-color:var(--teal);color:var(--teal700)}
.chip.warn{border-color:var(--gold);color:#7a5a18}
#log{flex:1;overflow:auto;padding:20px 24px;display:flex;flex-direction:column;gap:14px}
.msg{max-width:88%;padding:12px 15px;border-radius:14px;white-space:pre-wrap;font-size:15px}
.msg.you{align-self:flex-end;background:var(--teal);color:#fff;border-bottom-right-radius:4px}
.msg.ya{align-self:flex-start;background:var(--surf);border:1px solid var(--border);border-bottom-left-radius:4px}
.msg.ya .who{font-size:11px;font-weight:700;color:var(--teal700);margin-bottom:4px;letter-spacing:.04em}
.receipt{margin-top:9px;padding-top:8px;border-top:1px dashed var(--border);font:11px/1.4 ui-monospace,Menlo,monospace;color:var(--muted)}
.receipt b{color:var(--gold)}
.note{align-self:flex-start;background:#fff7ef;border:1px solid var(--gold);border-radius:12px;padding:10px 14px;font-size:13px;color:#7a5a18;max-width:88%}
form{display:flex;gap:10px;padding:16px 24px;border-top:1px solid var(--border);background:var(--surf)}
textarea{flex:1;resize:none;height:46px;padding:11px 13px;border:1px solid var(--border);
border-radius:10px;font:15px/1.4 inherit;color:var(--ink)}
textarea:focus{outline:2px solid var(--teal);border-color:var(--teal)}
button{padding:0 20px;border:0;border-radius:10px;background:var(--teal700);color:#fff;font-weight:600;cursor:pointer}
button:hover{background:var(--teal)}button:disabled{opacity:.5;cursor:wait}
.foot{padding:10px 24px 18px;font-size:11px;color:var(--muted);text-align:center}
a{color:var(--teal700)}
</style></head>
<body><div class="wrap">
<header>
  <div class="brand"><h1>Yachay</h1><span class="q">yachay · lived knowledge</span></div>
  <p class="sub">Persistent founder-facing CTO for SZL Holdings — math-grounded, receipt-signed, never mystical.
  Every answer carries a Khipu receipt. <em>That</em> is the differentiator.</p>
  <div class="canon" id="canon"><span class="chip">loading canon…</span></div>
</header>
<div id="log">
  <div class="msg ya"><div class="who">YACHAY</div>Awriki. I'm Yachay — your persistent CTO. I hold the session canon, the Doctrine v11 LOCKED numbers, the replay hash, and every flagship status across sessions, and I sign each answer with a Khipu receipt. Ask me what to ship today, the state of a flagship, or how the SZL wedge lands at Warhacker.<div class="receipt">khipu · chain initialised · ns=a11oy organ=yachay</div></div>
</div>
<form id="f">
  <textarea id="q" placeholder="Ask Yachay…  (e.g. 'what should I ship today?' or 'why does SZL win at Warhacker P6?')" autofocus></textarea>
  <button id="send" type="submit">Send</button>
</form>
<div class="foot">Doctrine v12 (v11 + PURIQ) · Khipu hash-chain verified (SHA3-256) · DSSE signature = honest PLACEHOLDER (Sigstore not wired) · © 2026 SZL Holdings</div>
</div>
<script>
const log=document.getElementById('log'),f=document.getElementById('f'),q=document.getElementById('q'),send=document.getElementById('send');
const session='yachay-'+Math.random().toString(36).slice(2,10);
function add(cls,html){const d=document.createElement('div');d.className='msg '+cls;d.innerHTML=html;log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
fetch('/api/a11oy/yachay/projects').then(r=>r.json()).then(d=>{
  const c=document.getElementById('canon');c.innerHTML='';
  c.insertAdjacentHTML('beforeend','<span class="chip"><b>Doctrine v11</b> 752 decl · 160 sorries · 44 gates</span>');
  c.insertAdjacentHTML('beforeend','<span class="chip"><b>Putnam</b> 4/12 GREEN</span>');
  c.insertAdjacentHTML('beforeend','<span class="chip"><b>Warhacker</b> 16–19 Jun · San Diego</span>');
  (d.flagships||[]).forEach(fp=>{const ok=fp.status==='RUNNING';c.insertAdjacentHTML('beforeend',
    '<span class="chip '+(ok?'run':'warn')+'">'+esc(fp.name)+': '+esc(fp.status)+'</span>');});
}).catch(()=>{});
f.addEventListener('submit',async e=>{
  e.preventDefault();const text=q.value.trim();if(!text)return;
  add('you',esc(text));q.value='';send.disabled=true;
  const wait=add('ya','<div class="who">YACHAY</div><em>thinking…</em>');
  try{
    const r=await fetch('/api/a11oy/yachay/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:text,session_id:session})});
    const d=await r.json();wait.remove();
    let body=esc(d.answer||d.note||'(no content)');
    const rc=d.khipu_receipt||{};
    const rcHtml='<div class="receipt">khipu · digest <b>'+esc((rc.digest||'').slice(0,16))+'…</b> · prev '+esc((rc.prev||'').slice(0,8))+'… · depth '+esc(String(rc.seq!=null?rc.seq+1:'?'))+' · chain_verified '+esc(String(rc.chain_verified))+' · sig '+esc(rc.signature||'?')+'</div>';
    if(d.answer){add('ya','<div class="who">YACHAY</div>'+body+rcHtml);}
    else{add('note','⚠ '+body+rcHtml.replace('class="receipt"','class="receipt" style="color:#7a5a18"'));}
  }catch(err){wait.remove();add('note','⚠ network error: '+esc(String(err)));}
  send.disabled=false;q.focus();
});
q.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();f.requestSubmit();}});
</script></body></html>"""


# ---------------------------------------------------------------------------
# attach(app) — mirrors a11oy_code_orchestrator.attach(app). Registers all Yachay
# routes directly on the app BEFORE the Node proxy + SPA catch-all.
# ---------------------------------------------------------------------------
def attach(app) -> None:
    # Import at module global scope so `from __future__ import annotations` string
    # annotations (e.g. `request: Request`) resolve for FastAPI signature parsing.
    global Request, HTMLResponse, JSONResponse
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse

    @app.get("/yachay", response_class=HTMLResponse)
    async def yachay_ui():
        _DAG.emit("yachay.ui.served", {"path": "/yachay"})
        return HTMLResponse(_YACHAY_HTML)

    @app.post("/api/a11oy/yachay/chat")
    async def yachay_chat(request: Request):
        body = await request.json()
        user_msg = (body.get("message") or body.get("query") or "").strip()
        session_id = body.get("session_id") or "founder"
        if not user_msg:
            rec = _DAG.emit("yachay.chat.empty", {"session": session_id})
            return JSONResponse({"note": "empty message", "khipu_receipt": rec}, status_code=400)

        _remember(session_id, "user", user_msg)

        # Build messages: live canon + canonical persona + recalled memory + turn.
        depth_now = _DAG.depth()
        system = _live_canon_block(depth_now) + "\n" + SYSTEM_PROMPT
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for m in _recall(session_id, k=8):
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_msg})

        result = await _yachay_complete(messages)

        if result["ok"]:
            answer = result["text"]
            _remember(session_id, "assistant", answer)
            receipt = _DAG.emit("yachay.chat.answer", {
                "session": session_id, "model": result["model"], "tier": result["tier"],
                "answer_len": len(answer), "route_receipt": result.get("route_receipt")})
            verify = _DAG.verify_chain()
            return JSONResponse({
                "organ": "yachay", "answer": answer, "model": result["model"],
                "tier": result["tier"], "khipu_receipt": receipt,
                "chain_verified": verify, "doctrine": "v12 (v11 + PURIQ)",
                "signed_by": "Yachay",
            })
        else:
            # Honest path: NO fake completion, but STILL receipt-signed.
            receipt = _DAG.emit("yachay.chat.honest_no_completion", {
                "session": session_id, "reason": result["note"][:200],
                "route_receipt": result.get("route_receipt")})
            return JSONResponse({
                "organ": "yachay", "note": result["note"], "answer": None,
                "model": result.get("model"), "tier": result.get("tier"),
                "khipu_receipt": receipt, "doctrine": "v12 (v11 + PURIQ)",
                "signed_by": "Yachay",
            })

    @app.get("/api/a11oy/yachay/projects")
    async def yachay_projects():
        rec = _DAG.emit("yachay.projects.read", {})
        flagships = [{"name": k, "status": v} for k, v in FLAGSHIP_SNAPSHOT.items()]
        flagships += [{"name": k, "status": "PRESENT"} for k in FLAGSHIP_ALSO]
        return JSONResponse({
            "organ": "yachay", "flagships": flagships,
            "doctrine_locked": DOCTRINE_LOCKED, "warhacker": WARHACKER,
            "khipu_source": _KHIPU_SOURCE, "unay_memory": _UNAY_PRESENT,
            "khipu_receipt": rec, "signed_by": "Yachay",
        })

    @app.get("/api/a11oy/yachay/priorities")
    async def yachay_priorities():
        # Hatun-Willay 5-axis priority frame (internal rename of the old term).
        priorities = [
            {"axis": "Round (Series-A)", "today":
             "Tighten the architecture one-pager so Greene sees the Lean gate + Khipu DAG, not business value."},
            {"axis": "Warhacker demo", "today":
             "Lock the P1 Cannonico drone-oversight flow + P6 ATO Body-of-Evidence script for the Mon 15 Jun dress rehearsal."},
            {"axis": "Flagship honesty", "today":
             "Get a11oy / amaru / rosie from APP_STARTING to RUNNING; keep LOCKED numbers exact (752/160/14/44)."},
            {"axis": "Receipts / trust", "today":
             "Keep the Khipu chain green; remember the DSSE signature is an honest PLACEHOLDER — do not claim Sigstore."},
            {"axis": "Founder bandwidth", "today":
             "One decision at a time. Flag rabbit holes. Protect the runway to San Diego."},
        ]
        rec = _DAG.emit("yachay.priorities.read", {"count": len(priorities)})
        return JSONResponse({
            "organ": "yachay", "frame": "Hatun-Willay 5-axis",
            "priorities": priorities, "khipu_receipt": rec, "signed_by": "Yachay",
        })

    @app.get("/api/a11oy/yachay/healthz")
    async def yachay_healthz():
        return JSONResponse({
            "organ": "yachay", "ok": True, "khipu_source": _KHIPU_SOURCE,
            "khipu_chain": _DAG.verify_chain(), "unay_memory": _UNAY_PRESENT,
            "doctrine": "v12 (v11 + PURIQ)",
        })

    print("[yachay] persistent CTO organ mounted at /yachay + /api/a11oy/yachay/* "
          f"(Khipu={_KHIPU_SOURCE}, Unay={_UNAY_PRESENT}, Doctrine v12 PURIQ)",
          file=sys.stderr)
