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

Per-negative-control distinct rejection paths
---------------------------------------------
The generic check above proves *a* policy-rejected failure exists, but the
arena's correctness rests on EACH declared negative control tripping its OWN
distinct rejection path: the adversarial-injection control via raw threat
signatures, the oversized-payload control via the >1MB size guard, and the
missing-operator-approval control via the high-impact approval guard. A second
validator (`validate_negative_controls`) therefore asserts that every control in
`NEGATIVE_CONTROL_FAMILIES` is present, genuinely FAILS, carries a non-empty
`policy_signals` list, fails through its EXPECTED signal family, and that no two
controls collapse onto the same family, share an individual signal, or duplicate
each other's signal list. This catches regressions the generic check misses: a
guard that silently stopped firing (e.g. the oversized blob shrank below 1MB so
the scenario now passes), or two controls drifting onto a single signal.

Recorded-run history
--------------------
The arena ALSO persists a capped ring buffer of recorded run summaries
(`/api/a11oy/v1/eval-arena/history`), and the console renders a trend strip from
it. A degraded recorded run could surface an all-green history strip even when
the live run is fine — the same blind spot, one layer removed. `--recorded`
loads EVERY recorded summary from the in-image ring (running ONE real live eval
to seed it the legitimate way if the ring is empty), normalizes each summary into
the validator's shape, and runs the SAME combined `validate()` over EVERY one —
validating only the latest would miss a degraded EARLIER run.
If the history is genuinely empty (no run could be recorded), it SKIPS with a
soft pass — it never fabricates a summary.

Usage
-----
  python3 scripts/check_eval_arena_negative_control.py            # real live run
  python3 scripts/check_eval_arena_negative_control.py --json     # + dump summary
  python3 scripts/check_eval_arena_negative_control.py --recorded # ALL recorded runs
  python3 scripts/check_eval_arena_negative_control.py --selftest # validator tests

Self-test feeds the pure validator synthetic runs (all-pass, all-fail-no-signals,
fail-but-above-threshold, fail-with-empty-signals) and asserts it REJECTS each,
plus accepts a known-good run — and exercises the recorded-run path too
(normalize a history summary, pick the latest, honest empty-history skip) — so a
neutered validator or a degraded recorded summary fails loudly in CI before it is
trusted against the real run. Stdlib-only; github-owned actions only.

