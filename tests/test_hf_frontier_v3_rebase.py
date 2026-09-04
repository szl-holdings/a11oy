"""Regression locks for the vertical frontier and intelligence publishers."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "scripts" / "hf_publish_vertical_flagships_v4.py"
INTELLIGENCE = ROOT / "scripts" / "hf_publish_vertical_services_intelligence_v4.py"
FRONTIER = ROOT / "scripts" / "hf_publish_vertical_services_frontier_v3.py"
BASE = ROOT / "scripts" / "hf_publish_vertical_services.py"


def function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_all_four_publisher_units_parse_and_remain_reviewable() -> None:
    for path in (ENTRYPOINT, INTELLIGENCE, FRONTIER, BASE):
        ast.parse(path.read_text(encoding="utf-8"))
    assert {
        "load_module",
        "constrain_public_flagships",
        "run_publisher",
        "main",
    }.issubset(function_names(ENTRYPOINT))
    assert {
        "load_v3",
        "request_text",
        "verify_intelligence",
        "configure_v4",
        "main",
    }.issubset(function_names(INTELLIGENCE))
    assert {"load_base", "verify_frontier", "configure", "main"}.issubset(
        function_names(FRONTIER)
    )
    assert {
        "request_json",
        "verify_contract",
        "deploy_with_controller",
        "main",
    }.issubset(function_names(BASE))


def test_current_four_space_topology_is_preserved() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8")
    for fragment in (
        'PUBLIC_FLAGSHIP_SLUGS = ("terra", "counsel", "finance", "lyte")',
        'FOLDED_INTO_KILLINCHU = ("sentra", "vessels")',
        'KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"',
        "constrain_public_flagships",
        "retired Killinchu capability plane reached public writer",
        'COMBINED_IMPL = HERE / "hf_publish_vertical_services_intelligence_v4.py"',
        '"szl.hf-vertical-estate/v7"',
        'flagship["public_flagship_slugs"]',
        'flagship["folded_into_killinchu"]',
        'flagship["combined_runtime"]',
        '"szl_vertical_services_intelligence_v4"',
    ):
        assert fragment in source
    assert "api.create_repo" not in source


def test_frontier_v3_remains_the_reviewed_base() -> None:
    source = FRONTIER.read_text(encoding="utf-8")
    for fragment in (
        'BASE_IMPL = HERE / "hf_publish_vertical_services.py"',
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


def test_intelligence_v4_locks_exact_source_models_kernels_and_non_authority() -> None:
    source = INTELLIGENCE.read_text(encoding="utf-8")
    for fragment in (
        'V3_IMPL = HERE / "hf_publish_vertical_services_frontier_v3.py"',
        'SOURCE_REVISION = "c24ef61716f173e48d95dad61408d9fa065f0204"',
        'EXPECTED_VERSION = "2.2.0"',
        '"sentra": "threat-shield"',
        '"lyte": "service-lattice"',
        '"killinchu": "voyage-radar"',
        '"finance": "probability-orbit"',
        '"terra": "parcel-grid"',
        '"counsel": "authority-chain"',
        '"khipu-1.5b": "SZLHOLDINGS/SZL-Khipu-1.5B"',
        '"receipt-agent": "SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2"',
        '"a11oy-mini": "SZLHOLDINGS/A11OY-MINI"',
        '"nemo-recipe": "SZLHOLDINGS/szl-nemo"',
        '"kernel-suite": "SZLHOLDINGS/szl-kernels"',
        '"lambda-gate": "SZLHOLDINGS/szl-lambda-gate"',
        '"invariants": "SZLHOLDINGS/szl-invariants"',
        '"blocked": "SZLHOLDINGS/szl-blocked"',
        '"receipt-attn": "SZLHOLDINGS/szl-receipt-attn"',
        '"block-kv": "SZLHOLDINGS/szl-block-kv"',
        '"/api/intelligence"',
        '"/intelligence/sentra"',
        '"/intelligence/counsel"',
        '"caller_supplied_endpoints_allowed": False',
        '"effectors_enabled": False',
        '"LAMBDA_BELOW_INFERENCE_FLOOR"',
        '"raw_context_returned": False',
        '"raw_context_stored": False',
        '"szl.vertical-intelligence-live-proof/v4"',
    ):
        assert fragment in source
    assert "delete_repo" not in source
    assert "delete_space" not in source
    assert "token_value_recorded\": True" not in source


def test_v4_augments_v3_and_v3_augments_base() -> None:
    frontier = FRONTIER.read_text(encoding="utf-8")
    for fragment in (
        "prior_verify = base.verify_contract",
        "result = prior_verify()",
        'result["frontier_v3"] = frontier',
        'result.get("complete") is True and frontier.get("complete") is True',
        "base.verify_contract = verify_contract_v3",
        "return int(base.main())",
    ):
        assert fragment in frontier

    intelligence = INTELLIGENCE.read_text(encoding="utf-8")
    for fragment in (
        "prior_verify_frontier = v3.verify_frontier",
        "result = prior_verify_frontier(base)",
        "intelligence_result = verify_intelligence(base)",
        'result["intelligence_v4"] = intelligence_result',
        "v3.verify_frontier = verify_frontier_v4",
        "return int(v3.main())",
    ):
        assert fragment in intelligence
