#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish six source-bound, domain-native SZLHOLDINGS flagship Spaces.

V4 keeps one small governed runtime contract while rendering a deliberately
separate information architecture for every vertical.  It never copies vendor
UI or proprietary code.  Each surface is an original SZL implementation built
from public category patterns and the estate's own truth/provenance doctrine.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

ORG = "SZLHOLDINGS"
A11OY = "https://szlholdings-a11oy.hf.space"
KILLINCHU = "https://szlholdings-killinchu.hf.space"
PUBLIC_EXPERIENCE_VERSION = "4.0.0"
PUBLIC_EXPERIENCE_MARKER = 'data-szl-domain-experience-v4="true"'
DEPLOYMENT_SOURCE_REPOSITORY = "szl-holdings/a11oy"
USER_AGENT = "SZLHOLDINGS-Vertical-Publisher/4.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TERRA_FORGE_BUNDLE = REPOSITORY_ROOT / "deployments" / "vertical-forge" / "terra"
TERRA_FORGE_MARKER = 'data-szl-vertical-forge="0.2.1"'
TERRA_FORGE_SOURCE_REPOSITORY = "szl-holdings/szl-vertical-forge"
TERRA_FORGE_GENERATOR = "szl-vertical-forge/0.2.1"

FLAGSHIPS: tuple[dict[str, Any], ...] = (
    {
        "slug": "terra",
        "title": "Terra",
        "vertical": "REAL ESTATE INTELLIGENCE",
        "short": "Parcel-to-portfolio real estate decision intelligence",
        "source": "https://github.com/szl-holdings/szl-real-estate",
        "upstream": f"{A11OY}/api/a11oy/v1/vert/realestate/feed",
        "workflow": ("DISCOVER", "OWNERSHIP", "UNDERWRITE", "APPROVE", "TRACK"),
        "lens": "parcel",
        "labels": ("Asset map", "Ownership graph", "Underwriting queue"),
    },
    {
        "slug": "sentra",
        "title": "Sentra",
        "vertical": "CYBERSECURITY INTELLIGENCE",
        "short": "Evidence-first cyber attack-path and response intelligence",
        "source": "https://github.com/szl-holdings/szl-defensive-control-plane",
        "upstream": f"{A11OY}/api/a11oy/v1/vert/cyber/feed",
        "workflow": ("DETECT", "CORRELATE", "CONTAIN", "VERIFY", "RECEIPT"),
        "lens": "attack",
        "labels": ("Entity graph", "Attack paths", "Response queue"),
    },
    {
        "slug": "counsel",
        "title": "PRISM Counsel",
        "vertical": "LEGAL MATTER INTELLIGENCE",
        "short": "Matter workspace for research, drafting, and verification",
        "source": "https://github.com/szl-holdings/a11oy/tree/main/verticals/counsel",
        "upstream": f"{A11OY}/api/a11oy/v1/vert/legal/feed",
        "workflow": ("INTAKE", "RESEARCH", "ANALYZE", "DRAFT", "VERIFY"),
        "lens": "matter",
        "labels": ("Matter file", "Authority rail", "Work-product queue"),
    },
    {
        "slug": "finance",
        "title": "PURIQ Finance",
        "vertical": "FINANCIAL INTELLIGENCE",
        "short": "Provenance-first financial signal and decision console",
        "source": "https://github.com/szl-holdings/puriq-live",
        "upstream": f"{A11OY}/api/a11oy/v1/vert/finance/feed",
        "workflow": ("INGEST", "PRICE", "STRESS", "DECIDE", "AUDIT"),
        "lens": "market",
        "labels": ("Decision tape", "Exposure matrix", "Evidence ledger"),
    },
    {
        "slug": "vessels",
        "title": "Vessels",
        "vertical": "MARITIME INTELLIGENCE",
        "short": "Fleet route, risk, and voyage intelligence with receipts",
        "source": "https://github.com/szl-holdings/a11oy/tree/main/verticals/vessels",
        "upstream": f"{KILLINCHU}/api/killinchu/v1/maritime/risk/fleet",
        "workflow": ("TRACK", "SCREEN", "ROUTE", "ECONOMICS", "VERIFY"),
        "lens": "fleet",
        "labels": ("Fleet chart", "Voyage lanes", "Risk watch"),
    },
    {
        "slug": "lyte",
        "title": "Lyte",
        "vertical": "BUSINESS OBSERVABILITY",
        "short": "Service, trace, incident, and agent observability command",
        "source": "https://github.com/szl-holdings/lyte-lattice",
        "upstream": f"{A11OY}/api/a11oy/v1/observability/summary",
        "workflow": ("OBSERVE", "TRACE", "DIAGNOSE", "ACT", "VERIFY"),
        "lens": "trace",
        "labels": ("Service graph", "Trace timeline", "Action queue"),
    },
)

