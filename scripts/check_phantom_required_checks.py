#!/usr/bin/env python3
# =============================================================================
# check_phantom_required_checks.py — catch a "required" merge check that can
# never pass before it silently stalls automation.
#
# WHY
#   Task #313 stayed invisible for weeks: `main` required a status check literally
#   named `check` that NO workflow ever emits on pull_request events
#   (readme-frontmatter-check.yml emits `check` only on push; doctrine.yml emits
#   `check / doctrine`). Every Dependabot PR therefore sat at mergeStateStatus
#   BLOCKED forever, quietly waiting for a human. Branch protection happily
#   "required" a context that could never go green.
#
#   This guard lists every EFFECTIVE required status check on a branch (the union
#   of classic protection AND rulesets) and flags any required context that has
#   not been reported on any recent pull_request run — i.e. a phantom that can
#   never pass. A phantom required check, by definition, never appears in a PR's
#   status-check rollup, so it cannot be discovered by inspecting check runs
#   alone; it can only be found by diffing the DECLARED required set against what
#   actually gets REPORTED on real PRs. That is exactly what this script does.
#
# HOW WE READ "REQUIRED"
#   The classic REST surface (/branches/<b>/protection) alone is misleading —
#   a11oy's governance lives in a ruleset now and classic protection 404s. We
#   read the EFFECTIVE union from /repos/<repo>/rules/branches/<branch> (which
#   already merges classic + every ruleset), and we cross-check the GraphQL
#   `isRequired(pullRequestNumber:)` flag on the contexts that DID report, so a
#   future extraction drift in the rules parser shows up as an observed-vs-
#   declared mismatch in the summary.
#
#   False-positive guard: a brand-new required context that simply has not run on
#   the sampled PRs yet would look phantom. We only render a verdict when at
#   least one sampled PR carried a status-check rollup, and the report states the
#   sample size so a human can tell "phantom" from "freshly added".
#
#   Stdlib only (urllib) — runs on a clean ubuntu-latest with no `pip install`
#   and no third-party action (org policy: github-owned/verified actions only).
#
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"


# --------------------------------------------------------------------------- #
# Pure parsing / logic (network-free, unit-tested in test_*.py)
# --------------------------------------------------------------------------- #
def extract_required_from_rules(rules):
    """Effective required contexts from GET /repos/<repo>/rules/branches/<b>.

    The endpoint returns a flat list of rule objects (the merged union of
    classic protection and every applicable ruleset). Required status checks
    live in rules of type ``required_status_checks`` under
    ``parameters.required_status_checks[].context``.
    """
    out = set()
    if not isinstance(rules, list):
        return out
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != "required_status_checks":
            continue
        params = rule.get("parameters") or {}
        for chk in params.get("required_status_checks") or []:
            if isinstance(chk, dict) and chk.get("context"):
                out.add(chk["context"])
            elif isinstance(chk, str) and chk:
                out.add(chk)
    return out


def extract_required_from_classic(obj):
    """Required contexts from the classic
    /branches/<b>/protection/required_status_checks payload (404-tolerant:
    callers pass ``None`` when the surface does not exist)."""
    out = set()
    if not isinstance(obj, dict):
        return out
    for c in obj.get("contexts") or []:
        if isinstance(c, str) and c:
            out.add(c)
    # Newer shape: checks: [{context, app_id}]
    for c in obj.get("checks") or []:
        if isinstance(c, dict) and c.get("context"):
            out.add(c["context"])
    return out


def extract_reported_from_pr(pr_payload):
    """From a single-PR GraphQL payload return (reported, required_observed).

    ``reported`` = every status-check context name that appeared in the head
    commit's rollup. ``required_observed`` = the subset GitHub flagged
    ``isRequired`` for this PR. Returns (set, set, had_rollup: bool)."""
    reported = set()
    required_observed = set()
    had_rollup = False
    try:
        pr = pr_payload["data"]["repository"]["pullRequest"]
    except (TypeError, KeyError):
        return reported, required_observed, had_rollup
    if not pr:
        return reported, required_observed, had_rollup
    commits = (pr.get("commits") or {}).get("nodes") or []
    if not commits:
        return reported, required_observed, had_rollup
    rollup = (commits[0].get("commit") or {}).get("statusCheckRollup")
    if not rollup:
        return reported, required_observed, had_rollup
    had_rollup = True
    for node in (rollup.get("contexts") or {}).get("nodes") or []:
        name = node.get("name") or node.get("context")
        if not name:
            continue
        reported.add(name)
        if node.get("isRequired"):
            required_observed.add(name)
    return reported, required_observed, had_rollup


def find_phantoms(required_declared, reported_union):
    """Required contexts that never reported on any sampled PR = phantoms that
    can never let a PR go green."""
    return sorted(set(required_declared) - set(reported_union))


