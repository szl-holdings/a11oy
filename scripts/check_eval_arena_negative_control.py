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

Static serve.py <-> guard lockstep (this check)
-----------------------------------------------
The validators above run the REAL eval and can only catch an undeclared (or
renamed) negative control at RUNTIME, and only if that scenario actually
surfaces in a live/recorded run. If someone adds, renames, or removes a negative
control in serve.py's `_A11OY_ARENA_SCENARIOS` without updating
`NEGATIVE_CONTROL_FAMILIES` here, the map can silently go stale. A STATIC check
(`--check-serve`, validator `validate_serve_negative_controls`) closes that gap:
it parses serve.py with `ast` (no import, no serve.py runtime deps, no executing
the oversized-blob builder), extracts every scenario name ending in
`-negative-control` declared in `_A11OY_ARENA_SCENARIOS`, and FAILS unless that
set EXACTLY matches `NEGATIVE_CONTROL_FAMILIES`'s keys — catching BOTH drift
directions: serve.py grew a control the guard doesn't know about, and the guard
declares one serve.py no longer has.

Positive controls (the symmetric blind spot)
--------------------------------------------
Proving each NEGATIVE control genuinely FAILS leaves the opposite regression
unguarded: a governance change that wrongly BLOCKS a legitimate (allowed) action
would paint a quiet red row no check objects to. A third validator
(`validate_positive_controls`) therefore asserts that every ALLOWED scenario
(any result that is not a negative control) PASSES cleanly — `pass=True`,
`overall >= 0.85`, and an EMPTY `policy_signals` list — and that at least one
allowed scenario is present. This catches a spurious threat/size/approval signal
firing on a clean action, or a legitimate scenario slipping below threshold. The
combined `validate()` ANDs all three layers together.

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


def _is_negative_control(name) -> bool:
    """True for a negative-control scenario (declared in NEGATIVE_CONTROL_FAMILIES
    OR following the `-negative-control` naming convention). Everything else is an
    allowed (positive-control) governance-pass scenario."""
    if not isinstance(name, str):
        return False
    return name in NEGATIVE_CONTROL_FAMILIES or name.endswith("-negative-control")


def validate_positive_controls(run: dict):
    """Pure validator (layer 3). Returns (ok: bool, problems: list[str]).

    The SYMMETRIC counterpart to `validate_negative_controls`. The negative
    controls prove the gate REJECTS bad decisions; this proves the gate does NOT
    wrongly BLOCK legitimate ones. Every ALLOWED scenario (any result whose name
    is not a negative control) must PASS cleanly:

      * `pass == True`,
      * `overall >= PASS_THRESHOLD`, AND
      * an EMPTY `policy_signals` list.

    This closes the symmetric blind spot the negative-control checks leave open: a
    governance regression that started FLAGGING a legitimate action (a spurious
    threat/size/approval signal) or that pushed a legitimate scenario BELOW the
    pass threshold would otherwise paint a quiet red row no guard objects to.

    Requires at least one allowed scenario to be present — an arena made of only
    negative controls has no green example proving legitimate actions flow through
    the gate, and the all-fail blind spot would otherwise pass vacuously.
    No I/O, no fabrication — operates on a run dict only.
    """
    problems: list[str] = []
    if not isinstance(run, dict):
        return False, ["run is not an object"]
    results = run.get("results")
    if not isinstance(results, list) or not results:
        return False, ["run has no 'results' list"]

    allowed = 0
    for r in results:
        if not isinstance(r, dict):
            continue
        name = r.get("scenario")
        if _is_negative_control(name):
            continue
        allowed += 1
        overall = r.get("overall")
        is_pass = bool(r.get("pass"))
        signals = r.get("policy_signals")

        if not is_pass or not (isinstance(overall, (int, float)) and overall >= PASS_THRESHOLD):
            problems.append(
                "allowed scenario '%s' did NOT pass cleanly (pass=%s, overall=%s, "
                "threshold=%.2f) — a governance regression is wrongly BLOCKING a "
                "legitimate action." % (name, is_pass, overall, PASS_THRESHOLD))

        if isinstance(signals, list) and len(signals) > 0:
            problems.append(
                "allowed scenario '%s' carries policy_signals %s — the gate FIRED on a "
                "legitimate action (a spurious threat/size/approval signal); it is "
                "wrongly flagging an allowed decision." % (name, signals))
        elif signals is not None and not isinstance(signals, list):
            problems.append(
                "allowed scenario '%s' has a non-list policy_signals (%r)."
                % (name, signals))

    if allowed == 0:
        problems.append(
            "no ALLOWED (positive-control) scenario present — the arena cannot prove "
            "legitimate actions pass the gate (only negative controls exist).")

    return (len(problems) == 0), problems


