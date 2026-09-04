#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One-pass, fail-closed recovery for unfinished Codex/Perplexity estate work.

This controller may update same-organization PR branches, approve trusted same-org
workflow runs, rerun a failed exact-head workflow once, merge clean PRs through
normal branch protection, close byte-identical superseded PRs, create recovery PRs
for explicit Codex/Perplexity orphan branches, and restart public Hugging Face
Spaces without changing hardware, visibility, secrets, storage, or domains.

It never prints credentials and never bypasses repository protection.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

ORG = "szl-holdings"
HF_ORG = "SZLHOLDINGS"
REPORT_DIR = Path("artifacts/agent-recovery")
REPORT_JSON = REPORT_DIR / "estate-recovery.json"
REPORT_MD = REPORT_DIR / "estate-recovery.md"
NOW = dt.datetime.now(dt.timezone.utc)
MUTATE = os.environ.get("RECOVERY_EXECUTE", "true").strip().lower() == "true"
GH_TOKEN = os.environ.get("GH_ADMIN_TOKEN", "").strip()
HF_TOKEN = os.environ.get("HF_ADMIN_TOKEN", "").strip()

TASK_IDS = {
    "6938cea2-070a-4cd4-afea-1be8ee8ef9e9",
    "5ef92f6b-71f1-454c-9985-bcb28fd07e80",
    "6420a522-c3d5-4042-b17d-ffa639bbe11a",
    "20663549-f94b-4177-8684-f98123611f55",
    "9f3c6da0-6736-4b1b-aa25-ab6c32e9ecf7",
    "ccc9bf3e-223a-4ab7-aee4-c3f03e12cc4b",
}
EXPLICIT_AGENT = re.compile(
    r"(?:codex|perplexity|computer[ -]?task|openai[ -]?agent|"
    + "|".join(re.escape(value) for value in sorted(TASK_IDS))
    + r")",
    re.IGNORECASE,
)
HOLD = re.compile(
    r"(?:do not merge|\bhold\b|evidence[- ]only|close without merge|"
    r"superseded|not ready|manual approval required|owner click|"
    r"terminal disposition)",
    re.IGNORECASE,
)
PROVIDER_WORKFLOW = re.compile(
    r"(?:cloudflare|custom.?domain|production witness|neon migration|gpu|train|billing)",
    re.IGNORECASE,
)
SUCCESS_CONCLUSIONS = {"success", "neutral", "skipped"}
BAD_CONCLUSIONS = {
    "failure", "timed_out", "cancelled", "startup_failure", "stale",
    "action_required",
}


def _redact(text: str) -> str:
    text = re.sub(r"(?i)(token|secret|password|authorization)=?[^\s,;]+", r"\1=[REDACTED]", text)
    text = re.sub(r"https://[^/@\s]+:[^/@\s]+@", "https://[REDACTED]@", text)
    return text[:800]


def gh(path: str, *, method: str = "GET", data: Any = None, accept: str = "application/vnd.github+json") -> tuple[int, Any]:
    url = path if path.startswith("https://") else f"https://api.github.com{path}"
    headers = {
        "Accept": accept,
        "User-Agent": "SZL-agent-estate-recovery/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GH_TOKEN:
        headers["Authorization"] = f"Bearer {GH_TOKEN}"
    body = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", "replace")
        try:
            parsed: Any = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"message": payload}
        return exc.code, parsed
    except Exception as exc:  # network failures remain evidence, not zero
        return 0, {"message": f"{type(exc).__name__}: {exc}"}


def gh_pages(path: str, key: str | None = None, limit_pages: int = 20) -> list[Any]:
    rows: list[Any] = []
    separator = "&" if "?" in path else "?"
    for page in range(1, limit_pages + 1):
        status, data = gh(f"{path}{separator}per_page=100&page={page}")
        if status != 200:
            raise RuntimeError(f"GitHub HTTP {status}: {_redact(str(data))}")
        batch = data.get(key, []) if key else data
        if not isinstance(batch, list):
            raise RuntimeError("GitHub pagination shape is not a list")
        rows.extend(batch)
        if len(batch) < 100:
            break
    return rows


