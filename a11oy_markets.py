#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
# Change-class: ADDITIVE — Doctrine v11 LOCKED. locked=8; Λ=Conjecture 1; BFT=Conjecture 2.
"""a11oy_markets — REAL free live BUSINESS / MARKETS data, server-side.

Wires three keyless/free public feeds for the BUSINESS cluster, each fetched
server-side with a bounded timeout + short TTL cache + an HONEST fallback that
NEVER fabricates a number (it reports the source status instead):

  GET /api/a11oy/v1/markets/company?cik=320193
        SEC EDGAR XBRL companyfacts — real 10-K financials (revenue, net income,
        assets, equity) for a real filer.  Keyless; UA header required.
        https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json

  GET /api/a11oy/v1/markets/debt
        U.S. Treasury FiscalData "debt to the penny" — the live national debt.
        Keyless.  https://api.fiscaldata.treasury.gov/.../v2/accounting/od/debt_to_penny

  GET /api/a11oy/v1/markets/macro?series_id=GDP
        FRED economic series (St. Louis Fed) — GDP / CPI / unemployment.  Needs a
        FREE key (SZL_FRED_API_KEY).  No key -> honest READY (path wired, NO faked
        numbers).  With key -> live CONNECTED observations.

Leader features adapted (made ours): Palantir Foundry's ontology-driven BI — every
figure carries its source, concept (XBRL tag / Treasury field / FRED series), and
an honest state label — and Bloomberg's cross-asset macro context (company facts
sit next to sovereign debt + Fed macro on one surface). Markets data is
INFORMATIONAL, not investment advice.
"""

import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

try:
    from szl_connectors.base import http_json
except Exception:  # pragma: no cover — keep route registration resilient
    import json as _json
    import urllib.error as _ue
    import urllib.request as _ur

    _UA_FALLBACK = "SZL-Connectors/1.0 (sovereign enterprise mesh; contact@szlholdings.ai)"

    def http_json(url, headers=None, method="GET", data=None, timeout=8.0):
        req = _ur.Request(url, headers={"User-Agent": _UA_FALLBACK, **(headers or {})},
                          method=method, data=data)
        try:
            with _ur.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
                try:
                    return resp.status, _json.loads(raw)
                except Exception:
                    return resp.status, raw
        except _ue.HTTPError as e:
            return e.code, ""
        except Exception as e:
            return 0, str(e)

_TIMEOUT = 8.0
_CACHE = {}


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cached(key, ttl):
    hit = _CACHE.get(key)
    return hit[1] if hit and (time.time() - hit[0]) < ttl else None


def _put(key, value):
    _CACHE[key] = (time.time(), value)
    return value


# ── SEC EDGAR companyfacts (keyless, live) ──────────────────────────────────
# Candidate US-GAAP concepts per metric (filers tag revenue differently).
_CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "stockholders_equity": ["StockholdersEquity",
                            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
}


def _latest_annual(facts, concepts):
    """Return the most recent ANNUAL (10-K, full-year) USD value for the first
    matching concept. Picks the entry with the latest period END date, preferring
    full-year (fp=='FY') 10-K filings. Returns dict or None — never fabricates."""
    gaap = (facts or {}).get("facts", {}).get("us-gaap", {})
    for concept in concepts:
        units = gaap.get(concept, {}).get("units", {}).get("USD")
        if not units:
            continue
        annual = [u for u in units
                  if u.get("form") in ("10-K", "10-K/A") and u.get("fp") == "FY" and u.get("end")]
        pool = annual or [u for u in units if u.get("end")]
        if not pool:
            continue
        best = max(pool, key=lambda u: u.get("end", ""))
        return {"concept": concept, "value": best.get("val"), "period_end": best.get("end"),
                "fiscal_year": best.get("fy"), "form": best.get("form"),
                "accession": best.get("accn")}
    return None


def _company(cik_raw):
    cik = "".join(ch for ch in str(cik_raw) if ch.isdigit()) or "320193"
    cik10 = cik.zfill(10)
    ck = f"markets:company:{cik10}"
    cached = _cached(ck, 1800)
    if cached:
        return cached
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
    st, raw = http_json(url, timeout=_TIMEOUT)
    if st == 200 and isinstance(raw, dict):
        metrics = {}
        for metric, concepts in _CONCEPTS.items():
            found = _latest_annual(raw, concepts)
            if found:
                metrics[metric] = found
        body = {
            "ok": True, "live": True, "state": "MEASURED",
            "source": "SEC EDGAR XBRL companyfacts",
            "source_label": "live from SEC",
            "source_url": url,
            "cik": cik10,
            "entity": raw.get("entityName"),
            "currency": "USD",
            "metrics": metrics,
            "note": "Real 10-K financials parsed from SEC EDGAR XBRL companyfacts. "
                    "Informational, not investment advice.",
            "advisory": "informational — not investment advice",
            "fetched_at": _now(),
        }
        return _put(ck, body)
    return {
        "ok": False, "live": False, "state": "SAMPLE",
        "source": "SEC EDGAR XBRL companyfacts", "source_label": "live from SEC",
        "source_url": url, "cik": cik10, "metrics": {},
        "note": f"SEC EDGAR unreachable at request time (HTTP {st}); no figures fabricated.",
        "advisory": "informational — not investment advice",
        "fetched_at": _now(),
    }


