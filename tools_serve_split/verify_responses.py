#!/usr/bin/env python3
"""Hit every MOVED endpoint via in-process TestClient and dump normalized responses.
Run against the pre-refactor tree and the post-refactor tree; diff the JSON to prove
byte-identical behavior (modulo volatile timestamp fields, which we drop)."""
import sys, os, json
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
    "/api/lambda-bounty/healthz",
    "/api/lambda-bounty/receipts",
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
            out[("GET", ep)] = (r.status_code, body)
        # POST submit — accepted path (deterministic minus ts/hash which depend on ts)
        good = {"submitter": {"name": "tester"},
                "pr_url": "https://github.com/szl-holdings/lambda-bounty/pull/1",
                "lean_toolchain": "leanprover/lean4:v4.13.0",
                "axiom_print": "propext, Classical.choice",
                "sorry_free_claim": True}
        r = c.post("/api/lambda-bounty/submit", json=good)
        b = r.json()
        # drop volatile receipt fields (ts/hash/hmac depend on time & prev)
        rec = b.get("receipt", {})
        for k in ("ts", "hash", "hmac_sha256", "prev"):
            rec.pop(k, None)
        out[("POST", "/api/lambda-bounty/submit[good]")] = (r.status_code, scrub(b))
        # POST submit — rejected path (bad payload)
        r = c.post("/api/lambda-bounty/submit", json={"foo": "bar"})
        b = r.json()
        rec = b.get("receipt", {})
        for k in ("ts", "hash", "hmac_sha256", "prev"):
            rec.pop(k, None)
        out[("POST", "/api/lambda-bounty/submit[bad]")] = (r.status_code, scrub(b))
    ser = {f"{m} {p}": v for (m, p), v in out.items()}
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/resp.json"
    with open(path, "w") as f:
        json.dump(ser, f, indent=2, sort_keys=True, ensure_ascii=False)
    codes = {k: v[0] for k, v in ser.items()}
    print("STATUS CODES:", json.dumps(codes))
    print("wrote", path)

if __name__ == "__main__":
    main()
