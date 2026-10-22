"""Fail when the live a11oy Space serves a commit that lags protected main beyond a grace period.

Why: hf-sync.yml deliberately skips deploys while the deploy window is closed (SQLite on the
bucket mount) and still ends green, and hf-drift-check.yml never compares the runtime commit.
Together they let the live Space drift behind main with every check green. This check makes
that drift visible. It never writes, deploys or restarts anything.

Exit codes: 0 IN_SYNC or WITHIN_GRACE, 1 DRIFT (lag beyond grace), 2 UNAVAILABLE (fail closed:
the runtime or GitHub could not be read, so drift cannot be ruled out).

Standard library only. Usage:
  python -I -B .github/scripts/check_space_runtime_drift.py \
      --origin https://szlholdings-a11oy.hf.space --repository szl-holdings/a11oy --max-lag-hours 24
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


def _get_json(url: str, token: str | None = None, timeout: int = 20):
    headers = {"Accept": "application/json"}
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def deployed_sha(origin: str, fetch=_get_json) -> str:
    doc = fetch(origin.rstrip("/") + "/api/a11oy/v1/honest")
    sha = doc.get("git_sha") if isinstance(doc, dict) else None
    if not isinstance(sha, str) or not SHA_RE.match(sha.lower()):
        raise ValueError("runtime did not report a well-formed git_sha")
    return sha.lower()


def evaluate(deployed: str, main_sha: str, compare: dict, now: dt.datetime, max_lag_hours: float) -> dict:
    """Pure decision. `compare` is GitHub's compare(deployed...main) response."""
    main_sha = main_sha.lower()
    if main_sha.startswith(deployed) or deployed.startswith(main_sha):
        return {"verdict": "IN_SYNC", "exit": 0, "behind_by": 0, "lag_hours": 0.0}
    status = compare.get("status")
    behind = compare.get("ahead_by")  # commits on main that the deployment lacks
    commits = compare.get("commits") or []
    if status not in ("ahead", "diverged") or not isinstance(behind, int) or behind < 1 or not commits:
        # identical-but-unequal shas, unknown deployed sha, or a deployment main does not contain
        return {"verdict": "DRIFT", "exit": 1, "behind_by": behind, "lag_hours": None,
                "reason": f"deployed {deployed[:12]} is not an ancestor of main {main_sha[:12]} (status={status})"}
    first_missing = commits[0]["commit"]["committer"]["date"]
    since = dt.datetime.strptime(first_missing, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    lag = (now - since).total_seconds() / 3600.0
    if lag <= max_lag_hours:
        return {"verdict": "WITHIN_GRACE", "exit": 0, "behind_by": behind, "lag_hours": round(lag, 2)}
    return {"verdict": "DRIFT", "exit": 1, "behind_by": behind, "lag_hours": round(lag, 2),
            "reason": f"live Space runs {deployed[:12]}, {behind} commit(s) behind main {main_sha[:12]}; "
                      f"oldest undeployed commit is {lag:.1f} h old (grace {max_lag_hours} h)"}


def main(argv=None, fetch=_get_json, now=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--origin", required=True)
    ap.add_argument("--repository", required=True)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--max-lag-hours", type=float, default=24.0)
    a = ap.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN")
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        dep = deployed_sha(a.origin, fetch)
        main_sha = fetch(f"https://api.github.com/repos/{a.repository}/commits/{a.branch}", token)["sha"]
        cmp_ = fetch(f"https://api.github.com/repos/{a.repository}/compare/{dep}...{main_sha}", token)
        out = evaluate(dep, main_sha, cmp_, now, a.max_lag_hours)
        out.update({"deployed": dep, "main": main_sha})
    except (urllib.error.URLError, ValueError, KeyError, TypeError, OSError) as exc:
        out = {"verdict": "UNAVAILABLE", "exit": 2, "reason": f"{type(exc).__name__}: {exc}"[:300]}
    print(json.dumps(out, sort_keys=True))
    level = {"IN_SYNC": "notice", "WITHIN_GRACE": "notice", "DRIFT": "error", "UNAVAILABLE": "error"}[out["verdict"]]
    print(f"::{level}::Space runtime drift: {out['verdict']} {out.get('reason', '')}".rstrip())
    return out["exit"]


if __name__ == "__main__":
    sys.exit(main())
