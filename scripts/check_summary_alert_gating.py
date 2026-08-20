#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Guard: prove the release-receipt summary-guard alert never pages on a healthy run.

`release-receipt-summary-guard.yml` ends with a *direct push* alert step
("Alert the team on summary-guard failure") that POSTs to a webhook. It is gated
so it fires ONLY when an earlier audit step actually failed *and* the run was a
real audit (`workflow_run` / `workflow_dispatch`):

    if: ${{ failure() && (github.event_name == 'workflow_run' ||
                          github.event_name == 'workflow_dispatch') }}

That gating is the only thing standing between a single regression and a pager
that fires on every green run — a future edit (changing the `if` to `always()`,
dropping `failure()`, or widening the event guard to `pull_request` / `push`)
would start paging on healthy runs, and nobody would notice until the channel
got noisy. The summary VALIDATOR is already self-tested
(`check_release_receipt_summary.py --selftest`); this script gives the *alert
gating* the same negative-fixture protection.

What it does:
  * extracts the alert step's `if:` expression from the workflow YAML,
  * evaluates it against a fixed CONTRACT of (event, job-status) scenarios using
    a tiny, safe GitHub-Actions expression evaluator (AST-checked — it refuses to
    silently mis-evaluate an expression it does not fully understand),
  * FAILS unless the real workflow matches the contract exactly:
      - real failure on workflow_run / workflow_dispatch  -> pages
      - soft-pass success (checked=0) on workflow_run/dispatch -> does NOT page
      - self-test-only pull_request / push runs (even on failure) -> do NOT page
      - cancelled runs -> do NOT page

`--selftest` proves the auditor itself is honest: a set of *weakened* fixtures
(`always()`, bare `failure()`, `success() && ...`, a widened event guard, a
missing `if:`) must each be REJECTED, and the correct expression must PASS. If a
future edit weakens the gate, both `--audit` (against the real file) and the
negative fixtures catch it loudly.

Exit codes:
  0  the alert gating matches the never-page-on-healthy-run contract
  1  the gating is weakened / missing / mis-shaped (the regression)
  2  usage / environment error
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

DEFAULT_WORKFLOW = ".github/workflows/release-receipt-summary-guard.yml"
ALERT_STEP_NAME = "Alert the team on summary-guard failure"

# The gating contract. Each row is (event_name, job_status, should_page, why).
# `job_status` is the GitHub job-status the status functions reflect at the step:
# 'success' (all prior steps passed), 'failure' (an earlier step failed) or
# 'cancelled'. The alert must page ONLY on the two real-audit failure rows.
CONTRACT: list[tuple[str, str, bool, str]] = [
    ("workflow_run", "failure", True, "real failure on a workflow_run audit must page"),
    ("workflow_dispatch", "failure", True, "real failure on a manual dispatch audit must page"),
    ("workflow_run", "success", False, "soft-pass (checked=0) success path must NOT page"),
    ("workflow_dispatch", "success", False, "manual dispatch success must NOT page"),
    ("pull_request", "failure", False, "PR self-test run must NOT page even if it fails"),
    ("push", "failure", False, "push self-test run must NOT page even if it fails"),
    ("pull_request", "success", False, "PR self-test success must NOT page"),
    ("push", "success", False, "push self-test success must NOT page"),
    ("workflow_run", "cancelled", False, "a cancelled audit run must NOT page"),
    ("workflow_dispatch", "cancelled", False, "a cancelled dispatch run must NOT page"),
]

_ALLOWED_NAMES = {"__status", "__event_name", "True", "False"}


class GatingExprError(ValueError):
    """Raised when an `if:` expression uses syntax this evaluator does not model.

    Failing loud (rather than guessing) is deliberate: if a future edit introduces
    a construct we do not understand, the guard must go RED, not green.
    """


def extract_alert_if(workflow_text: str) -> str:
    """Return the raw `if:` expression of the alert step (``${{ }}`` stripped).

    Raises GatingExprError if the step or its `if:` cannot be located.
    """
    lines = workflow_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*-\s*name:\s*" + re.escape(ALERT_STEP_NAME) + r"\s*$", line):
            start = i
            break
    if start is None:
        raise GatingExprError(
            f"could not find the alert step (- name: {ALERT_STEP_NAME}) in the workflow"
        )
    # Scan within this step block for its `if:`; stop at the next step (`- name:`).
    for line in lines[start + 1:]:
        if re.match(r"^\s*-\s*name:\s*", line):
            break
        m = re.match(r"^\s*if:\s*(.+?)\s*$", line)
        if m:
            return _strip_expr_wrapper(m.group(1))
    raise GatingExprError(
        f"the alert step ({ALERT_STEP_NAME}) has no `if:` — it is UNGATED and would "
        "run on every audit, including healthy ones"
    )


