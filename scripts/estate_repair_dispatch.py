#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Decide canonical hf-sync dispatch inputs for an estate repair.

Ordinary product repair never implies six sibling Space publications.
An incomplete or unapproved vertical plan stays NOT_REQUESTED and cannot
become whole-estate PASS. This helper does not dispatch, mutate providers,
or authorize production.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping


def _flag(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() in {"true", "1", "yes"}:
        return True
    return False


SHA40 = re.compile(r"[0-9a-f]{40}")
MAX_PLAN_BYTES = 65_535


def _sha(value: Any) -> bool:
    return isinstance(value, str) and SHA40.fullmatch(value) is not None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate plan key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("non-JSON constant in plan")


def parse_plan(text: str) -> dict[str, Any] | None:
    """Bounded operator input, never executable text or an approval signature."""
    try:
        if len(text.encode("utf-8")) > MAX_PLAN_BYTES:
            return None
        value = json.loads(
            text, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def load_plan(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        if not path.is_file():
            return None
        with path.open("rb") as handle:
            data = handle.read(MAX_PLAN_BYTES + 1)
        if len(data) > MAX_PLAN_BYTES:
            return None
        return parse_plan(data.decode("utf-8"))
    except (OSError, ValueError):
        return None


def plan_is_complete_and_approved(
    plan: Mapping[str, Any] | None, *, expected_sha: str | None = None
) -> bool:
    """Require an operator-declared plan for this exact source, not a boolean alone.

    GitHub's workflow-dispatch permissions remain the caller authority. These
    fields do not independently authenticate an approver or certify readiness.
    The downstream writer rechecks the same plan against its actual checkout.
    """
    return bool(
        isinstance(plan, Mapping)
        and plan.get("complete") is True
        and plan.get("approved") is True
        and _sha(expected_sha)
        and _sha(plan.get("expected_source_revision"))
        and plan.get("expected_source_revision") == expected_sha
    )


def plan_repair_dispatch(
    *,
    repair: Any,
    vertical_requested: Any,
    source_moved: Any = False,
    current_sha: str | None = None,
    expected_sha: str | None = None,
    plan: Mapping[str, Any] | None = None,
    duplicate_dispatch: Any = False,
) -> dict[str, Any]:
    """Return a fail-closed dispatch decision. Never writes remotes."""
    repair_on = _flag(repair)
    vertical_on = _flag(vertical_requested)
    moved = _flag(source_moved)
    if (
        not moved
        and isinstance(current_sha, str)
        and isinstance(expected_sha, str)
        and current_sha
        and expected_sha
        and current_sha != expected_sha
    ):
        moved = True
    if _flag(duplicate_dispatch):
        return {
            "dispatch": False,
            "product_scope": False,
            "vertical_flagships": False,
            "vertical_state": "NOT_REQUESTED",
            "reason": "DUPLICATE_DISPATCH_REFUSED",
            "production_authorization": False,
        }
    if not repair_on:
        return {
            "dispatch": False,
            "product_scope": False,
            "vertical_flagships": False,
            "vertical_state": "NOT_REQUESTED",
            "reason": "REPAIR_NOT_REQUESTED",
            "production_authorization": False,
        }
    if moved:
        return {
            "dispatch": False,
            "product_scope": False,
            "vertical_flagships": False,
            "vertical_state": "NOT_REQUESTED",
            "reason": "SOURCE_MOVED_BEFORE_DISPATCH",
            "production_authorization": False,
        }
    if not _sha(current_sha) or not _sha(expected_sha):
        return {
            "dispatch": False,
            "product_scope": False,
            "vertical_flagships": False,
            "vertical_state": "NOT_REQUESTED",
            "reason": "SOURCE_REVISION_UNAVAILABLE_OR_INVALID",
            "production_authorization": False,
        }
    if vertical_on and not plan_is_complete_and_approved(
        plan, expected_sha=expected_sha
    ):
        return {
            "dispatch": True,
            "product_scope": True,
            "vertical_flagships": False,
            "vertical_state": "NOT_REQUESTED",
            "reason": "VERTICAL_PLAN_INCOMPLETE_OR_UNAPPROVED",
            "production_authorization": False,
        }
    # Forward only the admitted source contract, never arbitrary plan fields.
    # This binds a queued hf-sync invocation even if main moves after dispatch.
    approved_plan = (
        {"complete": True, "approved": True, "expected_source_revision": expected_sha}
        if vertical_on else None
    )
    return {
        "dispatch": True,
        "product_scope": True,
        "vertical_flagships": vertical_on,
        "vertical_state": "REQUESTED" if vertical_on else "NOT_REQUESTED",
        "reason": "PRODUCT_AND_VERTICAL" if vertical_on else "PRODUCT_ONLY",
        "approved_plan": approved_plan,
        "production_authorization": False,
    }


def hf_sync_command(decision: Mapping[str, Any], *, repo: str) -> list[str] | None:
    """Exact gh invocation. Missing dispatch yields None, not a guessed write."""
    if decision.get("dispatch") is not True:
        return None
    command = [
        "gh",
        "workflow",
        "run",
        "hf-sync.yml",
        "--repo",
        repo,
        "--ref",
        "main",
    ]
    if decision.get("vertical_flagships") is True:
        plan = decision.get("approved_plan")
        revision = plan.get("expected_source_revision") if isinstance(plan, Mapping) else None
        if not plan_is_complete_and_approved(plan, expected_sha=revision):
            raise ValueError("vertical command requires the admitted source-bound plan")
        command.extend([
            "-f", "publish_vertical_flagships=true",
            "-f", "vertical_plan_json=" + json.dumps(plan, sort_keys=True),
        ])
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair", default="false")
    parser.add_argument("--vertical-requested", default="false")
    parser.add_argument("--expected-sha", default="")
    parser.add_argument("--current-sha", default="")
    plan_input = parser.add_mutually_exclusive_group()
    plan_input.add_argument("--plan", type=Path, default=None)
    plan_input.add_argument("--plan-from-env", action="store_true")
    parser.add_argument("--require-vertical", action="store_true")
    parser.add_argument("--duplicate-dispatch", default="false")
    parser.add_argument("--github-output", type=Path, default=None)
    parser.add_argument("--repo", default="szl-holdings/a11oy")
    args = parser.parse_args(argv)
    decision = plan_repair_dispatch(
        repair=args.repair,
        vertical_requested=args.vertical_requested,
        current_sha=args.current_sha or None,
        expected_sha=args.expected_sha or None,
        plan=(parse_plan(os.environ.get("VERTICAL_PLAN_JSON", ""))
              if args.plan_from_env else load_plan(args.plan)),
        duplicate_dispatch=args.duplicate_dispatch,
    )
    command = hf_sync_command(decision, repo=args.repo)
    decision = {
        **decision,
        "hf_sync_command": command,
        "not_requested_is_not_pass": True,
    }
    text = json.dumps(decision, sort_keys=True)
    print(text)
    if args.github_output is not None:
        lines = [
            f"dispatch={str(decision['dispatch']).lower()}",
            f"product_scope={str(decision['product_scope']).lower()}",
            f"vertical_flagships={str(decision['vertical_flagships']).lower()}",
            f"vertical_state={decision['vertical_state']}",
            f"reason={decision['reason']}",
        ]
        args.github_output.parent.mkdir(parents=True, exist_ok=True)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    # A denial is still printed/persisted, but the publisher gate must fail.
    return 2 if args.require_vertical and not decision["vertical_flagships"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
