#!/usr/bin/env python3
"""Publish Packet 8 vertical Space adapters as private Docker Spaces.

Uses the org token from GitHub Actions (HF_ORG_TOKEN || HF_TOKEN).

Does not wait for RUNNING. Does not stamp LIVE. Writes evidence JSON only.
Does not mutate the canonical product Space (hf-sync.yml is the writer).

create_repo(exist_ok=True) still POSTs /api/repos/create, which Hugging Face
rate-limits at 20 Space creations per day. Probe repo_exists first and skip
create when the Space is already there, then upload_folder.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

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


def _runtime_stage(value: Any) -> str | None:
    if value is None:
        return None
    stage = getattr(value, "stage", None)
    if stage:
        return str(stage)
    if isinstance(value, dict):
        stage = value.get("stage")
        return str(stage) if stage else None
    return None


def _probe_exists(api: HfApi, repo_id: str) -> bool:
    try:
        return bool(api.repo_exists(repo_id, repo_type="space"))
    except Exception:  # noqa: BLE001
        return False


def _readback(api: HfApi, record: dict[str, Any]) -> None:
    repo_id = record["space_id"]
    try:
        info = api.space_info(repo_id)
        record["hub_private"] = bool(getattr(info, "private", True))
        record["hub_sdk"] = getattr(info, "sdk", None)
        record["hub_runtime_stage"] = _runtime_stage(getattr(info, "runtime", None))
    except Exception as exc:  # noqa: BLE001
        record["readback_error"] = f"{type(exc).__name__}: {exc}"[:500]
        try:
            runtime = api.get_space_runtime(repo_id)
            record["hub_runtime_stage"] = _runtime_stage(runtime)
        except Exception as runtime_exc:  # noqa: BLE001
            record["runtime_readback_error"] = (
                f"{type(runtime_exc).__name__}: {runtime_exc}"[:500]
            )


def _publish_one(
    api: HfApi,
    token: str,
    item: dict[str, str],
    root: Path,
    source_sha: str,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "space_id": item["space_id"],
        "vertical_id": item["vertical_id"],
        "folder": item["folder"],
        "source_sha": source_sha,
        "visibility": "private",
        "status": "ROADMAP",
        "runtime_claimed": False,
        "created": False,
    }
    folder = root / item["folder"]
    if not folder.is_dir():
        record["ok"] = False
        record["error"] = f"missing adapter folder: {item['folder']}"
        return record

    existed = _probe_exists(api, item["space_id"])
    record["existed_before"] = existed

    if not existed:
        try:
            api.create_repo(
                repo_id=item["space_id"],
                repo_type="space",
                private=True,
                space_sdk="docker",
                exist_ok=True,
                token=token,
            )
            record["created"] = True
        except Exception as exc:  # noqa: BLE001
            existed_after = _probe_exists(api, item["space_id"])
            if not existed_after:
                record["ok"] = False
                record["error"] = f"{type(exc).__name__}: {exc}"
                err_l = str(exc).lower()
                if "20 per day" in err_l or "space creation" in err_l:
                    record["blocker"] = "hub-space-creation-daily-limit"
                return record
            record["create_error_ignored"] = f"{type(exc).__name__}: {exc}"[:500]
            record["existed_before"] = True

    try:
        api.update_repo_settings(
            repo_id=item["space_id"],
            repo_type="space",
            private=True,
        )
    except Exception as exc:  # noqa: BLE001
        record["settings_warning"] = f"{type(exc).__name__}: {exc}"[:500]

    try:
        info = api.upload_folder(
            folder_path=str(folder),
            repo_id=item["space_id"],
            repo_type="space",
            commit_message=(
                "packet8: sync thin decision-assurance adapter from a11oy "
                + source_sha[:12]
            ),
            ignore_patterns=[".git*", "__pycache__", "*.pyc"],
        )
        record["commit"] = getattr(info, "oid", None) or str(info)
        record["ok"] = True
    except Exception as exc:  # noqa: BLE001
        record["ok"] = False
        record["error"] = f"{type(exc).__name__}: {exc}"
        return record

    _readback(api, record)
    record["status"] = "ROADMAP"
    record["runtime_claimed"] = False
    return record


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
    records = [_publish_one(api, token, item, root, args.source_sha) for item in SPACES]
    failed = sum(1 for rec in records if not rec.get("ok"))

    evidence = {
        "schema": "szl.packet8-hub-publish/v8",
        "source_sha": args.source_sha,
        "spaces": records,
        "all_ok": failed == 0,
        "runtime_claimed": False,
        "note": (
            "Private adapters uploaded when the Space already existed or create "
            "succeeded. Do not claim RUNNING or LIVE without Hub runtime readback."
        ),
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
