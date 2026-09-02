#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Create/publish the six missing SZLHOLDINGS vertical flagship Spaces."""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

ORG = "SZLHOLDINGS"
A11OY = "https://szlholdings-a11oy.hf.space"
KILLINCHU = "https://szlholdings-killinchu.hf.space"
FLAGSHIPS = [
    ("terra", "Terra", "REAL ESTATE INTELLIGENCE", "https://github.com/szl-holdings/szl-real-estate", f"{A11OY}/api/a11oy/v1/vert/realestate/feed"),
    ("sentra", "Sentra", "CYBERSECURITY INTELLIGENCE", "https://github.com/szl-holdings/szl-defensive-control-plane", f"{A11OY}/api/a11oy/v1/vert/cyber/feed"),
    ("counsel", "PRISM Counsel", "LEGAL MATTER INTELLIGENCE", "https://github.com/szl-holdings/counsel", f"{A11OY}/api/a11oy/v1/vert/legal/feed"),
    ("finance", "PURIQ Finance", "FINANCIAL INTELLIGENCE", "https://github.com/szl-holdings/puriq-live", f"{A11OY}/api/a11oy/v1/vert/finance/feed"),
    ("vessels", "Vessels", "MARITIME INTELLIGENCE", "https://github.com/szl-holdings/szl-fleet-overlay", f"{KILLINCHU}/api/killinchu/v1/maritime/risk/fleet"),
    ("lyte", "Lyte", "BUSINESS OBSERVABILITY", "https://github.com/szl-holdings/lyte-lattice", f"{A11OY}/api/a11oy/v1/observability/summary"),
]

APP = '''import json,time\nfrom pathlib import Path\nimport httpx\nfrom fastapi import FastAPI\nfrom fastapi.responses import HTMLResponse\nCFG=json.loads(Path("config.json").read_text())\nINDEX=Path("index.html").read_text()\napp=FastAPI(title=CFG["title"]+" - SZL Holdings")\n\ndef probe():\n    started=time.time()\n    try:\n        r=httpx.get(CFG["upstream"],timeout=15,headers={"User-Agent":"SZLHOLDINGS-Flagship/1.0"})\n        body=r.json() if "json" in r.headers.get("content-type","") else {"text":r.text[:4000]}\n        return {"status":"LIVE" if r.is_success else "UNAVAILABLE","http_status":r.status_code,"latency_ms":round((time.time()-started)*1000,1),"source":CFG["upstream"],"data":body}\n    except Exception as exc:\n        return {"status":"UNAVAILABLE","error":type(exc).__name__,"source":CFG["upstream"],"data":None}\n\n@app.get("/healthz")\ndef healthz(): return {"ok":True,"product":CFG["title"],"source":CFG["source"]}\n@app.get("/api/live")\ndef live(): return probe()\n@app.get("/api/source")\ndef source(): return CFG\n@app.get("/",response_class=HTMLResponse)\ndef root(): return INDEX\n'''

DOCKER = '''FROM python:3.12-slim\nENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY app.py config.json index.html ./\nEXPOSE 7860\nCMD ["uvicorn","app:app","--host","0.0.0.0","--port","7860"]\n'''
REQ = "fastapi==0.116.1\nuvicorn[standard]==0.35.0\nhttpx==0.28.1\n"


