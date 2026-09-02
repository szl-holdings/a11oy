#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish the six missing SZLHOLDINGS vertical flagship Spaces.

The flagship UI is a governed presentation shell over already-shipped SZL live APIs.
It never fabricates data: upstream failures render UNAVAILABLE. Existing A11oy,
Killinchu and David Leads Spaces are intentionally not overwritten.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

ORG = "SZLHOLDINGS"
A11OY = "https://szlholdings-a11oy.hf.space"
KILLINCHU = "https://szlholdings-killinchu.hf.space"
FLAGSHIPS = [
    dict(slug="terra", title="Terra", vertical="REAL ESTATE INTELLIGENCE", source="https://github.com/szl-holdings/szl-real-estate", upstream=f"{A11OY}/api/a11oy/v1/vert/realestate/feed", product="https://a-11-oy.com/products/"),
    dict(slug="sentra", title="Sentra", vertical="CYBERSECURITY INTELLIGENCE", source="https://github.com/szl-holdings/szl-defensive-control-plane", upstream=f"{A11OY}/api/a11oy/v1/vert/cyber/feed", product="https://a-11-oy.com/products/"),
    dict(slug="counsel", title="PRISM Counsel", vertical="LEGAL MATTER INTELLIGENCE", source="https://github.com/szl-holdings/counsel", upstream=f"{A11OY}/api/a11oy/v1/vert/legal/feed", product="https://a-11-oy.com/products/"),
    dict(slug="finance", title="PURIQ Finance", vertical="FINANCIAL INTELLIGENCE", source="https://github.com/szl-holdings/puriq-live", upstream=f"{A11OY}/api/a11oy/v1/vert/finance/feed", product="https://a-11-oy.com/products/"),
    dict(slug="vessels", title="Vessels", vertical="MARITIME INTELLIGENCE", source="https://github.com/szl-holdings/szl-fleet-overlay", upstream=f"{KILLINCHU}/api/killinchu/v1/maritime/risk/fleet", product="https://a-11-oy.com/products/"),
    dict(slug="lyte", title="Lyte", vertical="BUSINESS OBSERVABILITY", source="https://github.com/szl-holdings/lyte-lattice", upstream=f"{A11OY}/api/a11oy/v1/observability/summary", product="https://a-11-oy.com/products/"),
]


def token_from_env() -> tuple[str, str]:
    for key in ("HF_ORG_TOKEN", "HF_WRITE_TOKEN", "HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        value = os.getenv(key)
        if value and value.strip():
            return value.strip(), key
    raise RuntimeError("no Hugging Face write token is available")


APP = '''from __future__ import annotations
import json, time
from pathlib import Path
import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

CFG = json.loads(Path("config.json").read_text(encoding="utf-8"))
INDEX = Path("index.html").read_text(encoding="utf-8")
app = FastAPI(title=CFG["title"] + " - SZL Holdings")


def read_upstream():
    started = time.time()
    try:
        response = httpx.get(CFG["upstream"], timeout=15, headers={"User-Agent": "SZLHOLDINGS-Flagship/1.0"})
        ctype = response.headers.get("content-type", "")
        body = response.json() if "json" in ctype else {"text": response.text[:4000]}
        return {
            "status": "LIVE" if response.is_success else "UNAVAILABLE",
            "http_status": response.status_code,
            "latency_ms": round((time.time() - started) * 1000, 1),
            "source": CFG["upstream"],
            "data": body,
        }
    except Exception as exc:
        return {"status": "UNAVAILABLE", "error": type(exc).__name__, "source": CFG["upstream"], "data": None}


@app.get("/healthz")
def healthz():
    return {"ok": True, "product": CFG["title"], "source": CFG["source"]}


@app.get("/api/live")
def live():
    return read_upstream()


@app.get("/api/source")
def source():
    return CFG


@app.get("/", response_class=HTMLResponse)
def root():
    return INDEX
'''

DOCKER = '''FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py config.json index.html ./
EXPOSE 7860
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","7860"]
'''
REQ = "fastapi==0.116.1\nuvicorn[standard]==0.35.0\nhttpx==0.28.1\n"


def html(cfg: dict[str, str]) -> str:
    title = cfg["title"]
    vertical = cfg["vertical"]
    source = cfg["source"]
    product = cfg["product"]
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} - SZL Holdings</title><meta name="description" content="{title}: governed {vertical.lower()} from SZL Holdings">
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#030405;color:#f5f7fa;font:15px Inter,system-ui,sans-serif;min-height:100vh}}body:before{{content:"";position:fixed;inset:0;background:radial-gradient(circle at 75% 10%,rgba(90,180,255,.12),transparent 34%),linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:auto,32px 32px,32px 32px;pointer-events:none}}main{{max-width:1180px;margin:auto;padding:42px 22px 70px;position:relative}}nav{{display:flex;justify-content:space-between;align-items:center;gap:15px;margin-bottom:70px}}.brand{{font-weight:800;letter-spacing:.14em}}.pill{{border:1px solid #2b3139;border-radius:999px;padding:8px 12px;color:#aab4c0;font:12px ui-monospace,monospace}}h1{{font-size:clamp(48px,8vw,104px);line-height:.92;margin:0 0 20px;letter-spacing:-.06em}}.k{{color:#7dd3fc;font:12px ui-monospace,monospace;letter-spacing:.17em}}.lede{{max-width:760px;color:#a9b2bc;font-size:19px;line-height:1.65}}.grid{{display:grid;grid-template-columns:1.3fr .7fr;gap:18px;margin-top:38px}}.card{{border:1px solid #252b32;background:rgba(10,12,15,.78);border-radius:18px;padding:22px;box-shadow:0 18px 60px rgba(0,0,0,.25)}}.status{{display:flex;align-items:center;gap:9px;font:12px ui-monospace,monospace}}.dot{{width:9px;height:9px;border-radius:50%;background:#64748b}}.live .dot{{background:#7dd3fc;box-shadow:0 0 18px #7dd3fc}}pre{{white-space:pre-wrap;word-break:break-word;color:#cbd5e1;font:12px/1.6 ui-monospace,monospace;max-height:420px;overflow:auto}}a{{color:#e9f6ff}}button{{background:#f5f7fa;color:#050607;border:0;border-radius:10px;padding:11px 16px;min-height:44px;font-weight:750;cursor:pointer}}.meta{{display:grid;gap:12px;color:#97a3af;font-size:13px}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}nav{{margin-bottom:44px}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important;transition:none!important}}}}
</style></head><body><main><nav><div class="brand">SZL HOLDINGS</div><div class="pill">A11OY / EVIDENCE-BEARING VERTICAL</div></nav><div class="k">{vertical}</div><h1>{title}</h1><p class="lede">A flagship vertical surface backed by SZL's governed runtime. Live upstream evidence is rendered when reachable; missing evidence remains <b>UNAVAILABLE</b> rather than fabricated.</p><div class="grid"><section class="card"><div id="st" class="status"><span class="dot"></span><span>PROBING</span></div><pre id="out">Loading governed live feed...</pre><button type="button" onclick="load()">Refresh evidence</button></section><aside class="card meta"><b>Canonical source</b><a href="{source}" target="_blank" rel="noopener">{source}</a><b>Product portfolio</b><a href="{product}" target="_blank" rel="noopener">a-11-oy.com/products/</a><b>Evidence doctrine</b><span>MEASURED / REPORTED / MODELED / UNAVAILABLE remain distinct.</span></aside></div></main><script>async function load(){{const st=document.getElementById('st'),out=document.getElementById('out');try{{const r=await fetch('/api/live',{{cache:'no-store'}}),j=await r.json();st.className='status '+(j.status==='LIVE'?'live':'');st.children[1].textContent=j.status+' / '+(j.latency_ms??'-')+' ms';out.textContent=JSON.stringify(j,null,2)}}catch(e){{st.children[1].textContent='UNAVAILABLE';out.textContent=String(e)}}}}load();setInterval(load,60000)</script></body></html>'''


