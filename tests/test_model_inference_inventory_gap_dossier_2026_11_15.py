#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The 2026-11-15 reconciliation matches the catalog and grants no admission."""

import json
from pathlib import Path

import a11oy_model_support as support

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / "docs/reviews/model-inference-inventory-gap-2026-11-15.json"
NOTE = ROOT / "docs/reviews/MODEL_INFERENCE_INVENTORY_GAP_2026-11-15.md"


def _inventory_ids(inventory):
    models = inventory["inventory"]["models"] if isinstance(inventory["inventory"], dict) else inventory["inventory"]
    return {row.get("id") or row.get("repo_id") or row.get("name") for row in models}


def test_reconciliation_matches_the_measured_catalog_without_admission():
    dossier = json.loads(DOSSIER.read_text(encoding="utf-8"))
    document = support.read_json(support.STATUS_PATH)
    inventory = support.read_json(support.INVENTORY_PATH)
    support.validate_document(document, inventory)
    live = {row["id"]: row for row in document["models"]}
    note = NOTE.read_text(encoding="utf-8")
    counts = dossier["counts"]
    assert counts["rows"] == 21
    assert counts["absorbed_unrecorded_rows"] == 48
    assert counts["inventory_rows_removed"] == 38
    assert counts["prior_support_rows_preserved"] == 45
    assert counts["provider_observations_http_200"] == 28
    assert counts["provider_mappings_empty"] == 28
    assert counts["provider_mappings_present"] == 0
    assert counts["verified_inference_admission_authority"] == 0
    assert counts["verified_exclusion_authority"] == 0
    assert counts["inventory_models_outside_this_record"] == 0
    assert all(value is False for value in dossier["authority"].values())
    assert dossier["runtime_change"]["inventory_rows_removed"] == 38
    assert dossier["runtime_change"]["support_rows_added"] == 21
    assert dossier["runtime_change"]["absorbed_unrecorded_rows"] == 48
    assert dossier["runtime_change"]["prior_support_rows_preserved"] == 45
    assert dossier["runtime_change"]["validator_changed"] is False
    assert dossier["runtime_change"]["authority_flags_changed"] is False

    rows = {row["id"]: row for row in dossier["rows"]}
    absorbed = {row["id"]: row for row in dossier["absorbed_rows"]}
    removed = {row["id"]: row for row in dossier["removed_rows"]}
    preserved = {row["id"]: row for row in dossier["preserved_prior_rows"]}
    restored = {row["id"]: row for row in dossier["restored_rows"]}
    assert len(rows) == 21 and len(absorbed) == 48
    assert len(removed) == 38 and len(preserved) == 45
    # The live catalog is exactly this record's rows plus absorbed plus preserved.
    assert set(live) == set(rows) | set(absorbed) | set(preserved) | set(restored)
    assert set(removed).isdisjoint(live)
    assert set(removed).isdisjoint(_inventory_ids(inventory))

    for model_id, entry in absorbed.items():
        row = live[model_id]
        fingerprint = entry["fingerprints"]
        assert entry["entered_without_dated_record"] is True
        assert fingerprint["inference_capture_sha256"] == row["inference"]["capture_sha256"]
        assert fingerprint["inference_observed_at"] == row["inference"]["observed_at"]
        assert fingerprint["assessment_hub_revision"] == row["assessment"]["hub_revision"]
        assert fingerprint["assessment_artifact_class"] == row["assessment"]["artifact_class"]
        assert fingerprint["support_state"] == row["support"]["state"]
        assert fingerprint["support_requests"] == len(row["support"]["requests"])

    for model_id, fingerprint in preserved.items():
        row = live[model_id]
        assert fingerprint["inference_capture_sha256"] == row["inference"]["capture_sha256"]
        assert fingerprint["inference_observed_at"] == row["inference"]["observed_at"]
        assert fingerprint["assessment_hub_revision"] == row["assessment"]["hub_revision"]

    for model_id, entry in removed.items():
        assert entry["final_row"]["id"] == model_id
        assert entry["removal_reason"]
    destinations = {entry["id"]: entry["evidence_destination"] for entry in dossier["removed_rows"]}
    assert "10649" in destinations["SZLHOLDINGS/a11oy-v19-substrate"]
    assert "12788" in destinations["SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2-merged"]
    discussions = {entry["discussion_number"] for entry in document["unmatched_prior_requests"]}
    assert {10649, 12788} <= discussions

    decisions = {decision["model_id"]: decision for decision in dossier["decisions"]}
    assert sorted(decisions) == sorted(set(rows) | set(restored))
    assert sorted(decision["decision_id"] for decision in dossier["decisions"]) == [
        f"D{n:02d}" for n in range(1, 29)]
    for model_id, row in rows.items():
        current = live[model_id]
        evidence = row["provider_observation"]
        assert row["inference_admission"] == "UNVERIFIED"
        assert row["exclusion_decision"] == "ABSENT"
        assert row["reconciliation"] == "RECORDED_NO_PROVIDER_MAPPING"
        assert row["admission_activated"] is False
        assert row["catalog_row_added"] is True
        assert evidence["http_status"] == 200
        assert evidence["mapping"] == "empty"
        assert evidence["state"] == "NO_PROVIDER_MAPPING"
        assert evidence["url"] == support.mapping_url(model_id)
        assert evidence["revision_matches_inventory"] is True
        assert current["inference"]["state"] == "NO_PROVIDER_MAPPING"
        assert current["inference"]["providers"] == []
        assert current["inference"]["hub_revision"] == evidence["observed_sha"]
        assert current["inference"]["capture_sha256"] == evidence["capture_sha256"]
        assert current["support"] == {"state": "NO_RECORDED_REQUEST", "requests": []}
        decision = decisions[model_id]
        assert decision["admission"] == "NOT_GRANTED"
        assert decision["selected"] is None
        assert decision["blocked_by"] == row["missing_proof"]
        assert model_id in note
        assert evidence["observed_sha"] in note
    assert counts["restored_rows"] == 7
    assert set(restored).isdisjoint(set(rows) | set(absorbed) | set(preserved))
    for model_id, row in restored.items():
        current = live[model_id]
        evidence = row["provider_observation"]
        assert row["reconciliation"] == "RECORDED_RESTORED_NO_PROVIDER_MAPPING"
        assert row["removal_reversed"] is True
        assert row["prior_removal"]["removal_reason"]
        assert evidence["http_status"] == 200
        assert evidence["mapping"] == "empty"
        assert evidence["state"] == "NO_PROVIDER_MAPPING"
        assert evidence["url"] == support.mapping_url(model_id)
        assert evidence["revision_matches_inventory"] is True
        assert current["inference"]["state"] == "NO_PROVIDER_MAPPING"
        assert current["inference"]["providers"] == []
        assert current["inference"]["hub_revision"] == evidence["observed_sha"]
        assert current["inference"]["capture_sha256"] == evidence["capture_sha256"]
        assert current["assessment"]["artifact_class"] == evidence["artifact_class"]
        assert current["support"] == {"state": "NO_RECORDED_REQUEST", "requests": []}
        decision = decisions[model_id]
        assert decision["admission"] == "NOT_GRANTED"
        assert decision["selected"] is None
        assert decision["blocked_by"] == row["missing_proof"]
        assert model_id in note
        assert evidence["observed_sha"] in note

    assert dossier["sources"]["support_model_count"] == 121
    assert dossier["sources"]["support_model_ids_sha256"] == document["inventory_source"]["model_ids_sha256"]
    assert dossier["inventory_models_outside_this_record"] == []
    assert all(value is False for value in document["authority"].values())
