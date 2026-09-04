#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One-shot source patch for existing Hugging Face Space publishers."""
from __future__ import annotations

from pathlib import Path


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement target, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    replace_exact(
        Path("scripts/hf_publish_vertical_flagships_v4_impl.py"),
        '''            api.create_repo(repo_id=rid, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
            row["actions"].append("ensure_space")
''',
        '''            api.auth_check(repo_id=rid, repo_type="space", write=True)
            row["actions"].append("verify_existing_space_write")
''',
    )
    replace_exact(
        Path("scripts/hf_publish_vertical_services.py"),
        '''    api.create_repo(
        repo_id=HF_REPOSITORY,
        repo_type="space",
        space_sdk="docker",
        exist_ok=True,
        private=False,
    )
    api.auth_check(repo_id=HF_REPOSITORY, repo_type="space", write=True)
''',
        '''    # The canonical Space is a governed, pre-existing estate asset. Do not call
    # create_repo(exist_ok=True): Hugging Face still counts that POST against the
    # daily Space-creation quota. Missing or unauthorized assets fail closed.
    api.auth_check(repo_id=HF_REPOSITORY, repo_type="space", write=True)
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
