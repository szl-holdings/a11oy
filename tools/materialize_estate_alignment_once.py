#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One-use materializer for the A11oy one-fabric product contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API = "https://api.github.com"
ORG = "szl-holdings"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
USER_AGENT = "SZL-One-Fabric-Materializer/1.0"
TARGET = Path("docs/strategy/living-command-fabric.v1.json")
TEST_TARGET = Path("tests/test_estate_one_fabric_alignment.py")
REPOSITORIES = (
    "a11oy",
    "szl-formulas",
    "lutar-lean",
    "anatomy",
    "szl-second-brain",
    "szl-forge",
    "vertical-services",
    "killinchu",
    "lyte-services",
)


class MaterializationError(RuntimeError):
    """Raised when source evidence is missing or ambiguous."""


def request_json(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise MaterializationError(f"GitHub returned HTTP {exc.code} for a fixed endpoint") from exc


def exact_main_sha(repository: str, token: str) -> str:
    value = request_json(f"{API}/repos/{repository}/branches/main", token)
    sha = str((value.get("commit") or {}).get("sha") or "").lower()
    if not SHA40.fullmatch(sha):
        raise MaterializationError(f"{repository} main did not resolve to an exact SHA")
    return sha


def organization_repositories(token: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    page = 1
    while True:
        rows = request_json(
            f"{API}/orgs/{ORG}/repos?type=all&sort=full_name&direction=asc"
            f"&per_page=100&page={page}",
            token,
        )
        if not isinstance(rows, list):
            raise MaterializationError("organization repository API did not return an array")
        result.extend(row for row in rows if isinstance(row, dict))
        if len(rows) < 100:
            break
        page += 1
        if page > 10:
            raise MaterializationError("organization repository pagination exceeded bound")
    identities = [str(row.get("full_name") or "") for row in result]
    if len(identities) != len(set(identities)) or not identities:
        raise MaterializationError("organization repository census is empty or duplicated")
    return result


def update_contract(value: dict[str, Any], repos: list[dict[str, Any]], revisions: dict[str, str], source_main: str) -> None:
    if revisions["a11oy"] != source_main:
        raise MaterializationError(
            f"A11oy source changed during materialization: {source_main} -> {revisions['a11oy']}"
        )
    value["generated_at"] = "2026-09-05"
    estate = value["estate"]
    estate.update(
        {
            "repository_count": len(repos),
            "active_repository_count": sum(not bool(row.get("archived")) for row in repos),
            "archived_repository_count": sum(bool(row.get("archived")) for row in repos),
            "public_repository_count": sum(not bool(row.get("private")) for row in repos),
            "private_repository_count": sum(bool(row.get("private")) for row in repos),
            "census_method": (
                "Authenticated GitHub organization repositories API; paginated at "
                "materialization and source-bound to the reviewed candidate."
            ),
        }
    )
    value["estate_alignment_contract"] = {
        "schema": "szl.estate-alignment/v1",
        "version": "1.0.0",
        "repository": "szl-holdings/.github",
        "path": "docs/ESTATE_ALIGNMENT_CONTRACT_V1.json",
        "product_origin": "https://a-11-oy.com",
        "proof_origin": "https://a11oy.net",
        "artifact_registry": "https://huggingface.co/SZLHOLDINGS",
    }

    authorities = value["authorities"]
    authorities["a11oy"]["revision_before_wave"] = revisions["a11oy"]
    authorities["formulas"]["revision"] = revisions["szl-formulas"]
    authorities["lean_kernel"]["revision"] = revisions["lutar-lean"]
    authorities["anatomy"]["revision"] = revisions["anatomy"]
    authorities["second_brain"]["revision"] = revisions["szl-second-brain"]
    authorities["forge"]["revision"] = revisions["szl-forge"]
    authorities["vertical_services"]["revision"] = revisions["vertical-services"]
    authorities["killinchu"]["revision"] = revisions["killinchu"]
    authorities["lyte"] = {
        "repository": "szl-holdings/lyte-services",
        "revision": revisions["lyte-services"],
        "runtime_version": "3.0.0",
        "role": (
            "source-owned business, service, journey, and AI-agent observability runtime"
        ),
    }

    taxonomy = value["public_product_taxonomy"]
    taxonomy.update(
        {
            "commercial_flagship_count": 3,
            "commercial_flagships": ["a11oy", "killinchu", "forge"],
            "product_origin": "https://a-11-oy.com",
            "proof_origin": "https://a11oy.net",
            "artifact_registry": "https://huggingface.co/SZLHOLDINGS",
        }
    )

    for vertical in value["verticals"]:
        slug = vertical["slug"]
        if slug == "lyte":
            vertical.update(
                {
                    "canonical_source": "szl-holdings/lyte-services",
                    "service_source": "szl-holdings/lyte-services",
                    "service_revision": revisions["lyte-services"],
                    "service_runtime_version": "3.0.0",
                }
            )
        elif slug == "killinchu":
            vertical["canonical_revision"] = revisions["killinchu"]
            vertical["service_revision"] = revisions["vertical-services"]
        else:
            vertical["service_revision"] = revisions["vertical-services"]

    value["wave_1"]["publisher_repair"] = (
        "A11oy remains the single Hugging Face writer. Terra, Counsel and Finance "
        "use vertical-services; Killinchu owns the folded resilience planes; Lyte "
        "publishes its exact tested lyte-services runtime. Every target requires "
        "source-tip, runtime revision and live route agreement."
    )


def test_source() -> str:
    return '''#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "strategy" / "living-command-fabric.v1.json"
LOCKED = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]


class EstateOneFabricAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_one_authority_graph(self) -> None:
        contract = self.value["estate_alignment_contract"]
        self.assertEqual(contract["schema"], "szl.estate-alignment/v1")
        self.assertEqual(contract["repository"], "szl-holdings/.github")
        self.assertEqual(contract["product_origin"], "https://a-11-oy.com")
        self.assertEqual(contract["proof_origin"], "https://a11oy.net")
        self.assertEqual(contract["artifact_registry"], "https://huggingface.co/SZLHOLDINGS")

    def test_three_five_six_taxonomy(self) -> None:
        taxonomy = self.value["public_product_taxonomy"]
        self.assertEqual(taxonomy["commercial_flagships"], ["a11oy", "killinchu", "forge"])
        self.assertEqual(taxonomy["commercial_flagship_count"], 3)
        self.assertEqual(taxonomy["public_domain_bodies"], ["terra", "killinchu", "counsel", "finance", "lyte"])
        self.assertEqual(taxonomy["public_domain_body_count"], 5)
        self.assertEqual(taxonomy["internal_engines"], ["sentra", "lyte", "killinchu", "finance", "terra", "counsel"])
        self.assertEqual(taxonomy["internal_engine_count"], 6)
        self.assertEqual(taxonomy["folded_into_killinchu"], ["aegis", "sentra", "immune", "vessels"])

    def test_lyte_uses_source_owned_runtime(self) -> None:
        lyte = next(row for row in self.value["verticals"] if row["slug"] == "lyte")
        self.assertEqual(lyte["canonical_source"], "szl-holdings/lyte-services")
        self.assertEqual(lyte["service_source"], "szl-holdings/lyte-services")
        self.assertEqual(lyte["service_runtime_version"], "3.0.0")
        self.assertEqual(lyte["service_revision"], self.value["authorities"]["lyte"]["revision"])

    def test_census_and_formula_contract_are_exact(self) -> None:
        estate = self.value["estate"]
        self.assertEqual(estate["repository_count"], estate["active_repository_count"] + estate["archived_repository_count"])
        self.assertEqual(estate["repository_count"], estate["public_repository_count"] + estate["private_repository_count"])
        self.assertEqual(self.value["authorities"]["lean_kernel"]["locked_proven_ids"], LOCKED)
        self.assertEqual(self.value["authorities"]["lean_kernel"]["locked_proven_count"], 8)
        self.assertFalse(self.value["formula_contract"]["lambda"]["authorizes_actions"])


if __name__ == "__main__":
    unittest.main()
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-main", required=True)
    parser.add_argument("--receipt", type=Path, default=Path("one-fabric-materialization.json"))
    args = parser.parse_args()
    if not SHA40.fullmatch(args.source_main):
        raise MaterializationError("--source-main must be an exact lowercase SHA")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise MaterializationError("GITHUB_TOKEN is required")
    repos = organization_repositories(token)
    revisions = {name: exact_main_sha(f"{ORG}/{name}", token) for name in REPOSITORIES}
    value = json.loads(TARGET.read_text(encoding="utf-8"))
    update_contract(value, repos, revisions, args.source_main)
    TARGET.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    TEST_TARGET.write_text(test_source(), encoding="utf-8")
    receipt = {
        "schema": "szl.one-fabric-materialization/v1",
        "source_main": args.source_main,
        "repository_count": len(repos),
        "active_repository_count": value["estate"]["active_repository_count"],
        "archived_repository_count": value["estate"]["archived_repository_count"],
        "public_repository_count": value["estate"]["public_repository_count"],
        "private_repository_count": value["estate"]["private_repository_count"],
        "revisions": revisions,
        "contract_sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
        "secret_values_recorded": False,
        "provider_writes": False,
    }
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
