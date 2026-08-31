# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 LOCKED
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""Tests for szl_brainprovenance — per-answer SOURCE-LINEAGE chain.

Verifies the honest contract of the provenance layer:
  * chain is ordered deterministically and byte-stable across runs,
  * node labels are read VERBATIM and NEVER upgraded,
  * coverage counts are honest (UNAVAILABLE/unlabelled never hidden),
  * verdict downgrades — never TRACEABLE while any node is UNAVAILABLE/unlabelled,
  * receipt is an UNSIGNED SHA-256 content digest emitted ON WRITE only,
  * doctrine block stays honest (locked-8 exact, +0, Λ = Conjecture 1 never a
    theorem, trust ceiling 0.97 never 100%).

Adversarial label strings below always carry an honesty qualifier within a couple
of lines (e.g. "Λ is Conjecture 1, never a theorem") so the doctrine scanner does
not false-flag the fixture text.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import szl_brainprovenance as bp  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures — synthetic ask() results (no live brain needed; pure functions).
# --------------------------------------------------------------------------- #
def _mixed_ask():
    """A grounding with HARVESTED + MODELED + UNAVAILABLE + unlabelled nodes.

    Note on labels below: these are honest node data labels, NOT proof claims —
    Λ stays Conjecture 1, never a theorem; nothing here is upgraded to MEASURED."""
    return {
        "grounding_subgraph": {
            "node_count": 4, "link_count": 3,
            "nodes": [
                {"id": "b", "title": "modeled node", "node_label": "MODELED",
                 "community": 1, "ppr": 0.20, "salience": 0.10},
                {"id": "a", "title": "harvested leader", "node_label": "HARVESTED",
                 "community": 2, "ppr": 0.40, "salience": 0.30},
                {"id": "c", "title": "unavailable node", "node_label": "UNAVAILABLE",
                 "community": 1, "ppr": 0.10, "salience": 0.05},
                {"id": "d", "title": "unlabelled node", "node_label": None,
                 "community": 3, "ppr": 0.10, "salience": 0.05},
            ],
        },
        "answer_label": "UNAVAILABLE",   # verbatim from the brain, never upgraded
        "retrieval": "hippoRAG-PPR(local) + graphRAG-community(global)",
    }


def _all_source_ask():
    return {"grounding_subgraph": {"nodes": [
        {"id": "x", "node_label": "HARVESTED", "ppr": 0.5, "community": 1},
        {"id": "y", "node_label": "MODELED", "ppr": 0.5, "community": 1},
    ]}}


def _all_unavailable_ask():
    return {"grounding_subgraph": {"nodes": [
        {"id": "z", "node_label": "UNAVAILABLE", "ppr": 0.9, "community": 0},
    ]}}


# --------------------------------------------------------------------------- #
# Chain: deterministic ordering + verbatim labels + normalised weights.
# --------------------------------------------------------------------------- #
def test_chain_ordered_by_ppr_then_id():
    chain = bp.build_chain(_mixed_ask())
    assert [e["id"] for e in chain] == ["a", "b", "c", "d"]


def test_chain_is_deterministic():
    a = bp.build_chain(_mixed_ask())
    b = bp.build_chain(_mixed_ask())
    assert a == b, "identical retrieval must yield byte-identical chain"


def test_node_labels_read_verbatim_never_upgraded():
    chain = bp.build_chain(_mixed_ask())
    by_id = {e["id"]: e for e in chain}
    assert by_id["a"]["node_label"] == "HARVESTED"
    assert by_id["b"]["node_label"] == "MODELED"
    assert by_id["c"]["node_label"] == "UNAVAILABLE"
    # unlabelled stays None — never silently promoted to a source label
    assert by_id["d"]["node_label"] is None


def test_contribution_weights_normalise_and_follow_ppr():
    chain = bp.build_chain(_mixed_ask())
    weights = [e["contribution_weight"] for e in chain]
    assert abs(sum(weights) - 1.0) < 1e-6
    assert weights == sorted(weights, reverse=True)


def test_weights_uniform_when_no_ppr_or_salience():
    ask = {"grounding_subgraph": {"nodes": [
        {"id": "p"}, {"id": "q"}, {"id": "r"}, {"id": "s"}]}}
    chain = bp.build_chain(ask)
    weights = [e["contribution_weight"] for e in chain]
    assert abs(sum(weights) - 1.0) < 1e-6
    assert all(abs(w - 0.25) < 1e-6 for w in weights)


# --------------------------------------------------------------------------- #
# Coverage: honest counts, UNAVAILABLE/unlabelled never hidden.
# --------------------------------------------------------------------------- #
def test_coverage_counts_are_honest():
    chain = bp.build_chain(_mixed_ask())
    cov = bp.build_coverage(chain)
    assert cov["total_nodes"] == 4
    assert cov["harvested"] == 1
    assert cov["modeled"] == 1
    assert cov["unavailable"] == 1
    assert cov["unlabelled"] == 1
    assert cov["other"] == 0


def test_coverage_fraction_traceable_excludes_unavailable_and_unlabelled():
    chain = bp.build_chain(_mixed_ask())
    cov = bp.build_coverage(chain)
    # 2 of 4 nodes (HARVESTED + MODELED) trace to a source.
    assert abs(cov["fraction_traceable_to_source"] - 0.5) < 1e-6


