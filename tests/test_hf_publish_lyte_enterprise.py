"""Source-owned Lyte publisher and estate-routing contract tests."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "scripts" / "hf_publish_lyte_enterprise.py"
ENTRYPOINT = ROOT / "scripts" / "hf_publish_vertical_flagships_v4.py"


def function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_source_owned_publisher_is_exact_reviewable_and_non_destructive() -> None:
    source = PUBLISHER.read_text(encoding="utf-8")
    ast.parse(source)
    assert {
        "token_from_env",
        "checkout_exact_source",
        "fetch_pinned_controller",
        "ensure_runtime_configuration",
        "deploy_with_controller",
        "verify_contract",
        "main",
    }.issubset(function_names(PUBLISHER))
    for fragment in (
        'SOURCE_REPOSITORY = "szl-holdings/lyte-services"',
        'SOURCE_REVISION = "2131d2eb3611267bd62c134b6bba6b4cf7523127"',
        'EXPECTED_VERSION = "3.0.0"',
        'HF_REPOSITORY = "SZLHOLDINGS/lyte"',
        'ORIGIN = "https://szlholdings-lyte.hf.space"',
        'SOURCE_VARIABLE = "LYTE_SOURCE_REVISION"',
        'CONTROLLER_REVISION = "c889276e51e7d954c4bba8b216f86fc7577721fa"',
        'CONTROLLER_BLOB_SHA1 = "9d5b90b8bbf04e6d46ef0f971fc65604e1323b1b"',
        '"--dockerfile-path"',
        '"Dockerfile"',
        '"--require-default-branch-tip"',
        '"--prune"',
        '"--restart-space"',
        '"--attest"',
        '"/api/lyte/v3/scenario"',
        '"/api/lyte/v3/second-brain?limit=20"',
        '"/api/lyte/v3/ask"',
        '"/api/lyte/v3/hatun/evaluate"',
        '"/api/lyte/v3/github/lyte-services?limit=5"',
        '"signal_lattice"',
        '"delete_operations": 0',
        '"sentra_signing_key_touched": False',
        '"space_created": False',
        '"token_value_recorded": False',
        '"secret_values_recorded": False',
    ):
        assert fragment in source
    for forbidden in (
        "api.create_repo",
        "api.delete_repo",
        "delete_space",
        "api.add_space_secret",
        "api.get_space_secrets",
        "SENTRA_SIGNING_KEY",
    ):
        assert forbidden not in source


def test_lyte_live_admission_requires_business_observability_and_non_authority() -> None:
    source = PUBLISHER.read_text(encoding="utf-8")
    for fragment in (
        'health.get("service") == "lyte-signal-lattice"',
        'health.get("version") == EXPECTED_VERSION',
        'ready.get("build", {}).get("revision") == SOURCE_REVISION',
        'build.get("source_repository") == SOURCE_REPOSITORY',
        'len(catalog.get("lenses", [])) == 6',
        'capabilities.get("service_observability") is True',
        'capabilities.get("customer_journey_intelligence") is True',
        'capabilities.get("ai_agent_operations") is True',
        'capabilities.get("automatic_remediation") is False',
        'scenario.get("truth_label") == "SAMPLE"',
        'analysis_receipt.get("raw_session_token_recorded") is False',
        'memory.get("raw_session_token_recorded") is False',
        'ask.get("causality_claimed") is False',
        'hatun.get("decision") == "REVIEW"',
        'hatun.get("can_authorize") is False',
        'hatun.get("can_execute") is False',
        'hatun.get("effectors_enabled") is False',
        'source_observation.get("truth_label") == "REPORTED"',
    ):
        assert fragment in source


def test_estate_entrypoint_routes_lyte_away_from_generic_renderer() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8")
    ast.parse(source)
    for fragment in (
        'LYTE_IMPL = HERE / "hf_publish_lyte_enterprise.py"',
        'LYTE_RECEIPT = Path("hf-lyte-enterprise-receipt.json")',
        'PUBLIC_FLAGSHIP_SLUGS = ("terra", "counsel", "finance", "lyte")',
        'GENERATED_FLAGSHIP_SLUGS = ("terra", "counsel", "finance")',
        'SOURCE_OWNED_FLAGSHIP_SLUGS = ("lyte",)',
        'forbidden = set(FOLDED_INTO_KILLINCHU) | set(SOURCE_OWNED_FLAGSHIP_SLUGS)',
        '"szl_lyte_enterprise"',
        'flagship["lyte_runtime"] = lyte',
        'flagship["source_owned_flagship_slugs"]',
        '"szl.hf-vertical-estate/v8"',
        'lyte.get("complete") is True',
        'lyte.get("source_repository") == "szl-holdings/lyte-services"',
        'and lyte_code == 0',
        'flagship["sentra_signing_key_rotated"] = False',
        'flagship["delete_operations"] = 0',
    ):
        assert fragment in source


def test_source_owned_lyte_does_not_change_other_vertical_authority() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8")
    assert 'FOLDED_INTO_KILLINCHU = ("sentra", "vessels")' in source
    assert 'KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"' in source
    assert 'COMBINED_IMPL = HERE / "hf_publish_vertical_services_intelligence_v4.py"' in source
    assert "ensure_space_secret_reader" in source
    assert "api.create_repo" not in source
    assert "delete_repo" not in source
    assert "delete_space" not in source
