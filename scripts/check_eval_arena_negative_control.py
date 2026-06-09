#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Guard: the live Eval Arena must keep BOTH a passing AND a failing example.

Why this exists
---------------
The live Eval Arena (`/api/a11oy/v1/eval-arena/live`) re-executes a11oy's own
governance primitives against a set of scenarios and derives every dimension
score from a real operation performed now. The honesty story depends on the
arena showing not just green "pass" rows but at least one RED "fail" row — a
deliberately-malicious "negative control" scenario whose action trips the policy
gate (multiple threat signatures), so `policy_adherence`/`approval_compliance`
drop to 0, `overall` falls below the 0.85 pass threshold, and `pass=False`. That
row is what proves the gate REJECTS bad decisions instead of rubber-stamping
them (the red fail line / `b-err` badge in the console).

That negative control has already been silently lost once: it was added as the
6th `_A11OY_ARENA_SCENARIOS` entry, then accidentally dropped when a later commit
rewrote that region, leaving an all-green arena that could never show a failure.
Nothing caught it. This guard does.

What it checks
--------------
Running the REAL live eval in-image (it imports `serve.py` and calls
`_a11oy_eval_run_live()` — no fabricated numbers), it FAILS unless the run has:

  * at least ONE passing scenario (`pass == True`), AND
  * at least ONE failing scenario that is a genuine policy rejection:
    `pass == False` AND `overall < 0.85` AND a non-empty `policy_signals` list.

The `policy_signals` requirement is deliberate: a scenario can fail for benign
reasons (e.g. a missing signing key drops evidence completeness), but the
negative control must fail because the policy gate FIRED on threat signatures.
That is the property the honesty story actually rests on.

Usage
-----
  python3 scripts/check_eval_arena_negative_control.py            # real live run
  python3 scripts/check_eval_arena_negative_control.py --json     # + dump summary
  python3 scripts/check_eval_arena_negative_control.py --selftest # validator tests

Self-test feeds the pure validator synthetic runs (all-pass, all-fail-no-signals,
fail-but-above-threshold, fail-with-empty-signals) and asserts it REJECTS each,
plus accepts a known-good run — so a neutered validator fails loudly in CI before
it is trusted against the real run. Stdlib-only; github-owned actions only.

Signed-off-by: Yachay <yachay@szlholdings.ai>
"""
from __future__ import annotations

import argparse
import json
import os
import sys

PASS_THRESHOLD = 0.85


def validate_run(run: dict):
    """Pure validator. Returns (ok: bool, problems: list[str]).

    Asserts the eval-arena run keeps at least one passing scenario AND at least
    one genuine policy-rejection failure (overall < 0.85 with populated
    policy_signals). No I/O, no fabrication — operates on a run dict only.
    """
    problems: list[str] = []
    if not isinstance(run, dict):
        return False, ["run is not an object"]
    results = run.get("results")
    if not isinstance(results, list) or not results:
        return False, ["run has no 'results' list"]

    passing = []
    failing_with_signals = []
    for r in results:
        if not isinstance(r, dict):
            problems.append("a result entry is not an object")
            continue
        scenario = r.get("scenario", "?")
        overall = r.get("overall")
        is_pass = bool(r.get("pass"))
        signals = r.get("policy_signals")
        if is_pass:
            passing.append(scenario)
            continue
        # failing scenario — does it qualify as a genuine policy rejection?
        if not isinstance(overall, (int, float)):
            continue
        if overall < PASS_THRESHOLD and isinstance(signals, list) and len(signals) > 0:
            failing_with_signals.append(scenario)

    if not passing:
        problems.append(
            "no PASSING scenario — the arena shows no green example "
            "(every scenario failed; the eval may be broken)"
        )
    if not failing_with_signals:
        problems.append(
            "no FAILING negative-control scenario (a result with pass=False, "
            "overall<%.2f, and a non-empty policy_signals list). The deliberately "
            "malicious 'negative control' that proves the gate REJECTS bad "
            "decisions has been dropped or neutered — the red fail line / b-err "
            "badge would never fire again." % PASS_THRESHOLD
        )

    return (len(problems) == 0), problems


def _run_real_live() -> dict:
    """Import serve.py (the real image module) and run the live eval."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    import serve  # noqa: E402  (real in-image module; heavy registration is guarded)

    return serve._a11oy_eval_run_live()