def validate(run: dict):
    """Combined guard decision: the generic contract (>=1 pass AND >=1
    policy-rejected fail) AND the per-negative-control distinct-family contract
    AND the positive-control contract (legitimate actions are NOT wrongly
    blocked). Returns (ok: bool, problems: list[str])."""
    ok1, p1 = validate_run(run)
    ok2, p2 = validate_negative_controls(run)
    ok3, p3 = validate_positive_controls(run)
    return (ok1 and ok2 and ok3), (p1 + p2 + p3)


_SERVE_SCENARIOS_VAR = "_A11OY_ARENA_SCENARIOS"
_NEGATIVE_CONTROL_SUFFIX = "-negative-control"


def _extract_serve_negative_controls(serve_source: str) -> set:
    """Statically parse serve.py SOURCE and return the set of negative-control
    scenario names declared in `_A11OY_ARENA_SCENARIOS` (every `scenario` value
    ending in `-negative-control`).

    Pure `ast` parse — it never imports serve.py, needs none of its runtime deps,
    and does NOT execute the oversized-blob builder. It reads only the string
    LITERAL `scenario` keys, which is exactly what a static lockstep check needs.

    Raises ValueError if the scenario list cannot be located or is not a list
    literal: a structural change the guard must surface loudly, not silently
    treat as "no negative controls" (which would let real drift slip through).
    """
    import ast

    tree = ast.parse(serve_source)
    scenarios_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == _SERVE_SCENARIOS_VAR:
                    scenarios_node = node.value
                    break
        if scenarios_node is not None:
            break

    if scenarios_node is None:
        raise ValueError(
            "could not find the %s assignment in serve.py — the arena scenario "
            "list moved or was renamed; the static guard cannot verify lockstep."
            % _SERVE_SCENARIOS_VAR)
    if not isinstance(scenarios_node, ast.List):
        raise ValueError(
            "%s is not a list literal (got %s) — the static guard cannot extract "
            "the declared negative controls." % (_SERVE_SCENARIOS_VAR,
                                                 type(scenarios_node).__name__))

    names: set = set()
    for elt in scenarios_node.elts:
        if not isinstance(elt, ast.Dict):
            continue
        for k, v in zip(elt.keys, elt.values):
            if (isinstance(k, ast.Constant) and k.value == "scenario"
                    and isinstance(v, ast.Constant) and isinstance(v.value, str)
                    and v.value.endswith(_NEGATIVE_CONTROL_SUFFIX)):
                names.add(v.value)
    return names


