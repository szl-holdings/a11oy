#!/usr/bin/env python3
# Publish check for /command/constellation on a-11-oy.com (NOT a11oy.net).
from __future__ import annotations

import json
import urllib.request

ORIGIN = "https://a-11-oy.com"
LOCKED = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
PATHS = [
    "/command/constellation",
    "/api/a11oy/v1/honest",
    "/api/a11oy/v1/formulas/selftest",
    "/api/a11oy/v1/lambda",
    "/api/a11oy/v1/energy/live",
    "/api/a11oy/v1/brain/capabilities",
]


def get(path: str):
    req = urllib.request.Request(ORIGIN + path, headers={"Accept": "application/json,text/html"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read(8000).decode("utf-8", "replace")
            return r.status, body
    except Exception as exc:
        return 0, str(exc)


def main() -> int:
    report = {"origin": ORIGIN, "proof_host_forbidden": "https://a11oy.net", "locked": LOCKED}
    for path in PATHS:
        status, body = get(path)
        report[path] = {"status": status, "ok": status == 200, "snippet": body[:180]}
    print(json.dumps(report, indent=2))
    print("Rebuild a11oy if /command/constellation is not 200. Do not publish runtime to a11oy.net.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