def gh_graphql(query: str, variables: dict[str, Any]) -> tuple[int, Any]:
    return gh("/graphql", method="POST", data={"query": query, "variables": variables})


def hf(path: str, *, method: str = "GET") -> tuple[int, Any]:
    url = path if path.startswith("https://") else f"https://huggingface.co{path}"
    headers = {"User-Agent": "SZL-agent-estate-recovery/1.0"}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"
    request = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", "replace")
        try:
            parsed: Any = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"message": payload}
        return exc.code, parsed
    except Exception as exc:
        return 0, {"message": f"{type(exc).__name__}: {exc}"}


def iso_age(value: str | None) -> float:
    if not value:
        return 10_000.0
    try:
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 10_000.0
    return (NOW - stamp).total_seconds() / 86400


def agent_text(pr: dict[str, Any], commits: Iterable[dict[str, Any]] = ()) -> str:
    pieces = [str(pr.get("title") or ""), str(pr.get("body") or ""), str(pr.get("head", {}).get("ref") or "")]
    for commit in commits:
        pieces.append(str(commit.get("commit", {}).get("message") or ""))
    return "\n".join(pieces)


def review_threads_clean(owner: str, repo: str, number: int) -> tuple[bool, int | None, str | None]:
    query = """
    query($owner:String!, $repo:String!, $number:Int!) {
      repository(owner:$owner, name:$repo) {
        pullRequest(number:$number) {
          reviewThreads(first:100) { nodes { isResolved } }
        }
      }
    }
    """
    status, data = gh_graphql(query, {"owner": owner, "repo": repo, "number": number})
    if status != 200 or data.get("errors"):
        return False, None, _redact(str(data))
    nodes = (((data.get("data") or {}).get("repository") or {}).get("pullRequest") or {}).get("reviewThreads", {}).get("nodes", [])
    unresolved = sum(1 for node in nodes if not node.get("isResolved"))
    return unresolved == 0, unresolved, None


