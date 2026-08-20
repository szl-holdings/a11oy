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

Enforcement is advisory-by-default: a paid call-site calls `allow(estimated_usd)` before
spending and honors a False. Two independent trip conditions:
  1) cumulative spent + estimate would exceed the cap, or
  2) an operator kill-file exists on disk (SZL_SPEND_KILL_FILE, default
     /opt/alloyscape/.spend-KILL) — matches the emergency stop already used in ops.

Importing this module gates nothing; wiring paid call-sites to honor it is a separate,
deliberate step so live inference is never silently broken.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

_GENESIS = "0" * 64
_LOCK = threading.Lock()


def sha256_canon(obj: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _env_float(name: str, default: float) -> float:
    try:
        raw = (os.environ.get(name, "") or "").strip()
        return float(raw) if raw else float(default)
    except (TypeError, ValueError):
        return float(default)


def _kill_file() -> str:
    return (os.environ.get("SZL_SPEND_KILL_FILE", "") or "").strip() or "/opt/alloyscape/.spend-KILL"


class SpendLedger:
    """Append-only, hash-linked USD spend ledger with a hard cap."""

    def __init__(self, cap_usd: Optional[float] = None, max_tail: int = 200) -> None:
        self.cap_usd = float(cap_usd) if cap_usd is not None else _env_float("SZL_SPEND_CAP_USD", 25.0)
        self.max_tail = int(max_tail)
        self._entries: List[Dict[str, Any]] = []
        self._spent = 0.0
        self._prev = _GENESIS

    def record(self, amount_usd: float, source: str = "unknown",
               meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        amt = max(0.0, float(amount_usd))
        with _LOCK:
            body = {
                "ts": _now_iso(),
                "amount_usd": round(amt, 6),
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
            return dict(body)

    def kill_engaged(self) -> bool:
        try:
            return os.path.exists(_kill_file())
        except OSError:
            return False

    def tripped(self) -> bool:
        return self.kill_engaged() or (self._spent >= self.cap_usd)

    def allow(self, estimated_usd: float = 0.0) -> Dict[str, Any]:
        est = max(0.0, float(estimated_usd))
        killed = self.kill_engaged()
        projected = self._spent + est
        ok = (not killed) and (projected <= self.cap_usd)
        reason = "kill-file engaged" if killed else ("ok" if ok else "cap exceeded")
        return {
            "allow": ok,
            "reason": reason,
            "estimated_usd": round(est, 6),
            "spent_usd": round(self._spent, 6),
            "projected_usd": round(projected, 6),
            "cap_usd": round(self.cap_usd, 6),
            "remaining_usd": round(max(0.0, self.cap_usd - self._spent), 6),
        }

    def verify(self) -> Dict[str, Any]:
        prev = _GENESIS
        intact = True
        for e in self._entries:
            body = {k: e[k] for k in ("ts", "amount_usd", "source", "meta", "prev")}
            if e.get("prev") != prev or sha256_canon(body) != e.get("digest"):
                intact = False
                break
            prev = e["digest"]
        return {"intact": intact, "entries": len(self._entries)}

    def set_cap(self, cap_usd: float) -> Dict[str, Any]:
        with _LOCK:
            self.cap_usd = max(0.0, float(cap_usd))
        return self.state()

    def state(self) -> Dict[str, Any]:
        spent = round(self._spent, 6)
        cap = round(self.cap_usd, 6)
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
        return led.record(
            payload.get("amount_usd", 0.0),
            payload.get("source", "api"),
            payload.get("meta"),
        )

    @app.post(base + "/cap", include_in_schema=False)
    def _spend_setcap(payload: Dict[str, Any]):
        return led.set_cap(payload.get("cap_usd", led.cap_usd))

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
