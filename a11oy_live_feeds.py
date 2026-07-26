"""
a11oy_live_feeds.py — SHARED LIVE-DATA LAYER for the a11oy console.

Exposes  GET /api/a11oy/v1/live/<feed>  endpoints that SERVER-SIDE fetch + CACHE
real, free, no-auth public feeds, CORS-safe (the browser only ever hits OUR
same-origin proxy, keeping the Space sovereign — 0 runtime CDN from the client).

Every response carries an HONEST label:
    {"source": <human source>, "source_url": <upstream URL>,
     "mode": "live" | "cached" | "unavailable" | "self",   # never fabricated
     "fetched_at": <iso8601>, "ttl_s": <int>, ...payload}

  - "live"   = freshly fetched from upstream this request (or within TTL).
  - "cached" = upstream was unreachable; serving the last good in-memory value
               or the bundled on-disk snapshot (stage resilience).
  - "unavailable" = upstream was unreachable and no cached or bundled data exists.
  - "self"   = our own internal real data (not third-party) — used by callers
               that pass through this layer's helpers; the feed endpoints here
               are all third-party live/cached.

Feeds + TTLs:
  prometheus  (prometheus.demo.prometheus.io/api/v1/query)        TTL 30s
  kev         (cisa.gov known_exploited_vulnerabilities.json)     TTL 6h
  osv         (api.osv.dev/v1/query, POST)                        TTL 1h
  rekor       (rekor.sigstore.dev/api/v1/log)                     TTL 60s
  celestrak   (celestrak.org gp.php?GROUP=stations&FORMAT=json)   TTL 2h
  iss         (api.wheretheiss.at/v1/satellites/25544)            TTL 15s
  fhir        (hapi.fhir.org/baseR4 Observation/Immunization)     TTL 10m

No auth required for any of these feeds. NEVER fabricates: a down feed returns
real cached data labelled "cached", or "unavailable" when no cached data exists.
"""
import json
import os
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

import httpx
from starlette.routing import Route
from starlette.responses import JSONResponse

_SNAP_DIR = Path(os.environ.get("A11OY_LIVE_SNAPSHOTS", "/app/live_snapshots"))
_UA = "a11oy-live-proxy/1.0 (+https://szlholdings-a11oy.hf.space)"
_MAX_RESPONSE_BYTES = 32 * 1024 * 1024

# in-memory cache: feed -> {"data":..., "ts":..., "mode":...}
_CACHE = {}
_LOCK = threading.Lock()

_TTL = {
    "prometheus": 30, "kev": 6 * 3600, "osv": 3600, "rekor": 60,
    "celestrak": 2 * 3600, "iss": 15, "fhir": 600,
}

