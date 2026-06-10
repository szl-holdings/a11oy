# a11oy_seismic.py — Honest statistical aftershock forecasting from REAL USGS data.
# ---------------------------------------------------------------------------
# Clean-room implementation (SZL Holdings, MIT). NO third-party code is copied;
# the math below is the published Reasenberg & Jones (1989,1994) / Omori-Utsu
# (Utsu 1961) aftershock-rate model, which is public-domain science.
#
# DOCTRINE: This is a STATISTICAL FORECAST, NOT A CERTAINTY and NOT a locked
# proven claim. It is never folded into the locked-8. Every response is
# labelled "statistical forecast — not certainty". Data is fetched LIVE from
# the public USGS Earthquake Hazards Program feeds (no fabrication; on a feed
# failure we return an honest error/stale marker, never invented numbers).
#
# Live data sources (public, attributed in every payload):
#   - USGS summary feeds:  https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{level}_{window}.geojson
#   - USGS ComCat FDSN:    https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&...
#
# Model (Reasenberg-Jones 1994, generic California parameters as the honest
# default prior; clearly disclosed):
#   Modified-Omori rate of aftershocks >= M at time t (days) after a mainshock
#   of magnitude Mm:
#       lambda(t, M) = 10^(a + b*(Mm - M)) * (t + c)^(-p)
#   Expected count in [T1, T2] days (p != 1):
#       N(M; T1,T2) = 10^(a + b*(Mm - M)) * ( (T2+c)^(1-p) - (T1+c)^(1-p) ) / (1-p)
#   Probability of >= 1 aftershock >= M in the window (Poisson):
#       P(>=1) = 1 - exp(-N)
#   95% range: Poisson quantiles around N (honest count uncertainty).
#
# Generic R&J parameters (Reasenberg & Jones 1994, Table; widely used defaults):
#   a = -1.67, b = 1.0, c = 0.05 days, p = 1.08
# These are PRIOR generic values, NOT fit to the specific sequence — disclosed.
# ---------------------------------------------------------------------------

from __future__ import annotations

import json
import math
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Generic Reasenberg-Jones (1994) aftershock parameters (PRIOR, disclosed).
# ---------------------------------------------------------------------------
RJ_A = -1.67   # productivity (generic California)
RJ_B = 1.00    # Gutenberg-Richter b-value (generic)
RJ_C = 0.05    # Omori offset, days
RJ_P = 1.08    # Omori decay exponent

USGS_SUMMARY = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{level}_{window}.geojson"
USGS_FDSN = "https://earthquake.usgs.gov/fdsnws/event/1/query"

_VALID_LEVELS = {"significant", "4.5", "2.5", "1.0", "all"}
_VALID_WINDOWS = {"hour", "day", "week", "month"}

_DISCLAIMER = (
    "STATISTICAL FORECAST — NOT A CERTAINTY. This is the published "
    "Reasenberg-Jones / Omori-Utsu aftershock-rate model evaluated with GENERIC "
    "prior parameters (a=-1.67, b=1.0, c=0.05d, p=1.08), not a sequence-specific "
    "fit. It is NOT one of a11oy's locked-proven claims and is never treated as "
    "certainty. Source data is live USGS. Real operational forecasts require "
    "sequence-specific parameter estimation and expert review."
)

_ATTRIBUTION = {
    "data_source": "U.S. Geological Survey, Earthquake Hazards Program (public domain).",
    "summary_feed": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php",
    "comcat_fdsn": "https://earthquake.usgs.gov/fdsnws/event/1/",
    "model_citation": (
        "Reasenberg, P.A. & Jones, L.M. (1989, 1994), Science / JGR; "
        "Utsu, T. (1961) Geophys. Mag. (Modified Omori law). Public-domain science."
    ),
    "parameter_note": (
        "Generic R&J prior parameters (a=-1.67, b=1.0, c=0.05d, p=1.08) — disclosed, "
        "not sequence-specific. CF-17/CF-18 numeric anchors."
    ),
}


