#!/usr/bin/env python3
"""Build the deterministic SZL ecosystem readiness report.

The report is intentionally offline by default. It converts the curated
ecosystem registry into a reviewable investor/UDS readiness packet and adds the
current claim guardrails observed during the GitHub deep dive. Live GitHub
status is useful for operators, but reproducible CI should not depend on network
calls.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path.cwd()
REGISTRY_PATH = REPO_ROOT / "docs" / "ecosystem-registry.json"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "ecosystem-readiness-report.json"
OBSERVED_AT = "2026-05-30"
LIVE_AUDIT_NOTES = {
    "a11oy": [
        "Live main has seven policy gate files under packages/policy/src/gates and ten theorem-runtime manifest entries; larger gate counts require merged PR evidence.",
        "uds-v0.3.0 release currently carries SBOM assets only, not signed binary payload assets.",
    ],
    "vessels": [
        "uds-v0.3.0 release was observed with zero release assets; use uds-v0.2.0 for signed-asset demonstration until v0.3.x assets land.",
        "GHCR manifest checks returned an authentication challenge in this environment; package availability needs owner-side push or visibility confirmation.",
    ],
    "lutar-lean": [
        "Putnam public language must stay at 1/12 truly discharged in Lean unless a current upstream proof report verifies more.",
    ],
}


ACTIVE_DEMO_REPOS = {
    "a11oy",
    "amaru",
    "sentra",
    "rosie",
    "ouroboros",
    "lutar-lean",
    "ouroboros-thesis",
    "uds-mesh",
    "vsp-otel",
    "vessels",
    "agi-forecast",
    "szl-trust",
    "szl-brand",
    "szl-cookbook",
    ".github",
    "platform",
}

EXCLUDED_UNTIL_FUNDED = {"counsel", "terra", "carlota-jo"}

FUNCTIONAL_STATUS = {
    "a11oy": "demo-ready",
    "vessels": "demo-ready",
    "amaru": "supporting",
    "sentra": "supporting",
    "rosie": "supporting",
    "ouroboros": "supporting",
    "uds-mesh": "supporting",
    "vsp-otel": "supporting",
    "agi-forecast": "supporting",
    "szl-trust": "supporting",
    "szl-brand": "supporting",
    "szl-cookbook": "supporting",
    ".github": "supporting",
    "platform": "supporting",
    "lutar-lean": "needs-upstream-fix",
    "ouroboros-thesis": "needs-upstream-fix",
    "counsel": "scaffold-excluded",
    "terra": "scaffold-excluded",
    "carlota-jo": "scaffold-excluded",
}

SHOWCASE_LABELS = {
    "a11oy": "Operational hub and UDS/Zarf-compatible payload publisher",
    "platform": "Canonical product integration monorepo and runtime evidence surface",
    "ouroboros": "Bounded-loop runtime and governance receipt spine",
    "lutar-lean": "Lean 4 proof substrate; cite exact closed modules and current CI",
    "ouroboros-thesis": "DOI-pinned thesis and public claim taxonomy",
    "rosie": "Khipu receipt DAG and CSS-ingress orchestration",
    "amaru": "Receipt minting, append-only provenance, and anchoring component",
    "sentra": "Telemetry, posture drift, and incident-command evidence component",
    "uds-mesh": "UDS/Zarf mesh pointer manifest and bundle topology",
    "vsp-otel": "OpenTelemetry exporter for Lambda-axis spans and receipt hashes",
    "szl-cookbook": "Operator recipes and governed-AI development patterns",
    "agi-forecast": "Governance trajectory forecast scenarios",
    "vessels": "Maritime vertical demo wedge with governed alert trails",
    "szl-trust": "Public trust and replay artifact ledger",
    "szl-brand": "Brand, anatomy, social previews, and visual doctrine",
    ".github": "Organization profile, reusable workflows, templates, and checks",
    "counsel": "Funded-roadmap legal vertical scaffold",
    "terra": "Funded-roadmap real-estate vertical scaffold",
    "carlota-jo": "Funded-roadmap advisory services scaffold",
}

EVIDENCE = {
    "a11oy": [
        "README.md",
        "docs/PROVENANCE.md",
        "docs/INVESTOR_DEMO.md",
        "artifacts/a11oy-uds/README.md",
        "deploy/MANIFEST.json",
        ".github/workflows/doctrine.yml",
        ".github/workflows/operational.yml",
        ".github/workflows/huggingface.yml",
        "https://github.com/szl-holdings/a11oy/releases/tag/v1.0.1",
        "https://github.com/szl-holdings/a11oy/releases/tag/uds-v0.2.0",
    ],
    "platform": [
        "https://github.com/szl-holdings/platform",
        "https://github.com/szl-holdings/platform/releases/tag/v1.0.0-codex-kernel",
    ],
    "ouroboros": [
        "https://github.com/szl-holdings/ouroboros",
        "https://github.com/szl-holdings/ouroboros/releases/tag/v6.3.0",
    ],
    "lutar-lean": [
        "https://github.com/szl-holdings/lutar-lean",
        "https://github.com/szl-holdings/lutar-lean/releases/tag/lutar-v18.0.0",
        "https://doi.org/10.5281/zenodo.20434308",
    ],
    "ouroboros-thesis": [
        "https://github.com/szl-holdings/ouroboros-thesis",
        "https://doi.org/10.5281/zenodo.20434276",
        "https://doi.org/10.5281/zenodo.19944926",
    ],
    "rosie": [
        "https://github.com/szl-holdings/rosie",
        "https://github.com/szl-holdings/rosie/releases/tag/v1.0.1",
        "https://github.com/szl-holdings/rosie/releases/tag/uds-v0.2.0",
    ],
    "amaru": [
        "https://github.com/szl-holdings/amaru",
        "https://github.com/szl-holdings/amaru/releases/tag/uds-v0.2.0",
    ],
    "sentra": [
        "https://github.com/szl-holdings/sentra",
        "https://github.com/szl-holdings/sentra/releases/tag/uds-v0.2.0",
    ],
    "uds-mesh": [
        "https://github.com/szl-holdings/uds-mesh",
        "https://github.com/szl-holdings/uds-mesh/releases/tag/uds-v0.2.0",
    ],
    "vsp-otel": [
        "https://github.com/szl-holdings/vsp-otel",
        "https://github.com/szl-holdings/vsp-otel/releases/tag/v0.1.0",
    ],
    "szl-cookbook": [
        "https://github.com/szl-holdings/szl-cookbook",
        "https://github.com/szl-holdings/szl-cookbook/releases/tag/v0.1.0",
    ],
    "agi-forecast": [
        "https://github.com/szl-holdings/agi-forecast",
        "https://github.com/szl-holdings/agi-forecast/releases/tag/v0.1.0",
    ],
    "vessels": [
        "https://github.com/szl-holdings/vessels",
        "https://github.com/szl-holdings/vessels/releases/tag/uds-v0.2.0",
    ],
    "szl-trust": [
        "https://github.com/szl-holdings/szl-trust",
    ],
    "szl-brand": [
        "https://github.com/szl-holdings/szl-brand",
        "https://github.com/szl-holdings/szl-brand/releases/tag/v0.1.0",
    ],
    ".github": [
        "https://github.com/szl-holdings/.github",
    ],
    "counsel": ["https://github.com/szl-holdings/counsel"],
    "terra": ["https://github.com/szl-holdings/terra"],
    "carlota-jo": ["https://github.com/szl-holdings/carlota-jo"],
}

CAVEATS = {
    "lutar-lean": [
        "Latest observed Lean kernel CI needs upstream repair before broad 'all green' or 'zero sorry' copy is repeated.",
        "Use exact theorem/module references for formal claims.",
    ],
    "ouroboros-thesis": [
        "Thesis v18.0 DOI is the current citation anchor; GitHub release list reconciliation remains an upstream action.",
        "Treat the thesis as the claim taxonomy, not blanket runtime proof.",
    ],
    "platform": [
        "Use as canonical integration evidence; keep production-readiness claims scoped to current CI and release artifacts.",
    ],
    "vessels": [
        "Use as the active vertical demo wedge; avoid implying every vertical scaffold is funded or production-ready.",
    ],
}


def repo_entry(repo: dict[str, object]) -> dict[str, object]:
    name = str(repo["name"])
    status = FUNCTIONAL_STATUS.get(name, "roadmap")
    active = name in ACTIVE_DEMO_REPOS and name not in EXCLUDED_UNTIL_FUNDED
    return {
        "name": name,
        "tier": repo.get("tier"),
        "readiness": repo.get("readiness"),
        "functionalDemoStatus": status,
        "activeShowcase": active,
        "showcaseLabel": SHOWCASE_LABELS.get(name, repo.get("role", "")),
        "role": repo.get("role"),
        "github": repo.get("github"),
        "defaultBranch": repo.get("defaultBranch"),
        "evidence": EVIDENCE.get(name, [repo.get("github")]),
        "guardrails": CAVEATS.get(name, []),
        "liveAuditNotes": LIVE_AUDIT_NOTES.get(name, []),
    }


def build_report() -> dict[str, object]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    repos = [repo_entry(repo) for repo in registry["repos"]]
    status_counts: dict[str, int] = {}
    for repo in repos:
        status = str(repo["functionalDemoStatus"])
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "schemaVersion": 1,
        "generatedBy": "scripts/build_ecosystem_readiness.py",
        "observedAt": OBSERVED_AT,
        "canonicalHub": registry["canonicalHub"],
        "huggingFaceTarget": registry["huggingFaceTarget"],
        "thesis": registry["thesis"],
        "namingPolicy": {
            "activeProductNames": [
                "a11oy",
                "amaru",
                "sentra",
                "rosie",
                "ouroboros",
                "lutar-lean",
                "ouroboros-thesis",
                "uds-mesh",
                "vsp-otel",
                "vessels",
                "agi-forecast",
                "szl-trust",
                "szl-brand",
                "szl-cookbook",
                "platform",
            ],
            "excludedUntilFunded": sorted(EXCLUDED_UNTIL_FUNDED),
            "retiredOrDisallowedInShowcase": ["KORA", "LUMINA", "PARAGON", "Lyte"],
        },
        "claimGuardrails": [
            "GitHub releases, workflows, manifests, checksums, and DOI records are canonical.",
            "Hugging Face is a generated diligence mirror, not the source of release truth.",
            "Counsel, Terra, and Carlota Jo are intentionally excluded from active-demo scope until funded.",
            "Do not repeat broad all-green or zero-sorry proof claims without a current machine-readable proof report.",
            "Do not repeat inflated Putnam closure claims; current public language is 1/12 truly discharged in Lean until upstream proof reports verify more.",
            "Do not describe SBOM-only or empty UDS v0.3.0 releases as signed binary payload releases.",
            "Do not describe unmerged G36-G40 or broader gate totals as live A11oy main runtime gates.",
            "Use Defense Unicorns UDS/Zarf-compatible phrasing; do not imply Defense Unicorns endorsement or catalog acceptance.",
        ],
        "runtimeManifestSummary": {
            "path": "docs/theorem-runtime-manifest.json",
            "trackedEntries": 10,
            "verifiedRuntimeEntries": 8,
            "stagedOrRoadmapEntries": 2,
        },
        "statusCounts": status_counts,
        "repos": repos,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--check", action="store_true", help="fail if output is stale")
    args = parser.parse_args()

    output = Path(args.output)
    report = build_report()
    rendered = json.dumps(report, indent=2, sort_keys=False) + "\n"

    if args.check:
        if not output.exists():
            print(f"Missing readiness report: {output}")
            return 1
        current = output.read_text(encoding="utf-8")
        if current != rendered:
            print(f"Readiness report is stale: {output}")
            return 1
        print(f"Readiness report is current: {output.relative_to(REPO_ROOT)}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote ecosystem readiness report: {output.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
