# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v10/v11
"""
szl_rag — shared agentic-RAG service, deployed identically on every live-Python SZL Space.

Pipeline (per Space, organ-filtered):
    embed(query)  ->  FAISS lookup (organ index)  ->  top-k chunks (similarity + source)
    if with_response:  top-k  ->  LLM tier (szl_brain.route)  ->  answer + sources + Λ-receipt

Corpus + per-organ FAISS indexes are pulled from the HF Dataset
    SZLHOLDINGS/rag-corpus-v1
via huggingface_hub.snapshot_download at first use (lazy, cached).

Each Space binds ONE organ:
    a11oy -> gate · amaru -> cortex · sentra -> immune · vessels -> receipt
    rosie -> all (nervous inherits everything) · uds-demo -> deploy(-> all fallback)

HONESTY (Doctrine v10/v11):
  - LLM responses cite chunk IDs (the `sources` list carries every chunk_id used).
  - Λ-receipt `signature` field is a PLACEHOLDER (Sigstore CI signing not yet wired).
  - If the embedding model / FAISS deps / dataset download are unavailable in this
    Space at runtime, the endpoint returns an HONEST JSON error (never fake chunks).
  - ADDITIVE only. The 13-axis `yuyay_v3` axis_scores feed szl_brain tier selection.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

# Module-level FastAPI imports. REQUIRED: with `from __future__ import annotations`
# the `request: Request` endpoint annotation is a STRING that FastAPI resolves
# against module globals at route-registration time. If Request is only imported
# inside register_rag_routes(), resolution fails and FastAPI wrongly treats
# `request` as a required query param (HTTP 422). Importing here fixes the bind.
try:
    from fastapi import Request as Request  # noqa: F401
    from fastapi.responses import JSONResponse as JSONResponse, HTMLResponse as HTMLResponse  # noqa: F401
except Exception:  # fastapi optional at import time in non-serving contexts
    Request = None  # type: ignore

DOCTRINE = "v10/v11"
DATASET_REPO = "SZLHOLDINGS/rag-corpus-v1"
MODEL_NAME = "BAAI/bge-base-en-v1.5"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
SIGNATURE_PLACEHOLDER = "PLACEHOLDER — Sigstore CI signing not yet wired (Doctrine v10/v11)"

# organ each Space binds. uds-demo is deploy; no 'deploy' index exists, fall back to all.
SPACE_ORGAN = {
    "a11oy": "gate",
    "amaru": "cortex",
    "sentra": "immune",
    "vessels": "receipt",
    "rosie": "all",
    "uds-demo": "all",   # deploy organ -> served from the all index
}

# ---------------------------------------------------------------------------
# Lazy global state — loaded once per process.
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_state: dict[str, Any] = {
    "ready": False,
    "error": None,
    "model": None,
    "corpus": None,        # chunk_id -> chunk dict
    "indexes": {},         # organ -> (faiss_index, [chunk_id,...])
    "manifest": None,
    "dataset_dir": None,
}


def _ensure_loaded() -> None:
    """Lazily download dataset + load model + FAISS indexes. Thread-safe, idempotent."""
    if _state["ready"] or _state["error"]:
        return
    with _lock:
        if _state["ready"] or _state["error"]:
            return
        try:
            from huggingface_hub import snapshot_download
            import faiss  # noqa
            from sentence_transformers import SentenceTransformer

            ddir = snapshot_download(DATASET_REPO, repo_type="dataset")
            _state["dataset_dir"] = ddir

            corpus = {}
            with open(os.path.join(ddir, "corpus.jsonl")) as f:
                for line in f:
                    c = json.loads(line)
                    corpus[c["chunk_id"]] = c
            _state["corpus"] = corpus

            manifest = json.load(open(os.path.join(ddir, "indexes", "manifest.json")))
            _state["manifest"] = manifest

            indexes = {}
            for organ, meta in manifest["organs"].items():
                if meta.get("n", 0) == 0:
                    continue
                idx = faiss.read_index(os.path.join(ddir, "indexes", f"{organ}.faiss"))
                ids = json.load(open(os.path.join(ddir, "indexes", f"{organ}.ids.json")))
                indexes[organ] = (idx, ids)
            _state["indexes"] = indexes

            _state["model"] = SentenceTransformer(MODEL_NAME, device="cpu")
            _state["ready"] = True
            print(f"[szl_rag] READY — {len(corpus)} chunks, organs={list(indexes)}",
                  flush=True)
        except Exception as exc:  # honest degradation, never fake data
            _state["error"] = f"{type(exc).__name__}: {exc}"
            print(f"[szl_rag] NOT READY (honest stub mode): {_state['error']}", flush=True)


def status(space: str) -> dict[str, Any]:
    organ = SPACE_ORGAN.get(space, "all")
    return {
        "service": "szl_rag",
        "space": space,
        "organ": organ,
        "ready": _state["ready"],
        "error": _state["error"],
        "dataset": DATASET_REPO,
        "model": MODEL_NAME,
        "doctrine": DOCTRINE,
        "n_chunks": (len(_state["corpus"]) if _state["corpus"] else None),
        "manifest": _state["manifest"],
        "honesty": {
            "lambda_receipt_signature": SIGNATURE_PLACEHOLDER,
            "llm_responses_cite_chunk_ids": True,
            "no_fake_chunks": "If deps/dataset unavailable, endpoint returns honest error.",
        },
    }


def _make_lambda_receipt(query: str, organ: str, axis_scores, chunk_ids) -> dict[str, Any]:
    return {
        "schema": "szl.rag.lambda_receipt/v1",
        "query": query,
        "organ": organ,
        "axis_scores": axis_scores or [],
        "chunk_ids": chunk_ids,            # honesty: every chunk used is cited
        "doctrine": DOCTRINE,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "signature": SIGNATURE_PLACEHOLDER,
    }


def search(query: str, space: str, top_k: int = 5,
           axis_scores: list[float] | None = None) -> dict[str, Any]:
    """Embed query -> FAISS lookup (organ-filtered) -> top-k chunks + similarity + sources."""
    _ensure_loaded()
    organ = SPACE_ORGAN.get(space, "all")
    if not _state["ready"]:
        return {
            "ok": False,
            "honest_error": _state["error"] or "rag not initialized",
            "detail": ("Embedding model / FAISS deps / dataset are not available in this "
                       "Space runtime. Returning honest error instead of fake chunks "
                       "(Doctrine v10/v11)."),
            "space": space, "organ": organ, "query": query, "doctrine": DOCTRINE,
        }
    if organ not in _state["indexes"]:
        organ = "all"
    idx, ids = _state["indexes"][organ]
    top_k = max(1, min(int(top_k or 5), 20))

    import numpy as np
    qe = _state["model"].encode([BGE_QUERY_PREFIX + query],
                                normalize_embeddings=True,
                                convert_to_numpy=True).astype("float32")
    k = min(top_k, len(ids))
    D, I = idx.search(qe, k)
    results = []
    for sim, row in zip(D[0].tolist(), I[0].tolist()):
        if row < 0:
            continue
        c = _state["corpus"][ids[row]]
        results.append({
            "chunk_id": c["chunk_id"],
            "similarity": round(float(sim), 6),
            "organ_tag": c["organ_tag"],
            "title": c.get("title", ""),
            "source": c["source"],
            "text": c["text"],
        })
    return {
        "ok": True,
        "space": space,
        "organ": organ,
        "query": query,
        "top_k": top_k,
        "count": len(results),
        "chunks": results,
        "sources": [{"chunk_id": r["chunk_id"], "source": r["source"],
                     "title": r["title"], "similarity": r["similarity"]} for r in results],
        "doctrine": DOCTRINE,
        "lambda_receipt": _make_lambda_receipt(query, organ, axis_scores,
                                               [r["chunk_id"] for r in results]),
    }


def rag(query: str, space: str, top_k: int = 5, with_response: bool = False,
        axis_scores: list[float] | None = None) -> dict[str, Any]:
    """Full agentic-RAG. with_response=True passes top-k to the LLM tier (szl_brain.route)."""
    out = search(query, space, top_k=top_k, axis_scores=axis_scores)
    if not out.get("ok") or not with_response:
        return out

    # Build a grounded prompt; honesty: instruct the model to cite chunk IDs.
    ctx_lines = []
    for r in out["chunks"]:
        ctx_lines.append(f"[chunk {r['chunk_id']} | {r['source']}]\n{r['text']}")
    context = "\n\n---\n\n".join(ctx_lines)
    prompt = (
        "You are an SZL Holdings agentic-RAG assistant. Answer the question using ONLY "
        "the retrieved chunks below. Cite the chunk_id in brackets for every claim. If the "
        "chunks do not contain the answer, say so honestly.\n\n"
        f"QUESTION: {query}\n\nRETRIEVED CHUNKS:\n{context}\n\nANSWER (cite chunk_ids):"
    )
    answer_block: dict[str, Any]
    try:
        import szl_brain as _brain
        routed = _brain.route(prompt, axis_scores=axis_scores, task_hint="research")
        answer_block = {
            "answer": routed.get("response"),
            "tier_used": routed.get("tier_used"),
            "tier_rank": routed.get("tier_rank"),
            "llm_lambda_receipt": routed.get("lambda_receipt"),
        }
    except Exception as exc:
        answer_block = {
            "answer": None,
            "honest_error": f"LLM router unavailable: {type(exc).__name__}: {exc}",
            "note": "Retrieval succeeded; generation tier not wired in this Space.",
        }
    out["with_response"] = True
    out["generation"] = answer_block
    # honesty: the answer must cite chunk_ids — we surface them explicitly too.
    out["cited_chunk_ids"] = [r["chunk_id"] for r in out["chunks"]]
    return out


# ---------------------------------------------------------------------------
# FastAPI route registration — additive, mounted before any catch-all.
# ---------------------------------------------------------------------------
def register_rag_routes(app, space: str, pages_dir: str | None = None) -> None:
    """Attach /api/<space>/v1/rag (POST+GET) and /rag UI (GET) to a FastAPI app."""
    from fastapi import Request
    from fastapi.responses import JSONResponse, HTMLResponse

    base = f"/api/{space}/v1/rag"

    @app.get(base)
    async def _rag_status() -> JSONResponse:  # noqa
        return JSONResponse(status(space))

    @app.post(base)
    async def _rag_query(request: Request) -> JSONResponse:  # noqa
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid JSON body",
                                 "example": {"query": "...", "top_k": 5,
                                             "with_response": False,
                                             "axis_scores": "[13 floats, optional]"}},
                                status_code=400)
        query = (body.get("query") or "").strip()
        if not query:
            return JSONResponse({"ok": False, "error": "missing 'query'"}, status_code=400)
        result = rag(
            query=query,
            space=space,
            top_k=body.get("top_k", 5),
            with_response=bool(body.get("with_response", False)),
            axis_scores=body.get("axis_scores"),
        )
        return JSONResponse(result)

    @app.get("/rag")
    async def _rag_ui() -> HTMLResponse:  # noqa
        return HTMLResponse(render_rag_html(space))


# ---------------------------------------------------------------------------
# /rag UI — single self-contained HTML page (search box + results + LLM toggle).
# ---------------------------------------------------------------------------
def render_rag_html(space: str) -> str:
    organ = SPACE_ORGAN.get(space, "all")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{space} — /rag · Agentic-RAG ({organ})</title>
<style>
:root{{--bg:#0b0e14;--fg:#e6e9ef;--mut:#8b94a7;--acc:#5ad1c4;--card:#141925;--bd:#222a3a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:920px;margin:0 auto;padding:28px 20px 80px}}
h1{{font-size:22px;margin:0 0 2px}}.sub{{color:var(--mut);font-size:13px;margin:0 0 18px}}
.bar{{display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
input[type=text]{{flex:1;min-width:240px;background:var(--card);color:var(--fg);
border:1px solid var(--bd);border-radius:10px;padding:11px 13px;font-size:15px}}
input[type=number]{{width:74px;background:var(--card);color:var(--fg);
border:1px solid var(--bd);border-radius:10px;padding:11px 9px}}
button{{background:var(--acc);color:#04211d;border:0;border-radius:10px;padding:11px 18px;
font-weight:600;cursor:pointer}}label.tog{{color:var(--mut);font-size:13px;
display:flex;align-items:center;gap:6px;cursor:pointer}}
.meta{{color:var(--mut);font-size:12px;margin:14px 0 6px}}
.card{{background:var(--card);border:1px solid var(--bd);border-radius:12px;
padding:14px 16px;margin:10px 0}}
.card h3{{margin:0 0 4px;font-size:14px}}.card .src{{color:var(--acc);font-size:12px}}
.card .sim{{float:right;color:var(--mut);font-size:12px}}
.card pre{{white-space:pre-wrap;word-break:break-word;margin:8px 0 0;font-size:13px;
color:#c7cede;max-height:230px;overflow:auto}}
.ans{{background:#10241f;border:1px solid #1f4a40}}
.err{{background:#241016;border:1px solid #4a1f28;color:#ffb3c0}}
.pill{{display:inline-block;background:#1c2436;border:1px solid var(--bd);
border-radius:999px;padding:2px 9px;font-size:11px;color:var(--mut);margin-right:6px}}
a{{color:var(--acc)}}
</style></head><body><div class="wrap">
<h1>{space} · /rag <span class="pill">organ: {organ}</span></h1>
<p class="sub">Agentic-RAG over <a href="https://huggingface.co/datasets/{DATASET_REPO}" target="_blank">{DATASET_REPO}</a>
· BGE-base-en-v1.5 (768-dim) · FAISS · Doctrine {DOCTRINE}.
LLM responses cite chunk IDs; Λ-receipt signature = PLACEHOLDER.</p>
<div class="bar">
  <input id="q" type="text" placeholder="Ask the {organ} corpus…"
   value="What does this Space prove and how is it governed?">
  <input id="k" type="number" min="1" max="20" value="5" title="top_k">
  <label class="tog"><input id="resp" type="checkbox"> LLM answer</label>
  <button id="go">Search</button>
</div>
<div class="meta" id="meta"></div>
<div id="out"></div>
<script>
const API="/api/{space}/v1/rag";
const out=document.getElementById('out'),meta=document.getElementById('meta');
function esc(s){{return (s||'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));}}
async function run(){{
  const q=document.getElementById('q').value.trim();if(!q)return;
  const k=parseInt(document.getElementById('k').value)||5;
  const wr=document.getElementById('resp').checked;
  meta.textContent='Searching…';out.innerHTML='';
  try{{
    const r=await fetch(API,{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{query:q,top_k:k,with_response:wr}})}});
    const d=await r.json();
    if(!d.ok){{meta.textContent='';out.innerHTML=
      '<div class="card err"><h3>Honest error</h3><pre>'+esc(d.honest_error||d.error)+
      '\\n\\n'+esc(d.detail||'')+'</pre></div>';return;}}
    meta.textContent='organ='+d.organ+' · '+d.count+' chunks · top_k='+d.top_k;
    let html='';
    if(d.generation){{
      const g=d.generation;
      html+='<div class="card ans"><h3>LLM answer'+(g.tier_used?(' · '+g.tier_used):'')+
        '</h3><pre>'+esc(g.answer||g.honest_error||'')+'</pre>'+
        '<div class="src">cited chunk_ids: '+esc((d.cited_chunk_ids||[]).join(', '))+'</div></div>';
    }}
    for(const c of d.chunks){{
      html+='<div class="card"><span class="sim">sim '+c.similarity.toFixed(3)+'</span>'+
        '<h3>'+esc(c.title)+'</h3>'+
        '<div class="src">'+esc(c.source)+' · '+esc(c.chunk_id)+' · ['+esc(c.organ_tag)+']</div>'+
        '<pre>'+esc(c.text)+'</pre></div>';
    }}
    out.innerHTML=html;
  }}catch(e){{meta.textContent='';out.innerHTML='<div class="card err"><pre>'+esc(''+e)+'</pre></div>';}}
}}
document.getElementById('go').onclick=run;
document.getElementById('q').addEventListener('keydown',e=>{{if(e.key==='Enter')run();}});
run();
</script></div></body></html>"""
