"""a11oy_ayllu.py — register the ayllu (ingested-and-reborn tribe) on the a11oy app.

Follows a11oy's module convention: expose `register(app, ns="a11oy") -> str`, mounted
by serve.py inside a try/except guard so a11oy boots unaffected if anything here fails.
Receipts use `szl_dsse` when present, else an honest UNSIGNED DSSE envelope (never a
fabricated signature) — the same pattern as a11oy_v4_agent.

Routes:
  GET  /api/{ns}/v1/ayllu/roster   — the a11oy-native persona roster
  POST /api/{ns}/v1/ayllu/ask      — one persona, bounded + honest + receipted
  POST /api/{ns}/v1/ayllu/council  — bounded multi-persona deliberation
  GET  /api/{ns}/v1/ayllu/lounge   — recent collaboration feed
  GET  /ayllu                      — honest human-readable page
"""
from __future__ import annotations

import base64
import hashlib
import json
import uuid
from typing import Any, Dict

try:
    import szl_dsse as _dsse  # type: ignore
except Exception:  # pragma: no cover
    _dsse = None  # honest UNSIGNED fallback

from ayllu import __version__ as _AYLLU_VERSION
from ayllu.lounge import Lounge
from ayllu.loop import run_turn
from ayllu.personas import ROSTER, get_persona

__version__ = _AYLLU_VERSION

# One process-wide lounge (in-memory, honest source labels).
_LOUNGE = Lounge()


def _make_receipt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap payload in a DSSE envelope (honest UNSIGNED if no cosign key)."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if _dsse is not None:
        try:
            return _dsse.sign(payload)
        except Exception:
            pass
    return {
        "payloadType": "application/vnd.szl.receipt+json",
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [],
        "signed": False,
        "honesty": "UNSIGNED — szl_dsse not present; no signature fabricated.",
    }


