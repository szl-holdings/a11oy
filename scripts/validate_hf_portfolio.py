#!/usr/bin/env python3
"""Offline, bounded validation for the checked-in SZL Hugging Face portfolio.

This command performs no network access, reads no credentials, and makes no
external mutations.  It verifies the component-level classifications that keep
language-model weights, adapters, recipes, surrogates, kernels, and no-weight
utilities from being presented as interchangeable artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "model_release" / "hf-portfolio" / "portfolio-classification.json"
DEFAULT_SCHEMA = ROOT / "model_release" / "hf-portfolio" / "portfolio-classification.schema.json"

EXPECTED_MODELS = {
    "SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent",
    "SZLHOLDINGS/SZL-Khipu-1.5B",
    "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF",
    "SZLHOLDINGS/a11oy-v19-substrate",
    "SZLHOLDINGS/governed-inference-meter",
    "SZLHOLDINGS/szl-blocked",
    "SZLHOLDINGS/szl-formulas",
    "SZLHOLDINGS/szl-governed-norm",
    "SZLHOLDINGS/szl-govsign",
    "SZLHOLDINGS/szl-invariants",
    "SZLHOLDINGS/szl-kernels",
    "SZLHOLDINGS/szl-lambda-gate",
    "SZLHOLDINGS/szl-nemo",
    "SZLHOLDINGS/szl-ouroboros",
    "SZLHOLDINGS/szl-provctl",
}
EXPECTED_MISSING_HEALTH = {
    "SZLHOLDINGS/cosmos",
    "SZLHOLDINGS/llm-router-live",
    "SZLHOLDINGS/sda",
    "SZLHOLDINGS/szl-model-inference-lab",
}
EXPECTED_BROKEN_DATASETS = {
    "SZLHOLDINGS/canonical-formulas-v1": "HTTP_500",
    "SZLHOLDINGS/killinchu-osint-corpus": "HTTP_500",
    "SZLHOLDINGS/SZLHOLDINGS": "HTTP_500",
    "SZLHOLDINGS/uds-bundles-v1": "HTTP_500",
    "SZLHOLDINGS/szl-lake": "NO_CONFIG",
    "SZLHOLDINGS/szl-quant-sft-v1": "NO_CONFIG",
    "SZLHOLDINGS/test-results": "NO_CONFIG",
}


class PortfolioValidationError(ValueError):
    """The checked-in portfolio violates an honesty or shape invariant."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PortfolioValidationError(f"{path} must contain a JSON object")
    return value


def _validate_schema_if_available(manifest: dict[str, Any], schema_path: Path) -> bool:
    try:
        import jsonschema
    except ImportError:
        return False
    schema = _load_json(schema_path)
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(manifest)
    except (jsonschema.SchemaError, jsonschema.ValidationError) as exc:
        raise PortfolioValidationError(f"JSON Schema validation failed: {exc.message}") from exc
    return True


