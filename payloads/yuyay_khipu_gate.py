#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compose YUYAY-JEV measurement + Khipu 3-of-4. This is the gate.

stdin JSON -> receipt. Decision is the tally, never Jev alone.
Default honesty=LIVE (fail-closed without TYPESAFE_API_KEY).
Pass honesty=SOFTWARE for the analog used by tests and the Command preview.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from khipu_organs import tally, vote_organs  # noqa: E402
from yuyay_jev import canon, fail, measure, sha256_hex  # noqa: E402


def gate(req: dict[str, Any]) -> dict[str, Any]:
    measurement = measure(req)
    intent = str(measurement.get("intent") or "")
    surface = str(req.get("surface") or "estate")
    if surface not in {"estate", "field"}:
        surface = "estate"
    field = req.get("field") or {}
    engage = float(field.get("engage_admissible") or 0.0)
    if surface == "field":
        engage = 0.0
    organs = vote_organs(
        intent=intent,
        lambda_=float(measurement["lambda"]),
        axes=measurement["axes"],
        surface=surface,
        engage_admissible=engage,
    )
    knot = tally(organs)
    decision = "ADMIT" if knot["decision"] == "canonical" else "BLOCKED"
    body = {
        **measurement,
        "payload": "yuyay_khipu_gate",
        "surface": surface,
        "decision": decision,
        "khipu": knot["decision"],
        "organs": organs,
        "allows": knot["allows"],
        "khipu_n": knot["n"],
        "khipu_threshold": knot["threshold"],
        "jev_allow_alone": False,
        "field": {
            "engage_admissible": engage,
            "track_id": req.get("track_id") or req.get("trackId"),
        }
        if surface == "field"
        else None,
    }
    body.pop("receipt_hash", None)
    body["receipt_hash"] = sha256_hex(canon({k: v for k, v in body.items() if k != "receipt_hash"}))
    return body


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        fail("empty stdin")
    try:
        req = json.loads(raw)
    except json.JSONDecodeError:
        fail("stdin is not JSON")
    try:
        body = gate(req)
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
