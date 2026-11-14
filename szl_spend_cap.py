#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_spend_cap.py — SZL Sovereign Ops: a hard cumulative spend cap + kill-switch.

The platform already MEASURES cost (szl_cheapest_watt, joule_billing) and ROUTES to
the cheapest safe model tier (szl_budget_router). What was missing is a single hard
*ceiling* that actually trips a kill-switch and tells paid call-sites to stop — the
brake, not another gauge.

Free-first and dependency-light: stdlib only for the core; FastAPI is touched only to
expose routes (never imported at module load, so the core stays importable anywhere).
It keeps an append-only, hash-linked spend ledger (receipts.in == receipts.out
doctrine) so the running total is tamper-evident.

`record` and `admit` are the gate: under the lock they refuse a write that would
pass the configured cap or while the kill-file exists. `allow` is a preview of
that same decision, including a zero estimate once spent has already met the cap.
The lock, the total, and the admission map live in this process only. A restart
or another replica does not see them, so this is not a durable or fleet-wide cap.
Importing this module does not attach the ledger to acoustic, data, or
experimental reads. Two trip conditions:
  1) cumulative spent + estimate would exceed the cap, or
  2) an operator kill-file exists on disk (SZL_SPEND_KILL_FILE, default
     /opt/alloyscape/.spend-KILL) — matches the emergency stop already used in ops.

Importing this module gates nothing; wiring paid call-sites to honor it is a separate,
deliberate step so live inference is never silently broken.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

_QUANTUM = Decimal("0.000001")
_AMOUNT_TEXT = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_DEFAULT_MAX_ADMISSIONS = 4096

_GENESIS = "0" * 64
_LOCK = threading.Lock()


