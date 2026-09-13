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
from pathlib import Path
from typing import Any, Mapping


def _flag(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() in {"true", "1", "yes"}:
        return True
    return False


def load_plan(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def plan_is_complete_and_approved(plan: Mapping[str, Any] | None) -> bool:
    if not isinstance(plan, Mapping):
        return False
    if plan.get("complete") is not True:
        return False
    if plan.get("approved") is not True:
        return False
    expected = plan.get("expected_source_revision")
    if expected is not None and not (
        isinstance(expected, str) and len(expected) == 40
    ):
        return False
    return True


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
    if plan is not None and not plan_is_complete_and_approved(plan):
        return {
            "dispatch": True,
            "product_scope": True,
            "vertical_flagships": False,
            "vertical_state": "NOT_REQUESTED",
            "reason": "VERTICAL_PLAN_INCOMPLETE_OR_UNAPPROVED",
            "production_authorization": False,
        }
    vertical_authorized = vertical_on
    return {
        "dispatch": True,
        "product_scope": True,
        "vertical_flagships": vertical_authorized,
        "vertical_state": "REQUESTED" if vertical_authorized else "NOT_REQUESTED",
        "reason": "PRODUCT_AND_VERTICAL" if vertical_authorized else "PRODUCT_ONLY",
        "production_authorization": False,
    }


def hf_sync_command(decision: Mapping[str, Any], *, repo: str) -> list[str] | None:
    """Exact gh invocation. Missing dispatch yields None, not a guessed write."""
    if not decision.get("dispatch"):
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
        command.extend(["-f", "publish_vertical_flagships=true"])
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair", default="false")
    parser.add_argument("--vertical-requested", default="false")
    parser.add_argument("--expected-sha", default="")
    parser.add_argument("--current-sha", default="")
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--duplicate-dispatch", default="false")
    parser.add_argument("--github-output", type=Path, default=None)
    parser.add_argument("--repo", default="szl-holdings/a11oy")
    args = parser.parse_args(argv)
    decision = plan_repair_dispatch(
        repair=args.repair,
        vertical_requested=args.vertical_requested,
        current_sha=args.current_sha or None,
        expected_sha=args.expected_sha or None,
        plan=load_plan(args.plan),
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
