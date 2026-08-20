# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1.
"""
test_be_hardening.py — real HTTP tests for the backend hardening surface.

Uses FastAPI's TestClient against a freshly hardened app. NO mocks: the Khipu
store writes to a real temp SQLite DB, the rate limiter counts real requests,
and OpenAPI is the real auto-generated schema. Restart durability is proven by
constructing a second DurableKhipu over the same on-disk path.

Run:  pytest -q test_be_hardening.py
"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

import szl_be_hardening as H

ORGAN = "testorgan"


@pytest.fixture()
def client(tmp_path):
    app = FastAPI(title="hardening-test", version="0.0.0")
    db_path = os.path.join(tmp_path, "khipu_test.sqlite3")
    report = H.harden(app, organ=ORGAN, khipu_path=db_path)
    assert report.get("ok") is True
    c = TestClient(app)
    c._db_path = db_path  # type: ignore[attr-defined]
    return c


# ---- 4: health probes ------------------------------------------------------
def test_healthz_liveness(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["doctrine"] == "v11"
    assert body["lock"] == "749/14/163"


def test_readyz_checks_chain(client):
    r = client.get(f"/api/{ORGAN}/v1/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["khipu_chain_ok"] is True
    assert body["khipu_durable"] is True
    assert body["khipu_backend"] == "sqlite"


# ---- 1: real input validation (pydantic) -----------------------------------
def test_echo_valid(client):
    r = client.post(f"/api/{ORGAN}/v1/be/echo", json={"message": "hi"})
    assert r.status_code == 200
    assert r.json()["echo"] == "hi"


def test_echo_rejects_raw_dict_extra_fields(client):
    r = client.post(f"/api/{ORGAN}/v1/be/echo", json={"message": "hi", "evil": 1})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert r.json()["error"]["doctrine"] == "v11"


def test_echo_rejects_missing_field(client):
    r = client.post(f"/api/{ORGAN}/v1/be/echo", json={})
    assert r.status_code == 422
    assert r.json()["error"]["doctrine"] == "v11"


# ---- 6: error envelopes ----------------------------------------------------
def test_error_envelope_on_404(client):
    r = client.get("/api/nope/v1/does-not-exist")
    assert r.status_code == 404
    err = r.json()["error"]
    assert set(err.keys()) >= {"code", "message", "trace_id", "doctrine"}
    assert err["doctrine"] == "v11"


def test_trace_headers_present(client):
    r = client.get("/healthz")
    assert r.headers.get("X-Trace-Id")
    assert r.headers.get("X-Span-Id")


def test_dynamic_page_is_no_store_and_truthfully_rate_limit_exempt(tmp_path):
    app = FastAPI()

    @app.get("/frontier")
    async def frontier():
        return HTMLResponse("<html><body>frontier</body></html>")

    H.harden(app, organ="headers", khipu_path=str(tmp_path / "headers.sqlite3"))
    response = TestClient(app).get("/frontier")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-RateLimit-Limit"] == str(H.RATE_LIMIT_PER_MIN)
    assert response.headers["X-RateLimit-Policy"] == "exempt"
    assert "X-RateLimit-Remaining" not in response.headers


def test_metered_api_emits_window_and_remaining_headers(client):
    response = client.get(f"/api/{ORGAN}/v1/readyz")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-RateLimit-Limit"] == str(H.RATE_LIMIT_PER_MIN)
    assert response.headers["X-RateLimit-Policy"] == "sliding-window;w=60"
    assert int(response.headers["X-RateLimit-Remaining"]) < H.RATE_LIMIT_PER_MIN
    assert int(response.headers["X-RateLimit-Reset"]) >= 1


# ---- 3: real OpenAPI -------------------------------------------------------
def test_openapi_served_at_organ_path(client):
    r = client.get(f"/api/{ORGAN}/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["openapi"].startswith("3.")
    # real generated paths include our hardening endpoints
    assert any("/khipu/verify" in p for p in spec["paths"])
    assert any("/echo" in p for p in spec["paths"])


# ---- 7: durable persistence (survives restart) -----------------------------
def test_khipu_append_and_verify(client):
    r = client.post(f"/api/{ORGAN}/v1/be/khipu/append",
                    json={"action": "test.action", "payload": {"k": 1}})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    v = client.get(f"/api/{ORGAN}/v1/be/khipu/verify").json()
    assert v["ok"] is True
    assert v["depth"] >= 1
    assert v["durable"] is True


def test_khipu_survives_restart(client):
    # append two receipts via the live API
    for i in range(2):
        client.post(f"/api/{ORGAN}/v1/be/khipu/append",
                    json={"action": f"a{i}", "payload": {"i": i}})
    depth_before = client.get(f"/api/{ORGAN}/v1/be/khipu/verify").json()["depth"]
    assert depth_before >= 2
    # simulate a process restart: brand-new store over the SAME on-disk path
    reopened = H.DurableKhipu(ORGAN, path=client._db_path)
    ok, depth, brk = reopened.verify()
    assert ok is True
    assert depth == depth_before  # receipts survived
    assert brk == -1


def test_khipu_append_rejects_bad_body(client):
    r = client.post(f"/api/{ORGAN}/v1/be/khipu/append", json={"payload": {}})
    assert r.status_code == 422  # missing required 'action'


# ---- 9: honest footer matches the exact v11 lock ---------------------------
def test_honest_footer_exact_lock(client):
    body = client.get("/honest").json()
    lock = body["doctrine_lock"]
    assert lock["doctrine"] == "v11"
    assert lock["state"] == "LOCKED"
    assert (lock["declarations"], lock["axioms"], lock["sorries"]) == (749, 14, 163)
    assert lock["commit"] == "c7c0ba17"
    assert lock["lambda"] == "Conjecture 1"
    assert body["footer"] == "Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1"


# ---- 2: rate limiting (RATE_LIMIT_PER_MIN/min/IP on the data surface) -------
def test_rate_limit_enforced():
    # The limiter meters the DATA surface (/api/<organ>/v1/...) only — human
    # pages and health/readiness probes are exempt (_is_rate_limited_path). So
    # hammer a real metered endpoint (POST /api/rl/v1/be/echo), not /healthz,
    # and key the threshold off the module constant rather than a hardcoded 60.
    app = FastAPI()
    with tempfile.TemporaryDirectory() as d:
        H.harden(app, organ="rl", khipu_path=os.path.join(d, "k.sqlite3"))
        c = TestClient(app)
        url = "/api/rl/v1/be/echo"
        statuses = [
            c.post(url, json={"message": "hi"}).status_code
            for _ in range(H.RATE_LIMIT_PER_MIN + 5)
        ]
        assert 429 in statuses, (
            f"expected at least one 429 after exceeding {H.RATE_LIMIT_PER_MIN}/min"
        )
        assert statuses[:H.RATE_LIMIT_PER_MIN] == [200] * H.RATE_LIMIT_PER_MIN
        # the 429 body is the uniform error envelope
        last = c.post(url, json={"message": "hi"})
        assert last.status_code == 429
        assert last.json()["error"]["code"] == "rate_limited"
        assert last.json()["error"]["doctrine"] == "v11"
        assert last.headers["Cache-Control"] == "no-store"
        assert last.headers["X-RateLimit-Limit"] == str(H.RATE_LIMIT_PER_MIN)
        assert last.headers["X-RateLimit-Remaining"] == "0"
        assert last.headers["X-RateLimit-Policy"] == "sliding-window;w=60"


def test_health_probe_is_rate_limit_exempt():
    # Liveness/readiness probes must NEVER be throttled — an over-eager probe
    # cadence can't be allowed to 429 the very endpoint that reports health.
    app = FastAPI()
    with tempfile.TemporaryDirectory() as d:
        H.harden(app, organ="rl", khipu_path=os.path.join(d, "k.sqlite3"))
        c = TestClient(app)
        statuses = [
            c.get("/healthz").status_code for _ in range(H.RATE_LIMIT_PER_MIN + 25)
        ]
        assert statuses == [200] * len(statuses), "health probe must be exempt from rate limiting"


# ---- assurance surface contracts -------------------------------------------
def test_assurance_attest_status_is_read_only(client, monkeypatch):
    import szl_dsse

    calls = {"count": 0}

    def _must_not_sign(*_args, **_kwargs):
        calls["count"] += 1
        raise AssertionError("read-only status endpoint attempted to mint a signature")

    monkeypatch.setattr(szl_dsse, "sign_payload", _must_not_sign)
    body = client.get(f"/api/{ORGAN}/v1/assurance/attest/status").json()
    assert calls["count"] == 0
    assert body["data_kind"] == "live"
    assert set(body["axes_present"]) == {"build", "model", "runtime"}
    assert body["axes_present"]["model"] is False
    assert "dsse" not in body


def test_assurance_compliance_exposes_canonical_measured_coverage(client):
    body = client.get(f"/api/{ORGAN}/v1/assurance/compliance").json()
    assert body["compliance_schema"] == "szl.compliance.crosswalk/v1"
    assert isinstance(body["crosswalk"], list)
    assert set(body["coverage"]["frameworks"]) >= {
        "NIST_AI_RMF", "ISO_IEC_42001", "EU_AI_ACT"
    }
    assert "NOT a certification" in body["crosswalk_disclaimer"]


def test_forge_ledger_exposes_deployed_summary_contract(client):
    body = client.get(f"/api/{ORGAN}/v1/forge/ledger").json()
    assert set(body) >= {"receipt_chain", "energy_ledger", "data_kind"}
    assert set(body["receipt_chain"]) >= {"depth", "chain_ok", "head", "count"}
