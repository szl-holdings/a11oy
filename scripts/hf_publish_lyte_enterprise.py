#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish the exact source-owned Lyte Enterprise runtime through A11oy.

The existing canonical writer deploys an already-existing Space through the
same byte-pinned, Dockerfile-derived controller. Current Lyte 4 runtime checks
live in an adjacent, pure verification module. No second writer is introduced.
Process execution uses the #2117 szl_release_guard runner: POSIX process-group
timeout, output cap, no shell. This module still owns mutation; the guard
does not gain execution authority.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

from szl_release_guard import run_bounded as guard_run_bounded, strict_json
from szl_release_guard import ReleaseJournal, digest, immutable_json, source_qualification

SOURCE_REPOSITORY = "szl-holdings/lyte-services"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
SOURCE_WORKFLOW_ID = 345363884
GITHUB_ACTIONS_APP_ID = 15368
SOURCE_REQUIRED_CHECKS = (
    "python-compile", "lint", "unit", "api-contract", "release-gates",
    "database-migrations", "connector-contract", "truth-and-governance",
    "security-scan", "secret-scan", "frontend-static-contract", "accessibility",
    "responsive-overflow", "bundle-budget", "container-build", "container-smoke",
    "source-binding",
)
EXPECTED_VERSION = "4.0.0"
HF_REPOSITORY = "SZLHOLDINGS/lyte"
ORIGIN = "https://szlholdings-lyte.hf.space"
SOURCE_VARIABLE = "LYTE_SOURCE_REVISION"
RECEIPT_PATH = Path("hf-lyte-enterprise-receipt.json")
FAILED_MANIFEST_PATH = Path("hf-lyte-enterprise-manifest.failed.json")
CONTRACT_PATH = Path(__file__).resolve().with_name("lyte_enterprise_live_contract.py")
DEFAULT_COMMAND_TIMEOUT_S = 600
ATTEST_COMMAND_TIMEOUT_S = 2400
PHASE_JOURNAL: list[dict[str, Any]] = []
EVIDENCE_DIRECTORY = Path("hf-lyte-release-evidence")
SOURCE_MARKER = "source_revision.txt"
RELEASE_PHASES = (
    "qualify-source", "controller-preflight", "snapshot-previous", "recheck-source",
    "publish-files", "confirm-publication", "bind-source", "restart",
    "attest-runtime", "verify-existing", "verify-source-again",
)

CONTROLLER_REPOSITORY = "szl-holdings/.github"
CONTROLLER_REVISION = "163a61fd9759e5ecc3c2daf13e528f7b281ff81d"
CONTROLLER_PATH = ".github/scripts/hf_deploy_from_dockerfile.py"
CONTROLLER_BLOB_SHA1 = "3fa968416a3623d66b5b5b64abf8b830cc854e1c"
USER_AGENT = "SZLHOLDINGS-Lyte-Enterprise-Publisher/4.0"


class SourceSuperseded(RuntimeError):
    """An admitted producer or publisher is no longer the current source."""


class OutcomeUncertain(RuntimeError):
    """A mutation may have happened; reconcile its retained intent before retry."""

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


def github_json(path: str) -> dict[str, Any]:
    if not path.startswith("/repos/") or "\\" in path or "#" in path:
        raise RuntimeError("invalid source evidence path")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT,
               "X-GitHub-Api-Version": "2022-11-28", "Cache-Control": "no-cache"}
    token = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, response_headers, newurl):
            raise RuntimeError("Lyte source resolution redirect refused")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=30) as response:
        payload = strict_json(response.read(2_000_001))
    if not isinstance(payload, dict):
        raise RuntimeError("Lyte source resolution returned a non-object")
    return payload


