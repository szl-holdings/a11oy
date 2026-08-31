#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""source_health.py — probe every external data endpoint in ops/sources.yaml.

Stdlib-only (urllib). For each source: issue the declared method, check HTTP status,
and validate the response shape (json / json_array / expected top-level keys). Emits a
JSON report to stdout and exits non-zero if any source is unhealthy — so a nightly cron
(or CI) can alert BEFORE production traffic hits a dead/renumbered endpoint.

Census key is injected from env (${CENSUS_API_KEY}); a source that needs a key but has
none is reported as SKIPPED (not FAIL), to stay honest about what was actually tested.

Usage: python3 ops/source_health.py [--sources ops/sources.yaml]
"""
from __future__ import annotations
import json, os, re, sys, urllib.request, urllib.error
from datetime import datetime, timezone

UA = {"User-Agent": "SZL Holdings David-Leads source-health research@szlholdings.com"}
TIMEOUT = 20


def _load_sources(path: str) -> list[dict]:
    """Minimal YAML reader for our flat sources list (no PyYAML dependency)."""
    srcs, cur = [], None
    with open(path) as f:
        for line in f:
            if line.strip().startswith("#") or not line.strip():
                continue
            m = re.match(r"\s*-\s+id:\s*(.+)", line)
            if m:
                if cur:
                    srcs.append(cur)
                cur = {"id": m.group(1).strip()}
                continue
            m = re.match(r"\s+(\w+):\s*(.*)", line)
            if m and cur is not None:
                k, v = m.group(1), m.group(2).strip()
                if v.startswith("[") and v.endswith("]"):
                    v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
                else:
                    v = v.strip('"').strip("'")
                cur[k] = v
    if cur:
        srcs.append(cur)
    return srcs


def _expand(url: str) -> str:
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), url)


def _probe(s: dict, _retries: int = 1) -> dict:
    """Probe one source. Retries once on a transient/flaky result (404/429/503/conn error)
    so intermittent endpoints don't false-alarm the nightly run."""
    r = _probe_once(s)
    if r["status"] in ("FAIL", "TRANSIENT") and _retries > 0 and r.get("http") in (404, 429, 503, None):
        import time as _t; _t.sleep(1.5)
        r2 = _probe_once(s)
        if r2["status"] == "OK":
            r2["note"] = (r2.get("note", "") + " (recovered on retry; endpoint is flaky)").strip()
            return r2
    return r


def _probe_once(s: dict) -> dict:
    url = _expand(s["url"])
    method = s.get("method", "GET")
    expect = s.get("expect", "any")
    # honest skip if a required key is absent
    if "${CENSUS_API_KEY}" in s["url"] and not os.environ.get("CENSUS_API_KEY"):
        return {"id": s["id"], "status": "SKIPPED", "reason": "CENSUS_API_KEY absent"}
    data = s.get("body")
    body = data.encode() if data else None
    headers = dict(UA)
    if body:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            code = r.getcode()
            final = r.geturl()
            # Read a bounded prefix: enough to confirm the body parses/starts as JSON
            # without pulling multi-MB time-series. For large bodies we validate the
            # first byte ('{' or '[') instead of full json.loads.
            raw = r.read(2_000_000) if method != "HEAD" else b""
            truncated = len(raw) >= 2_000_000
        if "missing_key" in final:
            return {"id": s["id"], "status": "FAIL", "http": code, "reason": "redirected to missing_key.html"}
        if code != 200:
            return {"id": s["id"], "status": "FAIL", "http": code, "reason": f"HTTP {code}"}
        if expect in ("json", "json_array") and method != "HEAD":
            body = raw.decode(errors="replace").lstrip()
            if truncated:
                # Body too large to fully parse; validate it *starts* as the right JSON type.
                first = body[:1]
                want = "[" if expect == "json_array" else "{"
                if first != want and not (expect == "json" and first in "[{"):
                    return {"id": s["id"], "status": "FAIL", "http": code, "reason": f"body does not start as {expect}"}
                return {"id": s["id"], "status": "OK", "http": code, "note": "large body; prefix-validated"}
            try:
                parsed = json.loads(body)
            except Exception as e:
                return {"id": s["id"], "status": "FAIL", "http": code, "reason": f"non-JSON body ({e})"}
            if expect == "json_array" and not isinstance(parsed, list):
                return {"id": s["id"], "status": "FAIL", "http": code, "reason": "expected JSON array"}
            for k in (s.get("expect_keys") or []):
                if isinstance(parsed, dict) and k not in parsed:
                    return {"id": s["id"], "status": "FAIL", "http": code, "reason": f"missing key '{k}' (schema drift)"}
        return {"id": s["id"], "status": "OK", "http": code}
    except urllib.error.HTTPError as e:
        # 429/503 are throttle/transient — don't hard-fail the whole run on a rate limit.
        if e.code in (429, 503):
            return {"id": s["id"], "status": "TRANSIENT", "http": e.code, "reason": f"HTTP {e.code} (throttled/transient)"}
        return {"id": s["id"], "status": "FAIL", "http": e.code, "reason": f"HTTPError {e.code}"}
    except Exception as e:
        return {"id": s["id"], "status": "FAIL", "reason": f"{type(e).__name__}: {e}"}


def main() -> int:
    path = "ops/sources.yaml"
    if "--sources" in sys.argv:
        path = sys.argv[sys.argv.index("--sources") + 1]
    sources = _load_sources(path)
    results = [_probe(s) for s in sources]
    fails = [r for r in results if r["status"] == "FAIL"]
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "OK"),
        "skipped": sum(1 for r in results if r["status"] == "SKIPPED"),
        "transient": sum(1 for r in results if r["status"] == "TRANSIENT"),
        "failed": len(fails),
        "results": results,
    }
    print(json.dumps(report, indent=2))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
