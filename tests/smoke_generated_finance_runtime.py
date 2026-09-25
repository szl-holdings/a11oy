# SPDX-License-Identifier: Apache-2.0
"""Execute INSIDE the generated image: stdlib-only, localhost reads, no credentials.

The CI container runs with no external network. This verifies the emitted
runtime and public failure boundaries, not live provider access or deployment.
"""
from importlib import metadata
import json
import os
from pathlib import Path
import re
import sys
from urllib import error, request


def main():
    if sys.version_info[:3] != (3, 12, 13):
        raise RuntimeError("generated image Python does not match qualified baseline")
    if os.getuid() != 1000:
        raise RuntimeError("generated application is not running as the declared nonroot user")
    locked = {}
    for line in Path("/app/requirements.txt").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)", line)
        if not match:
            raise RuntimeError("invalid emitted version-lock row")
        name, version = match.groups()
        if metadata.version(name) != version:
            raise RuntimeError("installed distribution differs from emitted version lock: " + name)
        locked[name] = version
    if not locked:
        raise RuntimeError("empty emitted version lock")
    routes = {}
    expected = {"/": 200, "/panels": 200, "/research": 200, "/api/live": 503, "/healthz": 200, "/readyz": 200,
                "/api/finance/observations/alpaca-quotes": 403,
                "/api/finance/observations/fred-series": 403,
                "/api/finance/overview": 503,
                "/api/finance/v2/signals/AAPL?origin=fixture": 503,
                "/api/finance/v2/quote/BTC-USD": 503,
                "/api/finance/v2/receipts": 503,
                "/api/finance/v2/receipts/verify": 503,
                "/orders": 404, "/wallet": 404}
    for path, code in expected.items():
        try:
            response = request.urlopen("http://127.0.0.1:7860" + path, timeout=20)
        except error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read(2_000_001)
            if response.code != code or len(raw) > 2_000_000:
                raise RuntimeError("unexpected generated runtime response: " + path)
            if path == "/readyz" and json.loads(raw).get("ready") is not True:
                raise RuntimeError("generated file-integrity readiness failed")
            if path == "/api/finance/overview":
                body = json.loads(raw)
                if body.get("ok") is not False or body.get("execution_enabled") is not False:
                    raise RuntimeError("missing provider access was not explicitly unavailable")
        routes[path] = code
    print(json.dumps({"schema": "szl.finance.generated-runtime-smoke/v1",
        "python": sys.version, "uid": os.getuid(), "locked_distributions": locked,
        "routes": routes, "live_provider_observations": False,
        "deployment_verified": False}, indent=2))


if __name__ == "__main__":
    main()