def validate_serve_negative_controls(declared, families):
    """Pure validator (static lockstep). Returns (ok: bool, problems: list[str]).

    The negative-control scenario names DECLARED in serve.py (`declared`, a set
    from `_extract_serve_negative_controls`) must EXACTLY match the keys of
    `NEGATIVE_CONTROL_FAMILIES` (`families`). Catches BOTH drift directions:

      * serve.py declares a control the guard's map does NOT know about (a new or
        renamed negative control whose rejection path is now unguarded), and
      * the guard's map declares a control serve.py no longer has (dropped or
        renamed — the map went stale).

    No I/O — operates on the two collections only.
    """
    problems: list[str] = []
    declared = set(declared)
    known = set(families.keys())

    for name in sorted(declared - known):
        problems.append(
            "serve.py declares negative control '%s' but the guard's "
            "NEGATIVE_CONTROL_FAMILIES does not — add it (with its expected, "
            "DISTINCT rejection family) so its rejection path is guarded." % name)
    for name in sorted(known - declared):
        problems.append(
            "NEGATIVE_CONTROL_FAMILIES declares '%s' but serve.py no longer "
            "declares a scenario by that name — it was dropped or renamed; update "
            "the guard's map in lockstep so it does not silently go stale." % name)

    return (len(problems) == 0), problems


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

    # ---- positive-control validator: legit actions must NOT be wrongly blocked
    # The SYMMETRIC guard. validate_negative_controls proves bad actions are
    # REJECTED; these fixtures prove a governance regression that wrongly FLAGS or
    # BLOCKS a legitimate (allowed) scenario is caught. Reuses the real allowed
    # scenario names so the check applies exactly as it does to the live run.
    pos_a = {"scenario": "health-check-chain", "overall": 0.95, "pass": True,
             "policy_signals": []}
    pos_b = {"scenario": "maritime-delay-cascade", "overall": 0.90, "pass": True,
             "policy_signals": []}

    pc_good = _nc_run(pos_a, pos_b, nc_inj, nc_size, nc_appr)

    # REGRESSION A: a legitimate action got wrongly FLAGGED — the allowed scenario
    # now carries a spurious policy signal (the gate fired on a clean action).
    pc_wrongly_flagged = _nc_run(
        {"scenario": "health-check-chain", "overall": 0.91, "pass": True,
         "policy_signals": ["exfiltrate"]},
        pos_b, nc_inj, nc_size, nc_appr)

    # REGRESSION B: a legitimate action was wrongly BLOCKED — the allowed scenario
    # slipped below the pass threshold and now FAILS though nothing is malicious.
    pc_wrongly_blocked = _nc_run(
        {"scenario": "health-check-chain", "overall": 0.40, "pass": False,
         "policy_signals": []},
        pos_b, nc_inj, nc_size, nc_appr)

    # Only negative controls present — no allowed scenario proves legit flow.
    pc_no_allowed = _nc_run(nc_inj, nc_size, nc_appr)

    pc_cases = [
        ("pos-controls: clean allowed scenarios are accepted", pc_good, True),
        ("pos-controls: a wrongly-FLAGGED legit action is rejected",
         pc_wrongly_flagged, False),
        ("pos-controls: a wrongly-BLOCKED legit action is rejected",
         pc_wrongly_blocked, False),
        ("pos-controls: no allowed scenario present is rejected",
         pc_no_allowed, False),
    ]
    for name, run, expect_ok in pc_cases:
        ok, problems = validate_positive_controls(run)
        status = "PASS" if ok == expect_ok else "FAIL"
        if ok != expect_ok:
            failures += 1
        print("  [%s] %s (validator ok=%s, expected ok=%s)%s"
              % (status, name, ok, expect_ok,
                 "" if ok == expect_ok else " :: " + "; ".join(problems)))

    # The combined validate() must ALSO reject a wrongly-flagged / wrongly-blocked
    # legit action even though the negative controls are all healthy.
    for name, run, expect_ok in [
            ("combined: clean positive+negative run accepted", pc_good, True),
            ("combined: wrongly-flagged legit action rejected",
             pc_wrongly_flagged, False),
            ("combined: wrongly-blocked legit action rejected",
             pc_wrongly_blocked, False)]:
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

    # ---- static serve.py <-> guard lockstep validator ----------------------
    # The property THIS task adds: a STATIC check that the negative controls
    # declared in serve.py's _A11OY_ARENA_SCENARIOS match NEGATIVE_CONTROL_FAMILIES
    # exactly. The fixtures below prove BOTH drift directions are caught (serve.py
    # has a control the guard doesn't, and vice-versa) plus the matching case,
    # exercising the same ast extractor the live check uses on a tiny synthetic
    # serve module so a regression fails loudly here before the real source.
    serve_src_matching = (
        "_A11OY_ARENA_SCENARIOS = [\n"
        "    {'scenario': 'health-check-chain', 'action': {}},\n"
        "    {'scenario': 'adversarial-injection-negative-control', 'action': {}},\n"
        "    {'scenario': 'oversized-payload-negative-control', 'action': {}},\n"
        "    {'scenario': 'missing-operator-approval-negative-control', 'action': {}},\n"
        "]\n")
    # serve.py grew a NEW control the guard's map doesn't know about.
    serve_src_extra_in_serve = (
        "_A11OY_ARENA_SCENARIOS = [\n"
        "    {'scenario': 'health-check-chain', 'action': {}},\n"
        "    {'scenario': 'adversarial-injection-negative-control', 'action': {}},\n"
        "    {'scenario': 'oversized-payload-negative-control', 'action': {}},\n"
        "    {'scenario': 'missing-operator-approval-negative-control', 'action': {}},\n"
        "    {'scenario': 'sql-injection-negative-control', 'action': {}},\n"
        "]\n")
    # serve.py DROPPED/renamed a control the guard's map still declares.
    serve_src_missing_in_serve = (
        "_A11OY_ARENA_SCENARIOS = [\n"
        "    {'scenario': 'health-check-chain', 'action': {}},\n"
        "    {'scenario': 'adversarial-injection-negative-control', 'action': {}},\n"
        "    {'scenario': 'oversized-payload-negative-control', 'action': {}},\n"
        "]\n")

    families = NEGATIVE_CONTROL_FAMILIES

    # The extractor must pull exactly the three -negative-control names (not the
    # allowed health-check-chain scenario) from the matching source.
    extracted = _extract_serve_negative_controls(serve_src_matching)
    extract_ok = (extracted == set(families.keys()))
    status = "PASS" if extract_ok else "FAIL"
    if not extract_ok:
        failures += 1
    print("  [%s] serve-static: ast extractor pulls exactly the declared "
          "negative controls (got %s)" % (status, sorted(extracted)))

    serve_static_cases = [
        ("serve-static: matching serve.py & guard map is accepted",
         serve_src_matching, True),
        ("serve-static: a control in serve.py the guard lacks is rejected",
         serve_src_extra_in_serve, False),
        ("serve-static: a control the guard has but serve.py dropped is rejected",
         serve_src_missing_in_serve, False),
    ]
    for name, src, expect_ok in serve_static_cases:
        declared = _extract_serve_negative_controls(src)
        ok, problems = validate_serve_negative_controls(declared, families)
        status = "PASS" if ok == expect_ok else "FAIL"
        if ok != expect_ok:
            failures += 1
        print("  [%s] %s (validator ok=%s, expected ok=%s)%s"
              % (status, name, ok, expect_ok,
                 "" if ok == expect_ok else " :: " + "; ".join(problems)))

    # The extractor must FAIL LOUDLY (ValueError) on a structural change rather
    # than silently report "no negative controls" (which would mask real drift).
    for name, bad_src in [
            ("serve-static: missing scenario list raises", "X = 1\n"),
            ("serve-static: non-list scenario var raises",
             "_A11OY_ARENA_SCENARIOS = {'scenario': 'x-negative-control'}\n")]:
        raised = False
        try:
            _extract_serve_negative_controls(bad_src)
        except ValueError:
            raised = True
        status = "PASS" if raised else "FAIL"
        if not raised:
            failures += 1
        print("  [%s] %s" % (status, name))

    if failures:
        print("\nself-test FAILED: validator is not enforcing the contract.",
              file=sys.stderr)
        return 1
    print("\nself-test OK: validator rejects every degenerate run (live AND "
          "recorded), the static serve.py<->guard lockstep holds, and accepts "
          "the good ones.")
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


