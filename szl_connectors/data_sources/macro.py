# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""a11oy macro / filings live connectors.

  sec_edgar   SEC EDGAR submissions + XBRL frames  (keyless; UA header required)  → CONNECTED now
  fred        FRED macro series (St. Louis Fed)     (free key SZL_FRED_API_KEY)    → READY → CONNECTED on key
"""
from __future__ import annotations

import os
import time
from typing import Any

from ..base import Connector, Records, State, http_json, _now
from ..registry import register

_CACHE: dict[str, tuple[float, Any]] = {}


def _cached(k, ttl):
    h = _CACHE.get(k)
    return h[1] if h and (time.time() - h[0]) < ttl else None


def _put(k, v):
    _CACHE[k] = (time.time(), v)


# ── SEC EDGAR (keyless, live) ────────────────────────────────────────────────
@register
class SecEdgarConnector(Connector):
    id = "sec_edgar"
    label = "SEC EDGAR filings/XBRL"
    category = "macro"
    auth_kind = "none"
    free_tier = True
    provider_base = "https://data.sec.gov"
    docs_url = "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
    schema_preview = ["form", "filingDate", "accessionNumber", "primaryDocument", "reportDate"]

    def _probe(self):
        # Apple CIK 0000320193 submissions as a cheap live probe
        st, _ = http_json(self.provider_base + "/submissions/CIK0000320193.json")
        return (st == 200), f"EDGAR HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        cik = str((query or {}).get("cik", "320193")).zfill(10)
        limit = max(1, min(int((query or {}).get("limit", 12)), 40))
        ck = f"edgar:{cik}:{limit}"
        c = _cached(ck, 600)
        if c:
            return c
        st, raw = http_json(f"{self.provider_base}/submissions/CIK{cik}.json")
        if st == 200 and isinstance(raw, dict):
            recent = raw.get("filings", {}).get("recent", {})
            forms = recent.get("form", []); dates = recent.get("filingDate", [])
            accs = recent.get("accessionNumber", []); docs = recent.get("primaryDocument", [])
            rdates = recent.get("reportDate", [])
            items = [{"form": forms[i] if i < len(forms) else None,
                      "filingDate": dates[i] if i < len(dates) else None,
                      "accessionNumber": accs[i] if i < len(accs) else None,
                      "primaryDocument": docs[i] if i < len(docs) else None,
                      "reportDate": rdates[i] if i < len(rdates) else None}
                     for i in range(min(limit, len(forms)))]
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=items, source=f"SEC EDGAR /submissions/CIK{cik}", live=True,
                        note=f"live · {raw.get('name','')} (CIK {cik})", schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"EDGAR unreachable (HTTP {st})")


# ── FRED (free key) ───────────────────────────────────────────────────────────
@register
class FredConnector(Connector):
    id = "fred"
    label = "FRED macro series (St. Louis Fed)"
    category = "macro"
    auth_kind = "api_key"
    free_tier = True   # a FREE key exists (minted once)
    env_vars = ["SZL_FRED_API_KEY"]
    provider_base = "https://api.stlouisfed.org/fred"
    docs_url = "https://fred.stlouisfed.org/docs/api/fred/"
    schema_preview = ["series_id", "date", "value"]

    def _probe(self):
        key = os.environ.get("SZL_FRED_API_KEY")
        if not key:
            return None, "no key"
        st, _ = http_json(f"{self.provider_base}/series/observations"
                          f"?series_id=GNPCA&file_type=json&api_key={key}&limit=1")
        return (st == 200), f"FRED HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        key = os.environ.get("SZL_FRED_API_KEY")
        if not key:
            return self._ready_records("provide credentials to activate — set SZL_FRED_API_KEY "
                                       "(free key: https://fred.stlouisfed.org/docs/api/api_key.html)")
        series = (query or {}).get("series_id", "GNPCA")
        limit = max(1, min(int((query or {}).get("limit", 12)), 60))
        st, raw = http_json(f"{self.provider_base}/series/observations"
                            f"?series_id={series}&file_type=json&api_key={key}"
                            f"&sort_order=desc&limit={limit}")
        if st == 200 and isinstance(raw, dict):
            items = [{"series_id": series, "date": o.get("date"), "value": o.get("value")}
                     for o in (raw.get("observations", []) or [])[:limit]]
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=items, source=f"FRED /series/observations {series}", live=True,
                           note="live (free key)", schema_preview=self.schema_preview)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but FRED returned HTTP {st}",
                       schema_preview=self.schema_preview)


__all__ = ["SecEdgarConnector", "FredConnector"]