def github_rows(path: str, field: str) -> list[dict[str, Any]]:
    """Retrieve a complete bounded native evidence collection, never a prefix."""
    rows: list[dict[str, Any]] = []
    expected: int | None = None
    for page in range(1, 21):
        separator = "&" if "?" in path else "?"
        payload = github_json(f"{path}{separator}per_page=100&page={page}")
        count, items = payload.get("total_count"), payload.get(field)
        if (type(count) is not int or not 0 <= count <= 2000
                or not isinstance(items, list) or len(items) > 100
                or any(not isinstance(item, dict) for item in items)):
            raise RuntimeError("invalid or excessive native source collection")
        if expected is None:
            expected = count
        if count != expected:
            raise RuntimeError("native source collection changed during pagination")
        rows.extend(items)
        identities = [item.get("id") for item in rows]
        if (any(type(identity) is not int or identity <= 0 for identity in identities)
                or len(set(identities)) != len(identities) or len(rows) > expected):
            raise RuntimeError("native source collection identities are invalid")
        if len(rows) == expected:
            return rows
        if not items or len(items) < 100:
            raise RuntimeError("native source collection is incomplete")
    raise RuntimeError("native source collection page limit exceeded")


def verified_revision(head: dict[str, Any]) -> str:
    revision = head.get("sha")
    commit = head.get("commit")
    verification = commit.get("verification") if isinstance(commit, dict) else None
    if (not isinstance(revision, str) or SHA40.fullmatch(revision) is None
            or revision == "0" * 40 or not isinstance(verification, dict)
            or verification.get("verified") is not True):
        raise RuntimeError("Lyte main is not an exact verified source commit")
    return revision


def resolve_verified_source_tip() -> tuple[str, dict[str, Any]]:
    """Qualify one current source SHA before any Hub configuration or write."""
    revision = verified_revision(github_json(f"/repos/{SOURCE_REPOSITORY}/commits/main"))
    checks = github_rows(
        f"/repos/{SOURCE_REPOSITORY}/commits/{revision}/check-runs?filter=latest", "check_runs"
    )
    trusted = [row for row in checks if isinstance(row, dict)
               and row.get("head_sha") == revision and isinstance(row.get("app"), dict)
               and row["app"].get("slug") == "github-actions"
               and row["app"].get("id") == GITHUB_ACTIONS_APP_ID]
    accepted = {
        name for name in SOURCE_REQUIRED_CHECKS
        if any(row.get("name") == name for row in trusted)
        and all(row.get("status") == "completed" and row.get("conclusion") == "success"
                for row in trusted if row.get("name") == name)
    }
    missing = sorted(set(SOURCE_REQUIRED_CHECKS) - accepted)
    if missing:
        raise RuntimeError("Lyte source gates did not pass: " + ", ".join(missing))
    runs = github_rows(
        f"/repos/{SOURCE_REPOSITORY}/actions/workflows/compiler.yml/runs"
        f"?head_sha={revision}&event=push&branch=main", "workflow_runs"
    )
    matching = [row for row in runs if row.get("head_sha") == revision
                and row.get("event") == "push" and row.get("head_branch") == "main"
                and row.get("workflow_id") == SOURCE_WORKFLOW_ID]
    if not matching:
        raise RuntimeError("Lyte native source workflow is missing")
    run_id = max(matching, key=lambda row: row["id"])["id"]
    run = github_json(f"/repos/{SOURCE_REPOSITORY}/actions/runs/{run_id}")
    attempt = run.get("run_attempt")
    if run.get("id") != run_id or type(attempt) is not int or attempt < 1:
        raise RuntimeError("Lyte native source workflow attempt is invalid")
    jobs = github_rows(
        f"/repos/{SOURCE_REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}/jobs", "jobs"
    )
    latest = github_json(f"/repos/{SOURCE_REPOSITORY}/actions/runs/{run_id}")
    if latest != run:
        # Source CI can change while its latest attempt is being collected.
        raise RuntimeError("Lyte source workflow changed during qualification")
    default_tip = github_json(f"/repos/{SOURCE_REPOSITORY}/git/ref/heads/main")
    qualification = source_qualification(
        source=revision, repository=SOURCE_REPOSITORY,
        default_tip=default_tip, workflow_run=run,
        jobs=jobs, expected_workflow_id=SOURCE_WORKFLOW_ID,
    )
    if qualification["passed"] is not True:
        raise RuntimeError("Lyte native source jobs did not qualify")
    return revision, {
        "schema": "szl.lyte-source-resolution/v1", "repository": SOURCE_REPOSITORY,
        "branch": "main", "revision": revision, "verified_commit": True,
        "required_checks": list(SOURCE_REQUIRED_CHECKS),
        "live_health_check_used_as_source_gate": False,
        "default_branch_tip_rechecked_by_deployer": True, "token_value_recorded": False,
        "check_app_id": GITHUB_ACTIONS_APP_ID, "pagination_complete": True,
        "workflow_id": SOURCE_WORKFLOW_ID, "run_id": run_id, "run_attempt": attempt,
        "source_qualification": qualification,
    }


