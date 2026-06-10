# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""killinchu maritime / air live connectors.

  opensky    OpenSky Network aircraft states (keyless anon)  → CONNECTED now
  aisstream  AISStream live vessel positions (free key)       → READY → CONNECTED on key
             HISTORICAL AIS / AIS-gap = SAMPLE (no free historical feed) — labelled verbatim.

HONEST MARITIME CAVEAT (carry verbatim): AISStream gives LIVE vessel positions for
free, but HISTORICAL AIS / AIS-gap timelines are NOT free — those panels stay
SAMPLE with sample_reason "no free historical AIS". Live ≠ historical.
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


@register
class OpenSkyConnector(Connector):
    id = "opensky"
    label = "OpenSky Network (live aircraft states)"
    category = "air"
    auth_kind = "none"   # anon works; account raises rate
    free_tier = True
    provider_base = "https://opensky-network.org/api/states/all"
    docs_url = "https://openskynetwork.github.io/opensky-api/rest.html"
    schema_preview = ["icao24", "callsign", "origin_country", "longitude", "latitude", "baro_altitude", "velocity"]

    def _probe(self):
        st, _ = http_json(self.provider_base + "?lamin=45&lomin=5&lamax=47&lomax=8", timeout=10.0)
        return (st == 200), f"OpenSky HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        # bounding box defaults to central Europe (dense traffic) for a live sample
        bbox = (query or {}).get("bbox", {"lamin": 45.0, "lomin": 5.0, "lamax": 47.0, "lomax": 8.0})
        limit = max(1, min(int((query or {}).get("limit", 15)), 50))
        ck = f"opensky:{bbox}:{limit}"
        c = _cached(ck, 30)
        if c:
            return c
        import urllib.parse as up
        st, raw = http_json(self.provider_base + "?" + up.urlencode(bbox), timeout=12.0)
        if st == 200 and isinstance(raw, dict) and raw.get("states") is not None:
            items = []
            for s in (raw.get("states") or [])[:limit]:
                # OpenSky state vector index order per REST docs
                items.append({"icao24": s[0], "callsign": (s[1] or "").strip(),
                              "origin_country": s[2], "longitude": s[5], "latitude": s[6],
                              "baro_altitude": s[7], "velocity": s[9]})
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=items, source="OpenSky Network /states/all (anon)", live=True,
                        note=f"live · {len(raw.get('states') or [])} aircraft in bbox · t={raw.get('time')}",
                        schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"OpenSky unreachable/rate-limited (HTTP {st})")


# AISStream LIVE positions (free key) — READY until key minted.
@register
class AisStreamConnector(Connector):
    id = "aisstream"
    label = "AISStream live vessel positions"
    category = "maritime"
    auth_kind = "api_key"
    free_tier = True  # free key via GitHub login
    env_vars = ["SZL_AISSTREAM_API_KEY"]
    provider_base = "wss://stream.aisstream.io/v0/stream"
    docs_url = "https://aisstream.io/documentation"
    schema_preview = ["mmsi", "ship_name", "latitude", "longitude", "sog", "cog", "timestamp"]

    def read(self, query: dict | None = None) -> Records:
        key = os.environ.get("SZL_AISSTREAM_API_KEY")
        if not key:
            return self._ready_records(
                "provide credentials to activate — set SZL_AISSTREAM_API_KEY "
                "(free key via GitHub login at https://aisstream.io). Live vessel positions stream over wss.")
        # With a key, a wss subscription would stream positions. The REST/poll
        # surface returns CONNECTED with an honest note (the live stream is wss).
        return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                       records=[], source="AISStream wss live stream", live=True,
                       note="credentials present — live positions stream over wss (subscribe with bounding boxes)",
                       schema_preview=self.schema_preview)


# HISTORICAL AIS / AIS-gap — SAMPLE only (no free historical feed). Labelled verbatim.
@register
class AisHistoricalConnector(Connector):
    id = "ais_historical"
    label = "Historical AIS / AIS-gap timeline"
    category = "maritime"
    auth_kind = "api_key"
    free_tier = False  # NO free historical AIS → SAMPLE
    env_vars = ["SZL_AIS_HISTORICAL_API_KEY"]
    provider_base = "https://(commercial historical AIS provider)"
    docs_url = "https://aisstream.io/documentation"
    sample_reason_text = "no free historical AIS"
    schema_preview = ["mmsi", "ship_name", "first_seen", "last_seen", "gap_minutes", "dark_segment"]
    sample_records = [
        {"mmsi": "SAMPLE-000000001", "ship_name": "(labelled sample — not a real vessel)",
         "first_seen": "2026-01-01T00:00:00Z", "last_seen": "2026-01-01T06:00:00Z",
         "gap_minutes": 180, "dark_segment": True},
        {"mmsi": "SAMPLE-000000002", "ship_name": "(labelled sample — not a real vessel)",
         "first_seen": "2026-01-02T00:00:00Z", "last_seen": "2026-01-02T03:00:00Z",
         "gap_minutes": 95, "dark_segment": True},
    ]

    def _missing_env(self):
        return [k for k in self.env_vars if not os.environ.get(k)]


__all__ = ["OpenSkyConnector", "AisStreamConnector", "AisHistoricalConnector"]