APP = r'''import hashlib,json,time,urllib.request
from pathlib import Path
import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
CFG=json.loads(Path("config.json").read_text(encoding="utf-8"))
INDEX=Path("index.html").read_text(encoding="utf-8")
PANELS=Path("panels.html").read_text(encoding="utf-8")
app=FastAPI(title=CFG["title"]+" - SZL Holdings")

def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def local_integrity():
    checks={
        "landing_sha256":sha256_text(INDEX)==CFG["landing_sha256"],
        "panels_sha256":sha256_text(PANELS)==CFG["panels_sha256"],
    }
    ready=all(checks.values())
    return {"schema":"szl.vertical-shell-readiness/v1","ready":ready,"state":"MEASURED" if ready else "INVALID","checks":checks,"routes":{"landing":"/","panels":"/panels","live":"/api/live","receipt":"/build-receipt.json"}}

def probe():
    started=time.time()
    try:
        r=httpx.get(CFG["upstream"],timeout=15,headers={"User-Agent":"SZLHOLDINGS-Flagship/4.0"})
        body=r.json() if "json" in r.headers.get("content-type","") else {"text":r.text[:4000]}
        return {"status":"LIVE" if r.is_success else "UNAVAILABLE","http_status":r.status_code,"latency_ms":round((time.time()-started)*1000,1),"source":CFG["upstream"],"data":body}
    except Exception as exc:
        return {"status":"UNAVAILABLE","error":type(exc).__name__,"source":CFG["upstream"],"data":None}

def hf_revision():
    try:
        req=urllib.request.Request("https://huggingface.co/api/spaces/"+CFG["hf_repository"],headers={"Accept":"application/json","User-Agent":"SZLHOLDINGS-BuildInfo/1.0"})
        with urllib.request.urlopen(req,timeout=10) as response:
            payload=json.loads(response.read().decode("utf-8"))
        value=str(payload.get("sha") or "").lower()
        return value if len(value)==40 else "UNAVAILABLE"
    except Exception:
        return "UNAVAILABLE"

@app.get("/healthz")
def healthz():
    return {"ok":True,"product":CFG["title"],"source":CFG["product_source"],"public_experience":CFG["public_experience"],"domain":CFG["slug"]}

@app.get("/readyz")
def readyz():
    status=local_integrity()
    return JSONResponse(status,status_code=200 if status["ready"] else 503)

@app.get("/api/live")
def live(): return probe()

@app.get("/api/source")
def source():
    return {"product_source":CFG["product_source"],"deployment_source":CFG["source_repository"],"source_revision":CFG["source_revision"],"workflow_run_id":CFG["workflow_run_id"]}

@app.get("/api/build-info")
def build_info():
    return JSONResponse({
        "schema":"szl.build-info/v1",
        "source_repository":CFG["source_repository"],
        "source_revision":CFG["source_revision"],
        "workflow_run_id":CFG["workflow_run_id"],
        "hf_repository":CFG["hf_repository"],
        "hf_revision":hf_revision(),
        "artifact_set_sha256":CFG["artifact_set_sha256"],
        "public_experience":CFG["public_experience"],
        "product_source":CFG["product_source"],
        "forge":CFG.get("forge"),
        "routes":{"landing":"/","panels":"/panels","live":"/api/live","receipt":"/build-receipt.json"},
    })

@app.get("/build-receipt.json")
def build_receipt():
    integrity=local_integrity()
    return JSONResponse({
        "schema":"szl.vertical-shell-deployment/v1",
        "state":"VERIFIED_RUNTIME_ARTIFACTS" if integrity["ready"] else "INVALID",
        "source_repository":CFG["source_repository"],
        "source_revision":CFG["source_revision"],
        "workflow_run_id":CFG["workflow_run_id"],
        "hf_repository":CFG["hf_repository"],
        "hf_revision":hf_revision(),
        "artifact_set_sha256":CFG["artifact_set_sha256"],
        "landing_sha256":CFG["landing_sha256"],
        "panels_sha256":CFG["panels_sha256"],
        "forge":CFG.get("forge"),
        "integrity":integrity,
    },status_code=200 if integrity["ready"] else 503)

@app.get("/.well-known/szl-source.json")
def source_document(): return build_info()

@app.get("/",response_class=HTMLResponse)
def root(): return INDEX

@app.get("/panels",response_class=HTMLResponse)
def panels(): return PANELS
'''

DOCKER = '''FROM python:3.12-slim\nENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY app.py config.json index.html panels.html ./\nEXPOSE 7860\nCMD ["uvicorn","app:app","--host","0.0.0.0","--port","7860"]\n'''
REQ = "fastapi==0.116.1\nuvicorn[standard]==0.35.0\nhttpx==0.28.1\n"

