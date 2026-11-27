#!/usr/bin/env python3
"""Staged canary controller: apply, analyze, rollback.

Apply and analyze fail closed when the control plane or metrics are missing.
This script never treats a missing SLO as a pass, and it does not deploy by
itself: a backend must be explicitly configured via RELEASE_CANARY_BACKEND
or config/release-canary.v1.json with enabled=true. Until that exists, apply
refuses so a merge of the workflow cannot shift traffic.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

STAGES = (1, 10, 50, 100)
STATE_VERSION = 1


def fail(message: str) -> None:
    print(f"::error::{message}", file=sys.stderr)
    raise SystemExit(1)


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        env_path = os.environ.get("RELEASE_CANARY_CONFIG", "").strip()
        path = Path(env_path) if env_path else Path("config/release-canary.v1.json")
    if not path.is_file():
        return {"enabled": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fail(f"canary config is not valid JSON: {path}")
    if not isinstance(data, dict):
        fail("canary config must be a JSON object; fails closed.")
    return data


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": STATE_VERSION, "applied_percent": 0, "applied": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fail(f"canary state is not valid JSON: {path}")
    if not isinstance(data, dict):
        fail("canary state must be a JSON object; fails closed.")
    return data


def write_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def require_stage(percent: int) -> None:
    if percent not in STAGES:
        fail(f"percent {percent} is not a allowed stage {STAGES}; fails closed.")


def backend_enabled(config: dict[str, Any]) -> bool:
    if os.environ.get("RELEASE_CANARY_BACKEND", "").strip():
        return True
    return config.get("enabled") is True and bool(str(config.get("backend") or "").strip())


def cmd_apply(args: argparse.Namespace) -> None:
    require_stage(args.percent)
    if not args.canary_ref.strip() or not args.stable_ref.strip():
        fail("canary_ref and stable_ref are required; fails closed.")
    config = load_config(Path(args.config) if args.config else None)
    if not backend_enabled(config):
        fail(
            "canary control plane is not configured (enabled backend missing). "
            "Refusing to claim a traffic shift; fails closed."
        )
    # A real backend hook would go here. None is wired, so even with
    # enabled=true we fail closed until a later change adds a checked adapter.
    fail(
        "canary backend is named but no apply adapter is implemented yet; "
        "fails closed rather than simulating a successful rollout."
    )


def _metric(metrics: dict[str, Any], key: str) -> float:
    value = metrics.get(key)
    if not isinstance(value, (int, float)):
        fail(f"metrics.{key} is missing; analysis fails closed.")
    return float(value)


def cmd_analyze(args: argparse.Namespace) -> None:
    require_stage(args.percent)
    path = Path(args.metrics)
    if not path.is_file():
        fail(f"metrics file is missing for the {args.percent}% stage; analysis fails closed.")
    try:
        metrics = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fail("metrics file is not valid JSON; analysis fails closed.")
    if not isinstance(metrics, dict):
        fail("metrics must be a JSON object; analysis fails closed.")
    config = load_config(Path(args.config) if args.config else None)
    thresholds = config.get("thresholds") if isinstance(config.get("thresholds"), dict) else {}
    # Default fail-closed ceilings / floors. Missing threshold still applies a conservative default.
    max_p95_ms = float(thresholds.get("max_p95_latency_ms", 2000))
    max_error = float(thresholds.get("max_error_rate", 0.01))
    max_refusal_delta = float(thresholds.get("max_refusal_rate_delta", 0.05))
    min_heldout = float(thresholds.get("min_heldout_score", 0.80))
    p95 = _metric(metrics, "p95_latency_ms")
    error_rate = _metric(metrics, "error_rate")
    refusal_rate = _metric(metrics, "refusal_rate")
    baseline_refusal = metrics.get("baseline_refusal_rate", 0.0)
    if not isinstance(baseline_refusal, (int, float)):
        fail("metrics.baseline_refusal_rate is malformed; analysis fails closed.")
    heldout = _metric(metrics, "heldout_score")
    problems = []
    if p95 > max_p95_ms:
        problems.append(f"p95_latency_ms {p95} > {max_p95_ms}")
    if error_rate > max_error:
        problems.append(f"error_rate {error_rate} > {max_error}")
    if (refusal_rate - float(baseline_refusal)) > max_refusal_delta:
        problems.append("refusal_rate rose more than the allowed delta")
    if heldout < min_heldout:
        problems.append(f"heldout_score {heldout} < {min_heldout}")
    if problems:
        fail("canary analysis failed: " + "; ".join(problems))
    print(f"analyze {args.percent}% PASS")
    print(f"  p95_latency_ms={p95} error_rate={error_rate} refusal_rate={refusal_rate} heldout_score={heldout}")


def cmd_rollback(args: argparse.Namespace) -> None:
    if not args.stable_ref.strip():
        fail("stable_ref is required for rollback; fails closed.")
    state_path = Path(args.state)
    state = load_state(state_path)
    if not state.get("applied"):
        print("rollback: nothing applied; no traffic change")
        return
    config = load_config(Path(args.config) if args.config else None)
    if not backend_enabled(config):
        fail(
            "canary traffic was recorded as applied but the control plane is "
            "not configured; cannot confirm rollback. Fails closed."
        )
    fail(
        "canary backend is named but no rollback adapter is implemented yet; "
        "fails closed rather than claiming a successful rollback."
    )


def self_check() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        metrics = root / "metrics.json"
        state = root / "state.json"
        metrics.write_text(
            json.dumps(
                {
                    "p95_latency_ms": 100,
                    "error_rate": 0.0,
                    "refusal_rate": 0.1,
                    "baseline_refusal_rate": 0.1,
                    "heldout_score": 0.85,
                }
            ),
            encoding="utf-8",
        )
        ns = argparse.Namespace(percent=1, metrics=str(metrics), config="")
        cmd_analyze(ns)

        bad = json.loads(metrics.read_text())
        bad.pop("heldout_score")
        metrics.write_text(json.dumps(bad), encoding="utf-8")
        try:
            cmd_analyze(ns)
        except SystemExit:
            pass
        else:
            raise AssertionError("missing heldout_score must fail closed")

        apply_ns = argparse.Namespace(
            percent=1,
            canary_ref="canary",
            stable_ref="stable",
            config="",
        )
        try:
            cmd_apply(apply_ns)
        except SystemExit:
            pass
        else:
            raise AssertionError("unconfigured apply must fail closed")

        # No apply recorded: rollback is a no-op.
        rb = argparse.Namespace(stable_ref="stable", state=str(state), config="")
        cmd_rollback(rb)

        write_state(state, {"version": 1, "applied": True, "applied_percent": 1})
        try:
            cmd_rollback(rb)
        except SystemExit:
            pass
        else:
            raise AssertionError("applied-but-unconfigured rollback must fail closed")

    print("self-check PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    apply_p = sub.add_parser("apply")
    apply_p.add_argument("--percent", type=int, required=True)
    apply_p.add_argument("--canary-ref", required=True)
    apply_p.add_argument("--stable-ref", required=True)
    apply_p.add_argument("--config", default="")
    analyze_p = sub.add_parser("analyze")
    analyze_p.add_argument("--percent", type=int, required=True)
    analyze_p.add_argument("--metrics", required=True)
    analyze_p.add_argument("--config", default="")
    rollback_p = sub.add_parser("rollback")
    rollback_p.add_argument("--stable-ref", required=True)
    rollback_p.add_argument("--state", required=True)
    rollback_p.add_argument("--config", default="")
    sub.add_parser("self-check")
    args = parser.parse_args()
    if args.cmd == "self-check":
        self_check()
    elif args.cmd == "apply":
        cmd_apply(args)
    elif args.cmd == "analyze":
        cmd_analyze(args)
    else:
        cmd_rollback(args)


if __name__ == "__main__":
    main()
