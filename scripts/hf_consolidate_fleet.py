#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Consolidate the SZLHOLDINGS Space estate around the canonical public keep set.

Safety contract:
- never deletes a Space;
- never changes hardware or billing settings;
- canonical keep Spaces are public and restarted when not RUNNING;
- every other Space is made private, then paused when the SDK/runtime permits it;
- all mutations are receipt-bound and token values are never emitted.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
from typing import Any

from huggingface_hub import HfApi
from huggingface_hub.utils import HfHubHTTPError

DEFAULT_ORG = "SZLHOLDINGS"
DEFAULT_POLICY = Path("docs/series-a/hf-space-keep-list.yaml")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def token_from_env() -> tuple[str | None, str | None]:
    for key in ("HF_ORG_TOKEN", "HF_WRITE_TOKEN", "HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        value = os.getenv(key)
        if value and value.strip():
            return value.strip(), key
    return None, None


def load_keep_set(path: Path, org: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    keep = {
        m.group(1)
        for m in re.finditer(r"^\s*-\s+id:\s*([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)\s*$", text, re.MULTILINE)
    }
    bad = sorted(repo for repo in keep if not repo.startswith(org + "/"))
    if bad:
        raise RuntimeError(f"policy contains foreign repo ids: {bad}")
    if not keep:
        raise RuntimeError("policy keep set is empty")
    return keep


def as_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    data = getattr(obj, "__dict__", None)
    return dict(data) if isinstance(data, dict) else {}


def repo_id(item: Any) -> str:
    return str(getattr(item, "id", None) or getattr(item, "repo_id", None) or as_dict(item).get("id") or "")


def is_private(item: Any) -> bool:
    return bool(getattr(item, "private", None) if hasattr(item, "private") else as_dict(item).get("private"))


def sdk_name(item: Any) -> str:
    return str(getattr(item, "sdk", None) or as_dict(item).get("sdk") or "unknown")


def stage(api: HfApi, rid: str) -> str:
    try:
        return str(api.get_space_runtime(rid).stage or "UNKNOWN").upper()
    except Exception as exc:
        return f"ERROR:{type(exc).__name__}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--org", default=DEFAULT_ORG)
    p.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    p.add_argument("--out", type=Path, default=Path("hf-consolidation-receipt.json"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    token, token_source = token_from_env()
    if not token:
        raise SystemExit("No Hugging Face write token available in the approved environment variables")

    keep = load_keep_set(args.policy, args.org)
    api = HfApi(token=token)
    spaces = list(api.list_spaces(author=args.org, full=True))
    ids = {repo_id(x) for x in spaces if repo_id(x)}
    missing_keep = sorted(keep - ids)

    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": now(),
        "org": args.org,
        "token_source": token_source,
        "token_value_persisted": False,
        "mode": "dry-run" if args.dry_run else "apply",
        "policy": str(args.policy),
        "inventory_total": len(spaces),
        "keep_target": sorted(keep),
        "missing_keep": missing_keep,
        "actions": [],
        "errors": [],
    }

    if missing_keep:
        report["errors"].append({"type": "missing_keep", "repos": missing_keep})

    for item in sorted(spaces, key=repo_id):
        rid = repo_id(item)
        if not rid:
            continue
        before_private = is_private(item)
        before_stage = stage(api, rid)
        row: dict[str, Any] = {
            "space": rid,
            "sdk": sdk_name(item),
            "desired": "KEEP_PUBLIC_RUNNING" if rid in keep else "FOLD_PRIVATE_PAUSED",
            "before": {"private": before_private, "stage": before_stage},
            "operations": [],
        }
        try:
            if rid in keep:
                if before_private:
                    row["operations"].append("set_public")
                    if not args.dry_run:
                        api.update_repo_settings(repo_id=rid, repo_type="space", private=False)
                if before_stage != "RUNNING":
                    row["operations"].append("restart")
                    if not args.dry_run:
                        api.restart_space(repo_id=rid)
                after_private = False if not args.dry_run else before_private
                after_stage = stage(api, rid) if not args.dry_run else before_stage
                row["after"] = {"private": after_private, "stage": after_stage}
                if not args.dry_run and (after_private or after_stage != "RUNNING"):
                    raise RuntimeError(f"keep target did not settle RUNNING/public: private={after_private} stage={after_stage}")
            else:
                if not before_private:
                    row["operations"].append("set_private")
                    if not args.dry_run:
                        api.update_repo_settings(repo_id=rid, repo_type="space", private=True)
                row["operations"].append("pause_if_supported")
                if not args.dry_run:
                    try:
                        api.pause_space(repo_id=rid)
                    except HfHubHTTPError as exc:
                        # Static Spaces cannot be paused; private visibility is the terminal fold state.
                        if "static" in str(exc).lower() or getattr(exc.response, "status_code", None) == 400:
                            row["operations"].append("pause_not_applicable_static")
                        else:
                            raise
                after_stage = stage(api, rid) if not args.dry_run else before_stage
                row["after"] = {"private": True if not args.dry_run else before_private, "stage": after_stage}
            row["ok"] = True
        except Exception as exc:
            row["ok"] = False
            row["error"] = f"{type(exc).__name__}: {exc}"[:1000]
            report["errors"].append({"space": rid, "error": row["error"]})
        report["actions"].append(row)

    report["completed_at"] = now()
    report["keep_count"] = sum(1 for row in report["actions"] if row["desired"] == "KEEP_PUBLIC_RUNNING")
    report["fold_count"] = sum(1 for row in report["actions"] if row["desired"] == "FOLD_PRIVATE_PAUSED")
    report["terminal_green"] = not report["errors"]
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("inventory_total", "keep_count", "fold_count", "terminal_green")}, sort_keys=True))
    return 0 if report["terminal_green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