BASE_CSS = r'''
:root{color-scheme:dark;--touch:44px;--stage:1440px;--gutter:clamp(16px,3vw,42px);--line:rgba(255,255,255,.12);--muted:#98a4b3;--ink:#f8fafc;--bg:#05070a;--panel:rgba(12,16,22,.86);--accent:#7dd3fc;--accent2:#a7f3d0}
*{box-sizing:border-box;min-inline-size:0}html{max-inline-size:100%;overflow-x:clip;text-size-adjust:100%}body{margin:0;min-height:100vh;max-inline-size:100%;overflow-x:clip;background:var(--bg);color:var(--ink);font:15px/1.55 Inter,ui-sans-serif,system-ui,sans-serif}a,button{min-block-size:var(--touch)}a{color:inherit;overflow-wrap:anywhere}button{border:1px solid var(--line);background:var(--ink);color:var(--bg);padding:10px 15px;border-radius:9px;font-weight:800;cursor:pointer}button:focus-visible,a:focus-visible{outline:3px solid var(--accent);outline-offset:3px}.shell{width:min(100%,var(--stage));margin:auto;padding:calc(24px + env(safe-area-inset-top)) var(--gutter) calc(64px + env(safe-area-inset-bottom))}.top{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}.brand{font-weight:900;letter-spacing:.16em}.eyebrow,.mono,.status{font:700 11px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase}.eyebrow{color:var(--accent)}h1{font-size:clamp(44px,8vw,116px);line-height:.88;letter-spacing:-.06em;margin:16px 0 22px;max-inline-size:12ch;overflow-wrap:anywhere}.lede{font-size:clamp(17px,2vw,22px);max-inline-size:70ch;color:var(--muted)}.flow{display:flex;gap:8px;flex-wrap:wrap;margin:30px 0}.flow span{border:1px solid var(--line);padding:8px 10px;border-radius:999px;font:700 10px ui-monospace,monospace;letter-spacing:.1em}.panel{border:1px solid var(--line);background:var(--panel);border-radius:18px;padding:18px}.livebar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.status{display:flex;align-items:center;gap:8px}.dot{inline-size:8px;block-size:8px;border-radius:50%;background:#64748b}.is-live .dot{background:var(--accent2);box-shadow:0 0 18px var(--accent2)}pre{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;max-block-size:360px;overflow:auto;font:12px/1.55 ui-monospace,monospace;color:#cbd5e1}.footer{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:18px}.footer .panel{font-size:12px;color:var(--muted)}.footer b{display:block;color:var(--ink);margin-bottom:8px}.truth{display:flex;gap:7px;flex-wrap:wrap}.truth span{font:700 10px ui-monospace,monospace;border:1px solid var(--line);padding:6px 8px;border-radius:6px}@media(max-width:760px){.footer{grid-template-columns:1fr}h1{font-size:clamp(42px,16vw,72px)}}@media(pointer:coarse){a,button{min-block-size:48px}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important;scroll-behavior:auto!important}}@media(forced-colors:active){*{forced-color-adjust:auto}.panel{border:1px solid CanvasText}}
.illus{display:inline-block;font:700 9.5px ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:#d4a444;border:1px dashed rgba(212,164,68,.55);border-radius:6px;padding:4px 8px;margin-bottom:10px}
.tape>.illus{grid-column:1/-1;margin:10px 12px 9px}
'''

