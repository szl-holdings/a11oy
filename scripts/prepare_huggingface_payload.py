#!/usr/bin/env python3
"""Prepare the Hugging Face payload directory from tracked source files."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path.cwd()
OUT_DIR = REPO_ROOT / "dist" / "huggingface" / "a11oy"


def git_value(*args: str, fallback: str = "unknown") -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return fallback


def copy_text(source: str, target: str) -> None:
    destination = OUT_DIR / target
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text((REPO_ROOT / source).read_text(encoding="utf-8"), encoding="utf-8")


def copy_tree(source: str, target: str) -> None:
    destination = OUT_DIR / target
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(REPO_ROOT / source, destination)


def main() -> int:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    files = [
        ("huggingface/README.md", "README.md"),
        ("huggingface/SHOWCASE.md", "SHOWCASE.md"),
        ("huggingface/INVESTOR_BRIEF.md", "INVESTOR_BRIEF.md"),
        ("huggingface/VERIFICATION.md", "VERIFICATION.md"),
        ("huggingface/INNOVATIONS_DEEP_DIVE.md", "INNOVATIONS_DEEP_DIVE.md"),
        ("huggingface/INTEGRATION_QUICKSTART.md", "INTEGRATION_QUICKSTART.md"),
        ("huggingface/EVAL_TRACE_SAMPLE.jsonl", "EVAL_TRACE_SAMPLE.jsonl"),
        ("LICENSE", "LICENSE"),
        ("CITATION.cff", "CITATION.cff"),
        ("README.md", "source/README.md"),
        ("ROADMAP.md", "source/ROADMAP.md"),
        ("CHANGELOG.md", "source/CHANGELOG.md"),
        ("docs/org-repo-map.md", "source/docs/org-repo-map.md"),
        ("docs/regulatory_to_lambda.md", "source/docs/regulatory_to_lambda.md"),
        ("docs/huggingface.md", "source/docs/huggingface.md"),
        ("docs/ecosystem-registry.json", "source/docs/ecosystem-registry.json"),
        ("docs/PROVENANCE.md", "source/docs/PROVENANCE.md"),
        ("docs/SERIES_A_DILIGENCE.md", "source/docs/SERIES_A_DILIGENCE.md"),
        ("docs/INVESTOR_DEMO.md", "source/docs/INVESTOR_DEMO.md"),
        ("docs/ECOSYSTEM_OPERATING_SYSTEM.md", "source/docs/ECOSYSTEM_OPERATING_SYSTEM.md"),
        ("docs/AUTONOMOUS_LEARNING_DOCTRINE.md", "source/docs/AUTONOMOUS_LEARNING_DOCTRINE.md"),
        ("docs/benchmark-evolution-doctrine.md", "source/docs/benchmark-evolution-doctrine.md"),
        ("docs/PUBLIC_PATTERN_SYNTHESIS.md", "source/docs/PUBLIC_PATTERN_SYNTHESIS.md"),
        ("docs/public-pattern-source-manifest.json", "source/docs/public-pattern-source-manifest.json"),
        ("docs/controls-evidence-map.json", "source/docs/controls-evidence-map.json"),
        ("docs/action-contract-manifest.json", "source/docs/action-contract-manifest.json"),
        ("docs/GITHUB_ENTERPRISE_ACCESS_RUNBOOK.md", "source/docs/GITHUB_ENTERPRISE_ACCESS_RUNBOOK.md"),
        ("docs/github-enterprise-access-checklist.json", "source/docs/github-enterprise-access-checklist.json"),
        ("docs/ANCIENT_TEXTS_FORMULA_LINEAGE.md", "source/docs/ANCIENT_TEXTS_FORMULA_LINEAGE.md"),
        ("docs/UDS_FRONTIER_GAP_MAP.md", "source/docs/UDS_FRONTIER_GAP_MAP.md"),
        ("docs/WARHACKER_UDS_PROOF_POINT.md", "source/docs/WARHACKER_UDS_PROOF_POINT.md"),
        ("docs/PERPLEXITY_BRIEF.md", "source/docs/PERPLEXITY_BRIEF.md"),
        ("docs/ECOSYSTEM.md", "source/docs/ECOSYSTEM.md"),
        ("docs/ecosystem-readiness-report.json", "source/docs/ecosystem-readiness-report.json"),
        ("docs/anatomy-formula-runtime-map.json", "source/docs/anatomy-formula-runtime-map.json"),
        ("docs/theorem-runtime-manifest.json", "source/docs/theorem-runtime-manifest.json"),
        ("benchmarks/benchmark-map.json", "source/benchmarks/benchmark-map.json"),
        ("deploy/MANIFEST.json", "payloads/deploy/MANIFEST.json"),
        ("deploy/zarf.yaml", "payloads/deploy/zarf.yaml"),
        ("deploy/attestations.jsonl", "payloads/deploy/attestations.jsonl"),
        ("package.json", "build/package.json"),
        ("pnpm-lock.yaml", "build/pnpm-lock.yaml"),
        ("pnpm-workspace.yaml", "build/pnpm-workspace.yaml"),
        ("tsconfig.base.json", "build/tsconfig.base.json"),
    ]

    for source, target in files:
        copy_text(source, target)

    if (REPO_ROOT / "NOTICE").exists():
        copy_text("NOTICE", "NOTICE")

    copy_tree("deploy/manifests", "payloads/deploy/manifests")
    copy_tree("huggingface/test-results", "test-results")

    metadata = {
        "name": "a11oy",
        "owner": "szl-holdings",
        "sourceRepository": "https://github.com/szl-holdings/a11oy",
        "sourceCommit": git_value("rev-parse", "HEAD"),
        "sourceBranch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
        "doctrineCommands": [
            "pnpm test:doctrine",
            "pnpm typecheck:doctrine",
            "pnpm build:doctrine",
            "pnpm ecosystem:audit",
            "pnpm ecosystem:readiness",
            "pnpm theorem:runtime:audit",
            "pnpm anatomy:runtime:audit",
            "pnpm benchmark:audit",
            "pnpm patterns:audit",
            "pnpm controls:audit",
            "pnpm action-contract:audit",
            "pnpm hf:test-results:audit",
            "pnpm github:access:audit",
            "pnpm payload:verify",
            "pnpm payload:huggingface",
            "pnpm payload:bundle",
            "pnpm payload:bundle:verify",
        ],
        "activeShowcaseRepos": [
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
        ],
        "excludedUntilFunded": ["carlota-jo", "counsel", "terra"],
        "retiredOrDisallowedNames": ["KORA", "LUMINA", "PARAGON", "Lyte"],
        "payloads": [
            {
                "name": "deploy",
                "manifest": "payloads/deploy/MANIFEST.json",
                "zarf": "payloads/deploy/zarf.yaml",
                "kubernetesManifests": "payloads/deploy/manifests/",
            }
        ],
    }

    (OUT_DIR / "a11oy-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Prepared Hugging Face payload at {OUT_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
