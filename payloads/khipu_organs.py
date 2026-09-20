#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Khipu n=4 t=3 organ votes. UNSIGNED-honest analog of khipu-consensus.

Organs: sentra, amaru, a11oy, killinchu.
Jev is not an organ. a11oy votes from Lambda + Yuyay floors.
"""
from __future__ import annotations

from typing import Any

from yuyay_jev import LAMBDA_BOUND, YUYAY_FLOORS

KHIPU_N, KHIPU_THRESHOLD = 4, 3
ORGANS = ("sentra", "amaru", "a11oy", "killinchu")
PAYLOAD_TYPE = "application/vnd.szl.khipu.organ-verdict+json"
POLICY_DENY = (
    "second flagship",
    "public effector",
    "effector",
    "engage the track",
    "jam",
    "spoof",
    "kinetic",
    "ato claim",
    "lambda proven",
    "jailbreak",
    "waive deny",
    "waive policy",
    "ignore gate",
    "bypass lambda",
    "turn off receipts",
)
ORGAN_JOBS = {
    "sentra": "Deny-by-default policy. No second flagship, ATO paint, or public effector.",
    "amaru": "Replay memory. Empty action is a block.",
    "a11oy": "Trust gate. Lambda and Yuyay-13 floors. Jev measures into this organ.",
    "killinchu": "Field organ. Sense-and-evidence. Public engage_admissible is 0.",
}


def vote_organs(
    *,
    intent: str,
    lambda_: float,
    axes: dict[str, float],
    surface: str = "estate",
    engage_admissible: float = 0.0,
) -> list[dict[str, Any]]:
    t = intent.lower()
    sentra_hit = next((p for p in POLICY_DENY if p in t), None)
    floors_ok = all((axes.get(k, 0.0) >= floor - 1e-9) for k, floor in YUYAY_FLOORS.items())
    a11oy_allow = lambda_ >= LAMBDA_BOUND and floors_ok
    if surface == "field":
        killinchu_allow = engage_admissible <= 0 and not sentra_hit
        killinchu_reason = (
            "public engage_admissible must be 0"
            if engage_admissible > 0
            else "sense-and-evidence only"
        )
    else:
        killinchu_allow = "effector" not in t and "engage the track" not in t
        killinchu_reason = (
            "no field effector language" if killinchu_allow else "effector language on public surface"
        )
    if a11oy_allow:
        a11oy_reason = f"Lambda {lambda_:.3f} >= {LAMBDA_BOUND} and floors"
    elif floors_ok:
        a11oy_reason = f"Lambda {lambda_:.3f} below bound"
    else:
        a11oy_reason = "axis floor miss"
    votes = [
        {
            "organ": "sentra",
            "verdict": "block" if sentra_hit else "allow",
            "reason": f"deny-by-default: {sentra_hit}" if sentra_hit else "policy holds",
        },
        {
            "organ": "amaru",
            "verdict": "allow" if intent.strip() else "block",
            "reason": "replay memory admitted" if intent.strip() else "empty action",
        },
        {
            "organ": "a11oy",
            "verdict": "allow" if a11oy_allow else "block",
            "reason": a11oy_reason,
        },
        {
            "organ": "killinchu",
            "verdict": "allow" if killinchu_allow else "block",
            "reason": killinchu_reason,
        },
    ]
    for v in votes:
        v["signer"] = "UNSIGNED-honest"
        v["payload_type"] = PAYLOAD_TYPE
        v["job"] = ORGAN_JOBS[v["organ"]]
        v["jev_allow_alone"] = False
        v["khipu_n"] = KHIPU_N
        v["khipu_threshold"] = KHIPU_THRESHOLD
    return votes


def tally(votes: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    allows = 0
    for v in votes:
        organ = str(v.get("organ") or "")
        if organ in seen:
            continue
        seen.add(organ)
        if v.get("verdict") == "allow":
            allows += 1
    canonical = allows >= KHIPU_THRESHOLD
    return {
        "n": KHIPU_N,
        "threshold": KHIPU_THRESHOLD,
        "allows": allows,
        "decision": "canonical" if canonical else "rejected",
        "jev_allow_alone": False,
        "signer": "UNSIGNED-honest",
        "conjecture_2": "OPEN",
        "conjecture_3": "OPEN",
    }