Signed-off-by: Yachay <yachay@szlholdings.ai>
"""
from __future__ import annotations

import argparse
import json
import os
import sys

PASS_THRESHOLD = 0.85

# Each declared negative control must trip its OWN distinct rejection path. This
# map is the validator's source of truth for which malicious scenarios MUST be
# present and which policy-signal FAMILY each one must fail through:
#   threat-sigs    — a raw threat signature matched in the action payload
#                    (e.g. "exfiltrate", "rm -rf"); any signal that is not a
#                    size-guard or approval-guard label.
#   size-guard     — the >1MB DoS ceiling fired ("size-guard:...").
#   approval-guard — a high-impact action missing operator approval
#                    ("approval-guard:...").
# Keeping these DISTINCT proves the gate is a multi-signal inspection, not one
# hard-coded string match, and stops two controls silently collapsing onto a
# single rejection path. Add a row here in lockstep whenever serve.py grows a
# new negative control, or that control's path goes unguarded.
NEGATIVE_CONTROL_FAMILIES = {
    "adversarial-injection-negative-control": "threat-sigs",
    "oversized-payload-negative-control": "size-guard",
    "missing-operator-approval-negative-control": "approval-guard",
}


def _signal_family(sig) -> str:
    """Classify a single policy signal into its rejection-path family."""
    if not isinstance(sig, str):
        return "?"
    if sig.startswith("size-guard:"):
        return "size-guard"
    if sig.startswith("approval-guard:"):
        return "approval-guard"
    return "threat-sigs"


def _families_of(signals) -> set:
    """Set of rejection-path families present in a policy_signals list."""
    if not isinstance(signals, list):
        return set()
    return {_signal_family(s) for s in signals}


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


def validate_negative_controls(run: dict):
    """Pure validator (layer 2). Returns (ok: bool, problems: list[str]).

    Asserts that EACH declared negative control (`NEGATIVE_CONTROL_FAMILIES`) is
    present in the run, genuinely FAILS (pass=False AND overall < threshold),
    carries a non-empty `policy_signals` list, fails through its OWN expected
    signal family, and that no two controls collapse onto the same family, share
    an individual signal, or duplicate each other's signal list.

    This is what catches the regressions the generic `validate_run` misses:
      * a guard that silently stopped firing (e.g. the oversized blob shrank
        below 1MB so its scenario now PASSES with an empty signal list), and
      * two negative controls drifting onto a single rejection signal/family.
    No I/O, no fabrication — operates on a run dict only.
    """
    problems: list[str] = []
    if not isinstance(run, dict):
        return False, ["run is not an object"]
    results = run.get("results")
    if not isinstance(results, list) or not results:
        return False, ["run has no 'results' list"]

    by_scenario = {}
    for r in results:
        if isinstance(r, dict):
            by_scenario[r.get("scenario")] = r

    # A scenario named like a negative control that this guard does not declare
    # means serve.py grew a control without updating NEGATIVE_CONTROL_FAMILIES —
    # the two MUST stay in lockstep or the new rejection path is unguarded.
    for name in by_scenario:
        if (isinstance(name, str) and name.endswith("-negative-control")
                and name not in NEGATIVE_CONTROL_FAMILIES):
            problems.append(
                "scenario '%s' looks like a negative control but is not declared in "
                "NEGATIVE_CONTROL_FAMILIES — add it (with its expected rejection "
                "family) so its path is guarded." % name)

    family_owner: dict = {}      # signal family -> first control that fired it
    signalset_owner: dict = {}   # frozenset(signals) -> first control
    signal_owner: dict = {}      # individual signal -> first control

    for name, expected_family in NEGATIVE_CONTROL_FAMILIES.items():
        r = by_scenario.get(name)
        if r is None:
            problems.append(
                "declared negative control '%s' is MISSING from the run — it was "
                "dropped or renamed and its rejection path is no longer exercised."
                % name)
            continue

        overall = r.get("overall")
        is_pass = bool(r.get("pass"))
        signals = r.get("policy_signals")

        if is_pass or not (isinstance(overall, (int, float)) and overall < PASS_THRESHOLD):
            problems.append(
                "negative control '%s' did NOT fail (pass=%s, overall=%s) — its guard "
                "stopped firing (e.g. the oversized blob shrank below 1MB, or the "
                "threat/approval gate was neutered)." % (name, is_pass, overall))

        if not (isinstance(signals, list) and len(signals) > 0):
            problems.append(
                "negative control '%s' has an EMPTY policy_signals list — it is no "
                "longer tripping any rejection path." % name)
            continue

        fams = _families_of(signals)
        if expected_family not in fams:
            problems.append(
                "negative control '%s' fired families %s but its expected DISTINCT "
                "rejection family is '%s' — its rejection path changed or collapsed "
                "onto another control's." % (name, sorted(fams), expected_family))

        # No two controls may rely on the SAME family — that is a collapse.
        for fam in fams:
            prior = family_owner.get(fam)
            if prior is not None and prior != name:
                problems.append(
                    "negative controls '%s' and '%s' both fail via the '%s' signal "
                    "family — two controls collapsed onto the SAME rejection path "
                    "(they must be distinct)." % (prior, name, fam))
            else:
                family_owner.setdefault(fam, name)

        # No two controls may have an IDENTICAL signal list (a duplicate).
        sigset = frozenset(s for s in signals if isinstance(s, str))
        prior_set = signalset_owner.get(sigset)
        if prior_set is not None and prior_set != name:
            problems.append(
                "negative controls '%s' and '%s' have IDENTICAL policy_signals %s — a "
                "duplicated rejection signal list, not distinct."
                % (prior_set, name, sorted(sigset)))
        else:
            signalset_owner.setdefault(sigset, name)

        # No two controls may SHARE even a single individual signal.
        for s in signals:
            if not isinstance(s, str):
                continue
            prior_sig = signal_owner.get(s)
            if prior_sig is not None and prior_sig != name:
                problems.append(
                    "negative controls '%s' and '%s' SHARE the policy signal '%s' — "
                    "their rejection paths overlap instead of being distinct."
                    % (prior_sig, name, s))
            else:
                signal_owner.setdefault(s, name)

    return (len(problems) == 0), problems


def validate(run: dict):
    """Combined guard decision: the generic contract (>=1 pass AND >=1
    policy-rejected fail) AND the per-negative-control distinct-family contract.
    Returns (ok: bool, problems: list[str])."""
    ok1, p1 = validate_run(run)
    ok2, p2 = validate_negative_controls(run)
    return (ok1 and ok2), (p1 + p2)


def _normalize_recorded_run(rec: dict) -> dict:
    """Map a recorded eval-arena history SUMMARY into the shape validate_run()
    expects.

    History summaries (the `/api/a11oy/v1/eval-arena/history` ring entries) keep
    their per-scenario rows under `scenarios` (not `results`), each carrying
    `scenario`/`overall`/`pass` and the deterministic, non-secret
    `policy_signals` labels. Renaming `scenarios`->`results` lets the SAME pure
    validator that guards the live run also guard the recorded timeline — so a
    degraded recorded summary that dropped its policy-rejected negative control
    is caught instead of quietly painting an all-green history strip. No I/O.
    """
    if not isinstance(rec, dict):
        return {"results": []}
    scenarios = rec.get("scenarios")
    if not isinstance(scenarios, list):
        return {"results": []}
    results = []
    for s in scenarios:
        if not isinstance(s, dict):
            continue
        results.append({
            "scenario": s.get("scenario"),
            "overall": s.get("overall"),
            "pass": s.get("pass"),
            "policy_signals": s.get("policy_signals"),
        })
    return {"results": results}


def _pick_latest_recorded(runs):
    """Return the newest recorded run summary from a history `runs` list (the
    ring/`/history` payload is ordered newest-LAST), or None when empty."""
    if not isinstance(runs, list) or not runs:
        return None
    return runs[-1]


def _validate_recorded_runs(runs):
    """Pure batch validator over a history `runs` list: run the combined
    `validate()` on EVERY recorded summary and return (ok, problems).

    Validating only the latest run (see `_pick_latest_recorded`) would miss a
    degraded EARLIER run that still renders a cell in the console trend strip —
    the exact blind spot this guard closes. A single failing run ANYWHERE in the
    ring fails the batch. An empty list is a soft pass (the caller decides
    whether an empty ring should SKIP). No I/O, no fabrication.
    """
    problems: list[str] = []
    for idx, rec in enumerate(runs or []):
        ok, probs = validate(_normalize_recorded_run(rec))
        if not ok:
            rid = (rec.get("run_id") if isinstance(rec, dict) else None) or ("index %d" % idx)
            problems.extend("[recorded run %s] %s" % (rid, p) for p in probs)
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

    # ---- per-negative-control distinct-rejection-path validator --------------
    # Each declared control must FAIL via its OWN expected, distinct family. The
    # fixtures below prove the layer-2 validator rejects the two regressions this
    # task closes ("two controls share one signal" and "a guard stopped firing")
    # plus empty/missing/duplicate signal lists, and accepts a clean run.
    nc_inj = {"scenario": "adversarial-injection-negative-control", "overall": 0.50,
              "pass": False, "policy_signals": ["ignore previous", "exfiltrate", "rm -rf"]}
    nc_size = {"scenario": "oversized-payload-negative-control", "overall": 0.60,
               "pass": False, "policy_signals": ["size-guard:payload-exceeds-1MB"]}
    nc_appr = {"scenario": "missing-operator-approval-negative-control", "overall": 0.62,
               "pass": False,
               "policy_signals": ["approval-guard:operator-approval-required-for-high-impact-action"]}
    ok_row = {"scenario": "health-check-chain", "overall": 0.95, "pass": True,
              "policy_signals": []}

    def _nc_run(*rows):
        return {"results": [dict(r) for r in rows]}

    nc_good = _nc_run(ok_row, nc_inj, nc_size, nc_appr)

    # REGRESSION 1: two controls SHARE one signal — the oversized-payload control
    # additionally fires the injection control's "exfiltrate" threat signature, so
    # the two collapse onto the threat-sigs family. Must be REJECTED.
    nc_shared_signal = _nc_run(
        ok_row, nc_inj,
        {"scenario": "oversized-payload-negative-control", "overall": 0.60, "pass": False,
         "policy_signals": ["size-guard:payload-exceeds-1MB", "exfiltrate"]},
        nc_appr)

    # REGRESSION 2: a guard STOPPED firing — the oversized blob shrank below 1MB,
    # so its control no longer trips anything and now PASSES with empty signals.
    nc_guard_stopped = _nc_run(
        ok_row, nc_inj,
        {"scenario": "oversized-payload-negative-control", "overall": 0.93, "pass": True,
         "policy_signals": []},
        nc_appr)

    # A control fails but with an EMPTY signal list (no rejection path recorded).
    nc_empty_signals = _nc_run(
        ok_row, nc_inj, nc_size,
        {"scenario": "missing-operator-approval-negative-control", "overall": 0.62,
         "pass": False, "policy_signals": []})

    # A declared control is MISSING entirely (dropped/renamed).
    nc_missing = _nc_run(ok_row, nc_inj, nc_size)

    # Two controls have an IDENTICAL signal list (duplicate, not distinct).
    nc_dup_list = _nc_run(
        ok_row, nc_inj,
        {"scenario": "oversized-payload-negative-control", "overall": 0.50, "pass": False,
         "policy_signals": ["ignore previous", "exfiltrate", "rm -rf"]},
        nc_appr)

    # A control fires the WRONG family (oversized fires only a threat sig, not the
    # size guard) — its expected distinct rejection path is gone.
    nc_wrong_family = _nc_run(
        ok_row, nc_inj,
        {"scenario": "oversized-payload-negative-control", "overall": 0.50, "pass": False,
         "policy_signals": ["drop table"]},
        nc_appr)

    nc_cases = [
        ("neg-controls: clean distinct-family run is accepted", nc_good, True),
        ("neg-controls: two controls sharing one signal is rejected",
         nc_shared_signal, False),
        ("neg-controls: a guard that stopped firing is rejected",
         nc_guard_stopped, False),
        ("neg-controls: empty signal list is rejected", nc_empty_signals, False),
        ("neg-controls: missing declared control is rejected", nc_missing, False),
        ("neg-controls: duplicate signal list is rejected", nc_dup_list, False),
        ("neg-controls: wrong/collapsed family is rejected", nc_wrong_family, False),
    ]
    for name, run, expect_ok in nc_cases:
        ok, problems = validate_negative_controls(run)
        status = "PASS" if ok == expect_ok else "FAIL"
        if ok != expect_ok:
            failures += 1
        print("  [%s] %s (validator ok=%s, expected ok=%s)%s"
              % (status, name, ok, expect_ok,
                 "" if ok == expect_ok else " :: " + "; ".join(problems)))

    # The combined validate() must accept the clean run and reject each regression.
    for name, run, expect_ok in [
            ("combined: clean run accepted", nc_good, True),
            ("combined: shared-signal run rejected", nc_shared_signal, False),
            ("combined: stopped-guard run rejected", nc_guard_stopped, False)]:
        ok, problems = validate(run)
        status = "PASS" if ok == expect_ok else "FAIL"
        if ok != expect_ok:
            failures += 1
        print("  [%s] %s (validator ok=%s, expected ok=%s)%s"
              % (status, name, ok, expect_ok,
                 "" if ok == expect_ok else " :: " + "; ".join(problems)))

    # ---- recorded-run path: normalize a history SUMMARY then validate it -----
    # History summaries store rows under `scenarios` (not `results`); the SAME
    # combined validator must catch a degraded recorded timeline. The recorded
    # summaries mirror the real arena's scenario names so the per-control checks
    # apply to the history strip exactly as they do to the live run.
    good_recorded = {
        "run_id": "arena-live-1", "timestamp": "2026-06-10T00:00:00Z",
        "scenarios": [dict(ok_row), dict(nc_inj), dict(nc_size), dict(nc_appr)],
    }
    # The exact degradation this task closes: the recorded summary kept the
    # green rows but dropped a negative control's policy_signals.
    degraded_recorded_no_signals = {
        "scenarios": [
            dict(ok_row), dict(nc_inj), dict(nc_size),
            {"scenario": "missing-operator-approval-negative-control", "overall": 0.62,
             "pass": False, "policy_signals": []},
        ],
    }
    # A recorded summary where a guard stopped firing (oversized control passes).
    degraded_recorded_stopped = {
        "scenarios": [
            dict(ok_row), dict(nc_inj),
            {"scenario": "oversized-payload-negative-control", "overall": 0.93,
             "pass": True, "policy_signals": []},
            dict(nc_appr),
        ],
    }
    all_green_recorded = {
        "scenarios": [
            {"scenario": "ok-1", "overall": 0.95, "pass": True, "policy_signals": []},
            {"scenario": "ok-2", "overall": 0.91, "pass": True, "policy_signals": []},
        ],
    }
    recorded_cases = [
        ("recorded: good summary is accepted", good_recorded, True),
        ("recorded: dropped-signals negative control is rejected",
         degraded_recorded_no_signals, False),
        ("recorded: a guard that stopped firing is rejected",
         degraded_recorded_stopped, False),
        ("recorded: all-green summary is rejected", all_green_recorded, False),
    ]
    for name, rec, expect_ok in recorded_cases:
        ok, problems = validate(_normalize_recorded_run(rec))
        status = "PASS" if ok == expect_ok else "FAIL"
        if ok != expect_ok:
            failures += 1
        print("  [%s] %s (validator ok=%s, expected ok=%s)%s"
              % (status, name, ok, expect_ok,
                 "" if ok == expect_ok else " :: " + "; ".join(problems)))

    # honest empty-history handling: no recorded run -> skip, never fabricate
    pick_cases = [
        ("recorded: empty history yields no latest (-> skip)", [], None),
        ("recorded: latest is the newest (last) entry",
         [good_recorded, all_green_recorded], all_green_recorded),
    ]
    for name, runs, expect in pick_cases:
        got = _pick_latest_recorded(runs)
        ok = (got is expect) or (got == expect)
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print("  [%s] %s" % (status, name))

    # ---- all-recorded-runs path: a degraded run ANYWHERE fails the batch -----
    # The property this task adds. Validating only the LATEST recorded run would
    # green-light a history whose newest cell is fine but an EARLIER cell dropped
    # its negative control or had a guard stop firing. _validate_recorded_runs
    # must catch a degraded run at ANY position in the ring.
    all_runs_good = [good_recorded, good_recorded]
    all_runs_early_degraded = [degraded_recorded_no_signals, good_recorded]
    all_runs_late_degraded = [good_recorded, degraded_recorded_stopped]
    all_runs_mixed = [good_recorded, degraded_recorded_no_signals, good_recorded]
    allrec_cases = [
        ("all-recorded: every run good is accepted", all_runs_good, True),
        ("all-recorded: a degraded EARLIER run (latest good) is rejected",
         all_runs_early_degraded, False),
        ("all-recorded: a degraded LATEST run is rejected",
         all_runs_late_degraded, False),
        ("all-recorded: a degraded MIDDLE run is rejected",
         all_runs_mixed, False),
        ("all-recorded: empty history is a soft pass (caller skips)", [], True),
    ]
    for name, _runs, expect_ok in allrec_cases:
        ok, problems = _validate_recorded_runs(_runs)
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
    print("\nself-test OK: validator rejects every degenerate run (live AND "
          "recorded) and accepts the good ones.")
    return 0


def _check_recorded(argv_json: bool = False) -> int:
    """Load EVERY RECORDED eval-arena run from the in-image history ring and
    validate each one with the same validator used for the live run.

    The ring is seeded by real live runs. In a fresh CI checkout it starts
    empty, so we perform ONE genuine live eval (which legitimately appends a
    recorded summary the same way production does) and then read it back — we
    never synthesize a fake summary. If, even then, no recorded run exists, we
    SKIP with a soft pass rather than fabricate one.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        import serve  # noqa: E402  (real in-image module)
    except Exception as exc:  # noqa: BLE001
        print("::error::failed to import serve.py for recorded-run check: %r" % exc,
              file=sys.stderr)
        return 2

    try:
        runs = list(serve._A11OY_EVAL_HIST)
        if not runs:
            # seed the ring the legitimate way: one real live run appends a summary
            serve._a11oy_eval_run_live()
            runs = list(serve._A11OY_EVAL_HIST)
    except Exception as exc:  # noqa: BLE001
        print("::error::failed to read the recorded eval-arena history: %r" % exc,
              file=sys.stderr)
        return 2

    if not runs:
        print("Recorded eval-arena history is empty — no recorded run to "
              "validate. SKIPPING (soft pass; nothing fabricated).")
        return 0

    # Validate EVERY recorded run in the ring, not just the latest: a degraded
    # run ANYWHERE in the history still paints a cell in the console trend strip,
    # so the guard must fail if ANY recorded run fails the contract. (Validating
    # only _pick_latest_recorded() would green-light a degraded EARLIER run.)
    ok, problems = _validate_recorded_runs(runs)
    failed_ids = []
    for idx, rec in enumerate(runs):
        normalized = _normalize_recorded_run(rec)
        rok, _rp = validate(normalized)
        results = normalized.get("results") or []
        rid = (rec.get("run_id") if isinstance(rec, dict) else None) or ("index %d" % idx)
        if not rok:
            failed_ids.append(rid)
        print("Recorded eval-arena run [%d/%d]: %s (%s) — %s scenarios%s"
              % (idx + 1, len(runs), rid,
                 (rec.get("timestamp") if isinstance(rec, dict) else None),
                 len(results), "" if rok else "  <-- FAILED"))
        for r in results:
            print("  - %-38s overall=%-9s pass=%-5s signals=%s"
                  % (r.get("scenario"), r.get("overall"), r.get("pass"),
                     r.get("policy_signals")))

    if argv_json:
        print(json.dumps(
            [{"run_id": (rec.get("run_id") if isinstance(rec, dict) else None),
              "timestamp": (rec.get("timestamp") if isinstance(rec, dict) else None),
              "results": _normalize_recorded_run(rec).get("results") or []}
             for rec in runs], indent=2))

    if not ok:
        for p in problems:
            print("::error::eval-arena recorded-run guard: %s" % p, file=sys.stderr)
        print("\n%d of %d recorded run(s) FAILED the guard: %s"
              % (len(failed_ids), len(runs), ", ".join(failed_ids)), file=sys.stderr)
        return 1

    print("\nGuard OK: ALL %d recorded run(s) keep a passing example AND a "
          "policy-rejected negative control (the history trend strip cannot go "
          "silently all-green at ANY point)." % len(runs))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true",
                    help="run the pure-validator fixtures and exit")
    ap.add_argument("--recorded", action="store_true",
                    help="validate EVERY RECORDED eval-arena run in the history "
                         "ring (soft-skips on empty history)")
    ap.add_argument("--json", action="store_true",
                    help="print the run summary as JSON")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if args.recorded:
        return _check_recorded(argv_json=args.json)

    try:
        run = _run_real_live()
    except Exception as exc:  # noqa: BLE001
        print("::error::failed to run the live eval arena in-image: %r" % exc,
              file=sys.stderr)
        return 2

    ok, problems = validate(run)

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