DOMAIN_CSS: dict[str, str] = {
    "terra": r''':root{--bg:#0b0b08;--panel:rgba(22,22,14,.9);--muted:#b2ad91;--accent:#e6b85c;--accent2:#96c983}.domain{margin-top:48px;display:grid;grid-template-columns:minmax(0,1.35fr) minmax(260px,.65fr);gap:14px}.parcel-map{min-height:410px;position:relative;overflow:hidden;background:linear-gradient(135deg,rgba(230,184,92,.07),transparent 60%),repeating-linear-gradient(0deg,transparent 0 39px,rgba(230,184,92,.09) 40px),repeating-linear-gradient(90deg,transparent 0 59px,rgba(230,184,92,.09) 60px)}.parcel{position:absolute;border:1px solid rgba(230,184,92,.55);background:rgba(230,184,92,.06);padding:8px;font:700 10px ui-monospace,monospace}.p1{inset:12% 54% 52% 8%}.p2{inset:18% 12% 47% 49%}.p3{inset:58% 48% 10% 14%}.p4{inset:61% 11% 13% 55%}.dealstack{display:grid;gap:9px}.deal{border-left:3px solid var(--accent);padding:12px;background:rgba(255,255,255,.025)}@media(max-width:850px){.domain{grid-template-columns:1fr}.parcel-map{min-height:340px}}@media(max-width:480px){.parcel-map{min-height:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;align-content:start}.parcel-map>.illus{grid-column:1/-1;margin:0 0 10px}.parcel{position:static;min-height:88px}}''',
    "sentra": r''':root{--bg:#030506;--panel:rgba(7,12,15,.92);--muted:#8ca1a8;--accent:#54f0d1;--accent2:#ff5d73}.domain{margin-top:48px;display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.8fr);gap:14px}.attack{min-height:410px;position:relative;overflow:hidden;background:radial-gradient(circle at 30% 30%,rgba(84,240,209,.08),transparent 35%),linear-gradient(rgba(84,240,209,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(84,240,209,.045) 1px,transparent 1px);background-size:auto,28px 28px,28px 28px}.node{position:absolute;inline-size:74px;block-size:74px;border:1px solid var(--accent);border-radius:50%;display:grid;place-items:center;background:#061014;font:800 9px ui-monospace,monospace;text-align:center}.n1{left:8%;top:18%}.n2{left:42%;top:10%}.n3{right:8%;top:38%;border-color:var(--accent2)}.n4{left:34%;bottom:9%}.path{position:absolute;block-size:1px;background:linear-gradient(90deg,var(--accent),var(--accent2));transform-origin:left center}.x1{left:16%;top:27%;inline-size:31%;transform:rotate(-8deg)}.x2{left:49%;top:20%;inline-size:37%;transform:rotate(25deg)}.x3{left:42%;top:65%;inline-size:42%;transform:rotate(-22deg)}.queue{display:grid;gap:8px}.incident{padding:12px;border:1px solid var(--line);display:grid;grid-template-columns:64px 1fr;gap:10px}.sev{font:900 10px ui-monospace,monospace;color:var(--accent2)}@media(max-width:850px){.domain{grid-template-columns:1fr}}''',
    "counsel": r''':root{color-scheme:light;--bg:#f3efe6;--panel:rgba(255,253,247,.92);--ink:#172033;--muted:#5d6574;--line:rgba(23,32,51,.16);--accent:#214b8f;--accent2:#8b5e34}.brand{font-family:Georgia,serif}.illus{color:#5b3a12;border-color:#8b5e34}.domain{margin-top:48px;display:grid;grid-template-columns:minmax(0,1.2fr) minmax(280px,.8fr);gap:14px}.matter{background:linear-gradient(90deg,transparent 52px,rgba(33,75,143,.14) 53px,transparent 54px),repeating-linear-gradient(0deg,transparent 0 31px,rgba(23,32,51,.06) 32px);min-height:420px;padding-left:72px}.matter h2{font:700 clamp(25px,4vw,42px)/1.1 Georgia,serif}.issue{border-bottom:1px solid var(--line);padding:15px 0}.authority{display:grid;gap:10px}.cite{padding:13px;border-left:3px solid var(--accent);background:rgba(33,75,143,.045)}.cite b{font-family:Georgia,serif}.truth span{background:#fff}@media(max-width:850px){.domain{grid-template-columns:1fr}.matter{padding-left:42px}}''',
    "finance": r''':root{--bg:#030403;--panel:rgba(7,10,7,.95);--muted:#9ca892;--accent:#f6c85f;--accent2:#7cf29a}.domain{margin-top:48px;display:grid;grid-template-columns:1fr;gap:12px}.tape{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:var(--line);border:1px solid var(--line)}.quote{background:#050805;padding:14px}.quote b{display:block;font:900 18px ui-monospace,monospace;color:var(--accent2)}.quote span{font:700 10px ui-monospace,monospace;color:var(--muted)}.matrix{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(280px,.75fr);gap:12px}.ledger{font:12px ui-monospace,monospace}.row{display:grid;grid-template-columns:1.2fr .7fr .7fr .8fr;gap:8px;padding:10px 0;border-bottom:1px solid var(--line)}.row b{color:var(--accent)}.stress{display:grid;gap:10px}.bar{display:grid;grid-template-columns:90px 1fr 50px;gap:8px;align-items:center}.bar i{display:block;block-size:8px;background:linear-gradient(90deg,var(--accent2),var(--accent));border-radius:9px}@media(max-width:850px){.tape{grid-template-columns:1fr 1fr}.matrix{grid-template-columns:1fr}.row{grid-template-columns:1fr 1fr}}''',
    "vessels": r''':root{--bg:#041018;--panel:rgba(4,20,29,.92);--muted:#8ca8b5;--accent:#52d9d0;--accent2:#f0b45a}.domain{margin-top:48px;display:grid;grid-template-columns:minmax(0,1.3fr) minmax(280px,.7fr);gap:14px}.chart{min-height:430px;position:relative;overflow:hidden;background:radial-gradient(circle at 68% 30%,rgba(82,217,208,.09),transparent 24%),linear-gradient(rgba(82,217,208,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(82,217,208,.05) 1px,transparent 1px);background-size:auto,36px 36px,36px 36px}.route{position:absolute;inset:12% 8%;border:2px dashed rgba(82,217,208,.55);border-left-color:transparent;border-bottom-color:transparent;border-radius:50%;transform:rotate(12deg)}.port{position:absolute;inline-size:12px;block-size:12px;border:2px solid var(--accent);border-radius:50%;background:var(--bg)}.a{left:11%;bottom:22%}.b{left:46%;top:24%}.c{right:13%;top:42%;border-color:var(--accent2)}.vessel{position:absolute;left:48%;top:47%;font-size:28px;transform:rotate(22deg)}.voyages{display:grid;gap:9px}.voyage{padding:12px;border:1px solid var(--line)}.voyage b{display:flex;justify-content:space-between;gap:8px;color:var(--accent)}@media(max-width:850px){.domain{grid-template-columns:1fr}.chart{min-height:340px}}''',
    "lyte": r''':root{--bg:#070710;--panel:rgba(12,12,25,.93);--muted:#a3a2bd;--accent:#a78bfa;--accent2:#67e8f9}.domain{margin-top:48px;display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr);gap:14px}.services{display:grid;gap:10px}.svc{display:grid;grid-template-columns:14px 1fr auto;align-items:center;gap:10px;padding:12px;border:1px solid var(--line)}.svc i{inline-size:10px;block-size:10px;border-radius:50%;background:var(--accent2);box-shadow:0 0 15px rgba(103,232,249,.45)}.waterfall{display:grid;gap:7px}.span{display:grid;grid-template-columns:120px 1fr 52px;gap:10px;align-items:center;font:11px ui-monospace,monospace}.span i{display:block;block-size:10px;margin-left:var(--offset);inline-size:var(--width);max-inline-size:calc(100% - var(--offset));background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:4px}.agentline{margin-top:12px;padding:12px;border-left:3px solid var(--accent);background:rgba(167,139,250,.06)}@media(max-width:850px){.domain{grid-template-columns:1fr}.span{grid-template-columns:95px 1fr 42px}}''',
}