def require_current_source(revision: str) -> None:
    if verified_revision(github_json(f"/repos/{SOURCE_REPOSITORY}/commits/main")) != revision:
        raise SourceSuperseded("PRODUCER_SOURCE_SUPERSEDED")


def require_current_publisher(revision: str) -> None:
    if verified_revision(github_json("/repos/szl-holdings/a11oy/commits/main")) != revision:
        raise SourceSuperseded("PUBLISHER_SOURCE_SUPERSEDED")


def journal(phase: str, **extra: Any) -> None:
    PHASE_JOURNAL.append({"ts": utc_now(), "phase": phase, **extra})


def run_bounded(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = DEFAULT_COMMAND_TIMEOUT_S,
) -> None:
    """Writer-facing wrapper over the #2117 POSIX bounded runner.

    Public journal records reason codes and pass/fail only. Guard receipts
    never include raw process output. A failed observation raises; it does
    not mint a publication success.
    """
    journal("run_bounded", argv=command[:6], timeout=timeout)
    workdir = cwd if cwd is not None else Path.cwd()
    observation = guard_run_bounded(command, cwd=workdir, timeout=float(timeout))
    journal(
        "run_bounded_observation",
        reason_code=observation.get("reason_code"),
        passed=observation.get("passed"),
        exit_code=observation.get("exit_code"),
        timed_out=observation.get("timed_out"),
        output_limited=observation.get("output_limited"),
        output_complete=observation.get("output_complete"),
        execution_authority="NONE",
    )
    if observation.get("passed") is not True:
        code = observation.get("reason_code") or "NONZERO_EXIT_UNCLASSIFIED"
        journal("run_bounded_fail", argv=command[:6], reason_code=code)
        raise RuntimeError(
            f"command failed with {code}: " + " ".join(command[:5])
        )
    journal("run_bounded_ok", argv=command[:6])


def run_checked(
    command: list[str], *, cwd: Path | None = None, timeout: int = DEFAULT_COMMAND_TIMEOUT_S,
) -> None:
    run_bounded(command, cwd=cwd, timeout=timeout)


def checkout_exact_source(destination: Path, *, revision: str) -> None:
    run_checked(["git", "init", "--quiet", str(destination)])
    run_checked([
        "git", "-C", str(destination), "remote", "add", "origin",
        f"https://github.com/{SOURCE_REPOSITORY}.git",
    ])
    run_checked([
        "git", "-C", str(destination), "fetch", "--quiet", "--depth=1",
        "origin", revision,
    ])
    run_checked([
        "git", "-C", str(destination), "checkout", "--quiet", "--detach", "FETCH_HEAD",
    ])
    # Guard runner does not return raw stdout. Detached HEAD is the SHA on disk.
    head_path = destination / ".git" / "HEAD"
    observed = head_path.read_text(encoding="utf-8").strip().lower()
    if observed.startswith("ref:"):
        raise RuntimeError("source checkout is not detached")
    if observed != revision:
        raise RuntimeError(
            f"source checkout mismatch: expected {revision}, observed {observed}"
        )


