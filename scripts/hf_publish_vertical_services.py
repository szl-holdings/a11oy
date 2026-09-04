#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deploy the exact SZL combined vertical runtime through the canonical HF writer.

The deployment reuses SZL's pinned Dockerfile-derived controller. It never
deletes a Space, never rotates an existing signing key, and never prints secret
values.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

SOURCE_REPOSITORY = "szl-holdings/vertical-services"
SOURCE_REVISION = "1c6d941da172e2132d3c7818911bd8669ca28f00"
HF_REPOSITORY = "SZLHOLDINGS/vertical-services"
ORIGIN = "https://szlholdings-vertical-services.hf.space"
SOURCE_VARIABLE = "SZL_SOURCE_REVISION"
SIGNING_SECRET = "SENTRA_SIGNING_KEY"
RECEIPT_PATH = Path("hf-vertical-services-receipt.json")

CONTROLLER_REPOSITORY = "szl-holdings/.github"
CONTROLLER_REVISION = "c889276e51e7d954c4bba8b216f86fc7577721fa"
CONTROLLER_PATH = ".github/scripts/hf_deploy_from_dockerfile.py"
CONTROLLER_BLOB_SHA1 = "9d5b90b8bbf04e6d46ef0f971fc65604e1323b1b"
USER_AGENT = "SZLHOLDINGS-Canonical-Vertical-Services-Publisher/1.0"