def _debt():
    ck = "markets:debt"
    cached = _cached(ck, 1800)
    if cached:
        return cached
    url = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
           "/v2/accounting/od/debt_to_penny"
           "?sort=-record_date&page[size]=1&fields=record_date,tot_pub_debt_out_amt")
    st, raw = http_json(url, timeout=_TIMEOUT)
    if st == 200 and isinstance(raw, dict) and raw.get("data"):
        row = raw["data"][0]
        amt = row.get("tot_pub_debt_out_amt")
        try:
            amt_num = float(amt)
        except (TypeError, ValueError):
            amt_num = None
        body = {
            "ok": True, "live": True, "state": "MEASURED",
            "source": "U.S. Treasury FiscalData — Debt to the Penny",
            "source_label": "live from Treasury",
            "source_url": "https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/debt-to-the-penny",
            "record_date": row.get("record_date"),
            "total_public_debt_outstanding_usd": amt_num,
            "total_public_debt_outstanding_raw": amt,
            "note": "Live U.S. national debt (total public debt outstanding) from the "
                    "Treasury FiscalData API. Keyless public feed.",
            "fetched_at": _now(),
        }
        return _put(ck, body)
    return {
        "ok": False, "live": False, "state": "SAMPLE",
        "source": "U.S. Treasury FiscalData — Debt to the Penny",
        "source_label": "live from Treasury", "source_url": url,
        "total_public_debt_outstanding_usd": None,
        "note": f"Treasury FiscalData unreachable at request time (HTTP {st}); no figure fabricated.",
        "fetched_at": _now(),
    }


def _macro(series_id):
    series = "".join(ch for ch in str(series_id) if ch.isalnum()) or "GDP"
    key = os.environ.get("SZL_FRED_API_KEY")
    base = "https://api.stlouisfed.org/fred/series/observations"
    if not key:
        return {
            "ok": False, "live": False, "state": "ROADMAP",
            "source": "FRED economic series (St. Louis Fed)",
            "source_label": "live from Fed (free key required)",
            "source_url": "https://fred.stlouisfed.org/series/" + series,
            "series_id": series, "observations": [],
            "note": "FRED path wired; set free key SZL_FRED_API_KEY to activate live data "
                    "(https://fred.stlouisfed.org/docs/api/api_key.html). No numbers fabricated.",
            "fetched_at": _now(),
        }
    ck = f"markets:macro:{series}"
    cached = _cached(ck, 1800)
    if cached:
        return cached
    url = (f"{base}?series_id={series}&file_type=json&api_key={key}"
           "&sort_order=desc&limit=12")
    st, raw = http_json(url, timeout=_TIMEOUT)
    if st == 200 and isinstance(raw, dict):
        obs = [{"date": o.get("date"), "value": o.get("value")}
               for o in (raw.get("observations") or [])[:12]]
        body = {
            "ok": True, "live": True, "state": "MEASURED",
            "source": f"FRED /series/observations {series}",
            "source_label": "live from Fed",
            "source_url": "https://fred.stlouisfed.org/series/" + series,
            "series_id": series, "observations": obs,
            "note": "Live FRED observations (free key).",
            "fetched_at": _now(),
        }
        return _put(ck, body)
    return {
        "ok": False, "live": False, "state": "SAMPLE",
        "source": f"FRED /series/observations {series}",
        "source_label": "live from Fed", "source_url": base,
        "series_id": series, "observations": [],
        "note": f"FRED key present but provider returned HTTP {st}; no numbers fabricated.",
        "fetched_at": _now(),
    }


# ── FastAPI router (ADDITIVE; registered before the SPA catch-all) ──────────
router = APIRouter()


@router.get("/api/a11oy/v1/markets/company")
@router.get("/v1/markets/company")
def markets_company(cik: str = "320193"):
    return JSONResponse(_company(cik))


@router.get("/api/a11oy/v1/markets/debt")
@router.get("/v1/markets/debt")
def markets_debt():
    return JSONResponse(_debt())


@router.get("/api/a11oy/v1/markets/macro")
@router.get("/v1/markets/macro")
def markets_macro(series_id: str = "GDP"):
    return JSONResponse(_macro(series_id))


@router.get("/api/a11oy/v1/markets/summary")
@router.get("/v1/markets/summary")
def markets_summary(cik: str = "320193", series_id: str = "GDP"):
    """One cross-asset surface: a real filer's SEC financials + live national debt
    + a Fed macro series — Bloomberg-style macro context, ontology-labelled."""
    return JSONResponse({
        "ok": True,
        "doctrine": {"locked": 8, "lambda": "Conjecture 1", "bft": "Conjecture 2"},
        "advisory": "informational — not investment advice; public data only",
        "company": _company(cik),
        "national_debt": _debt(),
        "macro": _macro(series_id),
        "fetched_at": _now(),
    })


def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Attach the markets router. ADDITIVE — registered BEFORE the SPA catch-all +
    Node proxy so /api/a11oy/v1/markets/* resolves LOCALLY. Touches no existing route."""
    app.include_router(router)
    # Front-move our routes ahead of any pre-existing SPA catch-all so the
    # /v1/... + /api/a11oy/v1/... forms match before the HTML fallback.
    try:
        ours, others = [], []
        for r in app.router.routes:
            path = getattr(r, "path", "")
            (ours if "/markets/" in path else others).append(r)
        if ours:
            app.router.routes[:] = ours + others
    except Exception:  # pragma: no cover — never break boot
        pass
    return ("a11oy.v1.markets mounted: GET /api/a11oy/v1/markets/{company,debt,macro,summary} "
            "(SEC EDGAR companyfacts + Treasury debt-to-penny + FRED; live, honest fallback)")


def attach(app: FastAPI) -> str:
    return register(app, ns="a11oy")


__all__ = ["router", "register", "attach"]