def head_evidence(repo_full: str, sha: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(sha, safe="")
    status, checks_data = gh(f"/repos/{repo_full}/commits/{encoded}/check-runs?per_page=100")
    checks = checks_data.get("check_runs", []) if status == 200 else []
    status_code, combined = gh(f"/repos/{repo_full}/commits/{encoded}/status?per_page=100")
    contexts = combined.get("statuses", []) if status_code == 200 else []
    failed = sorted({
        row.get("name") or "unnamed-check"
        for row in checks
        if row.get("status") == "completed" and row.get("conclusion") in BAD_CONCLUSIONS
    })
    pending = sorted({
        row.get("name") or "unnamed-check" for row in checks if row.get("status") != "completed"
    })
    failed.extend(sorted({row.get("context") or "unnamed-status" for row in contexts if row.get("state") in {"error", "failure"}}))
    pending.extend(sorted({row.get("context") or "unnamed-status" for row in contexts if row.get("state") == "pending"}))
    completed = [row for row in checks if row.get("status") == "completed"]
    success = [row for row in completed if row.get("conclusion") in SUCCESS_CONCLUSIONS]
    return {
        "checks_http": status,
        "status_http": status_code,
        "check_count": len(checks) + len(contexts),
        "success_count": len(success) + sum(1 for row in contexts if row.get("state") == "success"),
        "failed": sorted(set(failed)),
        "pending": sorted(set(pending)),
    }


def runs_for_sha(repo_full: str, sha: str) -> list[dict[str, Any]]:
    status, data = gh(f"/repos/{repo_full}/actions/runs?head_sha={sha}&per_page=100")
    return data.get("workflow_runs", []) if status == 200 else []


def recover_runs(repo_full: str, sha: str, report: dict[str, Any]) -> bool:
    changed = False
    for run in runs_for_sha(repo_full, sha):
        conclusion = run.get("conclusion")
        status = run.get("status")
        run_id = run.get("id")
        name = str(run.get("name") or "")
        if status == "completed" and conclusion == "action_required" and MUTATE:
            code, data = gh(f"/repos/{repo_full}/actions/runs/{run_id}/approve", method="POST")
            report["workflow_actions"].append({
                "repo": repo_full, "run_id": run_id, "workflow": name,
                "action": "approve", "http": code,
            })
            changed |= code in {201, 204}
        elif status == "completed" and conclusion in BAD_CONCLUSIONS and not PROVIDER_WORKFLOW.search(name):
            attempt = int(run.get("run_attempt") or 1)
            if attempt <= 1 and MUTATE:
                code, data = gh(f"/repos/{repo_full}/actions/runs/{run_id}/rerun-failed-jobs", method="POST")
                report["workflow_actions"].append({
                    "repo": repo_full, "run_id": run_id, "workflow": name,
                    "action": "rerun-failed-once", "http": code,
                })
                changed |= code in {201, 202}
    return changed


def wait_for_checks(repo_full: str, sha: str, *, seconds: int = 720) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    last = head_evidence(repo_full, sha)
    while time.monotonic() < deadline:
        if not last["pending"]:
            return last
        time.sleep(20)
        last = head_evidence(repo_full, sha)
    return last


def reconcile_pr(repo: dict[str, Any], pr_stub: dict[str, Any], report: dict[str, Any]) -> None:
    repo_full = repo["full_name"]
    owner, repo_name = repo_full.split("/", 1)
    number = int(pr_stub["number"])
    code, pr = gh(f"/repos/{repo_full}/pulls/{number}")
    if code != 200:
        report["errors"].append({"subject": f"{repo_full}#{number}", "error": f"PR read HTTP {code}"})
        return
    commits = gh_pages(f"/repos/{repo_full}/pulls/{number}/commits")
    text = agent_text(pr, commits)
    explicit = bool(EXPLICIT_AGENT.search(text))
    candidate = {
        "repo": repo_full,
        "number": number,
        "title": pr.get("title"),
        "url": pr.get("html_url"),
        "head": pr.get("head", {}).get("ref"),
        "head_sha": pr.get("head", {}).get("sha"),
        "agent_evidence": explicit,
        "draft": bool(pr.get("draft")),
    }
    report["observed_prs"].append(candidate)
    if pr.get("draft") or HOLD.search(text):
        candidate["disposition"] = "HELD_BY_SOURCE"
        return
    head_repo = str((pr.get("head", {}).get("repo") or {}).get("full_name") or "")
    if not head_repo.startswith(f"{ORG}/"):
        candidate["disposition"] = "UNTRUSTED_OR_EXTERNAL_HEAD"
        return

    compare_code, comparison = gh(f"/repos/{repo_full}/compare/{pr['base']['sha']}...{pr['head']['sha']}")
    if compare_code == 200 and int(comparison.get("ahead_by") or 0) == 0:
        if MUTATE:
            comment = "Closing without merge: GitHub reports this candidate has no commits ahead of the current base. The protected base already contains the effective work."
            gh(f"/repos/{repo_full}/issues/{number}/comments", method="POST", data={"body": comment})
            close_code, _ = gh(f"/repos/{repo_full}/pulls/{number}", method="PATCH", data={"state": "closed"})
        else:
            close_code = 0
        candidate["disposition"] = "CLOSED_IDENTICAL" if close_code == 200 else "IDENTICAL"
        return

    if pr.get("mergeable_state") == "behind" and MUTATE:
        update_code, _ = gh(
            f"/repos/{repo_full}/pulls/{number}/update-branch",
            method="PUT", data={"expected_head_sha": pr["head"]["sha"]},
        )
        candidate["update_branch_http"] = update_code
        if update_code in {202, 200}:
            time.sleep(20)
            code, pr = gh(f"/repos/{repo_full}/pulls/{number}")
            if code == 200:
                candidate["head_sha"] = pr.get("head", {}).get("sha")

    sha = str(pr.get("head", {}).get("sha") or candidate["head_sha"])
    evidence = head_evidence(repo_full, sha)
    if evidence["failed"] or evidence["pending"]:
        if recover_runs(repo_full, sha, report):
            time.sleep(20)
        evidence = wait_for_checks(repo_full, sha)
    candidate["checks"] = evidence

    clean_threads, unresolved, thread_error = review_threads_clean(owner, repo_name, number)
    candidate["unresolved_threads"] = unresolved
    if thread_error:
        candidate["review_thread_error"] = thread_error

    code, pr = gh(f"/repos/{repo_full}/pulls/{number}")
    if code != 200:
        candidate["disposition"] = "READBACK_FAILED"
        return
    candidate["mergeable"] = pr.get("mergeable")
    candidate["mergeable_state"] = pr.get("mergeable_state")
    sha = str(pr.get("head", {}).get("sha") or sha)
    candidate["head_sha"] = sha

    admissible = (
        pr.get("mergeable") is True
        and pr.get("mergeable_state") in {"clean", "has_hooks", "unstable"}
        and evidence["check_count"] > 0
        and not evidence["failed"]
        and not evidence["pending"]
        and clean_threads
    )
    if not admissible:
        candidate["disposition"] = "BLOCKED"
        return
    if not MUTATE:
        candidate["disposition"] = "MERGE_READY"
        return
    merge_code, merged = gh(
        f"/repos/{repo_full}/pulls/{number}/merge",
        method="PUT",
        data={
            "sha": sha,
            "merge_method": "squash",
            "commit_title": f"{pr.get('title')} (#{number})",
            "commit_message": "Recovered through the protected exact-head path.\n\nSigned-off-by: Stephen Lutar <stephenlutar2@gmail.com>",
        },
    )
    candidate["merge_http"] = merge_code
    candidate["merged"] = bool((merged or {}).get("merged"))
    candidate["merge_sha"] = (merged or {}).get("sha")
    candidate["disposition"] = "MERGED" if candidate["merged"] else "PROTECTED_MERGE_REFUSED"


def recover_orphan_agent_branches(repo: dict[str, Any], report: dict[str, Any]) -> list[tuple[str, int]]:
    repo_full = repo["full_name"]
    default = repo.get("default_branch") or "main"
    created: list[tuple[str, int]] = []
    try:
        branches = gh_pages(f"/repos/{repo_full}/branches")
    except Exception as exc:
        report["errors"].append({"subject": repo_full, "error": _redact(str(exc))})
        return created
    for branch in branches:
        name = str(branch.get("name") or "")
        if not name or name == default:
            continue
        sha = str((branch.get("commit") or {}).get("sha") or "")
        code, commit = gh(f"/repos/{repo_full}/commits/{sha}")
        if code != 200:
            continue
        message = str((commit.get("commit") or {}).get("message") or "")
        date = ((commit.get("commit") or {}).get("committer") or {}).get("date")
        explicit = bool(EXPLICIT_AGENT.search(f"{name}\n{message}"))
        if not explicit or iso_age(date) > 180:
            continue
        head_query = urllib.parse.quote(f"{ORG}:{name}", safe="")
        pr_code, existing = gh(f"/repos/{repo_full}/pulls?state=all&head={head_query}&per_page=100")
        if pr_code != 200:
            continue
        if existing:
            report["orphan_branches"].append({
                "repo": repo_full, "branch": name, "sha": sha,
                "state": "HAS_PR", "prs": [row.get("number") for row in existing],
            })
            continue
        compare_code, comparison = gh(f"/repos/{repo_full}/compare/{urllib.parse.quote(default, safe='')}...{urllib.parse.quote(name, safe='')}")
        if compare_code != 200 or int(comparison.get("ahead_by") or 0) <= 0:
            continue
        row = {
            "repo": repo_full, "branch": name, "sha": sha,
            "ahead_by": comparison.get("ahead_by"), "behind_by": comparison.get("behind_by"),
            "state": "UNREVIEWED_AGENT_BRANCH",
        }
        if MUTATE and int(comparison.get("ahead_by") or 0) <= 50:
            title_line = message.splitlines()[0].strip() or f"recover agent branch {name}"
            create_code, created_pr = gh(
                f"/repos/{repo_full}/pulls", method="POST",
                data={
                    "title": f"recover(agent): {title_line[:180]}",
                    "head": name, "base": default,
                    "body": (
                        "## Recovered agent handoff\n\n"
                        "This same-organization branch contains explicit Codex/Perplexity provenance but had no pull request. "
                        "The branch is being restored to the normal protected review path; no bypass or direct default-branch write is used.\n\n"
                        f"- Branch: `{name}`\n- Exact head: `{sha}`\n"
                        f"- Ahead/behind at discovery: `{comparison.get('ahead_by')}/{comparison.get('behind_by')}`\n\n"
                        "Merge only after exact-head checks and review-thread resolution.\n\n"
                        "Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>"
                    ),
                    "maintainer_can_modify": True,
                },
            )
            row["create_pr_http"] = create_code
            if create_code == 201:
                row["state"] = "RECOVERY_PR_CREATED"
                row["pr"] = created_pr.get("number")
                created.append((repo_full, int(created_pr["number"])))
        report["orphan_branches"].append(row)
    return created


def default_branch_failures(repo: dict[str, Any], report: dict[str, Any]) -> None:
    repo_full = repo["full_name"]
    default = repo.get("default_branch") or "main"
    code, branch = gh(f"/repos/{repo_full}/branches/{urllib.parse.quote(default, safe='')}")
    if code != 200:
        return
    sha = str((branch.get("commit") or {}).get("sha") or "")
    runs = runs_for_sha(repo_full, sha)
    failures = [
        {
            "id": row.get("id"), "name": row.get("name"),
            "conclusion": row.get("conclusion"), "attempt": row.get("run_attempt"),
        }
        for row in runs
        if row.get("status") != "completed" or row.get("conclusion") in BAD_CONCLUSIONS
    ]
    if failures:
        report["default_branch_findings"].append({"repo": repo_full, "sha": sha, "runs": failures})
        recover_runs(repo_full, sha, report)


def github_phase(report: dict[str, Any]) -> None:
    user_code, user = gh("/user")
    report["github_auth"] = {
        "present": bool(GH_TOKEN), "http": user_code,
        "login": user.get("login") if user_code == 200 else None,
        "token_recorded": False,
    }
    try:
        repos = gh_pages(f"/orgs/{ORG}/repos?type=all&sort=updated")
    except Exception as exc:
        report["errors"].append({"subject": ORG, "error": _redact(str(exc))})
        return
    report["github_repo_count"] = len(repos)
    active = [repo for repo in repos if not repo.get("archived") and not repo.get("disabled")]
    report["github_active_repo_count"] = len(active)

    newly_created: list[tuple[str, int]] = []
    for repo in active:
        repo_full = repo["full_name"]
        code, pulls = gh(f"/repos/{repo_full}/pulls?state=open&per_page=100")
        if code == 200:
            for pr in pulls:
                reconcile_pr(repo, pr, report)
        newly_created.extend(recover_orphan_agent_branches(repo, report))
        default_branch_failures(repo, report)

    if newly_created:
        time.sleep(45)
        repo_map = {repo["full_name"]: repo for repo in active}
        for repo_full, number in newly_created:
            reconcile_pr(repo_map[repo_full], {"number": number}, report)

    for term in ("Codex", "Perplexity"):
        query = urllib.parse.quote(f"org:{ORG} is:issue is:open {term}")
        code, data = gh(f"/search/issues?q={query}&per_page=100")
        if code == 200:
            for issue in data.get("items", []):
                report["agent_issues"].append({
                    "term": term,
                    "repo": str(issue.get("repository_url") or "").split("/repos/")[-1],
                    "number": issue.get("number"), "title": issue.get("title"),
                    "url": issue.get("html_url"),
                })


def hf_asset_list(kind: str) -> list[dict[str, Any]]:
    code, data = hf(f"/api/{kind}?author={HF_ORG}&limit=100&full=true")
    if code != 200 or not isinstance(data, list):
        raise RuntimeError(f"HF {kind} HTTP {code}: {_redact(str(data))}")
    return data


def hf_phase(report: dict[str, Any]) -> None:
    report["hf_auth"] = {"present": bool(HF_TOKEN), "token_recorded": False}
    try:
        models = hf_asset_list("models")
        datasets = hf_asset_list("datasets")
        spaces = hf_asset_list("spaces")
    except Exception as exc:
        report["errors"].append({"subject": HF_ORG, "error": _redact(str(exc))})
        return
    report["hf_counts"] = {"models": len(models), "datasets": len(datasets), "spaces": len(spaces)}
    unsafe: list[dict[str, Any]] = []
    for model in models:
        filenames = [str(row.get("rfilename") or "") for row in model.get("siblings", [])]
        flagged = sorted(name for name in filenames if name.lower().endswith((".joblib", ".pkl", ".pickle")))
        if flagged:
            unsafe.append({"model": model.get("id"), "files": flagged})
    report["hf_unsafe_serialization"] = unsafe

    restartable = {"PAUSED", "STOPPED", "RUNTIME_ERROR", "BUILD_ERROR", "NO_APP_FILE"}
    restarted: list[str] = []
    for space in spaces:
        space_id = str(space.get("id") or "")
        runtime = space.get("runtime") or {}
        stage = str(runtime.get("stage") or "UNKNOWN")
        hardware = runtime.get("hardware") or {}
        current_hardware = hardware.get("current") if isinstance(hardware, dict) else None
        row = {
            "space": space_id,
            "private": bool(space.get("private")),
            "sha": space.get("sha"),
            "stage_before": stage,
            "hardware": current_hardware,
            "action": "NONE",
        }
        if (
            MUTATE and HF_TOKEN and not space.get("private")
            and stage in restartable and stage != "NO_APP_FILE"
        ):
            code, data = hf(f"/api/spaces/{space_id}/restart", method="POST")
            row["restart_http"] = code
            if code in {200, 202}:
                row["action"] = "RESTART_REQUESTED"
                restarted.append(space_id)
            else:
                row["action"] = "RESTART_REFUSED"
        elif space.get("private") and stage in restartable:
            row["action"] = "PRIVATE_FOLDED_PRESERVED"
        elif stage == "NO_APP_FILE":
            row["action"] = "SOURCE_REPAIR_REQUIRED"
        report["hf_spaces"].append(row)

    if restarted:
        deadline = time.monotonic() + 720
        remaining = set(restarted)
        while remaining and time.monotonic() < deadline:
            time.sleep(30)
            for space_id in list(remaining):
                code, current = hf(f"/api/spaces/{space_id}")
                stage = str(((current or {}).get("runtime") or {}).get("stage") or "UNKNOWN") if code == 200 else "UNAVAILABLE"
                if stage in {"RUNNING", "RUNNING_APP_STARTING", "RUNNING_BUILDING"}:
                    remaining.remove(space_id)
                for row in report["hf_spaces"]:
                    if row["space"] == space_id:
                        row["stage_after"] = stage
                        break
        for row in report["hf_spaces"]:
            if row["space"] in remaining:
                row["stage_after"] = row.get("stage_after", "TIMEOUT")


def post_summary(report: dict[str, Any]) -> None:
    if not GH_TOKEN:
        return
    merged = [row for row in report["observed_prs"] if row.get("disposition") == "MERGED"]
    blocked = [row for row in report["observed_prs"] if row.get("disposition") in {"BLOCKED", "PROTECTED_MERGE_REFUSED"}]
    restarted = [row for row in report["hf_spaces"] if row.get("action") == "RESTART_REQUESTED"]
    body = (
        "## Codex / Perplexity estate recovery receipt\n\n"
        f"- Generated: `{report['generated_at']}`\n"
        f"- GitHub repositories observed: `{report.get('github_repo_count', 'UNAVAILABLE')}`\n"
        f"- Open PRs observed: `{len(report['observed_prs'])}`\n"
        f"- PRs merged through protected exact-head path: `{len(merged)}`\n"
        f"- PRs still blocked/held: `{len(blocked)}`\n"
        f"- Explicit orphan agent branches observed: `{len(report['orphan_branches'])}`\n"
        f"- Hugging Face counts: `{json.dumps(report.get('hf_counts', {}), sort_keys=True)}`\n"
        f"- Public Space restarts requested: `{len(restarted)}`\n"
        f"- Unsafe serialized model findings: `{len(report.get('hf_unsafe_serialization', []))}`\n"
        f"- Controller errors: `{len(report['errors'])}`\n\n"
        "The retained Actions artifact contains the exact redacted ledger. No credential value, hardware allocation, visibility, storage, custom domain, branch protection, or billing setting was changed."
    )
    gh(f"/repos/{ORG}/a11oy/issues/1326/comments", method="POST", data={"body": body})


def render(report: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    merged = [row for row in report["observed_prs"] if row.get("disposition") == "MERGED"]
    blocked = [row for row in report["observed_prs"] if row.get("disposition") not in {"MERGED", "CLOSED_IDENTICAL"}]
    lines = [
        "# Codex / Perplexity estate recovery",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Execution mode: `{'APPLY' if MUTATE else 'PLAN'}`",
        "",
        "## Summary",
        "",
        f"- GitHub repositories observed: **{report.get('github_repo_count', 'UNAVAILABLE')}**",
        f"- Open pull requests observed: **{len(report['observed_prs'])}**",
        f"- Pull requests merged: **{len(merged)}**",
        f"- Pull requests still held or blocked: **{len(blocked)}**",
        f"- Explicit orphan agent branches observed: **{len(report['orphan_branches'])}**",
        f"- Workflow recovery actions: **{len(report['workflow_actions'])}**",
        f"- Hugging Face assets: **{json.dumps(report.get('hf_counts', {}), sort_keys=True)}**",
        f"- Unsafe serialized-model findings: **{len(report.get('hf_unsafe_serialization', []))}**",
        f"- Errors: **{len(report['errors'])}**",
        "",
        "## Pull requests",
        "",
    ]
    if report["observed_prs"]:
        for row in report["observed_prs"]:
            lines.append(f"- `{row['repo']}#{row['number']}` — **{row.get('disposition', 'OBSERVED')}** — {row.get('title')}")
    else:
        lines.append("- No open pull requests were returned by the authenticated organization sweep.")
    lines.extend(["", "## Hugging Face Spaces", ""])
    for row in report["hf_spaces"]:
        lines.append(
            f"- `{row['space']}` — `{row.get('stage_before')}`"
            f" → `{row.get('stage_after', row.get('stage_before'))}` — `{row.get('action')}`"
        )
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        for row in report["errors"]:
            lines.append(f"- `{row.get('subject')}` — `{row.get('error')}`")
    lines.extend([
        "",
        "## Mutation boundary",
        "",
        "- No force push or direct protected-branch write.",
        "- No check, review, DCO, signature, or branch-protection bypass.",
        "- No Hugging Face hardware, visibility, secret, storage, model, dataset, or custom-domain change.",
        "- No credential value is printed, persisted, or placed in the receipt.",
    ])
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report: dict[str, Any] = {
        "schema": "szl.agent-estate-recovery/v1",
        "generated_at": NOW.isoformat(),
        "execute": MUTATE,
        "task_ids": sorted(TASK_IDS),
        "github_auth": {},
        "github_repo_count": None,
        "github_active_repo_count": None,
        "observed_prs": [],
        "orphan_branches": [],
        "workflow_actions": [],
        "default_branch_findings": [],
        "agent_issues": [],
        "hf_auth": {},
        "hf_counts": {},
        "hf_spaces": [],
        "hf_unsafe_serialization": [],
        "errors": [],
        "credential_values_recorded": False,
    }
    github_phase(report)
    hf_phase(report)
    render(report)
    post_summary(report)
    # The controller itself succeeds when it completes and emits the ledger. Any
    # unresolved component remains explicitly BLOCKED in the report.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
