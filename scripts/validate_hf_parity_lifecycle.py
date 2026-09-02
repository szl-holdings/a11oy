#!/usr/bin/env python3
"""Validate the temporal contract of A11oy's GitHub↔Hugging Face parity rail.

The deployed Hub repository can equal protected base before a pull request is
merged, or exact protected main after publication. It cannot equal both base
and an unmerged head when those trees differ. This validator therefore locks a
three-stage lifecycle:

1. pull_request: prove the already-deployed protected base;
2. hf-sync: publish and relock exact merged main;
3. schedule/manual/post-deploy dispatch: prove Hub bytes and served source both
   equal the exact protected main revision.

This script is standard-library only and performs no network or provider write.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-module-drift.yml"
SYNC_WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"
MARKER = "lifecycle: post-deployment-repository-parity/v1"
SELECTOR = "select_hf_candidate_admission.py"
VERIFIER = "verify_hf_repository_parity.py"
TOOLS_PIN = "0816263f1e83734658d6e5a8a7cd3834f36a2054"
POST_DEPLOY_DISPATCH = (
    'gh workflow run hf-module-drift.yml --repo "$GITHUB_REPOSITORY" --ref main'
)


def active_source(text: str) -> str:
    """Remove whole-line comments while preserving executable YAML and scripts."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def job_block(text: str, job: str) -> str:
    pattern = re.compile(
        rf"^  {re.escape(job)}:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(0) if match else ""


def require(block: str, token: str, error: str, errors: list[str]) -> None:
    if token not in block:
        errors.append(error)


def forbid(block: str, token: str, error: str, errors: list[str]) -> None:
    if token in block:
        errors.append(error)


def validate_text(workflow: str, sync_workflow: str) -> list[str]:
    errors: list[str] = []
    executable = active_source(workflow)

    if workflow.count(MARKER) != 1:
        errors.append("HF parity lifecycle marker must appear exactly once")
    if SELECTOR in executable:
        errors.append("pre-merge candidate selector must not execute in the lifecycle workflow")
    if executable.count(VERIFIER) != 2:
        errors.append("repository parity verifier must execute exactly twice: base and post-deploy")
    if executable.count(f"ref: {TOOLS_PIN}") != 2:
        errors.append("both local parity jobs must use the exact reusable-tools revision")

    trigger_prefix = workflow.split("\npermissions:", 1)[0]
    if "\n  push:" in trigger_prefix:
        errors.append("hf-module-drift must not run directly on push before publication")
    for token in ("  pull_request:", "  schedule:", "  workflow_dispatch:"):
        require(trigger_prefix, token, f"workflow trigger missing {token.strip()}", errors)

    base = job_block(workflow, "hf-module-drift")
    runtime = job_block(workflow, "hf-runtime-live")
    repository = job_block(workflow, "hf-repository-parity")
    if not base:
        errors.append("protected-base parity job is missing")
    if not runtime:
        errors.append("live runtime source-witness job is missing")
    if not repository:
        errors.append("post-deployment repository parity job is missing")

    require(base, "name: Protected base matches immutable HF repository", "protected-base check name drifted", errors)
    require(base, "if: github.event_name == 'pull_request'", "protected-base parity must run only for pull requests", errors)
    require(base, "path: baseline", "protected-base verifier must use the baseline checkout", errors)
    require(base, "ref: ${{ github.event.pull_request.base.sha }}", "protected-base checkout must use the exact PR base SHA", errors)
    require(base, "SOURCE_REF: ${{ github.event.pull_request.base.sha }}", "protected-base command must receive the exact PR base SHA", errors)
    require(base, "baseline/.github/scripts/verify_hf_repository_parity.py", "protected-base job must execute the base-controlled verifier", errors)
    require(base, "--report-out hf-current-base-parity.out.json", "protected-base report path drifted", errors)
    forbid(base, "github.event.pull_request.head.sha", "protected-base job must never consume the PR head SHA", errors)
    forbid(base, "--base-ref", "protected-base parity must compare one exact source revision", errors)

    require(runtime, "name: Scheduled live HF runtime source witness", "runtime source-witness check name drifted", errors)
    require(runtime, "if: github.event_name != 'pull_request'", "runtime witness must run only after merge/publication or on scheduled/manual checks", errors)
    require(runtime, "trusted-base-ref: ${{ github.sha }}", "runtime witness must trust exact protected main", errors)
    require(runtime, "candidate-ref: ${{ github.sha }}", "runtime witness candidate must be exact protected main", errors)
    require(runtime, "github-ref: ${{ github.sha }}", "runtime witness source must be exact protected main", errors)
    require(runtime, "source-probe-path: /api/build-info", "runtime witness must read the served source identity", errors)

    require(repository, "name: Immutable HF repository byte parity", "post-deployment repository check name drifted", errors)
    require(repository, "if: github.event_name != 'pull_request'", "immutable Hub byte parity must not run against an unmerged PR head", errors)
    require(repository, "path: source", "post-deployment parity must use an exact source checkout", errors)
    require(repository, "ref: ${{ github.sha }}", "post-deployment checkout must use exact protected main", errors)
    require(repository, "SOURCE_REF: ${{ github.sha }}", "post-deployment command must receive exact protected main", errors)
    require(repository, "source/.github/scripts/verify_hf_repository_parity.py", "post-deployment job must execute the exact-main verifier", errors)
    require(repository, "--report-out hf-post-deployment-repository-parity.out.json", "post-deployment report path drifted", errors)
    require(repository, "name: hf-post-deployment-repository-parity", "post-deployment artifact name drifted", errors)
    forbid(repository, "github.event.pull_request.", "post-deployment parity must not consume pull-request event fields", errors)
    forbid(repository, "BASE_REF", "post-deployment parity must not compare against a second source revision", errors)
    forbid(repository, "--base-ref", "post-deployment parity must compare exact main directly with the Hub", errors)
    forbid(repository, SELECTOR, "post-deployment parity must not invoke the historical candidate selector", errors)

    require(
        sync_workflow,
        POST_DEPLOY_DISPATCH,
        "hf-sync must dispatch the parity workflow against protected main after publication",
        errors,
    )
    deploy_index = sync_workflow.find("Deploy, source-bind, and attest exact surface")
    dispatch_index = sync_workflow.find(POST_DEPLOY_DISPATCH)
    if deploy_index < 0 or dispatch_index < 0 or dispatch_index <= deploy_index:
        errors.append("post-deployment parity dispatch must appear after the governed publication job")

    return errors


def validate(root: Path = ROOT) -> list[str]:
    workflow_path = root / ".github" / "workflows" / "hf-module-drift.yml"
    sync_path = root / ".github" / "workflows" / "hf-sync.yml"
    errors: list[str] = []
    for path, label in ((workflow_path, "HF drift workflow"), (sync_path, "HF sync workflow")):
        if not path.is_file():
            errors.append(f"{label} is missing: {path.relative_to(root)}")
    if errors:
        return errors
    try:
        workflow = workflow_path.read_text(encoding="utf-8")
        sync_workflow = sync_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"workflow source must be valid UTF-8: {exc}"]
    return validate_text(workflow, sync_workflow)


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("HF parity lifecycle contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