def readme(cfg: dict[str, str]) -> str:
    return f'''---
title: {cfg["title"]}
emoji: diamond_shape_with_a_dot_inside
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
pinned: true
---

# {cfg["title"]}

**{cfg["vertical"]}** flagship for SZL Holdings.

Canonical source: {cfg["source"]}

Product portfolio: {cfg["product"]}

This Space is a deployment/discovery surface. Runtime claims are sourced from the named live upstream and fail closed to `UNAVAILABLE`.
'''


def main() -> int:
    token, token_source = token_from_env()
    api = HfApi(token=token)
    receipt: dict[str, Any] = {
        "schema": "szl.hf-vertical-flagships/v1",
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "token_source": token_source,
        "spaces": [],
    }
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for cfg in FLAGSHIPS:
            rid = f'{ORG}/{cfg["slug"]}'
            directory = root / cfg["slug"]
            directory.mkdir()
            (directory / "app.py").write_text(APP, encoding="utf-8")
            (directory / "Dockerfile").write_text(DOCKER, encoding="utf-8")
            (directory / "requirements.txt").write_text(REQ, encoding="utf-8")
            (directory / "config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
            (directory / "index.html").write_text(html(cfg), encoding="utf-8")
            (directory / "README.md").write_text(readme(cfg), encoding="utf-8")
            item: dict[str, Any] = {"id": rid, "source": cfg["source"], "upstream": cfg["upstream"], "actions": []}
            try:
                api.create_repo(repo_id=rid, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
                item["actions"].append("ensure_public_docker_space")
                api.upload_folder(repo_id=rid, repo_type="space", folder_path=str(directory), commit_message="feat: publish governed SZL vertical flagship")
                item["actions"].append("publish_source")
                try:
                    api.update_repo_settings(repo_id=rid, repo_type="space", private=False)
                except Exception as exc:
                    item["visibility_note"] = type(exc).__name__
                try:
                    api.restart_space(rid)
                    item["actions"].append("restart")
                except Exception as exc:
                    item["restart_note"] = type(exc).__name__
                deadline = time.time() + 360
                while time.time() < deadline:
                    try:
                        stage = str(api.get_space_runtime(rid).stage or "UNKNOWN").upper()
                        item["stage"] = stage
                        if stage == "RUNNING" or "ERROR" in stage:
                            break
                    except Exception as exc:
                        item["stage_error"] = type(exc).__name__
                    time.sleep(10)
                item["ok"] = item.get("stage") == "RUNNING"
            except Exception as exc:
                item.update(ok=False, error=type(exc).__name__)
            receipt["spaces"].append(item)
    receipt["ok"] = all(x.get("ok") for x in receipt["spaces"])
    Path("hf-vertical-flagships-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": receipt["ok"], "spaces": [{"id": x["id"], "stage": x.get("stage"), "ok": x.get("ok")} for x in receipt["spaces"]]}, indent=2))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
