#!/usr/bin/env python3
"""Same as verify_responses.py but PINS wall-clock time so the time-seeded synthetic
metrics (_a11oy_router_stats_payload throughput / servedThisWindow — line ~5113:
`tick = int(time.time())`) are deterministic. This isolates refactor behavior from
the endpoints' own inherent per-poll non-determinism, giving a byte-identical
before/after proof for the MOVED route group."""
import sys, os, json, time as _time

# Freeze time BEFORE importing serve so all time-seeded state is deterministic.
_FIXED = 1_700_000_000
_orig_time = _time.time
_time.time = lambda: float(_FIXED)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import serve
from fastapi.testclient import TestClient

VOLATILE = {"ts", "uptime_s", "checked_at", "generated_at", "now", "timestamp"}

def scrub(o):
    if isinstance(o, dict):
        return {k: scrub(v) for k, v in o.items() if k not in VOLATILE}
    if isinstance(o, list):
        return [scrub(x) for x in o]
    return o

GET_ENDPOINTS = [
    "/api/lambda-bounty/healthz", "/api/lambda-bounty/receipts",
    "/api/a11oy/v1/router/metrics", "/v1/router/metrics",
    "/api/a11oy/v1/chaski/routing-graph", "/v1/chaski/routing-graph", "/api/chaski/routing-graph",
    "/api/a11oy/v1/reason/loop-depth", "/v1/reason/loop-depth",
    "/api/a11oy/v1/consensus/votes", "/v1/consensus/votes",
    "/api/a11oy/v1/forecast-baseline", "/v1/forecast-baseline",
    "/api/a11oy/v1/vertical-packs", "/v1/vertical-packs",
    "/api/a11oy/v1/observability/business", "/v1/observability/business",
]

def main():
    out = {}
    with TestClient(serve.app) as c:
        for ep in GET_ENDPOINTS:
            r = c.get(ep)
            try:
                body = scrub(r.json())
            except Exception:
                body = r.text
            out[f"GET {ep}"] = (r.status_code, body)
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/resp_frozen.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True, ensure_ascii=False)
    print("wrote", path, "codes:", {k: v[0] for k, v in out.items()})

if __name__ == "__main__":
    main()
