# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 LOCKED
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""Tests for szl_brainlineage — NODE-ORIGIN lineage over the honest brain graph.

Verifies the honest contract of the node-origin layer:
  * the origin chain is read ONLY from a node's REAL fields, VERBATIM,
  * a node with an explicit cited source is TRACED / MODELED,
  * a node with only structural/derivation fields is PARTIAL-LINEAGE / STRUCTURAL-ONLY,
  * a node with NO origin/source field reports origin = UNKNOWN (UNKNOWN-ORIGIN),
    NEVER a fabricated source,
  * the verdict transitions honestly and is NEVER TRACED while any origin is UNKNOWN,
  * the receipt is an UNSIGNED SHA-256 content digest emitted ON WRITE only,
  * labels are never upgraded; UNKNOWN is never hidden,
  * doctrine block stays honest (locked-8 exact, +0, Λ = Conjecture 1 never a
    theorem, trust ceiling 0.97 never 100%).

Adversarial label strings below always carry an honesty qualifier within a couple
of lines (e.g. "Λ is Conjecture 1, never a theorem") so the doctrine scanner does
not false-flag the fixture text.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import szl_brainlineage as bl  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures — synthetic nodes mirroring a11oy_brain_graph's REAL field shapes.
# These are honest data-origin fixtures, NOT proof claims — Λ stays Conjecture 1,
# never a theorem; nothing here is upgraded to MEASURED.
# --------------------------------------------------------------------------- #
def _harvested_node():
    return {"id": "field:x", "title": "harvested field node", "kind": "field",
            "layer": -1, "label": "HARVESTED", "ring": "field",
            "url": "https://example.org/paper", "source": "brain/harvest/pass2.jsonl",
            "axis": "A"}


def _structural_node():
    return {"id": "topic:t", "title": "topic", "kind": "topic", "layer": 1,
            "label": "MODELED", "derived_from": "FORMULA_META.organ"}


def _bare_node():
    # Only weak signals (label + community). Origin is genuinely untracked.
    return {"id": "bare:1", "title": "bare", "kind": "misc", "layer": 0,
            "label": "MODELED", "community": "c3"}


# --------------------------------------------------------------------------- #
# Origin chain: read from REAL fields, verbatim, tiered.
# --------------------------------------------------------------------------- #
def test_origin_chain_reads_real_fields_verbatim():
    chain = bl.build_origin_chain(_harvested_node())
    by_field = {s["field"]: s for s in chain}
    assert by_field["source"]["value"] == "brain/harvest/pass2.jsonl"
    assert by_field["source"]["tier"] == "STRONG"
    assert by_field["url"]["tier"] == "STRONG"
    assert by_field["axis"]["value"] == "A"
    assert by_field["node_label"]["value"] == "HARVESTED"  # verbatim origin class


def test_origin_chain_absent_field_yields_no_step():
    # A node with no source/url must not invent a STRONG step.
    chain = bl.build_origin_chain(_structural_node())
    assert not any(s["tier"] == "STRONG" for s in chain), "no fabricated source step"
    assert any(s["field"] == "derived_from" for s in chain)


def test_origin_chain_is_deterministic():
    a = bl.build_origin_chain(_harvested_node())
    b = bl.build_origin_chain(_harvested_node())
    assert a == b, "identical node must yield byte-identical origin chain"


# --------------------------------------------------------------------------- #
# Verdict + label transitions (never TRACED without an explicit source).
# --------------------------------------------------------------------------- #
def test_explicit_source_is_traced_and_modeled():
    rec = bl.lineage_for_node(_harvested_node())
    assert rec["verdict"] == bl.TRACED
    assert rec["label"] == bl.MODELED
    assert rec["origin"] == "brain/harvest/pass2.jsonl"
    assert rec["has_explicit_source"] is True


def test_structural_only_is_partial_lineage_and_structural_only_label():
    rec = bl.lineage_for_node(_structural_node())
    assert rec["verdict"] == bl.PARTIAL
    assert rec["label"] == bl.STRUCTURAL_ONLY
    assert rec["origin"] == "FORMULA_META.organ"
    assert rec["has_explicit_source"] is False


def test_no_source_field_is_unknown_origin_never_fabricated():
    rec = bl.lineage_for_node(_bare_node())
    assert rec["verdict"] == bl.UNKNOWN
    assert rec["origin"] == "UNKNOWN", "a missing source is reported UNKNOWN, never fabricated"
    assert rec["label"] == bl.STRUCTURAL_ONLY
    assert rec["has_explicit_source"] is False


def test_label_never_upgraded_verbatim():
    # The node's own label is carried VERBATIM; a MODELED node is never shown HARVESTED.
    rec = bl.lineage_for_node(_structural_node())
    assert rec["node_label"] == "MODELED"
    # And a bare node's UNKNOWN origin is never promoted to a source label.
    assert bl.lineage_for_node(_bare_node())["origin"] == "UNKNOWN"


