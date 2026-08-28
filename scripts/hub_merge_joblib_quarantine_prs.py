#!/usr/bin/env python3
"""Merge open Hub PRs that delete model.joblib.

Does not rewrite Hub main except via discussion merge of an already-opened
exact-parent PR. Missing token is UNAVAILABLE (exit 2), not success.
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
TITLE = "quarantine: remove model.joblib from approved path"


def main() -> int:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HF_ORG_TOKEN")
    if not token:
        print("UNAVAILABLE: HF_TOKEN/HF_ORG_TOKEN not present in this runner")
        return 2
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    merged = 0
    remaining = 0
    for repo_id in TARGETS:
        info = api.repo_info(repo_id=repo_id, repo_type="model")
        siblings = {s.rfilename for s in (info.siblings or [])}
        if "model.joblib" not in siblings:
            print(f"VERIFIED_CURRENT {repo_id}@{info.sha} no model.joblib")
            continue
        found = False
        for discussion in api.get_repo_discussions(repo_id=repo_id, repo_type="model"):
            if not discussion.is_pull_request:
                continue
            if discussion.status != "open":
                continue
            if TITLE not in (discussion.title or ""):
                continue
            found = True
            result = api.merge_pull_request(
                repo_id=repo_id,
                discussion_num=discussion.num,
                repo_type="model",
            )
            print(f"MERGED {repo_id} discussion={discussion.num} result={result}")
            merged += 1
            break
        if not found:
            print(f"OPEN_PR_MISSING {repo_id} still has model.joblib sha={info.sha}")
            remaining += 1
    print(f"merged={merged} remaining_joblib={remaining}")
    return 0 if remaining == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