def _page_html(ns: str) -> str:
    rows = "".join(
        f"<tr><td><b>{p.name}</b></td><td>{p.quechua}</td>"
        f"<td>{p.archetype}</td><td>{p.domain}</td></tr>"
        for p in ROSTER
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ayllu — a11oy agent community</title>
<style>
:root{{--void:#080c14;--teal:#3af4c8;--fg:#dfe7ee;--dim:#7f93a6}}
body{{margin:0;background:var(--void);color:var(--fg);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:900px;margin:0 auto;padding:40px 22px}}
h1{{color:var(--teal);margin:0 0 4px;font-size:26px}}
.sub{{color:var(--dim);margin:0 0 26px}}
table{{width:100%;border-collapse:collapse;margin:18px 0}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #16202c}}
th{{color:var(--teal);font-weight:600}}
.law{{background:#0d1520;border:1px solid #16202c;border-left:3px solid var(--teal);
padding:12px 14px;border-radius:6px;color:var(--dim);margin-top:22px}}
code{{color:var(--teal)}}
</style></head><body><main>
<h1>Ayllu</h1>
<p class="sub">The AlloyScape tribe, ingested and reborn as a11oy's own agent
community — {len(ROSTER)} personas, one guarded loop. v{__version__}</p>
<table><thead><tr><th>Persona</th><th>Quechua</th><th>Archetype</th>
<th>a11oy domain</th></tr></thead><tbody>{rows}</tbody></table>
<div class="law"><b>Bounded-autonomy law.</b> Every persona runs under a11oy's
fail-closed Λ-gate. State-changing actions require two-person attestation. The tribe's
"fully agentic, no sandbox" mandate is deliberately <b>not</b> adopted. No model backend
is wired here yet, so <code>ask</code>/<code>council</code> return the persona, the
selected model tier, and the bounded wiring — never a fabricated answer.<br><br>
API: <code>/api/{ns}/v1/ayllu/roster</code> ·
<code>/api/{ns}/v1/ayllu/ask</code> ·
<code>/api/{ns}/v1/ayllu/council</code> ·
<code>/api/{ns}/v1/ayllu/lounge</code></div>
</main></body></html>"""


def register(app, ns: str = "a11oy") -> str:
    """Mount the ayllu routes on `app`. Returns a status string."""
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse

    async def _roster(request: "Request") -> "JSONResponse":
        return JSONResponse({
            "count": len(ROSTER),
            "namespace": ns,
            "personas": [p.metadata() for p in ROSTER],
            "law": "a11oy bounded-autonomy (fail-closed Λ-gate); the tribe's unbounded "
                   "'always execute' mandate is NOT adopted",
            "provenance": "ingested from the AlloyScape tribe design; see ayllu/INGEST.md",
            "version": __version__,
        })

    async def _ask(request: "Request") -> "JSONResponse":
        try:
            body = await request.json()
        except Exception as e:
            return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
        name = (body or {}).get("persona")
        prompt = (body or {}).get("prompt")
        if not name or not prompt:
            return JSONResponse({"error": "'persona' and 'prompt' are required"},
                                status_code=422)
        p = get_persona(name)
        if p is None:
            return JSONResponse(
                {"error": f"unknown persona '{name}'",
                 "known": [x.name for x in ROSTER]}, status_code=404)
        difficulty = body.get("difficulty")
        turn = await run_turn(
            p, prompt,
            difficulty=None if difficulty is None else float(difficulty),
        )
        ask_id = str(uuid.uuid4())
        receipt = _make_receipt({
            "ask_id": ask_id,
            "persona": p.name,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "tier": turn.get("tier", {}).get("route"),
            "honesty": turn.get("honesty"),
        })
        _LOUNGE.post(
            p.name, turn.get("answer") or turn.get("honesty"),
            source=("brain" if turn.get("answer") is not None else "persona-fallback"))
        return JSONResponse({"ask_id": ask_id, "turn": turn, "receipt": receipt})

    async def _council(request: "Request") -> "JSONResponse":
        try:
            body = await request.json()
        except Exception as e:
            return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
        prompt = (body or {}).get("prompt")
        names = (body or {}).get("personas") or [p.name for p in ROSTER]
        if not prompt:
            return JSONResponse({"error": "'prompt' is required"}, status_code=422)
        personas = [get_persona(n) for n in names]
        personas = [p for p in personas if p is not None]
        if not personas:
            return JSONResponse(
                {"error": "no known personas in request",
                 "known": [x.name for x in ROSTER]}, status_code=422)
        result = await _LOUNGE.deliberate(prompt, personas)
        council_id = str(uuid.uuid4())
        receipt = _make_receipt({
            "council_id": council_id,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "participants": result["participants"],
        })
        return JSONResponse({"council_id": council_id, "result": result,
                             "receipt": receipt})

    async def _lounge_feed(request: "Request") -> "JSONResponse":
        return JSONResponse({"count": len(_LOUNGE.feed),
                             "recent": _LOUNGE.recent(50)})

    async def _page(request: "Request") -> "HTMLResponse":
        return HTMLResponse(_page_html(ns))

    app.add_api_route(f"/api/{ns}/v1/ayllu/roster", _roster, methods=["GET"],
                      tags=["ayllu"],
                      summary="a11oy-native agent roster (ingested from the tribe)")
    app.add_api_route(f"/api/{ns}/v1/ayllu/ask", _ask, methods=["POST"],
                      tags=["ayllu"],
                      summary="Ask one persona — bounded, honest, receipted")
    app.add_api_route(f"/api/{ns}/v1/ayllu/council", _council, methods=["POST"],
                      tags=["ayllu"],
                      summary="Bounded multi-persona deliberation")
    app.add_api_route(f"/api/{ns}/v1/ayllu/lounge", _lounge_feed, methods=["GET"],
                      tags=["ayllu"], summary="Recent collaboration lounge feed")
    app.add_api_route("/ayllu", _page, methods=["GET"], include_in_schema=False)

    return (
        f"ok — ayllu registered: {len(ROSTER)} personas; bounded-autonomy Λ-gate; "
        f"/ayllu + /api/{ns}/v1/ayllu/roster|ask|council|lounge; version={__version__}"
    )
