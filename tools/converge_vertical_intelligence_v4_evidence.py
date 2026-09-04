#!/usr/bin/env python3
"""Converge Living Command Fabric evidence on vertical-services 2.2/v4."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "strategy" / "living-command-fabric.v1.json"
CONTRACT = ROOT / "tests" / "test_living_command_fabric_frontdoor.py"

OLD_SOURCE = "e08231a110fd80f85a61fba82d72ab7f1fe23836"
NEW_SOURCE = "83edba5c5e730c91d8f5f0a6531213fb860677af"
TAXONOMY_MERGE = "a50b1970bae4383f9760f7146436d424d5101fd3"
PUBLISHER_MERGE = "55d9336fed3a23da5b1abfed4f7f38dcc5121a06"
EXPECTED_VERSION = "2.2.0"
PUBLIC_BODIES = ["terra", "killinchu", "counsel", "finance", "lyte"]
INTERNAL_ENGINES = ["sentra", "lyte", "killinchu", "finance", "terra", "counsel"]


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_manifest() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    authorities = data["authorities"]
    vertical = authorities["vertical_services"]
    if vertical.get("revision") != OLD_SOURCE:
        raise RuntimeError(
            "vertical-services authority drifted before convergence: "
            + str(vertical.get("revision"))
        )
    vertical.update(
        {
            "revision": NEW_SOURCE,
            "runtime_version": EXPECTED_VERSION,
            "publisher": "scripts/hf_publish_vertical_services_intelligence_v4.py",
            "publisher_merge_revision": PUBLISHER_MERGE,
            "role": "combined Python intelligence fabric for six internal domain engines; published through the protected-main single writer",
        }
    )
    authorities["a11oy"]["public_taxonomy_revision"] = TAXONOMY_MERGE
    authorities["a11oy"]["intelligence_publisher_revision"] = PUBLISHER_MERGE

    verticals = data["verticals"]
    observed_public = [row["slug"] for row in verticals]
    if observed_public != PUBLIC_BODIES:
        raise RuntimeError(f"unexpected public body order: {observed_public}")
    for row in verticals:
        if row.get("service_source") != "szl-holdings/vertical-services":
            raise RuntimeError(f"unexpected service authority for {row.get('slug')}")
        previous = row.get("service_revision")
        if previous not in (None, OLD_SOURCE):
            raise RuntimeError(
                f"unexpected service revision for {row.get('slug')}: {previous}"
            )
        row["service_revision"] = NEW_SOURCE
        row["service_runtime_version"] = EXPECTED_VERSION

    taxonomy = data["public_product_taxonomy"]
    if taxonomy["public_domain_bodies"] != PUBLIC_BODIES:
        raise RuntimeError("public taxonomy changed before v4 convergence")
    if taxonomy["internal_engines"] != INTERNAL_ENGINES:
        raise RuntimeError("internal engine taxonomy changed before v4 convergence")
    taxonomy["vertical_services_revision"] = NEW_SOURCE
    taxonomy["vertical_services_runtime_version"] = EXPECTED_VERSION

    data["intelligence_fabric"] = {
        "schema": "szl.vertical-intelligence-live-proof/v4",
        "runtime_version": EXPECTED_VERSION,
        "source_repository": "szl-holdings/vertical-services",
        "source_revision": NEW_SOURCE,
        "publisher_repository": "szl-holdings/a11oy",
        "publisher_revision": PUBLISHER_MERGE,
        "public_flagship_spaces": ["terra", "counsel", "finance", "lyte"],
        "internal_engines": INTERNAL_ENGINES,
        "killinchu_capability_aliases": {
            "aegis": "sentra",
            "immune": "sentra",
            "vessels": "killinchu",
        },
        "inference_assets": [
            "SZLHOLDINGS/SZL-Khipu-1.5B",
            "SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2",
            "SZLHOLDINGS/A11OY-MINI",
        ],
        "non_invokable_recipe_record": "SZLHOLDINGS/szl-nemo",
        "kernel_assets": [
            "SZLHOLDINGS/szl-kernels",
            "SZLHOLDINGS/szl-lambda-gate",
            "SZLHOLDINGS/szl-invariants",
            "SZLHOLDINGS/szl-blocked",
            "SZLHOLDINGS/szl-receipt-attn",
            "SZLHOLDINGS/szl-block-kv",
        ],
        "authority": {
            "caller_supplied_model_endpoints": False,
            "hatun_can_authorize": False,
            "finance_can_trade_or_hold_custody": False,
            "terra_person_level_prospecting": False,
            "killinchu_effectors": "SIMULATED_OR_OPERATOR_OWNED_UNLESS_SEPARATELY_PROVED",
            "lambda": "CONJECTURE_1_ADVISORY",
        },
        "readiness_rule": "A published artifact or reachable route is not current until exact source-revision, route, connector, authority, and receipt checks pass.",
    }

    data["wave_1"]["publisher_repair"] = (
        "Bind the canonical single writer to vertical-services@"
        + NEW_SOURCE
        + " / runtime 2.2.0 through the intelligence-v4 composition layer; "
        "keep Aegis/Sentra/Immune/Vessels inside Killinchu public authority."
    )
    MANIFEST.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def patch_contract() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'PUBLISHER = ROOT / "scripts" / "hf_publish_vertical_services_frontier_v3.py"',
        'PUBLISHER = ROOT / "scripts" / "hf_publish_vertical_services_intelligence_v4.py"',
        label="publisher implementation target",
    )
    text = replace_once(
        text,
        'PUBLISHER_TEST = ROOT / "tests" / "test_hf_frontier_v3_rebase.py"',
        'PUBLISHER_TEST = ROOT / "tests" / "test_hf_publish_vertical_flagships_v4.py"',
        label="publisher test target",
    )
    text = replace_once(
        text,
        f'VERTICAL_REVISION = "{OLD_SOURCE}"',
        f'VERTICAL_REVISION = "{NEW_SOURCE}"',
        label="vertical source revision",
    )

    anchor = '''        self.assertNotIn(stale, publisher)\n        self.assertNotIn(stale, contract_test)\n\n    def test_no_new_runtime_cdn_or_embedded_vendor_source_is_introduced(self) -> None:\n'''
    insertion = '''        self.assertNotIn(stale, publisher)\n        self.assertNotIn(stale, contract_test)\n        intelligence = self.manifest["intelligence_fabric"]\n        self.assertEqual(intelligence["runtime_version"], "2.2.0")\n        self.assertEqual(intelligence["source_revision"], VERTICAL_REVISION)\n        self.assertEqual(\n            intelligence["internal_engines"],\n            ["sentra", "lyte", "killinchu", "finance", "terra", "counsel"],\n        )\n        self.assertEqual(\n            intelligence["killinchu_capability_aliases"],\n            {"aegis": "sentra", "immune": "sentra", "vessels": "killinchu"},\n        )\n        self.assertFalse(intelligence["authority"]["hatun_can_authorize"])\n        self.assertFalse(intelligence["authority"]["caller_supplied_model_endpoints"])\n\n    def test_no_new_runtime_cdn_or_embedded_vendor_source_is_introduced(self) -> None:\n'''
    text = replace_once(text, anchor, insertion, label="v4 evidence assertions")
    CONTRACT.write_text(text, encoding="utf-8")


def main() -> int:
    patch_manifest()
    patch_contract()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
