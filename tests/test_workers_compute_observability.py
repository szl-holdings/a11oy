# SPDX-License-Identifier: Apache-2.0
"""Lock the declared Workers Compute contract to Wrangler and the page.

The Python process does not read Cloudflare. Live values stay UNAVAILABLE.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRANGLER = ROOT / "ops" / "alert-relay-worker" / "wrangler.jsonc"
PAGE = ROOT / "pages" / "observability.html"
ROUTE = "/api/a11oy/v1/observability/workers-compute"


def _wrangler_observability() -> dict:
    payload = json.loads(WRANGLER.read_text(encoding="utf-8"))
    return payload["observability"]


def test_wrangler_settings_match_python_contract() -> None:
    import szl_observability as obs

    contract = obs.workers_compute_contract()
    assert contract["settings"] == _wrangler_observability()
    assert contract["settings"] == obs.WORKERS_COMPUTE_SETTINGS
    assert contract["worker"]["source"] == "ops/alert-relay-worker/wrangler.jsonc"
    assert contract["worker"]["name"] == "szl-alert-relay"
    assert contract["worker"]["host"] == "ntfy.a11oy.net"


def test_contract_stays_declared_and_unsigned() -> None:
    import szl_observability as obs

    contract = obs.workers_compute_contract()
    assert contract["schema"] == "szl.workers-compute-observability/v1"
    assert contract["measurement"] == "DECLARED_SOURCE"
    assert contract["live_values"] == "UNAVAILABLE"
    assert contract["receipt_minted"] is False
    assert contract["production_authorization"] is False
    assert contract["signer"] == "ABSENT"
    assert contract["settings"]["redact_query_string"] is True
    keys = [tag["key"] for tag in contract["tags"]]
    assert "$metadata.service" in keys
    assert "$metadata.traceId" in keys
    assert "$metadata.duration" in keys
    assert len(keys) == len(set(keys))


def test_page_reads_the_python_route() -> None:
    html = PAGE.read_text(encoding="utf-8")
    assert 'id="workers-compute"' in html
    assert "API+'/observability/workers-compute'" in html
    assert "does not read the Cloudflare dataset" in html
    assert "loadWorkersCompute()" in html


def test_register_serves_the_declared_route() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import szl_observability as obs

    app = FastAPI()
    paths = obs.register(app, ns="a11oy")
    assert ROUTE in paths
    response = TestClient(app).get(ROUTE)
    assert response.status_code == 200
    body = response.json()
    assert body["ns"] == "a11oy"
    assert body["measurement"] == "DECLARED_SOURCE"
    assert body["live_values"] == "UNAVAILABLE"
    assert body["receipt_minted"] is False
    assert body["settings"] == _wrangler_observability()
    assert body["doctrine"]["version"] == "v11"
    assert body["doctrine"]["key_committed"] is False
    assert isinstance(body["ts"], str) and body["ts"]