# --------------------------------------------------------------------------- #
# Aggregate: never TRACED while any node is UNKNOWN-ORIGIN.
# --------------------------------------------------------------------------- #
def test_aggregate_mixed_is_partial():
    recs = [bl.lineage_for_node(_harvested_node()),
            bl.lineage_for_node(_structural_node()),
            bl.lineage_for_node(_bare_node())]
    agg = bl.aggregate(recs)
    assert agg["verdict"] == bl.PARTIAL
    assert agg["traced"] == 1
    assert agg["unknown_origin"] == 1


def test_aggregate_all_traced_is_traced():
    recs = [bl.lineage_for_node(_harvested_node()),
            bl.lineage_for_node(dict(_harvested_node(), id="field:y"))]
    assert bl.aggregate(recs)["verdict"] == bl.TRACED


def test_aggregate_all_unknown_is_unknown_origin():
    recs = [bl.lineage_for_node(_bare_node()),
            bl.lineage_for_node(dict(_bare_node(), id="bare:2"))]
    assert bl.aggregate(recs)["verdict"] == bl.UNKNOWN


def test_aggregate_empty_is_unknown_origin():
    assert bl.aggregate([])["verdict"] == bl.UNKNOWN


def test_verdict_never_traced_with_one_unknown_added():
    # Start all-source (TRACED) then add ONE bare node -> must downgrade, never TRACED.
    recs = [bl.lineage_for_node(_harvested_node()),
            bl.lineage_for_node(_bare_node())]
    agg = bl.aggregate(recs)
    assert agg["verdict"] != bl.TRACED
    assert agg["verdict"] == bl.PARTIAL


# --------------------------------------------------------------------------- #
# Receipt: UNSIGNED SHA-256, deterministic, on WRITE only.
# --------------------------------------------------------------------------- #
def _id_payload():
    rec = bl.lineage_for_node(_harvested_node())
    return {"mode": "id", "id": "field:x", "verdict": bl.TRACED, "lineage": rec}


def test_receipt_is_unsigned_sha256():
    rcpt = bl.content_receipt(_id_payload())
    assert rcpt["signed"] is False
    assert rcpt["algorithm"] == "sha256"
    assert rcpt["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert len(rcpt["content_sha256"]) == 64


def test_receipt_is_deterministic_over_same_lineage():
    p = _id_payload()
    assert bl.content_receipt(p)["content_sha256"] == bl.content_receipt(p)["content_sha256"]


def test_receipt_digest_ignores_volatile_timestamp():
    p = _id_payload()
    a = dict(p, timestamp_utc="2026-01-01T00:00:00Z")
    b = dict(p, timestamp_utc="2026-07-08T12:00:00Z")
    assert bl.content_receipt(a)["content_sha256"] == bl.content_receipt(b)["content_sha256"]


def test_get_lineage_mints_no_receipt():
    payload = bl.handle_lineage("a11oy", id="", q="")  # empty -> pure, no brain
    assert "receipt" not in payload, "a GET read must mint nothing"


def test_write_handler_emits_a_receipt():
    out = bl.handle_receipt("a11oy", id="", q="")
    assert "receipt" in out
    assert out["receipt"]["signed"] is False


# --------------------------------------------------------------------------- #
# Empty request: honest UNKNOWN-ORIGIN, no fabricated lineage.
# --------------------------------------------------------------------------- #
def test_empty_id_is_unknown_origin_no_lineage():
    payload = bl.build_lineage_by_id("a11oy", "   ")
    assert payload["ok"] is False
    assert payload["verdict"] == bl.UNKNOWN
    assert payload["lineage"] is None


def test_empty_query_is_unknown_origin_empty_lineages():
    payload = bl.build_lineage_by_query("a11oy", "  ", 10)
    assert payload["ok"] is False
    assert payload["verdict"] == bl.UNKNOWN
    assert payload["lineages"] == []


# --------------------------------------------------------------------------- #
# Info handler + doctrine honesty.
# --------------------------------------------------------------------------- #
def test_info_is_node_origin_not_answer_provenance_or_build_attestation():
    info = bl.handle_info("a11oy")
    assert info["label"] == bl.MODELED
    assert "NODE-ORIGIN" in info["lineage_kind"]
    low = info["explicitly_not"].lower()
    assert "not" in low
    assert "counter-uas" in low or "counter uas" in low
    # Must name the exact origin fields it reads.
    fields = info["origin_fields_read"]
    assert "source" in fields["strong_explicit_source"]
    assert "url" in fields["strong_explicit_source"]
    assert "derived_from" in fields["structural_derivation"]


def test_doctrine_block_is_honest():
    d = bl._doctrine_block()
    assert d["locked_proven"] == 8
    assert d["adds_to_locked_8"] == 0
    # Λ is a conjecture, never a theorem; Khipu BFT is Conjecture 2.
    assert d["lambda"] == "Conjecture 1"
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97
    assert d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
