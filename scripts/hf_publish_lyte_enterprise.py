#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish the exact source-owned Lyte Enterprise runtime through A11oy.

The existing canonical writer deploys an already-existing Space through the
same byte-pinned, Dockerfile-derived controller. Current Lyte 4 runtime checks
live in an adjacent, pure verification module. No second writer is introduced.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

SOURCE_REPOSITORY = "szl-holdings/lyte-services"
SOURCE_REVISION = "dd17d9f524b76c8f0e260d7ec1e084cc079dfc43"
EXPECTED_VERSION = "4.0.0"
HF_REPOSITORY = "SZLHOLDINGS/lyte"
ORIGIN = "https://szlholdings-lyte.hf.space"
SOURCE_VARIABLE = "LYTE_SOURCE_REVISION"
RECEIPT_PATH = Path("hf-lyte-enterprise-receipt.json")
CONTRACT_PATH = Path(__file__).resolve().with_name("lyte_enterprise_live_contract.py")

CONTROLLER_REPOSITORY = "szl-holdings/.github"
CONTROLLER_REVISION = "c889276e51e7d954c4bba8b216f86fc7577721fa"
CONTROLLER_PATH = ".github/scripts/hf_deploy_from_dockerfile.py"
CONTROLLER_BLOB_SHA1 = "9d5b90b8bbf04e6d46ef0f971fc65604e1323b1b"
USER_AGENT = "SZLHOLDINGS-Lyte-Enterprise-Publisher/4.0"

