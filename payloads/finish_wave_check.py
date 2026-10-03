#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Finish-wave checker. SOFTWARE report. Not a gate. Not LIVE."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "repo": "szl-holdings/a11oy",
    "doctrine": "v11 LOCKED",
    "kernel_pin": "c7c0ba17",
    "conjecture_1": "OPEN",
    "trust_ceiling": 0.97,
    "lambda_bound": 0.72,
    "khipu_n": 4,
    "khipu_threshold": 3,
    "organs": ["sentra", "amaru", "a11oy", "killinchu"],
    "jev_allow_alone": False,
    "sixth_space": False,
    "burned_pr": 2271,
    "burned_branch": "feat/command-yuyay-vector-score-20260925",
    "hf_space": "SZLHOLDINGS/a11oy",
    "honesty": "SOFTWARE",
    "proven_trust": False,
}

REQUIRED = [
    "payloads/yuyay_jev.py",
    "payloads/yuyay_vector.py",
    "payloads/yuyay_khipu_gate.py",
    "payloads/evaluate_surface.py",
    "payloads/lambda_gate.py",
    "payloads/typesafe_bind.py",
    "payloads/khipu_organs.py",
    "payloads/observer_jobs.py",
    "payloads/hf_align.py",
    "payloads/YUYAY_JEV.md",
    "pages/yuyay-gate.html",
]


def main() -> None:
    missing = [p for p in REQUIRED if not (ROOT / p).is_file()]
    cmd = ROOT / "pages" / "command-center.html"
    stub = False
    if cmd.is_file():
        text = cmd.read_text(encoding="utf-8", errors="replace")
        stub = "<p>temp</p>" in text or len(text) < 1000
    body = {
        "ok": not missing and not stub,
        "payload": "finish_wave_check",
        "honesty": "SOFTWARE",
        "conjecture_1": "OPEN",
        "proven_trust": False,
        "jev_allow_alone": False,
        "missing": missing,
        "command_center_stub": stub,
        "pins": PINS,
        "note": "Parity with HF is UNKNOWN until owner readback. Merge is not deploy. HTTP 200 is REACHABLE, never UP.",
    }
    sys.stdout.write(json.dumps(body, sort_keys=True) + "\n")
    if missing or stub:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
