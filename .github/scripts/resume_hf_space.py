#!/usr/bin/env python3
"""Resume a paused canonical Hugging Face Space without reallocating it."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ACTIVE_STAGES = frozenset({"RUNNING", "BUILDING", "RUNNING_BUILDING"})
STARTING_STAGE = "RUNNING_APP_STARTING"
STARTING_RECHECKS = 12
STARTING_RECHECK_SECONDS = 10


def _stage(value: object) -> str:
    return str(getattr(value, "value", value) or "UNKNOWN").upper()


def _request_restart(api: Any, *, repo_id: str, report: dict[str, object]) -> None:
    restarted = api.restart_space(repo_id=repo_id, factory_reboot=False)
    response_stage = getattr(
        getattr(restarted, "runtime", None),
        "stage",
        None,
    )
    report["response_stage"] = _stage(response_stage)


def resume_if_paused(
    api: Any,
    *,
    repo_id: str,
    report: dict[str, object],
) -> None:
    if repo_id != "SZLHOLDINGS/a11oy":
        raise RuntimeError("only the canonical A11oy Space is admitted")
    runtime = api.get_space_runtime(repo_id=repo_id)
    stage = _stage(getattr(runtime, "stage", None))
    report["observed_stage"] = stage

    if stage == "PAUSED":
        _request_restart(api, repo_id=repo_id, report=report)
        report["action"] = "RESTART_REQUESTED"
        return

    if stage in ACTIVE_STAGES:
        report["action"] = "ALREADY_ACTIVE"
        return

    if stage == STARTING_STAGE:
        # A previous publish can still be starting when this queued source runs.
        # Observe only this known transition; never restart or reallocate it.
        for attempt in range(1, STARTING_RECHECKS + 1):
            time.sleep(STARTING_RECHECK_SECONDS)
            runtime = api.get_space_runtime(repo_id=repo_id)
            stage = _stage(getattr(runtime, "stage", None))
            report["rechecks"] = attempt
            report["final_stage"] = stage
            if stage in ACTIVE_STAGES:
                report["action"] = "ALREADY_ACTIVE"
                return
            if stage != STARTING_STAGE:
                break
        raise RuntimeError(f"canonical Space did not become active after rechecks: {stage}")

    raise RuntimeError(f"canonical Space is neither paused nor active: {stage}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    report: dict[str, object] = {
        "schema": "szl.hf-space-resume/v1",
        "repo_id": args.repo_id,
        "action": "NOT_RUN",
        "factory_reboot": False,
        "allocation_changed": False,
    }
    try:
        from huggingface_hub import HfApi

        api = HfApi(token=os.environ["HF_TOKEN"])
        resume_if_paused(
            api,
            repo_id=args.repo_id,
            report=report,
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
        print("ERROR: canonical Space resume failed", file=sys.stderr)
        raise SystemExit(1)
