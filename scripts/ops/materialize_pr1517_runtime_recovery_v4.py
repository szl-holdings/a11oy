#!/usr/bin/env python3
"""Five-file PR #1517 recovery: reuse v3 gates, add readiness and loader repairs."""

from __future__ import annotations

import base64
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request

BASE_SCRIPT = Path("/tmp/materialize_pr1517_v3.py")
spec = importlib.util.spec_from_file_location("pr1517_v3", BASE_SCRIPT)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load v3 materializer")
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)

v3.PRODUCTION_FILES = (
    "a11oy_landing.html",
    "pages/console.html",
    "pages/landing.html",
    "serve.py",
    "tools/readiness-harness/tabs.json",
)


def apply_reviewed_frontend() -> None:
    patch = subprocess.run(
        (
            "git",
            "diff",
            "--binary",
            v3.SOURCE_BASE,
            v3.SOURCE_FINAL,
            "--",
            "a11oy_landing.html",
            "pages/console.html",
            "pages/landing.html",
            "tools/readiness-harness/tabs.json",
        ),
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    if not patch:
        raise SystemExit("reviewed frontend/readiness patch is empty")
    v3.run("git", "apply", "--3way", "--whitespace=nowarn", input_bytes=patch)
    v3.run("git", "reset", "--quiet")


def subtract_rejected_expansion_and_fix_loader() -> None:
    v3.subtract_rejected_expansion()

    landing = Path("a11oy_landing.html")
    text = landing.read_text(encoding="utf-8")
    declaration = "async function loadKernelLocked(){"
    corrected = "async function loadLockedKernel(){"
    old_call = "    loadKernelLocked();"
    new_call = "    loadLockedKernel();"
    orchestrate = "  // ---- orchestrate: overview first, fall back per-block for anything it didn't fill ----"
    alias = (
        "  // Backward-compatible alias for previously shipped callers; canonical contract is loadLockedKernel.\n"
        "  const loadKernelLocked = loadLockedKernel;\n\n"
    )
    if text.count(declaration) != 1:
        raise SystemExit(f"expected one legacy loader declaration, found {text.count(declaration)}")
    if text.count(old_call) != 1:
        raise SystemExit(f"expected one legacy loader call, found {text.count(old_call)}")
    if text.count(orchestrate) != 1:
        raise SystemExit("landing orchestrator marker changed")
    text = text.replace(declaration, corrected, 1)
    text = text.replace(old_call, new_call, 1)
    text = text.replace(orchestrate, alias + orchestrate, 1)
    landing.write_text(text, encoding="utf-8")

    tabs = json.loads(Path("tools/readiness-harness/tabs.json").read_text(encoding="utf-8"))
    rows = tabs.get("tabs")
    if not isinstance(rows, list):
        raise SystemExit("readiness tabs matrix has no tabs list")
    by_key = {str(row.get("key")): row for row in rows if isinstance(row, dict)}
    for key, route in (("estate", "/console#estate"), ("investor", "/console#investor")):
        row = by_key.get(key)
        if not isinstance(row, dict) or row.get("route") != route:
            raise SystemExit(f"readiness contract missing or malformed: {key}")
    if "five-space" in by_key:
        raise SystemExit("rejected Five-Space readiness expansion remains")


def materialize_verified_commit() -> str:
    v3.verify_remote_target()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GitHub token is unavailable")
    additions = [
        {
            "path": path,
            "contents": base64.b64encode(Path(path).read_bytes()).decode("ascii"),
        }
        for path in v3.PRODUCTION_FILES
    ]
    mutation = """
    mutation Materialize($input: CreateCommitOnBranchInput!) {
      createCommitOnBranch(input: $input) { commit { oid url } }
    }
    """
    variables = {
        "input": {
            "branch": {
                "repositoryNameWithOwner": v3.REPOSITORY,
                "branchName": v3.TARGET_BRANCH,
            },
            "expectedHeadOid": v3.EXPECTED_TARGET_HEAD,
            "message": {
                "headline": "fix(runtime): restore verified route, console and readiness contracts",
                "body": (
                    "Restore the reviewed runtime surfaces and readiness matrix at the exact "
                    "security-PR head. This recovers Khipu, investor and estate routes, KANCHAY "
                    "command chrome, honest Lean-8 and Killinchu labeling, dual-origin proof links, "
                    "the estate/investor readiness entries, and the canonical loadLockedKernel "
                    "contract while retaining the current crawler, sitemap, signer, and security-pin guards.\n\n"
                    "The rejected Five-Space product-door expansion is explicitly absent. "
                    "No protected-main write, force push, deployment, DNS mutation, secret change, "
                    "or evidence-class weakening is claimed.\n\n"
                    "Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>"
                ),
            },
            "fileChanges": {"additions": additions},
        }
    }
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": mutation, "variables": variables}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "szl-pr1517-runtime-recovery-v4",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub GraphQL HTTP {exc.code}: {body}") from exc
    if result.get("errors"):
        raise SystemExit("; ".join(str(row.get("message")) for row in result["errors"]))
    commit_sha = str(result["data"]["createCommitOnBranch"]["commit"]["oid"])
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise SystemExit(f"invalid successor OID: {commit_sha!r}")

    commit_json = json.loads(
        v3.output("gh", "api", f"repos/{v3.REPOSITORY}/commits/{commit_sha}")
    )
    if not commit_json["commit"]["verification"]["verified"]:
        raise SystemExit("successor commit is not GitHub-verified")
    parents = commit_json.get("parents", [])
    if len(parents) != 1 or parents[0].get("sha") != v3.EXPECTED_TARGET_HEAD:
        raise SystemExit("successor parent is not the exact reviewed head")
    changed = tuple(sorted(row["filename"] for row in commit_json.get("files", [])))
    if changed != tuple(sorted(v3.PRODUCTION_FILES)):
        raise SystemExit(f"successor changed an unexpected file set: {changed!r}")
    remote = v3.output(
        "gh",
        "api",
        f"repos/{v3.REPOSITORY}/git/ref/heads/{v3.TARGET_BRANCH}",
        "--jq",
        ".object.sha",
    )
    if remote != commit_sha:
        raise SystemExit("target branch did not advance to the verified successor")
    return commit_sha


def write_summary(commit_sha: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write("## PR #1517 clean runtime successor v4\n\n")
        handle.write(f"- target branch: `{v3.TARGET_BRANCH}`\n")
        handle.write(f"- verified successor: `{commit_sha}`\n")
        handle.write(f"- exact parent: `{v3.EXPECTED_TARGET_HEAD}`\n")
        handle.write(f"- reviewed source final: `{v3.SOURCE_FINAL}`\n")
        handle.write("- changed files: 5\n")
        handle.write("- estate/investor readiness entries: restored\n")
        handle.write("- canonical loadLockedKernel contract: restored\n")
        handle.write("- rejected Five-Space product-door expansion: absent\n")
        handle.write("- protected `main` mutation: none\n")


v3.apply_reviewed_frontend = apply_reviewed_frontend
v3.subtract_rejected_expansion = subtract_rejected_expansion_and_fix_loader
v3.materialize_verified_commit = materialize_verified_commit
v3.write_summary = write_summary

if __name__ == "__main__":
    v3.main()
