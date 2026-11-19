# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The M1 producer and admission reader agree without transferring proof credit."""

import json

import pytest

import szl_formula_training_admission as admission
import szl_m1_corpus_manifest as m1


@pytest.fixture
def current_rows(tmp_path, monkeypatch):
    knowledge = {"formulas": [{"id": f"F{i}", "latex": f"fragment {i}"} for i in range(1, 101)]}
    (tmp_path / "knowledge.json").write_text(json.dumps(knowledge), encoding="utf-8")
    monkeypatch.setattr(m1, "ROOT", tmp_path)
    rows = m1._build_formula_rows([], "evaluation:fixture")
    monkeypatch.setattr(admission, "_read_jsonl", lambda root, relative: rows)
    return tmp_path, rows, knowledge


def test_current_generator_roundtrips_with_separate_numeric_and_historical_namespaces(current_rows):
    root, rows, _ = current_rows
    index = admission._m1_formula_index(root)
    assert len(index) == len(rows) == 123
    numeric = index[(admission.M1_NUMERIC_SOURCE_FAMILY, "F1")]
    historical = index[("thesis-formula-corpus", "F1")]
    assert numeric["formula_namespace"] == admission.M1_NUMERIC_NAMESPACE
    assert historical["formula_namespace"] == admission.M1_THESIS_NAMESPACE
    assert numeric["record_id"] != historical["record_id"]
    assert numeric["formula_status"] == historical["formula_status"] == "OPEN"


@pytest.mark.parametrize("field,value,error", [
    ("source_family", "canonical-formula-registry", "NAMESPACE_MISMATCH"),
    ("formula_namespace", "lutar-lean.formal-f-id.v2", "NAMESPACE_MISMATCH"),
    ("record_id", "lutar-lean.formal-f-id.v2:F1", "NAMESPACE_MISMATCH"),
    ("formula_status", "KERNEL_ACCEPTED", "AUTHORITY_CONFLICT"),
    ("formal_binding", "PROVED", "AUTHORITY_CONFLICT"),
    ("training_eligible", True, "AUTHORITY_CONFLICT"),
    ("can_authorize_action", True, "AUTHORITY_CONFLICT"),
])
def test_reader_rejects_historical_fallback_or_unsupported_authority(current_rows, field, value, error):
    root, rows, _ = current_rows
    row = next(item for item in rows if item["source_family"] == admission.M1_NUMERIC_SOURCE_FAMILY)
    row[field] = value
    with pytest.raises(admission.AdmissionError, match=error):
        admission._m1_formula_index(root)


def test_crosswalk_never_transfers_same_id_proof_credit_from_new_m1_projection(current_rows, monkeypatch):
    root, _, knowledge = current_rows
    proof_items = [
        {"id": f"F{i}", "name": f"Separate formal statement {i}",
         "lean_ref": f"separate_formal_statement_{i}", "locked_kernel": f"F{i}" in admission.LOCKED_IDS}
        for i in range(1, 24)
    ]
    knowledge.update({"puriq_formulas": proof_items,
                      "proof_summary": {"locked_ids": sorted(admission.LOCKED_IDS)}})
    static = {"proven_formulas": proof_items}
    monkeypatch.setattr(admission, "_load_json", lambda root, relative: (
        knowledge if relative == admission.KNOWLEDGE else static))
    monkeypatch.setattr(admission, "_lean_inventory", lambda root: {
        "declarations": {item["lean_ref"] for item in proof_items},
    })
    state = {"formula_nodes": {
        f"F{i}": {"id": f"formula:F{i}", "formula_id": f"F{i}",
                  "formula_namespace": admission.M1_NUMERIC_NAMESPACE}
        for i in range(1, 24)
    }}
    records = admission._crosswalk_records(root, state)
    assert len(records) == 146
    assert all(row["proof_transfer_allowed"] is False for row in records)
    assert all(row["training_eligible"] is False and row["split"] == "HOLDOUT" for row in records)
    runtime = [row for row in records if row["formula_namespace"] == admission.RUNTIME_NAMESPACE]
    assert len(runtime) == 23
    assert all(row["resolved_status"] != "KERNEL_ACCEPTED" for row in runtime)
    assert all(row["historical_m1_status"] == "OPEN" for row in runtime)
    formal = [row for row in records if row["formula_namespace"] == admission.PROOF_NAMESPACE]
    assert any(row["resolved_status"] == "KERNEL_ACCEPTED" for row in formal)
