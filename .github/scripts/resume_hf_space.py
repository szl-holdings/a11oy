#!/usr/bin/env python3
"""Classify the canonical Hugging Face Space before a deploy, never restarting it.

The deploy path starts the new revision once. A serving Space is rebuilt by the
deploy commit itself. A crashed or failed-build Space must never block the
deploy that repairs it; the publisher restarts it after publication, because an
unchanged payload creates no commit and so no rebuild. A PAUSED, SLEEPING or
STOPPED Space does not start on a commit; the publisher starts it once, after
the commit has landed, so the old revision never runs alongside the new one. This helper therefore only reads the runtime
stage and reports what the deploy must do; it has no provider write path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

CANONICAL_SPACE = "SZLHOLDINGS/a11oy"
SERVING_STAGE = "RUNNING"
ACTIVE_STAGES = frozenset({SERVING_STAGE, "BUILDING", "RUNNING_BUILDING"})
# Exactly what a deploy repairs. A new commit triggers a fresh build, but an
# unchanged payload creates no commit, so the publisher also restarts it once
# after publication; no healthy writer is running in these stages.
REPAIRABLE_STAGES = frozenset({"RUNTIME_ERROR", "BUILD_ERROR"})
PAUSED_STAGE = "PAUSED"
# Not serving and not started by a commit: started once after publication.
IDLE_STAGES = frozenset({PAUSED_STAGE, "SLEEPING", "STOPPED"})
STARTING_STAGES = frozenset({"RUNNING_APP_STARTING", "APP_STARTING"})
STARTING_RECHECKS = 12
STARTING_RECHECK_SECONDS = 10


def _stage(value: object) -> str:
    return str(getattr(value, "value", value) or "UNKNOWN").upper()


def _decide(stage: str, report: dict[str, object]) -> dict[str, str] | None:
    """Return the deploy decision for a settled stage, or None if unsettled."""
    if stage in IDLE_STAGES:
        report["action"] = "START_AFTER_PUBLICATION"
        return {"restart_required": "true", "converge": "false"}
    if stage in ACTIVE_STAGES:
        report["action"] = "ALREADY_ACTIVE"
        # Only a serving runtime can prove its installed authority, which
        # configuration convergence requires before it writes anything.
        converge = "true" if stage == SERVING_STAGE else "false"
        return {"restart_required": "false", "converge": converge}
    if stage in REPAIRABLE_STAGES:
        report["action"] = "REBUILD_ON_PUBLICATION"
        return {"restart_required": "true", "converge": "false"}
    return None


def classify_runtime(
    api: Any,
    *,
    repo_id: str,
    report: dict[str, object],
) -> dict[str, str]:
    """Read the runtime stage and decide how the single deploy start happens."""
    if repo_id != CANONICAL_SPACE:
        raise RuntimeError("only the canonical A11oy Space is admitted")
    runtime = api.get_space_runtime(repo_id=repo_id)
    stage = _stage(getattr(runtime, "stage", None))
    report["observed_stage"] = stage

    if stage in STARTING_STAGES:
        # A previous publish can still be starting. Observe it settle without
        # any provider effect; a start that never settles is crash-looping,
        # which is exactly what the deploy commit repairs.
        for attempt in range(1, STARTING_RECHECKS + 1):
            time.sleep(STARTING_RECHECK_SECONDS)
            runtime = api.get_space_runtime(repo_id=repo_id)
            stage = _stage(getattr(runtime, "stage", None))
            report["rechecks"] = attempt
            report["final_stage"] = stage
            if stage not in STARTING_STAGES:
                break
        if stage in STARTING_STAGES:
            report["action"] = "REBUILD_ON_PUBLICATION"
            decision = {"restart_required": "true", "converge": "false"}
            report.update(decision)
            return decision

    decision = _decide(stage, report)
    if decision is None:
        raise RuntimeError(f"canonical Space stage is not deployable: {stage}")
    report.update(decision)
    return decision


def write_github_output(path: Path, decision: dict[str, str], stage: str) -> None:
    with path.open("a", encoding="utf-8") as stream:
        for key in ("restart_required", "converge"):
            stream.write(f"{key}={decision[key]}\n")
        # The first observed stage; the deploy-window gate admits PAUSED.
        stream.write(f"stage={stage}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)

    report: dict[str, object] = {
        "schema": "szl.hf-space-preflight/v2",
        "repo_id": args.repo_id,
        "action": "NOT_RUN",
        "provider_writes_performed": False,
        "factory_reboot": False,
        "allocation_changed": False,
    }
    try:
        from huggingface_hub import HfApi

        api = HfApi(token=os.environ["HF_TOKEN"])
        decision = classify_runtime(
            api,
            repo_id=args.repo_id,
            report=report,
        )
        if args.github_output is not None:
            write_github_output(
                args.github_output, decision, str(report["observed_stage"])
            )
    except Exception as exc:
        report["error"] = type(exc).__name__
        raise
    finally:
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("ERROR: canonical Space preflight failed", file=sys.stderr)
        raise SystemExit(1)