DOMAIN_HTML: dict[str, str] = {
    "terra": '''<div class="domain"><section class="panel parcel-map" aria-label="Illustrative parcel intelligence map"><span class="illus">Illustrative — schematic, not live data</span><div class="parcel p1">PARCEL A-14<br>OWNERSHIP 3 hops</div><div class="parcel p2">PARCEL B-07<br>DEBT watch</div><div class="parcel p3">PARCEL C-02<br>PIPELINE</div><div class="parcel p4">PARCEL D-11<br>REVIEW</div></section><aside class="panel dealstack"><div class="mono">UNDERWRITING QUEUE</div><div class="deal"><b>Ownership resolution</b><br><span>Evidence chain before outreach</span></div><div class="deal"><b>Basis / debt / distress</b><br><span>Separate observed facts from modeled value</span></div><div class="deal"><b>Human approval</b><br><span>No acquisition action without authority</span></div></aside></div>''',
    "sentra": '''<div class="domain"><section class="panel attack" aria-label="Illustrative attack path graph"><span class="path x1"></span><span class="path x2"></span><span class="path x3"></span><div class="node n1">IDENTITY</div><div class="node n2">WORKLOAD</div><div class="node n3">CROWN<br>ASSET</div><div class="node n4">CONTROL</div></section><aside class="panel queue"><div class="mono">RESPONSE QUEUE</div><div class="incident"><span class="sev">HIGH</span><span>Identity-to-workload path requires verification.</span></div><div class="incident"><span class="sev">MED</span><span>Control drift correlated across evidence sources.</span></div><div class="incident"><span class="sev">INFO</span><span>Every action remains deny-by-default and receipted.</span></div></aside></div>''',
    "counsel": '''<div class="domain"><article class="panel matter"><span class="illus">Illustrative — schematic, not live data</span><div class="mono">MATTER / WORK PRODUCT</div><h2>Question → authority → analysis → defensible draft.</h2><div class="issue"><b>Issue framing</b><br><span>Facts and jurisdiction stay visible beside the work.</span></div><div class="issue"><b>Drafting lane</b><br><span>Agent output is a proposed work product, never final legal authority.</span></div><div class="issue"><b>Verification lane</b><br><span>Claims and citations are checked before approval.</span></div></article><aside class="panel authority"><div class="mono">AUTHORITY RAIL</div><div class="cite"><b>Primary authority</b><br><span>Traceable source placeholder</span></div><div class="cite"><b>Practice material</b><br><span>Jurisdiction / date / status</span></div><div class="cite"><b>Matter evidence</b><br><span>Client documents remain distinguishable from law</span></div></aside></div>''',
    "finance": '''<div class="domain"><section class="tape" aria-label="Illustrative financial decision tape"><span class="illus">Illustrative — schematic, not live data</span><div class="quote"><b>Λ 0.94</b><span>GOVERNED SCORE</span></div><div class="quote"><b>+18 bp</b><span>SPREAD MOVE</span></div><div class="quote"><b>0.73</b><span>LIQUIDITY</span></div><div class="quote"><b>2.1×</b><span>STRESS</span></div><div class="quote"><b>OPEN</b><span>APPROVAL</span></div></section><div class="matrix"><section class="panel ledger"><div class="mono">DECISION TAPE</div><div class="row"><b>SIGNAL</b><b>OBSERVED</b><b>MODELED</b><b>STATE</b></div><div class="row"><span>Exposure</span><span>evidence</span><span>scenario</span><span>REVIEW</span></div><div class="row"><span>Liquidity</span><span>evidence</span><span>stress</span><span>REVIEW</span></div><div class="row"><span>Counterparty</span><span>evidence</span><span>impact</span><span>WATCH</span></div></section><aside class="panel stress"><div class="mono">STRESS LANES</div><div class="bar"><span>BASE</span><i style="width:42%"></i><b>42</b></div><div class="bar"><span>LIQUIDITY</span><i style="width:68%"></i><b>68</b></div><div class="bar"><span>TAIL</span><i style="width:86%"></i><b>86</b></div></aside></div></div>''',
    "vessels": '''<div class="domain"><section class="panel chart" aria-label="Illustrative maritime route chart"><div class="route"></div><span class="port a"></span><span class="port b"></span><span class="port c"></span><span class="vessel" aria-hidden="true">◢</span></section><aside class="panel voyages"><div class="mono">VOYAGE WATCH</div><div class="voyage"><b><span>ATLANTIC-07</span><span>WATCH</span></b><span>AIS continuity / sanctions / weather</span></div><div class="voyage"><b><span>PACIFIC-12</span><span>OPEN</span></b><span>Route economics / port state / ETA</span></div><div class="voyage"><b><span>MED-03</span><span>REVIEW</span></b><span>Evidence gaps remain explicit</span></div></aside></div>''',
    "lyte": '''<div class="domain"><aside class="panel services"><span class="illus">Illustrative — schematic, not live data</span><div class="mono">SERVICE GRAPH</div><div class="svc"><i></i><b>gateway</b><span>12 ms</span></div><div class="svc"><i></i><b>policy</b><span>31 ms</span></div><div class="svc"><i></i><b>receipt</b><span>18 ms</span></div><div class="svc"><i></i><b>evidence</b><span>24 ms</span></div><div class="agentline"><b>Agent context</b><br><span>Tool calls, handoffs, retries, and downstream spans belong on the same incident timeline.</span></div></aside><section class="panel waterfall"><span class="illus">Illustrative — schematic, not live data</span><div class="mono">TRACE TIMELINE</div><div class="span"><span>gateway</span><i style="--offset:0%;--width:74%"></i><b>74ms</b></div><div class="span"><span>policy</span><i style="--offset:14%;--width:36%"></i><b>36ms</b></div><div class="span"><span>model</span><i style="--offset:25%;--width:61%"></i><b>61ms</b></div><div class="span"><span>receipt</span><i style="--offset:64%;--width:25%"></i><b>25ms</b></div><div class="span"><span>verify</span><i style="--offset:75%;--width:18%"></i><b>18ms</b></div></section></div>''',
}


