"""Regression locks for the rebased vertical frontier-v3 publisher."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "scripts" / "hf_publish_vertical_flagships_v4.py"
WRAPPER = ROOT / "scripts" / "hf_publish_vertical_services_frontier_v3.py"
BASE = ROOT / "scripts" / "hf_publish_vertical_services.py"


def function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_all_three_publisher_units_parse_and_remain_reviewable() -> None:
    for path in (ENTRYPOINT, WRAPPER, BASE):
        ast.parse(path.read_text(encoding="utf-8"))
    assert {"load_module", "constrain_public_flagships", "run_publisher", "main"}.issubset(
        function_names(ENTRYPOINT)
    )
    assert {"load_base", "verify_frontier", "configure", "main"}.issubset(
        function_names(WRAPPER)
    )
    assert {"request_json", "verify_contract", "deploy_with_controller", "main"}.issubset(
        function_names(BASE)
    )


def test_current_four_space_topology_is_preserved() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8")
    for fragment in (
        'PUBLIC_FLAGSHIP_SLUGS = ("terra", "counsel", "finance", "lyte")',
        'FOLDED_INTO_KILLINCHU = ("sentra", "vessels")',
        'KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"',
        "constrain_public_flagships",
        "retired Killinchu capability plane reached public writer",
        'COMBINED_IMPL = HERE / "hf_publish_vertical_services_frontier_v3.py"',
        '"szl.hf-vertical-estate/v6"',
        'flagship["public_flagship_slugs"]',
        'flagship["folded_into_killinchu"]',
        'flagship["combined_runtime"]',
    ):
        assert fragment in source
    assert "api.create_repo" not in source


def test_wrapper_locks_exact_source_and_non_authority() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    for fragment in (
        'BASE_IMPL = HERE / "hf_publish_vertical_services.py"',
        'SOURCE_REVISION = "e08231a110fd80f85a61fba82d72ab7f1fe23836"',
        'EXPECTED_VERSION = "2.1.0"',
        '"aegis": "sentra"',
        '"immune": "sentra"',
        '"puriq": "finance"',
        '"markets": "finance"',
        '"real-estate": "terra"',
        '"business-observability": "lyte"',
        '"prism": "counsel"',
        '"vessels": "killinchu"',
        '"Aegis Immune Cell"',
        '"Lyte Signal Lattice"',
        '"Killinchu Voyage Radar"',
        '"PURIQ Market Chamber"',
        '"Terra Parcel Loom"',
        '"PRISM Authority Chain"',
        '("finance", "polymarket-markets", {"limit": 5})',
        '("finance", "coinbase-spot", {"base": "BTC", "currency": "USD"})',
        '("finance", "treasury-average-rates", {"limit": 5})',
        '("terra", "nyc-hpd-violations", {"limit": 5})',
        '("terra", "nyc-dob-violations", {"limit": 5})',
        '"/api/verticals/puriq/second-brain"',
        '"/api/verticals/puriq/hatun/evaluate"',
        '"trading_enabled": False',
        '"custody_enabled": False',
        '"person_level_real_estate_prospecting": False',
        '"effectors_enabled": False',
        '"Conjecture 1"',
    ):
        assert fragment in source
    assert "delete_repo" not in source
    assert "delete_space" not in source
    assert "session_token_recorded\": True" not in source


def test_wrapper_augments_base_verification_instead_of_replacing_it() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    for fragment in (
        "prior_verify = base.verify_contract",
        "result = prior_verify()",
        'result["frontier_v3"] = frontier',
        'result.get("complete") is True and frontier.get("complete") is True',
        "base.verify_contract = verify_contract_v3",
        "return int(base.main())",
    ):
        assert fragment in source
