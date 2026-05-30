#!/usr/bin/env python3
"""Generate a GitHub-backed Hugging Face ecosystem manifest for SZLHOLDINGS."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path.cwd()
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "huggingface-ecosystem-manifest.json"
ORG = "SZLHOLDINGS"
OBSERVED_AT = "2026-05-30T03:43:04Z"


def fetch_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def api_items(kind: str) -> list[dict[str, Any]]:
    data = fetch_json(f"https://huggingface.co/api/{kind}?author={ORG}&limit=100")
    if not isinstance(data, list):
        raise TypeError(f"Expected list from Hugging Face {kind} API")
    return sorted(data, key=lambda item: item.get("id", ""))


def item_summary(item: dict[str, Any], repo_type: str) -> dict[str, Any]:
    item_id = item.get("id") or item.get("modelId")
    tags = item.get("tags") or []
    card = item.get("cardData") or {}
    return {
        "id": item_id,
        "repoType": repo_type,
        "private": bool(item.get("private", False)),
        "gated": bool(item.get("gated", False)),
        "disabled": bool(item.get("disabled", False)),
        "sdk": item.get("sdk"),
        "license": card.get("license") or next((tag.removeprefix("license:") for tag in tags if isinstance(tag, str) and tag.startswith("license:")), None),
        "sha": item.get("sha"),
        "lastModified": item.get("lastModified"),
        "createdAt": item.get("createdAt"),
        "tags": tags,
        "claimStatus": "generated-mirror" if item_id == "SZLHOLDINGS/a11oy-v19-substrate" else "inventory",
        "evidenceUrls": [
            f"https://huggingface.co/{item_id}",
        ],
        "unsafeFlags": unsafe_flags(str(item_id), repo_type, tags, card),
    }


def unsafe_flags(item_id: str, repo_type: str, tags: list[Any], card: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    text = json.dumps({"id": item_id, "tags": tags, "card": card}, sort_keys=True).lower()
    if any(name in text for name in ["kora", "lumina", "paragon", "lyte"]):
        flags.append("stale-product-name-review")
    if item_id in {
        "SZLHOLDINGS/counsel-source",
        "SZLHOLDINGS/terra-source",
        "SZLHOLDINGS/carlota-jo-source",
    }:
        flags.append("funded-roadmap-scaffold-not-active-demo")
    if item_id == "SZLHOLDINGS/SZLHOLDINGS":
        flags.append("org-profile-duplicate-review")
    if repo_type == "space" and any(fragment in item_id for fragment in ["deep-dive", "platform"]):
        flags.append("space-card-should-link-github-commit")
    return flags


def build_manifest() -> dict[str, Any]:
    models = [item_summary(item, "model") for item in api_items("models")]
    datasets = [item_summary(item, "dataset") for item in api_items("datasets")]
    spaces = [item_summary(item, "space") for item in api_items("spaces")]
    counts = {
        "models": len(models),
        "datasets": len(datasets),
        "spaces": len(spaces),
    }
    return {
        "schemaVersion": 1,
        "generatedBy": "scripts/audit_huggingface_ecosystem.py",
        "observedAt": OBSERVED_AT,
        "org": ORG,
        "canonicalGitHubRepo": "https://github.com/szl-holdings/a11oy",
        "canonicalRule": "GitHub releases, CI, manifests, checksums, and DOI records are canonical; Hugging Face is a generated discovery and diligence mirror.",
        "publicApiEndpoints": [
            f"https://huggingface.co/api/models?author={ORG}&limit=100",
            f"https://huggingface.co/api/datasets?author={ORG}&limit=100",
            f"https://huggingface.co/api/spaces?author={ORG}&limit=100",
        ],
        "counts": counts,
        "canonicalNumbers": {
            "hfSpaces": counts["spaces"],
            "hfDatasets": counts["datasets"],
            "hfModels": counts["models"],
            "githubPublicRepos": 19,
            "leanDeclarations": 217,
            "leanAxioms": 12,
            "leanSorries": 7,
            "anchorFormulaGates": "35/35",
            "benchmarkBaseline": "8.3% (1/12)",
        },
        "guardrails": [
            "Do not present Counsel, Terra, or Carlota Jo as active demo surfaces.",
            "Do not use KORA, LUMINA, PARAGON, or active Lyte framing.",
            "Do not claim zero-sorry or all-green Lean proof status without current machine-readable proof evidence.",
            "Do not claim signed UDS release assets exist unless tarball, signature, sha256, and public key assets are present and verify.",
        ],
        "inventory": {
            "models": models,
            "datasets": datasets,
            "spaces": spaces,
        },
        "recommendedActions": [
            {
                "target": "SZLHOLDINGS/a11oy-v19-substrate",
                "action": "Republish from dist/huggingface/a11oy after every GitHub canonical-source change.",
            },
            {
                "target": "SZLHOLDINGS/SZLHOLDINGS",
                "action": "Replace duplicate org-profile model/dataset copy with generated counts and GitHub source links, or deprecate.",
            },
            {
                "target": "source mirrors",
                "action": "Add generated card section: GitHub repo, exact commit, release/CI, DOI, claim status, limitations.",
            },
            {
                "target": "counsel-source/terra-source/carlota-jo-source",
                "action": "Mark funded-roadmap scaffold and remove from active-demo collections until funded.",
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    rendered = json.dumps(build_manifest(), indent=2, sort_keys=False) + "\n"
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            print(f"Hugging Face ecosystem manifest is stale: {output}")
            return 1
        print(f"Hugging Face ecosystem manifest is current: {output.relative_to(REPO_ROOT)}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote Hugging Face ecosystem manifest: {output.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