def token_from_env() -> tuple[str, str]:
    for name in ("HF_ORG_TOKEN", "HF_WRITE_TOKEN", "HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    raise RuntimeError("no Hugging Face write token available")


def artifact_digest(*payloads: str) -> str:
    digest = hashlib.sha256()
    for payload in payloads:
        raw = payload.encode("utf-8")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid Terra forge bundle file: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Terra forge bundle is not a JSON object: {path}")
    return value


def load_terra_forge_bundle() -> tuple[str, dict[str, Any]]:
    """Load and independently verify the exact merged forge artifact."""
    page_path = TERRA_FORGE_BUNDLE / "index.html"
    artifact_path = TERRA_FORGE_BUNDLE / "build-receipt.json"
    fleet_path = TERRA_FORGE_BUNDLE / "fleet-receipt.json"
    lock_path = TERRA_FORGE_BUNDLE / "source-lock.json"
    try:
        page = page_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"missing Terra forge artifact: {page_path}") from exc
    artifact = read_json_object(artifact_path)
    fleet = read_json_object(fleet_path)
    source_lock = read_json_object(lock_path)

    if TERRA_FORGE_MARKER not in page:
        raise RuntimeError("Terra landing lacks the pinned forge marker")
    for route in ('href="/panels"', 'href="/build-receipt.json"', 'const EP="/api/live"'):
        if route not in page:
            raise RuntimeError(f"Terra landing lacks required runtime wiring: {route}")
    if fleet.get("schema") != "szl.vertical-forge.receipt/v3":
        raise RuntimeError("Terra fleet receipt schema mismatch")
    if artifact.get("schema") != "szl.vertical-forge.artifact/v1":
        raise RuntimeError("Terra artifact receipt schema mismatch")
    if source_lock.get("schema") != "szl.vertical-shell.source-lock/v1":
        raise RuntimeError("Terra source lock schema mismatch")
    if fleet.get("generator") != TERRA_FORGE_GENERATOR:
        raise RuntimeError("Terra fleet receipt generator mismatch")
    if artifact.get("generator") != TERRA_FORGE_GENERATOR:
        raise RuntimeError("Terra artifact receipt generator mismatch")
    if source_lock.get("generator") != TERRA_FORGE_GENERATOR:
        raise RuntimeError("Terra source lock generator mismatch")
    if source_lock.get("source_repository") != TERRA_FORGE_SOURCE_REPOSITORY:
        raise RuntimeError("Terra source repository mismatch")
    source_revision = str(source_lock.get("source_revision") or "")
    if len(source_revision) != 40 or any(ch not in "0123456789abcdef" for ch in source_revision):
        raise RuntimeError("Terra forge source revision is not an exact Git SHA")

    genesis = "0" * 64
    if fleet.get("genesis") != genesis:
        raise RuntimeError("Terra fleet receipt genesis mismatch")
    events = fleet.get("events")
    if not isinstance(events, list) or len(events) != fleet.get("vertical_count"):
        raise RuntimeError("Terra fleet receipt event count mismatch")
    previous = genesis
    terra_event: dict[str, Any] | None = None
    for position, event in enumerate(events):
        if not isinstance(event, dict) or event.get("prev_hash") != previous:
            raise RuntimeError(f"Terra fleet receipt link mismatch at event {position}")
        candidate = {key: value for key, value in event.items() if key != "chain_hash"}
        calculated = hashlib.sha256(canonical_json(candidate)).hexdigest()
        if event.get("chain_hash") != calculated:
            raise RuntimeError(f"Terra fleet receipt hash mismatch at event {position}")
        previous = calculated
        if event.get("path") == "terra/index.html":
            terra_event = event
    if previous != fleet.get("master_hash"):
        raise RuntimeError("Terra fleet master hash mismatch")
    if terra_event is None or artifact.get("chain_event") != terra_event:
        raise RuntimeError("Terra artifact receipt is not bound into the fleet chain")

    page_hash = hashlib.sha256(page.encode("utf-8")).hexdigest()
    expected_values = {
        "artifact_sha256": page_hash,
        "fleet_master_hash": fleet.get("master_hash"),
        "generator": fleet.get("generator"),
    }
    for field, expected in expected_values.items():
        if source_lock.get(field) != expected:
            raise RuntimeError(f"Terra source lock {field} mismatch")
    if terra_event.get("artifact_sha256") != page_hash:
        raise RuntimeError("Terra landing bytes do not match the chained artifact hash")
    if artifact.get("fleet_master_hash") != fleet.get("master_hash"):
        raise RuntimeError("Terra artifact receipt master hash mismatch")
    if artifact.get("vertical") != "terra":
        raise RuntimeError("Terra artifact receipt vertical mismatch")

    forge = {
        "schema": "szl.vertical-forge.deployment-source/v1",
        "generator": TERRA_FORGE_GENERATOR,
        "source_repository": TERRA_FORGE_SOURCE_REPOSITORY,
        "source_revision": source_revision,
        "source_pull_request": source_lock.get("source_pull_request"),
        "fleet_master_hash": fleet["master_hash"],
        "fleet_config_sha256": artifact.get("fleet_config_sha256"),
        "vertical_config_sha256": artifact.get("config_sha256"),
        "artifact_sha256": page_hash,
        "chain_hash": terra_event["chain_hash"],
    }
    return page, forge


