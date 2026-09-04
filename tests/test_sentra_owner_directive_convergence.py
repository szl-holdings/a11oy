# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Cross-manifest regression for the 2026-09-04 Sentra owner directive."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def literal_assignment(path: str, name: str):
    tree = ast.parse(read(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is not a literal assignment in {path}")


def test_publisher_has_distinct_sentra_target_and_only_vessels_is_folded() -> None:
    entrypoint = "scripts/hf_publish_vertical_flagships_v4.py"
    assert literal_assignment(entrypoint, "PUBLIC_FLAGSHIP_SLUGS") == (
        "terra",
        "sentra",
        "counsel",
        "finance",
        "lyte",
    )
    assert literal_assignment(entrypoint, "FOLDED_INTO_KILLINCHU") == ("vessels",)
    assert literal_assignment(entrypoint, "KILLINCHU_SPACE") == "SZLHOLDINGS/killinchu"
    assert literal_assignment(entrypoint, "SENTRA_SPACE") == "SZLHOLDINGS/sentra"


def test_public_estate_has_exact_six_products_and_preserves_history() -> None:
    estate = json.loads(read("governance/public-estate.v1.json"))
    assert estate["public_vertical_product_count"] == 6
    assert {item["id"] for item in estate["public_products"]} == {
        "killinchu",
        "sentra",
        "lyte",
        "finance",
        "terra",
        "counsel",
    }
    assert {item["id"] for item in estate["capability_planes"]} == {
        "vessels",
        "aegis",
        "immune",
    }
    assert all(
        item.get("hf_repository") != "SZLHOLDINGS/sentra"
        for item in estate["retirement_candidates"]
    )
    aegis = next(
        item
        for item in estate["decommissioned_surfaces"]
        if item["hf_repository"] == "SZLHOLDINGS/aegis-assurance"
    )
    assert aegis["state"] == "DECOMMISSIONED"
    assert aegis["mission_routes_to"] == "SZLHOLDINGS/sentra"
    assert aegis["history_preserved"] is True


def test_keep_lists_and_consolidation_controller_agree() -> None:
    for path in (
        "docs/series-a/hf-space-keep-list.yaml",
        "docs/estate/hf-nine-flagship-keep.yaml",
    ):
        policy = read(path)
        keep, retired = policy.split("retire_into_killinchu:", 1)
        assert "- id: SZLHOLDINGS/sentra" in keep
        assert "role: sole_assurance_command" in keep
        assert "- id: SZLHOLDINGS/sentra" not in retired
        assert "- id: SZLHOLDINGS/vessels" in retired
        assert "mission_routes_to: SZLHOLDINGS/sentra" in policy or (
            "mission_routes_to: https://szlholdings-sentra.hf.space" in policy
        )

    consolidation = json.loads(read("config/flagship_tab_consolidation.json"))
    by_id = {item["id"]: item for item in consolidation["flagships"]}
    assert "sentra" in by_id
    assert "sentra" not in by_id["killinchu"]["consolidates"]
    assert "immune" not in by_id["killinchu"]["capability_sources"]
    assert by_id["sentra"]["legacy_space_retirement"][
        "SZLHOLDINGS/aegis-assurance"
    ] == "DECOMMISSIONED_TO_SENTRA"


def test_product_policy_keeps_vessels_folded_and_aegis_decommissioned() -> None:
    policy = json.loads(read("docs/estate/PRODUCT_SURFACE_POLICY.json"))
    assert "sentra" in {item["slug"] for item in policy["flagship_spaces"]}
    assert "vessels" not in {item["slug"] for item in policy["flagship_spaces"]}
    assert policy["folded_surfaces"] == [
        {"slug": "vessels", "successor": "killinchu", "capability": "maritime"}
    ]
    assert policy["decommissioned_surfaces"] == [
        {"slug": "aegis-assurance", "successor": "sentra", "history_preserved": True}
    ]


def test_human_migration_ledger_routes_assurance_to_sentra() -> None:
    migration = read("docs/estate/HF_FLAGSHIP_MIGRATION.md")
    assert "Sentra is the sole Assurance Command" in migration
    assert "Aegis is absorbed history" in migration
    assert "Killinchu owns the maritime and counter-UAS command" in migration
    assert "does not own assurance" in migration
