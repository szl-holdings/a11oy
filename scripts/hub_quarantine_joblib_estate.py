#!/usr/bin/env python3
"""Open exact-parent Hub PRs deleting model.joblib from the governed estate.

Requires HF_TOKEN or HF_ORG_TOKEN. The token is never printed. Existing
matching PRs are reused, current-safe repositories are verified, and every
per-repository failure is reported without falsely upgrading the aggregate.
"""
from __future__ import annotations

import os
import sys
from typing import Any

TARGETS = (
    "SZLHOLDINGS/szl-blocked",
    "SZLHOLDINGS/szl-formulas",
    "SZLHOLDINGS/szl-governed-norm",
    "SZLHOLDINGS/szl-govsign",
    "SZLHOLDINGS/szl-invariants",
    "SZLHOLDINGS/szl-nemo",
    "SZLHOLDINGS/szl-ouroboros",
    "SZLHOLDINGS/szl-provctl",
)
TITLE = "quarantine: remove model.joblib from approved path"
JOBLIB_PATH = "model.joblib"


def _safe_error(error: BaseException, token: str) -> str:
    """Return a bounded single-line error without credential disclosure."""
    try:
        text = str(error)
    except Exception:
        text = "<unprintable>"
    if token:
        text = text.replace(token, "<redacted>")
    return " ".join(text.split())[:1000] or "<empty>"


def _files(info: Any) -> set[str]:
    return {s.rfilename for s in (getattr(info, "siblings", None) or [])}


def _matching_open_prs(api: Any, repo_id: str) -> list[Any]:
    return [
        discussion
        for discussion in api.get_repo_discussions(repo_id=repo_id, repo_type="model")
        if discussion.is_pull_request
        and discussion.status == "open"
        and discussion.title == TITLE
    ]


def main() -> int:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HF_ORG_TOKEN")
    if not token:
        print("UNAVAILABLE: HF_TOKEN/HF_ORG_TOKEN not present in this runner")
        return 2

    from huggingface_hub import CommitOperationDelete, HfApi

    api = HfApi(token=token)
    opened = 0
    reused = 0
    already_safe = 0
    failures: list[str] = []

    for repo_id in TARGETS:
        try:
            info = api.repo_info(repo_id=repo_id, repo_type="model")
            parent = info.sha
            if JOBLIB_PATH not in _files(info):
                print(f"VERIFIED_CURRENT {repo_id}@{parent} no {JOBLIB_PATH}")
                already_safe += 1
                continue

            matches = _matching_open_prs(api, repo_id)
            if len(matches) > 1:
                raise RuntimeError(
                    f"ambiguous quarantine PRs: {[discussion.num for discussion in matches]}"
                )
            if matches:
                print(
                    f"REUSE_OPEN_PR {repo_id} discussion={matches[0].num} "
                    f"parent_observed={parent}"
                )
                reused += 1
                continue

            commit = api.create_commit(
                repo_id=repo_id,
                repo_type="model",
                operations=[CommitOperationDelete(path_in_repo=JOBLIB_PATH)],
                commit_message=TITLE,
                create_pr=True,
                parent_commit=parent,
            )
            oid = getattr(commit, "oid", None) or getattr(commit, "commit_oid", None)
            pr_url = getattr(commit, "pr_url", None)
            print(
                f"CREATED_QUARANTINE_PR {repo_id} parent={parent} "
                f"commit={oid or 'UNKNOWN'} pr={pr_url or 'UNKNOWN'}"
            )
            opened += 1
        except Exception as error:
            failures.append(repo_id)
            print(
                f"ERROR {repo_id} {type(error).__name__}: {_safe_error(error, token)}",
                file=sys.stderr,
            )

    print(
        "SUMMARY "
        f"opened={opened} reused={reused} already_safe={already_safe} "
        f"failed={len(failures)} total={len(TARGETS)}"
    )
    if failures:
        print(f"FAILED_REPOS={','.join(failures)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
