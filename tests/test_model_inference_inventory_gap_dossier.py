#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""The inventory-gap dossier matches the canonical files and admits nothing."""

import json
from pathlib import Path

import pytest

import a11oy_model_support as support

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / "docs/reviews/model-inference-inventory-gap-2026-11-07.json"
NOTE = ROOT / "docs/reviews/MODEL_INFERENCE_INVENTORY_GAP_2026-11-07.md"


def _gap_ids():
    document = support.read_json(support.STATUS_PATH)
    inventory = support.read_json(support.INVENTORY_PATH)
    present = {row["id"] for row in document["models"]}
    return [
        row["id"]
        for row in inventory["inventory"]["models"]
        if row.get("repoType") == "model" and row.get("id") not in present
    ]


def test_dossier_is_the_exact_gap_and_admits_nothing():
    dossier = json.loads(DOSSIER.read_text(encoding="utf-8"))
    expected = _gap_ids()
    got = [row["id"] for row in dossier["rows"]]
    assert got == expected
    assert len(got) == 33
    assert len(set(got)) == 33
    counts = dossier["counts"]
    assert counts["rows"] == 33
    assert counts["verified_inventory_observations"] == 33
    assert counts["verified_inference_admission_authority"] == 0
    assert counts["verified_exclusion_authority"] == 0
    assert counts["proposed_hold"] == 33
    assert counts["unverified_support_rows"] == 33
    assert counts["unresolved_decisions"] == 33
    assert dossier["runtime_change"] == {
        "support_rows_added": 0,
        "inventory_rows_removed": 0,
        "validator_changed": False,
        "coverage_expectation_changed": False,
    }
    assert dossier["authority"]["inference_admission"] is False
    assert dossier["authority"]["exclusion"] is False
    inventory = support.read_json(support.INVENTORY_PATH)
    by_id = {row["id"]: (index, row) for index, row in enumerate(inventory["inventory"]["models"])}
    decisions = {item["model_id"]: item for item in dossier["decisions"]}
    note = NOTE.read_text(encoding="utf-8")
    for number, row in enumerate(dossier["rows"], start=1):
        index, source = by_id[row["id"]]
        assert row["inventory_observation"] == "VERIFIED"
        assert row["inference_admission"] == "UNVERIFIED"
        assert row["exclusion_decision"] == "ABSENT"
        assert row["reconciliation"] == "PROPOSED_HOLD"
        assert row["activated_in_runtime"] is False
        assert row["revision"]["sha"] == source["sha"]
        assert row["identity"]["json_pointer"] == f"/inventory/models/{index}"
        assert row["stage_matrix"]["stage"] == "inventory"
        assert row["revision_class"]["explicit_entry"] is False
        assert row["revision_class"]["class"] == "SOURCE_TRACKED"
        assert row["release_bindings"] == []
        assert row["support_catalog"]["row_present"] is False
        assert row["card_self_labels"]["authority"] == "NONE"
        assert row["card_declared_lineage"]["verification"] == "UNVERIFIED"
        assert row["hub_overview"]["resolved"] is True
        assert row["hub_overview"]["sha_returned"] is False
        assert row["hub_overview"]["inference_provider_mapping_returned"] is False
        assert set(row["hub_overview"]["self_labels_also_seen"]) <= set(row["card_self_labels"]["from_inventory_tags"])
        assert len(row["missing_proof"]) == 4
        decision = decisions[row["id"]]
        assert decision["decision_id"] == f"D{number:02d}"
        assert decision["selected"] is None
        assert decision["proposal"] == "PROPOSED_HOLD"
        assert row["id"] in note
        assert decision["decision_id"] in note
    document = support.read_json(support.STATUS_PATH)
    assert len(document["models"]) == 41
    assert {row["id"] for row in document["models"]}.isdisjoint(got)
    with pytest.raises(support.SupportDataError, match="inventory coverage differs"):
        support.validate_document(document, inventory)