def _selftest() -> int:
    good = {
        "results": [
            {"scenario": "ok-1", "overall": 0.95, "pass": True, "policy_signals": []},
            {"scenario": "neg-control", "overall": 0.54, "pass": False,
             "policy_signals": ["ignore previous", "exfiltrate", "rm -rf"]},
        ]
    }
    bad_all_pass = {
        "results": [
            {"scenario": "ok-1", "overall": 0.95, "pass": True, "policy_signals": []},
            {"scenario": "ok-2", "overall": 0.91, "pass": True, "policy_signals": []},
        ]
    }
    bad_fail_no_signals = {
        "results": [
            {"scenario": "ok-1", "overall": 0.95, "pass": True, "policy_signals": []},
            {"scenario": "broke", "overall": 0.40, "pass": False, "policy_signals": []},
        ]
    }
    bad_fail_above_threshold = {
        "results": [
            {"scenario": "ok-1", "overall": 0.95, "pass": True, "policy_signals": []},
            {"scenario": "soft", "overall": 0.90, "pass": False,
             "policy_signals": ["ignore previous"]},
        ]
    }
    bad_no_pass = {
        "results": [
            {"scenario": "neg-control", "overall": 0.54, "pass": False,
             "policy_signals": ["exfiltrate"]},
        ]
    }
    bad_empty = {"results": []}

    cases = [
        ("known-good run is accepted", good, True),
        ("all-pass run is rejected (no fail example)", bad_all_pass, False),
        ("failing-without-signals run is rejected", bad_fail_no_signals, False),
        ("failing-above-threshold run is rejected", bad_fail_above_threshold, False),
        ("no-passing-scenario run is rejected", bad_no_pass, False),
        ("empty results run is rejected", bad_empty, False),
    ]
    failures = 0
    for name, run, expect_ok in cases:
        ok, problems = validate_run(run)
        status = "PASS" if ok == expect_ok else "FAIL"
        if ok != expect_ok:
            failures += 1
        print("  [%s] %s (validator ok=%s, expected ok=%s)%s"
              % (status, name, ok, expect_ok,
                 "" if ok == expect_ok else " :: " + "; ".join(problems)))
    if failures:
        print("\nself-test FAILED: validator is not enforcing the contract.",
              file=sys.stderr)
        return 1
    print("\nself-test OK: validator rejects every degenerate run and accepts the good one.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true",
                    help="run the pure-validator fixtures and exit")
    ap.add_argument("--json", action="store_true",
                    help="print the live run summary as JSON")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    try:
        run = _run_real_live()
    except Exception as exc:  # noqa: BLE001
        print("::error::failed to run the live eval arena in-image: %r" % exc,
              file=sys.stderr)
        return 2

    ok, problems = validate_run(run)

    results = run.get("results") or []
    print("Eval Arena live run: %s scenarios, %s passed, %s failed"
          % (run.get("scenarios_total"), run.get("scenarios_passed"),
             run.get("scenarios_failed")))
    for r in results:
        print("  - %-38s overall=%-9s pass=%-5s signals=%s"
              % (r.get("scenario"), r.get("overall"), r.get("pass"),
                 r.get("policy_signals")))

    if args.json:
        print(json.dumps({"scenarios_total": run.get("scenarios_total"),
                          "scenarios_passed": run.get("scenarios_passed"),
                          "scenarios_failed": run.get("scenarios_failed"),
                          "results": [{"scenario": r.get("scenario"),
                                       "overall": r.get("overall"),
                                       "pass": r.get("pass"),
                                       "policy_signals": r.get("policy_signals")}
                                      for r in results]}, indent=2))

    if not ok:
        for p in problems:
            print("::error::eval-arena negative-control guard: %s" % p, file=sys.stderr)
        return 1

    print("\nGuard OK: arena keeps a passing example AND a policy-rejected "
          "negative control (red fail line is real).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
