#!/usr/bin/env python3
"""Generate a GitHub-backed Hugging Face ecosystem manifest for SZLHOLDINGS."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "huggingface-ecosystem-manifest.json"
ORG = "SZLHOLDINGS"
PAGE_LIMIT = 100


def fetch_page(url: str) -> tuple[Any, str | None]:
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.load(response)
        link = response.headers.get("Link", "")
    next_url = None
    for part in link.split(","):
        match = re.search(r'<([^>]+)>\s*;\s*rel="?next"?', part, re.IGNORECASE)
        if match:
            next_url = match.group(1)
            break
    return data, next_url


def api_items(kind: str) -> list[dict[str, Any]]:
    url: str | None = (
        f"https://huggingface.co/api/{kind}?author={ORG}&limit={PAGE_LIMIT}"
    )
    items: dict[str, dict[str, Any]] = {}
    seen_urls: set[str] = set()
    while url:
        if url in seen_urls:
            raise RuntimeError(f"Pagination loop from Hugging Face {kind} API: {url}")
        seen_urls.add(url)
        data, url = fetch_page(url)
        if not isinstance(data, list):
            raise TypeError(f"Expected list from Hugging Face {kind} API")
        for item in data:
            if not isinstance(item, dict):
                raise TypeError(f"Expected object item from Hugging Face {kind} API")
            item_id = item.get("id") or item.get("modelId")
            if not isinstance(item_id, str) or not item_id:
                raise ValueError(f"Hugging Face {kind} API item has no repository id")
            items[item_id] = item
    return sorted(items.values(), key=lambda item: item.get("id", ""))


def observed_at_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def evidence_url(item_id: str, repo_type: str) -> str:
    prefix = {"model": "", "dataset": "datasets/", "space": "spaces/"}[repo_type]
    return f"https://huggingface.co/{prefix}{item_id}"


def display_path(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


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
            evidence_url(str(item_id), repo_type),
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


def build_manifest(*, observed_at: str) -> dict[str, Any]:
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
        "observedAt": observed_at,
        "org": ORG,
        "inventoryScope": {
            "visibility": "public-only",
            "authenticated": False,
            "privateAssetsIncluded": False,
            "countMeaning": "Items returned by the author-filtered public APIs; not the authenticated organization total.",
        },
        "canonicalGitHubRepo": "https://github.com/szl-holdings/a11oy",
        "canonicalRule": "GitHub releases, CI, manifests, checksums, and DOI records are canonical; Hugging Face is a generated discovery and diligence mirror.",
        "publicApiEndpoints": [
            f"https://huggingface.co/api/models?author={ORG}&limit={PAGE_LIMIT}",
            f"https://huggingface.co/api/datasets?author={ORG}&limit={PAGE_LIMIT}",
            f"https://huggingface.co/api/spaces?author={ORG}&limit={PAGE_LIMIT}",
        ],
        "counts": counts,
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
    parser.add_argument(
        "--observed-at",
        help="Explicit RFC 3339 observation time for deterministic generation.",
    )
    args = parser.parse_args()
    output = Path(args.output)
    if args.check:
        if not output.exists():
            print(f"Hugging Face ecosystem manifest is stale: {output}")
            return 1
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
            observed_at = existing["observedAt"]
            if not isinstance(observed_at, str) or not observed_at:
                raise ValueError("observedAt must be a non-empty string")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            print(f"Hugging Face ecosystem manifest is invalid: {output}: {exc}")
            return 1
        rendered = (
            json.dumps(
                build_manifest(observed_at=observed_at),
                indent=2,
                sort_keys=False,
            )
            + "\n"
        )
        if output.read_text(encoding="utf-8") != rendered:
            print(f"Hugging Face ecosystem manifest is stale: {output}")
            return 1
        print(f"Hugging Face ecosystem manifest is current: {display_path(output)}")
        return 0
    observed_at = args.observed_at or observed_at_now()
    rendered = (
        json.dumps(
            build_manifest(observed_at=observed_at),
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote Hugging Face ecosystem manifest: {display_path(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
