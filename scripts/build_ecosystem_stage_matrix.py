#!/usr/bin/env python3
"""Build the SZL ecosystem stage matrix.

The matrix is intentionally conservative: it records what is operational,
verified, staged, blocked, or excluded without turning roadmap items into
shipping claims.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path.cwd()
READINESS = REPO_ROOT / "docs" / "ecosystem-readiness-report.json"
THEOREMS = REPO_ROOT / "docs" / "theorem-runtime-manifest.json"
HF = REPO_ROOT / "docs" / "huggingface-ecosystem-manifest.json"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "ecosystem-stage-matrix.json"
OBSERVED_AT = "2026-05-30"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def stage_for_repo(repo: dict) -> str:
    status = repo["functionalDemoStatus"]
    if status == "demo-ready":
        return "operational"
    if status == "supporting":
        return "supporting-operational"
    if status == "needs-upstream-fix":
        return "blocked-upstream"
    if status == "scaffold-excluded":
        return "excluded-until-funded"
    return "roadmap"


def build_matrix() -> dict:
    readiness = load_json(READINESS)
    theorem_manifest = load_json(THEOREMS)
    hf = load_json(HF)

    repos = []
    for repo in readiness["repos"]:
        repos.append({
            "name": repo["name"],
            "stage": stage_for_repo(repo),
            "tier": repo["tier"],
            "github": repo["github"],
            "activeShowcase": repo["activeShowcase"],
            "evidence": repo["evidence"],
            "guardrails": repo["guardrails"],
            "nextAction": next_action_for_repo(repo),
        })

    formulas = []
    for entry in theorem_manifest["entries"]:
        formulas.append({
            "id": entry["id"],
            "formula": entry["formula"],
            "stage": formula_stage(entry["claimStatus"]),
            "claimStatus": entry["claimStatus"],
            "runtimeFile": entry["runtimeFile"],
            "testFile": entry["testFile"],
            "validationCommand": entry["validationCommand"],
            "caveat": entry["caveat"],
        })

    hf_items = []
    for repo_type, items in hf["inventory"].items():
        for item in items:
            hf_items.append({
                "id": item["id"],
                "repoType": repo_type[:-1] if repo_type.endswith("s") else repo_type,
                "stage": "generated-mirror" if item["id"] == "SZLHOLDINGS/a11oy-v19-substrate" else "inventory",
                "private": item["private"],
                "unsafeFlags": item["unsafeFlags"],
                "evidenceUrls": item["evidenceUrls"],
            })

    return {
        "schemaVersion": 1,
        "generatedBy": "scripts/build_ecosystem_stage_matrix.py",
        "observedAt": OBSERVED_AT,
        "doctrine": {
            "noFakeGreen": True,
            "noFakeSignedAssets": True,
            "githubCanonical": True,
            "hfGeneratedMirror": True,
            "excludedUntilFunded": ["carlota-jo", "counsel", "terra"],
        },
        "stageDefinitions": {
            "operational": "Code/tests/docs support an active demo path in GitHub.",
            "supporting-operational": "Supports the demo as library, proof, receipt, telemetry, brand, trust, or workflow infrastructure.",
            "blocked-upstream": "Requires upstream proof/CI/release correction before broad claims.",
            "proxy-ready": "Patch/artifact exists but target repo write or owner action is required.",
            "release-payload": "Included in checksummed/signed or generated payload artifacts.",
            "generated-mirror": "Published/generated Hugging Face mirror of GitHub-backed content.",
            "staged": "Prepared but not public/verified/live enough for active claims.",
            "excluded-until-funded": "Visible scaffold, intentionally outside active-demo scope.",
        },
        "canonicalNumbers": {
            "githubPublicRepos": len(readiness["repos"]),
            "hfModels": hf["counts"]["models"],
            "hfDatasets": hf["counts"]["datasets"],
            "hfSpaces": hf["counts"]["spaces"],
            "theoremRuntimeEntries": len(theorem_manifest["entries"]),
        },
        "repositories": repos,
        "formulas": formulas,
        "huggingFace": hf_items,
        "uds": {
            "stage": "operator-proof-point",
            "evidence": [
                "artifacts/a11oy-uds/README.md",
                "artifacts/a11oy-uds/docs/OPERATOR-QUICKSTART.md",
                "docs/UDS_FRONTIER_GAP_MAP.md",
                "deploy/MANIFEST.json"
            ],
            "blockedForCatalogGrade": [
                "Signed tar.zst/signature/sha256/pubkey assets must exist and verify for each v0.3.x release.",
                "UDS Package CR / Helm / monitor / network policy integration is not complete for A11oy catalog-grade packaging.",
                "Multi-repo mesh capstone requires real a11oy/amaru/sentra/rosie/vessels assets."
            ]
        }
    }


def formula_stage(status: str) -> str:
    if status == "verified-runtime":
        return "operational"
    if status.startswith("lean-backed"):
        return "blocked-upstream" if "needs" in status else "supporting-operational"
    if status == "historical-roadmap":
        return "roadmap"
    return "staged"


def next_action_for_repo(repo: dict) -> str:
    name = repo["name"]
    status = repo["functionalDemoStatus"]
    if name == "a11oy":
        return "Merge/proxy runtime hardening branches and republish HF payload from GitHub."
    if name == "lutar-lean":
        return "Apply kernel-green proxy patch in Lean-enabled runner; keep 7 sorries honest."
    if name == "agi-forecast":
        return "Merge FG-S1-S4 pipeline and competition-math v2 harness; preserve the recorded raw-score baseline unless a rerun proves improvement."
    if name in {"amaru", "rosie", "sentra", "uds-mesh", "vessels"}:
        return "Land repo-specific receipt/formula/UDS patches via proxy; do not fake signed assets."
    if status == "scaffold-excluded":
        return "Keep excluded until funded; do not market as active demo."
    return "Keep GitHub evidence current and link from generated HF surfaces."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    rendered = json.dumps(build_matrix(), indent=2) + "\n"
    output = Path(args.output)
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            print(f"Ecosystem stage matrix is stale: {output}")
            return 1
        print(f"Ecosystem stage matrix is current: {output.relative_to(REPO_ROOT)}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote ecosystem stage matrix: {output.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
