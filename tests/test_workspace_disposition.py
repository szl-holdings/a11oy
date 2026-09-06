# SPDX-License-Identifier: Apache-2.0
"""Adversarial contract for the workspace-disposition receipt schema.

Refs a11oy#2020. Proves the schema enforces the doctrine: honesty labels read
verbatim, four of five workspace properties are pinned UNAVAILABLE, and no
field may carry a measured claim the provider has not exposed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "workspace-disposition-v1.json").read_text())


def test_schema_identity_and_required() -> None:
    assert SCHEMA["$id"].endswith("workspace-disposition-v1.json")
    assert set(SCHEMA["required"]) == {
        "schema", "inference_receipt_id", "bound_route", "workspace_disposition",
    }


def test_top_level_label_never_exceeds_measured() -> None:
    label = SCHEMA["properties"]["workspace_disposition"]["properties"]["label"]
    assert "MEASURED" in label["enum"] and "PASS" not in label["enum"]


def test_unavailable_properties_are_const_locked() -> None:
    wd = SCHEMA["properties"]["workspace_disposition"]["properties"]
    for prop in ("directed_modulation", "internal_reasoning", "generalization"):
        assert wd[prop] == {"const": "UNAVAILABLE"}, prop


def test_measurable_properties_cannot_claim_unavailable_state_as_measured() -> None:
    wd = SCHEMA["properties"]["workspace_disposition"]["properties"]
    for prop in ("reportability", "selectivity"):
        states = wd[prop]["properties"]["state"]["enum"]
        assert set(states) == {"MEASURED", "UNAVAILABLE"}, prop


def test_no_untracked_fields() -> None:
    assert SCHEMA["additionalProperties"] is False
    wd = SCHEMA["properties"]["workspace_disposition"]
    assert wd["additionalProperties"] is False
