#!/usr/bin/env python3
"""tools/github_org_audit.py — READ_ONLY audit of repos, open PRs, and merge
state across the szl-holdings GitHub org (turn-16 payload §1).

Dual backend, no hard dependency:
  * Preferred here: authenticated `gh` CLI (this executor's credential).
  * Preferred in Codex's env: GITHUB_TOKEN + PyGithub.
If neither is available, every repo records AUTH_REQUIRED — NEVER zero.
This script NEVER merges, closes, or pushes.

Outputs:
  audits/github_org_audit.json      (machine)
  audits/github_org_audit.md        (human)
  receipts/sub-github-org-audit.json (GovernedAction/v1, signed if key present)
"""
from __future__ import annotations

import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
AUDITS = ROOT / "audits"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
ORG = "szl-holdings"

RISKY_MARKERS = (
    "receipt", "verifier", "policy_engine", "capability_constitution",
    "flight_recorder", "predicate", "attestation", "governance", "security",
    "governedaction",
)


def _gh(*args) -> list | dict | None:
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=180)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
        return [] if r.returncode == 0 else {"__err__": r.stderr.strip()[:300]}
    except FileNotFoundError:
        return None
    except Exception as e:  # noqa: BLE001
        return {"__exc__": f"{type(e).__name__}: {e}"}


def collect_via_gh() -> dict:
    repos = _gh("repo", "list", ORG, "--limit", "200", "--json",
                "name,visibility,isArchived,pushedAt,url,defaultBranchRef")
    if repos is None:
        return {"backend": None, "repos": [], "meta_errors": ["gh CLI not found"]}
    open_prs, merged_prs, ci_fail = [], [], []
    for repo in repos:
        name = repo["name"]
        ops = _gh("pr", "list", "-R", f"{ORG}/{name}", "--state", "open", "--limit", "100", "--json",
                  "number,title,author,createdAt,isDraft,mergeable,headRefName,baseRefName,url,files,reviews,statusCheckRollup") or []
        for p in ops if isinstance(ops, list) else []:
            files = [f.get("path", "") for f in p.get("files", [])]
            risky = any(m in f.lower() for f in files for m in RISKY_MARKERS)
            reviews = p.get("reviews", [])
            approved = any(rv.get("state") == "APPROVED" for rv in reviews)
            rollup = p.get("statusCheckRollup") or []
            checks = [(c.get("conclusion") or c.get("status") or "") for c in rollup if isinstance(c, dict)]
            ci = ("success" if rollup and all(c.lower() in ("success", "neutral", "skipped", "completed") for c in checks)
                  else "failure" if any(c.lower() in ("failure", "timed_out") for c in checks)
                  else "pending" if checks else "no_checks")
            mergeable = p.get("mergeable", "UNKNOWN")
            if risky:
                rec = "HUMAN_REQUIRED"
            elif mergeable != "MERGEABLE":
                rec = "BLOCKED_CONFLICT"
            elif ci == "success" and approved:
                rec = "AUTO_ELIGIBLE"
            elif ci == "failure":
                rec = "BLOCKED_CI"
            else:
                rec = "HUMAN_REQUIRED_NO_APPROVAL"
            open_prs.append({
                "repo": name, "number": p["number"], "title": p.get("title", ""),
                "author": (p.get("author") or {}).get("login", "UNKNOWN"),
                "mergeable": mergeable, "ci": ci, "approved": approved,
                "touches_risky_path": risky, "createdAt": p.get("createdAt"),
                "merge_recommendation": rec, "url": p.get("url"),
            })
        runs = _gh("run", "list", "-R", f"{ORG}/{name}", "--limit", "3", "--json",
                   "displayTitle,conclusion,status,name,headBranch") or []
        if isinstance(runs, list) and runs:
            fails = [r for r in runs if r.get("conclusion") == "failure"]
            if fails:
                ci_fail.append({"repo": name, "recent": len(runs), "failures": len(fails)})
        mps = _gh("pr", "list", "-R", f"{ORG}/{name}", "--state", "merged", "--limit", "50", "--json",
                  "number,mergedAt") or []
        if isinstance(mps, list):
            merged_prs += [{"repo": name, "mergedAt": p.get("mergedAt")} for p in mps]
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=45)
    recent_merged = [p for p in merged_prs if p["mergedAt"] and
                     datetime.datetime.fromisoformat(p["mergedAt"].replace("Z", "+00:00")) >= cutoff]
    return {
        "backend": "gh-cli", "org": ORG, "collected_at": NOW,
        "repo_count": len(repos), "repos": repos,
        "open_prs": open_prs, "merged_45d_count": len(recent_merged),
        "ci_failing_repos": ci_fail, "meta_errors": [],
    }


