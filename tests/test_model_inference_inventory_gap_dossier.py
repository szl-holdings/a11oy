#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Recorded gap observations match the catalog and do not grant admission."""

import json
from pathlib import Path

import a11oy_model_support as support

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / "docs/reviews/model-inference-inventory-gap-2026-11-07.json"
NOTE = ROOT / "docs/reviews/MODEL_INFERENCE_INVENTORY_GAP_2026-11-07.md"
DOSSIER_20261110 = ROOT / "docs/reviews/model-inference-inventory-gap-2026-11-10.json"
NOTE_20261110 = ROOT / "docs/reviews/MODEL_INFERENCE_INVENTORY_GAP_2026-11-10.md"


def test_recorded_observations_cover_the_gap_without_admission():
    dossier = json.loads(DOSSIER.read_text(encoding="utf-8"))
    document = support.read_json(support.STATUS_PATH)
    inventory = support.read_json(support.INVENTORY_PATH)
    support.validate_document(document, inventory)
    by_id = {row["id"]: row for row in document["models"]}
    # 74 rows when this review was recorded; later reviews own the whole-catalog count.
    assert dossier["sources"]["support_model_count"] == 74
    assert dossier["counts"]["provider_observations_http_200"] == 33
    assert dossier["counts"]["provider_mappings_empty"] == 33
    assert dossier["counts"]["provider_lookups_failed"] == 0
    assert dossier["counts"]["verified_inference_admission_authority"] == 0
    assert dossier["counts"]["verified_exclusion_authority"] == 0
    assert dossier["counts"]["revision_differs_from_inventory"] == 4
    assert dossier["authority"]["inference_admission"] is False
    assert dossier["runtime_change"]["prior_support_rows_preserved"] == 41
    assert dossier["runtime_change"]["inventory_rows_removed"] == 0
    assert dossier["runtime_change"]["validator_changed"] is False
    note = NOTE.read_text(encoding="utf-8")
    preserved = {row["id"]: row for row in dossier["preserved_prior_rows"]}
    assert len(preserved) == 41
    for model_id, fingerprint in preserved.items():
        current = by_id[model_id]
        assert current["inference"]["capture_sha256"] == fingerprint["inference_capture_sha256"]
        assert current["inference"]["observed_at"] == fingerprint["inference_observed_at"]
        assert current["assessment"]["hub_revision"] == fingerprint["assessment_hub_revision"]
    added = []
    for row, decision in zip(dossier["rows"], dossier["decisions"]):
        current = by_id[row["id"]]
        evidence = row["provider_observation"]
        assert row["id"] not in preserved
        assert row["inference_admission"] == "UNVERIFIED"
        assert row["exclusion_decision"] == "ABSENT"
        assert row["reconciliation"] == "RECORDED_NO_PROVIDER_MAPPING"
        assert row["admission_activated"] is False
        assert evidence["http_status"] == 200
        assert evidence["mapping"] == "empty"
        assert evidence["state"] == "NO_PROVIDER_MAPPING"
        assert current["inference"]["state"] == "NO_PROVIDER_MAPPING"
        assert current["inference"]["providers"] == []
        assert current["inference"]["hub_revision"] == evidence["observed_sha"]
        assert current["inference"]["capture_sha256"] == evidence["capture_sha256"]
        assert current["inference"]["source_url"] == evidence["url"]
        assert current["assessment"]["hub_revision"] == evidence["observed_sha"]
        assert current["assessment"]["artifact_class"] == evidence["artifact_class"]
        assert current["support"] == {"state": "NO_RECORDED_REQUEST", "requests": []}
        assert decision["selected"] is None
        assert decision["admission"] == "NOT_GRANTED"
        assert row["id"] in note
        added.append(row["id"])
    assert len(added) == 33
    assert set(added).isdisjoint(preserved)
    assert set(added) | set(preserved) <= set(by_id)
    assert all(value is False for value in document["authority"].values())


def test_recorded_2026_11_10_observations_cover_the_gap_without_admission():
    dossier = json.loads(DOSSIER_20261110.read_text(encoding="utf-8"))
    earlier = json.loads(DOSSIER.read_text(encoding="utf-8"))
    document = support.read_json(support.STATUS_PATH)
    inventory = support.read_json(support.INVENTORY_PATH)
    support.validate_document(document, inventory)
    by_id = {row["id"]: row for row in document["models"]}
    assert len(by_id) == 86
    assert dossier["sources"]["inventory_model_count"] == 86
    assert dossier["sources"]["support_model_ids_sha256"] == document["inventory_source"]["model_ids_sha256"]
    assert dossier["counts"]["provider_observations_http_200"] == 12
    assert dossier["counts"]["provider_mappings_empty"] == 12
    assert dossier["counts"]["provider_lookups_failed"] == 0
    assert dossier["counts"]["verified_inference_admission_authority"] == 0
    assert dossier["counts"]["verified_exclusion_authority"] == 0
    assert all(value is False for value in dossier["authority"].values())
    assert dossier["runtime_change"]["prior_support_rows_preserved"] == 74
    assert dossier["runtime_change"]["inventory_rows_removed"] == 0
    assert dossier["runtime_change"]["validator_changed"] is False
    note = NOTE_20261110.read_text(encoding="utf-8")
    preserved = {row["id"]: row for row in dossier["preserved_prior_rows"]}
    earlier_ids = {row["id"] for row in earlier["rows"]} | {row["id"] for row in earlier["preserved_prior_rows"]}
    assert set(preserved) == earlier_ids
    for model_id, fingerprint in preserved.items():
        current = by_id[model_id]
        assert current["inference"]["capture_sha256"] == fingerprint["inference_capture_sha256"]
        assert current["inference"]["observed_at"] == fingerprint["inference_observed_at"]
        assert current["assessment"]["hub_revision"] == fingerprint["assessment_hub_revision"]
    added = []
    for row, decision in zip(dossier["rows"], dossier["decisions"]):
        current = by_id[row["id"]]
        evidence = row["provider_observation"]
        assert row["id"] not in preserved
        assert row["inference_admission"] == "UNVERIFIED"
        assert row["exclusion_decision"] == "ABSENT"
        assert row["reconciliation"] == "RECORDED_NO_PROVIDER_MAPPING"
        assert row["admission_activated"] is False
        assert evidence["http_status"] == 200
        assert evidence["mapping"] == "empty"
        assert evidence["state"] == "NO_PROVIDER_MAPPING"
        assert current["inference"]["state"] == "NO_PROVIDER_MAPPING"
        assert current["inference"]["providers"] == []
        assert current["inference"]["hub_revision"] == evidence["observed_sha"]
        assert current["inference"]["capture_sha256"] == evidence["capture_sha256"]
        assert current["inference"]["source_url"] == evidence["url"]
        assert current["assessment"]["hub_revision"] == evidence["observed_sha"]
        assert current["assessment"]["artifact_class"] == evidence["artifact_class"]
        assert current["support"] == {"state": "NO_RECORDED_REQUEST", "requests": []}
        assert decision["model_id"] == row["id"]
        assert decision["selected"] is None
        assert decision["admission"] == "NOT_GRANTED"
        assert row["id"] in note
        added.append(row["id"])
    assert len(added) == 12
    assert set(added).isdisjoint(preserved)
    assert set(by_id) == set(added) | set(preserved)
    assert all(value is False for value in document["authority"].values())
