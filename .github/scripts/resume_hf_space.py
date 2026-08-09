#!/usr/bin/env python3
"""Resume a paused canonical Hugging Face Space without reallocating it."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

ACTIVE_STAGES = frozenset({"RUNNING", "BUILDING", "RUNNING_BUILDING"})


def _stage(value: object) -> str:
    return str(getattr(value, "value", value) or "UNKNOWN").upper()


def _hardware(runtime: object) -> str:
    return str(getattr(runtime, "hardware", None) or "").lower()


def _is_cpu_basic_quota_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    return (
        getattr(response, "status_code", None) == 403
        and "cpu-basic quota limit" in str(exc).lower()
    )


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
    capacity_donor: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    capacity_wait_attempts: int = 30,
    capacity_restart_attempts: int = 24,
    capacity_restart_delay: float = 5.0,
) -> None:
    runtime = api.get_space_runtime(repo_id=repo_id)
    stage = _stage(getattr(runtime, "stage", None))
    report["observed_stage"] = stage

    if stage == "PAUSED":
        try:
            _request_restart(api, repo_id=repo_id, report=report)
            report["action"] = "RESTART_REQUESTED"
            return
        except Exception as exc:
            if not capacity_donor or not _is_cpu_basic_quota_error(exc):
                raise

        donor_runtime = api.get_space_runtime(repo_id=capacity_donor)
        donor_stage = _stage(getattr(donor_runtime, "stage", None))
        donor_hardware = _hardware(donor_runtime)
        donor_report: dict[str, object] = {
            "repo_id": capacity_donor,
            "observed_stage": donor_stage,
            "observed_hardware": donor_hardware or None,
            "pause_requested": False,
        }
        report["initial_restart_blocker"] = "CPU_BASIC_QUOTA"
        report["capacity_donor"] = donor_report
        if donor_stage != "RUNNING" or donor_hardware != "cpu-basic":
            raise RuntimeError(
                "capacity donor is not a running cpu-basic Space: "
                f"{capacity_donor} stage={donor_stage} hardware={donor_hardware or 'NONE'}"
            )

        api.pause_space(repo_id=capacity_donor)
        donor_report["pause_requested"] = True
        for _ in range(capacity_wait_attempts):
            observed = api.get_space_runtime(repo_id=capacity_donor)
            observed_stage = _stage(getattr(observed, "stage", None))
            observed_hardware = _hardware(observed)
            donor_report["final_stage"] = observed_stage
            donor_report["final_hardware"] = observed_hardware or None
            if observed_stage == "PAUSED" and not observed_hardware:
                break
            sleep(2.0)
        else:
            raise RuntimeError(
                f"capacity donor did not become unallocated: {capacity_donor}"
            )

        for restart_attempt in range(1, capacity_restart_attempts + 1):
            donor_report["canonical_restart_attempts"] = restart_attempt
            try:
                _request_restart(api, repo_id=repo_id, report=report)
                break
            except Exception as exc:
                if (
                    restart_attempt == capacity_restart_attempts
                    or not _is_cpu_basic_quota_error(exc)
                ):
                    raise
                sleep(capacity_restart_delay)
        report["action"] = "RESTART_REQUESTED_AFTER_CAPACITY_RELEASE"
        return

    if stage in ACTIVE_STAGES:
        report["action"] = "ALREADY_ACTIVE"
        return

    raise RuntimeError(f"canonical Space is neither paused nor active: {stage}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--capacity-donor")
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
            capacity_donor=args.capacity_donor,
        )
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
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
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
