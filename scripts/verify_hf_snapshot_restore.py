#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Create exact Hugging Face Space snapshots and prove offline restoration.

The token is read only from ``HF_TOKEN`` and is never included in output. Each
Space is downloaded at an immutable Hub revision, archived, restored into a
fresh directory, and compared using a path/size/SHA-256 manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

DEFAULT_REPOSITORIES = ("SZLHOLDINGS/a11oy", "SZLHOLDINGS/killinchu")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == ".cache" or relative.startswith(".cache/"):
            continue
        files.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {
        "files": files,
        "file_count": len(files),
        "total_bytes": sum(item["size"] for item in files),
        "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def write_archive(source: Path, archive: Path, manifest: dict[str, Any]) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as bundle:
        for item in manifest["files"]:
            path = source / item["path"]
            bundle.add(path, arcname=item["path"], recursive=False)


def restore_archive(archive: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as bundle:
        bundle.extractall(destination, filter="data")


def verify_local_snapshot(source: Path, workspace: Path, name: str) -> dict[str, Any]:
    original = build_manifest(source)
    archive = workspace / "archives" / f"{name}.tar.gz"
    restored = workspace / "restored" / name
    write_archive(source, archive, original)
    restore_archive(archive, restored)
    restored_manifest = build_manifest(restored)
    if original != restored_manifest:
        raise RuntimeError(f"restored manifest differs for {name}")
    return {
        "archive": archive.as_posix(),
        "archive_sha256": sha256_file(archive),
        "file_count": original["file_count"],
        "total_bytes": original["total_bytes"],
        "manifest_sha256": original["manifest_sha256"],
        "restore_match": True,
    }


def download_snapshot_files(
    api: Any,
    repo_id: str,
    revision: str,
    source: Path,
    token: str,
    download_file: Callable[..., str],
) -> list[str]:
    """Download every file from one immutable Hub revision without concurrency.

    ``snapshot_download`` delegates an empty file list to ``tqdm.thread_map`` in
    some client versions, which raises an opaque ``min()`` error before evidence
    can be written. Listing first also makes the completeness boundary explicit:
    an empty repository is a hard failure, and every returned path must be safe.
    """
    files = sorted(
        str(path)
        for path in api.list_repo_files(
            repo_id=repo_id,
            repo_type="space",
            revision=revision,
        )
    )
    if not files:
        raise RuntimeError(
            f"Hugging Face returned no files for {repo_id}@{revision}"
        )

    if source.exists():
        shutil.rmtree(source)
    source.mkdir(parents=True)

    for filename in files:
        relative = PurePosixPath(filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"unsafe Hub path for {repo_id}: {filename}")
        cached = Path(
            download_file(
                repo_id=repo_id,
                filename=filename,
                repo_type="space",
                revision=revision,
                token=token,
            )
        )
        destination = source.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached, destination)

    return files


def verify_spaces(
    repositories: Iterable[str], workspace: Path, token: str
) -> dict[str, Any]:
    from huggingface_hub import HfApi, hf_hub_download

    api = HfApi(token=token)
    results = []
    for repo_id in repositories:
        info = api.space_info(repo_id=repo_id)
        revision = info.sha
        if not revision:
            raise RuntimeError(f"Hugging Face did not return a revision for {repo_id}")
        name = repo_id.replace("/", "--")
        source = workspace / "snapshots" / name
        remote_files = download_snapshot_files(
            api,
            repo_id,
            revision,
            source,
            token,
            hf_hub_download,
        )
        result = verify_local_snapshot(source, workspace, name)
        if result["file_count"] != len(remote_files):
            raise RuntimeError(
                f"downloaded file count differs for {repo_id}: "
                f"{result['file_count']} != {len(remote_files)}"
            )
        result.update(
            {
                "repository": repo_id,
                "revision": revision,
                "remote_file_count": len(remote_files),
            }
        )
        results.append(result)

    return {
        "schema": "szl.hf-backup-restoration/v1",
        "generated_at": utc_now(),
        "workflow_run_url": (
            f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
            f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
            if all(
                os.environ.get(key)
                for key in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID")
            )
            else None
        ),
        "repositories": results,
        "all_restores_match": all(item["restore_match"] for item in results),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path(".hf-backup"))
    parser.add_argument(
        "--repo",
        action="append",
        dest="repositories",
        help="Space repository to back up; repeat for multiple repositories",
    )
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN is required; use the repository Actions secret")

    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    evidence = args.evidence or workspace / "evidence" / "hf-backup-restoration.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    result = verify_spaces(args.repositories or DEFAULT_REPOSITORIES, workspace, token)
    evidence.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "schema": result["schema"],
                "repositories": len(result["repositories"]),
                "all_restores_match": result["all_restores_match"],
                "evidence": evidence.as_posix(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
