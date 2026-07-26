#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Fail-closed paired vLLM/SGLang benchmark runner.

This runner will not invent results, pick a model, or guess hardware. It emits a
complete BLOCKED cell for every requested matrix entry when prerequisites are
missing, and preserves failures alongside successful measurements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

CLIENT_VERSION = "0.1.0"
CLIENT_DIGEST = "sha256:e2e246dfe34cd603b85e4d763f9aa6d60940be8b9cef48221f8a70d78420716c"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def environment_digest(environment: dict) -> str:
    payload = json.dumps(environment, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def blocked_cell(engine: str, workload: str, repetition: int, reason: str, config: dict) -> dict:
    at = now()
    return {
        "run_id": str(uuid.uuid4()),
        "engine": engine,
        "engine_version": config.get(f"{engine}_version", "0.0.0-blocked"),
        "model_revision": config.get("model_revision", "UNAVAILABLE"),
        "tokenizer_revision": config.get("tokenizer_revision", "UNAVAILABLE"),
        "environment_digest": environment_digest(config),
        "workload": workload,
        "repetition": repetition,
        "status": "BLOCKED",
        "started_at": at,
        "completed_at": at,
        "metrics": {},
        "failure": reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="run the pinned client instead of producing blocked evidence")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    repetitions = int(config.get("repetitions", 0))
    if repetitions < 5:
        raise SystemExit("repetitions must be at least 5")
    matrix = [
        (engine, workload, repetition)
        for engine in ("vllm", "sglang")
        for workload in config.get("workloads", [])
        for repetition in range(1, repetitions + 1)
    ]
    failures = []
    required = ("gpu_node", "model_revision", "tokenizer_revision", "vllm_endpoint", "sglang_endpoint")
    missing = [key for key in required if not config.get(key)]
    client = Path(str(config.get("client_path", "")))
    if not client.is_file():
        missing.append("client_path")
    elif "sha256:" + hashlib.sha256(client.read_bytes()).hexdigest() != CLIENT_DIGEST:
        missing.append("client_digest_mismatch")
    if not args.execute or missing:
        reason = "execution not authorized" if not args.execute else "missing prerequisites: " + ", ".join(missing)
        failures = [blocked_cell(*cell, reason, config) for cell in matrix]
    else:
        # The exact Rust client interface is preserved in the evidence command.
        # Any non-zero cell remains a published FAILED result.
        for engine, workload, repetition in matrix:
            endpoint = config[f"{engine}_endpoint"]
            command = [
                str(client),
                "--base-url",
                endpoint,
                "--workload",
                workload,
                "--repetition",
                str(repetition),
                "--json",
            ]
            started = now()
            completed = subprocess.run(command, text=True, capture_output=True, timeout=config.get("cell_timeout_seconds", 900))
            if completed.returncode:
                failures.append(blocked_cell(engine, workload, repetition, completed.stderr[-4096:], config) | {"status": "FAILED", "started_at": started, "completed_at": now()})
            else:
                result = json.loads(completed.stdout)
                result.update(
                    {
                        "engine": engine,
                        "workload": workload,
                        "repetition": repetition,
                        "status": "MEASURED",
                        "started_at": started,
                        "completed_at": now(),
                        "failure": None,
                    }
                )
                failures.append(result)
    output = {
        "_license": "SPDX-License-Identifier: Apache-2.0; (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173",
        "label": "MEASURED" if failures and all(cell["status"] == "MEASURED" for cell in failures) else "BLOCKED",
        "benchmark_client": {"name": "vllm-bench", "version": CLIENT_VERSION, "artifact_digest": CLIENT_DIGEST},
        "results": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return 0 if output["label"] == "MEASURED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
