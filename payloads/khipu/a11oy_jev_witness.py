#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""a11oy organ adapter: YUYAY-JEV measurement -> one UNSIGNED-honest verdict.

This is the a11oy witness for khipu-consensus (n=4 t=3).
Jev never signs. PEM signing stays in khipu-consensus when keys exist.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if (HERE / "yuyay_jev.py").exists():
    PAYLOADS = HERE
elif (HERE.parent / "payloads" / "yuyay_jev.py").exists():
    PAYLOADS = HERE.parent / "payloads"
else:
    PAYLOADS = HERE.parent
if str(PAYLOADS) not in sys.path:
    sys.path.insert(0, str(PAYLOADS))

from khipu_organs import PAYLOAD_TYPE, vote_organs  # noqa: E402
from yuyay_jev import fail, measure  # noqa: E402


def witness(req: dict) -> dict:
    measurement = measure(req)
    votes = vote_organs(
        intent=str(measurement.get("intent") or ""),
        lambda_=float(measurement.get("lambda") or 0.0),
        axes=measurement.get("axes") or {},
        surface=str(req.get("surface") or "estate"),
        engage_admissible=0.0,
    )
    a11oy = next(v for v in votes if v["organ"] == "a11oy")
    return {
        "organ": "a11oy",
        "verdict": a11oy["verdict"],
        "reason": a11oy["reason"],
        "signer": "UNSIGNED-honest",
        "khipu_n": 4,
        "khipu_threshold": 3,
        "jev_allow_alone": False,
        "payload_type": PAYLOAD_TYPE,
        "measurement": measurement,
    }


if __name__ == "__main__":
    raw = sys.stdin.read()
    if not raw.strip():
        fail("empty stdin")
    try:
        req = json.loads(raw)
    except json.JSONDecodeError:
        fail("stdin is not JSON")
    try:
        print(json.dumps(witness(req), sort_keys=True))
    except RuntimeError as exc:
        fail(str(exc))
