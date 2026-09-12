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

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from szl_release_guard import (  # noqa: E402
    ReleaseJournal,
    digest,
    retain_manifest_metadata,
    run_bounded,
)

SOURCE_REPOSITORY = "szl-holdings/lyte-services"
SOURCE_REVISION = "dd17d9f524b76c8f0e260d7ec1e084cc079dfc43"
EXPECTED_VERSION = "4.0.0"
HF_REPOSITORY = "SZLHOLDINGS/lyte"
ORIGIN = "https://szlholdings-lyte.hf.space"
SOURCE_VARIABLE = "LYTE_SOURCE_REVISION"
RECEIPT_PATH = Path("hf-lyte-enterprise-receipt.json")
EVIDENCE_PATH = Path("hf-lyte-enterprise-evidence")
CONTRACT_PATH = Path(__file__).resolve().with_name("lyte_enterprise_live_contract.py")

CONTROLLER_REPOSITORY = "szl-holdings/.github"
CONTROLLER_REVISION = "c889276e51e7d954c4bba8b216f86fc7577721fa"
CONTROLLER_PATH = ".github/scripts/hf_deploy_from_dockerfile.py"
CONTROLLER_BLOB_SHA1 = "9d5b90b8bbf04e6d46ef0f971fc65604e1323b1b"
USER_AGENT = "SZLHOLDINGS-Lyte-Enterprise-Publisher/4.0"

# Custom journal order matches the current writer. Default kit PHASES place
# bind-source after publish-files; that reorder waits on the marker strategy.
WRITER_PHASES = (
    "qualify-source",
    "controller-preflight",
    "bind-source",
    "publish-files",
    "restart",
    "attest-runtime",
    "verify-existing",
)
CHECKOUT_TIMEOUT = 180.0
PUBLISH_TIMEOUT = 3600.0
RESTART_TIMEOUT = 600.0
ATTEST_TIMEOUT = 3600.0

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


def phase_pass(payload: Any, *, reason_code: str = "OBSERVED_PASS") -> dict[str, Any]:
    """Public journal callback result: digests only, never process output."""
    body = payload if isinstance(payload, dict) else {"observed": True}
    return {
        "executed": True,
        "passed": True,
        "reason_code": reason_code,
        "evidence_sha256": digest(body),
    }


def observed_publisher_revision() -> str:
    root = Path(__file__).resolve().parents[1]
    try:
        observed = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=30,
        ).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("publisher revision is UNAVAILABLE") from exc
    if len(observed) != 40 or any(ch not in "0123456789abcdef" for ch in observed):
        raise RuntimeError("publisher revision is not a git sha")
    return observed


