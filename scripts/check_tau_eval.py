#!/usr/bin/env python3
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# check_tau_eval.py — CI guard for the szl-tau-tool-rules eval suite.
#
# Keeps the τ-bench-style tool-rule-following eval HONEST:
#   * the suite must contain >=1 NEGATIVE-CONTROL task (expect_refusal=True),
#   * a real run must score < 1.0 for an ALWAYS-PASS agent (proves the rules
#     actually reject bad trajectories — the score is non-trivial), and
#   * the reference rule-follower must pass every positive task and refuse every
#     negative control (proves the suite is satisfiable by a correct agent).
# No fabricated numbers — the validator runs the REAL szl_tau_eval.run_suite().
#
# --selftest feeds the validator degenerate runs and asserts it REJECTS each
# before the guard trusts it (org guard pattern; cf.
# eval-arena-negative-control.yml). Org policy: github-owned actions, SHAs pinned.
import os
import sys

# allow running as `python3 scripts/check_tau_eval.py` from the repo root: the
# eval module lives at the repo root next to serve.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def validate_run(res: dict) -> tuple[bool, str]:
    """Assert a τ-bench run is structurally honest. Returns (ok, reason)."""
    if not isinstance(res, dict):
        return False, "result is not a dict"
    if not res.get("tasks"):
        return False, "no tasks in run"
    if res.get("as_of") is None:
        return False, "missing as_of (score must be dated)"
    if res.get("determinism_hash") is None:
        return False, "missing determinism_hash"
    neg = sum(1 for t in res["tasks"] if t.get("expect_refusal"))
    if neg < 1:
        return False, "no negative-control task (expect_refusal=True)"
    if res.get("pass_at_1") is None:
        return False, "missing pass_at_1"
    return True, "ok"


def _always_pass_runner(scenario):
    # An agent that takes every disallowed action and never refuses.
    return {"trajectory": [{"tool": "issue_refund", "allowed": True},
                           {"tool": "send_email", "allowed": True},
                           {"tool": "run_sql", "allowed": True},
                           {"tool": "assign_seat", "allowed": True},
                           {"tool": "reset_password", "allowed": True}],
            "refused": False}


def main(argv) -> int:
    import szl_tau_eval as tau

    if "--selftest" in argv:
        # degenerate runs the validator MUST reject
        bad = [
            ({}, "empty"),
            ({"tasks": []}, "no tasks"),
            ({"tasks": [{"expect_refusal": False}], "as_of": "x",
              "determinism_hash": "y", "pass_at_1": 1.0}, "no negative control"),
            ({"tasks": [{"expect_refusal": True}], "determinism_hash": "y",
              "pass_at_1": 1.0}, "missing as_of"),
        ]
        for run, label in bad:
            ok, _ = validate_run(run)
            if ok:
                print("SELFTEST FAIL: validator accepted degenerate run: %s" % label)
                return 1
        # a good run the validator MUST accept
        good = tau.run_suite()
        ok, why = validate_run(good)
        if not ok:
            print("SELFTEST FAIL: validator rejected a good run: %s" % why)
            return 1
        print("SELFTEST OK: validator rejects degenerate runs, accepts a good one")
        return 0

    # real run with the reference rule-follower
    ref = tau.run_suite()
    ok, why = validate_run(ref)
    if not ok:
        print("GUARD FAIL: reference run not honest: %s" % why)
        return 1
    if ref["pass_at_1"] < 1.0:
        print("GUARD FAIL: reference rule-follower should pass all tasks, got %.4f"
              % ref["pass_at_1"])
        return 1

    # NON-TRIVIALITY: an always-pass agent must NOT get a perfect score
    ap = tau.run_suite(runner=_always_pass_runner)
    if ap["pass_at_1"] >= 1.0:
        print("GUARD FAIL: always-pass agent scored %.4f — suite is trivial!"
              % ap["pass_at_1"])
        return 1

    print("GUARD OK: suite=%s %s as_of=%s | reference pass^1=%.4f | "
          "always-pass pass^1=%.4f (< 1.0, score is non-trivial) | det=%s"
          % (ref["suite_id"], ref["suite_version"], ref["as_of"],
             ref["pass_at_1"], ap["pass_at_1"], ref["determinism_hash"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
