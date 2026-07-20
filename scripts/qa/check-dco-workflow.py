#!/usr/bin/env python3
# VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — scripts/qa/check-dco-workflow.py
# DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
"""Regression guard for the platform DCO workflow.

The GitHub pull-request commits API is paginated.  A DCO check that reads only
the first page silently skips sign-off enforcement for later commits.  Keep the
pagination contract and the per-commit trailer check coupled in one local,
dependency-free guard.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "dco.yml"


def require(fragment: str, source: str, description: str) -> None:
    if fragment not in source:
        raise SystemExit(f"DCO workflow regression: missing {description}: {fragment!r}")


def main() -> int:
    source = WORKFLOW.read_text(encoding="utf-8")

    require("gh api --paginate", source, "GitHub API pagination")
    require("/commits?per_page=100", source, "explicit maximum page size")
    require("--jq '.[].sha'", source, "commit SHA extraction")
    require("for sha in $COMMITS; do", source, "per-commit iteration")
    require('git log -1 --format="%B" "$sha"', source, "full commit-message lookup")
    require('grep -q "^Signed-off-by:"', source, "Signed-off-by trailer enforcement")
    require("FAIL=1", source, "missing-trailer failure state")
    require("exit $FAIL", source, "non-zero enforcement exit")
    require(
        "python3 scripts/qa/check-dco-workflow.py",
        source,
        "workflow self-validation step",
    )

    print("DCO workflow pagination and per-commit sign-off contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
