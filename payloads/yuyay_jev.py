#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""YUYAY-JEV measurement for szl-holdings/a11oy.

Jev measures Yuyay-13. Code owns Lambda. This file does not ALLOW-alone.
LIVE path: TypeSafe System One. Missing TYPESAFE_API_KEY -> UNAVAILABLE.
SOFTWARE path: explicit honesty=SOFTWARE analog for tests and preview.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

TRUST_CEILING, LAMBDA_BOUND = 0.97, 0.72
KERNEL_PIN, DOCTRINE, PAYLOAD, VERSION = "c7c0ba17", "v11 LOCKED", "yuyay_jev", "1.0.0"
ENDPOINT, DEFAULT_MODEL = "https://api.typesafe.ai/v1/systemone", "jev-latest"
LOCKED_EIGHT = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
YUYAY_AXES = (
    "moralGrounding",
    "measurabilityHonesty",
    "empiricalGrounding",
    "logicalConsistency",
    "sourceTransparency",
    "reproducibility",
    "licenseHygiene",
    "scopeDiscipline",
    "claimCalibration",
    "evalAwareness",
    "deceptionKeywords",
    "conflictingDirectives",
    "reversalDirective",
)
INVERT_AXES = frozenset({"deceptionKeywords", "conflictingDirectives", "reversalDirective"})
YUYAY_FLOORS = {
    "moralGrounding": 0.95,
    "measurabilityHonesty": 0.95,
    "empiricalGrounding": 0.90,
    "logicalConsistency": 0.90,
    "sourceTransparency": 0.90,
    "reproducibility": 0.90,
    "licenseHygiene": 0.90,
    "scopeDiscipline": 0.90,
    "claimCalibration": 0.90,
    "evalAwareness": 0.90,
    "deceptionKeywords": 0.90,
    "conflictingDirectives": 0.90,
    "reversalDirective": 0.90,
}
HITS: dict[str, tuple[str, ...]] = {
    "moralGrounding": ("harm", "covert", "unowned authority", "spoof"),
    "measurabilityHonesty": ("painted", "fabricat", "fake live", "green as proven"),
    "empiricalGrounding": ("unsourced", "invent", "no evidence"),
    "logicalConsistency": ("contradict", "override policy"),
    "sourceTransparency": ("anonymous authority", "hide source"),
    "reproducibility": ("hidden step", "irreproduc"),
    "licenseHygiene": ("pirat", "copy as original"),
    "scopeDiscipline": ("second flagship", "hologram", "new product name", "cloned product name"),
    "claimCalibration": ("lambda proven", "ato", "fedramp", "proven trust"),
    "evalAwareness": ("conjecture 1 closed", "theorem lambda", "trust 1.0"),
    "deceptionKeywords": ("deceive", "jailbreak", "spoof", "social-engineer"),
    "conflictingDirectives": ("ignore gate", "split the gate", "waive policy"),
    "reversalDirective": ("nullify", "bypass lambda", "disable deny", "turn off receipts"),
}
PACK_PATH = Path(__file__).resolve().parent.parent / "packs" / "yuyay13.questions.json"
if not PACK_PATH.exists():
    PACK_PATH = Path(__file__).resolve().parent / "packs" / "yuyay13.questions.json"
VECTOR_DIM = 13
VECTOR_KIND = "yuyay13.systemone.v1"


def clamp01(n: Any) -> float:
    try:
        v = float(n)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(v):
        return 0.0
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def wgm(values: list[float], weights: list[float] | None = None) -> float:
    n = len(values)
    if n == 0 or any(x <= 0.0 for x in values):
        return 0.0
    w = weights if weights is not None else [1.0 / n] * n
    log = sum(wi * math.log(max(x, 1e-12)) for x, wi in zip(values, w))
    return min(TRUST_CEILING, math.exp(log / sum(w)))


def djb2(s: str) -> int:
    h = 5381
    for ch in s:
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
    return h


def as_vector(axes: dict[str, float]) -> list[float]:
    if len(YUYAY_AXES) != VECTOR_DIM:
        raise RuntimeError("YUYAY_AXES dim drift")
    return [clamp01(axes.get(axis, 0.0)) for axis in YUYAY_AXES]


def floor_misses(axes: dict[str, float]) -> list[str]:
    return [
        axis
        for axis, floor in YUYAY_FLOORS.items()
        if clamp01(axes.get(axis, 0.0)) < floor - 1e-9
    ]


def compose_vector(
    axes: dict[str, float], *, model: str, pack_hash: str, state_hash: str
) -> dict[str, Any]:
    x = as_vector(axes)
    miss = floor_misses(axes)
    lam = wgm(x)
    return {
        "kind": VECTOR_KIND,
        "dim": VECTOR_DIM,
        "axes": list(YUYAY_AXES),
        "x": [round(v, 12) for v in x],
        "lambda": lam,
        "lambda_bound": LAMBDA_BOUND,
        "trust_ceiling": TRUST_CEILING,
        "floors_ok": not miss,
        "floor_misses": miss,
        "axioms": list(LOCKED_EIGHT),
        "conjecture_1": "OPEN",
        "proven_trust": False,
        "jev_allow_alone": False,
        "model": model,
        "pack_hash": pack_hash,
        "state_hash": state_hash,
        "vector_hash": sha256_hex(
            (
                f"{VECTOR_KIND}|{','.join(f'{v:.12f}' for v in x)}|"
                f"{model}|{pack_hash}|{state_hash}"
            ).encode()
        ),
    }


