# SPDX-License-Identifier: Apache-2.0
"""Identity regressions: reject, never normalize, ambiguous source subjects."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/workspace-disposition-v1.json").read_text())
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)


def receipt():
    return {
        "schema": "szl.workspace-disposition/v1",
        "inference_receipt_id": "route-1:receipt_2.3",
        "bound_route": {"model_revision": "a" * 40, "tokenizer_revision": "b" * 40},
        "workspace_disposition": {
            "label": "UNAVAILABLE", "claim_boundary": "BEHAVIORAL_PROXY_ONLY",
            "reportability": {"state": "UNAVAILABLE", "verbalizable_fraction": None},
            "selectivity": {"state": "UNAVAILABLE", "workspace_variance_fraction": None},
            "directed_modulation": "UNAVAILABLE", "internal_reasoning": "UNAVAILABLE",
            "generalization": "UNAVAILABLE",
        },
    }


@pytest.mark.parametrize("field", ["model_revision", "tokenizer_revision"])
@pytest.mark.parametrize("value", ["a" * 40 + "\n", "a" * 40 + "\r\n", " " + "a" * 40,
                                    "a" * 39, "a" * 41, "A" * 40, "main", "a" * 39 + "\n"])
def test_source_identity_rejects_non_exact_strings(field, value):
    data = receipt()
    data["bound_route"][field] = value
    assert not VALIDATOR.is_valid(data)
    assert data["bound_route"][field] == value  # No consumer-side trim/repair.


@pytest.mark.parametrize("value", ["r\n", "r\r\n", "r\r", "r\t", "r ", " r", "r\x00",
                                    "r\u0085", "r\u2028", "r\u2029", "r/other", "é", "", "r" * 129])
def test_receipt_identity_rejects_whitespace_controls_and_non_ascii(value):
    data = receipt()
    data["inference_receipt_id"] = value
    assert not VALIDATOR.is_valid(data)


@pytest.mark.parametrize("value", ["a", "A0-._:b", "r" * 128])
def test_valid_identifier_boundaries_remain_compatible(value):
    data = receipt()
    data["inference_receipt_id"] = value
    assert VALIDATOR.is_valid(data)


def test_only_identity_constraints_change():
    route = SCHEMA["properties"]["bound_route"]["properties"]
    for field in route.values():
        assert field["minLength"] == field["maxLength"] == 40
    w = SCHEMA["properties"]["workspace_disposition"]["properties"]
    assert w["claim_boundary"] == {"const": "BEHAVIORAL_PROXY_ONLY"}
    for field in ("directed_modulation", "internal_reasoning", "generalization"):
        assert w[field] == {"const": "UNAVAILABLE"}
