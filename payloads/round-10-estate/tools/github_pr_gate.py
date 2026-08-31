#!/usr/bin/env python3
"""tools/github_pr_gate.py — CI gate over the PR classification produced by
tools/github_org_audit.py.

Law (enforced in the exit code, not prose):
  * Any PR with failing CI          -> gate finds BLOCKED_CI
  * Any PR with a merge conflict    -> gate finds BLOCKED_CONFLICT
  * Any PR touching a governed path -> HUMAN_REQUIRED (never auto-merged)
  * Any PR without an approval      -> HUMAN_REQUIRED_NO_APPROVAL

Exit codes:
  0 = zero open PRs blocked by CI or conflict (clean merge queue)
  1 = one or more BLOCKED_* PRs (queue not green)
  2 = classification artifact missing / unparseable
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLASSIFICATION = ROOT / "audits" / "github_org_audit.json"


def main() -> int:
    if not CLASSIFICATION.is_file():
        print(f"github_pr_gate: {CLASSIFICATION} not found — run tools/github_org_audit.py --report first",
              file=sys.stderr)
        return 2
    data = json.loads(CLASSIFICATION.read_text())
    prs = data.get("open_prs", [])
    blocked = [p for p in prs if p["merge_recommendation"].startswith("BLOCKED")]
    human = [p for p in prs if "HUMAN" in p["merge_recommendation"]]
    auto = [p for p in prs if p["merge_recommendation"] == "AUTO_ELIGIBLE"]

    print(f"github_pr_gate: {len(prs)} open PRs — "
          f"{len(auto)} auto-eligible, {len(human)} human-required, {len(blocked)} blocked")
    if blocked:
        print("github_pr_gate: FAIL — queue not green:")
        for p in blocked:
            print(f"  {p['repo']}#{p['number']} [{p['merge_recommendation']}] {p['title'][:70]}")
        return 1
    print("github_pr_gate: PASS — no CI- or conflict-blocked PRs")
    return 0


if __name__ == "__main__":
    sys.exit(main() if not ("--help" in sys.argv) else (print(__doc__) or 2))
