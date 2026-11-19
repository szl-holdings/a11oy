# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""A short formula ID or historical label never admits a proof into M1."""

import json

import pytest

import szl_m1_corpus_manifest as m1
import szl_puriq_formulas as puriq


@pytest.mark.parametrize("declared", ["PROVED", "LOCKED_PROVEN", "KERNEL_ACCEPTED", "REFUTED"])
def test_raw_formula_declarations_cannot_admit_proof_or_refutation(declared):
    for formula_id in ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22", "F23"):
        assert m1._formula_status(formula_id, {
            "proof_status": declared, "lean_status": declared,
            "status": declared, "maturity": declared,
        }) == "OPEN"


def test_m1_generator_keeps_same_id_namespaces_separate_and_evaluation_only(tmp_path, monkeypatch):
    # Deliberately hostile historical labels exercise the consumer's admission
    # boundary without replacing or regenerating retained corpus artifacts.
    (tmp_path / "knowledge.json").write_text(json.dumps({"formulas": [
        {"id": "F1", "name": "Replay-Hash Determinism", "proof_status": "PROVED", "lean_status": "PROVED"},
        {"id": "F23", "name": "Historical refutation claim", "status": "REFUTED"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(m1, "ROOT", tmp_path)
    numeric_node = {
        "id": "formula:F1", "kind": "formula", "formula_id": "F1",
        "formula_namespace": m1.NUMERIC_NAMESPACE, "title": "Euler numeric example", "layer": 2,
    }
    formal_node = {
        "id": "formal-formula:F1", "kind": "formal_formula", "formula_id": "F1",
        "formula_namespace": "lutar-lean.formal-f-id.v2", "title": "Replay-Hash Determinism", "layer": 2,
    }
    rows = m1._build_formula_rows([numeric_node, formal_node], "evaluation:test")
    assert len(rows) == len(puriq.numeric_demo_metadata()) + 2
    assert len({row["record_id"] for row in rows}) == len(rows)
    assert all(row["formula_status"] == "OPEN" for row in rows)
    assert all(row["training_decision"] == "HOLDOUT_ABSTENTION" for row in rows)
    assert all(row["training_eligible"] is False and row["abstention_required"] is True for row in rows)
    assert all(row["negative_example"] is False and row["can_authorize_action"] is False for row in rows)
    assert all(row["formal_binding"] == "UNKNOWN_NOT_ASSERTED" for row in rows)
    numeric = next(row for row in rows if row["record_id"] == f"{m1.NUMERIC_NAMESPACE}:F1")
    historical = next(row for row in rows if row["record_id"] == f"{m1.THESIS_NAMESPACE}:F1")
    assert numeric["brain_anatomy_receipt_id"] == m1._receipt("brain-node", numeric_node)
    assert historical["brain_anatomy_receipt_id"] is None
    assert numeric["receipt_id"] != historical["receipt_id"]


def test_graph_formula_receipt_never_binds_through_bare_f_id():
    ambiguous = {"id": "formula:F1", "kind": "formula", "formula_id": "F1"}
    formal = {**ambiguous, "formula_namespace": "lutar-lean.formal-f-id.v2"}
    assert m1._graph_formula_receipts([ambiguous, formal]) == {}
