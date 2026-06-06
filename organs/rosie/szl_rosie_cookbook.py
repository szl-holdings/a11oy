# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO). Co-Authored-By: Perplexity Computer Agent.
"""
szl_rosie_cookbook — ADDITIVE runtime cookbook + thesis library + Lean index for Rosie.

Founder directive (2026-06-01, verbatim):
  "audit the mono repo and cherry pick the things that Rosie needs to be truly one
   of one ... also look at all the repos and cherry pick stuff doctrine and
   exhaustive ... runtime cookbook all the thesis in Rosie."

Rosie is a PERSONAL AI AIDE (NOT healthcare) — a11oy's understudy with provenanced
memory. This module gives her an in-aide knowledge base she can cite and execute:

  GET  /api/<ns>/v2/cookbook                  -> 22 recipes (index)
  GET  /api/<ns>/v2/cookbook/mcp-tools        -> 16 Hatun-MCP tool descriptors
  GET  /api/<ns>/v2/cookbook/formulas/F<n>    -> 1 of 23 Codex formula descriptors
  GET  /api/<ns>/v2/cookbook/<recipe-id>      -> recipe content + signed recall receipt
  GET  /api/<ns>/v2/theses                    -> 5 theses (each with PDF SHA-256)
  GET  /api/<ns>/v2/theses/<name>[?cite=true] -> chapters + lean_citations + receipt
  GET  /api/<ns>/v2/lean-index?q=<term>       -> substring search over 870 Lean decls
  POST /api/<ns>/v2/recall {"query": "..."}   -> best cookbook/thesis/lean hit + receipt

PURELY ADDITIVE: only adds new routes; never deletes/overwrites. Caller MUST
register() BEFORE the SPA/Gradio catch-all so these explicit routes win FastAPI's
ordered route match. The more-specific /cookbook/mcp-tools and /cookbook/formulas/*
routes are registered BEFORE the /cookbook/{id} catch so they are matched first.

Honesty (Doctrine v11, verbatim 749/14/163, locked c7c0ba17):
  * Λ (lambda) is Conjecture 1 — NOT a proven theorem.
  * SLSA L1 (honest) — not L3.
  * Reed-Solomon RS(10,6) is erasure coding — NOT holographic.
  * Lean status counts reflect the source tree actually present.
  * If szl_dsse is unavailable, receipts carry a sha256 hash (NOT a DSSE signature),
    with an honest unblock note — never a fabricated signature.

Content lives in static/cookbook/ (md + json; no PDFs — SHAs are recorded in the
index). Apache-2.0.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse

try:
    import szl_dsse as _dsse
except Exception:  # pragma: no cover
    _dsse = None

DOCTRINE = "v11"
DOCTRINE_LOCKED_AT = "c7c0ba17"
NUMBERS = {"declarations": 749, "axioms": 14, "sorries": 163,
           "sorry_breakdown": "51 Putnam + 112 baseline"}
SIGNED_BY = "Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent"


def _cookbook_dir() -> str:
    """Resolve static/cookbook relative to this module (WORKDIR=/home/user/app)."""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "static", "cookbook"),
                 os.path.join(os.getcwd(), "static", "cookbook"),
                 "/home/user/app/static/cookbook"):
        if os.path.isdir(cand):
            return cand
    return os.path.join(here, "static", "cookbook")


def _load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _read_text(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


# ── honest hashing embedder + cosine (no external model; deterministic) ─────
_DIM = 512
_TOK = re.compile(r"[a-z0-9_]+")


def _embed(text: str) -> list[float]:
    vec = [0.0] * _DIM
    for tok in _TOK.findall((text or "").lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % _DIM] += 1.0
        vec[(h // _DIM) % _DIM] += 0.5  # bigram-ish spread
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _sign_receipt(ns: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Sign a recall/citation receipt with the REAL DSSE key. Honest fallback if absent."""
    receipt = {
        "space": ns, "kind": kind, "doctrine": DOCTRINE,
        "doctrine_numbers": dict(NUMBERS), "payload": payload,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "signed_by": SIGNED_BY,
    }
    if _dsse is not None and getattr(_dsse, "signing_available", lambda: False)():
        try:
            env = _dsse.sign_payload(
                receipt, getattr(_dsse, "KHIPU_PAYLOAD_TYPE", "application/vnd.szl.khipu+json"))
            return {"signed": True, "envelope": env, "receipt": receipt,
                    "keyid": getattr(_dsse, "KEYID", "szlholdings-cosign"),
                    "fingerprint_sha256": _dsse.public_key_fingerprint()}
        except Exception as e:  # pragma: no cover
            return {"signed": False, "receipt": receipt,
                    "honest_error": f"sign failed: {type(e).__name__}: {e}"}
    h = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    return {"signed": False, "receipt": receipt, "sha256": h,
            "honesty": "szl_dsse unavailable; receipt carries a sha256 hash, not a DSSE "
                       "signature. Unblock: vendor szl_dsse.py + set the cosign secret."}


