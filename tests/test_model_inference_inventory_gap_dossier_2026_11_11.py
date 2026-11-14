#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The 2026-11-11 gap observations match the catalog and do not grant admission."""

import json
from pathlib import Path

import a11oy_model_support as support

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / "docs/reviews/model-inference-inventory-gap-2026-11-11.json"
NOTE = ROOT / "docs/reviews/MODEL_INFERENCE_INVENTORY_GAP_2026-11-11.md"
# Rows added by later dated records. Each later record names its own rows, so
# exact catalog membership stays checked as this record's rows plus those.
LATER_DOSSIERS = ()
DISPOSITION = "No support discussion for this repository is recorded in this catalog."
ROUTE = "No serving route is authorized. The observed provider mapping was empty."
ASSIGNED = {
    "SZLHOLDINGS/abstention-v2-candidate",
    "SZLHOLDINGS/physics-master-v1-candidate",
}
REGENERATION = "2026-11-11T15:08:20Z"
ADAPTER_PHRASE = (
    "The recursive file list at that revision shows training checkpoint "
    "directories with adapter_config.json and adapter_model.safetensors and no "
    "root-level serving bundle."
)
NO_WEIGHTS_PHRASE = "The file list at that revision shows no safetensors, GGUF, adapter, or numpy weight file."
README_404_PHRASE = "README.md returned HTTP 404 at the revision root."


def _later_recorded_ids():
    ids = set()
    for path in LATER_DOSSIERS:
        ids |= {row["id"] for row in json.loads(path.read_text(encoding="utf-8"))["rows"]}
    return ids