def git_blob_sha1(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def fetch_pinned_controller(destination: Path) -> None:
    url = (
        f"https://raw.githubusercontent.com/{CONTROLLER_REPOSITORY}/"
        f"{CONTROLLER_REVISION}/{CONTROLLER_PATH}"
    )
    # A socket timeout alone does not bound a slow response body. This fixed,
    # reviewed fetch program runs inside the existing POSIX wall-clock runner.
    program = """import pathlib,sys,urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):
        raise RuntimeError('CONTROLLER_REDIRECT_REFUSED')
url,destination,user_agent=sys.argv[1:]
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
request=urllib.request.Request(url,headers={'Cache-Control':'no-cache','User-Agent':user_agent})
with opener.open(request,timeout=30) as response:
    if response.status!=200 or response.geturl()!=url:
        raise RuntimeError('CONTROLLER_RESPONSE_IDENTITY_DIFFERS')
    payload=response.read(1000001)
if len(payload)>1000000:
    raise RuntimeError('CONTROLLER_BYTE_LIMIT_EXCEEDED')
pathlib.Path(destination).write_bytes(payload)
"""
    run_checked([sys.executable, "-c", program, url, str(destination), USER_AGENT], timeout=35)
    if destination.is_symlink() or not destination.is_file() or destination.stat().st_size > 1_000_000:
        raise RuntimeError("controller output is not a bounded regular file")
    payload = destination.read_bytes()
    if len(payload) > 1_000_000:
        raise RuntimeError("controller byte limit exceeded")
    observed = git_blob_sha1(payload)
    if observed != CONTROLLER_BLOB_SHA1:
        raise RuntimeError(
            f"controller blob mismatch: expected {CONTROLLER_BLOB_SHA1}, observed {observed}"
        )
    destination.write_bytes(payload)


def prepare_source_marker(source: Path, *, revision: str) -> dict[str, Any]:
    """Remove only the tracked marker in this isolated publication checkout.

    The controller generates its replacement from the admitted revision and
    records generated_from_source_sha in the derived manifest. The original
    marker hash is retained; the projection is not described as Git byte parity.
    """
    marker = source / SOURCE_MARKER
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 256:
        raise RuntimeError("source marker is not a bounded regular file")
    original = marker.read_bytes()
    value = original.decode("ascii").strip()
    if value != "UNAVAILABLE" and SHA40.fullmatch(value) is None:
        raise RuntimeError("source marker has an unsupported contract")
    if SHA40.fullmatch(revision) is None or revision == "0" * 40:
        raise RuntimeError("source marker revision is invalid")
    marker.unlink()
    return {
        "path": SOURCE_MARKER, "original_sha256": hashlib.sha256(original).hexdigest(),
        "original_bytes": len(original), "generated_from_source_sha": True,
        "projection_revision": revision, "producer_file_modified_remotely": False,
    }


def reset_generated_marker(source: Path, *, revision: str) -> None:
    marker = source / SOURCE_MARKER
    expected = (revision + "\n").encode("ascii")
    if (marker.is_symlink() or not marker.is_file() or marker.stat().st_size != len(expected)
            or marker.read_bytes() != expected):
        raise RuntimeError("generated source marker changed after preflight")
    marker.unlink()


def read_manifest(path: Path, *, revision: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise RuntimeError("controller manifest is missing or excessive")
    value = strict_json(path.read_bytes())
    if not isinstance(value, dict):
        raise RuntimeError("controller manifest is not an object")
    if (value.get("github_repo") != SOURCE_REPOSITORY or value.get("hf_repo") != HF_REPOSITORY
            or value.get("ref") != revision or value.get("source_sha") != revision
            or value.get("source_revision_file") != SOURCE_MARKER
            or value.get("unresolved_sources") != []
            or not isinstance(value.get("manifest_sha256"), str)
            or SHA64.fullmatch(value["manifest_sha256"]) is None):
        raise RuntimeError("controller manifest identity differs from the source plan")
    stable = {key: item for key, item in value.items() if key not in {
        "generated_utc", "manifest_sha256", "hf_commit_oid", "pruned", "transaction",
    }}
    if digest(stable) != value["manifest_sha256"]:
        raise RuntimeError("controller manifest digest is inconsistent")
    files = value.get("files")
    if (not isinstance(files, dict) or not files or type(value.get("files_deployed")) is not int
            or value["files_deployed"] != len(files)
            or not {"Dockerfile", "README.md", SOURCE_MARKER} <= set(files)):
        raise RuntimeError("controller file closure is incomplete")
    marker = files[SOURCE_MARKER]
    content = revision + "\n"
    if (not isinstance(marker, dict) or marker.get("generated_from_source_sha") is not True
            or marker.get("generated_content_utf8") != content
            or marker.get("sha256") != hashlib.sha256(content.encode("ascii")).hexdigest()
            or marker.get("size") != len(content)):
        raise RuntimeError("controller source marker is not independently bound")
    return value


def controller_publish_command(source: Path, controller: Path, manifest: Path, *, revision: str) -> list[str]:
    return [
        sys.executable, str(controller), "--repo-root", str(source),
        "--github-repo", SOURCE_REPOSITORY, "--hf-repo", HF_REPOSITORY,
        "--ref", revision, "--source-sha", revision,
        "--source-revision-file", SOURCE_MARKER,
        "--dockerfile-path", "Dockerfile", "--include-readme", "true",
        "--smoke-paths", json.dumps(SMOKE_PATHS, separators=(",", ":")),
        "--manifest-out", str(manifest), "--prune", "--require-default-branch-tip",
    ]


def controller_preflight(source: Path, controller: Path, manifest: Path, *, revision: str) -> dict[str, Any]:
    marker = prepare_source_marker(source, revision=revision)
    run_checked(controller_publish_command(source, controller, manifest, revision=revision) + ["--dry-run"])
    derived = read_manifest(manifest, revision=revision)
    return {"source_marker": marker, "manifest_sha256": derived["manifest_sha256"],
            "file_count": len(derived["files"]), "remote_writes": 0}


def snapshot_previous(api: HfApi) -> dict[str, Any]:
    """Read the existing target parent; creation and capacity changes are absent."""
    api.auth_check(repo_id=HF_REPOSITORY, repo_type="space", write=True)
    info = api.repo_info(repo_id=HF_REPOSITORY, repo_type="space")
    parent = getattr(info, "sha", None)
    if not isinstance(parent, str) or SHA40.fullmatch(parent) is None or parent == "0" * 40:
        raise RuntimeError("target parent is not an exact existing commit")
    return {"expected_hf_parent": parent, "space_preexisted": True,
            "rollback_parent_retained": True, "rollback_runtime_acceptance": "UNVERIFIED"}


def require_published_commit(api: HfApi, *, revision: str, manifest: Path, plan: dict[str, Any]) -> dict[str, Any]:
    value = read_manifest(manifest, revision=revision)
    commit = value.get("hf_commit_oid")
    transaction = value.get("transaction")
    if (not isinstance(commit, str) or SHA40.fullmatch(commit) is None
            or value["manifest_sha256"] != plan["manifest_sha256"]
            or not isinstance(transaction, dict)
            or transaction.get("operation_id") != plan["operation_id"]
            or transaction.get("expected_parent") != plan["expected_hf_parent"]):
        raise OutcomeUncertain("PUBLISHED_MANIFEST_IDENTITY_UNCONFIRMED")
    if getattr(api.repo_info(repo_id=HF_REPOSITORY, repo_type="space"), "sha", None) != commit:
        raise SourceSuperseded("HF_PUBLICATION_SUPERSEDED")
    return {"hf_commit_oid": commit, "operation_id": plan["operation_id"],
            "manifest_sha256": value["manifest_sha256"], "current_target_matched": True}


def ensure_runtime_configuration(api: HfApi, *, revision: str) -> dict[str, Any]:
    """Require the existing Space and bind only a non-secret source variable."""
    api.auth_check(repo_id=HF_REPOSITORY, repo_type="space", write=True)
    try:
        api.add_space_variable(
            repo_id=HF_REPOSITORY, key=SOURCE_VARIABLE, value=revision,
            description="Exact tested GitHub revision for Lyte fail-closed source binding.",
        )
        variables = api.get_space_variables(repo_id=HF_REPOSITORY)
        metadata = variables.get(SOURCE_VARIABLE) if isinstance(variables, dict) else None
        observed = metadata.get("value") if isinstance(metadata, dict) else getattr(metadata, "value", None)
        if observed != revision:
            raise RuntimeError("source variable readback differs")
    except Exception as exc:
        raise OutcomeUncertain("SOURCE_BINDING_RECONCILIATION_REQUIRED") from exc
    return {
        "space_preexisted": True, "space_created": False,
        "source_variable": SOURCE_VARIABLE, "source_variable_value": revision,
        "source_variable_readback_matched": True,
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
    source: Path, controller: Path, manifest: Path, *, revision: str,
    plan: dict[str, Any], intent: Path,
) -> None:
    # Dry-run has materialized the admitted marker. Only that exact generated
    # file is reset so the controller can derive the identical plan again.
    read_manifest(manifest, revision=revision)
    reset_generated_marker(source, revision=revision)
    require_current_source(revision)
    require_current_publisher(plan["publisher_revision"])
    command = controller_publish_command(source, controller, manifest, revision=revision)
    command += [
        "--expected-hf-parent", plan["expected_hf_parent"],
        "--operation-id", plan["operation_id"],
        "--expected-manifest-sha256", plan["manifest_sha256"],
        "--transaction-journal", str(intent),
    ]
    try:
        run_checked(command)
    except BaseException as exc:
        # An intent exists only after the real writer has qualified the complete
        # closure and is about to submit its provider CAS. Never retry here.
        if intent.exists():
            raise OutcomeUncertain("HF_WRITE_RECONCILIATION_REQUIRED") from exc
        raise


def restart_with_controller(controller: Path, manifest: Path) -> None:
    try:
        run_checked([
            sys.executable, str(controller), "--restart-space", "--manifest", str(manifest),
            "--hf-repo", HF_REPOSITORY,
        ])
    except Exception as exc:
        raise OutcomeUncertain("RESTART_RECONCILIATION_REQUIRED") from exc


def attest_with_controller(controller: Path, manifest: Path) -> None:
    run_checked([
        sys.executable, str(controller), "--attest", "--manifest", str(manifest),
        "--hf-repo", HF_REPOSITORY, "--wait-running", "1200", "--smoke-retries", "24",
    ], timeout=ATTEST_COMMAND_TIMEOUT_S)


def verify_contract(*, revision: str) -> dict[str, Any]:
    """Verify the current source-owned API, never the retired v3 deployment."""
    spec = importlib.util.spec_from_file_location("szl_lyte_live_contract", CONTRACT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("source-owned Lyte live contract is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_current_contract(
        request_json, request_text, revision=revision, version=EXPECTED_VERSION,
    )


def main() -> int:
    PHASE_JOURNAL.clear()
    token, token_source = token_from_env()
    os.environ["HF_TOKEN"] = token
    receipt: dict[str, Any] = {
        "schema": "szl.hf-lyte-enterprise-publication/v3", "generated_at": utc_now(),
        "source_repository": SOURCE_REPOSITORY, "source_revision": "UNRESOLVED",
        "expected_version": EXPECTED_VERSION, "hf_repository": HF_REPOSITORY,
        "origin": ORIGIN, "controller_repository": CONTROLLER_REPOSITORY,
        "controller_revision": CONTROLLER_REVISION, "controller_blob_sha1": CONTROLLER_BLOB_SHA1,
        "token_source_name": token_source, "token_value_recorded": False,
        "secret_values_recorded": False, "sentra_signing_key_touched": False,
        "space_created": False, "delete_operations": 0, "complete": False,
        "release_guard_runner": "szl_release_guard.run_bounded",
        "execution_authority": "NONE",
        "state": "PREPARE", "reconciliation_required": False,
    }
    try:
        revision, receipt["source_resolution"] = resolve_verified_source_tip()
        receipt["source_revision"] = revision
        publisher = os.getenv("GITHUB_SHA", "")
        if SHA40.fullmatch(publisher) is None or publisher == "0" * 40:
            raise RuntimeError("exact canonical publisher source is required")
        release = ReleaseJournal(EVIDENCE_DIRECTORY, source=revision, publisher=publisher,
                                 phases=RELEASE_PHASES)
        receipt["release_evidence_directory"] = str(release.directory)
        def phase(name, action):
            evidence = None
            def execute():
                nonlocal evidence
                evidence = action()
                if evidence is None:
                    evidence = {"executed": True}
                immutable_json(release.directory, evidence)
                return {"executed": True, "passed": True, "evidence_sha256": digest(evidence)}
            release.perform(name, execute)
            return evidence
        phase("qualify-source", lambda: receipt["source_resolution"])
        api = HfApi(token=token)
        with tempfile.TemporaryDirectory(prefix="szl-lyte-enterprise-") as td:
            root = Path(td)
            source, controller, manifest = root / "source", root / "controller.py", root / "manifest.json"
            checkout_exact_source(source, revision=revision)
            fetch_pinned_controller(controller)
            preflight = phase("controller-preflight", lambda: controller_preflight(
                source, controller, manifest, revision=revision))
            previous = phase("snapshot-previous", lambda: snapshot_previous(api))
            operation = digest({"publisher": publisher, "source": revision,
                                "run_id": os.getenv("GITHUB_RUN_ID", ""),
                                "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", ""),
                                "manifest_sha256": preflight["manifest_sha256"],
                                "expected_parent": previous["expected_hf_parent"],
                                "journal_identity": release.directory.name})
            plan = {
                "schema": "szl.lyte-release-plan/v1", "source_repository": SOURCE_REPOSITORY,
                "source_revision": revision, "publisher_revision": publisher,
                "controller_revision": CONTROLLER_REVISION,
                "controller_blob_sha1": CONTROLLER_BLOB_SHA1,
                "expected_version": EXPECTED_VERSION, "hf_repository": HF_REPOSITORY,
                "origin": ORIGIN, "operation_id": operation,
                **preflight, **previous,
            }
            immutable_json(release.directory, plan)
            receipt["release_plan"] = plan
            intent = release.directory.resolve() / ("operation-" + operation + ".json")
            receipt["transaction_journal"] = str(intent)
            def recheck():
                require_current_source(revision)
                require_current_publisher(publisher)
                return {"source_revision": revision, "publisher_revision": publisher,
                        "current_default_tips_matched": True}
            phase("recheck-source", recheck)
            try:
                receipt["state"] = "PUBLISH"
                phase("publish-files", lambda: deploy_with_controller(
                    source, controller, manifest, revision=revision, plan=plan, intent=intent))
                confirmation = phase("confirm-publication", lambda: require_published_commit(
                    api, revision=revision, manifest=manifest, plan=plan))
                receipt["publication"] = confirmation
                # The image already carries the admitted source marker. Bind the
                # runtime variable only after observing the actual publication.
                def bind():
                    recheck()
                    require_published_commit(api, revision=revision, manifest=manifest, plan=plan)
                    return ensure_runtime_configuration(api, revision=revision)
                receipt["configuration"] = phase("bind-source", bind)
                def restart():
                    recheck()
                    require_published_commit(api, revision=revision, manifest=manifest, plan=plan)
                    restart_with_controller(controller, manifest)
                    return {"restart_requested": True, "hf_commit_oid": confirmation["hf_commit_oid"]}
                phase("restart", restart)
                receipt["state"] = "VERIFY"
                phase("attest-runtime", lambda: attest_with_controller(controller, manifest))
                receipt["deployment_manifest"] = read_manifest(manifest, revision=revision)
            except Exception:
                if manifest.exists():
                    FAILED_MANIFEST_PATH.write_bytes(manifest.read_bytes())
                    receipt["retained_manifest"] = str(FAILED_MANIFEST_PATH.resolve())
                    journal("manifest_retained", path=receipt["retained_manifest"])
                raise
            def verify():
                evidence = verify_contract(revision=revision)
                if evidence.get("complete") is not True:
                    raise RuntimeError("LIVE_APPLICATION_CONTRACT_FAILED")
                return evidence
            receipt["verification"] = phase("verify-existing", verify)
            phase("verify-source-again", lambda: {
                **recheck(), **require_published_commit(api, revision=revision, manifest=manifest, plan=plan)})
        receipt["state"] = "RECORD"
        receipt["release_journal"] = release.summary()
        receipt["complete"] = receipt["release_journal"]["complete"]
        receipt["state"] = "RUNTIME_VERIFIED" if receipt["complete"] else "FAILED"
    except Exception as exc:
        causes = [exc]
        while causes[-1].__cause__ is not None:
            causes.append(causes[-1].__cause__)
        cause = next((item for item in causes if isinstance(item, (SourceSuperseded, OutcomeUncertain))), causes[-1])
        receipt["state"] = ("SUPERSEDED" if isinstance(cause, SourceSuperseded) else
                            "OUTCOME_UNCERTAIN" if isinstance(cause, OutcomeUncertain) else "FAILED")
        receipt["reconciliation_required"] = receipt["state"] == "OUTCOME_UNCERTAIN"
        # Provider exceptions can contain tokens or presigned URLs. Retain fixed
        # reason/phase evidence and process digests, never arbitrary error text.
        receipt["error"] = type(cause).__name__
        if "release" in locals():
            receipt["release_journal"] = release.summary()
        journal("error", error_type=receipt["error"], state=receipt["state"])
    finally:
        receipt["phase_journal"] = list(PHASE_JOURNAL)
        receipt["finished_at"] = utc_now()
        RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