def html(item: dict[str, Any]) -> str:
    flow = "".join(f"<span>{step}</span>" for step in item["workflow"])
    labels = item["labels"]
    return f'''<!doctype html>
<html lang="en" data-szl-public-experience-v3="true" data-szl-domain-experience-v4="true" data-domain="{item['slug']}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#05070a"><title>{item['title']} — SZL Holdings</title><style>{BASE_CSS}{DOMAIN_CSS[item['slug']]}</style></head>
<body><main class="shell"><header class="top"><div class="brand">SZL HOLDINGS / {item['title'].upper()}</div><div class="mono">DOMAIN EXPERIENCE V4 · SOURCE BOUND</div></header><section style="margin-top:clamp(52px,9vw,112px)"><div class="eyebrow">{item['vertical']}</div><h1>{item['title']}</h1><p class="lede">{item['short']}. One governed runtime underneath; a domain-native workbench above it. Observed evidence, modeled analysis, human authority, and audit receipts remain separate states.</p><div class="flow">{flow}</div></section>{DOMAIN_HTML[item['slug']]}<section class="panel" style="margin-top:14px"><div class="livebar"><div id="st" class="status"><span class="dot"></span><span>PROBING GOVERNED EVIDENCE</span></div><button type="button" onclick="loadEvidence()">Refresh evidence</button></div><pre id="out">Loading governed evidence…</pre></section><footer class="footer"><div class="panel"><b>{labels[0]}</b><span>Domain-specific visualization remains distinct from the shared execution contract.</span></div><div class="panel"><b>{labels[1]}</b><span>Every decision surface keeps provenance and evidence status visible.</span></div><div class="panel"><b>{labels[2]}</b><div class="truth"><span>MEASURED</span><span>REPORTED</span><span>MODELED</span><span>UNAVAILABLE</span></div></div></footer><p class="mono" style="margin-top:18px;color:var(--muted)">Canonical product source: <a href="{item['source']}" target="_blank" rel="noopener">{item['source']}</a> · Portfolio: <a href="https://a-11-oy.com/products/" target="_blank" rel="noopener">a-11-oy.com/products/</a></p></main><script>async function loadEvidence(){{const s=document.getElementById('st'),o=document.getElementById('out');try{{const r=await fetch('/api/live',{{cache:'no-store'}}),j=await r.json();s.className='status '+(j.status==='LIVE'?'is-live':'');s.children[1].textContent=j.status+' / '+(j.latency_ms??'-')+' ms';o.textContent=JSON.stringify(j,null,2)}}catch(e){{s.children[1].textContent='UNAVAILABLE';o.textContent=String(e)}}}}loadEvidence();setInterval(loadEvidence,60000)</script></body></html>'''


def readme(item: dict[str, Any]) -> str:
    forge_note = ""
    if item["slug"] == "terra":
        forge_note = f'''\nLanding shell: `{TERRA_FORGE_GENERATOR}` from [{TERRA_FORGE_SOURCE_REPOSITORY}](https://github.com/{TERRA_FORGE_SOURCE_REPOSITORY}). The existing Domain Experience v4 workbench remains available at `/panels`; `/build-receipt.json` exposes the source-bound runtime receipt.\n'''
    return f'''---
title: {item['title']}
emoji: 🛰️
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
pinned: true
license: apache-2.0
short_description: "{item['short']}"
tags:
  - szl-holdings
  - governed-ai
  - {item['slug']}
---

# {item['title']}

{item['vertical']} flagship for SZL Holdings.

This Space uses **Domain Experience v4**: an original, domain-specific interface over the shared governed vertical runtime. Runtime claims fail closed to `UNAVAILABLE`; evidence states are never collapsed.
{forge_note}

Canonical product source: {item['source']}

Deployment controller: https://github.com/szl-holdings/a11oy

Portfolio: https://a-11-oy.com/products/

License: Apache-2.0. Public Experience: `{PUBLIC_EXPERIENCE_VERSION}`.
'''


def upload_text(api: HfApi, repo_id: str, path: str, content: str) -> Any:
    return api.upload_file(path_or_fileobj=content.encode("utf-8"), path_in_repo=path, repo_id=repo_id, repo_type="space", commit_message=f"feat(domain-v4): publish {path}")