def sha256_canon(obj: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _kill_file() -> str:
    return (os.environ.get("SZL_SPEND_KILL_FILE", "") or "").strip() or "/opt/alloyscape/.spend-KILL"


def _canonical_usd(value: Any, *, allow_zero: bool) -> Optional[Decimal]:
    """One 6-decimal USD value for the cap check, the stored row, and its hash.

    NaN, infinity, booleans, negatives, and a positive value that rounds to zero
    are refused. They are not coerced to zero.
    """
    try:
        if isinstance(value, Decimal):
            parsed = value
        elif isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return None
        elif isinstance(value, str):
            text = value.strip()
            if _AMOUNT_TEXT.fullmatch(text) is None:
                return None
            parsed = Decimal(text)
        elif isinstance(value, float):
            if not math.isfinite(value):
                return None
            parsed = Decimal(str(value))
        else:
            parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite():
        return None
    canonical = parsed.quantize(_QUANTUM)
    if canonical < 0 or (canonical == 0 and parsed != 0):
        return None
    if canonical == 0 and not allow_zero:
        return None
    return canonical


def _money(value: Decimal) -> float:
    return float(value)


class SpendCapError(ValueError):
    """The supplied cap cannot be used. No substitute budget is granted."""


class SpendLedger:
    """Append-only, hash-linked USD spend ledger with an in-process cap.

    ``max_tail`` bounds the retained rows. ``verify`` checks that retained
    history only; a trimmed prefix is not claimed to still link to genesis.
    ``max_admissions`` bounds retry memory. When it is full, a new operation
    id is refused and an id already stored is still protected.

    An omitted constructor cap uses ``SZL_SPEND_CAP_USD`` when that variable is
    set, and otherwise 25. A non-finite or non-canonical cap raises
    ``SpendCapError`` instead of substituting 25. Passing the ledger's current
    ``cap_usd`` back to ``set_cap`` keeps that cap; it does not widen it.
    """

    def __init__(self, cap_usd: Optional[float] = None, max_tail: int = 200,
                 max_admissions: int = _DEFAULT_MAX_ADMISSIONS) -> None:
        if cap_usd is None:
            raw = (os.environ.get("SZL_SPEND_CAP_USD") or "").strip()
            parsed = Decimal("25.000000") if not raw else _canonical_usd(raw, allow_zero=True)
            if parsed is None:
                raise SpendCapError("SZL_SPEND_CAP_USD is not a usable cap")
        else:
            parsed = _canonical_usd(cap_usd, allow_zero=True)
            if parsed is None:
                raise SpendCapError("cap_usd is not a usable cap")
        self.cap_usd = parsed
        self.max_tail = int(max_tail)
        self.max_admissions = int(max_admissions)
        self._entries: List[Dict[str, Any]] = []
        self._admissions: Dict[str, Dict[str, Any]] = {}
        self._spent = Decimal("0")
        self._prev = _GENESIS

    def _refused(self, reason: str, estimated: Optional[Decimal]) -> Dict[str, Any]:
        return {
            "allow": False, "recorded": False, "reason": reason,
            "estimated_usd": None if estimated is None else _money(estimated),
            "spent_usd": _money(self._spent),
            "cap_usd": _money(self.cap_usd),
        }

    def _append(self, amt: Decimal, source: str, meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        body = {
            "ts": _now_iso(),
            "amount_usd": _money(amt),
            "source": str(source)[:80],
            "meta": meta or {},
            "prev": self._prev,
        }
        body["digest"] = sha256_canon(body)
        self._entries.append(body)
        if len(self._entries) > self.max_tail:
            self._entries = self._entries[-self.max_tail:]
        self._spent += amt
        self._prev = body["digest"]
        stored = dict(body)
        stored["allow"] = True
        stored["recorded"] = True
        return stored

    def _over_cap(self, amt: Decimal) -> bool:
        return self._spent >= self.cap_usd or self._spent + amt > self.cap_usd

    def record(self, amount_usd: float, source: str = "unknown",
               meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Append only while the existing cap and kill-file still allow it."""
        amt = _canonical_usd(amount_usd, allow_zero=False)
        with _LOCK:
            if amt is None:
                return self._refused("invalid amount", None)
            if self.kill_engaged():
                return self._refused("kill-file engaged", amt)
            if self._over_cap(amt):
                return self._refused("cap exceeded", amt)
            return self._append(amt, source, meta)

    def admit(self, amount_usd: float, operation_id: str, payload_digest: str,
              source: str = "admit", meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Reserve once under the lock.

        A retry with the same operation id, canonical amount, and payload digest
        does not record again. A different amount or digest is refused and does
        not append. The id is an operation name supplied by the caller, not a
        hash of a payment token. The admission map is not evicted: at capacity,
        a new id is refused and an existing id stays protected.
        """
        amt = _canonical_usd(amount_usd, allow_zero=False)
        if not isinstance(operation_id, str) or not operation_id:
            return self._refused("operation id required", amt)
        if not isinstance(payload_digest, str) or not payload_digest:
            return self._refused("payload digest required", amt)
        with _LOCK:
            if amt is None:
                return self._refused("invalid amount", None)
            prior = self._admissions.get(operation_id)
            if prior is not None:
                if prior["payload_digest"] != payload_digest or prior["amount"] != amt:
                    return self._refused("operation reuse conflict", amt)
                replay = dict(prior["body"])
                replay["allow"] = True
                replay["recorded"] = False
                replay["reason"] = "duplicate"
                return replay
            if len(self._admissions) >= self.max_admissions:
                return self._refused("admission memory full", amt)
            if self.kill_engaged():
                return self._refused("kill-file engaged", amt)
            if self._over_cap(amt):
                return self._refused("cap exceeded", amt)
            stored = self._append(amt, source, meta)
            self._admissions[operation_id] = {
                "payload_digest": payload_digest, "amount": amt, "body": dict(stored),
            }
            stored["reason"] = "admitted"
            return stored

    def kill_engaged(self) -> bool:
        try:
            return os.path.exists(_kill_file())
        except OSError:
            return False

    def tripped(self) -> bool:
        return self.kill_engaged() or (self._spent >= self.cap_usd)

    def allow(self, estimated_usd: float = 0.0) -> Dict[str, Any]:
        """Preview only. ``record`` and ``admit`` are the gate; they re-check under the lock."""
        est = _canonical_usd(estimated_usd, allow_zero=True)
        with _LOCK:
            if est is None:
                return self._refused("invalid amount", None)
            killed = self.kill_engaged()
            spent = self._spent
            projected = spent + est
            ok = (not killed) and (spent < self.cap_usd) and (projected <= self.cap_usd)
            reason = "kill-file engaged" if killed else ("ok" if ok else "cap exceeded")
            return {
                "allow": ok,
                "reason": reason,
                "estimated_usd": _money(est),
                "spent_usd": _money(spent),
                "projected_usd": _money(projected),
                "cap_usd": _money(self.cap_usd),
                "remaining_usd": _money(max(Decimal("0"), self.cap_usd - spent)),
            }

    def verify(self) -> Dict[str, Any]:
        """Check the rows still retained. A trimmed prefix is not genesis."""
        if not self._entries:
            return {"intact": True, "entries": 0, "retained_only": False}
        prev = self._entries[0]["prev"]
        intact = True
        for e in self._entries:
            body = {k: e[k] for k in ("ts", "amount_usd", "source", "meta", "prev")}
            if e.get("prev") != prev or sha256_canon(body) != e.get("digest"):
                intact = False
                break
            prev = e["digest"]
        return {
            "intact": intact,
            "entries": len(self._entries),
            "retained_only": self._entries[0]["prev"] != _GENESIS,
        }

    def set_cap(self, cap_usd: float) -> Dict[str, Any]:
        parsed = _canonical_usd(cap_usd, allow_zero=True)
        with _LOCK:
            if parsed is None:
                rejected = self.state()
                rejected["cap_rejected"] = True
                return rejected
            self.cap_usd = parsed
        return self.state()

    def state(self) -> Dict[str, Any]:
        spent = _money(self._spent)
        cap = _money(self.cap_usd)
        return {
            "cap_usd": cap,
            "spent_usd": spent,
            "remaining_usd": round(max(0.0, cap - spent), 6),
            "pct_used": round(100.0 * spent / cap, 2) if cap > 0 else None,
            "armed": True,
            "tripped": self.tripped(),
            "kill_file_engaged": self.kill_engaged(),
            "kill_file": _kill_file(),
            "entries": len(self._entries),
            "chain": self.verify(),
            "tail": self._entries[-10:],
            "generated": _now_iso(),
        }


_LEDGER: Optional[SpendLedger] = None


def get_ledger() -> SpendLedger:
    global _LEDGER
    if _LEDGER is None:
        _LEDGER = SpendLedger()
    return _LEDGER


def allow(estimated_usd: float = 0.0) -> Dict[str, Any]:
    return get_ledger().allow(estimated_usd)


def record(amount_usd: float, source: str = "unknown",
           meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return get_ledger().record(amount_usd, source, meta)


def state() -> Dict[str, Any]:
    return get_ledger().state()


def register(app: Any, ns: str = "a11oy") -> str:
    led = get_ledger()
    base = f"/api/{ns}/v1/spend"

    @app.get(base + "/state", include_in_schema=False)
    def _spend_state():
        return led.state()

    @app.get(base + "/allow", include_in_schema=False)
    def _spend_allow(estimated_usd: float = 0.0):
        return led.allow(estimated_usd)

    @app.post(base + "/record", include_in_schema=False)
    def _spend_record(payload: Dict[str, Any]):
        from starlette.responses import JSONResponse
        operation_id = payload.get("operation_id")
        if operation_id:
            result = led.admit(
                payload.get("amount_usd", 0.0),
                str(operation_id),
                str(payload.get("payload_digest") or ""),
                payload.get("source", "api"),
                payload.get("meta"),
            )
        else:
            result = led.record(
                payload.get("amount_usd", 0.0),
                payload.get("source", "api"),
                payload.get("meta"),
            )
        if result.get("recorded") is False and result.get("allow") is False:
            return JSONResponse(result, status_code=409)
        return result

    @app.post(base + "/cap", include_in_schema=False)
    def _spend_setcap(payload: Dict[str, Any]):
        # Omission keeps the current cap. The stored value is a Decimal, and
        # set_cap accepts that same value without widening it.
        if not isinstance(payload, dict) or "cap_usd" not in payload or payload.get("cap_usd") is None:
            return led.set_cap(led.cap_usd)
        return led.set_cap(payload.get("cap_usd"))

    @app.get("/spend-cap", include_in_schema=False)
    def _spend_cap_view():
        return led.state()

    return f"szl_spend_cap mounted: base={base} cap_usd={led.cap_usd}"


def _selftest() -> Dict[str, Any]:
    led = SpendLedger(cap_usd=1.0)
    led.record(0.4, "test")
    a1 = led.allow(0.5)  # 0.4 + 0.5 = 0.9 <= 1.0  -> allow
    led.record(0.4, "test")
    a2 = led.allow(0.5)  # 0.8 + 0.5 = 1.3 >  1.0  -> deny
    return {
        "a1_ok": a1["allow"],
        "a2_deny": (not a2["allow"]),
        "chain_intact": led.verify()["intact"],
    }


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
