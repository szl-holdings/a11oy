# SPDX-License-Identifier: Apache-2.0
"""Adversarial validation for the workspace-disposition receipt schema.

The receipt records bounded behavioral proxies only. It never claims access to
hidden internal reasoning, directed modulation, generalization, or chain of
thought.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas" / "workspace-disposition-v1.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA)


def receipt() -> dict:
    return {
        "schema": "szl.workspace-disposition/v1",
        "inference_receipt_id": "inference:receipt-001",
        "bound_route": {
            "model_revision": "a" * 40,
            "tokenizer_revision": "b" * 40,
        },
        "workspace_disposition": {
            "label": "MEASURED",
            "claim_boundary": "BEHAVIORAL_PROXY_ONLY",
            "reportability": {
                "state": "MEASURED",
                "verbalizable_fraction": 0.5,
            },
            "selectivity": {
                "state": "MEASURED",
                "workspace_variance_fraction": 0.25,
            },
            "directed_modulation": "UNAVAILABLE",
            "internal_reasoning": "UNAVAILABLE",
            "generalization": "UNAVAILABLE",
        },
    }


def validate(value: dict) -> None:
    VALIDATOR.validate(value)


def test_schema_is_valid_draft_2020_12_and_accepts_bounded_receipt() -> None:
    Draft202012Validator.check_schema(SCHEMA)
    validate(receipt())


def test_route_revisions_are_exact_lowercase_git_subjects() -> None:
    for field, invalid in (
        ("model_revision", "a" * 39),
        ("tokenizer_revision", "B" * 40),
        ("model_revision", "main"),
    ):
        candidate = receipt()
        candidate["bound_route"][field] = invalid
        with pytest.raises(ValidationError):
            validate(candidate)


def test_behavioral_proxy_boundary_is_required_and_immutable() -> None:
    missing = receipt()
    del missing["workspace_disposition"]["claim_boundary"]
    with pytest.raises(ValidationError):
        validate(missing)

    changed = receipt()
    changed["workspace_disposition"]["claim_boundary"] = "INTERNAL_STATE"
    with pytest.raises(ValidationError):
        validate(changed)


def test_measured_values_are_bounded_and_state_consistent() -> None:
    for field, value_name in (
        ("reportability", "verbalizable_fraction"),
        ("selectivity", "workspace_variance_fraction"),
    ):
        for invalid in (-0.01, 1.01, None):
            candidate = receipt()
            candidate["workspace_disposition"][field][value_name] = invalid
            with pytest.raises(ValidationError):
                validate(candidate)

        unavailable_with_value = receipt()
        unavailable_with_value["workspace_disposition"][field] = {
            "state": "UNAVAILABLE",
            value_name: 0.5,
        }
        with pytest.raises(ValidationError):
            validate(unavailable_with_value)


def test_unavailable_label_requires_both_proxies_unavailable() -> None:
    candidate = receipt()
    candidate["workspace_disposition"]["label"] = "UNAVAILABLE"
    candidate["workspace_disposition"]["reportability"] = {
        "state": "UNAVAILABLE",
        "verbalizable_fraction": None,
    }
    candidate["workspace_disposition"]["selectivity"] = {
        "state": "UNAVAILABLE",
        "workspace_variance_fraction": None,
    }
    validate(candidate)

    contradictory = copy.deepcopy(candidate)
    contradictory["workspace_disposition"]["reportability"] = {
        "state": "MEASURED",
        "verbalizable_fraction": 0.5,
    }
    with pytest.raises(ValidationError):
        validate(contradictory)


def test_measured_or_modeled_label_requires_observed_proxy_evidence() -> None:
    for label in ("MEASURED", "MODELED"):
        candidate = receipt()
        candidate["workspace_disposition"]["label"] = label
        candidate["workspace_disposition"]["reportability"] = {
            "state": "UNAVAILABLE",
            "verbalizable_fraction": None,
        }
        candidate["workspace_disposition"]["selectivity"] = {
            "state": "UNAVAILABLE",
            "workspace_variance_fraction": None,
        }
        with pytest.raises(ValidationError):
            validate(candidate)


def test_unobservable_properties_are_required_and_const_locked() -> None:
    for field in ("directed_modulation", "internal_reasoning", "generalization"):
        missing = receipt()
        del missing["workspace_disposition"][field]
        with pytest.raises(ValidationError):
            validate(missing)

        upgraded = receipt()
        upgraded["workspace_disposition"][field] = "MEASURED"
        with pytest.raises(ValidationError):
            validate(upgraded)


def test_unknown_fields_fail_closed_at_every_object_boundary() -> None:
    candidates = []

    top = receipt()
    top["untracked"] = True
    candidates.append(top)

    route = receipt()
    route["bound_route"]["provider_guess"] = "unknown"
    candidates.append(route)

    disposition = receipt()
    disposition["workspace_disposition"]["chain_of_thought"] = "available"
    candidates.append(disposition)

    nested = receipt()
    nested["workspace_disposition"]["reportability"]["untracked"] = 1
    candidates.append(nested)

    for candidate in candidates:
        with pytest.raises(ValidationError):
            validate(candidate)


def test_label_vocabulary_excludes_pass_and_live() -> None:
    labels = SCHEMA["properties"]["workspace_disposition"]["properties"]["label"]["enum"]
    assert set(labels) == {"MEASURED", "MODELED", "UNAVAILABLE"}
    assert {"PASS", "LIVE"}.isdisjoint(labels)
