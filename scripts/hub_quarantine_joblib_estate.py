#!/usr/bin/env python3
"""Open Hub PRs deleting model.joblib at exact parent_commit for P0 kernel cards.

Requires HF_TOKEN or HF_ORG_TOKEN. Never prints the token.
Exit 2 if the token is missing (UNAVAILABLE). Partial Hub success is reported
per repo; any remaining joblib is not claimed remediated.
"""
from __future__ import annotations

import os
import sys

TARGETS = [
    "SZLHOLDINGS/szl-blocked",
    "SZLHOLDINGS/szl-formulas",
    "SZLHOLDINGS/szl-governed-norm",
    "SZLHOLDINGS/szl-govsign",
    "SZLHOLDINGS/szl-invariants",
    "SZLHOLDINGS/szl-nemo",
    "SZLHOLDINGS/szl-ouroboros",
    "SZLHOLDINGS/szl-provctl",
]


def main() -> int:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HF_ORG_TOKEN")
    if not token:
        print("UNAVAILABLE: HF_TOKEN/HF_ORG_TOKEN not present in this runner")
        return 2
    from huggingface_hub import CommitOperationDelete, HfApi

    api = HfApi(token=token)
    remaining = 0
    for repo_id in TARGETS:
        info = api.repo_info(repo_id=repo_id, repo_type="model")
        parent = info.sha
        siblings = {s.rfilename for s in (info.siblings or [])}
        if "model.joblib" not in siblings:
            print(f"VERIFIED_CURRENT {repo_id}@{parent} no model.joblib")
            continue
        commit = api.create_commit(
            repo_id=repo_id,
            repo_type="model",
            operations=[CommitOperationDelete(path_in_repo="model.joblib")],
            commit_message="quarantine: remove model.joblib from approved path",
            create_pr=True,
            parent_commit=parent,
        )
        print(f"Hub PR {repo_id} parent={parent} result={commit}")
        remaining += 1
    print(f"opened_or_needed={remaining}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
