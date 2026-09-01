#!/usr/bin/env python3
"""Thin Hugging Face Space adapter for an A11oy Decision Assurance vertical.

Product logic lives in szl-holdings/a11oy/verticals/. This image evaluates
frozen demonstration cases through the Decision Integrity Kernel. Formulas
have authority NONE. Models and market signals never authorize.

Stdlib HTTP server plus the pinned shared SZL substrate. Listens on PORT.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import a11oy_kernel as kernel  # noqa: E402
from szl_space_brain import anatomy, substrate_status  # noqa: E402

SPACE_ID = os.environ.get("SPACE_ID", "SZLHOLDINGS/unknown")
VERTICAL_ID = os.environ.get("VERTICAL_ID", "unknown")
PORT = int(os.environ.get("PORT", "7860"))
GIT_SHA = os.environ.get("SZL_GIT_SHA") or os.environ.get("A11OY_GIT_SHA") or "UNKNOWN"
STATUS = "ROADMAP"

POLICY = json.loads((HERE / "policy_bundle.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((HERE / "vertical_manifest.json").read_text(encoding="utf-8"))
CASES = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))


def build_info() -> dict:
    brain = substrate_status()
    return {
        "schema": "szl.space-adapter-build-info/v8",
        "space_id": SPACE_ID,
        "vertical_id": VERTICAL_ID,
        "kernel_version": kernel.VERSION,
        "kernel_schema": kernel.SCHEMA,
        "formula_authority": "NONE",
        "locked_proven_count": brain["locked_proven_count"],
        "lambda": "Conjecture 1 OPEN",
        "second_brain": "LIVE" if not brain["missing"] else "DEGRADED",
        "status": STATUS,
        "visibility": "private",
        "source_sha": GIT_SHA,
        "canonical_source": f"szl-holdings/a11oy/verticals/{VERTICAL_ID}",
        "adapter": f"szl-holdings/a11oy/huggingface/spaces/{Path(SPACE_ID).name}",
        "limitations": [
            "Demonstration kernel. Does not prove production readiness.",
            "Formulas do not grant authority.",
            "This Space is initially private. Do not claim RUNNING until Hub readback.",
        ],
    }


def html_page() -> bytes:
    cases_js = json.dumps(CASES, ensure_ascii=False)
    title = MANIFEST.get("display_name", VERTICAL_ID)
    wedge = MANIFEST.get("wedge", "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title} — Decision Assurance</title>
<style>
  :root {{ color-scheme: dark; --bg:#050607; --panel:#0d1014; --ink:#f3f3ef; --mute:#929aa4; --line:#252b33; --deny:#c7c9cd; --ok:#f3f3ef; --wait:#aeb3ba; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: ui-sans-serif, system-ui, sans-serif; background:radial-gradient(circle at 50% 0%,#15191f 0,#050607 42%); color:var(--ink); }}
  main {{ max-width: 1080px; margin: 0 auto; padding: clamp(24px,5vw,64px) 18px 72px; }}
  .hero {{ position:relative; overflow:hidden; border:1px solid var(--line); background:rgba(13,16,20,.82); padding:clamp(22px,5vw,54px); margin-bottom:22px; }}
  .hero:after {{ content:""; position:absolute; width:360px; height:360px; border:1px solid #353b44; border-radius:50%; right:-120px; top:-170px; box-shadow:0 0 80px rgba(255,255,255,.06), inset 0 0 60px rgba(255,255,255,.03); }}
  h1 {{ font-size:clamp(1.7rem,4.5vw,3.4rem); letter-spacing:-.045em; margin:8px 0; max-width:15ch; }}
  p {{ color:var(--mute); line-height:1.55; max-width:72ch; }}
  .row {{ display:flex; flex-wrap:wrap; gap:8px; margin:16px 0 22px; }}
  button {{ min-height:44px; cursor:pointer; background:#11161c; color:var(--ink); border:1px solid var(--line); border-radius:999px; padding:8px 14px; }}
  button:hover, button:focus-visible {{ border-color:#f3f3ef; outline:2px solid transparent; }}
  pre {{ background:var(--panel); border:1px solid var(--line); padding:16px; overflow:auto; white-space:pre-wrap; word-break:break-word; }}
  .chip {{ display:inline-block; font-size:12px; padding:4px 9px; border-radius:999px; border:1px solid var(--line); color:var(--mute); margin:0 6px 6px 0; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr)); gap:12px; margin:18px 0; }}
  .card {{ min-width:0; border:1px solid var(--line); background:rgba(13,16,20,.75); padding:15px; }}
  .card b {{ display:block; margin-bottom:6px; }}
  @media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior:auto!important; animation:none!important; transition:none!important; }} }}
</style>
</head>
<body>
<main>
  <section class="hero">
    <div class="chip">{SPACE_ID}</div><div class="chip">kernel {kernel.VERSION}</div><div class="chip">formula authority NONE</div><div class="chip">{STATUS}</div>
    <h1>{title}</h1><p>{wedge}</p>
    <p>Governed decision assurance with a six-organ second-brain runtime. Real observations are labelled MEASURED; unavailable data stays UNAVAILABLE. The locked proof set is eight formulas and Lambda remains Conjecture 1.</p>
  </section>
  <div class="grid">
    <div class="card"><b>Second brain</b><span class="chip">/api/second-brain</span><p>Brain · Heart · Circulatory · Nervous · Skeleton · Immune.</p></div>
    <div class="card"><b>Formula substrate</b><span class="chip">/api/formulas</span><p>Pinned shared SZL substrate. Formula authority remains NONE for this adapter.</p></div>
    <div class="card"><b>Truth contract</b><span class="chip">MEASURED</span><span class="chip">REPORTED</span><span class="chip">MODELED</span><span class="chip">UNAVAILABLE</span></div>
  </div>
  <p>Evaluate a frozen demonstration case. The kernel is fail-closed. Models, formulas and market signals never authorize. This adapter does not own product logic.</p>
  <div class="row" id="cases"></div><div id="status"></div><pre id="out">Select a frozen case.</pre>
</main>
<script>
const CASES = {cases_js}; const root=document.getElementById('cases'); const out=document.getElementById('out'); const status=document.getElementById('status');
for (const item of CASES) {{ const b=document.createElement('button'); b.textContent=item.eval_id+' · '+item.expected_state; b.addEventListener('click',()=>run(item)); root.appendChild(b); }}
async function run(item) {{ out.textContent='Evaluating '+item.eval_id+'…'; const res=await fetch('/api/evaluate',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify(item.payload)}}); const data=await res.json(); const state=data.state||'UNKNOWN'; status.innerHTML='<span class="chip">'+state+'</span><span class="chip">'+(data.reason_codes||[]).join(', ')+'</span><span class="chip">digest '+((data.receipt&&data.receipt.digest)||'').slice(0,12)+'</span>'; out.textContent=JSON.stringify(data,null,2); }}
</script>
</body>
</html>
""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "a11oy-packet8-adapter/8.1.0"
    def log_message(self, fmt: str, *args) -> None: sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))
    def _send(self, code:int, body:bytes, content_type:str)->None:
        self.send_response(code); self.send_header("content-type",content_type); self.send_header("content-length",str(len(body))); self.send_header("cache-control","no-store"); self.end_headers(); self.wfile.write(body)
    def _json(self, code:int, obj)->None: self._send(code,json.dumps(obj,indent=2,sort_keys=True).encode("utf-8")+b"\n","application/json; charset=utf-8")
    def _read_json(self):
        length=int(self.headers.get("content-length") or "0")
        if length<=0 or length>1_000_000: return None
        raw=self.rfile.read(length)
        try: return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError): return None
    def do_GET(self)->None:
        path=urlparse(self.path).path
        if path in {"/","/index.html"}: self._send(200,html_page(),"text/html; charset=utf-8"); return
        if path in {"/api/livez","/healthz","/health"}:
            brain=substrate_status(); self._json(200,{"ok":not brain["missing"],"status":STATUS,"space_id":SPACE_ID,"second_brain":"LIVE" if not brain["missing"] else "DEGRADED","locked_proven_count":8,"lambda":"Conjecture 1 OPEN"}); return
        if path=="/api/second-brain": self._json(200,anatomy(SPACE_ID)); return
        if path=="/api/formulas": self._json(200,substrate_status()); return
        if path=="/api/build-info": self._json(200,build_info()); return
        if path=="/api/policy": self._json(200,POLICY); return
        if path=="/api/manifest": self._json(200,MANIFEST); return
        if path=="/api/cases": self._json(200,CASES); return
        self._json(404,{"error":"not found","path":path})
    def do_POST(self)->None:
        path=urlparse(self.path).path; payload=self._read_json()
        if payload is None: self._json(400,{"error":"expected JSON body"}); return
        if path=="/api/evaluate": self._json(200,kernel.evaluate(payload)); return
        if path=="/api/scan": self._json(200,kernel.scan_memo(str(payload.get("text") or ""))); return
        if path=="/api/replay": self._json(200,kernel.replay_receipt(payload if isinstance(payload,dict) else {})); return
        self._json(404,{"error":"not found","path":path})


def main()->int:
    server=ThreadingHTTPServer(("0.0.0.0",PORT),Handler); sys.stderr.write("packet8 adapter %s vertical=%s kernel=%s port=%s status=%s\n"%(SPACE_ID,VERTICAL_ID,kernel.VERSION,PORT,STATUS)); server.serve_forever(); return 0

if __name__=="__main__": raise SystemExit(main())