# --------------------------------------------------------------------------- #
# Network
# --------------------------------------------------------------------------- #
def _request(url, token, method="GET", data=None):
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "a11oy-phantom-required-check-guard",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.getcode(), json.loads(resp.read().decode("utf-8"))


def fetch_effective_rules(repo, token, branch):
    code, data = _request("%s/repos/%s/rules/branches/%s" % (API, repo, branch), token)
    return data


def fetch_classic_required(repo, token, branch):
    url = "%s/repos/%s/branches/%s/protection/required_status_checks" % (API, repo, branch)
    try:
        _code, data = _request(url, token)
        return data
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):  # no classic protection / no required checks
            return None
        raise


def list_recent_prs(repo, token, n):
    url = "%s/repos/%s/pulls?state=all&sort=updated&direction=desc&per_page=%d" % (API, repo, n)
    _code, data = _request(url, token)
    return [pr["number"] for pr in data if isinstance(pr, dict) and "number" in pr]


_PR_QUERY = """
query($owner:String!,$name:String!,$pr:Int!){
  repository(owner:$owner,name:$name){
    pullRequest(number:$pr){
      commits(last:1){nodes{commit{statusCheckRollup{contexts(first:100){nodes{
        __typename
        ... on CheckRun{name isRequired(pullRequestNumber:$pr)}
        ... on StatusContext{context isRequired(pullRequestNumber:$pr)}
      }}}}}}
    }
  }
}
"""


def fetch_pr_contexts(repo, token, pr_number):
    owner, name = repo.split("/", 1)
    payload = {"query": _PR_QUERY, "variables": {"owner": owner, "name": name, "pr": pr_number}}
    _code, data = _request(GRAPHQL, token, method="POST", data=payload)
    if isinstance(data, dict) and data.get("errors"):
        # isRequired can 404 on weird PR refs; keep the rollup we can read.
        pass
    return data


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run(repo, token, branch, pr_sample):
    rules = fetch_effective_rules(repo, token, branch)
    classic = fetch_classic_required(repo, token, branch)
    required_declared = extract_required_from_rules(rules) | extract_required_from_classic(classic)

    reported_union = set()
    required_observed = set()
    prs_checked = []
    prs_with_rollup = 0
    for pr in list_recent_prs(repo, token, pr_sample):
        payload = fetch_pr_contexts(repo, token, pr)
        reported, req_obs, had_rollup = extract_reported_from_pr(payload)
        prs_checked.append(pr)
        if had_rollup:
            prs_with_rollup += 1
        reported_union |= reported
        required_observed |= req_obs

    phantoms = find_phantoms(required_declared, reported_union)
    return {
        "repo": repo,
        "branch": branch,
        "pr_sample_requested": pr_sample,
        "prs_checked": prs_checked,
        "prs_with_rollup": prs_with_rollup,
        "required_declared": sorted(required_declared),
        "reported_union": sorted(reported_union),
        "required_observed": sorted(required_observed),
        "phantoms": phantoms,
    }


def render(summary):
    lines = []
    lines.append("Phantom required-check guard — %s @ %s" % (summary["repo"], summary["branch"]))
    lines.append("  PRs sampled: %d (with a status rollup: %d)"
                 % (len(summary["prs_checked"]), summary["prs_with_rollup"]))
    lines.append("  Required (declared, effective union): %d" % len(summary["required_declared"]))
    for c in summary["required_declared"]:
        mark = "phantom" if c in summary["phantoms"] else "ok"
        lines.append("    [%s] %s" % (mark, c))
    if summary["phantoms"]:
        lines.append("")
        lines.append("  PHANTOM required checks (required but never reported on any sampled PR):")
        for c in summary["phantoms"]:
            lines.append("    - %s" % c)
        lines.append("  -> these can never go green on a PR; every PR will sit BLOCKED.")
    else:
        lines.append("  No phantom required checks. Every required context reports on PRs.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default="szl-holdings/a11oy")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--pr-sample", type=int, default=15,
                    help="how many recent PRs to inspect for reported contexts")
    ap.add_argument("--summary-file", default=None)
    args = ap.parse_args(argv)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: set GH_TOKEN or GITHUB_TOKEN.", file=sys.stderr)
        return 2

    summary = run(args.repo, token, args.branch, args.pr_sample)
    print(render(summary))

    if args.summary_file:
        with open(args.summary_file, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, sort_keys=True)
            fh.write("\n")

    if summary["prs_with_rollup"] == 0:
        # Can't render a verdict — no PR carried a rollup. Don't false-flag.
        print("WARNING: no sampled PR had a status-check rollup; cannot judge "
              "phantom checks. Widen --pr-sample.", file=sys.stderr)
        return 0

    if summary["phantoms"]:
        print("FAIL: %d phantom required check(s) found." % len(summary["phantoms"]),
              file=sys.stderr)
        return 1

    print("PASS: no phantom required checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
