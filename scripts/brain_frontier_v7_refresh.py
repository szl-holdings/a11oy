#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Reconcile the Brain Frontier review transaction and seal its run receipt.

The reconciler owns one narrow write boundary: a content-addressed review branch
whose tree is the exact protected ``main`` tree plus the materialized snapshot.
It never force-pushes, merges, approves, or mutates a provider. Existing branches
are accepted only after their snapshot, history scope, and source ancestry are
validated; a missing or closed pull request is then recovered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = "szl-holdings/a11oy"
BASE_BRANCH = "main"
SNAPSHOT_PATH = "console/assets/brain-frontier-v7.json"
BRANCH_PREFIX = "automation/brain-frontier-v7-"
SNAPSHOT_SCHEMA = "szl.a11oy.brain-frontier-holographic-v7/v1"
RECEIPT_SCHEMA = "szl.a11oy.brain-frontier-v7-refresh/v2"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PR_URL = re.compile(
    r"^https://github\.com/szl-holdings/a11oy/pull/(?P<number>[1-9][0-9]*)$"
)
SUCCESSFUL_PROPOSAL_STATES = {
    "EXISTING_REVIEW_PR",
    "NEW_REVIEW_PR",
    "RECOVERED_REVIEW_PR",
}
AUTOMATION_AUTHORS = {
    "41898282+github-actions[bot]@users.noreply.github.com",
    # Legacy branches were created by the previous workflow under this identity.
    "stephenlutar2@gmail.com",
}


class RefreshError(RuntimeError):
    """The refresh transaction could not prove a safe terminal state."""


