"""Source-owned Lyte publisher and estate-routing contract tests."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "scripts" / "hf_publish_lyte_enterprise.py"
CONTRACT = ROOT / "scripts" / "lyte_enterprise_live_contract.py"
ENTRYPOINT = ROOT / "scripts" / "hf_publish_vertical_flagships_v4.py"


def function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def module_constant(path: Path, name: str):
    """Return one literal module-level assignment without matching comments/docs."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    matches = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if name in targets:
                matches.append(ast.literal_eval(node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                matches.append(ast.literal_eval(node.value))
    assert len(matches) == 1, f"expected one literal assignment for {name}, found {len(matches)}"
    return matches[0]


def test_source_owned_publisher_is_exact_reviewable_and_non_destructive() -> None:
    source = PUBLISHER.read_text(encoding="utf-8")
    ast.parse(source)
    assert {
        "token_from_env", "checkout_exact_source", "fetch_pinned_controller",
        "ensure_runtime_configuration", "deploy_with_controller", "verify_contract", "main",
        "run_checked", "run_bounded", "journal",
    }.issubset(function_names(PUBLISHER))
    for fragment in (
        'SOURCE_REPOSITORY = "szl-holdings/lyte-services"',
        'SOURCE_REVISION = "9ce4e6b5f36fe0b094a07308abe3665cd2a210c1"',
        'EXPECTED_VERSION = "4.0.0"',
        'HF_REPOSITORY = "SZLHOLDINGS/lyte"',
        'ORIGIN = "https://szlholdings-lyte.hf.space"',
        'SOURCE_VARIABLE = "LYTE_SOURCE_REVISION"',
        'CONTROLLER_REVISION = "c889276e51e7d954c4bba8b216f86fc7577721fa"',
        'CONTROLLER_BLOB_SHA1 = "9d5b90b8bbf04e6d46ef0f971fc65604e1323b1b"',
        '"--dockerfile-path"', '"Dockerfile"', '"--require-default-branch-tip"',
        '"--prune"', '"--restart-space"', '"--attest"',
        'with_name("lyte_enterprise_live_contract.py")',
        'module.verify_current_contract(',
        '"delete_operations": 0', '"sentra_signing_key_touched": False',
        '"space_created": False', '"token_value_recorded": False',
        '"secret_values_recorded": False',
    ):
        assert fragment in source
    for forbidden in (
        "api.create_repo", "api.delete_repo", "delete_space", "api.add_space_secret",
        "api.get_space_secrets", "SENTRA_SIGNING_KEY",
    ):
        assert forbidden not in source
    smoke = module_constant(PUBLISHER, "SMOKE_PATHS")
    assert all("/api/lyte/v3" not in path for path in smoke)
    assert "/metrics" not in smoke
    assert {"/api/lyte/v2/catalog", "/api/lyte/v2/second-brain", "/api/lyte/v2/receipts",
            "/api/lyte/v2/metrics", "/api/build-info", "/api/source",
            "/static/lyte/styles.css", "/static/lyte/app.js"} <= set(smoke)


def test_lyte_live_admission_requires_business_observability_and_non_authority() -> None:
    source = CONTRACT.read_text(encoding="utf-8")
    ast.parse(source)
    for fragment in (
        '"szl.lyte-build/v2"', '"six observability lenses"',
        '"operational capabilities"', '"formula non-authority"', '"scoped second brain"',
        '"ask evidence and non-causality"', '"hatun review cannot authorize"',
        '"hatun execution denied"', '"authentication denial is explicit"',
        '"github observation is read-only"', '"forecast values and output digest"',
        '"forecast request independently bound"', '"fractional quantiles preserved"',
        '"raw missingness provenance"', '"granite disabled explicitly"',
        '"read and advisory calls do not mint persisted receipts"',
        '"external responsive assets"', '"complete": not failed',
        '"production_telemetry_verified": False', '"production_granite_admitted": False',
        '"execution_authority": "NONE"',
        'path = "/api/lyte/v2/metrics"', 'observe_metrics("initial")', 'observe_metrics("final")',
    ):
        assert fragment in source


def test_estate_entrypoint_routes_lyte_away_from_generic_renderer() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8")
    ast.parse(source)
    for fragment in (
        'LYTE_IMPL = HERE / "hf_publish_lyte_enterprise.py"',
        'LYTE_RECEIPT = Path("hf-lyte-enterprise-receipt.json")',
        'PUBLIC_FLAGSHIP_SLUGS = ("terra", "sentra", "counsel", "finance", "lyte")',
        'GENERATED_FLAGSHIP_SLUGS = ("terra", "sentra", "counsel", "finance")',
        'SOURCE_OWNED_FLAGSHIP_SLUGS = ("lyte",)',
        'forbidden = set(FOLDED_INTO_KILLINCHU) | set(SOURCE_OWNED_FLAGSHIP_SLUGS)',
        '"szl_lyte_enterprise"', 'flagship["lyte_runtime"] = lyte',
        'flagship["source_owned_flagship_slugs"]', '"szl.hf-vertical-estate/v8"',
        'lyte.get("complete") is True',
        'lyte.get("source_repository") == "szl-holdings/lyte-services"',
        'and lyte_code == 0', 'flagship["sentra_signing_key_rotated"] = False',
        'flagship["delete_operations"] = 0',
    ):
        assert fragment in source


def test_source_owned_lyte_does_not_change_other_vertical_authority() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8")
    ast.parse(source)
    assert module_constant(ENTRYPOINT, "FOLDED_INTO_KILLINCHU") == ("vessels",)
    assert module_constant(ENTRYPOINT, "PUBLIC_FLAGSHIP_SLUGS") == (
        "terra", "sentra", "counsel", "finance", "lyte",
    )
    assert module_constant(ENTRYPOINT, "GENERATED_FLAGSHIP_SLUGS") == (
        "terra", "sentra", "counsel", "finance",
    )
    assert module_constant(ENTRYPOINT, "SENTRA_SPACE") == "SZLHOLDINGS/sentra"
    assert module_constant(ENTRYPOINT, "KILLINCHU_SPACE") == "SZLHOLDINGS/killinchu"
    assert 'COMBINED_IMPL = HERE / "hf_publish_vertical_services_intelligence_v4.py"' in source
    assert "ensure_space_secret_reader" in source
    assert "api.create_repo" not in source
    assert "delete_repo" not in source
    assert "delete_space" not in source


def test_estate_receipt_binds_the_exact_lyte_source_revision() -> None:
    publisher = PUBLISHER.read_text(encoding="utf-8")
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    expected = "9ce4e6b5f36fe0b094a07308abe3665cd2a210c1"
    assert f'SOURCE_REVISION = "{expected}"' in publisher
    assert f'LYTE_SOURCE_REVISION = "{expected}"' in entrypoint
    assert 'lyte.get("source_revision") == LYTE_SOURCE_REVISION' in entrypoint