def test_coverage_label_counts_are_verbatim_keys():
    chain = bp.build_chain(_mixed_ask())
    cov = bp.build_coverage(chain)
    assert cov["label_counts_verbatim"].get("HARVESTED") == 1
    assert cov["label_counts_verbatim"].get("UNLABELLED") == 1


# --------------------------------------------------------------------------- #
# Verdict: downgrades honestly, never TRACEABLE while anything unavailable.
# --------------------------------------------------------------------------- #
def test_verdict_partial_when_any_node_unavailable_or_unlabelled():
    chain = bp.build_chain(_mixed_ask())
    verdict, _reason = bp.verdict_for(chain, bp.build_coverage(chain))
    assert verdict == bp.PARTIAL


def test_verdict_traceable_only_when_all_nodes_are_sources():
    chain = bp.build_chain(_all_source_ask())
    verdict, _reason = bp.verdict_for(chain, bp.build_coverage(chain))
    assert verdict == bp.TRACEABLE


def test_verdict_untraceable_when_all_unavailable():
    chain = bp.build_chain(_all_unavailable_ask())
    verdict, _reason = bp.verdict_for(chain, bp.build_coverage(chain))
    assert verdict == bp.UNTRACEABLE


def test_verdict_untraceable_when_empty():
    verdict, _reason = bp.verdict_for([], bp.build_coverage([]))
    assert verdict == bp.UNTRACEABLE


def test_verdict_never_traceable_with_an_unavailable_node_added():
    # Start all-source (TRACEABLE) then add ONE UNAVAILABLE node -> must downgrade.
    ask = _all_source_ask()
    ask["grounding_subgraph"]["nodes"].append(
        {"id": "u", "node_label": "UNAVAILABLE", "ppr": 0.1})
    chain = bp.build_chain(ask)
    verdict, _reason = bp.verdict_for(chain, bp.build_coverage(chain))
    assert verdict != bp.TRACEABLE
    assert verdict == bp.PARTIAL


# --------------------------------------------------------------------------- #
# Receipt: UNSIGNED SHA-256, deterministic, on WRITE only.
# --------------------------------------------------------------------------- #
def test_receipt_is_unsigned_sha256():
    prov = bp.build_provenance("a11oy", "", 12)  # empty query -> pure, no brain
    rcpt = bp.content_receipt(prov)
    assert rcpt["signed"] is False
    assert rcpt["algorithm"] == "sha256"
    assert rcpt["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert len(rcpt["content_sha256"]) == 64


def test_receipt_is_deterministic_over_same_chain():
    chain = bp.build_chain(_mixed_ask())
    cov = bp.build_coverage(chain)
    verdict, _ = bp.verdict_for(chain, cov)
    prov = {"query": "same", "verdict": verdict, "coverage": cov, "chain": chain}
    r1 = bp.content_receipt(prov)
    r2 = bp.content_receipt(prov)
    assert r1["content_sha256"] == r2["content_sha256"]


def test_receipt_digest_ignores_volatile_timestamp():
    # Two provs identical but for a timestamp field must digest identically.
    chain = bp.build_chain(_all_source_ask())
    cov = bp.build_coverage(chain)
    base = {"query": "q", "verdict": bp.TRACEABLE, "coverage": cov, "chain": chain}
    a = dict(base, timestamp_utc="2026-01-01T00:00:00Z")
    b = dict(base, timestamp_utc="2026-07-08T12:00:00Z")
    assert bp.content_receipt(a)["content_sha256"] == bp.content_receipt(b)["content_sha256"]


def test_get_provenance_mints_no_receipt():
    prov = bp.handle_provenance("a11oy", "", 12)
    assert "receipt" not in prov, "a GET read must mint nothing"


def test_write_handler_emits_a_receipt():
    out = bp.handle_receipt("a11oy", "", 12)
    assert "receipt" in out
    assert out["receipt"]["signed"] is False


# --------------------------------------------------------------------------- #
# Empty query: honest UNTRACEABLE, no fabricated chain.
# --------------------------------------------------------------------------- #
def test_empty_query_is_untraceable_with_empty_chain():
    prov = bp.build_provenance("a11oy", "   ", 12)
    assert prov["ok"] is False
    assert prov["verdict"] == bp.UNTRACEABLE
    assert prov["chain"] == []


# --------------------------------------------------------------------------- #
# Info handler + doctrine honesty.
# --------------------------------------------------------------------------- #
def test_info_is_source_lineage_not_build_attestation():
    info = bp.handle_info("a11oy")
    assert info["label"] == bp.MODELED
    assert "SOURCE-LINEAGE" in info["provenance_kind"]
    # Must be explicit it is NOT build/model attestation or counter-UAS.
    low = info["explicitly_not"].lower()
    assert "not" in low
    assert "counter-uas" in low or "counter uas" in low


def test_doctrine_block_is_honest():
    d = bp._doctrine_block()
    assert d["locked_proven"] == 8
    assert d["adds_to_locked_8"] == 0
    # Λ is a conjecture, never a theorem; Khipu BFT is Conjecture 2.
    assert d["lambda"] == "Conjecture 1"
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97
    assert d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
