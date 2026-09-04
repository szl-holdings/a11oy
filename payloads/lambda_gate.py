#!/usr/bin/env python3
"""a11oy lambda_gate payload — operational, fail-closed, stdlib only.

Reads one JSON object on stdin:
  { "intent": str, "kernel": str | null, "energy_available": false }

Writes one JSON object on stdout. Never invents joules, signatures, or
a proven Λ. Uniqueness stays Conjecture 1.

Bind as an a11oy package. Not a second flagship.
Product origin: https://a-11-oy.com
Proof origin: https://a11oy.net
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from typing import Any

TRUST_CEILING = 0.97
LAMBDA_BOUND = 0.72
KERNEL_PIN = "c7c0ba17"
DOCTRINE = "v11 LOCKED"
PAYLOAD = "lambda_gate"
VERSION = "1.0.0"

AXIS_WEIGHTS = {
    "honesty": 1.2,
    "authority": 1.1,
    "evidence": 1.15,
    "safety": 1.25,
    "energy": 0.7,
}

DENY = [
    re.compile(r"force[-\s]?push", re.I),
    re.compile(r"extract (the )?(secret|token|key|pem)", re.I),
    re.compile(r"print .{0,40}(secret|token|private key)", re.I),
    re.compile(r"admin(istrator)? merge bypass", re.I),
    re.compile(r"weaken .{0,20}(gate|check)", re.I),
    re.compile(r"claim .{0,20}(ato|fedramp|proven theorem)", re.I),
    re.compile(r"lambda.{0,20}(proven|theorem)", re.I),
    re.compile(r"take over (my )?(laptop|machine)", re.I),
    re.compile(r"paste .{0,20}(credential|password)", re.I),
]

KERNELS = (
    "retrieval",
    "theorem",
    "style",
    "code-edit",
    "self-critique",
    "alignment",
    "multimodal",
    "router",
)


def clamp01(n: float) -> float:
    if not math.isfinite(n):
        return 0.0
    return min(1.0, max(0.0, n))


def lambda_of(axes: dict[str, float], energy_available: bool = False) -> float:
    keys = [k for k in AXIS_WEIGHTS if energy_available or k != "energy"]
    log = 0.0
    wsum = 0.0
    for k in keys:
        w = AXIS_WEIGHTS[k]
        v = max(1e-6, clamp01(axes[k]))
        log += w * math.log(v)
        wsum += w
    raw = math.exp(log / wsum) if wsum else 0.0
    return min(TRUST_CEILING, raw)


def gate(lam: float) -> str:
    return "ADMIT" if lam >= LAMBDA_BOUND else "BLOCKED"


def route_kernel(intent: str) -> str:
    t = intent.lower()
    if re.search(r"(lean|theorem|proof|conjecture|formula)", t):
        return "theorem"
    if re.search(r"(style|design|taste|aura|fashion)", t):
        return "style"
    if re.search(r"(code|pr|merge|repo|edit|typescript|python)", t):
        return "code-edit"
    if re.search(r"(critique|verify|audit|review)", t):
        return "self-critique"
    if re.search(r"(policy|align|deny|block|trust)", t):
        return "alignment"
    if re.search(r"(audio|vision|image|multimodal|ground)", t):
        return "multimodal"
    if re.search(r"(remember|retrieve|cache|kv|state|memory)", t):
        return "retrieval"
    return "router"


def policy_check(intent: str) -> tuple[bool, str | None]:
    if not intent.strip():
        return True, "Empty intent. Nothing to admit."
    for rx in DENY:
        if rx.search(intent):
            return (
                True,
                "Policy denied. Deny-by-default: this intent collides with operating law.",
            )
    return False, None


def score_axes(intent: str, blocked: bool) -> dict[str, float]:
    length = min(1.0, len(intent.strip()) / 240.0)
    return {
        "honesty": 0.88 if blocked else 0.84,
        "authority": 0.40 if blocked else 0.76,
        "evidence": 0.35 if blocked else 0.62 + 0.2 * length,
        "safety": 0.95 if blocked else 0.78,
        "energy": 0.5,
    }


def fail(detail: str) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "ok": False,
                "error": "UNAVAILABLE",
                "detail": detail,
                "payload": PAYLOAD,
                "version": VERSION,
                "runtime": "python3",
                "lambda_status": "CONJECTURE",
                "energy": "UNAVAILABLE",
                "signer": "UNSIGNED-honest",
                "honesty": "UNAVAILABLE",
                "doctrine": DOCTRINE,
                "kernel_pin": KERNEL_PIN,
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    raise SystemExit(0)


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        fail("Empty stdin. Payload expects one JSON object.")
    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON: {exc}")

    intent = str(data.get("intent") or "")
    asked = data.get("kernel")
    if data.get("energy_available"):
        fail("Energy meter UNAVAILABLE. Do not set energy_available.")

    blocked, reason = policy_check(intent)
    kernel = asked if asked in KERNELS else route_kernel(intent)
    axes = score_axes(intent, blocked)
    axes["energy"] = 0.5
    if blocked:
        axes["authority"] = min(axes["authority"], 0.42)
    lam = lambda_of(axes, energy_available=False)
    decision = "BLOCKED" if blocked or gate(lam) == "BLOCKED" else "ADMIT"
    text = reason if blocked else (
        f"Python payload {PAYLOAD} admitted via {kernel}. "
        f"Λ {lam:.3f} CONJECTURE. Energy UNAVAILABLE. "
        f"Signer UNSIGNED-honest. receipts.in ≡ receipts.out."
    )
    body = {
        "payload": PAYLOAD,
        "version": VERSION,
        "intent": intent,
        "kernel": kernel,
        "decision": decision,
        "lambda": float(f"{lam:.6f}"),
        "axes": {k: float(f"{axes[k]:.6f}") for k in AXIS_WEIGHTS},
        "energy": "UNAVAILABLE",
        "signer": "UNSIGNED-honest",
    }
    body_sha256 = hashlib.sha256(
        json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    sys.stdout.write(
        json.dumps(
            {
                "ok": True,
                "payload": PAYLOAD,
                "version": VERSION,
                "runtime": "python3",
                "doctrine": DOCTRINE,
                "kernel_pin": KERNEL_PIN,
                "decision": decision,
                "lambda": lam,
                "lambda_status": "CONJECTURE",
                "energy": "UNAVAILABLE",
                "signer": "UNSIGNED-honest",
                "honesty": "MEASURED",
                "axes": axes,
                "kernel": kernel,
                "policy": {"blocked": blocked, "reason": reason},
                "body_sha256": body_sha256,
                "text": text,
            },
            separators=(",", ":"),
        )
        + "\n"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"Payload crashed: {type(exc).__name__}: {exc}")
