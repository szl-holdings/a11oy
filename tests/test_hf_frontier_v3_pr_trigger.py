"""Small AST regression lock for the frontier-v3 wrapper boundary."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "hf_publish_vertical_services_frontier_v3.py"
BASE = ROOT / "scripts" / "hf_publish_vertical_services.py"


def function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_wrapper_and_base_parse_as_independent_reviewable_units() -> None:
    wrapper_source = WRAPPER.read_text(encoding="utf-8")
    base_source = BASE.read_text(encoding="utf-8")
    ast.parse(wrapper_source)
    ast.parse(base_source)
    assert {"load_base", "verify_frontier", "configure", "main"}.issubset(
        function_names(WRAPPER)
    )
    assert {"request_json", "verify_contract", "deploy_with_controller", "main"}.issubset(
        function_names(BASE)
    )


def test_wrapper_cannot_silently_expand_execution_authority() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    for fragment in (
        'SOURCE_REVISION = "e08231a110fd80f85a61fba82d72ab7f1fe23836"',
        'EXPECTED_VERSION = "2.1.0"',
        '"trading_enabled": False',
        '"custody_enabled": False',
        '"person_level_real_estate_prospecting": False',
        '"effectors_enabled": False',
        'hatun.get("can_authorize") is not False',
        'hatun.get("can_execute") is not False',
        '"Conjecture 1"',
    ):
        assert fragment in source
    assert "delete_repo" not in source
    assert "delete_space" not in source
