#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Public GET-only observation; JSON evidence is not a production/trading approval.

No private data source, account, wallet, provider mutation, or credential values
are acquired. Every attempted source is retained, including failures and skips.
"""
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from importlib import import_module
_transport = import_module("verticals.puriq-markets.runtime.transport")
FinanceClient, canonical, stamp = _transport.FinanceClient, _transport.canonical, _transport.stamp


def main():
    out = Path("finance-source-evidence")
    out.mkdir(exist_ok=False)
    # This smoke intentionally excludes all credentialed or licensed sources.
    # The identified SEC User-Agent is an operator configuration, never guessed.
    env = {k: os.environ[k] for k in ("SZL_SOURCE_REVISION", "SZL_SEC_USER_AGENT") if k in os.environ}
    client = FinanceClient(environ=env)
    results, omitted = [], []
    requests = (
        ("polymarket-markets", {"limit": "20"}),
        ("kalshi-markets", {"limit": "20"}),
        ("coinbase-products", {}),
        ("coinbase-ticker", {"product": "BTC-USD"}),
        ("coinbase-candles", {"product": "BTC-USD", "granularity": "3600", "count": "100"}),
        ("treasury-rates", {"limit": "12"}),
        ("treasury-debt", {"limit": "5"}),
        ("bls-series", {"series_id": "CUUR0000SA0"}),
        ("sec-submissions", {"cik": "320193", "limit": "5"}),
        ("sec-companyfacts", {"cik": "320193", "limit": "2"}),
    )
    for source, parameters in requests:
        results.append(client.observe(source, parameters))
        time.sleep(0.4)  # Respect the process-wide provider pacer, no retry loop.
    by_source = {row["source"]: row for row in results}
    poly = by_source["polymarket-markets"]
    token = None
    if poly["ok"]:
        token = next((outcome["token_id"] for market in poly["data"]["items"]
            if market["book_enabled"] and not market["quality_flags"]
            for outcome in market["outcomes"] if outcome["token_id"]), None)
    if token:
        results.append(client.observe("polymarket-book", {"token_id": token}))
        time.sleep(0.4)
        results.append(client.observe("polymarket-history", {"token_id": token, "interval": "1d", "fidelity": "60"}))
    else:
        omitted.extend({"source": s, "status": "NOT_ATTEMPTED", "reason": "No valid enabled-book token observed in the bounded Gamma page"}
                       for s in ("polymarket-book", "polymarket-history"))
    kalshi = by_source["kalshi-markets"]
    ticker = next((m["ticker"] for m in kalshi.get("data", {}).get("items", []) if m["ticker"]), None) if kalshi["ok"] else None
    if ticker:
        results.append(client.observe("kalshi-book", {"ticker": ticker, "depth": "20"}))
    else:
        omitted.append({"source": "kalshi-book", "status": "NOT_ATTEMPTED", "reason": "No ticker observed in bounded Kalshi page"})
    for name in ("fred-series", "alpaca-bars", "alpaca-quote"):
        omitted.append({"source": name, "status": "NOT_ATTEMPTED", "reason": "Private credentialed source excluded from public CI smoke"})
    report = {"schema": "szl.finance.source-smoke/v1", "finished_at": stamp(time.time()),
        "source_revision": env.get("SZL_SOURCE_REVISION", "UNBOUND"),
        "attempted": len(results), "successful": sum(row["ok"] for row in results),
        "all_attempted_sources_available": all(row["ok"] for row in results),
        "results": results, "omissions": omitted, "production_admitted": False,
        "execution_enabled": False, "note": "A passing collection process is not proof every provider is available."}
    (out / "report.json").write_bytes(canonical(report) + b"\n")
    (out / "registry.json").write_bytes(canonical(client.registry()) + b"\n")
    summary = {"source_revision": report["source_revision"], "attempted": report["attempted"],
        "successful": report["successful"], "all_attempted_sources_available": report["all_attempted_sources_available"],
        "results": [{"source": row["source"], "state": row["state"], "ok": row["ok"], "error": row.get("error"),
                     "count": (row.get("data") or {}).get("count"),
                     "observation_id": (row.get("provenance") or {}).get("observation_id")} for row in results],
        "omissions": omitted, "production_admitted": False}
    (out / "summary.json").write_bytes(canonical(summary) + b"\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