def _strip_expr_wrapper(expr: str) -> str:
    expr = expr.strip()
    # Drop surrounding quotes a YAML author might add around the whole value.
    if len(expr) >= 2 and expr[0] == expr[-1] and expr[0] in {"'", '"'}:
        expr = expr[1:-1].strip()
    if expr.startswith("${{") and expr.endswith("}}"):
        expr = expr[3:-2].strip()
    return expr


def _to_python(expr: str) -> str:
    """Translate the supported GitHub-Actions expression subset to Python source.

    Only the constructs the alert gate uses are modelled: the status functions
    success()/failure()/cancelled()/always(), `github.event_name`, string
    literals, `==`/`!=`, `&&`/`||` and parentheses. Anything else survives the
    translation and is rejected by the AST allow-list below.
    """
    py = expr
    py = re.sub(r"\bsuccess\s*\(\s*\)", "(__status == 'success')", py)
    py = re.sub(r"\bfailure\s*\(\s*\)", "(__status == 'failure')", py)
    py = re.sub(r"\bcancelled\s*\(\s*\)", "(__status == 'cancelled')", py)
    py = re.sub(r"\balways\s*\(\s*\)", "True", py)
    py = re.sub(r"github\s*\.\s*event_name", "__event_name", py)
    py = py.replace("&&", " and ").replace("||", " or ")
    return py


def _eval_node(node: ast.AST, env: dict[str, object]) -> object:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env)
    if isinstance(node, ast.BoolOp):
        vals = [_eval_node(v, env) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(vals)
        if isinstance(node.op, ast.Or):
            return any(vals)
        raise GatingExprError("unsupported boolean operator")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, env)
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1:
            raise GatingExprError("chained comparisons are not supported")
        left = _eval_node(node.left, env)
        right = _eval_node(node.comparators[0], env)
        op = node.ops[0]
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        raise GatingExprError("unsupported comparison operator")
    if isinstance(node, ast.Name):
        if node.id in ("True", "False"):
            return node.id == "True"
        if node.id in env:
            return env[node.id]
        raise GatingExprError(f"unexpected identifier in expression: {node.id!r}")
    if isinstance(node, ast.Constant):
        return node.value
    raise GatingExprError(
        f"unsupported expression construct: {type(node).__name__} "
        "(the evaluator refuses to guess — fix the gate or extend the evaluator)"
    )


def evaluate(expr: str, event_name: str, status: str) -> bool:
    """Return whether the gate would RUN the alert step for (event_name, status)."""
    py = _to_python(expr)
    try:
        tree = ast.parse(py, mode="eval")
    except SyntaxError as exc:  # noqa: BLE001
        raise GatingExprError(f"could not parse expression {expr!r}: {exc}") from exc
    # Reject any identifier outside the allow-list (e.g. an unmodelled function
    # call that survived translation as `foo()` -> ast.Call, or `github.event.*`).
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            raise GatingExprError(
                f"expression {expr!r} contains an unmodelled function call — "
                "refusing to evaluate"
            )
        if isinstance(n, ast.Name) and n.id not in _ALLOWED_NAMES:
            raise GatingExprError(
                f"expression {expr!r} references unknown name {n.id!r}"
            )
        if isinstance(n, ast.Attribute):
            raise GatingExprError(
                f"expression {expr!r} references an unmodelled attribute — "
                "refusing to evaluate"
            )
    return bool(_eval_node(tree, {"__status": status, "__event_name": event_name}))


def audit_expr(expr: str) -> list[str]:
    """Check `expr` against the CONTRACT. Returns a list of violations ([] == ok)."""
    violations: list[str] = []
    for event_name, status, should_page, why in CONTRACT:
        try:
            runs = evaluate(expr, event_name, status)
        except GatingExprError as exc:
            violations.append(f"[{event_name}/{status}] {exc}")
            continue
        if runs != should_page:
            verb = "WOULD PAGE" if runs else "would NOT page"
            want = "page" if should_page else "stay silent"
            violations.append(
                f"[{event_name}/{status}] {verb} but should {want} — {why}"
            )
    return violations


def audit_workflow(path: Path) -> int:
    if not path.exists():
        print(f"::error::workflow file '{path}' does not exist.")
        return 2
    try:
        expr = extract_alert_if(path.read_text(encoding="utf-8"))
    except GatingExprError as exc:
        print(f"::error::{exc}")
        return 1
    violations = audit_expr(expr)
    if violations:
        print(
            "::error::the summary-guard alert gating is WEAKENED — it would page on "
            "healthy runs. Alert `if:` = "
            f"{expr!r}"
        )
        for v in violations:
            print(f"::error::  {v}")
        return 1
    print(
        "[alert-gating] OK: the alert step pages ONLY on a real audit failure "
        "(workflow_run / workflow_dispatch) and never on the soft-pass success "
        "path or on PR/push self-test runs.\n"
        f"[alert-gating] verified `if:` = {expr}"
    )
    return 0


