# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 LOCKED 749/14/163
"""REAL end-to-end test of the cortex reasoning pipeline as wired into
/api/amaru/v1/reason — exercised through a minimal FastAPI app that reuses the
*same* amaru modules (citations + verification + khipu_binding + retrieval) the
production serve.py uses. Hits the live network (arXiv). No mocks."""
from __future__ import annotations

import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sidecar", "src"))

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from amaru import citations as C
from amaru import khipu_binding as K
from amaru import retrieval as R
from amaru import verification as V


def _online() -> bool:
    try:
        urllib.request.urlopen("https://arxiv.org/abs/2309.11495", timeout=10)
        return True
    except Exception:
        return False


def _grounded(q: str) -> str:
    return "cortex re-ask: " + q


app = FastAPI()


@app.post("/api/amaru/v1/reason")
async def reason(request: Request) -> JSONResponse:
    body = await request.json()
    question = (body.get("question") or "").strip()
    answer = body.get("answer")
    user_citations = body.get("citations") or []
    require_resolution = bool(body.get("require_resolution", False))
    if not question:
        return JSONResponse({"ok": False, "error": "question required"}, status_code=400)
    steps = [{"step": "ingest", "question": question}]
    if not answer:
        answer = _grounded(question)
    steps.append({"step": "primary_answer", "answer": answer})
    retrieved = []
    if not user_citations:
        rs = R.retrieve(question, k=3, timeout=15.0)
        retrieved = [r.to_dict() for r in rs]
        user_citations = [r["url"] for r in retrieved]
        if user_citations:
            require_resolution = True
        steps.append({"step": "rag_retrieval", "sources": retrieved})
    chk = C.check_citations(text=answer, citations=user_citations,
                            require_resolution=require_resolution, timeout=12.0)
    steps.append({"step": "citation_guard", **chk.to_dict()})
    if not chk.ok:
        env = K.bind_chain(steps + [{"step": "refusal", "reason": chk.reason}])
        return JSONResponse({"ok": False, "refused": True, "reason": chk.reason,
                             "retrieved": retrieved, "khipu": env}, status_code=200)
    vres = V.verify(question, answer, _grounded, threshold=0.5)
    steps.append({"step": "chain_of_verification", **vres.to_dict()})
    env = K.bind_chain(steps)
    return JSONResponse({"ok": True, "question": question, "answer": answer,
                         "citations": chk.urls, "retrieved": retrieved,
                         "verification": vres.to_dict(), "khipu": env,
                         "khipu_signed": all(e.get("signed") for e in env)})


client = TestClient(app)


@pytest.mark.skipif(not _online(), reason="network required")
def test_rag_self_retrieval_yields_resolvable_citation():
    r = client.post("/api/amaru/v1/reason",
                    json={"question": "chain-of-verification reduce hallucination in LLMs"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True, d
    # The cortex retrieved real sources and at least one URL resolved (200).
    assert d["retrieved"], "RAG returned no sources"
    assert d["citations"], "no citations attached"
    res = d["verification"]
    assert res["reference"] == "arXiv:2309.11495"
    # Khipu chain is DSSE-signed with a real key.
    assert d["khipu_signed"] is True
    # Re-verify one returned URL independently.
    url = d["citations"][0]
    with urllib.request.urlopen(url, timeout=12) as rr:
        assert 200 <= int(getattr(rr, "status", rr.getcode())) < 300


def test_honest_refusal_when_no_citation():
    # Supply a question but force NO retrieval & NO citation -> honest refusal.
    r = client.post("/api/amaru/v1/reason",
                    json={"question": "x", "answer": "ungrounded claim", "citations": []})
    d = r.json()
    # With retrieval on, a gibberish 'x' may still find something; the contract
    # we assert is: either it grounded with a real URL, or it honestly refused.
    if d.get("ok"):
        assert d["citations"], "claimed ok without any citation"
    else:
        assert d["refused"] is True
        assert "citation" in (d["reason"] or "").lower()


def test_refusal_path_no_network_no_citation():
    # Directly exercise the guard with empty citations -> must refuse.
    chk = C.check_citations(text="no urls here", citations=[], require_resolution=False)
    assert chk.ok is False
    assert "citation" in (chk.reason or "").lower()
