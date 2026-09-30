# SPDX-License-Identifier: Apache-2.0
"""Services/finance: explicit read contracts for eight authorities, no execution.

Decimal strings preserve venue price/count units. Missing values remain null;
event semantics, outcome identity, timestamps and pagination remain explicit.
Provider text is untrusted data, never an instruction or a fetched destination.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re
from typing import Any, Mapping
from urllib.parse import urlencode

from .transport import FinanceError, Plan, stamp, strict_json

SOURCES = {
    "polymarket-markets": {"provider": "polymarket", "operation": "Public Gamma market discovery", "parameters": ["limit", "offset"], "required_environment": [], "private": False},
    "polymarket-book": {"provider": "polymarket", "operation": "CLOB outcome-token order book", "parameters": ["token_id"], "required_environment": [], "private": False},
    "polymarket-history": {"provider": "polymarket", "operation": "CLOB outcome-token price history", "parameters": ["token_id", "interval", "fidelity"], "required_environment": [], "private": False},
    "kalshi-markets": {"provider": "kalshi", "operation": "Public open-market discovery", "parameters": ["limit", "cursor", "series_ticker"], "required_environment": [], "private": False},
    "kalshi-book": {"provider": "kalshi", "operation": "YES/NO bids and explicitly derived complementary asks", "parameters": ["ticker", "depth"], "required_environment": [], "private": False},
    "coinbase-products": {"provider": "coinbase", "operation": "Public Exchange product catalogue", "parameters": [], "required_environment": [], "private": False},
    "coinbase-ticker": {"provider": "coinbase", "operation": "Public Exchange last trade and bid/ask snapshot", "parameters": ["product"], "required_environment": [], "private": False},
    "coinbase-candles": {"provider": "coinbase", "operation": "Completed historical Exchange candles, no interpolation", "parameters": ["product", "granularity", "end", "count"], "required_environment": [], "private": False},
    "sec-submissions": {"provider": "sec", "operation": "EDGAR recent submissions with filing and report dates", "parameters": ["cik", "limit"], "required_environment": ["SZL_SEC_USER_AGENT"], "private": False},
    "sec-companyfacts": {"provider": "sec", "operation": "Bounded XBRL observations with units and period context", "parameters": ["cik", "limit"], "required_environment": ["SZL_SEC_USER_AGENT"], "private": False},
    "treasury-rates": {"provider": "treasury", "operation": "Average interest rates on Treasury securities; not a spot yield curve", "parameters": ["limit"], "required_environment": [], "private": False},
    "treasury-debt": {"provider": "treasury", "operation": "Debt to the Penny", "parameters": ["limit"], "required_environment": [], "private": False},
    "bls-series": {"provider": "bls", "operation": "Public BLS series; release vintages not established", "parameters": ["series_id"], "required_environment": [], "private": False},
    "fred-series": {"provider": "fred", "operation": "FRED/ALFRED series at an explicit as-of date", "parameters": ["series_id", "as_of", "limit"], "required_environment": ["SZL_FRED_API_KEY", "SZL_FINANCE_PRIVATE_READ_TOKEN"], "private": True},
    "alpaca-quote": {"provider": "alpaca", "operation": "Entitled stock quote; private read only", "parameters": ["symbol"], "required_environment": ["APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "SZL_FINANCE_PRIVATE_READ_TOKEN"], "private": True},
    "alpaca-bars": {"provider": "alpaca", "operation": "Entitled stock bars; no split adjustment or completeness inferred", "parameters": ["symbol", "timeframe", "start", "end", "limit", "page_token"], "required_environment": ["APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "SZL_FINANCE_PRIVATE_READ_TOKEN"], "private": True},
}


def invalid() -> None:
    raise FinanceError("INVALID_PARAMETERS")


def pattern(value: Any, expression: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(expression, value):
        invalid()
    return value


def integer(value: Any, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        invalid()
    if isinstance(value, str) and not re.fullmatch(r"[0-9]{1,12}", value):
        invalid()
    value = int(value)
    if not low <= value <= high:
        invalid()
    return value


def iso_date(value: str, now: float) -> str:
    pattern(value, r"\d{4}-\d{2}-\d{2}")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        invalid()
    if not date(1900, 1, 1) <= parsed <= datetime.fromtimestamp(now, timezone.utc).date():
        invalid()
    return value


def utc_time(value: str, now: float) -> tuple[str, float]:
    pattern(value, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
    try:
        seconds = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        invalid()
    if not 0 <= seconds <= now:
        invalid()
    return value, seconds


def build_plan(source: str, query: dict, env: Mapping[str, str], now: float) -> Plan:
    if source not in SOURCES or set(query) - set(SOURCES[source]["parameters"]):
        invalid()
    spec = SOURCES[source]
    # Do not echo untrusted query values or credential values in failures.
    if len(query) > 8 or any(not isinstance(v, (str, int)) or len(str(v)) > 2048 for v in query.values()):
        invalid()
    p, upstream, headers = {}, {}, {}
    ttl, max_bytes, interval = 30, 4_000_000, 0.3
    if source == "polymarket-markets":
        p = {"limit": integer(query.get("limit", 20), 1, 100), "offset": integer(query.get("offset", 0), 0, 100_000)}
        base = "https://gamma-api.polymarket.com/markets"
        upstream = {**p, "active": "true", "closed": "false"}
        ttl = 60
    elif source in {"polymarket-book", "polymarket-history"}:
        p["token_id"] = pattern(query.get("token_id"), r"[0-9]{1,80}")
        if source == "polymarket-book":
            base = "https://clob.polymarket.com/book"
            upstream = dict(p)
            ttl = 10
        else:
            p["interval"] = pattern(query.get("interval", "1d"), r"1h|6h|1d|1w|1m")
            p["fidelity"] = integer(query.get("fidelity", 60), 1, 1440)
            base = "https://clob.polymarket.com/prices-history"
            upstream = {"market": p["token_id"], "interval": p["interval"], "fidelity": p["fidelity"]}
            ttl = 300
    elif source == "kalshi-markets":
        p["limit"] = integer(query.get("limit", 20), 1, 100)
        if query.get("cursor"):
            p["cursor"] = pattern(query["cursor"], r"[A-Za-z0-9_=+./~-]{1,2048}")
        if query.get("series_ticker"):
            p["series_ticker"] = pattern(query["series_ticker"], r"[A-Z0-9][A-Z0-9_-]{0,119}")
        base = "https://external-api.kalshi.com/trade-api/v2/markets"
        upstream = {**p, "status": "open"}
        ttl = 60
    elif source == "kalshi-book":
        p = {"ticker": pattern(query.get("ticker"), r"[A-Z0-9][A-Z0-9_-]{0,199}"),
             "depth": integer(query.get("depth", 50), 1, 100)}
        base = "https://external-api.kalshi.com/trade-api/v2/markets/" + p["ticker"] + "/orderbook"
        upstream, ttl = {"depth": p["depth"]}, 10
    elif source.startswith("coinbase-"):
        base = "https://api.exchange.coinbase.com/products"
        if source != "coinbase-products":
            p["product"] = pattern(query.get("product", "BTC-USD"), r"[A-Z0-9]{2,12}-[A-Z0-9]{2,12}")
            base += "/" + p["product"] + "/" + ("ticker" if source == "coinbase-ticker" else "candles")
        if source == "coinbase-candles":
            p["granularity"] = integer(query.get("granularity", 3600), 60, 86400)
            if p["granularity"] not in {60, 300, 900, 3600, 21600, 86400}:
                invalid()
            p["count"] = integer(query.get("count", 200), 1, 300)
            end = integer(query.get("end", int(now)), 0, int(now))
            p["end"] = end - end % p["granularity"]
            p["start"] = p["end"] - p["count"] * p["granularity"]
            if p["start"] < 0:
                invalid()
            upstream = {"granularity": p["granularity"], "start": stamp(p["start"]), "end": stamp(p["end"])}
            ttl = 300
        elif source == "coinbase-products":
            max_bytes, ttl = 8_000_000, 3600
        else:
            ttl = 10
    elif source.startswith("sec-"):
        p = {"cik": pattern(query.get("cik", "320193"), r"[0-9]{1,10}").zfill(10),
             "limit": integer(query.get("limit", 10), 1, 100)}
        ua = env.get("SZL_SEC_USER_AGENT", "").strip()
        if not 8 <= len(ua) <= 200 or "@" not in ua or any(ord(c) < 32 or ord(c) > 126 for c in ua):
            raise FinanceError("NEEDS_SEC_USER_AGENT")
        headers["User-Agent"] = ua
        if source == "sec-submissions":
            base = "https://data.sec.gov/submissions/CIK" + p["cik"] + ".json"
        else:
            base = "https://data.sec.gov/api/xbrl/companyfacts/CIK" + p["cik"] + ".json"
        max_bytes, ttl, interval = 16_000_000, 900, 0.2
    elif source.startswith("treasury-"):
        p["limit"] = integer(query.get("limit", 12), 1, 100)
        dataset = "avg_interest_rates" if source == "treasury-rates" else "debt_to_penny"
        base = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/" + dataset
        upstream = {"sort": "-record_date", "page[size]": p["limit"], "page[number]": 1}
        ttl = 3600
    elif source == "bls-series":
        p["series_id"] = pattern(query.get("series_id", "CUUR0000SA0"), r"[A-Z0-9]{3,30}")
        base = "https://api.bls.gov/publicAPI/v2/timeseries/data/" + p["series_id"]
        ttl, interval = 3600, 3600
    elif source == "fred-series":
        p = {"series_id": pattern(query.get("series_id", "GDP"), r"[A-Za-z0-9_.-]{1,64}"),
             "as_of": iso_date(query.get("as_of", stamp(now)[:10]), now),
             "limit": integer(query.get("limit", 24), 1, 1000)}
        key = env.get("SZL_FRED_API_KEY", "").strip()
        if not re.fullmatch(r"[a-z0-9]{32}", key):
            raise FinanceError("NEEDS_FRED_KEY")
        base = "https://api.stlouisfed.org/fred/series/observations"
        upstream = {"series_id": p["series_id"], "realtime_start": p["as_of"],
                    "realtime_end": p["as_of"], "limit": p["limit"], "sort_order": "desc",
                    "file_type": "json", "api_key": key}
        ttl = 3600
    elif source.startswith("alpaca-"):
        p["symbol"] = pattern(query.get("symbol", "SPY"), r"[A-Z][A-Z0-9.]{0,14}")
        feed = env.get("SZL_ALPACA_DATA_FEED", "iex")
        if feed not in {"iex", "sip", "delayed_sip"}:
            raise FinanceError("INVALID_ALPACA_FEED_CONFIGURATION")
        p["feed"] = feed
        for envname, header in (("APCA_API_KEY_ID", "APCA-API-KEY-ID"), ("APCA_API_SECRET_KEY", "APCA-API-SECRET-KEY")):
            value = env.get(envname, "").strip()
            if not value or len(value) > 512 or any(ord(c) < 33 or ord(c) > 126 for c in value):
                raise FinanceError("NEEDS_ALPACA_CREDENTIALS")
            headers[header] = value
        base = "https://data.alpaca.markets/v2/stocks/" + p["symbol"]
        upstream = {"feed": feed}
        if source == "alpaca-quote":
            base += "/quotes/latest"
            ttl = 10
        else:
            base += "/bars"
            p["timeframe"] = pattern(query.get("timeframe", "1Day"), r"1Min|15Min|1Hour|1Day")
            p["start"], start = utc_time(query.get("start", stamp(int(now) - 7 * 86400).split(".")[0].replace("+00:00", "Z")), now)
            p["end"], end = utc_time(query.get("end", stamp(int(now))), now)
            if not 0 < end - start <= 31 * 86400:
                invalid()
            p["limit"] = integer(query.get("limit", 200), 1, 1000)
            if query.get("page_token"):
                p["page_token"] = pattern(query["page_token"], r"[A-Za-z0-9_=+./~-]{1,2048}")
            upstream = {k: v for k, v in p.items() if k != "symbol"}
            upstream["adjustment"] = "raw"
            ttl = 300
    else:
        invalid()
    public = base + ("?" + urlencode({k: v for k, v in upstream.items() if k != "api_key"}) if upstream else "")
    url = base + ("?" + urlencode(upstream) if upstream else "")
    private_values = [env.get(k, "") for k in spec["required_environment"]]
    partition = hashlib.sha256("\x00".join(private_values).encode()).hexdigest() if private_values else "public"
    return Plan(source, spec["provider"], url, public, headers, p, ttl, max_bytes, interval, partition)


def obj(value: Any) -> dict:
    if not isinstance(value, dict):
        raise FinanceError("INVALID_SOURCE_SCHEMA")
    return value


def rows(value: Any, maximum: int = 5000) -> list:
    if not isinstance(value, list) or len(value) > maximum:
        raise FinanceError("INVALID_SOURCE_COLLECTION")
    return value


def text(value: Any, maximum: int = 12_000) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, str)) and not isinstance(value, bool):
        return str(value)[:maximum]
    raise FinanceError("INVALID_SOURCE_TEXT")


def identifier(value: Any, maximum: int = 200, required: bool = False) -> str | None:
    value = text(value, 100_000)
    if (value is None or not value) and required:
        raise FinanceError("MISSING_SOURCE_IDENTIFIER")
    if value is not None and len(value) > maximum:
        raise FinanceError("INVALID_SOURCE_IDENTIFIER")
    return value


def number(value: Any, *, low: str | None = None, high: str | None = None,
           optional: bool = True) -> str | None:
    if value is None or value in ("", ".", "null", "N/A"):
        if optional:
            return None
        raise FinanceError("MISSING_SOURCE_NUMBER")
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)) or len(str(value)) > 80:
        raise FinanceError("INVALID_SOURCE_NUMBER")
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise FinanceError("INVALID_SOURCE_NUMBER") from None
    if (not d.is_finite() or abs(d) > Decimal("1e30") or d.as_tuple().exponent < -30
            or (low is not None and d < Decimal(low)) or (high is not None and d > Decimal(high))):
        raise FinanceError("INVALID_SOURCE_NUMBER")
    return format(d, "f")


def probability(value: Any) -> str | None:
    return number(value, low="0", high="1")


def epoch(value: Any) -> int:
    v = number(value, low="0", high="9999999999999", optional=False)
    d = Decimal(v)
    if d != d.to_integral_value():
        raise FinanceError("INVALID_SOURCE_TIMESTAMP")
    return int(d)


def source_array(value: Any) -> list:
    if isinstance(value, str):
        value = strict_json(value.encode())
    return rows(value, 100)


def catalogue(data: list, *, pagination=None, **metadata) -> dict:
    return {"items": data, "count": len(data), "data_state": "AVAILABLE" if data else "EMPTY",
            "scope": "bounded provider response, not an all-market census",
            "pagination": pagination, **metadata}


def levels(value: Any, *, cents: bool = False, mappings: bool = False) -> list[dict]:
    result, seen = [], set()
    for row in rows(value):
        if mappings:
            row = obj(row)
            price, quantity = row.get("price"), row.get("size")
        else:
            row = rows(row, 2)
            if len(row) != 2:
                raise FinanceError("INVALID_BOOK_LEVEL")
            price, quantity = row
        price = number(price, low="0", high="100" if cents else "1", optional=False)
        if cents:
            price = str(Decimal(price) / 100)
        quantity = number(quantity, low="0", optional=False)
        key = Decimal(price)
        if key in seen:
            raise FinanceError("DUPLICATE_BOOK_LEVEL")
        seen.add(key)
        if Decimal(quantity) == 0:
            continue
        result.append({"price": price, "quantity": quantity})
    return sorted(result, key=lambda r: Decimal(r["price"]), reverse=True)


def orderbook(bids: list, asks: list, **metadata) -> dict:
    asks = sorted(asks, key=lambda r: Decimal(r["price"]))
    best_bid = bids[0]["price"] if bids else None
    best_ask = asks[0]["price"] if asks else None
    crossed = best_bid is not None and best_ask is not None and Decimal(best_bid) > Decimal(best_ask)
    spread = str(Decimal(best_ask) - Decimal(best_bid)) if best_bid is not None and best_ask is not None and not crossed else None
    return {"bids": bids, "asks": asks, "best_bid": best_bid, "best_ask": best_ask,
            "spread": spread, "crossed": crossed,
            "quality": "INVALID_CROSSED" if crossed else "TWO_SIDED" if spread is not None else "INCOMPLETE",
            "data_state": "AVAILABLE" if bids or asks else "EMPTY", "price_unit": "USD_per_contract",
            "execution_enabled": False, **metadata}


def normalize(source: str, payload: Any, p: dict, now: float) -> dict:
    if source == "polymarket-markets":
        output = []
        for row in rows(payload, p["limit"]):
            row = obj(row)
            labels = source_array(row.get("outcomes", []))
            prices = source_array(row.get("outcomePrices", []))
            tokens = source_array(row.get("clobTokenIds", []))
            flags = []
            aligned = len(labels) == len(prices) == len(tokens) and len(labels) > 0
            if not aligned:
                flags.append("OUTCOME_ARRAY_LENGTH_MISMATCH")
            outcomes = []
            for i, label in enumerate(labels):
                value = None
                if len(prices) == len(labels):
                    try:
                        value = probability(prices[i])
                    except FinanceError:
                        flags.append("INVALID_PRICE_AT_" + str(i))
                token = identifier(tokens[i], 80) if len(tokens) == len(labels) else None
                if token is not None and re.fullmatch(r"[0-9]{1,80}", token) is None:
                    token = None
                    flags.append("INVALID_TOKEN_AT_" + str(i))
                outcomes.append({"index": i, "label": text(label, 200), "price": value, "token_id": token})
            output.append({"venue": "polymarket", "market_id": identifier(row.get("id"), 100, True),
                "condition_id": identifier(row.get("conditionId"), 100), "question": text(row.get("question")),
                "description": text(row.get("description")),
                "description_truncated": isinstance(row.get("description"), str) and len(row["description"]) > 12_000, "resolution_source": text(row.get("resolutionSource")),
                "end_date": text(row.get("endDate"), 100), "updated_at": text(row.get("updatedAt"), 100),
                "active": row.get("active") is True, "closed": row.get("closed") is True,
                "book_enabled": row.get("enableOrderBook") is True, "outcomes": outcomes,
                "volume_24h_usd": number(row.get("volume24hr"), low="0"),
                "volume_lifetime_usd": number(row.get("volumeNum", row.get("volume")), low="0"),
                "liquidity_usd": number(row.get("liquidityNum", row.get("liquidity")), low="0"),
                "quality_flags": flags, "cross_venue_equivalence": "NOT_ESTABLISHED"})
        return catalogue(output, pagination={"offset": p["offset"], "limit": p["limit"],
            "next_offset_candidate": p["offset"] + len(output) if len(output) == p["limit"] else None,
            "has_more": "UNKNOWN"})
    if source == "polymarket-book":
        raw = obj(payload)
        if identifier(raw.get("asset_id"), 80, True) != p["token_id"]:
            raise FinanceError("OUTCOME_TOKEN_IDENTITY_MISMATCH")
        bids = levels(raw.get("bids"), mappings=True)
        asks = levels(raw.get("asks"), mappings=True)
        provider_time = epoch(raw.get("timestamp")) if raw.get("timestamp") is not None else None
        if provider_time is not None and provider_time / 1000 > now + 5:
            raise FinanceError("PROVIDER_CLOCK_AHEAD")
        age = max(0, now - provider_time / 1000) if provider_time is not None else None
        return orderbook(bids, asks, token_id=p["token_id"], provider_timestamp_ms=provider_time,
            provider_age_seconds=age, source_freshness="UNKNOWN" if age is None else "STALE" if age > 30 else "WITHIN_30_SECONDS", asks_kind="REPORTED", tick_size=number(raw.get("tick_size"), low="0"),
            min_order_size=number(raw.get("min_order_size"), low="0"))
    if source == "polymarket-history":
        history, seen = [], set()
        for row in rows(obj(payload).get("history"), 5000):
            row = obj(row)
            t = epoch(row.get("t"))
            if t in seen or t > now + 5:
                raise FinanceError("INVALID_HISTORY_TIMESTAMP")
            seen.add(t)
            history.append({"time": t, "price": probability(row.get("p"))})
        return catalogue(sorted(history, key=lambda r: r["time"]), token_id=p["token_id"],
                         timestamp_unit="epoch_seconds", interpolation="NONE")
    if source == "kalshi-markets":
        raw, output = obj(payload), []
        def quoted(row, key):
            if key + "_dollars" in row:
                return probability(row[key + "_dollars"])
            v = number(row.get(key), low="0", high="100")
            return str(Decimal(v) / 100) if v is not None else None
        for row in rows(raw.get("markets"), p["limit"]):
            row = obj(row)
            bid, ask = quoted(row, "yes_bid"), quoted(row, "yes_ask")
            output.append({"venue": "kalshi", "ticker": identifier(row.get("ticker"), 200, True),
                "event_ticker": text(row.get("event_ticker"), 200), "title": text(row.get("title")),
                "yes_sub_title": text(row.get("yes_sub_title")), "no_sub_title": text(row.get("no_sub_title")),
                "rules_primary": text(row.get("rules_primary")), "rules_secondary": text(row.get("rules_secondary")),
                "rules_truncated": any(isinstance(row.get(k), str) and len(row[k]) > 12_000 for k in ("rules_primary", "rules_secondary")),
                "close_time": text(row.get("close_time"), 100), "status": text(row.get("status"), 100),
                "yes_bid": bid, "yes_ask": ask, "last_price": quoted(row, "last_price"),
                "price_unit": "USD_per_contract", "volume_unit": "contracts",
                "volume_24h": number(row.get("volume_24h_fp", row.get("volume_24h")), low="0"),
                "volume_lifetime": number(row.get("volume_fp", row.get("volume")), low="0"),
                "crossed": bid is not None and ask is not None and Decimal(bid) > Decimal(ask),
                "cross_venue_equivalence": "NOT_ESTABLISHED"})
        return catalogue(output, pagination={"next_cursor": identifier(raw.get("cursor"), 2048), "limit": p["limit"]})
    if source == "kalshi-book":
        raw = obj(payload)
        if "orderbook_fp" in raw:
            raw = obj(raw["orderbook_fp"])
            yes, no = levels(raw.get("yes_dollars")), levels(raw.get("no_dollars"))
            format_name = "fixed_point_dollars"
        else:
            raw = obj(raw.get("orderbook"))
            yes, no = levels(raw.get("yes"), cents=True), levels(raw.get("no"), cents=True)
            format_name = "legacy_integer_cents"
        asks = [{"price": str(Decimal(1) - Decimal(r["price"])), "quantity": r["quantity"]} for r in no]
        return orderbook(yes, asks, ticker=p["ticker"], no_bids=no, provider_timestamp=None,
            provider_age_seconds=None, asks_kind="DERIVED_COMPLEMENT_OF_NO_BIDS", venue_format=format_name)
    if source == "coinbase-products":
        return catalogue([{k: text(obj(row).get(k), 200) for k in
            ("id", "base_currency", "quote_currency", "base_increment", "quote_increment", "status")}
            | {"trading_disabled": obj(row).get("trading_disabled") is True}
            for row in rows(payload, 5000)])
    if source == "coinbase-ticker":
        raw = obj(payload)
        return {"product": p["product"], "price": number(raw.get("price"), low="0", optional=False),
            "bid": number(raw.get("bid"), low="0"), "ask": number(raw.get("ask"), low="0"),
            "last_trade_time": text(raw.get("time"), 100), "volume_24h_base_units": number(raw.get("volume"), low="0"),
            "data_state": "AVAILABLE", "price_kind": "LAST_TRADE_NOT_EXECUTION_QUOTE"}
    if source == "coinbase-candles":
        output, seen, excluded = [], set(), 0
        for row in rows(payload, 300):
            row = rows(row, 6)
            if len(row) != 6:
                raise FinanceError("INVALID_CANDLE_SCHEMA")
            t = epoch(row[0])
            if t in seen or t % p["granularity"]:
                raise FinanceError("INVALID_CANDLE_TIMESTAMP")
            seen.add(t)
            low, high, opened, close, volume = [number(x, low="0", optional=False) for x in row[1:]]
            if not Decimal(low) <= min(Decimal(opened), Decimal(close)) <= max(Decimal(opened), Decimal(close)) <= Decimal(high) or Decimal(low) <= 0:
                raise FinanceError("INVALID_OHLC_ORDER")
            if t < p["start"] or t >= p["end"] or t + p["granularity"] > now:
                excluded += 1
                continue
            output.append({"time": t, "open": opened, "high": high, "low": low, "close": close, "volume": volume})
        output.sort(key=lambda row: row["time"])
        missing = sorted(set(range(p["start"], p["end"], p["granularity"])) - {r["time"] for r in output})
        return catalogue(output, product=p["product"], granularity_seconds=p["granularity"],
            timestamp_unit="epoch_seconds", window_start=p["start"], window_end_exclusive=p["end"],
            missing_intervals=missing, excluded_outside_window=excluded, interpolation="NONE",
            window_complete=bool(output) and not missing)
    if source == "sec-submissions":
        raw = obj(payload)
        actual_cik = identifier(raw.get("cik"), 10, True)
        if not actual_cik or actual_cik.zfill(10) != p["cik"]:
            raise FinanceError("CIK_IDENTITY_MISMATCH")
        filings = obj(raw.get("filings"))
        recent = obj(filings.get("recent"))
        fields = ("accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "primaryDocument")
        arrays = {k: rows(recent.get(k), 5000) for k in fields}
        count = len(arrays["accessionNumber"])
        if any(len(a) != count for a in arrays.values()):
            raise FinanceError("FILING_COLUMN_LENGTH_MISMATCH")
        output = [{k: text(arrays[k][i], 500) for k in fields} for i in range(min(count, p["limit"]))]
        return catalogue(output, cik=p["cik"], entity=text(raw.get("name")),
            recent_records_available=count, historical_files_available=len(rows(filings.get("files", []))),
            historical_files_fetched=False)
    if source == "sec-companyfacts":
        raw = obj(payload)
        if (identifier(raw.get("cik"), 10, True) or "").zfill(10) != p["cik"]:
            raise FinanceError("CIK_IDENTITY_MISMATCH")
        gaap = obj(obj(raw.get("facts")).get("us-gaap", {}))
        output = []
        for concept in ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "NetIncomeLoss", "Assets", "Liabilities", "StockholdersEquity"):
            units = obj(obj(gaap.get(concept, {})).get("units", {}))
            for unit, entries in units.items():
                entries = rows(entries, 20_000)
                entries = sorted([obj(e) for e in entries], key=lambda e: text(e.get("filed"), 20) or "", reverse=True)
                for row in entries[:min(p["limit"], 20)]:
                    output.append({"concept": concept, "unit": text(unit, 100), "value": number(row.get("val")),
                        **{k: text(row.get(k), 100) for k in ("start", "end", "filed", "form", "accn", "fy", "fp", "frame")}})
        return catalogue(output, cik=p["cik"], entity=text(raw.get("entityName")),
                         comparison="PERIODS_AND_UNITS_MUST_BE_MATCHED; no annual-period inference")
    if source in {"treasury-rates", "treasury-debt"}:
        raw, output = obj(payload), []
        for row in rows(raw.get("data"), 100):
            row = obj(row)
            item = {"record_date": text(row.get("record_date"), 20)}
            if source == "treasury-rates":
                item.update(security_type=text(row.get("security_type_desc")),
                    security_description=text(row.get("security_desc")), average_interest_rate_percent=number(row.get("avg_interest_rate_amt"), optional=False))
            else:
                item.update(total_public_debt_outstanding_usd=number(row.get("tot_pub_debt_out_amt"), low="0", optional=False))
            output.append(item)
        meta = obj(raw.get("meta", {}))
        return catalogue(output, pagination={"page": 1, "limit": p["limit"],
            "total_pages_reported": text(meta.get("total-pages"), 20)},
            measurement="average_interest_rate_not_spot_yield" if source == "treasury-rates" else "debt_outstanding")
    if source == "bls-series":
        raw = obj(payload)
        if raw.get("status") != "REQUEST_SUCCEEDED":
            raise FinanceError("BLS_REQUEST_NOT_SUCCEEDED", 3600)
        series = rows(obj(raw.get("Results")).get("series"), 1)
        if len(series) != 1 or obj(series[0]).get("seriesID") != p["series_id"]:
            raise FinanceError("SERIES_IDENTITY_MISMATCH")
        output = []
        for row in rows(series[0].get("data"), 1000):
            row = obj(row)
            output.append({"year": text(row.get("year"), 4), "period": text(row.get("period"), 8),
                "period_name": text(row.get("periodName"), 100),
                # BLS explicitly documents '-' as missing CPI data in its API.
                # Preserve the marker and footnote; never substitute zero or impute.
                "value": None if row.get("value") == "-" else number(row.get("value")),
                "missing_value_marker": "-" if row.get("value") == "-" else None,
                "is_annual_average": row.get("period") == "M13",
                "footnotes": [{k: text(obj(n).get(k), 2000) for k in ("code", "text")} for n in rows(row.get("footnotes", []), 100)]})
        return catalogue(output, series_id=p["series_id"], vintage="LATEST_PROVIDER_RESPONSE; release vintage not established")
    if source == "fred-series":
        raw = obj(payload)
        if raw.get("realtime_start") != p["as_of"] or raw.get("realtime_end") != p["as_of"]:
            raise FinanceError("FRED_VINTAGE_MISMATCH")
        output = [{"date": text(obj(row).get("date"), 20), "value": number(row.get("value")),
                   "realtime_start": text(row.get("realtime_start"), 20), "realtime_end": text(row.get("realtime_end"), 20)}
                  for row in rows(raw.get("observations"), 1000)]
        return catalogue(output, series_id=p["series_id"], as_of=p["as_of"], units="lin; see source series metadata")
    if source == "alpaca-quote":
        raw = obj(payload)
        if raw.get("symbol") != p["symbol"]:
            raise FinanceError("SYMBOL_IDENTITY_MISMATCH")
        quote = obj(raw.get("quote"))
        return {"symbol": p["symbol"], "feed": p["feed"], "timestamp": text(quote.get("t"), 100),
            "bid": number(quote.get("bp"), low="0"), "ask": number(quote.get("ap"), low="0"),
            "bid_size": number(quote.get("bs"), low="0"), "ask_size": number(quote.get("as"), low="0"),
            "bid_exchange": text(quote.get("bx"), 20), "ask_exchange": text(quote.get("ax"), 20),
            "data_state": "AVAILABLE", "redistribution": "PRIVATE_AUTHENTICATED_RESPONSE_ONLY"}
    if source == "alpaca-bars":
        raw = obj(payload)
        if raw.get("symbol") != p["symbol"]:
            raise FinanceError("SYMBOL_IDENTITY_MISMATCH")
        output = []
        for row in rows(raw.get("bars"), 1000):
            row = obj(row)
            values = {k: number(row.get(k), low="0", optional=False) for k in ("o", "h", "l", "c", "v")}
            if not Decimal(values["l"]) <= min(Decimal(values["o"]), Decimal(values["c"])) <= max(Decimal(values["o"]), Decimal(values["c"])) <= Decimal(values["h"]):
                raise FinanceError("INVALID_OHLC_ORDER")
            output.append({"timestamp": text(row.get("t"), 100), **values})
        return catalogue(output, symbol=p["symbol"], feed=p["feed"], timeframe=p["timeframe"], adjustment="raw",
            pagination={"next_page_token": identifier(raw.get("next_page_token"), 2048)},
            session_completeness_verified=False, replay_eligible=False,
            redistribution="PRIVATE_AUTHENTICATED_RESPONSE_ONLY")
    raise FinanceError("UNKNOWN_SOURCE")