# API version and package version are distinct. The current 4.0.0 application
# owns /api/lyte/v2; the removed v3 application must never be its smoke target.
# Public metrics use the source-owned API alias, not a hosting ingress path.
SMOKE_PATHS = (
    "/", "/healthz", "/readyz", "/api/build-info", "/api/source",
    "/.well-known/szl-source.json", "/api/lyte/v2/metrics",
    "/static/lyte/styles.css", "/static/lyte/app.js",
    "/api/lyte/v2/catalog", "/api/lyte/v2/capabilities",
    "/api/lyte/v2/anatomy", "/api/lyte/v2/formulas", "/api/lyte/v2/sources",
    "/api/lyte/v2/services", "/api/lyte/v2/journeys", "/api/lyte/v2/outcomes",
    "/api/lyte/v2/agents", "/api/lyte/v2/incidents", "/api/lyte/v2/decisions",
    "/api/lyte/v2/playback", "/api/lyte/v2/second-brain",
    "/api/lyte/v2/evidence", "/api/lyte/v2/receipts",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def token_from_env() -> tuple[str, str]:
    for name in (
        "HF_ORG_TOKEN", "HF_WRITE_TOKEN", "HF_TOKEN",
        "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    raise RuntimeError("no Hugging Face write token available to canonical writer")


def run_checked(command: list[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode:
        raise RuntimeError(
            f"command failed with exit {result.returncode}: " + " ".join(command[:5])
        )


def checkout_exact_source(destination: Path) -> None:
    run_checked(["git", "init", "--quiet", str(destination)])
    run_checked([
        "git", "-C", str(destination), "remote", "add", "origin",
        f"https://github.com/{SOURCE_REPOSITORY}.git",
    ])
    run_checked([
        "git", "-C", str(destination), "fetch", "--quiet", "--depth=1",
        "origin", SOURCE_REVISION,
    ])
    run_checked([
        "git", "-C", str(destination), "checkout", "--quiet", "--detach", "FETCH_HEAD",
    ])
    observed = subprocess.check_output(
        ["git", "-C", str(destination), "rev-parse", "HEAD"], text=True,
    ).strip()
    if observed != SOURCE_REVISION:
        raise RuntimeError(
            f"source checkout mismatch: expected {SOURCE_REVISION}, observed {observed}"
        )


def git_blob_sha1(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def fetch_pinned_controller(destination: Path) -> None:
    url = (
        f"https://raw.githubusercontent.com/{CONTROLLER_REPOSITORY}/"
        f"{CONTROLLER_REVISION}/{CONTROLLER_PATH}"
    )
    request = urllib.request.Request(
        url, headers={"Cache-Control": "no-cache", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
        if response.status != 200:
            raise RuntimeError(f"controller fetch failed: HTTP {response.status}")
    observed = git_blob_sha1(payload)
    if observed != CONTROLLER_BLOB_SHA1:
        raise RuntimeError(
            f"controller blob mismatch: expected {CONTROLLER_BLOB_SHA1}, observed {observed}"
        )
    destination.write_bytes(payload)


def ensure_runtime_configuration(api: HfApi) -> dict[str, Any]:
    """Require the existing Space and bind only a non-secret source variable."""
    api.auth_check(repo_id=HF_REPOSITORY, repo_type="space", write=True)
    api.add_space_variable(
        repo_id=HF_REPOSITORY, key=SOURCE_VARIABLE, value=SOURCE_REVISION,
        description="Exact tested GitHub revision for Lyte fail-closed source binding.",
    )
    return {
        "space_preexisted": True, "space_created": False,
        "source_variable": SOURCE_VARIABLE, "source_variable_value": SOURCE_REVISION,
        "secret_values_read": False, "secret_values_written": False,
        "sentra_signing_key_touched": False,
    }


def request_json(
    path: str, *, method: str = "GET", payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None, attempts: int = 4,
    expected_statuses: tuple[int, ...] = (200,),
) -> tuple[int, Any]:
    """Retry transport failures, but preserve explicit negative-control statuses.

    A disabled Granite 503 is expected evidence, not a transient service failure.
    HTML 200 fallback responses cannot pass JSON decoding.
    """
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {
        "Accept": "application/json", "Cache-Control": "no-cache",
        "User-Agent": USER_AGENT, **(headers or {}),
    }
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        separator = "&" if "?" in path else "?"
        request = urllib.request.Request(
            f"{ORIGIN}{path}{separator}szl_verify={time.time_ns()}",
            data=body, method=method, headers=request_headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=75) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            if exc.code < 500 or exc.code in expected_statuses:
                try:
                    parsed: Any = json.loads(response_body)
                except json.JSONDecodeError:
                    parsed = {"body_excerpt": response_body[:500]}
                return exc.code, parsed
            last_error = exc
        except Exception as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(2 ** (attempt - 1))
    raise RuntimeError(
        f"live request did not converge: {method} {path}: "
        f"{type(last_error).__name__ if last_error else 'UnknownError'}"
    )


def request_text(path: str, *, attempts: int = 4) -> tuple[int, str]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        separator = "&" if "?" in path else "?"
        request = urllib.request.Request(
            f"{ORIGIN}{path}{separator}szl_verify={time.time_ns()}",
            headers={"Accept": "*/*", "Cache-Control": "no-cache", "User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(2 ** (attempt - 1))
    raise RuntimeError(
        "live text request did not converge: "
        f"{type(last_error).__name__ if last_error else 'UnknownError'}"
    )


def deploy_with_controller(source: Path, controller: Path, manifest: Path) -> None:
    smoke_json = json.dumps(SMOKE_PATHS, separators=(",", ":"))
    base = [
        sys.executable, str(controller), "--repo-root", str(source),
        "--github-repo", SOURCE_REPOSITORY, "--hf-repo", HF_REPOSITORY,
    ]
    run_checked(base + [
        "--ref", SOURCE_REVISION, "--source-sha", SOURCE_REVISION,
        "--dockerfile-path", "Dockerfile", "--include-readme", "true",
        "--smoke-paths", smoke_json, "--manifest-out", str(manifest),
        "--prune", "--require-default-branch-tip",
    ])
    run_checked([
        sys.executable, str(controller), "--restart-space", "--manifest", str(manifest),
        "--hf-repo", HF_REPOSITORY,
    ])
    run_checked([
        sys.executable, str(controller), "--attest", "--manifest", str(manifest),
        "--hf-repo", HF_REPOSITORY, "--wait-running", "1200", "--smoke-retries", "24",
    ])


def verify_contract() -> dict[str, Any]:
    """Verify the current source-owned API, never the retired v3 deployment."""
    spec = importlib.util.spec_from_file_location("szl_lyte_live_contract", CONTRACT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("source-owned Lyte live contract is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_current_contract(
        request_json, request_text, revision=SOURCE_REVISION, version=EXPECTED_VERSION,
    )


def main() -> int:
    token, token_source = token_from_env()
    os.environ["HF_TOKEN"] = token
    receipt: dict[str, Any] = {
        "schema": "szl.hf-lyte-enterprise-publication/v3", "generated_at": utc_now(),
        "source_repository": SOURCE_REPOSITORY, "source_revision": SOURCE_REVISION,
        "expected_version": EXPECTED_VERSION, "hf_repository": HF_REPOSITORY,
        "origin": ORIGIN, "controller_repository": CONTROLLER_REPOSITORY,
        "controller_revision": CONTROLLER_REVISION, "controller_blob_sha1": CONTROLLER_BLOB_SHA1,
        "token_source_name": token_source, "token_value_recorded": False,
        "secret_values_recorded": False, "sentra_signing_key_touched": False,
        "space_created": False, "delete_operations": 0, "complete": False,
    }
    try:
        api = HfApi(token=token)
        with tempfile.TemporaryDirectory(prefix="szl-lyte-enterprise-") as td:
            root = Path(td)
            source, controller, manifest = root / "source", root / "controller.py", root / "manifest.json"
            checkout_exact_source(source)
            fetch_pinned_controller(controller)
            # Verify source and controller bytes before any runtime configuration write.
            receipt["configuration"] = ensure_runtime_configuration(api)
            deploy_with_controller(source, controller, manifest)
            receipt["deployment_manifest"] = json.loads(manifest.read_text(encoding="utf-8"))
        receipt["verification"] = verify_contract()
        receipt["complete"] = receipt["verification"]["complete"]
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        receipt["finished_at"] = utc_now()
        RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
