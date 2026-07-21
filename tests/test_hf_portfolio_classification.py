"""Offline contracts for the component-level Hugging Face estate registry."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_hf_portfolio.py"
SPEC = importlib.util.spec_from_file_location("validate_hf_portfolio", VALIDATOR_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _manifest() -> dict:
    return json.loads(validator.DEFAULT_MANIFEST.read_text(encoding="utf-8"))


def _write(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def test_checked_in_portfolio_passes_offline_and_has_exact_observed_counts() -> None:
    report = validator.validate_portfolio()
    assert report["state"] == "PASS"
    assert report["offline"] is True
    assert report["network_accessed"] is False
    assert report["credentials_accessed"] is False
    assert report["external_mutation_performed"] is False
    assert report["model_count"] == 15
    assert report["missing_health_space_count"] == 4
    assert report["broken_dataset_count"] == 7


def test_neural_models_recipes_surrogates_kernels_and_utilities_are_distinct() -> None:
    items = {item["repository_id"]: item for item in _manifest()["models"]}
    forge = items["SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent"]
    assert forge["primary_class"] == "FULL_LANGUAGE_MODEL"
    assert forge["claims"]["peft_adapter"] is True
    assert forge["claims"]["sklearn_surrogate"] is False

    nemo = items["SZLHOLDINGS/szl-nemo"]
    assert nemo["primary_class"] == "RUNTIME_RECIPE"
    assert nemo["claims"]["runtime_recipe"] is True
    assert nemo["claims"]["sklearn_surrogate"] is True
    assert nemo["claims"]["full_language_model"] is False
    assert "NOT_NEMOTRON_FINE_TUNE" in nemo["release_state"]

    substrate = items["SZLHOLDINGS/a11oy-v19-substrate"]
    assert substrate["primary_class"] == "CUSTOM_CHARACTER_MODEL"
    assert substrate["claims"]["custom_character_model"] is True

    meter = items["SZLHOLDINGS/governed-inference-meter"]
    assert meter["primary_class"] == "NO_WEIGHT_UTILITY"
    assert meter["claims"]["kernel_source"] is True
    assert meter["claims"]["no_weight_utility"] is True


def test_nemo_cannot_be_relabelled_as_a_full_language_model(tmp_path: Path) -> None:
    value = _manifest()
    nemo = next(item for item in value["models"] if item["repository_id"] == "SZLHOLDINGS/szl-nemo")
    nemo["primary_class"] = "FULL_LANGUAGE_MODEL"
    nemo["components"].append("FULL_LANGUAGE_MODEL")
    nemo["claims"]["full_language_model"] = True
    with pytest.raises(validator.PortfolioValidationError, match="exact weight evidence"):
        validator.validate_portfolio(_write(tmp_path, value))


def test_observed_broken_states_cannot_be_painted_green(tmp_path: Path) -> None:
    value = _manifest()
    value["observed_findings"]["docker_spaces_missing_standard_health_boundary"][0]["health_state"] = "HEALTHY"
    with pytest.raises(Exception):
        validator.validate_portfolio(_write(tmp_path, value))

    value = _manifest()
    value["observed_findings"]["datasets_broken_or_no_config"][0]["dataset_server_state"] = "READY"
    with pytest.raises(Exception):
        validator.validate_portfolio(_write(tmp_path, value))


def test_promotion_and_external_mutation_remain_fail_closed(tmp_path: Path) -> None:
    value = copy.deepcopy(_manifest())
    value["models"][0]["promotion_authorized"] = True
    value["external_mutations"]["hub_repository_mutated"] = True
    with pytest.raises(Exception):
        validator.validate_portfolio(_write(tmp_path, value))


def test_schema_is_valid_draft_2020_12_and_manifest_conforms() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(validator.DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    manifest = _manifest()
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(manifest)


def test_bounded_validation_command_has_no_network_or_secret_client() -> None:
    source = VALIDATOR_PATH.read_text(encoding="utf-8")
    forbidden = ("urllib", "requests", "httpx", "huggingface_hub", "socket", "HF_TOKEN")
    assert all(token not in source for token in forbidden)
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report["state"] == "PASS"
    assert report["network_accessed"] is False
    assert report["external_mutation_performed"] is False


def test_live_estate_uses_component_registry_when_feed_is_offline(monkeypatch) -> None:
    import a11oy_model_intel as intel

    monkeypatch.setattr(
        intel,
        "_cached_fetch",
        lambda *args, **kwargs: {
            "value": None,
            "freshness": {"status": "unavailable", "error": "offline test"},
        },
    )
    payload = intel.get_szl_estate()
    assert payload["state"] == "STATIC_CLASSIFICATION_LIVE_FEED_UNAVAILABLE"
    items = {item["repository_id"]: item for item in payload["models"]}
    assert items["SZLHOLDINGS/szl-nemo"]["primary_class"] == "RUNTIME_RECIPE"
    assert items["SZLHOLDINGS/a11oy-v19-substrate"]["primary_class"] == "CUSTOM_CHARACTER_MODEL"
    assert payload["summary"]["primary_classes"]["SKLEARN_SURROGATE"] == 7
    assert len(payload["observedFindings"]["datasets_broken_or_no_config"]) == 7


def test_live_file_parser_separates_adapter_joblib_gguf_and_kernel_source() -> None:
    import a11oy_model_intel as intel

    rows = intel._parse_hf_org_models([
        {
            "id": "SZLHOLDINGS/component-mix",
            "sha": "a" * 40,
            "siblings": [
                {"rfilename": "adapter/adapter_model.safetensors"},
                {"rfilename": "model.joblib"},
                {"rfilename": "weights/model-Q4_K_M.gguf"},
                {"rfilename": "build.toml"},
                {"rfilename": "build/torch-universal/example/__init__.py"},
            ],
        }
    ])
    assert len(rows) == 1
    row = rows[0]
    assert row["adapter_file_present"] is True
    assert row["sklearn_artifact_file_present"] is True
    assert row["gguf_file_present"] is True
    assert row["kernel_source_file_present"] is True
    assert row["full_checkpoint_file_present"] is False
