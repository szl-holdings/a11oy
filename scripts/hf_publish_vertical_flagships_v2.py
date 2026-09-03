#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish and live-verify the six SZLHOLDINGS vertical flagship Spaces.

The publisher is revision-bound to the checked-out A11oy source. It updates only
Space source files, keeps visibility and hardware unchanged, restarts each
runtime, and fails closed unless every root is RUNNING, HTTP 200, and exposes
the Public Experience v3 marker.
"""
from __future__ import annotations

import datetime as dt
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
PUBLIC_EXPERIENCE_VERSION = "3.0.0"
PUBLIC_EXPERIENCE_MARKER = 'data-szl-public-experience-v3="true"'
USER_AGENT = "SZLHOLDINGS-Vertical-Publisher/3.0"

FLAGSHIPS: tuple[dict[str, str], ...] = (
    {
        "slug": "terra",
        "title": "Terra",
        "vertical": "REAL ESTATE INTELLIGENCE",
        "source": "https://github.com/szl-holdings/szl-real-estate",
        "upstream": f"{A11OY}/api/a11oy/v1/vert/realestate/feed",
    },
    {
        "slug": "sentra",
        "title": "Sentra",
        "vertical": "CYBERSECURITY INTELLIGENCE",
        "source": "https://github.com/szl-holdings/szl-defensive-control-plane",
        "upstream": f"{A11OY}/api/a11oy/v1/vert/cyber/feed",
    },
    {
        "slug": "counsel",
        "title": "PRISM Counsel",
        "vertical": "LEGAL MATTER INTELLIGENCE",
        "source": "https://github.com/szl-holdings/a11oy/tree/main/verticals/counsel",
        "upstream": f"{A11OY}/api/a11oy/v1/vert/legal/feed",
    },
    {
        "slug": "finance",
        "title": "PURIQ Finance",
        "vertical": "FINANCIAL INTELLIGENCE",
        "source": "https://github.com/szl-holdings/puriq-live",
        "upstream": f"{A11OY}/api/a11oy/v1/vert/finance/feed",
    },
    {
        "slug": "vessels",
        "title": "Vessels",
        "vertical": "MARITIME INTELLIGENCE",
        "source": "https://github.com/szl-holdings/a11oy/tree/main/verticals/vessels",
        "upstream": f"{KILLINCHU}/api/killinchu/v1/maritime/risk/fleet",
    },
    {
        "slug": "lyte",
        "title": "Lyte",
        "vertical": "BUSINESS OBSERVABILITY",
        "source": "https://github.com/szl-holdings/lyte-lattice",
        "upstream": f"{A11OY}/api/a11oy/v1/observability/summary",
    },
)

APP = '''import json,time\nfrom pathlib import Path\nimport httpx\nfrom fastapi import FastAPI\nfrom fastapi.responses import HTMLResponse\nCFG=json.loads(Path("config.json").read_text())\nINDEX=Path("index.html").read_text()\napp=FastAPI(title=CFG["title"]+" - SZL Holdings")\n\ndef probe():\n    started=time.time()\n    try:\n        r=httpx.get(CFG["upstream"],timeout=15,headers={"User-Agent":"SZLHOLDINGS-Flagship/3.0"})\n        body=r.json() if "json" in r.headers.get("content-type","") else {"text":r.text[:4000]}\n        return {"status":"LIVE" if r.is_success else "UNAVAILABLE","http_status":r.status_code,"latency_ms":round((time.time()-started)*1000,1),"source":CFG["upstream"],"data":body}\n    except Exception as exc:\n        return {"status":"UNAVAILABLE","error":type(exc).__name__,"source":CFG["upstream"],"data":None}\n\n@app.get("/healthz")\ndef healthz(): return {"ok":True,"product":CFG["title"],"source":CFG["source"],"public_experience":CFG["public_experience"]}\n@app.get("/api/live")\ndef live(): return probe()\n@app.get("/api/source")\ndef source(): return CFG\n@app.get("/api/build-info")\ndef build_info(): return {"git_sha":CFG["source_revision"],"source":CFG["source"],"public_experience":CFG["public_experience"]}\n@app.get("/",response_class=HTMLResponse)\ndef root(): return INDEX\n'''

DOCKER = '''FROM python:3.12-slim\nENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY app.py config.json index.html ./\nEXPOSE 7860\nCMD ["uvicorn","app:app","--host","0.0.0.0","--port","7860"]\n'''

REQ = "fastapi==0.116.1\nuvicorn[standard]==0.35.0\nhttpx==0.28.1\n"

HTML_TEMPLATE = '''<!doctype html>
<html lang="en" data-szl-public-experience-v3="true">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ - SZL Holdings</title>
<style>
html,body{max-width:100%;overflow-x:hidden}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:#030405;color:#f5f7fa;font:15px Inter,system-ui,sans-serif;min-height:100vh}
body::before{content:"";position:fixed;inset:0;background:radial-gradient(circle at 75% 8%,rgba(86,180,255,.14),transparent 32%),linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:auto,32px 32px,32px 32px;pointer-events:none}
main{width:min(100%,1180px);margin:auto;padding:42px 22px 72px;position:relative;min-width:0}
nav{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;margin-bottom:72px}
.brand{font-weight:850;letter-spacing:.14em}.tag,.k{font:12px ui-monospace,monospace;letter-spacing:.12em}.tag{border:1px solid #29313a;border-radius:999px;padding:12px;color:#aab4c0}.k{color:#7dd3fc;margin-bottom:14px}
h1{font-size:clamp(42px,9vw,112px);line-height:.9;letter-spacing:-.06em;margin:0 0 24px;overflow-wrap:anywhere}.lede{max-width:760px;color:#a9b2bc;font-size:19px;line-height:1.65;overflow-wrap:anywhere}
.grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,.65fr);gap:18px;margin-top:40px;min-width:0}.card{min-width:0;border:1px solid #252c34;background:rgba(9,12,15,.82);border-radius:18px;padding:22px;overflow:hidden}.status{display:flex;gap:9px;align-items:center;font:12px ui-monospace,monospace}.dot{width:9px;height:9px;border-radius:50%;background:#64748b}.live .dot{background:#7dd3fc;box-shadow:0 0 18px #7dd3fc}
pre{width:100%;max-width:100%;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;color:#cbd5e1;font:12px/1.6 ui-monospace,monospace;max-height:440px;overflow:auto}a{display:inline-flex;align-items:center;min-height:44px;max-width:100%;color:#e9f6ff;overflow-wrap:anywhere;word-break:break-word}button{min-width:44px;min-height:44px;border:0;border-radius:10px;padding:11px 16px;background:#f5f7fa;color:#050607;font-weight:750}.meta{display:grid;gap:13px;color:#97a3af;font-size:13px;min-width:0}
@media(max-width:760px){.grid{grid-template-columns:minmax(0,1fr)}nav{margin-bottom:44px}}
@media(max-width:420px){main{padding:30px 16px 56px}.card{padding:16px}h1{font-size:clamp(38px,16vw,64px)}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
</style>
</head>
<body>
<main>
<nav><div class="brand">SZL HOLDINGS</div><div class="tag">A11OY / FLAGSHIP VERTICAL</div></nav>
<div class="k">__VERTICAL__</div>
<h1>__TITLE__</h1>
<p class="lede">A governed vertical interface over the SZL evidence fabric. The live panel reports observed upstream data when reachable and remains <b>UNAVAILABLE</b> when evidence cannot be obtained.</p>
<div class="grid">
<section class="card"><div id="st" class="status"><span class="dot"></span><span>PROBING</span></div><pre id="out">Loading governed evidence...</pre><button type="button" onclick="load()">Refresh evidence</button></section>
<aside class="card meta"><b>Canonical source</b><a href="__SOURCE__" target="_blank" rel="noopener">__SOURCE__</a><b>Product portfolio</b><a href="https://a-11-oy.com/products/" target="_blank" rel="noopener">a-11-oy.com/products/</a><b>Truth vocabulary</b><span>MEASURED / REPORTED / MODELED / UNAVAILABLE are never collapsed into one claim.</span></aside>
</div>
</main>
<script>
async function load(){const s=document.getElementById('st'),o=document.getElementById('out');try{const r=await fetch('/api/live',{cache:'no-store'}),j=await r.json();s.className='status '+(j.status==='LIVE'?'live':'');s.children[1].textContent=j.status+' / '+(j.latency_ms??'-')+' ms';o.textContent=JSON.stringify(j,null,2)}catch(e){s.children[1].textContent='UNAVAILABLE';o.textContent=String(e)}}
load();setInterval(load,60000)
</script>
</body>
</html>
'''


def token_from_env() -> tuple[str, str]:
    for name in (
        "HF_ORG_TOKEN",
        "HF_WRITE_TOKEN",
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
        "HUGGING_FACE_HUB_TOKEN",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    raise RuntimeError("no Hugging Face write token available")


def html(title: str, vertical: str, source: str) -> str:
    return (
        HTML_TEMPLATE.replace("__TITLE__", title)
        .replace("__VERTICAL__", vertical)
        .replace("__SOURCE__", source)
    )


def readme(title: str, vertical: str, source: str) -> str:
    return f'''---\ntitle: {title}\nemoji: 🛰️\ncolorFrom: gray\ncolorTo: blue\nsdk: docker\napp_port: 7860\npinned: true\n---\n\n# {title}\n\n{vertical} flagship for SZL Holdings.\n\nCanonical source: {source}\n\nPortfolio: https://a-11-oy.com/products/\n\nPublic Experience: `{PUBLIC_EXPERIENCE_VERSION}`. Runtime claims fail closed to `UNAVAILABLE`.\n'''


def upload_text(api: HfApi, repo_id: str, path: str, content: str) -> None:
    api.upload_file(
        path_or_fileobj=content.encode("utf-8"),
        path_in_repo=path,
        repo_id=repo_id,
        repo_type="space",
        commit_message=f"feat(public-experience): publish {path}",
    )


def probe_root(slug: str, *, timeout: int = 20) -> dict[str, Any]:
    url = f"https://szlholdings-{slug}.hf.space/"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {
                "url": url,
                "http_status": response.status,
                "v3_marker": PUBLIC_EXPERIENCE_MARKER in body,
            }
    except urllib.error.HTTPError as exc:
        return {"url": url, "http_status": exc.code, "v3_marker": False}
    except Exception as exc:  # provider transport failures are recorded, not hidden
        return {
            "url": url,
            "http_status": None,
            "v3_marker": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    token, token_source = token_from_env()
    api = HfApi(token=token)
    source_revision = os.getenv("GITHUB_SHA", "UNAVAILABLE").strip() or "UNAVAILABLE"
    rows: list[dict[str, Any]] = []

    for item in FLAGSHIPS:
        slug = item["slug"]
        rid = f"{ORG}/{slug}"
        row: dict[str, Any] = {
            "id": rid,
            "source": item["source"],
            "upstream": item["upstream"],
            "source_revision": source_revision,
            "actions": [],
        }
        try:
            api.create_repo(
                repo_id=rid,
                repo_type="space",
                space_sdk="docker",
                exist_ok=True,
                private=False,
            )
            row["actions"].append("ensure_space")
            config = json.dumps(
                {
                    "title": item["title"],
                    "vertical": item["vertical"],
                    "source": item["source"],
                    "upstream": item["upstream"],
                    "source_revision": source_revision,
                    "public_experience": PUBLIC_EXPERIENCE_VERSION,
                },
                indent=2,
                sort_keys=True,
            ) + "\n"
            payloads = (
                ("app.py", APP),
                ("Dockerfile", DOCKER),
                ("requirements.txt", REQ),
                ("config.json", config),
                ("index.html", html(item["title"], item["vertical"], item["source"])),
                ("README.md", readme(item["title"], item["vertical"], item["source"])),
            )
            for path, payload in payloads:
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

    stage_deadline = time.time() + 600
    pending = {row["id"] for row in rows if "error" not in row}
    while pending and time.time() < stage_deadline:
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

    root_deadline = time.time() + 300
    pending_roots = {
        row["id"]
        for row in rows
        if "error" not in row and row.get("stage") == "RUNNING"
    }
    while pending_roots and time.time() < root_deadline:
        for row in rows:
            if row["id"] not in pending_roots:
                continue
            slug = row["id"].split("/", 1)[1]
            root = probe_root(slug)
            row["root"] = root
            if root.get("http_status") == 200 and root.get("v3_marker") is True:
                pending_roots.discard(row["id"])
        if pending_roots:
            time.sleep(10)

    for row in rows:
        root = row.get("root") if isinstance(row.get("root"), dict) else {}
        row["ok"] = (
            row.get("stage") == "RUNNING"
            and root.get("http_status") == 200
            and root.get("v3_marker") is True
        )

    receipt = {
        "schema": "szl.hf-vertical-flagships/v3",
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "token_source": token_source,
        "source_revision": source_revision,
        "public_experience": PUBLIC_EXPERIENCE_VERSION,
        "ok": all(row["ok"] for row in rows),
        "spaces": rows,
    }
    Path("hf-vertical-flagships-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": receipt["ok"],
                "source_revision": source_revision,
                "spaces": [
                    {
                        "id": row["id"],
                        "stage": row.get("stage"),
                        "root": row.get("root"),
                        "ok": row["ok"],
                        "error": row.get("error"),
                    }
                    for row in rows
                ],
            },
            indent=2,
        )
    )
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