def test_recorded_observations_cover_the_two_reviewed_ids_without_admission():
    dossier = json.loads(DOSSIER.read_text(encoding="utf-8"))
    document = support.read_json(support.STATUS_PATH)
    inventory = support.read_json(support.INVENTORY_PATH)
    support.validate_document(document, inventory)
    by_id = {row["id"]: row for row in document["models"]}
    later = _later_recorded_ids()
    assert len(by_id) == 90 + len(later)
    counts = dossier["counts"]
    assert counts["rows"] == 2
    assert counts["provider_observations_http_200"] == 2
    assert counts["provider_mappings_empty"] == 2
    assert counts["provider_mappings_present"] == 0
    assert counts["provider_lookups_failed"] == 0
    assert counts["provider_lookups_retried"] == 0
    assert counts["file_list_reads_retried"] == 0
    assert counts["verified_inference_admission_authority"] == 0
    assert counts["verified_exclusion_authority"] == 0
    assert counts["revision_differs_from_inventory"] == 0
    assert counts["readme_http_200"] == 0
    assert counts["readme_http_404"] == 2
    assert counts["inventory_models_outside_this_record"] == 0
    assert counts["unresolved_owner_decisions"] == 2
    assert counts["artifact_classes"] == {"adapter_bundle": 1, "non_provider_artifact": 1}
    assert all(value is False for value in dossier["authority"].values())
    assert dossier["runtime_change"]["prior_support_rows_preserved"] == 88
    assert dossier["runtime_change"]["inventory_rows_removed"] == 0
    assert dossier["runtime_change"]["validator_changed"] is False
    assert dossier["runtime_change"]["authority_flags_changed"] is False
    note = NOTE.read_text(encoding="utf-8")

    preserved = {row["id"]: row for row in dossier["preserved_prior_rows"]}
    assert len(preserved) == 88
    for model_id, fingerprint in preserved.items():
        current = by_id[model_id]
        assert current["inference"]["capture_sha256"] == fingerprint["inference_capture_sha256"]
        assert current["inference"]["observed_at"] == fingerprint["inference_observed_at"]
        assert current["assessment"]["hub_revision"] == fingerprint["assessment_hub_revision"]

    assert [row["id"] for row in dossier["rows"]] == sorted(ASSIGNED)
    assert [decision["model_id"] for decision in dossier["decisions"]] == sorted(ASSIGNED)
    decision_ids = {decision["model_id"]: decision["decision_id"] for decision in dossier["decisions"]}
    assert sorted(decision_ids.values()) == ["D01", "D02"]
    added = []
    for row, decision in zip(dossier["rows"], dossier["decisions"]):
        current = by_id[row["id"]]
        evidence = row["provider_observation"]
        assessment = current["assessment"]
        assert row["id"] not in preserved
        assert row["inference_admission"] == "UNVERIFIED"
        assert row["exclusion_decision"] == "ABSENT"
        assert row["reconciliation"] == "RECORDED_NO_PROVIDER_MAPPING"
        assert row["admission_activated"] is False
        assert row["catalog_row_added"] is True
        assert row["card_self_labels"]["authority"] == "NONE"
        assert row["release_bindings"] == []
        assert evidence["http_status"] == 200
        assert evidence["redirected"] is False
        assert evidence["mapping"] == "empty"
        assert evidence["state"] == "NO_PROVIDER_MAPPING"
        assert evidence["tree_http_status"] == 200
        assert evidence["revision_matches_inventory"] is (evidence["observed_sha"] == evidence["inventory_sha"])
        assert evidence["url"] == support.mapping_url(row["id"])
        assert row["revision"]["inventory_observed_at"] == REGENERATION
        assert row["stage_matrix"]["observed_at"] == REGENERATION
        assert current["inference"]["state"] == "NO_PROVIDER_MAPPING"
        assert current["inference"]["providers"] == []
        assert current["inference"]["error"] is None
        assert current["inference"]["hub_revision"] == evidence["observed_sha"]
        assert current["inference"]["capture_sha256"] == evidence["capture_sha256"]
        assert current["inference"]["source_url"] == evidence["url"]
        assert current["inference"]["observed_at"] == evidence["observed_at"]
        assert assessment["hub_revision"] == evidence["observed_sha"]
        assert assessment["observed_at"] == evidence["observed_at"]
        assert assessment["artifact_class"] == evidence["artifact_class"]
        assert assessment["request_disposition"] == DISPOSITION
        assert assessment["suggested_route"] == ROUTE
        qualification = assessment["qualification_note"]
        assert qualification.startswith("Provider mapping returned HTTP 200 with an empty inferenceProviderMapping.")
        assert f"Observed revision {evidence['observed_sha']} " in qualification
        assert qualification.endswith("Weights were not downloaded and the model was not run.")
        assert README_404_PHRASE in qualification
        if evidence["artifact_class"] == "adapter_bundle":
            assert ADAPTER_PHRASE in qualification
        else:
            assert evidence["artifact_class"] == "non_provider_artifact"
            assert NO_WEIGHTS_PHRASE in qualification
        assert evidence["readme_http_status"] == 404
        assert evidence["readme_sha256"] is None
        assert evidence["readme_bytes"] is None
        assert current["support"] == {"state": "NO_RECORDED_REQUEST", "requests": []}
        assert decision["selected"] is None
        assert decision["admission"] == "NOT_GRANTED"
        assert decision["blocked_by"] == row["missing_proof"]
        assert row["id"] in note
        assert evidence["observed_sha"] in note
        added.append(row["id"])
    assert len(added) == 2
    assert set(added).isdisjoint(preserved)
    assert later.isdisjoint(set(added) | set(preserved))
    assert {row["id"] for row in document["models"]} == set(added) | set(preserved) | later

    assert dossier["inventory_models_outside_this_record"] == []
    regenerations = dossier["sources"]["inventory_regenerations"]
    assert [(r["observed_at"], r["model_count"], r["rows_read_against_it"]) for r in regenerations] == [
        (REGENERATION, 90, 2),
    ]
    assert regenerations[-1]["catalog_ids_equal_inventory_ids"] is True
    assert dossier["sources"]["support_model_count"] == 90
    assert dossier["sources"]["support_model_ids_sha256"] == document["inventory_source"]["model_ids_sha256"]
    assert all(value is False for value in document["authority"].values())
