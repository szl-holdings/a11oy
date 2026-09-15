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
        FRED economic series (St. Louis Fed) — GDP / CPI / unemployment.
        Owner-authenticated compatibility view of the canonical private FRED
        reader. Both an API key and X-SZL-Finance-Read-Token are required.

Leader features adapted (made ours): Palantir Foundry's ontology-driven BI — every
figure carries its source, concept (XBRL tag / Treasury field / FRED series), and
an honest state label — and Bloomberg's cross-asset macro context (company facts
sit next to sovereign debt + Fed macro on one surface). Markets data is
INFORMATIONAL, not investment advice.
"""

import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI, Request
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


def _macro(series_id, access_token=None):
    """Compatibility view of the one canonical private FRED reader.

    The legacy route must not become a credential/entitlement bypass merely
    because it predates /finance. No independent FRED HTTP client or cache.
    """
    import importlib
    canonical_routes = importlib.import_module("verticals.puriq-markets.runtime.routes")
    canonical_transport = importlib.import_module("verticals.puriq-markets.runtime.transport")
    try:
        observation = canonical_routes.CLIENT.observe(
            "fred-series", {"series_id": series_id}, access_token=access_token,
        )
    except canonical_transport.FinanceError as exc:
        return {"ok": False, "live": False, "state": "UNAVAILABLE",
                "error": exc.code, "source": "FRED private read",
                "source_label": "Canonical owner-authenticated FRED reader",
                "series_id": None, "observations": [], "execution_enabled": False,
                "note": "Use the canonical owner read credential; it is never accepted in a URL.",
                "fetched_at": _now()}
    data = observation.get("data") or {}
    return {"ok": observation["ok"], "live": False, "state": observation["state"],
            "error": observation.get("error"), "source": "FRED private read",
            "source_label": "Canonical owner-authenticated FRED reader",
            "series_id": data.get("series_id", series_id),
            "as_of": data.get("as_of"), "observations": data.get("items", []),
            "source_revision": observation["source_revision"],
            "provenance": observation.get("provenance"),
            "execution_enabled": False, "fetched_at": observation.get("retrieved_at"),
            "note": "Historical observations at the explicit reported as-of date; not live executable quotes."}


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
def markets_macro(request: Request, series_id: str = "GDP"):
    body = _macro(series_id, request.headers.get("X-SZL-Finance-Read-Token"))
    status = 200 if body["ok"] else 403 if body.get("error") == "PRIVATE_SOURCE_ACCESS_REQUIRED" else 422 if body.get("error") == "INVALID_PARAMETERS" else 503
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/api/a11oy/v1/markets/summary")
@router.get("/v1/markets/summary")
def markets_summary(request: Request, cik: str = "320193", series_id: str = "GDP"):
    """Compatibility summary; partial failure is not aggregate success."""
    company, debt = _company(cik), _debt()
    macro = _macro(series_id, request.headers.get("X-SZL-Finance-Read-Token"))
    complete = all(row.get("ok") is True for row in (company, debt, macro))
    return JSONResponse({
        "ok": complete, "state": "SNAPSHOTS_AVAILABLE" if complete else "DEGRADED",
        "doctrine": {"locked": 8, "lambda": "Conjecture 1", "bft": "Conjecture 2"},
        "advisory": "informational, not investment advice; FRED requires owner-authenticated access",
        "company": company, "national_debt": debt, "macro": macro,
        "execution_enabled": False, "fetched_at": _now(),
    }, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Register once, ahead of SPA fallbacks, with flat or grouped routers."""
    if getattr(app.state, "szl_legacy_markets_registered", False):
        return "a11oy markets already mounted"
    before = {id(route) for route in app.router.routes}
    app.include_router(router)
    added = [route for route in app.router.routes if id(route) not in before]
    if not added:
        raise RuntimeError("legacy market router registration produced no route objects")
    app.router.routes[:] = added + [route for route in app.router.routes if id(route) in before]
    import importlib
    importlib.import_module("verticals.puriq-markets.runtime.routes").register(app)
    app.state.szl_legacy_markets_registered = True
    return "a11oy market compatibility routes and canonical finance sources mounted; no execution"


def attach(app: FastAPI) -> str:
    return register(app, ns="a11oy")


__all__ = ["router", "register", "attach"]
