# SPDX-License-Identifier: Apache-2.0
"""Focused guards for the evidence-Brain query surface.

These tests keep backend timing, graph counts, canonical/dedupe posture,
read-only provenance, and safe source-link rendering from being collapsed into
one optimistic UI claim.
"""

from pathlib import Path
import types

import szl_brain_api as brain_api


def _tiny_index(monkeypatch):
    idx = object.__new__(brain_api.BrainIndex)
    idx.ids = ["node:1"]
    idx.nodes = [{"id": "node:1", "title": "Evidence node", "kind": "paper",
                  "label": "HARVESTED", "url": "https://example.test/evidence"}]
    idx.by_id = {"node:1": idx.nodes[0]}
    idx.links = []
    idx.graph = {
        "node_count": 9464,
        "link_count": 14234,
        "distinct_artifacts": 4229,
        "person_node_count": 5235,
        "artifact_note": "fixture counts are separate dimensions",
    }
    idx.content_hash = "0123456789abcdef"
    idx.embed_source = "hash-fallback"
    idx.embed_tier = brain_api.LBL_MODELED
    idx.embed_dim = 256
    idx.vector_backend = "python-cosine"
    idx.community_algo = "fixture"
    idx.communities = {}
    idx.community_of = {}
    idx.community_summaries = {}
    idx._pagerank_global = {"node:1": 1.0}
    idx.DG = None
    monkeypatch.setattr(idx, "search", lambda q, k=10: [
        {"id": "node:1", "title": "Evidence node", "kind": "paper",
         "score": 1.0, "match": "exact"}
    ])
    monkeypatch.setattr(idx, "_compute_pagerank", lambda personalization=None: {"node:1": 1.0})
    monkeypatch.setattr(
        idx, "_maybe_generate",
        types.MethodType(lambda self, q, grounding, global_ctx:
                         (None, brain_api.LBL_UNAVAILABLE, None), idx),
    )
    return idx


def test_ask_reports_only_server_monotonic_measured_latency(monkeypatch):
    idx = _tiny_index(monkeypatch)
    out = idx.ask("exact evidence query", 1)

    latency = out["query_latency"]
    assert latency["label"] == "MEASURED"
    assert latency["value_ms"] >= 0
    assert latency["unit"] == "milliseconds"
    assert "perf_counter_ns" in latency["clock"]
    assert "server" in latency["basis"]
    assert "network transport" in latency["excludes"]
    assert "browser" in latency["excludes"]
    assert out["answer"] is None
    assert out["answer_label"] == "UNAVAILABLE"
    assert out["answer_model"] is None


def test_index_status_keeps_raw_distinct_and_person_counts_separate(monkeypatch):
    idx = _tiny_index(monkeypatch)
    status = idx.index_status()

    assert status["raw_node_count"] == 9464
    assert status["node_count"] == 9464
    assert status["link_count"] == 14234
    assert status["distinct_artifacts"] == 4229
    assert status["person_node_count"] == 5235
    assert status["distinct_artifacts"] + status["person_node_count"] == status["raw_node_count"]
    assert "do not imply training admission" in status["note"]


def test_surface_wires_honest_inventory_provenance_and_safe_links():
    source = (Path(__file__).parents[1] / "static" / "3d" / "surfaces" /
              "brainquery.js").read_text(encoding="utf-8")

    assert "/brain/reranker/inventory?limit=1" in source
    assert "canonical count is dedupe lineage, not admission" in source
    assert "BLOCKED / UNAVAILABLE" in source
    assert "0 training-eligible" in source
    assert "raw nodes quarantined" in source
    assert "j.query_latency" in source
    assert "server monotonic" in source
    assert "startExpanded: !compactViewport" in source
    assert "(max-width: 640px)" in source

    # Provenance follows the exact query via pure GET. No receipt POST is made.
    assert 'String(j.query || "") !== q' in source
    assert 'fetch(url, { method: "GET"' in source
    assert 'method: "POST"' not in source
    assert "fraction_traceable_to_source" in source

    # Only http(s) URLs or same-origin paths with one initial slash become links.
    assert "parsed.protocol === \"http:\" || parsed.protocol === \"https:\"" in source
    assert "^\\/(?![\\/\\\\])" in source
    assert "local.origin === window.location.origin" in source
    assert 'title.rel = "noopener noreferrer"' in source
    assert 'id.textContent = String(n.id || "UNAVAILABLE")' in source