# ---------------------------------------------------------------------------
# HTTP (stdlib only, short timeout, honest failure).
# ---------------------------------------------------------------------------
def _get_json(url: str, timeout: float = 12.0) -> tuple[Optional[dict], Optional[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "a11oy-seismic/1.0 (SZL Holdings; honest forecast)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, "HTTP %s from USGS" % e.code
    except Exception as e:  # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, e)


# ---------------------------------------------------------------------------
# Reasenberg-Jones / Omori-Utsu core math (clean-room, public science).
# ---------------------------------------------------------------------------
def _expected_count(mm: float, m_min: float, t1: float, t2: float,
                    a: float = RJ_A, b: float = RJ_B, c: float = RJ_C, p: float = RJ_P) -> float:
    """Expected number of aftershocks >= m_min in [t1, t2] days after a mainshock Mm."""
    k = 10.0 ** (a + b * (mm - m_min))
    if abs(1.0 - p) < 1e-9:
        # p == 1 limit: integral of (t+c)^-1 = ln((t2+c)/(t1+c))
        integral = math.log((t2 + c) / (t1 + c))
    else:
        integral = ((t2 + c) ** (1.0 - p) - (t1 + c) ** (1.0 - p)) / (1.0 - p)
    return max(0.0, k * integral)


def _poisson_prob_ge1(n_expected: float) -> float:
    """P(>=1 event) under Poisson(n_expected)."""
    return 1.0 - math.exp(-max(0.0, n_expected))


def _poisson_quantile(lam: float, q: float) -> int:
    """Smallest k with CDF_Poisson(k; lam) >= q. Honest count-uncertainty range."""
    if lam <= 0:
        return 0
    # iterative CDF (stable for the small lambdas typical here)
    cum = math.exp(-lam)
    term = cum
    k = 0
    while cum < q and k < 100000:
        k += 1
        term *= lam / k
        cum += term
    return k


def aftershock_forecast(mm: float, m_min: float, t1: float, t2: float) -> dict:
    """Honest R&J/Omori forecast for aftershocks >= m_min in [t1,t2] days after Mm."""
    n = _expected_count(mm, m_min, t1, t2)
    p1 = _poisson_prob_ge1(n)
    lo = _poisson_quantile(n, 0.025)
    hi = _poisson_quantile(n, 0.975)
    return {
        "mainshock_magnitude": round(mm, 2),
        "target_min_magnitude": round(m_min, 2),
        "window_days": [t1, t2],
        "expected_count": round(n, 3),
        "prob_at_least_one": round(p1, 4),
        "count_95pct_range": [lo, hi],
        "method": "Reasenberg-Jones (1994) + Modified Omori (Utsu 1961), Poisson counts",
        "parameters": {"a": RJ_A, "b": RJ_B, "c": RJ_C, "p": RJ_P, "kind": "generic prior (disclosed)"},
        "label": "statistical forecast — not certainty",
    }


# ---------------------------------------------------------------------------
# Live USGS catalog.
# ---------------------------------------------------------------------------
def fetch_quakes(level: str = "4.5", window: str = "day") -> dict:
    """Live USGS summary feed -> normalized quake list + the largest event."""
    if level not in _VALID_LEVELS:
        level = "4.5"
    if window not in _VALID_WINDOWS:
        window = "day"
    url = USGS_SUMMARY.format(level=level, window=window)
    data, err = _get_json(url)
    if err is not None:
        return {"ok": False, "error": err, "source": url,
                "honesty": "USGS feed unavailable — no fabricated quakes returned.",
                "attribution": _ATTRIBUTION}
    feats = data.get("features", []) or []
    quakes = []
    for f in feats:
        p = f.get("properties", {}) or {}
        g = (f.get("geometry") or {}).get("coordinates") or [None, None, None]
        quakes.append({
            "id": f.get("id"),
            "mag": p.get("mag"),
            "place": p.get("place"),
            "time": p.get("time"),
            "time_iso": (datetime.fromtimestamp(p["time"] / 1000.0, tz=timezone.utc).isoformat()
                         if isinstance(p.get("time"), (int, float)) else None),
            "depth_km": g[2] if len(g) > 2 else None,
            "lon": g[0], "lat": g[1],
            "tsunami": p.get("tsunami"),
            "alert": p.get("alert"),
            "url": p.get("url"),
        })
    quakes = [q for q in quakes if isinstance(q.get("mag"), (int, float))]
    quakes.sort(key=lambda q: (q.get("time") or 0), reverse=True)
    largest = max(quakes, key=lambda q: q["mag"]) if quakes else None
    return {
        "ok": True,
        "level": level, "window": window,
        "count": len(quakes),
        "quakes": quakes[:200],
        "largest": largest,
        "feed_title": (data.get("metadata") or {}).get("title"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": url,
        "attribution": _ATTRIBUTION,
        "honesty": "Live USGS data; aftershock numbers (if requested) are a statistical forecast, not certainty.",
    }


def forecast_for_largest(level: str = "4.5", window: str = "week",
                         m_min: Optional[float] = None) -> dict:
    """Pick the largest recent quake from the live USGS feed and emit an honest
    7-day and 30-day aftershock forecast for it. NO fabrication: if the feed is
    down or empty, return an honest error."""
    cat = fetch_quakes(level=level, window=window)
    if not cat.get("ok"):
        return {"ok": False, "error": cat.get("error"), "disclaimer": _DISCLAIMER,
                "attribution": _ATTRIBUTION}
    largest = cat.get("largest")
    if not largest:
        return {"ok": False, "error": "no qualifying events in the live feed window",
                "disclaimer": _DISCLAIMER, "attribution": _ATTRIBUTION}
    mm = float(largest["mag"])
    if m_min is None:
        m_min = max(3.0, round(mm - 2.0, 1))  # default target: 2 magnitudes below mainshock, floor M3
    # elapsed days since the mainshock (forecast windows are anchored from "now")
    now_ms = time.time() * 1000.0
    elapsed_days = max(0.0, (now_ms - (largest.get("time") or now_ms)) / 86400000.0)
    horizons = {
        "next_24h": (elapsed_days, elapsed_days + 1.0),
        "next_7d": (elapsed_days, elapsed_days + 7.0),
        "next_30d": (elapsed_days, elapsed_days + 30.0),
    }
    forecasts = {k: aftershock_forecast(mm, m_min, t1, t2) for k, (t1, t2) in horizons.items()}
    return {
        "ok": True,
        "mainshock": {
            "id": largest.get("id"), "mag": mm, "place": largest.get("place"),
            "time_iso": largest.get("time_iso"), "lat": largest.get("lat"),
            "lon": largest.get("lon"), "depth_km": largest.get("depth_km"),
            "url": largest.get("url"),
        },
        "target_min_magnitude": round(m_min, 1),
        "elapsed_days_since_mainshock": round(elapsed_days, 3),
        "forecasts": forecasts,
        "feed": {"level": level, "window": window, "count": cat.get("count"),
                 "title": cat.get("feed_title"), "source": cat.get("source")},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": _DISCLAIMER,
        "attribution": _ATTRIBUTION,
    }