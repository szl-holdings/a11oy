#!/usr/bin/env python3
"""Publish the prepared A11oy Hugging Face payload.

Requires HF_TOKEN in the environment. The token is never printed.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default="SZLHOLDINGS/a11oy-v19-substrate")
    parser.add_argument("--repo-type", default="model")
    parser.add_argument("--folder", default="dist/huggingface/a11oy")
    parser.add_argument(
        "--no-delete-stale",
        action="store_true",
        help="upload without pruning remote files absent from the generated payload",
    )
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if not token:
        print("Missing HF_TOKEN. Add it as a GitHub Actions secret or export it locally.")
        return 2

    folder = Path(args.folder)
    if not folder.exists():
        print(f"Missing payload folder: {folder}. Run `pnpm payload:huggingface` first.")
        return 1

    try:
        from huggingface_hub import CommitOperationDelete, HfApi
    except ImportError:
        print("Missing huggingface_hub. Install with: python -m pip install --upgrade huggingface_hub")
        return 2

    api = HfApi(token=token)
    api.create_repo(repo_id=args.repo_id, repo_type=args.repo_type, exist_ok=True)

    if not args.no_delete_stale:
        local_files = {
            path.relative_to(folder).as_posix()
            for path in folder.rglob("*")
            if path.is_file()
        }
        remote_files = set(api.list_repo_files(repo_id=args.repo_id, repo_type=args.repo_type))
        stale_files = sorted(remote_files - local_files)
        if stale_files:
            operations = [CommitOperationDelete(path_in_repo=path) for path in stale_files]
            api.create_commit(
                repo_id=args.repo_id,
                repo_type=args.repo_type,
                operations=operations,
                commit_message="prune stale a11oy payload files",
            )
            print(f"Pruned {len(stale_files)} stale Hugging Face files")

    api.upload_folder(
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        folder_path=str(folder),
        commit_message="publish a11oy operational payload",
    )
    print(f"Published Hugging Face payload to {args.repo_type}:{args.repo_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