def software_measure(intent: str) -> dict[str, float]:
    t = intent.lower()
    axes: dict[str, float] = {}
    for axis in YUYAY_AXES:
        floor = YUYAY_FLOORS[axis]
        p_hit = 0.0
        for w in HITS[axis]:
            if w in t:
                p_hit += 0.42
        p_hit = clamp01(p_hit)
        jitter = ((djb2(intent + ":" + axis) % 17) - 8) / 800.0
        if not t.strip():
            goodness = 0.4
        elif axis in INVERT_AXES:
            goodness = clamp01(1.0 - p_hit)
        elif p_hit >= 0.4:
            goodness = min(floor - 0.25, 0.55)
        else:
            goodness = min(0.97, max(floor + 0.012, 0.962) + jitter)
        axes[axis] = round(clamp01(goodness), 12)
    return axes


def load_pack() -> dict[str, Any]:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    missing = [a for a in YUYAY_AXES if a not in pack.get("questions", {})]
    extra = [k for k in pack.get("questions", {}) if k not in YUYAY_AXES]
    if missing or extra:
        raise SystemExit(f"pack lexicon drift missing={missing} extra={extra}")
    return pack


def axis_from_answer(spec: dict[str, Any], answer: dict[str, Any], conf_floor: float) -> float:
    typ, polarity = spec.get("type"), spec.get("polarity", "direct")
    if typ == "noul":
        raw = clamp01(answer.get("noul", 0.0))
    elif typ == "score":
        legend = answer.get("legend") or {}
        raw = clamp01(float(answer.get("score", 0.0)) / max(len(legend) - 1, 1))
        if float(answer.get("confidence", 0.0) or 0.0) < conf_floor:
            raw = 0.0
    else:
        raw = 0.0
    return round(clamp01(1.0 - raw) if polarity == "invert" else raw, 12)


def call_jev(state: Any, pack: dict[str, Any]) -> dict[str, Any]:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("TYPESAFE_UNAVAILABLE")
    questions = {
        qid: {k: v for k, v in spec.items() if k in {"type", "instructions", "criteria"}}
        for qid, spec in pack["questions"].items()
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=canon({"state": state, "model": pack.get("model", DEFAULT_MODEL), "questions": questions}),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"TYPESAFE_HTTP_{exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("TYPESAFE_UNAVAILABLE") from exc


def fail(detail: str) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "ok": False,
                "error": "UNAVAILABLE",
                "detail": detail,
                "payload": PAYLOAD,
                "lambda_status": "CONJECTURE",
                "energy": "UNAVAILABLE",
                "signer": "UNSIGNED-honest",
                "proven_trust": False,
                "jev_allow_alone": False,
                "khipu_n": 4,
                "khipu_threshold": 3,
                "locked_eight": list(LOCKED_EIGHT),
            },
            sort_keys=True,
        )
        + "\n"
    )
    raise SystemExit(0)


def measure(req: dict[str, Any]) -> dict[str, Any]:
    intent = str(req.get("intent") or req.get("action") or "")
    honesty = str(req.get("honesty") or "").upper()
    state = req.get("state") or {"action": intent, "policy": req.get("policy"), "prior_receipts": []}
    if honesty == "SOFTWARE":
        axes = software_measure(intent)
        values = [axes[a] for a in YUYAY_AXES]
        lam = wgm(values)
        model = "software-jev"
        pack_id = "yuyay13.doctrine.v1"
        pack_hash = "SOFTWARE"
    else:
        pack = load_pack()
        jev = call_jev(state, pack)
        answers, conf = jev.get("answers") or {}, float(pack.get("confidence_floor", 0.55))
        axes = {qid: axis_from_answer(spec, answers.get(qid) or {}, conf) for qid, spec in pack["questions"].items()}
        values = [axes[a] for a in YUYAY_AXES]
        lam = wgm(values)
        model = jev.get("model") or DEFAULT_MODEL
        pack_id = pack.get("pack_id")
        pack_hash = sha256_hex(canon(pack))
        honesty = "LIVE"
    pem = os.environ.get("SZL_COSIGN_PRIVATE_PEM", "").strip()
    signer = "PEM-present-use-khipu-consensus" if pem else "UNSIGNED-honest"
    state_hash = sha256_hex(canon(state))
    vector = compose_vector(axes, model=str(model), pack_hash=str(pack_hash), state_hash=state_hash)
    body = {
        "ok": True,
        "payload": PAYLOAD,
        "version": VERSION,
        "doctrine": DOCTRINE,
        "kernel_pin": KERNEL_PIN,
        "intent": intent,
        "lambda": lam,
        "lambda_status": "CONJECTURE",
        "lambda_bound": LAMBDA_BOUND,
        "trust_ceiling": TRUST_CEILING,
        "conjecture_1": "OPEN",
        "proven_trust": False,
        "axes": axes,
        "x": vector["x"],
        "vector": vector,
        "floors": dict(YUYAY_FLOORS),
        "floors_ok": vector["floors_ok"],
        "floor_misses": vector["floor_misses"],
        "locked_eight": list(LOCKED_EIGHT),
        "model": model,
        "pack_id": pack_id,
        "pack_hash": pack_hash,
        "state_hash": state_hash,
        "energy": "UNAVAILABLE",
        "signer": signer,
        "honesty": honesty or "LIVE",
        "organ": "a11oy",
        "role": "measurement",
        "khipu_n": 4,
        "khipu_threshold": 3,
        "jev_allow_alone": False,
    }
    body["receipt_hash"] = sha256_hex(canon(body))
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
        body = measure(req)
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