def get_json(url: str, *, timeout: int = 20) -> tuple[int | None, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return None, {"error": f"{type(exc).__name__}: {exc}"}


def probe_html(slug: str, path: str, marker: str, *, timeout: int = 20) -> dict[str, Any]:
    url = f"https://szlholdings-{slug}.hf.space{path}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {"url": url, "http_status": response.status, "marker_present": marker in body}
    except urllib.error.HTTPError as exc:
        return {"url": url, "http_status": exc.code, "marker_present": False}
    except Exception as exc:
        return {"url": url, "http_status": None, "marker_present": False, "error": f"{type(exc).__name__}: {exc}"}


def observe_flagship(row: dict[str, Any]) -> None:
    slug = row["slug"]
    origin = f"https://szlholdings-{slug}.hf.space"
    row["root"] = probe_html(slug, "/", row["root_marker"])
    row["panels"] = probe_html(slug, "/panels", PUBLIC_EXPERIENCE_MARKER)
    for name, path in (
        ("build_info", "/api/build-info"),
        ("readyz", "/readyz"),
        ("deployment_receipt", "/build-receipt.json"),
    ):
        status, payload = get_json(origin + path)
        row[f"{name}_http"] = status
        row[name] = payload


def observation_passes(
    row: dict[str, Any],
    *,
    source_revision: str,
    workflow_run_id: str,
) -> bool:
    root = row.get("root")
    panels = row.get("panels")
    build = row.get("build_info")
    ready = row.get("readyz")
    deployment = row.get("deployment_receipt")
    if not all(isinstance(value, dict) for value in (root, panels, build, ready, deployment)):
        return False
    hf_revision = str(build.get("hf_revision") or "")
    return bool(
        root.get("http_status") == 200
        and root.get("marker_present") is True
        and panels.get("http_status") == 200
        and panels.get("marker_present") is True
        and row.get("build_info_http") == 200
        and build.get("schema") == "szl.build-info/v1"
        and build.get("source_repository") == DEPLOYMENT_SOURCE_REPOSITORY
        and build.get("source_revision") == source_revision
        and str(build.get("workflow_run_id")) == workflow_run_id
        and build.get("artifact_set_sha256") == row["artifact_set_sha256"]
        and build.get("forge") == row["forge"]
        and len(hf_revision) == 40
        and all(ch in "0123456789abcdef" for ch in hf_revision)
        and row.get("readyz_http") == 200
        and ready.get("schema") == "szl.vertical-shell-readiness/v1"
        and ready.get("ready") is True
        and ready.get("state") == "MEASURED"
        and row.get("deployment_receipt_http") == 200
        and deployment.get("schema") == "szl.vertical-shell-deployment/v1"
        and deployment.get("state") == "VERIFIED_RUNTIME_ARTIFACTS"
        and deployment.get("source_revision") == source_revision
        and str(deployment.get("workflow_run_id")) == workflow_run_id
        and deployment.get("artifact_set_sha256") == row["artifact_set_sha256"]
        and deployment.get("landing_sha256") == row["landing_sha256"]
        and deployment.get("panels_sha256") == row["panels_sha256"]
        and deployment.get("forge") == row["forge"]
    )



def ensure_space_repository(api: HfApi, repo_id: str) -> str:
    """Create only a genuinely absent Space, then prove write access."""
    try:
        exists = bool(api.repo_exists(repo_id=repo_id, repo_type="space"))
    except Exception as exc:
        raise RuntimeError(
            f"unable to determine whether target Space exists: {repo_id}"
        ) from exc
    if exists:
        action = "space_existing"
    else:
        api.create_repo(
            repo_id=repo_id,
            repo_type="space",
            space_sdk="docker",
            exist_ok=True,
            private=False,
        )
        action = "space_created"
    api.auth_check(repo_id=repo_id, repo_type="space", write=True)
    return action


def main() -> int:
    token, token_source = token_from_env()
    api = HfApi(token=token)
    source_revision = os.getenv("GITHUB_SHA", "").strip().lower()
    workflow_run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    if len(source_revision) != 40 or not all(ch in "0123456789abcdef" for ch in source_revision):
        raise RuntimeError("publisher requires an exact 40-hex GITHUB_SHA")
    if not workflow_run_id.isdigit() or int(workflow_run_id) <= 0:
        raise RuntimeError("publisher requires a positive GITHUB_RUN_ID")

    terra_page, terra_forge = load_terra_forge_bundle()
    rows: list[dict[str, Any]] = []
    for item in FLAGSHIPS:
        slug = item["slug"]
        rid = f"{ORG}/{slug}"
        panels = html(item)
        page = terra_page if slug == "terra" else panels
        forge = terra_forge if slug == "terra" else None
        root_marker = TERRA_FORGE_MARKER if slug == "terra" else PUBLIC_EXPERIENCE_MARKER
        card = readme(item)
        forge_payload = json.dumps(forge, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        landing_sha256 = hashlib.sha256(page.encode("utf-8")).hexdigest()
        panels_sha256 = hashlib.sha256(panels.encode("utf-8")).hexdigest()
        artifacts = artifact_digest(APP, DOCKER, REQ, page, panels, card, forge_payload)
        config = json.dumps({
            "slug": slug,
            "title": item["title"],
            "vertical": item["vertical"],
            "product_source": item["source"],
            "source_repository": DEPLOYMENT_SOURCE_REPOSITORY,
            "source_revision": source_revision,
            "workflow_run_id": int(workflow_run_id),
            "hf_repository": rid,
            "artifact_set_sha256": artifacts,
            "landing_sha256": landing_sha256,
            "panels_sha256": panels_sha256,
            "forge": forge,
            "upstream": item["upstream"],
            "public_experience": PUBLIC_EXPERIENCE_VERSION,
        }, indent=2, sort_keys=True) + "\n"
        row: dict[str, Any] = {"id": rid, "slug": slug, "source": item["source"], "source_revision": source_revision, "workflow_run_id": int(workflow_run_id), "artifact_set_sha256": artifacts, "landing_sha256": landing_sha256, "panels_sha256": panels_sha256, "forge": forge, "root_marker": root_marker, "actions": []}
        try:
            row["actions"].append(ensure_space_repository(api, rid))
            for path, payload in (("app.py", APP), ("Dockerfile", DOCKER), ("requirements.txt", REQ), ("config.json", config), ("index.html", page), ("panels.html", panels), ("README.md", card)):
                upload_text(api, rid, path, payload)
            row["actions"].append("publish_source")
            api.restart_space(rid)
            row["actions"].append("restart")
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)

    deadline = time.time() + 900
    pending = {row["id"].split("/", 1)[1] for row in rows if "error" not in row}
    while pending and time.time() < deadline:
        for slug in tuple(pending):
            row = next(value for value in rows if value["id"].endswith("/" + slug))
            observe_flagship(row)
            if observation_passes(row, source_revision=source_revision, workflow_run_id=workflow_run_id):
                pending.remove(slug)
        if pending:
            time.sleep(15)

    complete = True
    for row in rows:
        observe_flagship(row)
        ok = (
            "error" not in row
            and observation_passes(
                row,
                source_revision=source_revision,
                workflow_run_id=workflow_run_id,
            )
        )
        row["operational"] = ok
        complete = complete and ok

    receipt = {
        "schema": "szl.hf-vertical-flagships/v4",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_repository": DEPLOYMENT_SOURCE_REPOSITORY,
        "source_revision": source_revision,
        "workflow_run_id": int(workflow_run_id),
        "token_source_name": token_source,
        "token_value_recorded": False,
        "public_experience": PUBLIC_EXPERIENCE_VERSION,
        "verticals_total": len(rows),
        "verticals_operational": sum(1 for row in rows if row.get("operational") is True),
        "complete": complete,
        "rows": rows,
    }
    Path("hf-vertical-flagships-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
