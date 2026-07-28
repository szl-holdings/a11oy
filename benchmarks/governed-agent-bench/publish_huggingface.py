#!/usr/bin/env python3
"""Publish and independently read back governed-agent-bench Hub payloads."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MANAGED_BY = "szl-holdings/a11oy:benchmarks/governed-agent-bench"


class PublicationError(RuntimeError):
    """The protected Hub publication failed closed."""


def _files(folder: Path) -> dict[str, bytes]:
    files = {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }
    if not files:
        raise PublicationError(f"empty publication folder: {folder}")
    return files


def _manifest_is_managed(files: dict[str, bytes]) -> None:
    try:
        manifest = json.loads(files["publication-manifest.json"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise PublicationError("payload lacks a valid publication manifest") from exc
    if manifest.get("managed_by") != MANAGED_BY:
        raise PublicationError("publication manifest ownership mismatch")


def _publish_and_readback(api, repo_id: str, repo_type: str, folder: Path, token: str):
    from huggingface_hub import CommitOperationAdd, hf_hub_download

    expected = _files(folder)
    _manifest_is_managed(expected)
    api.create_repo(repo_id=repo_id, repo_type=repo_type, private=False, exist_ok=True)
    commit = api.create_commit(
        repo_id=repo_id,
        repo_type=repo_type,
        operations=[
            CommitOperationAdd(path_in_repo=name, path_or_fileobj=io.BytesIO(body))
            for name, body in expected.items()
        ],
        commit_message="publish governed-agent-bench from protected GitHub source",
    )
    revision = commit.oid
    observed = {}
    for name, body in expected.items():
        path = hf_hub_download(
            repo_id=repo_id,
            repo_type=repo_type,
            filename=name,
            revision=revision,
            token=token,
            force_download=True,
        )
        readback = Path(path).read_bytes()
        if readback != body:
            raise PublicationError(f"immutable readback mismatch: {repo_type}:{repo_id}/{name}")
        observed[name] = {
            "bytes": len(readback),
            "sha256": hashlib.sha256(readback).hexdigest(),
        }
    return revision, observed


def publish(
    bundle: Path,
    source_revision: str,
    dataset_repo: str,
    space_repo: str,
    receipt_path: Path,
) -> dict[str, object]:
    if not SHA_RE.fullmatch(source_revision):
        raise PublicationError("source revision must be 40 lowercase hexadecimal characters")
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if not token:
        raise PublicationError("HF_TOKEN is not configured")
    dataset = bundle / "dataset"
    space = bundle / "space"
    if not dataset.is_dir() or not space.is_dir():
        raise PublicationError("bundle must contain dataset and space folders")

    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise PublicationError("huggingface_hub is not installed") from exc

    api = HfApi(token=token)
    dataset_revision, dataset_files = _publish_and_readback(
        api, dataset_repo, "dataset", dataset, token
    )

    with tempfile.TemporaryDirectory(prefix="governed-agent-bench-space-") as tmp:
        resolved_space = Path(tmp) / "space"
        shutil.copytree(space, resolved_space)
        publication_path = resolved_space / "publication.json"
        publication = json.loads(publication_path.read_text(encoding="utf-8"))
        publication["dataset_revision"] = dataset_revision
        publication_path.write_text(
            json.dumps(publication, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        manifest_path = resolved_space / "publication-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"] = [
            {
                "path": path.relative_to(resolved_space).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in sorted(resolved_space.rglob("*"))
            if path.is_file() and path.name != "publication-manifest.json"
        ]
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        space_revision, space_files = _publish_and_readback(
            api, space_repo, "space", resolved_space, token
        )

    receipt = {
        "schema_version": "szl.governed-agent-bench-publication-receipt.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_repository": "szl-holdings/a11oy",
        "source_revision": source_revision,
        "dataset": {
            "repo_id": dataset_repo,
            "revision": dataset_revision,
            "files": dataset_files,
        },
        "space": {
            "repo_id": space_repo,
            "revision": space_revision,
            "files": space_files,
        },
        "status": "VERIFIED_IMMUTABLE_READBACK",
        "credential_value_recorded": False,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--dataset-repo", default="SZLHOLDINGS/governed-agent-bench")
    parser.add_argument("--space-repo", default="SZLHOLDINGS/governed-agent-bench")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = publish(
            args.bundle,
            args.source_revision,
            args.dataset_repo,
            args.space_repo,
            args.receipt,
        )
    except PublicationError as exc:
        print(f"publication failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