def token_from_env() -> tuple[str, str]:
    for name in ("HF_ORG_TOKEN", "HF_WRITE_TOKEN", "HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    raise RuntimeError("no Hugging Face write token available")


def html(title: str, vertical: str, source: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} - SZL Holdings</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#030405;color:#f5f7fa;font:15px Inter,system-ui,sans-serif;min-height:100vh}}body:before{{content:"";position:fixed;inset:0;background:radial-gradient(circle at 75% 8%,rgba(86,180,255,.14),transparent 32%),linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:auto,32px 32px,32px 32px;pointer-events:none}}main{{max-width:1180px;margin:auto;padding:42px 22px 72px;position:relative}}nav{{display:flex;justify-content:space-between;gap:16px;margin-bottom:72px}}.brand{{font-weight:850;letter-spacing:.14em}}.tag,.k{{font:12px ui-monospace,monospace;letter-spacing:.12em}}.tag{{border:1px solid #29313a;border-radius:999px;padding:8px 12px;color:#aab4c0}}.k{{color:#7dd3fc;margin-bottom:14px}}h1{{font-size:clamp(52px,9vw,112px);line-height:.9;letter-spacing:-.06em;margin:0 0 24px}}.lede{{max-width:760px;color:#a9b2bc;font-size:19px;line-height:1.65}}.grid{{display:grid;grid-template-columns:1.35fr .65fr;gap:18px;margin-top:40px}}.card{{border:1px solid #252c34;background:rgba(9,12,15,.82);border-radius:18px;padding:22px}}.status{{display:flex;gap:9px;align-items:center;font:12px ui-monospace,monospace}}.dot{{width:9px;height:9px;border-radius:50%;background:#64748b}}.live .dot{{background:#7dd3fc;box-shadow:0 0 18px #7dd3fc}}pre{{white-space:pre-wrap;word-break:break-word;color:#cbd5e1;font:12px/1.6 ui-monospace,monospace;max-height:440px;overflow:auto}}a{{color:#e9f6ff}}button{{min-height:44px;border:0;border-radius:10px;padding:11px 16px;background:#f5f7fa;color:#050607;font-weight:750}}.meta{{display:grid;gap:13px;color:#97a3af;font-size:13px}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}nav{{margin-bottom:44px}}}}@media(prefers-reduced-motion:reduce){{*{{transition:none!important}}}}</style></head><body><main><nav><div class="brand">SZL HOLDINGS</div><div class="tag">A11OY / FLAGSHIP VERTICAL</div></nav><div class="k">{vertical}</div><h1>{title}</h1><p class="lede">A governed vertical interface over the SZL evidence fabric. The live panel reports observed upstream data when reachable and remains <b>UNAVAILABLE</b> when evidence cannot be obtained.</p><div class="grid"><section class="card"><div id="st" class="status"><span class="dot"></span><span>PROBING</span></div><pre id="out">Loading governed evidence...</pre><button onclick="load()">Refresh evidence</button></section><aside class="card meta"><b>Canonical source</b><a href="{source}" target="_blank" rel="noopener">{source}</a><b>Product portfolio</b><a href="https://a-11-oy.com/products/" target="_blank" rel="noopener">a-11-oy.com/products/</a><b>Truth vocabulary</b><span>MEASURED / REPORTED / MODELED / UNAVAILABLE are never collapsed into one claim.</span></aside></div></main><script>async function load(){{const s=document.getElementById('st'),o=document.getElementById('out');try{{const r=await fetch('/api/live',{{cache:'no-store'}}),j=await r.json();s.className='status '+(j.status==='LIVE'?'live':'');s.children[1].textContent=j.status+' / '+(j.latency_ms??'-')+' ms';o.textContent=JSON.stringify(j,null,2)}}catch(e){{s.children[1].textContent='UNAVAILABLE';o.textContent=String(e)}}}}load();setInterval(load,60000)</script></body></html>'''


def readme(title: str, vertical: str, source: str) -> str:
    return f'''---\ntitle: {title}\nemoji: 🛰️\ncolorFrom: gray\ncolorTo: blue\nsdk: docker\napp_port: 7860\npinned: true\n---\n\n# {title}\n\n{vertical} flagship for SZL Holdings.\n\nCanonical source: {source}\n\nPortfolio: https://a-11-oy.com/products/\n\nRuntime claims fail closed to `UNAVAILABLE`.\n'''


def upload_text(api: HfApi, repo_id: str, path: str, content: str) -> None:
    api.upload_file(path_or_fileobj=content.encode("utf-8"), path_in_repo=path, repo_id=repo_id, repo_type="space", commit_message=f"feat: publish {path}")


def main() -> int:
    token, token_source = token_from_env()
    api = HfApi(token=token)
    rows: list[dict[str, Any]] = []
    for slug, title, vertical, source, upstream in FLAGSHIPS:
        rid = f"{ORG}/{slug}"
        row: dict[str, Any] = {"id": rid, "source": source, "upstream": upstream, "actions": []}
        try:
            api.create_repo(repo_id=rid, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
            row["actions"].append("ensure_space")
            config = json.dumps({"title": title, "vertical": vertical, "source": source, "upstream": upstream}, indent=2) + "\n"
            for path, payload in (("app.py", APP), ("Dockerfile", DOCKER), ("requirements.txt", REQ), ("config.json", config), ("index.html", html(title, vertical, source)), ("README.md", readme(title, vertical, source))):
                upload_text(api, rid, path, payload)
            row["actions"].append("publish_source")
            try:
                api.update_repo_settings(repo_id=rid, repo_type="space", private=False)
            except Exception as exc:
                row["visibility_note"] = f"{type(exc).__name__}: {exc}"
            try:
                api.restart_space(rid)
                row["actions"].append("restart")
            except Exception as exc:
                row["restart_note"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)

    deadline = time.time() + 600
    pending = {row["id"] for row in rows if "error" not in row}
    while pending and time.time() < deadline:
        for row in rows:
            if row["id"] not in pending:
                continue
            try:
                stage = str(api.get_space_runtime(row["id"]).stage or "UNKNOWN").upper()
                row["stage"] = stage
                if stage == "RUNNING" or "ERROR" in stage:
                    pending.discard(row["id"])
            except Exception as exc:
                row["stage_note"] = f"{type(exc).__name__}: {exc}"
        if pending:
            time.sleep(10)

    for row in rows:
        row["ok"] = row.get("stage") == "RUNNING"
    receipt = {"schema": "szl.hf-vertical-flagships/v2", "at": dt.datetime.now(dt.timezone.utc).isoformat(), "token_source": token_source, "ok": all(r["ok"] for r in rows), "spaces": rows}
    Path("hf-vertical-flagships-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": receipt["ok"], "spaces": [{"id": r["id"], "stage": r.get("stage"), "ok": r["ok"], "error": r.get("error")} for r in rows]}, indent=2))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