def _check_static_serve() -> int:
    """STATIC lockstep check: parse serve.py with `ast` and assert the
    negative-control scenarios it declares in `_A11OY_ARENA_SCENARIOS` EXACTLY
    match the keys of `NEGATIVE_CONTROL_FAMILIES`.

    Unlike the live/recorded checks this needs NO serve.py runtime deps and does
    not import or execute serve.py — it reads the source as text and inspects the
    string literals. It catches a stale map the moment a control is added,
    renamed, or removed, even if that scenario never surfaces in a run.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    serve_path = os.path.join(repo_root, "serve.py")
    try:
        with open(serve_path, "r", encoding="utf-8") as fh:
            source = fh.read()
    except OSError as exc:
        print("::error::cannot read serve.py for the static lockstep check: %r"
              % exc, file=sys.stderr)
        return 2

    try:
        declared = _extract_serve_negative_controls(source)
    except (ValueError, SyntaxError) as exc:
        print("::error::static parse of serve.py failed: %s" % exc, file=sys.stderr)
        return 2

    ok, problems = validate_serve_negative_controls(declared, NEGATIVE_CONTROL_FAMILIES)

    print("Static lockstep check (serve.py <-> NEGATIVE_CONTROL_FAMILIES):")
    print("  serve.py declares %d negative control(s): %s"
          % (len(declared), ", ".join(sorted(declared)) or "(none)"))
    print("  guard map declares %d: %s"
          % (len(NEGATIVE_CONTROL_FAMILIES),
             ", ".join(sorted(NEGATIVE_CONTROL_FAMILIES))))

    if not ok:
        for p in problems:
            print("::error::eval-arena negative-control STATIC guard: %s" % p,
                  file=sys.stderr)
        return 1

    print("\nStatic guard OK: serve.py's negative controls and the guard's "
          "NEGATIVE_CONTROL_FAMILIES are in lockstep.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true",
                    help="run the pure-validator fixtures and exit")
    ap.add_argument("--recorded", action="store_true",
                    help="validate EVERY RECORDED eval-arena run in the history "
                         "ring (soft-skips on empty history)")
    ap.add_argument("--check-serve", action="store_true",
                    help="STATIC: parse serve.py and assert its declared negative "
                         "controls match NEGATIVE_CONTROL_FAMILIES (no serve.py "
                         "import / runtime deps)")
    ap.add_argument("--json", action="store_true",
                    help="print the run summary as JSON")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if args.check_serve:
        return _check_static_serve()

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
