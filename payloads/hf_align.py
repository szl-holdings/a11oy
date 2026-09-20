#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""GitHub szl-holdings <-> Hugging Face SZLHOLDINGS alignment receipt.

GitHub is canonical. HF is the runtime twin / mirror.
Do not pin a sixth Hub Space for this payload.
Inventory counts are MEASURED on the dated snapshot, not live-probed here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from yuyay_jev import canon, fail, sha256_hex  # noqa: E402

HF_INVENTORY = {
    "org": "SZLHOLDINGS",
    "github_org": "szl-holdings",
    "measured_on": "2026-09-20",
    "class": "MEASURED",
    "models": 47,
    "datasets": 35,
    "spaces": 22,
    "pinned_spaces": (
        "SZLHOLDINGS/llm-router-live",
        "SZLHOLDINGS/david-leads",
        "SZLHOLDINGS/szl-khipu",
        "SZLHOLDINGS/a11oy",
        "SZLHOLDINGS/szl-atelier",
        "SZLHOLDINGS/killinchu",
    ),
    "origin": "GitHub canonical. Hugging Face mirror. No sixth Space for this bind.",
}

KEEP = (
    ("szl-holdings/a11oy", "SZLHOLDINGS/a11oy", "LIVE", "flagship"),
    ("szl-holdings/killinchu", "SZLHOLDINGS/killinchu", "LIVE", "field COP"),
    ("szl-holdings/szl-router", "SZLHOLDINGS/llm-router-live", "LIVE", "inference"),
    ("szl-holdings/szl-khipu", "SZLHOLDINGS/szl-khipu", "LIVE", "lambda kernel"),
    ("szl-holdings/khipu-consensus", None, "REPORTED", "BFT tally - no HF twin"),
    ("szl-holdings/szl-atelier", "SZLHOLDINGS/szl-atelier", "LIVE", "card walker"),
    ("szl-holdings/immune", "SZLHOLDINGS/immune", "LIVE", "admit / seal"),
    ("szl-holdings/david-leads", "SZLHOLDINGS/david-leads", "LIVE", "broker research"),
    ("szl-holdings/anatomy", None, "REPORTED", "organs viz - different cut than n=4"),
    ("szl-holdings/vertical-services", "SZLHOLDINGS/vertical-services", "STALE", "no probe-shell fiction"),
    ("szl-holdings/szl-forge", "SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent", "STALE", "weights not source of truth"),
    ("szl-holdings/yarqa", "SZLHOLDINGS/yarqa", "FOLD", "do not warm as flagship"),
    ("szl-holdings/szl-lake", "SZLHOLDINGS/szl-lake", "LIVE", "receipt lake"),
)


def align() -> dict:
    pairs = [
        {
            "github": gh,
            "hf": hf or "UNAVAILABLE",
            "status": status,
            "note": note,
            "aligned": bool(hf),
        }
        for gh, hf, status, note in KEEP
    ]
    body = {
        "ok": True,
        "payload": "hf_align",
        "version": "1.0.0",
        "doctrine": "v11 LOCKED",
        "kernel_pin": "c7c0ba17",
        "conjecture_1": "OPEN",
        "proven_trust": False,
        "energy": "UNAVAILABLE",
        "signer": "UNSIGNED-honest",
        "honesty": "MEASURED",
        "inventory": dict(HF_INVENTORY),
        "pairs": pairs,
        "unpaired": [p["github"] for p in pairs if not p["aligned"]],
        "jev_allow_alone": False,
        "khipu_n": 4,
        "khipu_threshold": 3,
    }
    body["receipt_hash"] = sha256_hex(canon(body))
    return body


def main() -> None:
    sys.stdout.write(json.dumps(align(), sort_keys=True) + "\n")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"crash:{type(exc).__name__}")
