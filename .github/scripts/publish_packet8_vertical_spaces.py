#!/usr/bin/env python3
"""Publish Packet 8 vertical Space adapters to Hugging Face as private Docker Spaces.

Uses the org token from GitHub Actions (HF_ORG_TOKEN || HF_TOKEN). Does not
wait for RUNNING. Does not stamp LIVE. Writes evidence JSON only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi, create_repo

SPACES = [
    {
        "space_id": "SZLHOLDINGS/terra-assurance",
        "folder": "huggingface/spaces/terra-assurance",
        "vertical_id": "terra",
    },
    {
        "space_id": "SZLHOLDINGS/aegis-assurance",
        "folder": "huggingface/spaces/aegis-assurance",
        "vertical_id": "aegis",
    },
    {
        "space_id": "SZLHOLDINGS/puriq-markets",
        "folder": "huggingface/spaces/puriq-markets",
        "vertical_id": "puriq-markets",
    },
    {
        "space_id": "SZLHOLDINGS/counsel-assurance",
        "folder": "huggingface/spaces/counsel-assurance",
        "vertical_id": "counsel",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-sha", default=os.environ.get("GITHUB_SHA", "UNKNOWN"))
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN") or os.environ.get("HF_ORG_TOKEN")
    if not token:
        print("HF_TOKEN / HF_ORG_TOKEN missing", file=sys.stderr)
        return 2

    root = Path(args.root).resolve()
    api = HfApi(token=token)
    records = []
    failed = 0
    for item in SPACES:
        folder = root / item["folder"]
        record = {
            "space_id": item["space_id"],
            "vertical_id": item["vertical_id"],
            "folder": item["folder"],
            "source_sha": args.source_sha,
            "visibility": "private",
            "status": "ROADMAP",
            "runtime_claimed": False,
        }
        try:
            create_repo(
                item["space_id"],
                repo_type="space",
                private=True,
                space_sdk="docker",
                exist_ok=True,
                token=token,
            )
            api.update_repo_settings(
                repo_id=item["space_id"],
                repo_type="space",
                private=True,
            )
            info = api.upload_folder(
                folder_path=str(folder),
                repo_id=item["space_id"],
                repo_type="space",
                commit_message=(
                    "packet8: sync thin decision-assurance adapter from a11oy "
                    + args.source_sha[:12]
                ),
                ignore_patterns=[".git*", "__pycache__", "*.pyc"],
            )
            record["commit"] = getattr(info, "oid", None) or str(info)
            record["ok"] = True
        except Exception as exc:  # noqa: BLE001
            failed += 1
            record["ok"] = False
            record["error"] = f"{type(exc).__name__}: {exc}"
        records.append(record)

    evidence = {
        "schema": "szl.packet8-hub-publish/v8",
        "source_sha": args.source_sha,
        "spaces": records,
        "all_ok": failed == 0,
        "runtime_claimed": False,
        "note": "Private adapters uploaded. Do not claim RUNNING or LIVE without Hub runtime readback.",
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
