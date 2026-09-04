"""Active vertical-services source-pin and authority regression contract."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "docs" / "strategy" / "vertical-services-active-pin.v1.json"
FRONTIER = ROOT / "scripts" / "hf_publish_vertical_services_frontier_v3.py"
INTELLIGENCE = ROOT / "scripts" / "hf_publish_vertical_services_intelligence_v4.py"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _string_constant(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    raise AssertionError(f"{name} is not a literal string in {path}")


def test_active_pin_matches_both_composed_publishers() -> None:
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    revision = pin["source_revision"]
    assert pin["schema"] == "szl.vertical-services-active-pin/v1"
    assert pin["repository"] == "szl-holdings/vertical-services"
    assert SHA40.fullmatch(revision)
    assert pin["runtime_version"] == "2.2.0"
    assert pin["guard"] == "require-default-branch-tip"
    assert pin["historical_strategy_manifest_rewritten"] is False
    assert _string_constant(FRONTIER, "SOURCE_REVISION") == revision
    assert _string_constant(INTELLIGENCE, "SOURCE_REVISION") == revision
    assert _string_constant(FRONTIER, "EXPECTED_VERSION") == pin["runtime_version"]
    assert _string_constant(INTELLIGENCE, "EXPECTED_VERSION") == pin["runtime_version"]


def test_defend_is_the_runtime_alias_and_immune_remains_migration_gated() -> None:
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    frontier = FRONTIER.read_text(encoding="utf-8")
    intelligence = INTELLIGENCE.read_text(encoding="utf-8")
    assert '"defend": "sentra"' in frontier
    assert '"defend": "sentra"' in intelligence
    assert '"immune": "sentra"' not in frontier
    assert '"immune": "sentra"' not in intelligence
    assert '"/experience/defend"' in frontier
    assert '"/api/verticals/defend/frontier"' in frontier
    assert '"/api/verticals/defend/intelligence"' in intelligence
    assert pin["authority"]["immune_state"] == "MIGRATION_GATED"
    assert pin["authority"]["effectors_enabled"] is False
    assert pin["authority"]["human_approval_required"] is True
