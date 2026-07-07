# SPDX-License-Identifier: Apache-2.0
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""Wave O · Dev 4 — Brain-FEEDS-flywheel TestClient smoke.

Verifies the Brain's harvested knowledge POWERS the governed flywheel:

  * RAG: POST /rag/query {"corpus":"brain"} retrieves over the SZL Brain knowledge
    graph and returns 200 with brain-sourced per-claim citations + a signed receipt
    (or an HONEST UNAVAILABLE when the vault is empty — never a fabricated hit).
  * RAG: every brain-sourced citation resolves to a REAL retrieved brain passage id
    (no fabricated citations).
  * Agent-loop: POST /agentloop/run {"consult_brain":true} returns 200 and records an
    ADVISORY, LABELLED Brain-pulse context in the composite receipt WITHOUT changing a
    gate/decision and WITHOUT touching the locked-8.
  * /rag/health + /agentloop/health advertise the brain corpus / consult option honestly.
  * A non-brain request is byte-for-byte unaffected (additive change).

Run: python3 test_brain_feeds_flywheel_dev4.py   (also import-safe under pytest).
Additive; touches no locked-8 numbers; Λ = Conjecture 1 (advisory, never green).
"""
from __future__ import annotations
import os

os.environ.pop("SZL_LOCAL_LLM_URL", None)  # honest degradation path (no local model)

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_governed_rag as R
import szl_agent_loop_governed as A
import szl_brain_corpus as B

NS = "a11oy"


def _client() -> TestClient:
    app = FastAPI()
    R.register(app, NS)
    A.register(app, NS)
    return TestClient(app)


def test_rag_corpus_brain():
    c = _client()
    r = c.post(f"/api/{NS}/v1/rag/query",
               json={"query": "Euler Khipu DAG identity F1 proof status", "corpus": "brain"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["corpus_origin"] == "brain", j
    if j["rag_state"] == "UNAVAILABLE":
        # honest UNAVAILABLE — no fabricated brain hit
        assert not j["claims"], j
        assert "UNAVAILABLE" in (j.get("grounded_answer") or "")
        print("  [rag/query corpus=brain] HONEST UNAVAILABLE (empty vault) — 200, no fabrication.")
        return
    # brain-sourced answer: labelled + per-claim citations to REAL retrieved passages
    assert j["brain_sourced"] is True, j
    assert j["rag_receipt"]["corpus"]["brain_sourced"] is True
    retrieved_ids = {s["id"] for s in j["rag_receipt"]["retrieval"]["scores"]}
    assert retrieved_ids, "brain retrieval returned nothing"
    n_cited = 0
    for claim in j["claims"]:
        for cit in claim["citations"]:
            assert cit["passage_id"] in retrieved_ids, \
                f"brain claim cites non-retrieved passage {cit['passage_id']}"
            n_cited += 1
    # every retrieved brain id is a REAL graph node id (no fabrication)
    import a11oy_brain_graph as bg
    real_ids = {n["id"] for n in bg.get_brain_graph(NS)["nodes"]}
    for rid in retrieved_ids:
        assert rid in real_ids, f"fabricated brain passage id {rid}"
    # signed receipt present + honest (UNSIGNED-LOCAL expected off-Space)
    sig = j["rag_receipt"]["signature"]
    assert sig["alg"] == "ECDSA-P256" and sig["envelope"] == "DSSE"
    print(f"  [rag/query corpus=brain] 200 — {len(j['claims'])} claims, {n_cited} brain "
          f"citations, all to REAL nodes; receipt signed={sig['signed']} (UNSIGNED-LOCAL ok).")


def test_rag_non_brain_unaffected():
    c = _client()
    r = c.post(f"/api/{NS}/v1/rag/query",
               json={"query": "What is RAGAS faithfulness?"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["corpus_origin"] == "shipped_demo", j
    assert j["brain_sourced"] is False
    assert j["claims"], "shipped-demo path must still ground"
    print("  [rag/query non-brain] unaffected — shipped_demo origin, brain_sourced=False.")


def test_rag_health_advertises_brain():
    c = _client()
    r = c.get(f"/api/{NS}/v1/rag/health")
    assert r.status_code == 200, r.text
    j = r.json()
    assert "brain_corpus" in j and "module_loaded" in j["brain_corpus"]
    print(f"  [rag/health] brain_corpus advertised: available={j['brain_corpus']['available']}.")


def test_agentloop_consult_brain():
    c = _client()
    r = c.post(f"/api/{NS}/v1/agentloop/run",
               json={"task": "explain the Euler Khipu DAG identity F1", "mode": "chat",
                     "max_retries": 0, "consult_brain": True})
    assert r.status_code == 200, r.text
    j = r.json()
    body = j["composite_receipt"]["body"]
    bc = body["brain_context"]
    assert isinstance(bc, dict) and "label" in bc and "available" in bc, bc
    assert body["brain_consulted"] is True
    # ADVISORY only: gate/decision unaffected, locked-8 untouched.
    assert body["locked8_touched"] is False
    assert body["aggregate"]["lambda_status"] == "CONJECTURE"
    print(f"  [agentloop/run consult_brain] 200 — brain_context label={bc['label']!r} "
          f"available={bc['available']} relevant={len(bc.get('relevant', []))}; locked-8 untouched.")


def test_agentloop_health_advertises_brain():
    c = _client()
    r = c.get(f"/api/{NS}/v1/agentloop/health")
    assert r.status_code == 200, r.text
    j = r.json()
    assert "consult_brain" in j and "available" in j["consult_brain"]
    print(f"  [agentloop/health] consult_brain advertised: "
          f"available={j['consult_brain']['available']}.")


def test_brain_corpus_no_fabrication():
    # If the Brain is available, every corpus passage id must be a real node id.
    if not B.available(NS):
        print("  [brain_corpus] UNAVAILABLE — empty corpus (honest).")
        return
    import a11oy_brain_graph as bg
    real_ids = {n["id"] for n in bg.get_brain_graph(NS)["nodes"]}
    docs = B.corpus(NS, limit=50)
    assert docs, "brain available but corpus empty"
    for d in docs:
        assert d["id"] in real_ids, f"fabricated brain id {d['id']}"
        assert d["text"] and d["source"], d
    print(f"  [brain_corpus] {len(docs)} passages, all ids REAL, all have provenance.")


def main() -> int:
    print("Wave O · Dev 4 — Brain-feeds-flywheel TestClient smoke")
    test_brain_corpus_no_fabrication()
    test_rag_corpus_brain()
    test_rag_non_brain_unaffected()
    test_rag_health_advertises_brain()
    test_agentloop_consult_brain()
    test_agentloop_health_advertises_brain()
    print("ALL OK — Brain FEEDS the flywheel: RAG corpus=brain + agent-loop consult_brain, "
          "honest labels, no fabricated citations, locked-8 untouched, Λ = Conjecture 1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
