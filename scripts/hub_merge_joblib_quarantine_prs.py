#!/usr/bin/env python3
"""Verify and merge only exact Hub PRs that delete model.joblib.

The merge path fails closed unless each candidate is an open pull request owned
by the authenticated actor, targets the Hub's canonical main ref, has no
conflicts, and contains one and only one git diff: deletion of model.joblib.
Each merge is followed by a fresh Hub readback proving that model.joblib is
absent.
"""
from __future__ import annotations

import os
import re
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
MAIN_TARGETS = frozenset(("main", "refs/heads/main"))
_DIFF_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$", re.MULTILINE)


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


def _actor_name(api: Any) -> str:
    identity = api.whoami()
    actor = identity.get("name") if isinstance(identity, dict) else None
    if not isinstance(actor, str) or not actor.strip():
        raise RuntimeError("authenticated Hub actor identity is unavailable")
    return actor.strip()


def _matching_open_prs(api: Any, repo_id: str) -> list[Any]:
    return [
        discussion
        for discussion in api.get_repo_discussions(repo_id=repo_id, repo_type="model")
        if discussion.is_pull_request
        and discussion.status == "open"
        and discussion.title == TITLE
    ]


def _validate_candidate(api: Any, repo_id: str, discussion: Any, actor: str) -> Any:
    details = api.get_discussion_details(
        repo_id=repo_id,
        discussion_num=discussion.num,
        repo_type="model",
    )
    if not details.is_pull_request or details.status != "open":
        raise RuntimeError("candidate is not an open pull request")
    if details.title != TITLE:
        raise RuntimeError("candidate title does not exactly match quarantine contract")
    if details.author != actor:
        raise RuntimeError(
            f"candidate author {details.author!r} does not match authenticated actor {actor!r}"
        )
    if details.target_branch not in MAIN_TARGETS:
        raise RuntimeError(
            f"candidate target branch is {details.target_branch!r}, not a canonical main ref"
        )
    if details.conflicting_files not in (None, False, [], ()):
        raise RuntimeError(f"candidate has conflicts: {details.conflicting_files!r}")

    diff = details.diff
    if not isinstance(diff, str) or not diff.strip():
        raise RuntimeError("candidate diff is unavailable")
    headers = _DIFF_HEADER.findall(diff)
    if headers != [(JOBLIB_PATH, JOBLIB_PATH)]:
        raise RuntimeError(f"candidate changes unexpected paths: {headers!r}")
    if "deleted file mode" not in diff and "/dev/null" not in diff:
        raise RuntimeError("candidate does not prove deletion of model.joblib")
    for forbidden in ("new file mode", "rename from ", "rename to ", "copy from ", "copy to "):
        if forbidden in diff:
            raise RuntimeError(f"candidate contains forbidden diff operation: {forbidden.strip()}")
    return details


def main() -> int:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HF_ORG_TOKEN")
    if not token:
        print("UNAVAILABLE: HF_TOKEN/HF_ORG_TOKEN not present in this runner")
        return 2

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    try:
        actor = _actor_name(api)
    except Exception as error:
        print(
            f"ERROR identity {type(error).__name__}: {_safe_error(error, token)}",
            file=sys.stderr,
        )
        return 2

    merged = 0
    already_safe = 0
    failures: list[str] = []

    for repo_id in TARGETS:
        try:
            before = api.repo_info(repo_id=repo_id, repo_type="model")
            if JOBLIB_PATH not in _files(before):
                print(f"VERIFIED_CURRENT {repo_id}@{before.sha} no {JOBLIB_PATH}")
                already_safe += 1
                continue

            matches = _matching_open_prs(api, repo_id)
            if len(matches) != 1:
                raise RuntimeError(
                    "expected exactly one open quarantine PR, found "
                    f"{[discussion.num for discussion in matches]}"
                )
            details = _validate_candidate(api, repo_id, matches[0], actor)
            result = api.merge_pull_request(
                repo_id=repo_id,
                discussion_num=details.num,
                repo_type="model",
                comment=(
                    "Merged by the fail-closed executable-artifact quarantine controller "
                    "after exact diff, author, target, and conflict validation."
                ),
            )
            after = api.repo_info(repo_id=repo_id, repo_type="model")
            if JOBLIB_PATH in _files(after):
                raise RuntimeError(
                    f"post-merge readback still contains {JOBLIB_PATH} at {after.sha}"
                )
            print(
                f"MERGED_AND_VERIFIED {repo_id} discussion={details.num} "
                f"before={before.sha} after={after.sha} result={result}"
            )
            merged += 1
        except Exception as error:
            failures.append(repo_id)
            print(
                f"ERROR {repo_id} {type(error).__name__}: {_safe_error(error, token)}",
                file=sys.stderr,
            )

    print(
        "SUMMARY "
        f"merged={merged} already_safe={already_safe} failed={len(failures)} "
        f"total={len(TARGETS)}"
    )
    if failures:
        print(f"FAILED_REPOS={','.join(failures)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
