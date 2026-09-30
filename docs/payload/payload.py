#!/usr/bin/env python3
"""PAYLOAD-1 probe. Read-only. Never stamps LIVE."""
from __future__ import annotations

import json
import urllib.request

ORIGIN = "https://a-11-oy.com"
UA = "a11oy-payload-1/1.0"
TIMEOUT = 15
ROUTES = ("/", "/holographic", "/frontier-now", "/console")


def get(path: str, json_body: bool = False):
    req = urllib.request.Request(ORIGIN + path, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            if json_body:
                return r.status, json.loads(raw.decode("utf-8", "replace"))
            return r.status, raw
    except Exception as e:
        return None, str(e)


def main() -> None:
    print("PAYLOAD-1 probe", ORIGIN)
    for path in ROUTES:
        status, _ = get(path)
        print(f"  {path:16} {status}")

    st, ident = get("/api/a11oy/v1/frontier-now/summary", json_body=True)
    print("  /frontier-now/summary", st)
    if isinstance(ident, dict):
        i = ident.get("identity") or {}
        cg = ident.get("claim_gate") or {}
        ob = ident.get("observation") or {}
        rt = i.get("runtime_reported_source_revision") or ""
        gh = i.get("github_default_branch_revision") or ""
        print("  runtime", rt[:12])
        print("  github ", gh[:12])
        print("  eq     ", i.get("equivalence_state"))
        print("  reason ", i.get("reason"))
        print("  claim  ", cg.get("state"), cg.get("reason"))
        print("  obs    ", ob.get("state"), ob.get("critical_failures"))
        print("  MATCH requires HF overlay + digest — equal SHA is not operational")
    else:
        print("  summary UNAVAILABLE", ident)

    st, honest = get("/api/a11oy/v1/honest", json_body=True)
    if isinstance(honest, dict):
        print(
            "  honest ",
            (honest.get("git_sha") or "")[:12],
            "locked",
            honest.get("locked_formula_count"),
        )
    else:
        print("  honest UNAVAILABLE", st, honest)


if __name__ == "__main__":
    main()