@dataclass(frozen=True)
class Completed:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class Runner:
    """Run fixed argv commands without a shell or credential-bearing command text."""

    def __init__(self, cwd: Path | None = None) -> None:
        self.cwd = cwd or Path.cwd()

    def run(
        self,
        args: Sequence[str],
        *,
        check: bool = True,
        input_text: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> Completed:
        argv = tuple(str(value) for value in args)
        process = subprocess.run(
            argv,
            cwd=self.cwd,
            env=dict(env) if env is not None else None,
            input=input_text,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        result = Completed(argv, process.returncode, process.stdout, process.stderr)
        if check and process.returncode != 0:
            detail = (process.stderr or process.stdout).strip()
            raise RefreshError(
                f"command failed ({process.returncode}): {argv[0]} {argv[1] if len(argv) > 1 else ''}: {detail}"
            )
        return result


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def exact_sha(value: str, label: str) -> str:
    candidate = str(value or "").strip().lower()
    if HEX40.fullmatch(candidate) is None:
        raise RefreshError(f"{label} must be an exact 40-character revision")
    return candidate


def exact_digest(value: str, label: str) -> str:
    candidate = str(value or "").strip().lower()
    if HEX64.fullmatch(candidate) is None:
        raise RefreshError(f"{label} must be an exact SHA-256 digest")
    return candidate


def expected_branch(snapshot_digest: str) -> str:
    return f"{BRANCH_PREFIX}{exact_digest(snapshot_digest, 'snapshot digest')[:16]}"


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RefreshError(f"{label} is unavailable or invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RefreshError(f"{label} must be a JSON object")
    return payload


def validate_snapshot(
    path: Path,
    snapshot_digest: str,
    candidate_set: str,
) -> dict[str, Any]:
    expected_snapshot = exact_digest(snapshot_digest, "snapshot digest")
    expected_candidates = exact_digest(candidate_set, "candidate-set digest")
    payload = load_object(path, "Brain Frontier snapshot")
    if payload.get("schema") != SNAPSHOT_SCHEMA:
        raise RefreshError("Brain Frontier snapshot schema is not the reviewed v7 schema")
    observed_snapshot = payload.pop("snapshot_sha256", None)
    if observed_snapshot != expected_snapshot or sha256(canonical_bytes(payload)) != expected_snapshot:
        raise RefreshError("Brain Frontier snapshot digest does not bind the canonical payload")
    sources = payload.get("sources")
    second_brain = sources.get("second_brain") if isinstance(sources, Mapping) else None
    if (
        not isinstance(second_brain, Mapping)
        or second_brain.get("candidate_set_sha256") != expected_candidates
    ):
        raise RefreshError("Brain Frontier candidate-set digest does not match the proposal")
    if payload.get("selected_handle_count") != 72 or not isinstance(payload.get("handles"), list) or len(payload["handles"]) != 72:
        raise RefreshError("Brain Frontier proposal does not contain exactly 72 handles")
    authority = payload.get("authority")
    if not isinstance(authority, Mapping) or any(
        authority.get(name) != "NONE"
        for name in ("training", "promotion", "execution", "merge", "provider_mutation")
    ):
        raise RefreshError("Brain Frontier proposal carries authority outside review")
    return payload


def one_line(value: str) -> str:
    return re.sub(r"[\r\n]+", " ", str(value)).strip()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def append_outputs(path: Path | None, values: Mapping[str, str]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for key, value in values.items():
            if re.fullmatch(r"[a-z][a-z0-9_]*", key) is None:
                raise RefreshError(f"invalid GitHub output key: {key}")
            handle.write(f"{key}={one_line(value)}\n")


def git_text(runner: Runner, *args: str) -> str:
    return runner.run(("git", *args)).stdout.strip()


def current_main_sha(runner: Runner, base: str) -> str:
    result = runner.run(
        ("git", "ls-remote", "--exit-code", "origin", f"refs/heads/{base}")
    )
    fields = result.stdout.strip().split()
    if len(fields) != 2 or fields[1] != f"refs/heads/{base}":
        raise RefreshError("protected main did not resolve to exactly one remote ref")
    return exact_sha(fields[0], "protected main")


def require_exact_main(runner: Runner, source_sha: str, base: str) -> None:
    source = exact_sha(source_sha, "source revision")
    if git_text(runner, "rev-parse", "HEAD").lower() != source:
        raise RefreshError("checkout HEAD is not the materialized source revision")
    if current_main_sha(runner, base) != source:
        raise RefreshError("protected main moved; refusing a stale review transaction")


def permissions_preflight(runner: Runner, credential_kind: str) -> dict[str, Any]:
    """Check readable policy before any ref write; never edit repository policy."""
    if credential_kind not in {"github-token", "automation-token"}:
        raise RefreshError("unknown proposal credential kind")
    response = runner.run(
        ("gh", "api", f"repos/{REPOSITORY}/actions/permissions/workflow"),
        check=False,
    )
    policy = None
    if response.returncode == 0:
        try:
            policy = json.loads(response.stdout)
        except json.JSONDecodeError as exc:
            raise RefreshError("workflow permissions preflight returned invalid JSON") from exc
        if not isinstance(policy, dict) or type(policy.get("can_approve_pull_request_reviews")) is not bool:
            raise RefreshError("workflow permissions preflight returned incomplete policy")
    if credential_kind == "github-token":
        if policy is None:
            raise RefreshError(
                "GITHUB_TOKEN policy is UNAVAILABLE; a scoped BRAIN_FRONTIER_PR_TOKEN "
                "is required to propose without an unverified policy assumption"
            )
        if policy["can_approve_pull_request_reviews"] is not True:
            raise RefreshError(
                "repository policy disables GITHUB_TOKEN pull-request creation; "
                "configure BRAIN_FRONTIER_PR_TOKEN or explicitly enable the repository policy"
            )
    # External credentials have their own repository grants. The Actions bot policy
    # does not grant or deny them authority; actual branch and PR writes are read back.
    return {
        "credential_kind": credential_kind,
        "actions_policy_observed": policy is not None,
        "github_token_pr_creation_allowed": policy.get("can_approve_pull_request_reviews") if policy else None,
        "write_authority": "UNVERIFIED_UNTIL_WRITE_READBACK",
    }


def changed_paths(runner: Runner, left: str, right: str) -> set[str]:
    output = git_text(runner, "diff", "--name-only", f"{left}..{right}", "--")
    return {line.strip() for line in output.splitlines() if line.strip()}


def remote_branch_head(runner: Runner, branch: str) -> str | None:
    remote_ref = f"refs/remotes/origin/{branch}"
    fetch = runner.run(
        (
            "git",
            "fetch",
            "--no-tags",
            "origin",
            f"+refs/heads/{branch}:{remote_ref}",
        ),
        check=False,
    )
    if fetch.returncode != 0:
        lookup = runner.run(
            ("git", "ls-remote", "--exit-code", "origin", f"refs/heads/{branch}"),
            check=False,
        )
        if lookup.returncode == 2:
            return None
        detail = (fetch.stderr or lookup.stderr or fetch.stdout or lookup.stdout).strip()
        raise RefreshError(f"could not resolve review branch: {detail}")
    return exact_sha(git_text(runner, "rev-parse", remote_ref), "review branch head")


def commit_metadata(runner: Runner, revision: str) -> tuple[str, str, str]:
    raw = runner.run(
        ("git", "show", "-s", "--format=%ae%x00%s%x00%B", revision)
    ).stdout
    fields = raw.split("\x00", 2)
    if len(fields) != 3:
        raise RefreshError("review branch commit metadata is incomplete")
    return fields[0].strip(), fields[1].strip(), fields[2]


def snapshot_from_revision(runner: Runner, revision: str) -> dict[str, Any]:
    raw = runner.run(("git", "show", f"{revision}:{SNAPSHOT_PATH}")).stdout
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RefreshError("existing review branch snapshot is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RefreshError("existing review branch snapshot is not a JSON object")
    return payload


def validate_existing_branch(
    runner: Runner,
    remote_head: str,
    source_sha: str,
    snapshot_digest: str,
    candidate_set: str,
) -> None:
    merge_base = exact_sha(
        git_text(runner, "merge-base", remote_head, source_sha),
        "review branch merge base",
    )
    ancestor = runner.run(
        ("git", "merge-base", "--is-ancestor", merge_base, source_sha),
        check=False,
    )
    if ancestor.returncode != 0:
        raise RefreshError("review branch is not rooted in protected main history")
    if changed_paths(runner, merge_base, remote_head) != {SNAPSHOT_PATH}:
        raise RefreshError("existing review branch changes files outside the snapshot boundary")
    email, subject, body = commit_metadata(runner, remote_head)
    if email not in AUTOMATION_AUTHORS or not subject.startswith(
        "chore(holographic): refresh Brain Frontier "
    ):
        raise RefreshError("existing review branch is not owned by the refresh automation")
    expected_source_trailer = f"Brain-Frontier-Source-SHA: {source_sha}"
    if "Brain-Frontier-Source-SHA:" in body and expected_source_trailer not in body:
        # A branch may be advanced from an older main by a later exact-tree commit.
        trailer_source = re.findall(r"Brain-Frontier-Source-SHA: ([0-9a-f]{40})", body)
        if not trailer_source or runner.run(
            ("git", "merge-base", "--is-ancestor", trailer_source[-1], source_sha),
            check=False,
        ).returncode != 0:
            raise RefreshError("existing review branch source trailer is not protected-main ancestry")
    payload = snapshot_from_revision(runner, remote_head)
    observed = payload.pop("snapshot_sha256", None)
    if observed != snapshot_digest or sha256(canonical_bytes(payload)) != snapshot_digest:
        raise RefreshError("existing review branch does not carry the content-addressed snapshot")
    sources = payload.get("sources")
    second_brain = sources.get("second_brain") if isinstance(sources, Mapping) else None
    if not isinstance(second_brain, Mapping) or second_brain.get(
        "candidate_set_sha256"
    ) != candidate_set:
        raise RefreshError("existing review branch candidate-set binding is invalid")


def prepare_target_tree(runner: Runner) -> str:
    unstaged = {
        line.strip()
        for line in git_text(runner, "diff", "--name-only", "HEAD", "--").splitlines()
        if line.strip()
    }
    staged = {
        line.strip()
        for line in git_text(runner, "diff", "--cached", "--name-only", "HEAD", "--").splitlines()
        if line.strip()
    }
    if unstaged | staged != {SNAPSHOT_PATH}:
        raise RefreshError("working tree changes are not exactly the materialized snapshot")
    runner.run(("git", "add", "--", SNAPSHOT_PATH))
    cached = {
        line.strip()
        for line in git_text(runner, "diff", "--cached", "--name-only", "HEAD", "--").splitlines()
        if line.strip()
    }
    if cached != {SNAPSHOT_PATH}:
        raise RefreshError("staged review tree is not exactly the materialized snapshot")
    return exact_sha(git_text(runner, "write-tree"), "review tree")


def commit_message(
    source_sha: str,
    snapshot_digest: str,
    candidate_set: str,
    run_url: str,
) -> str:
    return (
        f"chore(holographic): refresh Brain Frontier {snapshot_digest[:16]}\n\n"
        f"Brain-Frontier-Source-SHA: {source_sha}\n"
        f"Brain-Frontier-Snapshot-SHA256: {snapshot_digest}\n"
        f"Brain-Frontier-Candidate-Set-SHA256: {candidate_set}\n"
        f"Brain-Frontier-Run: {run_url}\n"
        "Signed-off-by: github-actions[bot] "
        "<41898282+github-actions[bot]@users.noreply.github.com>\n"
    )


def create_commit(
    runner: Runner,
    tree: str,
    parent: str,
    message: str,
    source_parent: str | None = None,
) -> str:
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_AUTHOR_NAME": "github-actions[bot]",
            "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
            "GIT_COMMITTER_NAME": "github-actions[bot]",
            "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
        }
    )
    parents = ("-p", parent)
    if source_parent is not None and source_parent != parent:
        parents += ("-p", source_parent)
    result = runner.run(
        ("git", "commit-tree", tree, *parents, "-F", "-"),
        input_text=message,
        env=environment,
    )
    return exact_sha(result.stdout.strip(), "review commit")


def ensure_review_branch(
    runner: Runner,
    branch: str,
    tree: str,
    source_sha: str,
    snapshot_digest: str,
    candidate_set: str,
    run_url: str,
) -> tuple[str, str]:
    message = commit_message(source_sha, snapshot_digest, candidate_set, run_url)
    for attempt in range(2):
        remote_head = remote_branch_head(runner, branch)
        if remote_head is not None:
            validate_existing_branch(
                runner,
                remote_head,
                source_sha,
                snapshot_digest,
                candidate_set,
            )
            if git_text(runner, "rev-parse", f"{remote_head}^{{tree}}").lower() == tree:
                return remote_head, "REUSED_BRANCH"
            parent = remote_head
            branch_state = "ADVANCED_BRANCH"
        else:
            parent = source_sha
            branch_state = "CREATED_BRANCH"

        require_exact_main(runner, source_sha, BASE_BRANCH)
        # Keep both histories so a retry compares the snapshot against current main,
        # without force-pushing an older automation branch or reverting main files.
        commit = create_commit(runner, tree, parent, message, source_sha)
        push = runner.run(
            ("git", "push", "--porcelain", "origin", f"{commit}:refs/heads/{branch}"),
            check=False,
        )
        if push.returncode == 0:
            observed = remote_branch_head(runner, branch)
            if observed != commit:
                raise RefreshError("review branch readback does not match the pushed commit")
            if git_text(runner, "rev-parse", f"{observed}^{{tree}}").lower() != tree:
                raise RefreshError("review branch readback tree differs from the reviewed tree")
            return commit, branch_state
        if attempt == 1:
            detail = (push.stderr or push.stdout).strip()
            raise RefreshError(f"review branch push lost its non-force race: {detail}")
    raise AssertionError("unreachable")


def parse_prs(raw: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RefreshError("GitHub pull-request listing returned invalid JSON") from exc
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise RefreshError("GitHub pull-request listing is not an array of objects")
    return payload


def choose_pr_action(
    pull_requests: Sequence[Mapping[str, Any]],
    branch: str,
    base: str,
    head_sha: str,
) -> tuple[str, Mapping[str, Any] | None]:
    candidates = [
        item
        for item in pull_requests
        if item.get("headRefName") == branch and item.get("baseRefName") == base
    ]
    opened = [item for item in candidates if item.get("state") == "OPEN"]
    if len(opened) > 1:
        raise RefreshError("multiple open review PRs exist for one content-addressed branch")
    if opened:
        if opened[0].get("headRefOid") != head_sha:
            raise RefreshError("open review PR is not bound to the observed branch head")
        return "existing", opened[0]
    closed = [
        item
        for item in candidates
        if item.get("state") == "CLOSED" and item.get("headRefOid") == head_sha
    ]
    if closed:
        return "reopen", closed[0]
    return "create", None


def review_body(snapshot_digest: str, candidate_set: str, source_sha: str) -> str:
    return f"""## Source-bound handle refresh

This automated proposal updates only the deterministic metadata snapshot consumed by the existing A11oy Holographic v7 Brain Frontier instrument.

- Protected-main source: `{source_sha}`
- Snapshot: `{snapshot_digest}`
- Second Brain candidate set: `{candidate_set}`
- Public content access: `HANDLES_ONLY`
- Training authority: `NONE`
- Promotion authority: `NONE`
- Execution authority: `NONE`
- Provider mutation: `NONE`
- Human review required: `true`

The workflow validated fixed-source digests and focused tests, then read back the exact branch head. It cannot force-push, approve, merge, or mutate a provider.
"""


def validate_pr(payload: Mapping[str, Any], branch: str, head_sha: str) -> str:
    url = str(payload.get("url") or "")
    if (
        payload.get("state") != "OPEN"
        or payload.get("baseRefName") != BASE_BRANCH
        or payload.get("headRefName") != branch
        or payload.get("headRefOid") != head_sha
        or PR_URL.fullmatch(url) is None
    ):
        raise RefreshError("review PR readback is not open at the exact branch head")
    return url


def ensure_review_pr(
    runner: Runner,
    branch: str,
    head_sha: str,
    snapshot_digest: str,
    candidate_set: str,
    source_sha: str,
) -> tuple[str, str]:
    listed = runner.run(
        (
            "gh",
            "pr",
            "list",
            "--repo",
            REPOSITORY,
            "--state",
            "all",
            "--head",
            branch,
            "--limit",
            "100",
            "--json",
            "number,state,url,headRefName,headRefOid,baseRefName,isDraft",
        )
    )
    action, selected = choose_pr_action(
        parse_prs(listed.stdout), branch, BASE_BRANCH, head_sha
    )
    if action == "existing":
        assert selected is not None
        return "EXISTING_REVIEW_PR", validate_pr(selected, branch, head_sha)

    if action == "reopen":
        assert selected is not None
        number = str(selected.get("number") or "")
        if re.fullmatch(r"[1-9][0-9]*", number) is None:
            raise RefreshError("closed review PR lacks a valid number")
        runner.run(("gh", "pr", "reopen", number, "--repo", REPOSITORY))
        state = "RECOVERED_REVIEW_PR"
        reference = number
    else:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix="brain-frontier-v7-",
            suffix=".md",
            delete=False,
        ) as handle:
            handle.write(review_body(snapshot_digest, candidate_set, source_sha))
            body_path = Path(handle.name)
        try:
            created = runner.run(
                (
                    "gh",
                    "pr",
                    "create",
                    "--repo",
                    REPOSITORY,
                    "--base",
                    BASE_BRANCH,
                    "--head",
                    branch,
                    "--title",
                    f"chore(holographic): review Brain Frontier {snapshot_digest[:16]}",
                    "--body-file",
                    str(body_path),
                )
            )
        finally:
            body_path.unlink(missing_ok=True)
        url = created.stdout.strip()
        if PR_URL.fullmatch(url) is None:
            raise RefreshError("GitHub did not return the canonical review PR URL")
        state = "NEW_REVIEW_PR"
        reference = url

    viewed = runner.run(
        (
            "gh",
            "pr",
            "view",
            reference,
            "--repo",
            REPOSITORY,
            "--json",
            "number,state,url,headRefName,headRefOid,baseRefName,isDraft",
        )
    )
    try:
        payload = json.loads(viewed.stdout)
    except json.JSONDecodeError as exc:
        raise RefreshError("review PR readback returned invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise RefreshError("review PR readback is not a JSON object")
    return state, validate_pr(payload, branch, head_sha)


def reconcile(args: argparse.Namespace) -> int:
    evidence_path = Path(args.evidence)
    output_path = Path(args.github_output) if args.github_output else None
    branch = ""
    try:
        if args.repository != REPOSITORY or args.base != BASE_BRANCH:
            raise RefreshError("refresh controller is locked to szl-holdings/a11oy protected main")
        source_sha = exact_sha(args.source_sha, "source revision")
        snapshot_digest = exact_digest(args.snapshot_digest, "snapshot digest")
        candidate_set = exact_digest(args.candidate_set, "candidate-set digest")
        branch = expected_branch(snapshot_digest)
        validate_snapshot(Path(args.snapshot), snapshot_digest, candidate_set)
        runner = Runner()
        require_exact_main(runner, source_sha, BASE_BRANCH)
        preflight = permissions_preflight(runner, args.credential_kind)
        tree = prepare_target_tree(runner)
        run_url = one_line(args.run_url)
        if not run_url.startswith("https://github.com/szl-holdings/a11oy/actions/runs/"):
            raise RefreshError("run URL is not the canonical repository Actions URL")
        head_sha, branch_state = ensure_review_branch(
            runner,
            branch,
            tree,
            source_sha,
            snapshot_digest,
            candidate_set,
            run_url,
        )
        require_exact_main(runner, source_sha, BASE_BRANCH)
        state, url = ensure_review_pr(
            runner,
            branch,
            head_sha,
            snapshot_digest,
            candidate_set,
            source_sha,
        )
        require_exact_main(runner, source_sha, BASE_BRANCH)
        evidence = {
            "schema": "szl.a11oy.brain-frontier-v7-proposal/v1",
            "terminal": True,
            "state": state,
            "url": url,
            "branch": branch,
            "branch_state": branch_state,
            "head_sha": head_sha,
            "source_sha": source_sha,
            "snapshot_sha256": snapshot_digest,
            "candidate_set_sha256": candidate_set,
            "permissions_preflight": preflight,
            "signature_state": "UNSIGNED",
        }
        write_json(evidence_path, evidence)
        append_outputs(
            output_path,
            {key: str(evidence[key]) for key in ("state", "url", "branch", "head_sha")},
        )
        print(json.dumps(evidence, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        failure = {
            "schema": "szl.a11oy.brain-frontier-v7-proposal/v1",
            "terminal": False,
            "state": "FAILED_CLOSED",
            "url": None,
            "branch": branch or None,
            "head_sha": None,
            "failure": f"{type(exc).__name__}: {one_line(str(exc))}",
        }
        write_json(evidence_path, failure)
        append_outputs(
            output_path,
            {"state": "FAILED_CLOSED", "url": "", "branch": branch, "head_sha": ""},
        )
        print(f"::error::{failure['failure']}", file=sys.stderr)
        return 1


def parse_bool(value: str) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def optional_object(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    return load_object(path, "proposal evidence")


def build_receipt(args: argparse.Namespace) -> dict[str, Any]:
    changed = parse_bool(args.changed)
    proposal = optional_object(Path(args.proposal) if args.proposal else None)
    source_sha = str(args.source_sha or "").strip().lower()
    snapshot_digest = str(args.snapshot_digest or "").strip().lower()
    candidate_set = str(args.candidate_set or "").strip().lower()
    failures: list[str] = []
    if args.repository != REPOSITORY:
        failures.append("unexpected_repository")
    if args.ref != "refs/heads/main":
        failures.append("workflow_not_owned_by_protected_main")
    if args.materialize_result != "success":
        failures.append("materialization_not_successful")
    if changed is None:
        failures.append("changed_state_unknown")
    if HEX40.fullmatch(source_sha) is None:
        failures.append("source_revision_invalid")
    if HEX64.fullmatch(snapshot_digest) is None:
        failures.append("snapshot_digest_invalid")
    if HEX64.fullmatch(candidate_set) is None:
        failures.append("candidate_set_digest_invalid")

    proposal_record: dict[str, Any] = {
        "state": "NO_PROPOSAL",
        "url": None,
        "branch": None,
        "head_sha": None,
    }
    if proposal is not None:
        for name in proposal_record:
            proposal_record[name] = proposal.get(name)

    if changed is True:
        expected = expected_branch(snapshot_digest) if HEX64.fullmatch(snapshot_digest) else None
        if args.proposal_result != "success":
            failures.append("proposal_job_not_successful")
        if proposal is None or proposal.get("terminal") is not True:
            failures.append("proposal_evidence_not_terminal")
        if proposal_record["state"] not in SUCCESSFUL_PROPOSAL_STATES:
            failures.append("proposal_state_not_reviewable")
        if PR_URL.fullmatch(str(proposal_record["url"] or "")) is None:
            failures.append("proposal_url_missing_or_invalid")
        if proposal_record["branch"] != expected:
            failures.append("proposal_branch_not_content_addressed")
        if HEX40.fullmatch(str(proposal_record["head_sha"] or "")) is None:
            failures.append("proposal_head_invalid")
        if proposal is not None and any(
            proposal.get(key) != expected_value
            for key, expected_value in (
                ("source_sha", source_sha),
                ("snapshot_sha256", snapshot_digest),
                ("candidate_set_sha256", candidate_set),
            )
        ):
            failures.append("proposal_binding_mismatch")
    elif changed is False:
        if args.proposal_result not in {"skipped", "success"}:
            failures.append("unexpected_proposal_job_result")
        if proposal is not None and proposal.get("state") != "NO_PROPOSAL":
            failures.append("unchanged_run_has_proposal")

    if failures:
        outcome = "FAILED_CLOSED"
        terminal = False
    elif changed:
        outcome = "REVIEW_PR_OPEN"
        terminal = True
    else:
        outcome = "NO_CHANGE"
        terminal = True

    try:
        run_attempt = int(args.run_attempt)
    except (TypeError, ValueError):
        run_attempt = 0
        failures.append("run_attempt_invalid")
        outcome = "FAILED_CLOSED"
        terminal = False
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "signature_state": "UNSIGNED",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "terminal": terminal,
        "outcome": outcome,
        "failures": sorted(set(failures)),
        "run": {
            "id": str(args.run_id),
            "attempt": run_attempt,
            "url": str(args.run_url),
            "event": str(args.event_name),
            "ref": str(args.ref),
        },
        "source": {
            "repository": str(args.repository),
            "revision": source_sha or None,
            "branch": BASE_BRANCH,
        },
        "materialization": {
            "job_result": str(args.materialize_result),
            "changed": changed,
            "snapshot_sha256": snapshot_digest or None,
            "candidate_set_sha256": candidate_set or None,
        },
        "proposal_job_result": str(args.proposal_result),
        "proposal": proposal_record,
        "authority": {
            "content_access": "HANDLES_ONLY",
            "training": "NONE",
            "promotion": "NONE",
            "execution": "NONE",
            "merge": "NONE",
            "provider_mutation": "NONE",
        },
    }
    receipt["receipt_sha256"] = sha256(canonical_bytes(receipt))
    return receipt


def receipt_command(args: argparse.Namespace) -> int:
    receipt = build_receipt(args)
    write_json(Path(args.output), receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


def verify_receipt(path: Path, require_terminal: bool = True) -> dict[str, Any]:
    receipt = load_object(path, "refresh receipt")
    observed = receipt.pop("receipt_sha256", None)
    if HEX64.fullmatch(str(observed or "")) is None or sha256(
        canonical_bytes(receipt)
    ) != observed:
        raise RefreshError("refresh receipt digest is invalid")
    if require_terminal and (
        receipt.get("terminal") is not True
        or receipt.get("outcome") not in {"NO_CHANGE", "REVIEW_PR_OPEN"}
    ):
        failures = receipt.get("failures")
        raise RefreshError(f"refresh transaction failed closed: {failures}")
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("signature_state") != "UNSIGNED":
        raise RefreshError("refresh receipt schema or signature classification is invalid")
    if require_terminal:
        source = receipt.get("source")
        materialization = receipt.get("materialization")
        proposal = receipt.get("proposal")
        run = receipt.get("run")
        if not all(isinstance(record, dict) for record in (source, materialization, proposal, run)):
            raise RefreshError("refresh receipt lacks structured source and outcome evidence")
        if (
            source.get("repository") != REPOSITORY
            or source.get("branch") != BASE_BRANCH
            or HEX40.fullmatch(str(source.get("revision") or "")) is None
            or run.get("ref") != "refs/heads/main"
            or receipt.get("failures") != []
            or materialization.get("job_result") != "success"
            or HEX64.fullmatch(str(materialization.get("snapshot_sha256") or "")) is None
            or HEX64.fullmatch(str(materialization.get("candidate_set_sha256") or "")) is None
        ):
            raise RefreshError("refresh receipt source or materialization binding is invalid")
        if receipt.get("authority") != {
            "content_access": "HANDLES_ONLY", "training": "NONE", "promotion": "NONE",
            "execution": "NONE", "merge": "NONE", "provider_mutation": "NONE",
        }:
            raise RefreshError("refresh receipt authority boundary is invalid")
        changed = materialization.get("changed")
        if changed is True:
            if (
                receipt.get("outcome") != "REVIEW_PR_OPEN"
                or receipt.get("proposal_job_result") != "success"
                or proposal.get("state") not in SUCCESSFUL_PROPOSAL_STATES
                or PR_URL.fullmatch(str(proposal.get("url") or "")) is None
                or HEX40.fullmatch(str(proposal.get("head_sha") or "")) is None
                or proposal.get("branch") != expected_branch(materialization["snapshot_sha256"])
            ):
                raise RefreshError("refresh receipt lacks a bound review PR")
        elif changed is False:
            if (
                receipt.get("outcome") != "NO_CHANGE"
                or receipt.get("proposal_job_result") not in {"success", "skipped"}
                or proposal != {"state": "NO_PROPOSAL", "url": None, "branch": None, "head_sha": None}
            ):
                raise RefreshError("refresh receipt no-change outcome is inconsistent")
        else:
            raise RefreshError("refresh receipt change state is unknown")
    return receipt


def verify_receipt_command(args: argparse.Namespace) -> int:
    try:
        verify_receipt(Path(args.receipt), require_terminal=True)
    except RefreshError as exc:
        print(f"::error::{one_line(str(exc))}", file=sys.stderr)
        return 1
    print("Brain Frontier refresh receipt is terminal and digest-valid.")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    reconcile_parser = commands.add_parser("reconcile")
    reconcile_parser.add_argument("--repository", required=True)
    reconcile_parser.add_argument("--base", default=BASE_BRANCH)
    reconcile_parser.add_argument("--source-sha", required=True)
    reconcile_parser.add_argument("--snapshot", default=SNAPSHOT_PATH)
    reconcile_parser.add_argument("--snapshot-digest", required=True)
    reconcile_parser.add_argument("--candidate-set", required=True)
    reconcile_parser.add_argument("--run-url", required=True)
    reconcile_parser.add_argument("--evidence", required=True)
    reconcile_parser.add_argument("--github-output")
    reconcile_parser.add_argument("--credential-kind", choices=("github-token", "automation-token"), default="github-token")
    reconcile_parser.set_defaults(handler=reconcile)

    receipt_parser = commands.add_parser("receipt")
    receipt_parser.add_argument("--output", required=True)
    receipt_parser.add_argument("--proposal")
    receipt_parser.add_argument("--repository", required=True)
    receipt_parser.add_argument("--ref", required=True)
    receipt_parser.add_argument("--event-name", required=True)
    receipt_parser.add_argument("--run-id", required=True)
    receipt_parser.add_argument("--run-attempt", required=True)
    receipt_parser.add_argument("--run-url", required=True)
    receipt_parser.add_argument("--materialize-result", required=True)
    receipt_parser.add_argument("--proposal-result", required=True)
    receipt_parser.add_argument("--changed", default="")
    receipt_parser.add_argument("--source-sha", default="")
    receipt_parser.add_argument("--snapshot-digest", default="")
    receipt_parser.add_argument("--candidate-set", default="")
    receipt_parser.set_defaults(handler=receipt_command)

    verify_parser = commands.add_parser("verify-receipt")
    verify_parser.add_argument("--receipt", required=True)
    verify_parser.set_defaults(handler=verify_receipt_command)
    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
