"""szl_metrics_prom.py — real Prometheus /metrics exporter (shared, byte-identical
a11oy <-> killinchu).

WHY: the UDS Package `spec.monitor` for both flagships scrapes `GET :7860/metrics`,
but with no metrics route that path fell through to the SPA `/{full_path:path}`
catch-all and returned the app's HTML shell (HTTP 200, content-type text/html).
A Prometheus scrape therefore connected (up=1) yet harvested ZERO usable samples,
so the dashboards stayed empty.

This module fixes that by serving genuine Prometheus exposition format at `/metrics`.
All metrics are REAL and self-measured at runtime — no fabricated values:
  * szl_build_info{flagship,python}                 — info gauge (=1)
  * szl_process_start_time_seconds                  — process start (unix epoch)
  * szl_process_uptime_seconds                      — now - start
  * szl_process_resident_memory_bytes               — RSS from /proc/self/statm
  * szl_process_open_fds                            — len(/proc/self/fd)
  * szl_http_requests_in_progress                   — in-flight requests gauge
  * szl_http_requests_total{method,code}            — request counter
  * szl_http_request_duration_seconds (histogram)   — request latency
  * szl_routes_registered                           — number of registered routes

Design constraints honored:
  * Pure stdlib (threading/time/os/sys) + starlette.responses.Response only.
  * Request accounting uses a pass-through ASGI middleware (NOT BaseHTTPMiddleware)
    so Server-Sent-Events / streaming responses are never buffered or broken.
  * register() front-inserts the /metrics route so it wins over the SPA catch-all,
    and is safe to call LAST (after any frontier_patch routes.clear()+extend).
  * try/except guarded end-to-end — can never take the Space down.
"""

from __future__ import annotations

import os
import sys
import time
import threading

_START_EPOCH = time.time()
_LOCK = threading.Lock()

# request counters keyed by (method, status_code_str)
_req_total: "dict[tuple[str, str], int]" = {}
_in_progress = 0

# global latency histogram (unlabeled to keep cardinality bounded)
_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
_bucket_counts = [0] * len(_BUCKETS)  # cumulative: count of obs with dur <= BUCKETS[i]
_lat_sum = 0.0
_lat_count = 0

_flagship = "unknown"


def _observe(method: str, status, dur: float) -> None:
    """Record one completed HTTP request. Thread-safe."""
    global _lat_sum, _lat_count
    code = str(status if status else 0)
    with _LOCK:
        key = (method or "UNKNOWN", code)
        _req_total[key] = _req_total.get(key, 0) + 1
        _lat_sum += dur
        _lat_count += 1
        for i, b in enumerate(_BUCKETS):
            if dur <= b:
                _bucket_counts[i] += 1


def _esc(v: str) -> str:
    """Escape a Prometheus label VALUE (backslash, double-quote, newline)."""
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _proc_metrics() -> "dict[str, int]":
    out: "dict[str, int]" = {}
    try:
        with open("/proc/self/statm") as f:
            pages = int(f.read().split()[1])  # resident pages
        out["rss"] = pages * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        pass
    try:
        out["open_fds"] = len(os.listdir("/proc/self/fd"))
    except Exception:
        pass
    return out