def validate_portfolio(
    manifest_path: Path = DEFAULT_MANIFEST,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    schema_validated = _validate_schema_if_available(manifest, schema_path)
    errors: list[str] = []

    if manifest.get("schema_version") != "szl.hf-portfolio-classification.v1":
        errors.append("unsupported schema_version")
    if manifest.get("organization") != "SZLHOLDINGS":
        errors.append("organization must be SZLHOLDINGS")

    policies = manifest.get("policies")
    if not isinstance(policies, dict):
        errors.append("policies must be an object")
        policies = {}
    expected_policy = {
        "classification_unit": "REPOSITORY_COMPONENTS_NOT_HUB_REPOSITORY_TYPE",
        "downloads_are_adoption_signal_not_quality": True,
        "zero_downloads_authorize_deletion": False,
        "unknown_repository_policy": "UNCLASSIFIED_FAIL_CLOSED",
        "promotion_authority": False,
        "delete_authority": False,
    }
    for key, expected in expected_policy.items():
        if policies.get(key) != expected:
            errors.append(f"policy mismatch: {key}")

    models = manifest.get("models")
    if not isinstance(models, list):
        errors.append("models must be an array")
        models = []
    model_ids = [item.get("repository_id") for item in models if isinstance(item, dict)]
    if len(model_ids) != len(set(model_ids)):
        errors.append("duplicate model repository_id")
    if set(model_ids) != EXPECTED_MODELS:
        errors.append("model repository inventory differs from the 2026-07-21 observation")

    class_counts: dict[str, int] = {}
    for item in models:
        if not isinstance(item, dict):
            errors.append("model item is not an object")
            continue
        repository_id = item.get("repository_id", "<unknown>")
        primary_class = item.get("primary_class")
        components = item.get("components")
        evidence_files = item.get("evidence_files")
        claims = item.get("claims")
        if not isinstance(components, list) or not components:
            errors.append(f"{repository_id}: components missing")
            components = []
        if not isinstance(evidence_files, list) or not evidence_files:
            errors.append(f"{repository_id}: evidence_files missing")
            evidence_files = []
        if not isinstance(claims, dict):
            errors.append(f"{repository_id}: claims missing")
            claims = {}
        class_counts[str(primary_class)] = class_counts.get(str(primary_class), 0) + 1

        component_claims = {
            "FULL_LANGUAGE_MODEL": "full_language_model",
            "PEFT_ADAPTER": "peft_adapter",
            "QUANTIZED_LANGUAGE_MODEL": "quantized_language_model",
            "CUSTOM_CHARACTER_MODEL": "custom_character_model",
            "SKLEARN_SURROGATE": "sklearn_surrogate",
            "TORCH_SURROGATE": "torch_surrogate",
            "RUNTIME_RECIPE": "runtime_recipe",
            "KERNEL_SOURCE": "kernel_source",
            "NO_WEIGHT_UTILITY": "no_weight_utility",
        }
        for component, claim in component_claims.items():
            if (component in components) != (claims.get(claim) is True):
                errors.append(f"{repository_id}: {component} and {claim} disagree")

        if primary_class not in components:
            errors.append(f"{repository_id}: primary_class is not a component")
        if claims.get("full_language_model") and "model.safetensors" not in evidence_files:
            errors.append(f"{repository_id}: full language model lacks exact weight evidence")
        if claims.get("peft_adapter") and "adapter/adapter_model.safetensors" not in evidence_files:
            errors.append(f"{repository_id}: PEFT adapter lacks exact weight evidence")
        if claims.get("quantized_language_model") and not any(str(name).endswith(".gguf") for name in evidence_files):
            errors.append(f"{repository_id}: quantized model lacks GGUF evidence")
        if claims.get("sklearn_surrogate") and "model.joblib" not in evidence_files:
            errors.append(f"{repository_id}: sklearn surrogate lacks model.joblib evidence")
        if claims.get("runtime_recipe") and "Modelfile" not in evidence_files:
            errors.append(f"{repository_id}: runtime recipe lacks Modelfile evidence")
        if claims.get("kernel_source") and "build.toml" not in evidence_files:
            errors.append(f"{repository_id}: kernel source lacks build.toml evidence")
        if claims.get("no_weight_utility") and any(
            str(name).endswith((".safetensors", ".gguf", ".joblib"))
            for name in evidence_files
        ):
            errors.append(f"{repository_id}: no-weight utility cites a weight artifact")
        if item.get("serving_qualified") is not False:
            errors.append(f"{repository_id}: serving qualification is not evidenced")
        if item.get("promotion_authorized") is not False:
            errors.append(f"{repository_id}: promotion must remain unauthorized")
        if item.get("delete_authorized") is not False:
            errors.append(f"{repository_id}: deletion must remain unauthorized")

    findings = manifest.get("observed_findings")
    if not isinstance(findings, dict):
        errors.append("observed_findings must be an object")
        findings = {}
    health = findings.get("docker_spaces_missing_standard_health_boundary")
    if not isinstance(health, list):
        errors.append("Docker Space findings must be an array")
        health = []
    health_ids = {
        item.get("repository_id") for item in health if isinstance(item, dict)
    }
    if health_ids != EXPECTED_MISSING_HEALTH:
        errors.append("missing-health Space inventory differs from observed four")
    for item in health:
        if not isinstance(item, dict):
            continue
        if item.get("health_state") != "STANDARD_HEALTH_BOUNDARY_NOT_FOUND":
            errors.append(f"{item.get('repository_id')}: health finding was incorrectly upgraded")

    datasets = findings.get("datasets_broken_or_no_config")
    if not isinstance(datasets, list):
        errors.append("dataset findings must be an array")
        datasets = []
    dataset_states = {
        item.get("repository_id"): item.get("dataset_server_state")
        for item in datasets
        if isinstance(item, dict)
    }
    if dataset_states != EXPECTED_BROKEN_DATASETS:
        errors.append("broken/no-config dataset inventory differs from observed seven")

    mutations = manifest.get("external_mutations")
    if not isinstance(mutations, dict) or not mutations:
        errors.append("external mutation ledger is missing")
    elif any(value is not False for value in mutations.values()):
        errors.append("external mutation ledger contains a non-false value")

    report = {
        "state": "PASS" if not errors else "FAIL",
        "offline": True,
        "network_accessed": False,
        "credentials_accessed": False,
        "external_mutation_performed": False,
        "schema_validated": schema_validated,
        "model_count": len(models),
        "class_counts": dict(sorted(class_counts.items())),
        "missing_health_space_count": len(health),
        "broken_dataset_count": len(datasets),
        "errors": errors,
    }
    if errors:
        raise PortfolioValidationError("; ".join(errors))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        report = validate_portfolio(args.manifest, args.schema)
    except (OSError, json.JSONDecodeError, PortfolioValidationError) as exc:
        report = {
            "state": "FAIL",
            "offline": True,
            "network_accessed": False,
            "credentials_accessed": False,
            "external_mutation_performed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(json.dumps(report, indent=2) if args.as_json else report["error"])
        return 1
    print(json.dumps(report, indent=2) if args.as_json else "HF portfolio classification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
