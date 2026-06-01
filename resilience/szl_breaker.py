# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v12 (additive over v11 LOCKED). Yachay.
"""
szl_breaker — Hystrix-style circuit breakers for every external SZL call.

pybreaker = state machine (CLOSED/OPEN/HALF-OPEN).
tenacity  = bounded retry w/ exponential backoff + full jitter.
We add:   per-call timeout, named fallback, and a Khipu degradation receipt
          on every OPEN transition and every fallback execution.

ADDITIVE only: this wraps calls; it never alters the 13-axis Yuyay gate, the
Lambda aggregator, or any LOCKED number (749/14/163, replay-hash bacf5443…631fc5).

HONEST: receipt signature is DSSE PLACEHOLDER (Sigstore CI not wired, v11 §9).
        Khipu DAG ingest reuses szl_wire.ingest_receipt (in-memory ring + S3 mirror).
"""
from __future__ import annotations
import functools
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timezone
from typing import Any, Callable

import pybreaker
from tenacity import (retry, stop_after_attempt, wait_exponential_jitter,
                      retry_if_exception_type)

try:
    from szl_wire import ingest_receipt, SIGNATURE_PLACEHOLDER  # reuse the live DAG
except Exception:  # edge / standalone import
    SIGNATURE_PLACEHOLDER = "PLACEHOLDER — Sigstore CI not wired (Doctrine v12)"
    def ingest_receipt(receipt: dict) -> dict:  # local fallback writer
        return {"receipt": receipt, "note": "local-only ingest (no szl_wire)"}

_POOL = ThreadPoolExecutor(max_workers=16)


def _emit_degradation(breaker_name: str, flagship: str, failure_mode: str,
                      fallback_tier: str, state: str, traceparent: str | None) -> None:
    """Append a szl.degradation.receipt/v1 to the canonical Khipu DAG (RUWAY-only path)."""
    ingest_receipt({
        "schema": "szl.degradation.receipt/v1",
        "event_id": f"deg-{datetime.now(timezone.utc).isoformat()}-{flagship}-{breaker_name}",
        "flagship": flagship,
        "failure_mode": failure_mode,
        "circuit": breaker_name,
        "breaker_state": state,
        "fallback_tier_served": fallback_tier,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "user_visible": True,
        "traceparent": traceparent,
        "doctrine": "v12",
        "dsse": {"sig": SIGNATURE_PLACEHOLDER, "keyid": "PENDING"},
    })


class KhipuListener(pybreaker.CircuitBreakerListener):
    """Emit a Khipu receipt on every breaker state transition (honest audit trail)."""
    def __init__(self, name: str, flagship: str, failure_mode: str, fallback_tier: str):
        self.name, self.flagship = name, flagship
        self.failure_mode, self.fallback_tier = failure_mode, fallback_tier
    def state_change(self, cb, old, new):
        _emit_degradation(self.name, self.flagship, self.failure_mode,
                          self.fallback_tier, str(new.name).upper(), None)


def make_breaker(name: str, flagship: str, failure_mode: str, fallback_tier: str,
                 fail_max: int = 5, reset_timeout_s: int = 15) -> pybreaker.CircuitBreaker:
    return pybreaker.CircuitBreaker(
        fail_max=fail_max,
        reset_timeout=reset_timeout_s,
        listeners=[KhipuListener(name, flagship, failure_mode, fallback_tier)],
        name=name,
    )


def guarded_call(breaker: pybreaker.CircuitBreaker, *, flagship: str, failure_mode: str,
                 fallback_tier: str, timeout_s: float, retry_budget: int,
                 fallback: Callable[[], Any], traceparent: str | None = None):
    """
    Decorator: wraps an external call with breaker + timeout + bounded retry + fallback.
    On OPEN (short-circuit) or exhausted retries, runs `fallback` and emits a Khipu receipt.
    """
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @retry(stop=stop_after_attempt(max(1, retry_budget + 1)),
               wait=wait_exponential_jitter(initial=1, max=300),
               retry=retry_if_exception_type(Exception), reraise=True)
        def _attempt(*a, **k):
            fut = _POOL.submit(fn, *a, **k)
            try:
                return fut.result(timeout=timeout_s)   # per-call hard timeout
            except FutureTimeout:
                raise TimeoutError(f"{breaker.name} exceeded {timeout_s}s")

        @functools.wraps(fn)
        def wrapper(*a, **k):
            try:
                return breaker.call(_attempt, *a, **k)   # breaker tracks success/fail
            except pybreaker.CircuitBreakerError:        # OPEN → short-circuit
                _emit_degradation(breaker.name, flagship, failure_mode,
                                  fallback_tier, "OPEN", traceparent)
                return fallback()
            except Exception:                            # retries exhausted
                _emit_degradation(breaker.name, flagship, failure_mode,
                                  fallback_tier, "FALLBACK", traceparent)
                return fallback()
        return wrapper
    return deco


# Breaker registry helper (names match OBSERVABILITY_DASHBOARD §3 + CIRCUIT_BREAKER_LAYER §1)
REGISTRY = {}

def register(name: str, flagship: str, failure_mode: str, fallback_tier: str,
             fail_max: int = 5, reset_timeout_s: int = 15) -> pybreaker.CircuitBreaker:
    b = make_breaker(name, flagship, failure_mode, fallback_tier, fail_max, reset_timeout_s)
    REGISTRY[name] = b
    return b


def breaker_states() -> dict[str, int]:
    """For /healthz: 0=CLOSED, 1=HALF_OPEN, 2=OPEN per registered breaker."""
    m = {"closed": 0, "half-open": 1, "open": 2}
    return {n: m.get(str(b.current_state).lower(), -1) for n, b in REGISTRY.items()}
