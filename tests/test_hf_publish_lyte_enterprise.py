"""Source-owned Lyte publisher and estate-routing contract tests."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
import tempfile
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from szl_release_guard import inspect_publisher

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
        "run_checked",
    }.issubset(function_names(PUBLISHER))
    for fragment in (
        'SOURCE_REPOSITORY = "szl-holdings/lyte-services"',
        'SOURCE_REVISION = "dd17d9f524b76c8f0e260d7ec1e084cc079dfc43"',
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
        "from szl_release_guard import",
        "run_bounded",
        "ReleaseJournal",
        "retain_manifest_metadata",
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
    expected = "dd17d9f524b76c8f0e260d7ec1e084cc079dfc43"
    assert f'SOURCE_REVISION = "{expected}"' in publisher
    assert f'LYTE_SOURCE_REVISION = "{expected}"' in entrypoint
    assert 'lyte.get("source_revision") == LYTE_SOURCE_REVISION' in entrypoint


def named_calls(tree: ast.AST) -> list[tuple[int, str]]:
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.append((node.lineno, node.func.id))
    calls.sort()
    return calls


def function_def(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


def load_publisher():
    """Load the writer without requiring huggingface_hub in the contract job."""
    try:
        import huggingface_hub  # noqa: F401
    except ImportError:
        stub = types.ModuleType("huggingface_hub")
        stub.HfApi = type("HfApi", (), {})
        sys.modules["huggingface_hub"] = stub
    spec = importlib.util.spec_from_file_location(
        "szl_hf_publish_lyte_enterprise_under_test", PUBLISHER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_run_checked_is_the_run_bounded_adapter() -> None:
    tree = ast.parse(PUBLISHER.read_text(encoding="utf-8"))
    run_checked = function_def(tree, "run_checked")
    names = [name for _, name in named_calls(run_checked)]
    assert "run_bounded" in names
    assert "subprocess" not in {
        node.attr for node in ast.walk(run_checked) if isinstance(node, ast.Attribute)
    }


def test_kit_journal_preserves_config_before_deploy_and_default_tip() -> None:
    source = PUBLISHER.read_text(encoding="utf-8")
    inspection = inspect_publisher(source)
    assert inspection["constants"]["SOURCE_REVISION"] == (
        "dd17d9f524b76c8f0e260d7ec1e084cc079dfc43"
    )
    assert inspection["config_call_lexically_before_deploy"] is True
    phases = module_constant(PUBLISHER, "WRITER_PHASES")
    assert phases.index("bind-source") < phases.index("publish-files")
    assert '"--require-default-branch-tip"' in source
    tree = ast.parse(source)
    main = function_def(tree, "main")
    names = [name for _, name in named_calls(main)]
    assert "ReleaseJournal" in names
    assert "retain_manifest_metadata" in names
    assert "ensure_runtime_configuration" in names
    assert "deploy_with_controller" in names
    finally_names: list[str] = []
    for node in ast.walk(main):
        if isinstance(node, ast.Try):
            for handler in node.finalbody:
                for call in ast.walk(handler):
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                        finally_names.append(call.func.id)
    assert "retain_manifest_metadata" in finally_names


def test_failure_manifest_observation_is_retained() -> None:
    from szl_release_guard import retain_manifest_metadata

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        missing = retain_manifest_metadata(root / "manifest.json", root / "out")
        assert missing["state"] == "ABSENT"
        assert missing["raw_manifest_published"] is False
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({
            "ref": "a" * 40,
            "hf_commit_oid": "b" * 40,
            "files": {"secret.file": {"generated_content_utf8": "DO_NOT_DISCLOSE"}},
        }), encoding="utf-8")
        parsed = retain_manifest_metadata(manifest, root / "out")
        assert parsed["state"] == "PARSED_METADATA_ONLY"
        dumped = json.dumps(parsed)
        assert "DO_NOT_DISCLOSE" not in dumped
        assert parsed["ref"] == "a" * 40


@pytest.mark.skipif(os.name != "posix", reason="run_bounded requires POSIX")
def test_run_checked_adapter_bounds_real_children() -> None:
    module = load_publisher()
    ok = module.run_checked([sys.executable, "-c", "pass"], cwd=Path.cwd())
    assert ok["passed"] is True
    assert ok["raw_output_recorded"] is False
    assert "stdout" not in ok or "captured_sha256" in ok["streams"]["stdout"]
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "child.py"
        script.write_text('print("private-token")\nraise SystemExit(2)\n', encoding="utf-8")
        with pytest.raises(RuntimeError) as failed:
            module.run_checked([sys.executable, str(script)], cwd=Path(td))
        assert "private-token" not in str(failed.value)
        assert "NONZERO_EXIT_UNCLASSIFIED" in str(failed.value)
    with pytest.raises(RuntimeError) as timed:
        module.run_checked(
            [sys.executable, "-c", "import time; time.sleep(20)"],
            cwd=Path.cwd(),
            timeout=0.15,
        )
    assert "TIMEOUT" in str(timed.value)
    assert "private-token" not in str(timed.value)