_SOURCE = {
    "prometheus": ("Prometheus demo (node/caddy/blackbox exporters)",
                   "https://prometheus.demo.prometheus.io/api/v1/query"),
    "kev": ("CISA Known Exploited Vulnerabilities catalog (GitHub mirror)",
            "https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"),
    "osv": ("OSV.dev open-source vulnerability database",
            "https://api.osv.dev/v1/query"),
    "rekor": ("Sigstore Rekor transparency log",
              "https://rekor.sigstore.dev/api/v1/log"),
    "celestrak": ("CelesTrak GP element sets (ISS + stations)",
                  "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=json"),
    "iss": ("Where-the-ISS-at live ISS position",
            "https://api.wheretheiss.at/v1/satellites/25544"),
    "fhir": ("HAPI FHIR R4 public test server (Observation / Immunization)",
             "https://hapi.fhir.org/baseR4"),
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _http_get(url, timeout=20, headers=None, data=None, method=None, deadline=None):
    """Fetch one bounded JSON response.

    Socket timeouts alone are insufficient because a peer can trickle bytes and
    reset the per-read timer forever.  ``iter_bytes`` exposes each received
    network chunk so the absolute monotonic deadline is checked throughout the
    body read.  The response context is closed before a deadline error escapes,
    which lets the calling worker finish instead of being abandoned.
    """
    h = {"User-Agent": _UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    request_timeout = _remaining_timeout(deadline, timeout)
    request_deadline = (
        deadline
        if deadline is not None
        else time.monotonic() + request_timeout
    )
    request_method = method or ("POST" if data is not None else "GET")
    chunks = []
    received = 0
    try:
        with httpx.stream(
            request_method,
            url,
            content=data,
            headers=h,
            timeout=httpx.Timeout(request_timeout),
            follow_redirects=True,
        ) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_bytes = int(content_length)
                except (TypeError, ValueError):
                    declared_bytes = None
                if declared_bytes is not None and declared_bytes > _MAX_RESPONSE_BYTES:
                    raise ValueError("live-feed response exceeds size limit")
            for chunk in response.iter_bytes():
                if time.monotonic() >= request_deadline:
                    raise TimeoutError("live-feed response deadline exhausted")
                if not chunk:
                    continue
                received += len(chunk)
                if received > _MAX_RESPONSE_BYTES:
                    raise ValueError("live-feed response exceeds size limit")
                chunks.append(chunk)
            if time.monotonic() >= request_deadline:
                raise TimeoutError("live-feed response deadline exhausted")
    except httpx.TimeoutException as exc:
        raise TimeoutError("live-feed response deadline exhausted") from exc
    return json.loads(b"".join(chunks))


def _load_snapshot(feed):
    p = _SNAP_DIR / ("%s.json" % feed)
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def get_cached_feed(feed, error):
    """Return only real cached evidence, without attempting an upstream read."""
    ttl = _TTL.get(feed, 60)
    src, url = _SOURCE.get(feed, ("unknown", ""))
    with _LOCK:
        ent = _CACHE.get(feed)
    if ent:
        return {"source": src, "source_url": url, "mode": "cached",
                "fetched_at": ent["iso"], "ttl_s": ttl,
                "cache_note": "upstream unreachable (%s) — serving last good value"
                              % type(error).__name__,
                "data": ent["data"]}
    snap = _load_snapshot(feed)
    if snap is not None:
        return {"source": src, "source_url": url, "mode": "cached",
                "fetched_at": "bundled-snapshot", "ttl_s": ttl,
                "cache_note": "upstream unreachable (%s) — serving bundled in-image snapshot"
                              % type(error).__name__,
                "data": snap}
    return {"source": src, "source_url": url, "mode": "unavailable",
            "fetched_at": None, "ttl_s": ttl,
            "error": "upstream unreachable and no snapshot (%s): %s"
                     % (type(error).__name__, error),
            "data": None}


def _remaining_timeout(deadline, default):
    """Return a cooperative per-request socket timeout within ``deadline``."""
    if deadline is None:
        return float(default)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("live-feed network budget exhausted")
    return min(float(default), remaining)


def _fetch(feed, deadline=None):
    """Return raw upstream JSON for a feed (raises on failure)."""
    if feed == "prometheus":
        import urllib.parse
        base = "https://prometheus.demo.prometheus.io/api/v1/query?query="
        out = {}
        for k, q in (("up", "up"),
                     ("cpu", 'rate(node_cpu_seconds_total{mode="user"}[5m])'),
                     ("mem", "node_memory_MemAvailable_bytes"),
                     ("http_req", "rate(prometheus_http_requests_total[5m])")):
            out[k] = _http_get(
                base + urllib.parse.quote(q),
                timeout=_remaining_timeout(deadline, 12),
                deadline=deadline,
            )
        return out
    if feed == "kev":
        return _http_get(
            _SOURCE["kev"][1], timeout=_remaining_timeout(deadline, 40),
            deadline=deadline)
    if feed == "osv":
        out = {}
        for pkg, eco in (("tensorflow", "PyPI"), ("torch", "PyPI"),
                         ("transformers", "PyPI"), ("numpy", "PyPI"), ("requests", "PyPI")):
            body = json.dumps({"package": {"name": pkg, "ecosystem": eco}}).encode()
            r = _http_get("https://api.osv.dev/v1/query",
                          timeout=_remaining_timeout(deadline, 20), data=body,
                          headers={"Content-Type": "application/json"}, method="POST",
                          deadline=deadline)
            vulns = r.get("vulns", [])
            out[pkg] = {"ecosystem": eco, "count": len(vulns),
                        "vulns": [{"id": v.get("id"), "summary": v.get("summary"),
                                   "modified": v.get("modified"),
                                   "aliases": (v.get("aliases") or [])[:4]} for v in vulns[:25]]}
        return out
    if feed == "rekor":
        return {"log": _http_get(
            _SOURCE["rekor"][1], timeout=_remaining_timeout(deadline, 15),
            deadline=deadline)}
    if feed == "celestrak":
        return _http_get(
            _SOURCE["celestrak"][1], timeout=_remaining_timeout(deadline, 20),
            deadline=deadline)
    if feed == "iss":
        return _http_get(
            _SOURCE["iss"][1], timeout=_remaining_timeout(deadline, 12),
            deadline=deadline)
    if feed == "fhir":
        out = {}
        for rt in ("Immunization", "Observation"):
            b = _http_get("https://hapi.fhir.org/baseR4/%s?_count=10" % rt,
                          timeout=_remaining_timeout(deadline, 25),
                          headers={"Accept": "application/fhir+json"},
                          deadline=deadline)
            entries = b.get("entry", [])
            out[rt] = {"total": b.get("total"), "count": len(entries),
                       "entries": [e.get("resource", {}) for e in entries[:10]]}
        return out
    raise ValueError("unknown feed: %s" % feed)


def get_feed(feed, timeout_s=None):
    """Cached, honestly-labelled accessor with an optional cooperative network budget."""
    ttl = _TTL.get(feed, 60)
    src, url = _SOURCE.get(feed, ("unknown", ""))
    with _LOCK:
        ent = _CACHE.get(feed)
    now = time.time()
    if ent and (now - ent["ts"]) < ttl:
        return {"source": src, "source_url": url, "mode": ent["mode"],
                "fetched_at": ent["iso"], "ttl_s": ttl, "data": ent["data"]}
    # need refresh
    try:
        deadline = (
            time.monotonic() + max(0.001, float(timeout_s))
            if timeout_s is not None else None
        )
        data = _fetch(feed, deadline=deadline)
        iso = _now_iso()
        with _LOCK:
            _CACHE[feed] = {"data": data, "ts": now, "mode": "live", "iso": iso}
        return {"source": src, "source_url": url, "mode": "live",
                "fetched_at": iso, "ttl_s": ttl, "data": data}
    except Exception as e:
        return get_cached_feed(feed, e)


def register(app, ns="a11oy"):
    base = "/api/%s/v1/live" % ns

    async def _feed_route(request):
        feed = request.path_params["feed"]
        if feed not in _TTL:
            return JSONResponse({"error": "unknown feed", "feed": feed,
                                 "available": sorted(_TTL.keys())}, status_code=404)
        import anyio
        payload = await anyio.to_thread.run_sync(get_feed, feed)
        return JSONResponse(payload)

    async def _index(request):
        feeds = []
        for f in sorted(_TTL.keys()):
            src, url = _SOURCE[f]
            with _LOCK:
                ent = _CACHE.get(f)
            feeds.append({"feed": f, "endpoint": "%s/%s" % (base, f),
                          "source": src, "source_url": url, "ttl_s": _TTL[f],
                          "last_mode": (ent or {}).get("mode"),
                          "last_fetched": (ent or {}).get("iso"),
                          "snapshot_present": (_SNAP_DIR / ("%s.json" % f)).exists()})
        return JSONResponse({
            "layer": "a11oy live-data proxy",
            "honest": "Every feed is server-side fetched + cached, CORS-safe via OUR same-origin "
                      "proxy (0 client CDN). Mode is honestly labelled live/cached/unavailable; "
                      "a down feed serves real cached data when present and reports unavailable "
                      "when absent, never fabricated.",
            "count": len(feeds), "feeds": feeds,
        })

    routes = [
        Route(base, _index, methods=["GET"], name="%s_live_index" % ns),
        Route(base + "/{feed}", _feed_route, methods=["GET"], name="%s_live_feed" % ns),
    ]
    for r in reversed(routes):
        app.router.routes.insert(0, r)
    return {"status": "ok", "base": base, "feeds": sorted(_TTL.keys())}