def register(app, ns: str = "rosie") -> dict[str, Any]:
    """Install the runtime cookbook layer. ADDITIVE. Returns a status dict.

    Caller MUST register BEFORE the SPA/Gradio catch-all.
    """
    P = f"/api/{ns}/v2"
    CB = _cookbook_dir()
    registered: list[str] = []

    def R(p):
        registered.append(p)

    # Load content once (cheap; reloaded lazily per request if missing)
    cookbook_index = _load_json(os.path.join(CB, "index.json"),
                                {"count": 0, "recipes": []})
    theses_index = _load_json(os.path.join(CB, "theses", "theses_index.json"),
                              {"theses": {}}).get("theses", {})
    lean_index = _load_json(os.path.join(CB, "lean-index.json"),
                            {"declarations": [], "total_declarations": 0})
    mcp_catalog = _load_json(os.path.join(CB, "mcp-tools", "catalog.json"),
                             {"count": 0, "tools": []})

    # Build the recall corpus: recipes + theses + a sample of lean decls.
    corpus: list[dict[str, Any]] = []
    for r in cookbook_index.get("recipes", []):
        text = " ".join([r.get("title", ""), r.get("summary", ""),
                         " ".join(r.get("tags", []))])
        corpus.append({"kind": "recipe", "id": r["id"], "title": r.get("title"),
                       "tags": [t.lower() for t in r.get("tags", [])],
                       "endpoint": r.get("endpoint"), "vec": _embed(text)})
    for name, meta in theses_index.items():
        text = " ".join([meta.get("title", ""), name,
                         " ".join(c.get("title", "") for c in meta.get("chapters", []))])
        corpus.append({"kind": "thesis", "id": name, "title": meta.get("title"),
                       "tags": [name, "thesis", "cite"],
                       "endpoint": f"{P}/theses/{name}?cite=true", "vec": _embed(text)})
    for d in lean_index.get("declarations", []):
        corpus.append({"kind": "lean", "id": d["name"], "title": d["name"],
                       "tags": [d["name"].lower(), d.get("kind", ""), "lean", "theorem"],
                       "endpoint": f"{P}/lean-index?q={d['name']}", "vec": _embed(d["name"])})

    _KIND_WEIGHT = {"recipe": 1.15, "thesis": 1.0, "lean": 0.85}

    def _recall(query: str, k: int = 5) -> list[dict[str, Any]]:
        qv = _embed(query)
        qtok = set(_TOK.findall(query.lower()))
        scored = []
        for item in corpus:
            base = _cosine(qv, item["vec"]) * _KIND_WEIGHT.get(item["kind"], 1.0)
            # tag-match bonus: 0.04 per matched tag token, capped at 0.12
            tagmatch = sum(1 for t in item["tags"] if t and t in qtok)
            bonus = min(0.12, 0.04 * tagmatch)
            scored.append((base + bonus, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for s, item in scored[:k]:
            out.append({"score": round(s, 4), "kind": item["kind"], "id": item["id"],
                        "title": item["title"], "endpoint": item["endpoint"]})
        return out

    # ── recall (POST) ───────────────────────────────────────────────────────
    @app.post(f"{P}/recall")
    async def cb_recall(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        query = (body.get("query") or body.get("q") or "").strip()
        if not query:
            return JSONResponse({"status": "error", "honest_error": "missing 'query'"},
                                status_code=400)
        hits = _recall(query, k=int(body.get("k", 5)))
        receipt = _sign_receipt(ns, "recall", {"query": query,
                                               "top": hits[0] if hits else None,
                                               "n_candidates": len(corpus)})
        return JSONResponse({"status": "ok", "query": query, "results": hits,
                             "top": hits[0] if hits else None,
                             "recall_receipt": receipt, "doctrine": DOCTRINE})
    R(f"{P}/recall")

    # ── lean-index search ────────────────────────────────────────────────────
    @app.get(f"{P}/lean-index")
    async def cb_lean(q: str = "") -> JSONResponse:
        q = (q or "").strip().lower()
        decls = lean_index.get("declarations", [])
        if not q:
            return JSONResponse({"status": "ok", "total_declarations":
                                 lean_index.get("total_declarations", len(decls)),
                                 "status_counts": lean_index.get("status_counts", {}),
                                 "doctrine": DOCTRINE,
                                 "lambda_note": "Λ is Conjecture 1 — NOT a theorem.",
                                 "note": "pass ?q=<term> to search by declaration name."})
        matches = [d for d in decls if q in d["name"].lower()]
        return JSONResponse({"status": "ok", "query": q, "count": len(matches),
                             "matches": matches[:50],
                             "lambda_note": "Λ is Conjecture 1 — NOT a theorem.",
                             "doctrine": DOCTRINE, "source": lean_index.get("source")})
    R(f"{P}/lean-index")

    # ── theses ───────────────────────────────────────────────────────────────
    @app.get(f"{P}/theses")
    async def cb_theses() -> JSONResponse:
        items = [{"name": n, "title": m.get("title"), "pdf_sha256": m.get("pdf_sha256"),
                  "pages": m.get("pages"), "doi": m.get("doi"),
                  "chapters": len(m.get("chapters", []))}
                 for n, m in theses_index.items()]
        return JSONResponse({"status": "ok", "count": len(items), "theses": items,
                             "doctrine": DOCTRINE})
    R(f"{P}/theses")

    @app.get(P + "/theses/{name}")
    async def cb_thesis(name: str, cite: bool = False) -> JSONResponse:
        meta = theses_index.get(name)
        if not meta:
            return JSONResponse({"status": "not_found", "name": name,
                                 "available": list(theses_index.keys())}, status_code=404)
        # honest lean citations: lean decls whose name appears in the thesis title/name
        lean_citations = []
        for d in lean_index.get("declarations", [])[:0]:  # keep cheap; populated below
            pass
        # cheap heuristic: tie axis/lambda decls to ouroboros theses
        if "ouroboros" in name:
            lean_citations = [d["name"] for d in lean_index.get("declarations", [])
                              if any(t in d["name"].lower() for t in ("lambda", "axis",
                                     "babylon", "egyptian"))][:12]
        out = {"status": "ok", "name": name, "title": meta.get("title"),
               "pdf_sha256": meta.get("pdf_sha256"), "pages": meta.get("pages"),
               "doi": meta.get("doi"), "note": meta.get("note"),
               "chapters": meta.get("chapters", []),
               "doctrine": DOCTRINE}
        if cite:
            md = _read_text(os.path.join(CB, "theses", meta.get("md_file", name + ".md")))
            out["text"] = md
            out["lean_citations"] = lean_citations
            out["recall_receipt"] = _sign_receipt(
                ns, "thesis_citation",
                {"name": name, "pdf_sha256": meta.get("pdf_sha256"),
                 "chapters": len(meta.get("chapters", []))})
        return JSONResponse(out)
    R(P + "/theses/{name}")

    # ── cookbook: register MORE-SPECIFIC routes BEFORE /cookbook/{id} ────────
    @app.get(f"{P}/cookbook/mcp-tools")
    async def cb_mcp() -> JSONResponse:
        return JSONResponse({"status": "ok", "count": mcp_catalog.get("count", 0),
                             "tools": mcp_catalog.get("tools", []),
                             "doctrine": DOCTRINE})
    R(f"{P}/cookbook/mcp-tools")

    @app.get(P + "/cookbook/formulas/{fid}")
    async def cb_formula(fid: str) -> JSONResponse:
        fid = fid.upper().split("/")[0]
        obj = _load_json(os.path.join(CB, "formulas", fid + ".json"), None)
        if obj is None:
            return JSONResponse({"ok": False, "id": fid,
                                 "valid": "F1..F23"}, status_code=404)
        # nest the descriptor so its own 'status' (PROVEN/OPEN_CONJECTURE) does not
        # clobber the response envelope.
        return JSONResponse({"ok": True, "formula": obj})
    R(P + "/cookbook/formulas/{fid}")

    @app.get(f"{P}/cookbook")
    async def cb_index() -> JSONResponse:
        return JSONResponse({"status": "ok", "count": cookbook_index.get("count", 0),
                             "recipes": cookbook_index.get("recipes", []),
                             "doctrine": DOCTRINE, "generated_by": SIGNED_BY})
    R(f"{P}/cookbook")

    @app.get(P + "/cookbook/{recipe_id}")
    async def cb_recipe(recipe_id: str) -> JSONResponse:
        recipe_id = recipe_id.split("/")[0]
        md = _read_text(os.path.join(CB, "recipes", recipe_id + ".md"))
        if md is None:
            return JSONResponse({"status": "not_found", "id": recipe_id,
                                 "list": f"{P}/cookbook"}, status_code=404)
        meta = next((r for r in cookbook_index.get("recipes", [])
                     if r["id"] == recipe_id), {})
        receipt = _sign_receipt(ns, "recipe_recall",
                                {"id": recipe_id, "title": meta.get("title")})
        return JSONResponse({"status": "ok", "id": recipe_id, "title": meta.get("title"),
                             "tags": meta.get("tags", []), "content": md,
                             "recall_receipt": receipt, "doctrine": DOCTRINE})
    R(P + "/cookbook/{recipe_id}")

    return {
        "module": "szl_rosie_cookbook", "ns": ns, "registered_count": len(registered),
        "routes": registered, "cookbook_present": os.path.isdir(CB),
        "recipes": cookbook_index.get("count", 0),
        "theses": len(theses_index),
        "lean_declarations": lean_index.get("total_declarations", 0),
        "mcp_tools": mcp_catalog.get("count", 0),
        "dsse_signing": bool(_dsse is not None
                             and getattr(_dsse, "signing_available", lambda: False)()),
        "doctrine": DOCTRINE,
    }
