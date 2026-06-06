# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v10/v11
#
# lean_wire.py — ADDITIVE H-backplane wiring to SZLHOLDINGS/lean-kernel.
#
# Registers two surfaces on the host FastAPI app (a11oy or rosie):
#   POST|GET /api/<ns>/v1/lean-verify  — forwards a Λ-receipt to the live
#                                        lean-kernel /api/lean/verify endpoint.
#   GET      /lean                     — HTML page that renders the live
#                                        theorem table fetched from lean-kernel.
#
# ZERO BANDAID: if the kernel is unreachable the proxy returns the upstream
# error verbatim (502/503), and /lean shows an honest "kernel unreachable"
# banner rather than faking a green table.

from __future__ import annotations

import json

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

LEAN_KERNEL_BASE = "https://szlholdings-lean-kernel.hf.space"


def register(app: FastAPI, ns: str = "a11oy") -> None:
    """Attach lean-verify proxy + /lean theorem page to `app`.

    Must be called BEFORE any /api/<ns>/{path:path} catch-all and before the
    SPA /{full_path:path} fallback so these explicit routes win.
    """

    verify_path = f"/api/{ns}/v1/lean-verify"

    async def _forward_verify(request: Request) -> JSONResponse:
        url = f"{LEAN_KERNEL_BASE}/api/lean/verify"
        try:
            if request.method == "POST":
                payload = await request.body()
            else:
                # GET convenience: ?axes=0.5,0.5,...&lambda=0.5
                qp = dict(request.query_params)
                axes = qp.get("axes", "")
                values = [float(x) for x in axes.split(",") if x.strip() != ""]
                body = {"axes": values}
                if "lambda" in qp:
                    body["lambda"] = float(qp["lambda"])
                payload = json.dumps(body).encode()
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url, content=payload,
                    headers={"content-type": "application/json"},
                )
            try:
                data = resp.json()
            except Exception:
                data = {"upstream_status": resp.status_code,
                        "upstream_text": resp.text[:500]}
            data["_proxied_via"] = f"{ns}{verify_path}"
            data["_kernel"] = LEAN_KERNEL_BASE
            return JSONResponse(data, status_code=resp.status_code)
        except httpx.ConnectError:
            return JSONResponse(
                {"error": "lean-kernel unreachable", "kernel": LEAN_KERNEL_BASE},
                status_code=503,
            )
        except Exception as exc:
            return JSONResponse(
                {"error": str(exc), "kernel": LEAN_KERNEL_BASE}, status_code=502
            )

    app.add_api_route(
        verify_path, _forward_verify, methods=["GET", "POST"],
        name=f"{ns}_lean_verify",
    )

    async def _lean_page() -> HTMLResponse:
        return HTMLResponse(_LEAN_HTML.replace("__KERNEL__", LEAN_KERNEL_BASE)
                            .replace("__NS__", ns))

    app.add_api_route("/lean", _lean_page, methods=["GET"], name=f"{ns}_lean_page")


_LEAN_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lean Kernel — Live Theorem Table</title>
<style>
:root{--bg:#0b0e14;--fg:#e6edf3;--mut:#8b949e;--ok:#3fb950;--ax:#d29922;--sr:#f85149;--card:#11161f;--bd:#222b38}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
header{padding:24px 28px;border-bottom:1px solid var(--bd)}
h1{margin:0 0 4px;font-size:20px}.sub{color:var(--mut);font-size:13px}
.wrap{padding:20px 28px;max-width:1100px;margin:0 auto}
.stats{display:flex;gap:14px;flex-wrap:wrap;margin:16px 0}
.stat{background:var(--card);border:1px solid var(--bd);border-radius:8px;padding:10px 16px}
.stat b{font-size:22px;display:block}
.stat span{color:var(--mut);font-size:12px}
table{width:100%;border-collapse:collapse;margin-top:14px;font-size:13px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--bd)}
th{color:var(--mut);position:sticky;top:0;background:var(--bg)}
.PROVEN{color:var(--ok)}.AXIOM{color:var(--ax)}.SORRY{color:var(--sr)}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;border:1px solid currentColor}
.err{background:#2d1416;border:1px solid var(--sr);color:#ffb4ad;padding:12px 16px;border-radius:8px;margin:14px 0}
.note{color:var(--mut);font-size:12px;margin-top:10px}
input,button{font:inherit}
a{color:#58a6ff}
.filter{margin:10px 0}.filter input{background:var(--card);border:1px solid var(--bd);color:var(--fg);padding:6px 10px;border-radius:6px;width:240px}
</style></head>
<body>
<header>
  <h1>🔏 Lean Kernel — Live Theorem Table</h1>
  <div class="sub">Embedded live from <a href="__KERNEL__" target="_blank">SZLHOLDINGS/lean-kernel</a> ·
  Lutar Invariant Λ · Lean v4.13.0 + Mathlib · Doctrine v10/v11 · proxied via <code>__NS__</code></div>
</header>
<div class="wrap">
  <div id="status">Loading live data from the lean kernel…</div>
  <div class="stats" id="stats"></div>
  <div class="filter"><input id="q" placeholder="filter by name / file…" oninput="render()"></div>
  <div id="tablewrap"></div>
  <div class="note">Build status: <span id="build">?</span> ·
    <a href="__KERNEL__/api/lean/theorems" target="_blank">raw JSON</a> ·
    <a href="__KERNEL__/api/lean/healthz" target="_blank">healthz</a></div>
</div>
<script>
const K="__KERNEL__";let ITEMS=[];
async function load(){
  try{
    const h=await fetch(K+"/api/lean/healthz").then(r=>r.json()).catch(()=>null);
    if(h){document.getElementById("build").textContent=(h.build&&h.build.status||"unknown")+" @ "+(h.repo_sha||"").slice(0,8)+" ("+(h.toolchain||"")+")";}
    const t=await fetch(K+"/api/lean/theorems").then(r=>r.json());
    if(t.error){throw new Error(t.error);}
    ITEMS=t.items||[];
    const s=t.summary||{};
    document.getElementById("status").textContent="";
    document.getElementById("stats").innerHTML=
      stat(s.total_declarations,"declarations")+stat(s.theorems_and_lemmas,"theorems+lemmas")+
      stat(s.proven,"PROVEN","PROVEN")+stat(s.axiom,"AXIOM","AXIOM")+stat(s.sorry,"SORRY","SORRY");
    render();
  }catch(e){
    document.getElementById("status").innerHTML='<div class="err">Lean kernel unreachable or building: '+e.message+
      '. This page does NOT fake a green table — it reports the honest state. Try again once the Space finishes building.</div>';
  }
}
function stat(n,l,c){return '<div class="stat"><b class="'+(c||'')+'">'+(n??'?')+'</b><span>'+l+'</span></div>';}
function render(){
  const q=(document.getElementById("q").value||"").toLowerCase();
  const rows=ITEMS.filter(i=>!q||(i.name+" "+i.file).toLowerCase().includes(q));
  let h='<table><thead><tr><th>#</th><th>Name</th><th>Kind</th><th>Status</th><th>File:Line</th></tr></thead><tbody>';
  rows.forEach((i,n)=>{h+='<tr><td>'+(n+1)+'</td><td>'+esc(i.name)+'</td><td>'+esc(i.kind)+
    '</td><td><span class="badge '+i.status+'">'+i.status+'</span></td><td>'+esc(i.file)+':'+i.line+'</td></tr>';});
  h+='</tbody></table>';
  document.getElementById("tablewrap").innerHTML=h+'<div class="note">'+rows.length+' rows</div>';
}
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
load();
</script>
</body></html>"""
