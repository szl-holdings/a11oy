# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""killinchu / shared geo live connectors (keyless → CONNECTED now).

  usgs      USGS earthquake feeds (GeoJSON)         keyless
  noaa      NOAA api.weather.gov forecast/alerts    keyless (UA header)
  overpass  OpenStreetMap Overpass API               keyless
"""
from __future__ import annotations

import time
from typing import Any

from ..base import Connector, Records, State, http_json, http_text, _now
from ..registry import register

_CACHE: dict[str, tuple[float, Any]] = {}


def _cached(k, ttl):
    h = _CACHE.get(k)
    return h[1] if h and (time.time() - h[0]) < ttl else None


def _put(k, v):
    _CACHE[k] = (time.time(), v)


@register
class UsgsConnector(Connector):
    id = "usgs"
    label = "USGS earthquakes"
    category = "geo"
    auth_kind = "none"
    free_tier = True
    provider_base = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    docs_url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php"
    schema_preview = ["mag", "place", "time", "longitude", "latitude", "depth"]

    def _probe(self):
        st, _ = http_json(self.provider_base)
        return (st == 200), f"USGS HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        window = (query or {}).get("window", "all_day")  # all_day|2.5_week|4.5_month
        limit = max(1, min(int((query or {}).get("limit", 15)), 50))
        url = f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{window}.geojson"
        ck = f"usgs:{window}:{limit}"
        c = _cached(ck, 120)
        if c:
            return c
        st, raw = http_json(url)
        if st == 200 and isinstance(raw, dict):
            items = []
            for f in (raw.get("features", []) or [])[:limit]:
                p = f.get("properties", {}); g = f.get("geometry", {}).get("coordinates", [None, None, None])
                items.append({"mag": p.get("mag"), "place": p.get("place"), "time": p.get("time"),
                              "longitude": g[0], "latitude": g[1], "depth": g[2]})
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=items, source=f"USGS {window} GeoJSON", live=True,
                        note=f"live · {len(raw.get('features', []))} events", schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"USGS unreachable (HTTP {st})")


@register
class NoaaConnector(Connector):
    id = "noaa"
    label = "NOAA weather (api.weather.gov)"
    category = "geo"
    auth_kind = "none"
    free_tier = True
    provider_base = "https://api.weather.gov"
    docs_url = "https://www.weather.gov/documentation/services-web-api"
    schema_preview = ["event", "severity", "area", "effective", "headline"]

    def _probe(self):
        st, _ = http_json(self.provider_base + "/alerts/active?limit=1")
        return (st == 200), f"NOAA HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        limit = max(1, min(int((query or {}).get("limit", 12)), 50))
        area = (query or {}).get("area", "")
        url = f"{self.provider_base}/alerts/active?limit={limit}" + (f"&area={area}" if area else "")
        ck = f"noaa:{area}:{limit}"
        c = _cached(ck, 180)
        if c:
            return c
        st, raw = http_json(url)
        if st == 200 and isinstance(raw, dict):
            items = []
            for f in (raw.get("features", []) or [])[:limit]:
                p = f.get("properties", {})
                items.append({"event": p.get("event"), "severity": p.get("severity"),
                              "area": p.get("areaDesc"), "effective": p.get("effective"),
                              "headline": (p.get("headline") or "")[:120]})
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=items, source="NOAA /alerts/active", live=True,
                        note=f"live · {len(raw.get('features', []))} active alerts", schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"NOAA unreachable (HTTP {st})")


@register
class OverpassConnector(Connector):
    id = "overpass"
    label = "OpenStreetMap Overpass"
    category = "geo"
    auth_kind = "none"
    free_tier = True
    provider_base = "https://overpass-api.de/api/interpreter"
    docs_url = "https://wiki.openstreetmap.org/wiki/Overpass_API"
    schema_preview = ["type", "id", "name", "lat", "lon"]

    def _probe(self):
        q = "[out:json][timeout:8];node(1);out;"
        import urllib.parse as up
        st, _ = http_json(self.provider_base + "?data=" + up.quote(q), timeout=10.0)
        return (st == 200), f"Overpass HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        # default: harbours/ports near a bbox (maritime/coastline use)
        oql = (query or {}).get("oql") or (
            "[out:json][timeout:15];node[\"harbour\"=\"yes\"](36.0,-6.0,44.0,3.0);out 15;")
        limit = max(1, min(int((query or {}).get("limit", 15)), 40))
        import urllib.parse as up
        ck = f"overpass:{hash(oql)}:{limit}"
        c = _cached(ck, 600)
        if c:
            return c
        st, raw = http_json(self.provider_base + "?data=" + up.quote(oql), timeout=20.0)
        if st == 200 and isinstance(raw, dict):
            items = []
            for el in (raw.get("elements", []) or [])[:limit]:
                items.append({"type": el.get("type"), "id": el.get("id"),
                              "name": (el.get("tags", {}) or {}).get("name"),
                              "lat": el.get("lat"), "lon": el.get("lon")})
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=items, source="OpenStreetMap Overpass", live=True,
                        note=f"live · {len(raw.get('elements', []))} elements", schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"Overpass unreachable (HTTP {st})")


__all__ = ["UsgsConnector", "NoaaConnector", "OverpassConnector"]