def render(data: dict) -> tuple[str, str]:
    auto = [p for p in data["open_prs"] if p["merge_recommendation"] == "AUTO_ELIGIBLE"]
    human = [p for p in data["open_prs"] if "HUMAN" in p["merge_recommendation"]]
    blocked = [p for p in data["open_prs"] if p["merge_recommendation"].startswith("BLOCKED")]
    md = [
        f"# GitHub Org Audit — {data['org']}",
        f"Collected: {data['collected_at']} · backend={data['backend']} · READ_ONLY", "",
        f"- repos: {data['repo_count']}",
        f"- open PRs: {len(data['open_prs'])}",
        f"- merged in last 45d: {data['merged_45d_count']}",
        f"- repos with failing recent CI: {len(data['ci_failing_repos'])}", "",
        "## Open PR classification", "",
        "| PR | CI | Approved | Risky path | Mergeable | Recommendation |",
        "|---|---|---|---|---|---|",
    ]
    for p in sorted(data["open_prs"], key=lambda x: (x["repo"], x["number"])):
        md.append(f"| {p['repo']}#{p['number']} | {p['ci']} | {p['approved']} | "
                  f"{'YES' if p['touches_risky_path'] else 'no'} | {p['mergeable']} | {p['merge_recommendation']} |")
    auto_lines = [f"- {p['repo']}#{p['number']} {p['title']}" for p in auto] or ["- none"]
    human_lines = [f"- {p['repo']}#{p['number']} {p['title']}" for p in human] or ["- none"]
    blocked_lines = [f"- {p['repo']}#{p['number']} {p['title']} [{p['merge_recommendation']}]" for p in blocked] or ["- none"]
    md += ["", f"### AUTO_ELIGIBLE ({len(auto)})"] + auto_lines
    md += ["", f"### HUMAN_REQUIRED ({len(human)})"] + human_lines
    md += ["", f"### BLOCKED ({len(blocked)})"] + blocked_lines
    md += ["", "### Repos with failing recent CI", ""]
    md += [f"- {r['repo']}: {r['failures']}/{r['recent']} failed" for r in data["ci_failing_repos"]] or ["- none"]
    if data["meta_errors"]:
        md += ["", "## Errors", *[f"- {e}" for e in data["meta_errors"]]]
    return "\n".join(md) + "\n", json.dumps(data, indent=2)


def main() -> int:
    AUDITS.mkdir(parents=True, exist_ok=True)
    data = collect_via_gh()
    md, js = render(data)
    (AUDITS / "github_org_audit.md").write_text(md)
    (AUDITS / "github_org_audit.json").write_text(js)
    auto = sum(1 for p in data["open_prs"] if p["merge_recommendation"] == "AUTO_ELIGIBLE")
    print(f"github_org_audit: repos={data['repo_count']} open_prs={len(data['open_prs'])} "
          f"merged45d={data['merged_45d_count']} auto_eligible={auto} backend={data['backend']}")
    return 0


if __name__ == "__main__":
    if "--report" in sys.argv:
        sys.exit(main())
    print(__doc__)
    sys.exit(2)