def _selftest() -> int:
    """Prove the auditor accepts the correct gate and rejects weakened ones."""
    failures: list[str] = []

    correct = (
        "failure() && (github.event_name == 'workflow_run' || "
        "github.event_name == 'workflow_dispatch')"
    )

    # Negative fixtures: each MUST produce >=1 contract violation. The trailing
    # note records the specific healthy-run row that should trip.
    weakened: list[tuple[str, str]] = [
        ("always()", "pages on every event/status, including success"),
        (
            "always() && (github.event_name == 'workflow_run' || "
            "github.event_name == 'workflow_dispatch')",
            "drops failure() -> pages on the soft-pass success path",
        ),
        ("failure()", "drops the event guard -> pages on PR/push self-test failures"),
        (
            "success() && (github.event_name == 'workflow_run' || "
            "github.event_name == 'workflow_dispatch')",
            "fires on success not failure -> pages on healthy runs and not real ones",
        ),
        (
            "failure() && (github.event_name == 'workflow_run' || "
            "github.event_name == 'workflow_dispatch' || "
            "github.event_name == 'pull_request')",
            "widened event guard -> pages on PR self-test failures",
        ),
        (
            "failure() && (github.event_name == 'pull_request' || "
            "github.event_name == 'push')",
            "wrong events -> pages on self-test runs, silent on real audits",
        ),
    ]

    # 1. The correct gate must PASS the contract.
    correct_violations = audit_expr(correct)
    if correct_violations:
        failures.append(
            "the CORRECT gate was rejected by the contract: "
            + "; ".join(correct_violations)
        )

    # 2. Every weakened gate must be REJECTED (>=1 violation).
    for expr, note in weakened:
        if not audit_expr(expr):
            failures.append(f"weakened gate accepted (should be rejected): {expr!r} — {note}")

    # 3. Direct evaluator spot-checks (independent of the contract loop).
    spot: list[tuple[str, str, str, bool]] = [
        (correct, "workflow_run", "failure", True),
        (correct, "workflow_dispatch", "failure", True),
        (correct, "workflow_run", "success", False),
        (correct, "pull_request", "failure", False),
        (correct, "push", "failure", False),
        (correct, "workflow_run", "cancelled", False),
        ("always()", "push", "success", True),
    ]
    for expr, ev, st, want in spot:
        got = evaluate(expr, ev, st)
        if got != want:
            failures.append(f"evaluator[{ev}/{st}] of {expr!r} = {got}, expected {want}")

    # 4. Extraction: a missing `if:` and a missing step must both be rejected.
    no_if_workflow = (
        "jobs:\n"
        "  audit:\n"
        "    steps:\n"
        f"      - name: {ALERT_STEP_NAME}\n"
        "        run: echo hi\n"
    )
    try:
        extract_alert_if(no_if_workflow)
        failures.append("extract_alert_if accepted a step with NO `if:` (ungated alert)")
    except GatingExprError:
        pass

    try:
        extract_alert_if("jobs:\n  audit:\n    steps:\n      - name: Something else\n")
        failures.append("extract_alert_if accepted a workflow missing the alert step")
    except GatingExprError:
        pass

    # 5. Extraction + audit on a well-formed synthetic workflow round-trips clean.
    good_workflow = (
        "jobs:\n"
        "  audit:\n"
        "    steps:\n"
        f"      - name: {ALERT_STEP_NAME}\n"
        "        if: ${{ failure() && (github.event_name == 'workflow_run' || "
        "github.event_name == 'workflow_dispatch') }}\n"
        "        run: echo alert\n"
    )
    extracted = extract_alert_if(good_workflow)
    if audit_expr(extracted):
        failures.append("round-trip extraction of the correct gate failed the contract")

    # 6. An unmodelled construct must be REFUSED, not silently passed.
    try:
        evaluate("contains(github.event_name, 'x')", "workflow_run", "failure")
        failures.append("evaluator silently accepted an unmodelled function call")
    except GatingExprError:
        pass

    if failures:
        print("::error::self-test FAILED — the alert-gating guard is not trustworthy:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(
        "[alert-gating] self-test passed: the contract accepts the correct "
        "failure-only gate and rejects always()/bare-failure()/success()/widened-"
        "event/missing-if weakenings; the evaluator refuses unmodelled syntax."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--workflow",
        default=DEFAULT_WORKFLOW,
        help="path to the summary-guard workflow to audit (default: %(default)s)",
    )
    ap.add_argument(
        "--selftest",
        action="store_true",
        help="run built-in positive/negative fixtures and exit (no workflow needed)",
    )
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    return audit_workflow(Path(args.workflow))


if __name__ == "__main__":
    raise SystemExit(main())