def run_checked(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Adapter over the admitted POSIX run_bounded primitive.

    Preserves the fail-closed command contract. Public results are reason codes
    and stream digests; raw child output is not returned.
    """
    observation = run_bounded(command, cwd=cwd or Path.cwd(), timeout=timeout)
    if not observation["passed"]:
        head = Path(command[0]).name if command else "argv"
        raise RuntimeError(
            f"command failed with {observation['reason_code']} "
            f"exit {observation['exit_code']}: {head}"
        )
    return observation


def checkout_exact_source(destination: Path) -> None:
    run_checked(["git", "init", "--quiet", str(destination)], timeout=CHECKOUT_TIMEOUT)
    run_checked([
        "git", "-C", str(destination), "remote", "add", "origin",
        f"https://github.com/{SOURCE_REPOSITORY}.git",
    ], timeout=CHECKOUT_TIMEOUT)
    run_checked([
        "git", "-C", str(destination), "fetch", "--quiet", "--depth=1",
        "origin", SOURCE_REVISION,
    ], timeout=CHECKOUT_TIMEOUT)
    run_checked([
        "git", "-C", str(destination), "checkout", "--quiet", "--detach", "FETCH_HEAD",
    ], timeout=CHECKOUT_TIMEOUT)
    observed = subprocess.check_output(
        ["git", "-C", str(destination), "rev-parse", "HEAD"], text=True, timeout=30,
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


def deploy_with_controller(
    source: Path,
    controller: Path,
    manifest: Path,
    journal: ReleaseJournal | None = None,
) -> None:
    smoke_json = json.dumps(SMOKE_PATHS, separators=(",", ":"))
    base = [
        sys.executable, str(controller), "--repo-root", str(source),
        "--github-repo", SOURCE_REPOSITORY, "--hf-repo", HF_REPOSITORY,
    ]
    publish_cmd = base + [
        "--ref", SOURCE_REVISION, "--source-sha", SOURCE_REVISION,
        "--dockerfile-path", "Dockerfile", "--include-readme", "true",
        "--smoke-paths", smoke_json, "--manifest-out", str(manifest),
        "--prune", "--require-default-branch-tip",
    ]
    restart_cmd = [
        sys.executable, str(controller), "--restart-space", "--manifest", str(manifest),
        "--hf-repo", HF_REPOSITORY,
    ]
    attest_cmd = [
        sys.executable, str(controller), "--attest", "--manifest", str(manifest),
        "--hf-repo", HF_REPOSITORY, "--wait-running", "1200", "--smoke-retries", "24",
    ]

    def publish_files() -> dict[str, Any]:
        return phase_pass(run_checked(publish_cmd, timeout=PUBLISH_TIMEOUT))

    def restart() -> dict[str, Any]:
        return phase_pass(run_checked(restart_cmd, timeout=RESTART_TIMEOUT))

    def attest_runtime() -> dict[str, Any]:
        return phase_pass(run_checked(attest_cmd, timeout=ATTEST_TIMEOUT))

    if journal is None:
        publish_files()
        restart()
        attest_runtime()
        return
    journal.perform("publish-files", publish_files)
    journal.perform("restart", restart)
    journal.perform("attest-runtime", attest_runtime)


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
        "raw_manifest_published": False, "writer_dispatched": False,
    }
    journal: ReleaseJournal | None = None
    try:
        api = HfApi(token=token)
        publisher_sha = observed_publisher_revision()
        receipt["publisher_revision"] = publisher_sha
        with tempfile.TemporaryDirectory(prefix="szl-lyte-enterprise-") as td:
            root = Path(td)
            source, controller, manifest = root / "source", root / "controller.py", root / "manifest.json"
            journal = ReleaseJournal(
                EVIDENCE_PATH, source=SOURCE_REVISION, publisher=publisher_sha,
                phases=WRITER_PHASES,
            )
            try:
                def qualify_source() -> dict[str, Any]:
                    checkout_exact_source(source)
                    return phase_pass({"source_revision": SOURCE_REVISION})

                def controller_preflight() -> dict[str, Any]:
                    fetch_pinned_controller(controller)
                    return phase_pass({"controller_blob_sha1": CONTROLLER_BLOB_SHA1})

                def bind_source() -> dict[str, Any]:
                    # Verify source and controller bytes before any runtime configuration write.
                    receipt["configuration"] = ensure_runtime_configuration(api)
                    return phase_pass(receipt["configuration"])

                journal.perform("qualify-source", qualify_source)
                journal.perform("controller-preflight", controller_preflight)
                journal.perform("bind-source", bind_source)
                deploy_with_controller(source, controller, manifest, journal=journal)

                def verify_existing() -> dict[str, Any]:
                    receipt["verification"] = verify_contract()
                    complete = receipt["verification"].get("complete") is True
                    receipt["complete"] = complete
                    if complete is not True:
                        raise RuntimeError("live contract is not complete")
                    return phase_pass({
                        "complete": True,
                        "execution_authority": receipt["verification"].get(
                            "execution_authority", "NONE",
                        ),
                    })

                journal.perform("verify-existing", verify_existing)
            finally:
                # Observe the controller manifest before the temporary workspace exits.
                receipt["controller_manifest"] = retain_manifest_metadata(
                    manifest, EVIDENCE_PATH,
                )
                receipt["phase_journal"] = journal.summary()
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        if journal is not None and "phase_journal" not in receipt:
            receipt["phase_journal"] = journal.summary()
    finally:
        receipt["finished_at"] = utc_now()
        RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
