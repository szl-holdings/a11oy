#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Evaluate-facing envelope for YUYAY + Khipu.

stdin JSON -> one receipt the Command / COP surfaces can render.
Decision is still the 3-of-4 tally. Jev never ALLOW-alone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from observer_jobs import attach as attach_jobs  # noqa: E402
from yuyay_jev import fail  # noqa: E402
from yuyay_khipu_gate import gate  # noqa: E402


def evaluate(req: dict[str, Any]) -> dict[str, Any]:
    body = gate(req)
    jobs = attach_jobs(
        intent=str(body.get("intent") or ""),
        surface=str(body.get("surface") or "estate"),
        engage_admissible=float((body.get("field") or {}).get("engage_admissible") or 0.0),
    )
    return {
        "ok": body.get("ok", False),
        "payload": "evaluate_surface",
        "surface": body.get("surface") or "estate",
        "decision": body.get("decision"),
        "khipu": body.get("khipu"),
        "allows": body.get("allows"),
        "lambda": body.get("lambda"),
        "lambda_status": "CONJECTURE",
        "conjecture_1": "OPEN",
        "honesty": body.get("honesty"),
        "x": body.get("x"),
        "floors_ok": body.get("floors_ok"),
        "observer_domain": jobs.get("observer_domain"),
        "jobs": jobs,
        "jev_allow_alone": False,
        "proven_trust": False,
        "energy": "UNAVAILABLE",
        "signer": body.get("signer") or "UNSIGNED-honest",
        "receipt_hash": body.get("receipt_hash"),
        "organs": [
            {"organ": o.get("organ"), "verdict": o.get("verdict"), "keyid": o.get("keyid")}
            for o in (body.get("organs") or [])
        ],
    }


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        fail("empty stdin")
    try:
        req = json.loads(raw)
    except json.JSONDecodeError:
        fail("stdin is not JSON")
    try:
        body = evaluate(req)
    except RuntimeError as exc:
        fail(str(exc))
    sys.stdout.write(json.dumps(body, sort_keys=True) + "\n")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"crash:{type(exc).__name__}")
