#!/usr/bin/env python3
"""Resume a paused canonical Hugging Face Space without reallocating it."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ACTIVE_STAGES = frozenset({"RUNNING", "BUILDING", "RUNNING_BUILDING"})


def _stage(value: object) -> str:
    return str(getattr(value, "value", value) or "UNKNOWN").upper()


def resume_if_paused(api: Any, *, repo_id: str, report: dict[str, object]) -> None:
    runtime = api.get_space_runtime(repo_id=repo_id)
    stage = _stage(getattr(runtime, "stage", None))
    report["observed_stage"] = stage

    if stage == "PAUSED":
        restarted = api.restart_space(repo_id=repo_id, factory_reboot=False)
        response_stage = getattr(
            getattr(restarted, "runtime", None),
            "stage",
            None,
        )
        report["action"] = "RESTART_REQUESTED"
        report["response_stage"] = _stage(response_stage)
        return

    if stage in ACTIVE_STAGES:
        report["action"] = "ALREADY_ACTIVE"
        return

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
        resume_if_paused(api, repo_id=args.repo_id, report=report)
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