def render(app=None) -> str:
    """Build the Prometheus exposition text from the live counters."""
    now = time.time()
    pyver = "%d.%d.%d" % sys.version_info[:3]
    lines: "list[str]" = []

    lines.append("# HELP szl_build_info Flagship build/runtime info (constant 1).")
    lines.append("# TYPE szl_build_info gauge")
    lines.append(
        'szl_build_info{flagship="%s",python="%s"} 1'
        % (_esc(_flagship), _esc(pyver))
    )

    lines.append("# HELP szl_process_start_time_seconds Process start time (unix epoch seconds).")
    lines.append("# TYPE szl_process_start_time_seconds gauge")
    lines.append("szl_process_start_time_seconds %r" % _START_EPOCH)

    lines.append("# HELP szl_process_uptime_seconds Seconds since process start.")
    lines.append("# TYPE szl_process_uptime_seconds gauge")
    lines.append("szl_process_uptime_seconds %r" % (now - _START_EPOCH))

    proc = _proc_metrics()
    if "rss" in proc:
        lines.append("# HELP szl_process_resident_memory_bytes Resident memory (RSS) in bytes.")
        lines.append("# TYPE szl_process_resident_memory_bytes gauge")
        lines.append("szl_process_resident_memory_bytes %d" % proc["rss"])
    if "open_fds" in proc:
        lines.append("# HELP szl_process_open_fds Number of open file descriptors.")
        lines.append("# TYPE szl_process_open_fds gauge")
        lines.append("szl_process_open_fds %d" % proc["open_fds"])

    with _LOCK:
        in_prog = _in_progress
        req_snapshot = dict(_req_total)
        buckets = list(_bucket_counts)
        lat_sum = _lat_sum
        lat_count = _lat_count

    lines.append("# HELP szl_http_requests_in_progress In-flight HTTP requests.")
    lines.append("# TYPE szl_http_requests_in_progress gauge")
    lines.append("szl_http_requests_in_progress %d" % in_prog)

    lines.append("# HELP szl_http_requests_total Total HTTP requests handled.")
    lines.append("# TYPE szl_http_requests_total counter")
    if req_snapshot:
        for (method, code), n in sorted(req_snapshot.items()):
            lines.append(
                'szl_http_requests_total{method="%s",code="%s"} %d'
                % (_esc(method), _esc(code), n)
            )
    else:
        # Emit a zero series so the metric always exists for the scraper.
        lines.append('szl_http_requests_total{method="GET",code="200"} 0')

    lines.append("# HELP szl_http_request_duration_seconds HTTP request latency.")
    lines.append("# TYPE szl_http_request_duration_seconds histogram")
    for i, b in enumerate(_BUCKETS):
        lines.append(
            'szl_http_request_duration_seconds_bucket{le="%s"} %d' % (b, buckets[i])
        )
    lines.append(
        'szl_http_request_duration_seconds_bucket{le="+Inf"} %d' % lat_count
    )
    lines.append("szl_http_request_duration_seconds_sum %r" % lat_sum)
    lines.append("szl_http_request_duration_seconds_count %d" % lat_count)

    try:
        n_routes = len(app.router.routes) if app is not None else 0
    except Exception:
        n_routes = 0
    lines.append("# HELP szl_routes_registered Number of registered application routes.")
    lines.append("# TYPE szl_routes_registered gauge")
    lines.append("szl_routes_registered %d" % n_routes)

    return "\n".join(lines) + "\n"


class _PromASGIMiddleware:
    """Pass-through ASGI middleware that counts requests + latency WITHOUT buffering
    the response body, so SSE / streaming responses keep working."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        global _in_progress
        method = scope.get("method", "")
        status = {"code": 0}

        async def _send(message):
            if message.get("type") == "http.response.start":
                status["code"] = message.get("status", 0)
            await send(message)

        with _LOCK:
            _in_progress += 1
        t0 = time.perf_counter()
        try:
            await self.app(scope, receive, _send)
        finally:
            dur = time.perf_counter() - t0
            with _LOCK:
                _in_progress -= 1
            _observe(method, status["code"] or 500, dur)


def register(app, ns: str = "a11oy") -> str:
    """Install the request-accounting middleware and the /metrics route.

    Call this LAST in serve.py (after any frontier_patch routes.clear()+extend):
    the route is front-inserted so it always beats the SPA /{full_path:path}
    catch-all. Idempotent-ish: a second call adds a second (harmless) route, so
    register exactly once per app.
    """
    global _flagship
    _flagship = ns

    try:
        from starlette.responses import Response
    except Exception as e:  # pragma: no cover
        return "unavailable: %r" % (e,)

    mw_ok = False
    try:
        app.add_middleware(_PromASGIMiddleware)
        mw_ok = True
    except Exception as e:
        print("[%s] prom metrics middleware NOT added (non-fatal): %r" % (ns, e),
              file=sys.stderr)

    n_before = len(app.router.routes)

    @app.get("/metrics")
    async def _szl_prom_metrics():  # noqa
        body = render(app)
        return Response(
            content=body,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    new = app.router.routes[n_before:]
    del app.router.routes[n_before:]
    app.router.routes[0:0] = new

    print(
        "[%s] szl_metrics_prom: GET /metrics registered (Prometheus exposition; "
        "request-accounting middleware=%s) [moved %d route(s) to front]"
        % (ns, "on" if mw_ok else "off", len(new)),
        file=sys.stderr,
    )
    return "ok: /metrics middleware=%s" % ("on" if mw_ok else "off")


if __name__ == "__main__":
    # Self-test: render with a couple of synthetic observations.
    _flagship = "selftest"
    _observe("GET", 200, 0.003)
    _observe("GET", 200, 0.07)
    _observe("POST", 500, 1.2)
    text = render(None)
    print(text)
    assert "szl_build_info{" in text
    assert "szl_http_requests_total{method=\"GET\",code=\"200\"} 2" in text
    assert "szl_http_request_duration_seconds_bucket{le=\"+Inf\"} 3" in text
    assert "szl_http_request_duration_seconds_count 3" in text
    assert text.endswith("\n")
    # bucket monotonicity
    import re as _re
    cum = [int(m) for m in _re.findall(r'_bucket\{le="[^+][^"]*"\} (\d+)', text)]
    assert cum == sorted(cum), cum
    print("SELFTEST OK", file=sys.stderr)
