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
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MANAGED_BY = "szl-holdings/a11oy:benchmarks/governed-agent-bench"
HF_API_ROOT = "https://huggingface.co/api"
HF_WEB_ROOT = "https://huggingface.co"
SPACE_RUNTIME_FAILURE_STAGES = {
    "BUILD_ERROR",
    "CONFIG_ERROR",
    "DELETED",
    "NO_APP_FILE",
    "RUNTIME_ERROR",
}


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


def _require_declared_source(path: Path, source_revision: str) -> None:
    try:
        document = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationError(f"source identity document is invalid: {path}") from exc
    observed = document.get("source_revision")
    if observed != source_revision:
        raise PublicationError(
            "publication source revision mismatch: "
            f"{path} expected={source_revision!r} observed={observed!r}"
        )


def _require_bundle_source(
    dataset: Path,
    space: Path,
    source_revision: str,
) -> None:
    for path in (
        dataset / "publication-manifest.json",
        space / "publication-manifest.json",
        space / "publication.json",
    ):
        _require_declared_source(path, source_revision)


def _public_bytes(url: str, timeout_seconds: float = 30.0) -> tuple[int, bytes]:
    request = Request(url, headers={"User-Agent": "szl-governed-agent-bench/1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status), response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise PublicationError(f"anonymous HTTP read failed: {url}: {exc}") from exc


def _public_json(url: str) -> dict[str, object]:
    status, body = _public_bytes(url)
    if status != 200:
        raise PublicationError(f"anonymous API read returned HTTP {status}: {url}")
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PublicationError(f"anonymous API read returned invalid JSON: {url}") from exc
    if not isinstance(value, dict):
        raise PublicationError(f"anonymous API read returned a non-object: {url}")
    return value


def _repo_api_url(repo_id: str, repo_type: str) -> str:
    collection = "datasets" if repo_type == "dataset" else "spaces"
    return f"{HF_API_ROOT}/{collection}/{quote(repo_id, safe='/')}"


def _resolve_url(repo_id: str, repo_type: str, revision: str, name: str) -> str:
    collection = "datasets" if repo_type == "dataset" else "spaces"
    return (
        f"{HF_WEB_ROOT}/{collection}/{quote(repo_id, safe='/')}/resolve/"
        f"{quote(revision, safe='')}/{quote(name, safe='/')}"
    )


def _validate_public_info(
    info: dict[str, object],
    repo_id: str,
    repo_type: str,
    revision: str,
    expected_names: set[str],
) -> None:
    if info.get("private") is not False:
        raise PublicationError(
            f"anonymous API does not prove public visibility: {repo_type}:{repo_id}"
        )
    if info.get("sha") != revision:
        raise PublicationError(
            f"public repository revision mismatch: {repo_type}:{repo_id} "
            f"expected={revision!r} observed={info.get('sha')!r}"
        )
    siblings = info.get("siblings")
    if not isinstance(siblings, list):
        raise PublicationError(f"public repository inventory missing: {repo_type}:{repo_id}")
    observed_names = {
        entry.get("rfilename")
        for entry in siblings
        if isinstance(entry, dict) and isinstance(entry.get("rfilename"), str)
    }
    if observed_names != expected_names:
        missing = sorted(expected_names - observed_names)
        unexpected = sorted(observed_names - expected_names)
        raise PublicationError(
            "anonymous inventory mismatch: "
            f"{repo_type}:{repo_id} missing={missing!r} unexpected={unexpected!r}"
        )


def _verify_public_repository(
    repo_id: str,
    repo_type: str,
    revision: str,
    expected: dict[str, bytes],
    *,
    fetch_json=_public_json,
    fetch_bytes=_public_bytes,
) -> dict[str, object]:
    info = fetch_json(_repo_api_url(repo_id, repo_type))
    _validate_public_info(info, repo_id, repo_type, revision, set(expected))
    observed = {}
    for name, body in expected.items():
        status, readback = fetch_bytes(_resolve_url(repo_id, repo_type, revision, name))
        if status != 200:
            raise PublicationError(
                f"anonymous immutable readback returned HTTP {status}: "
                f"{repo_type}:{repo_id}/{name}"
            )
        if readback != body:
            raise PublicationError(
                f"anonymous immutable readback mismatch: {repo_type}:{repo_id}/{name}"
            )
        observed[name] = {
            "bytes": len(readback),
            "sha256": hashlib.sha256(readback).hexdigest(),
        }
    return {"info": info, "files": observed}


def _wait_for_public_repository(
    repo_id: str,
    repo_type: str,
    revision: str,
    expected: dict[str, bytes],
    timeout_seconds: float,
    poll_interval_seconds: float,
    *,
    fetch_json=_public_json,
    fetch_bytes=_public_bytes,
    sleep=time.sleep,
    monotonic=time.monotonic,
) -> dict[str, object]:
    deadline = monotonic() + timeout_seconds
    latest_error: PublicationError | None = None
    while monotonic() <= deadline:
        try:
            return _verify_public_repository(
                repo_id,
                repo_type,
                revision,
                expected,
                fetch_json=fetch_json,
                fetch_bytes=fetch_bytes,
            )
        except PublicationError as exc:
            latest_error = exc
        sleep(poll_interval_seconds)
    raise PublicationError(
        "public immutable readback did not converge before timeout: "
        f"{repo_type}:{repo_id} expected={revision!r} last_error={latest_error}"
    )


def _space_runtime_ready(info: dict[str, object], revision: str) -> bool:
    runtime = info.get("runtime")
    if not isinstance(runtime, dict):
        return False
    return runtime.get("stage") == "RUNNING" and runtime.get("sha") == revision


def _space_identity_source(expected: dict[str, bytes]) -> str:
    try:
        publication = json.loads(expected["publication.json"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise PublicationError("Space payload lacks a valid publication identity") from exc
    source_revision = publication.get("source_revision")
    if not isinstance(source_revision, str) or not SHA_RE.fullmatch(source_revision):
        raise PublicationError("Space publication identity lacks an exact source revision")
    return source_revision


def _validate_space_identity(body: bytes, source_revision: str) -> dict[str, object]:
    try:
        config = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PublicationError("Space /config returned invalid JSON") from exc
    if not isinstance(config, dict) or config.get("mode") != "blocks":
        raise PublicationError("Space /config is not a Gradio blocks application")
    components = config.get("components")
    if not isinstance(components, list):
        raise PublicationError("Space /config does not expose components")
    encoded = json.dumps(config, sort_keys=True)
    if "Governed Agent Bench" not in encoded:
        raise PublicationError("Space /config lacks the expected application identity")
    if source_revision not in encoded:
        raise PublicationError("Space /config lacks the exact protected source revision")
    return {
        "application": "Governed Agent Bench",
        "source_revision": source_revision,
    }


def _wait_for_public_space(
    repo_id: str,
    revision: str,
    expected: dict[str, bytes],
    timeout_seconds: float,
    poll_interval_seconds: float,
    *,
    fetch_json=_public_json,
    fetch_bytes=_public_bytes,
    sleep=time.sleep,
    monotonic=time.monotonic,
) -> dict[str, object]:
    deadline = monotonic() + timeout_seconds
    latest: dict[str, object] = {}
    latest_error: PublicationError | None = None
    source_revision = _space_identity_source(expected)
    while monotonic() <= deadline:
        try:
            latest = fetch_json(_repo_api_url(repo_id, "space"))
        except PublicationError as exc:
            latest = {}
            latest_error = exc
        runtime = latest.get("runtime")
        stage = runtime.get("stage") if isinstance(runtime, dict) else None
        runtime_sha = runtime.get("sha") if isinstance(runtime, dict) else None
        if stage in SPACE_RUNTIME_FAILURE_STAGES and runtime_sha == revision:
            raise PublicationError(f"Space entered terminal failure stage: {stage}")
        if _space_runtime_ready(latest, revision):
            try:
                public = _verify_public_repository(
                    repo_id,
                    "space",
                    revision,
                    expected,
                    fetch_json=lambda _url: latest,
                    fetch_bytes=fetch_bytes,
                )
                subdomain = latest.get("subdomain")
                if not isinstance(subdomain, str) or not re.fullmatch(
                    r"[a-z0-9-]+", subdomain
                ):
                    raise PublicationError("Space public subdomain is missing or invalid")
                public_url = f"https://{subdomain}.hf.space/"
                status, body = fetch_bytes(public_url)
                if status != 200 or not body:
                    raise PublicationError(
                        f"Space public root is not serving: "
                        f"status={status} bytes={len(body)}"
                    )
                identity_url = f"{public_url}config"
                identity_status, identity_body = fetch_bytes(identity_url)
                if identity_status != 200 or not identity_body:
                    raise PublicationError(
                        "Space identity endpoint is not serving: "
                        f"status={identity_status} bytes={len(identity_body)}"
                    )
                identity = _validate_space_identity(identity_body, source_revision)
            except PublicationError as exc:
                latest_error = exc
            else:
                runtime = latest["runtime"]
                public["runtime"] = {
                    "stage": runtime["stage"],
                    "sha": runtime["sha"],
                    "public_url": public_url,
                    "http_status": status,
                    "response_bytes": len(body),
                    "identity_url": identity_url,
                    "identity_http_status": identity_status,
                    "identity": identity,
                }
                return public
        sleep(poll_interval_seconds)
    runtime = latest.get("runtime")
    stage = runtime.get("stage") if isinstance(runtime, dict) else None
    runtime_sha = runtime.get("sha") if isinstance(runtime, dict) else None
    raise PublicationError(
        "Space did not converge to exact public runtime before timeout: "
        f"stage={stage!r} runtime_sha={runtime_sha!r} expected={revision!r} "
        f"last_error={latest_error}"
    )


def _publish_and_readback(api, repo_id: str, repo_type: str, folder: Path, token: str):
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, hf_hub_download

    expected = _files(folder)
    _manifest_is_managed(expected)

    existed = api.repo_exists(repo_id=repo_id, repo_type=repo_type, token=token)
    if existed:
        remote_files = set(
            api.list_repo_files(repo_id=repo_id, repo_type=repo_type, revision="main")
        )
        if remote_files:
            if "publication-manifest.json" not in remote_files:
                raise PublicationError(
                    f"refusing to replace unmanaged {repo_type} repository: {repo_id}"
                )
            owner_path = hf_hub_download(
                repo_id=repo_id,
                repo_type=repo_type,
                filename="publication-manifest.json",
                revision="main",
                token=token,
                force_download=True,
            )
            try:
                owner = json.loads(Path(owner_path).read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise PublicationError(
                    f"remote ownership manifest is invalid: {repo_type}:{repo_id}"
                ) from exc
            if owner.get("managed_by") != MANAGED_BY:
                raise PublicationError(
                    f"refusing to replace foreign {repo_type} repository: {repo_id}"
                )
    else:
        create_kwargs = {
            "repo_id": repo_id,
            "repo_type": repo_type,
            "private": False,
            "exist_ok": False,
        }
        if repo_type == "space":
            create_kwargs["space_sdk"] = "gradio"
        api.create_repo(
            **create_kwargs,
        )
        remote_files = set(
            api.list_repo_files(repo_id=repo_id, repo_type=repo_type, revision="main")
        )

    expected_names = set(expected)
    current_is_exact = remote_files == expected_names
    if current_is_exact:
        for name, body in expected.items():
            path = hf_hub_download(
                repo_id=repo_id,
                repo_type=repo_type,
                filename=name,
                revision="main",
                token=token,
                force_download=True,
            )
            if Path(path).read_bytes() != body:
                current_is_exact = False
                break

    if current_is_exact:
        revision = api.repo_info(repo_id=repo_id, repo_type=repo_type).sha
        action = "already_exact"
    else:
        stale = sorted(remote_files - expected_names)
        operations = [
            CommitOperationAdd(path_in_repo=name, path_or_fileobj=io.BytesIO(body))
            for name, body in expected.items()
        ]
        operations.extend(CommitOperationDelete(path_in_repo=name) for name in stale)
        commit = api.create_commit(
            repo_id=repo_id,
            repo_type=repo_type,
            operations=operations,
            commit_message="publish governed-agent-bench from protected GitHub source",
        )
        revision = commit.oid
        action = "published"

    observed_inventory = set(
        api.list_repo_files(
            repo_id=repo_id,
            repo_type=repo_type,
            revision=revision,
        )
    )
    if observed_inventory != expected_names:
        missing = sorted(expected_names - observed_inventory)
        unexpected = sorted(observed_inventory - expected_names)
        raise PublicationError(
            f"immutable inventory mismatch for {repo_type}:{repo_id}; "
            f"missing={missing!r}; unexpected={unexpected!r}"
        )

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
    return revision, observed, action, sorted(observed_inventory)


def publish(
    bundle: Path,
    source_revision: str,
    dataset_repo: str,
    space_repo: str,
    receipt_path: Path,
    space_timeout_seconds: float = 900.0,
    poll_interval_seconds: float = 10.0,
    dataset_timeout_seconds: float = 180.0,
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
    _require_bundle_source(dataset, space, source_revision)

    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise PublicationError("huggingface_hub is not installed") from exc

    api = HfApi(token=token)
    (
        dataset_revision,
        dataset_files,
        dataset_action,
        dataset_inventory,
    ) = _publish_and_readback(
        api, dataset_repo, "dataset", dataset, token
    )
    dataset_public = _wait_for_public_repository(
        dataset_repo,
        "dataset",
        dataset_revision,
        _files(dataset),
        dataset_timeout_seconds,
        poll_interval_seconds,
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
        (
            space_revision,
            space_files,
            space_action,
            space_inventory,
        ) = _publish_and_readback(
            api, space_repo, "space", resolved_space, token
        )
        space_public = _wait_for_public_space(
            space_repo,
            space_revision,
            _files(resolved_space),
            space_timeout_seconds,
            poll_interval_seconds,
        )

    receipt = {
        "schema_version": "szl.governed-agent-bench-publication-receipt.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_repository": "szl-holdings/a11oy",
        "source_revision": source_revision,
        "dataset": {
            "repo_id": dataset_repo,
            "revision": dataset_revision,
            "action": dataset_action,
            "inventory": dataset_inventory,
            "files": dataset_files,
            "public_readback": dataset_public["files"],
        },
        "space": {
            "repo_id": space_repo,
            "revision": space_revision,
            "action": space_action,
            "inventory": space_inventory,
            "files": space_files,
            "public_readback": space_public["files"],
            "runtime": space_public["runtime"],
        },
        "status": "VERIFIED_PUBLIC_IMMUTABLE_READBACK_AND_RUNNING_SPACE",
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
    parser.add_argument("--space-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--dataset-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=10.0)
    args = parser.parse_args()
    try:
        receipt = publish(
            args.bundle,
            args.source_revision,
            args.dataset_repo,
            args.space_repo,
            args.receipt,
            args.space_timeout_seconds,
            args.poll_interval_seconds,
            args.dataset_timeout_seconds,
        )
    except PublicationError as exc:
        print(f"publication failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
