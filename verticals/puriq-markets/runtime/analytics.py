# SPDX-License-Identifier: Apache-2.0
# Author: SZL Holdings
"""Source-bound advisory analytics; no account, trade or shared receipt ledger.

Only the byte-attested upstream math component is imported. Provider access stays
inside FinanceClient. Receipts are deterministic, unsigned response evidence;
GET does not append to or replace the independent signed quant ledger.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import re
import time

from .transport import FinanceError, canonical, digest, source_revision

ROOT = Path(__file__).parent / "components" / "finance_v2"
COMPONENT = json.loads((ROOT / "source.json").read_text(encoding="utf-8"))
engine_bytes = (ROOT / "engine.py").read_bytes()
if hashlib.sha256(engine_bytes).hexdigest() != COMPONENT["engine_sha256"]:
    raise RuntimeError("finance engine component digest mismatch")
spec = importlib.util.spec_from_file_location("szl_finance_v2_component", ROOT / "engine.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
SCHEMA = "szl.finance.analytics/v2"
FLAGS = {"execution_enabled": False, "advisory_only": True, "paper_only": True,
         "not_financial_advice": True}


def symbol(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,23}", value):
        raise FinanceError("INVALID_PARAMETERS")
    return value


def series(values, minimum=35):
    if not isinstance(values, list) or not minimum <= len(values) <= 300:
        raise FinanceError("INVALID_SERIES")
    if any(type(x) not in (int, float) or not math.isfinite(x) or not 1e-12 <= x <= 1e12 for x in values):
        raise FinanceError("INVALID_SERIES")
    return [float(x) for x in values]


def fixture(symbol_name):
    """Explicit synthetic daily walk matching the reviewed v2 fixture algorithm."""
    rng = random.Random(int(hashlib.sha256(symbol_name.encode()).hexdigest()[:16], 16))
    values = [100.0]
    for _ in range(259):
        values.append(round(values[-1] * (1 + .0004 + rng.gauss(0, .015)), 4))
    return values


def history(client, symbol_name, origin, end=None):
    symbol(symbol_name)
    if origin == "fixture":
        values = fixture(symbol_name)
        return values, list(range(len(values))), {"origin": "fixture", "truth_label": "SYNTHETIC",
            "generator": "sha256-seeded-geometric-walk/v1", "values_sha256": digest(values)}, 252
    if origin != "coinbase" or not re.fullmatch(r"[A-Z0-9]{2,12}-[A-Z0-9]{2,12}", symbol_name):
        raise FinanceError("INVALID_PARAMETERS")
    params = {"product": symbol_name, "granularity": "86400", "count": "260"}
    if end is not None:
        params["end"] = str(end)
    observation = client.observe("coinbase-candles", params)
    # Honor the canonical shared cooldown. A second product may follow the
    # first faster than the normal 300 ms interval. Never override a provider
    # backoff or sleep/retry indefinitely inside a request.
    delay = observation.get("retry_after_seconds")
    if (observation.get("error") == "PROVIDER_COOLDOWN"
            and type(delay) in (int, float) and 0 < delay <= .35):
        time.sleep(delay + .005)
        observation = client.observe("coinbase-candles", params)
    if observation.get("ok") is not True or observation.get("state") not in ("SNAPSHOT", "CACHED"):
        raise FinanceError("PROVIDER_HISTORY_UNAVAILABLE")
    data = observation["data"]
    if data.get("window_complete") is not True:
        raise FinanceError("INCOMPLETE_HISTORY")
    rows = data["items"]
    values = series([float(row["close"]) for row in rows])
    return values, [row["time"] for row in rows], {"origin": "coinbase",
        "truth_label": "REPORTED", "observation": observation}, 365


def envelope(client, operation, payload, inputs):
    revision = source_revision(client.environ)
    if revision == "UNBOUND":
        raise FinanceError("CANONICAL_SOURCE_UNBOUND")
    # The source component uses MEASURED for successful arithmetic. The public
    # contract qualifies these derived values as modeled, including fixtures.
    # Recompute its optional content digest after adapting that label.
    if operation in ("signals", "portfolio"):
        payload = {**payload, "state": "COMPUTED", "truth_label": "MODELED"}
        if "report_digest" in payload:
            payload["report_digest"] = engine.canonical_digest(
                {key: value for key, value in payload.items() if key != "report_digest"})
    content = {"schema": SCHEMA, "ok": True, "state": "COMPUTED", "truth_label": "MODELED",
        "operation": operation, "source_revision": revision, "component": COMPONENT,
        "inputs": inputs, "result": payload, **FLAGS}
    receipt = {"schema": "szl.finance.computation-receipt/v1", "signing": "UNSIGNED_HONEST",
        "signed": False, "payload_sha256": digest(content), "source_revision": revision,
        "component_revision": COMPONENT["revision"], "component_sha256": COMPONENT["engine_sha256"],
        "persistence": "CALLER_HELD", "authority": "NONE"}
    receipt["receipt_sha256"] = digest(receipt)
    # Serialization rejects non-finite results even if the imported math regresses.
    canonical(content)
    return {**content, "receipt": receipt}


def compute(client, operation, symbol_name, origin="coinbase", benchmark=None):
    # Both products share one completed UTC window; never pair trailing dates blindly.
    end = int(client.clock()) // 86400 * 86400
    values, times, provenance, annual = history(client, symbol_name, origin, end)
    if len(set(values)) < 2:
        raise FinanceError("NO_PRICE_VARIATION")
    inputs = {"asset": provenance, "periods_per_year": annual,
              "timestamp_alignment": "COMPLETE_DAILY_WINDOW" if origin == "coinbase" else "SYNTHETIC_INDEX"}
    if operation == "signals":
        result = engine.signal_suite(values, symbol_name, origin)
    elif operation == "quote":
        stats = {"last": values[-1], "bars": len(values),
            "price_kind": "LAST_COMPLETED_DAILY_CLOSE_NOT_EXECUTION_QUOTE",
            "volatility": engine.volatility(values, annual),
            "sharpe": engine.sharpe(values, periods_per_year=annual),
            "max_drawdown": engine.max_drawdown(values)}
        if benchmark:
            other, other_times, proof, _ = history(client, benchmark, origin, end)
            if times != other_times:
                raise FinanceError("BENCHMARK_TIMESTAMPS_MISMATCH")
            stats.update(beta=engine.beta(values, other), beta_vs=benchmark)
            inputs["benchmark"] = proof
        result = {"symbol": symbol_name, "data_origin": origin, "stats": stats, **FLAGS}
    else:
        raise FinanceError("INVALID_PARAMETERS")
    return envelope(client, operation, result, inputs)


def portfolio(client, body):
    if not isinstance(body, dict) or set(body) != {"holdings", "periods_per_year"}:
        raise FinanceError("INVALID_PARAMETERS")
    holdings, annual = body["holdings"], body["periods_per_year"]
    if (not isinstance(holdings, dict) or not 1 <= len(holdings) <= 16
            or type(annual) is not int or annual not in (252, 365)):
        raise FinanceError("INVALID_PARAMETERS")
    checked = {symbol(key): series(value, 3) for key, value in holdings.items()}
    result = engine.portfolio_report(checked, annual)
    return envelope(client, "portfolio", result, {"origin": "caller_supplied", "truth_label": "UNVERIFIED",
        "holdings_sha256": digest(checked), "periods_per_year": annual,
        "scope": "Per-asset statistics and arithmetic means; no weighted portfolio, correlation or backtest."})


def verify(body):
    """Verify a supplied computation envelope; integrity is not authenticity."""
    if not isinstance(body, dict) or not isinstance(body.get("receipt"), dict):
        return False
    receipt = dict(body["receipt"])
    claimed = receipt.pop("receipt_sha256", None)
    content = {key: value for key, value in body.items() if key != "receipt"}
    return bool(claimed == digest(receipt) and receipt.get("payload_sha256") == digest(content)
        and receipt.get("signing") == "UNSIGNED_HONEST" and receipt.get("signed") is False
        and body.get("schema") == SCHEMA and body.get("component") == COMPONENT
        and receipt.get("source_revision") == body.get("source_revision")
        and isinstance(body.get("source_revision"), str)
        and re.fullmatch(r"[0-9a-f]{40}", body["source_revision"])
        and body["source_revision"] != "0" * 40
        and receipt.get("persistence") == "CALLER_HELD" and receipt.get("authority") == "NONE"
        and receipt.get("component_revision") == COMPONENT["revision"]
        and receipt.get("component_sha256") == COMPONENT["engine_sha256"]
        and all(body.get(key) is value for key, value in FLAGS.items()))
