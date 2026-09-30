"""
SZL Finance Engine v2 — sovereign market-intelligence core.

Doctrine v11:
  - Five-state honesty contract: MEASURED / BLOCKED / INVALID / FAILED / PROMOTED
  - Every advisory output is advisory_only, paper_only, not_financial_advice
  - Fail-closed: missing or malformed input -> BLOCKED / INVALID, never fabricated
  - Pure stdlib math; deterministic; every input digest-able for receipts
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

SCHEMA_VERSION = "szl.finance-engine/v2"

STATE_MEASURED = "MEASURED"
STATE_BLOCKED = "BLOCKED"
STATE_INVALID = "INVALID"
STATE_FAILED = "FAILED"
STATE_PROMOTED = "PROMOTED"

TRUTH_LABELS = {
    "advisory_only": True,
    "paper_only": True,
    "not_financial_advice": True,
}


class EngineBlocked(Exception):
    """Raised when a computation cannot proceed honestly."""


def canonical_digest(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _require_series(values, min_len, name):
    if not isinstance(values, (list, tuple)):
        raise EngineBlocked(f"{name}: not a series")
    if len(values) < min_len:
        raise EngineBlocked(f"{name}: need >= {min_len} points, got {len(values)}")
    out = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise EngineBlocked(f"{name}: non-numeric point {v!r}")
        if not math.isfinite(f):
            raise EngineBlocked(f"{name}: non-finite point")
        out.append(f)
    return out


def sma(values, window: int):
    s = _require_series(values, window, "sma")
    return sum(s[-window:]) / window


def ema_series(values, window: int):
    s = _require_series(values, window, "ema")
    k = 2.0 / (window + 1)
    out = [sum(s[:window]) / window]
    for v in s[window:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes, period: int = 14) -> float:
    s = _require_series(closes, period + 1, "rsi")
    deltas = [s[i] - s[i - 1] for i in range(1, len(s))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def macd(closes, fast: int = 12, slow: int = 26, signal_p: int = 9):
    s = _require_series(closes, slow + signal_p, "macd")
    ef = ema_series(s, fast)
    es = ema_series(s, slow)
    macd_line = [f - sl for f, sl in zip(ef[-len(es):], es)]
    if len(macd_line) < signal_p:
        raise EngineBlocked("macd: insufficient history for signal line")
    k = 2.0 / (signal_p + 1)
    sig = [sum(macd_line[:signal_p]) / signal_p]
    for v in macd_line[signal_p:]:
        sig.append(v * k + sig[-1] * (1 - k))
    return {"macd": macd_line[-1], "signal": sig[-1], "histogram": macd_line[-1] - sig[-1]}


def bollinger_z(closes, window: int = 20) -> float:
    s = _require_series(closes, window, "bollinger")
    w = s[-window:]
    mu = sum(w) / window
    var = sum((x - mu) ** 2 for x in w) / window
    sd = math.sqrt(var)
    if sd == 0.0:
        return 0.0
    return (s[-1] - mu) / sd


def returns_series(closes):
    s = _require_series(closes, 2, "returns")
    out = []
    for i in range(1, len(s)):
        if s[i - 1] == 0.0:
            raise EngineBlocked("returns: zero price")
        out.append(s[i] / s[i - 1] - 1.0)
    return out


def volatility(closes, periods_per_year: int = 252) -> float:
    r = returns_series(closes)
    if len(r) < 2:
        raise EngineBlocked("volatility: need >= 2 returns")
    mu = sum(r) / len(r)
    var = sum((x - mu) ** 2 for x in r) / (len(r) - 1)
    return math.sqrt(var) * math.sqrt(periods_per_year)


def sharpe(closes, risk_free_daily: float = 0.0, periods_per_year: int = 252) -> float:
    r = returns_series(closes)
    if len(r) < 2:
        raise EngineBlocked("sharpe: need >= 2 returns")
    excess = [x - risk_free_daily for x in r]
    mu = sum(excess) / len(excess)
    var = sum((x - mu) ** 2 for x in excess) / (len(excess) - 1)
    sd = math.sqrt(var)
    if sd == 0.0:
        return 0.0
    return (mu / sd) * math.sqrt(periods_per_year)


def max_drawdown(closes) -> float:
    s = _require_series(closes, 2, "max_drawdown")
    peak = s[0]
    worst = 0.0
    for v in s:
        peak = max(peak, v)
        dd = (v - peak) / peak
        worst = min(worst, dd)
    return worst


def beta(closes, benchmark_closes) -> float:
    r = returns_series(closes)
    b = returns_series(benchmark_closes)
    n = min(len(r), len(b))
    if n < 2:
        raise EngineBlocked("beta: insufficient paired returns")
    r, b = r[-n:], b[-n:]
    mr = sum(r) / n
    mb = sum(b) / n
    cov = sum((x - mr) * (y - mb) for x, y in zip(r, b)) / (n - 1)
    vb = sum((y - mb) ** 2 for y in b) / (n - 1)
    if vb == 0.0:
        raise EngineBlocked("beta: zero-variance benchmark")
    return cov / vb


def signal_suite(closes, symbol: str, data_origin: str):
    """Full indicator stack -> advisory verdict. Fails closed."""
    s = _require_series(closes, 35, "signal_suite")
    ind = {
        "sma_fast": sma(s, 10),
        "sma_slow": sma(s, 30),
        "rsi_14": rsi(s, 14),
        "macd": macd(s, 12, 26, 9),
        "bollinger_z_20": bollinger_z(s, 20),
    }
    votes = 0
    votes += 1 if ind["sma_fast"] > ind["sma_slow"] else -1
    votes += 1 if ind["macd"]["histogram"] > 0 else -1
    r = ind["rsi_14"]
    votes += 1 if r < 30 else (-1 if r > 70 else 0)
    z = ind["bollinger_z_20"]
    votes += 1 if z < -2 else (-1 if z > 2 else 0)
    verdict = "BULLISH" if votes >= 2 else ("BEARISH" if votes <= -2 else "NEUTRAL")
    return {
        "schema": SCHEMA_VERSION,
        "state": STATE_MEASURED,
        "symbol": symbol.upper(),
        "data_origin": data_origin,
        "series_len": len(s),
        "input_digest": canonical_digest(s),
        "indicators": ind,
        "verdict": verdict,
        "vote_score": votes,
        **TRUTH_LABELS,
    }


def portfolio_report(holdings, periods_per_year: int = 252):
    """holdings: {symbol: closes(list)} — per-asset analytics over measured series."""
    if not holdings or not isinstance(holdings, dict):
        raise EngineBlocked("portfolio: empty holdings")
    reports = {}
    for sym, closes in holdings.items():
        reports[sym.upper()] = {
            "volatility": volatility(closes, periods_per_year),
            "sharpe": sharpe(closes, periods_per_year=periods_per_year),
            "max_drawdown": max_drawdown(closes),
            "input_digest": canonical_digest(_require_series(closes, 2, sym)),
            "series_len": len(closes),
        }
    keys = sorted(reports)
    port = {
        "schema": SCHEMA_VERSION,
        "state": STATE_MEASURED,
        "constituents": keys,
        "per_asset": reports,
        "aggregate": {
            "mean_volatility": sum(reports[k]["volatility"] for k in keys) / len(keys),
            "mean_sharpe": sum(reports[k]["sharpe"] for k in keys) / len(keys),
            "worst_drawdown": min(reports[k]["max_drawdown"] for k in keys),
        },
        **TRUTH_LABELS,
    }
    port["report_digest"] = canonical_digest({k: v for k, v in port.items() if k != "report_digest"})
    return port