SMOKE_PATHS = (
    "/",
    "/healthz",
    "/readyz",
    "/api/build-info",
    "/sentra/healthz",
    "/lyte/healthz",
    "/vessels/healthz",
    "/finance/healthz",
    "/terra/healthz",
    "/counsel/healthz",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def token_from_env() -> tuple[str, str]:
    for name in (
        "HF_ORG_TOKEN",
        "HF_WRITE_TOKEN",
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
        "HUGGING_FACE_HUB_TOKEN",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    raise RuntimeError("no Hugging Face write token available to canonical writer")


def run_checked(command: list[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode:
        raise RuntimeError(
            f"command failed with exit {result.returncode}: "
            + " ".join(command[:4])
        )


def checkout_exact_source(destination: Path) -> None:
    run_checked(["git", "init", "--quiet", str(destination)])
    run_checked(
        [
            "git",
            "-C",
            str(destination),
            "remote",
            "add",
            "origin",
            f"https://github.com/{SOURCE_REPOSITORY}.git",
        ]
    )
    run_checked(
        [
            "git",
            "-C",
            str(destination),
            "fetch",
            "--quiet",
            "--depth=1",
            "origin",
            SOURCE_REVISION,
        ]
    )
    run_checked(
        ["git", "-C", str(destination), "checkout", "--quiet", "--detach", "FETCH_HEAD"]
    )
    observed = subprocess.check_output(
        ["git", "-C", str(destination), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    if observed != SOURCE_REVISION:
        raise RuntimeError(
            f"source checkout mismatch: expected {SOURCE_REVISION}, observed {observed}"
        )


def git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def fetch_pinned_controller(destination: Path) -> None:
    url = (
        f"https://raw.githubusercontent.com/{CONTROLLER_REPOSITORY}/"
        f"{CONTROLLER_REVISION}/{CONTROLLER_PATH}"
    )
    request = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
        if response.status != 200:
            raise RuntimeError(f"controller fetch failed: HTTP {response.status}")
    observed = git_blob_sha1(payload)
    if observed != CONTROLLER_BLOB_SHA1:
        raise RuntimeError(
            f"controller blob mismatch: expected {CONTROLLER_BLOB_SHA1}, "
            f"observed {observed}"
        )
    destination.write_bytes(payload)


def ensure_runtime_configuration(api: HfApi) -> dict[str, Any]:
    api.create_repo(
        repo_id=HF_REPOSITORY,
        repo_type="space",
        space_sdk="docker",
        exist_ok=True,
        private=False,
    )
    api.auth_check(repo_id=HF_REPOSITORY, repo_type="space", write=True)

    configured = set(api.get_space_secrets(repo_id=HF_REPOSITORY))
    if SIGNING_SECRET in configured:
        secret_action = "preserved"
    else:
        api.add_space_secret(
            repo_id=HF_REPOSITORY,
            key=SIGNING_SECRET,
            value=secrets.token_hex(32),
            description=(
                "Persistent HMAC key for Sentra verdict receipts; generated once "
                "by the canonical a11oy writer."
            ),
        )
        secret_action = "created"

    api.add_space_variable(
        repo_id=HF_REPOSITORY,
        key=SOURCE_VARIABLE,
        value=SOURCE_REVISION,
        description="Exact GitHub revision for fail-closed runtime binding.",
    )
    return {
        "secret": SIGNING_SECRET,
        "secret_action": secret_action,
        "secret_value_recorded": False,
        "source_variable": SOURCE_VARIABLE,
        "source_variable_value": SOURCE_REVISION,
    }


def get_json(path: str) -> tuple[int, Any]:
    separator = "&" if "?" in path else "?"
    request = urllib.request.Request(
        f"{ORIGIN}{path}{separator}szl_verify={time.time_ns()}",
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.loads(response.read())


def verify_contract() -> dict[str, Any]:
    ready_status, ready = get_json("/readyz")
    build_status, build = get_json("/api/build-info")
    complete = (
        ready_status == 200
        and ready.get("ready") is True
        and ready.get("sentra_signing_key_source") == "env"
        and ready.get("build", {}).get("state") == "OBSERVED"
        and ready.get("build", {}).get("revision") == SOURCE_REVISION
        and build_status == 200
        and build.get("schema") == "szl.build-info/v1"
        and build.get("source_repository") == SOURCE_REPOSITORY
        and build.get("build", {}).get("state") == "OBSERVED"
        and build.get("build", {}).get("revision") == SOURCE_REVISION
        and build.get("source_binding", {}).get("bindings_agree") is True
        and build.get("receipt_minted") is False
    )
    return {
        "complete": complete,
        "ready_http": ready_status,
        "ready": ready,
        "build_info_http": build_status,
        "build_info": build,
    }


def deploy_with_controller(source: Path, controller: Path, manifest: Path) -> None:
    smoke_json = json.dumps(SMOKE_PATHS, separators=(",", ":"))
    base = [
        sys.executable,
        str(controller),
        "--repo-root",
        str(source),
        "--github-repo",
        SOURCE_REPOSITORY,
        "--hf-repo",
        HF_REPOSITORY,
    ]
    run_checked(
        base
        + [
            "--ref",
            SOURCE_REVISION,
            "--source-sha",
            SOURCE_REVISION,
            "--dockerfile-path",
            "deploy/Dockerfile",
            "--source-revision-file",
            "deploy/source_revision.txt",
            "--include-readme",
            "true",
            "--smoke-paths",
            smoke_json,
            "--manifest-out",
            str(manifest),
            "--require-default-branch-tip",
        ]
    )
    run_checked(
        [
            sys.executable,
            str(controller),
            "--restart-space",
            "--manifest",
            str(manifest),
            "--hf-repo",
            HF_REPOSITORY,
        ]
    )
    run_checked(
        [
            sys.executable,
            str(controller),
            "--attest",
            "--manifest",
            str(manifest),
            "--hf-repo",
            HF_REPOSITORY,
            "--wait-running",
            "1200",
            "--smoke-retries",
            "20",
        ]
    )


def main() -> int:
    token, token_source = token_from_env()
    os.environ["HF_TOKEN"] = token
    receipt: dict[str, Any] = {
        "schema": "szl.hf-vertical-services-publication/v1",
        "generated_at": utc_now(),
        "source_repository": SOURCE_REPOSITORY,
        "source_revision": SOURCE_REVISION,
        "hf_repository": HF_REPOSITORY,
        "origin": ORIGIN,
        "controller_repository": CONTROLLER_REPOSITORY,
        "controller_revision": CONTROLLER_REVISION,
        "controller_blob_sha1": CONTROLLER_BLOB_SHA1,
        "token_source_name": token_source,
        "token_value_recorded": False,
        "delete_operations": 0,
        "vessels_space_retained": True,
        "complete": False,
    }
    try:
        api = HfApi(token=token)
        receipt["configuration"] = ensure_runtime_configuration(api)
        with tempfile.TemporaryDirectory(prefix="szl-vertical-services-") as td:
            root = Path(td)
            source = root / "source"
            controller = root / "hf_deploy_from_dockerfile.py"
            manifest = root / "manifest.json"
            checkout_exact_source(source)
            fetch_pinned_controller(controller)
            deploy_with_controller(source, controller, manifest)
            receipt["deployment_manifest"] = json.loads(
                manifest.read_text(encoding="utf-8")
            )
        receipt["verification"] = verify_contract()
        receipt["complete"] = receipt["verification"]["complete"]
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        receipt["finished_at"] = utc_now()
        RECEIPT_PATH.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
