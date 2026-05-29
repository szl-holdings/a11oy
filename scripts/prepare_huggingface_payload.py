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


def main() -> int:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    files = [
        ("huggingface/README.md", "README.md"),
        ("README.md", "source/README.md"),
        ("ROADMAP.md", "source/ROADMAP.md"),
        ("CHANGELOG.md", "source/CHANGELOG.md"),
        ("docs/org-repo-map.md", "source/docs/org-repo-map.md"),
        ("docs/regulatory_to_lambda.md", "source/docs/regulatory_to_lambda.md"),
        ("docs/huggingface.md", "source/docs/huggingface.md"),
        ("docs/ecosystem-registry.json", "source/docs/ecosystem-registry.json"),
        ("docs/PROVENANCE.md", "source/docs/PROVENANCE.md"),
        ("docs/ECOSYSTEM.md", "source/docs/ECOSYSTEM.md"),
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
            "pnpm payload:verify",
            "pnpm payload:bundle:verify",
        ],
        "payloads": [
            {
                "name": "deploy",
                "manifest": "payloads/deploy/MANIFEST.json",
                "zarf": "payloads/deploy/zarf.yaml",
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
