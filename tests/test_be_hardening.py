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
    assert body["scope"] == "PROCESS_LIVENESS"
    assert body["capability_readiness_asserted"] is False
    assert body["operational_readiness_endpoint"] == "/api/a11oy/healthz"
    assert body["doctrine"] == "v11"
    assert body["lock"] == "749/14/163"
    assert body["signer"]["status"] in ("ABSENT", "UNAVAILABLE")
    assert body["signer"]["status"] != "DSSE-LIVE"
    assert body["signer"]["signing_available"] is False
    assert body["signer"]["scope"] == "NOT_EVALUATED_BY_THIS_ROUTE"
    assert body["signer"]["availability_evaluated"] is False
    assert body["signer"]["runtime_status_endpoint"] == "/api/a11oy/healthz"
    dsse = body.get("dsse_live") or {}
    assert dsse.get("status") in ("ABSENT", "UNAVAILABLE")
    assert dsse.get("status") != "DSSE-LIVE"
    assert dsse.get("signing_available") is False
    assert dsse.get("rollup") == "/api/a11oy/healthz"


def test_healthz_head_matches_get(client):
    get_r = client.get("/healthz")
    head_r = client.head("/healthz")
    assert get_r.status_code == 200
    assert head_r.status_code == 200
    assert head_r.content in (b"", None) or len(head_r.content) == 0


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
    assert lock["locked_formula_count"] == 8
    assert lock["locked_formula_ids"] == [
        "F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22",
    ]
    assert body["locked_formula_count"] == 8
    assert body["locked_formula_ids"] == lock["locked_formula_ids"]
    assert body["footer"] == "Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1"
    # 163 is lean_numbers.py sorries_raw @ c7c0ba17 (text occurrences incl. comments);
    # the same script gives sorries_noncomment = 149 at that commit.
    assert lock["sorries_method"].startswith(
        "lutar-lean .github/scripts/lean_numbers.py sorries_raw @ c7c0ba17")
    assert "including comments and docstrings" in lock["sorries_method"]
    assert "not a count of open proof obligations" in lock["sorries_method"]
    assert lock["sorries_noncomment"] == 149
    # 149 drops only `--` line comments; the served label must say so.
    nc = lock["sorries_noncomment_method"]
    assert "drops only lines whose first non-blank characters are `--`" in nc
    assert "/- -/ block comments" in nc and "/-- -/ doc comments" in nc
    assert "not a count of open proof obligations" in nc
    # The locked-8 theorems are not in lutar-lean at c7c0ba17; the source is pinned
    # to an immutable lutar-lean commit, never a moving branch.
    src = lock["locked_formula_source"]
    assert src.startswith("lutar-lean Lutar/Puriq/Formulas/ProvedFormulas.lean @ 3a886349")
    assert "lutar-lean main" not in src
    assert "not present at c7c0ba17" in src
    assert "outside the 749/14/163 count" in src
    assert "huggingface_hub_version" in body
    assert isinstance(body["huggingface_hub_version"], str)
    assert body["huggingface_hub_version"]


def test_huggingface_hub_version_helper_unavailable_without_module(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)
    assert H.huggingface_hub_version() == "UNAVAILABLE"


def test_huggingface_hub_version_helper_does_not_invent_pin(monkeypatch):
    import sys
    import types
    fake = types.ModuleType("huggingface_hub")
    fake.__version__ = "9.9.9-test"
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake)
    assert H.huggingface_hub_version() == "9.9.9-test"
    assert H.huggingface_hub_version() != "1.31.0"


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
    assert body["dsse"] is None
    assert body["signed"] is False
    assert body["receipt_minted"] is False
    assert body["export_read_only"] is True


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


# ---- passive reads: actual routes, real SQLite, no provider calls -----------
@pytest.fixture()
def passive_backend(monkeypatch, tmp_path):
    import copy
    import socket
    import sys
    import urllib.request
    import a11oy_signing_key
    import szl_cheapest_watt as cheapest
    import szl_dsse

    app = FastAPI()
    H.harden(app, organ="a11oy", khipu_path=str(tmp_path / "existing.sqlite3"))
    store = app.state.be_khipu
    store.emit("fixture.existing", {"evidence_class": "SAMPLE"})
    ledger = cheapest.CheapestWattLedger()
    ledger.record({})  # Offline no-choice fixture; no MEASURED input is supplied.
    monkeypatch.setattr(cheapest, "_LEDGER", ledger)
    calls = {name: 0 for name in ("sign", "key_loader", "factory", "constructor",
                                 "record", "emit", "operator", "network",
                                 "creating_connection", "sql_write")}

    def forbid(name):
        def blocked(*_args, **_kwargs):
            calls[name] += 1
            raise AssertionError(f"passive request called {name}")
        return blocked

    monkeypatch.setattr(szl_dsse, "sign_payload", forbid("sign"))
    monkeypatch.setattr(a11oy_signing_key, "load_signing_key", forbid("key_loader"))
    monkeypatch.setattr(cheapest, "get_ledger", forbid("factory"))
    monkeypatch.setattr(cheapest, "CheapestWattLedger", forbid("constructor"))
    monkeypatch.setattr(ledger, "record", forbid("record"))
    monkeypatch.setattr(store, "emit", forbid("emit"))
    monkeypatch.setattr(urllib.request, "urlopen", forbid("network"))
    monkeypatch.setattr(socket, "create_connection", forbid("network"))
    original_connect = H.sqlite3.connect

    def readonly_connect(*args, **kwargs):
        if kwargs.get("uri") is not True or "mode=ro" not in str(args[0]):
            calls["creating_connection"] += 1
            raise AssertionError("passive request used a creating SQLite connection")
        db = original_connect(*args, **kwargs)
        def trace(statement):
            if not statement.lstrip().upper().startswith("SELECT "):
                calls["sql_write"] += 1
        db.set_trace_callback(trace)
        return db

    monkeypatch.setattr(H.sqlite3, "connect", readonly_connect)
    # A module that is already loaded must still never be activated or queried.
    import types
    operator = types.ModuleType("szl_energy_operator")
    operator._OPERATOR = types.SimpleNamespace(status=forbid("operator"))
    operator.register = forbid("operator")
    operator.start = forbid("operator")
    monkeypatch.setitem(sys.modules, "szl_energy_operator", operator)

    async def fallback():
        return HTMLResponse("fallback must not own the API")
    app.add_api_route("/{remaining:path}", fallback, methods=["GET", "HEAD"])

    # RLock/callback identities are process objects, not mutable evidence.
    def stable_snapshot():
        return {
            "files": {str(p.relative_to(tmp_path)): p.read_bytes()
                      for p in tmp_path.rglob("*") if p.is_file()},
            "receipts": copy.deepcopy(store._all(read_only=True)),
            "memory_receipts": copy.deepcopy(store._mem),
            "placement": {key: copy.deepcopy(value) for key, value in ledger.__dict__.items()
                          if key not in {"_lock", "record"}},
            "loaded_modules": {name: sys.modules.get(name) for name in
                               ("szl_cheapest_watt", "szl_energy_operator")},
        }

    with TestClient(app) as http:
        yield app, http, store, cheapest, ledger, calls, stable_snapshot, tmp_path


def _assert_unsigned_read(response):
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    body = response.json()
    assert body["dsse"] is None
    assert body["signed"] is False
    assert body["receipt_minted"] is False
    assert body["export_read_only"] is True
    assert body["retained_signature_verified"] is False
    assert body["retained_attestation_state"] == "UNKNOWN"
    return body


@pytest.mark.parametrize("path,endpoint", [
    ("assurance/attest", "_assurance_attest"),
    ("assurance/attest/status", "_assurance_attest_status"),
    ("energy/cheapest-watt", "_cheapest_watt"),
])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_passive_backend_first_match_preserves_state(passive_backend, path, endpoint, method):
    from starlette.routing import Match

    app, http, store, _module, ledger, calls, snapshot, _root = passive_backend
    url = f"/api/a11oy/v1/{path}"
    scope = {"type": "http", "path": url, "method": method, "root_path": ""}
    first = next(r for r in app.routes if r.matches(scope)[0] == Match.FULL)
    assert first.endpoint.__name__ == endpoint
    before = snapshot()
    for _ in range(3):
        response = http.request(method, url)
        assert response.status_code == 200
        if method == "HEAD":
            assert response.content == b""
            assert response.headers["Cache-Control"] == "no-store"
        else:
            body = _assert_unsigned_read(response)
            if path.startswith("assurance"):
                assert body["statement"]["khipu_chain"]["depth"] == 1
                assert body["statement"]["khipu_chain"]["chain_ok"] is True
                assert body["signing_available"] is None
                assert body["signing_state"] == "UNKNOWN"
            else:
                assert body["decisions_total"] == 1
                assert body["latest_decision"] == ledger.status()["recent_decisions"][-1]
                assert body["ledger_state"] == "AVAILABLE"
    assert snapshot() == before
    assert all(count == 0 for count in calls.values())


@pytest.mark.parametrize("path", ["assurance/attest", "assurance/attest/status"])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize("damage", ["missing", "malformed", "broken-chain"])
def test_passive_attestation_does_not_recreate_or_certify_bad_store(
    passive_backend, path, method, damage
):
    from pathlib import Path

    _app, http, store, _module, _ledger, calls, _snapshot, root = passive_backend
    database = Path(store._path)
    if damage == "missing":
        # A missing binding must stay missing; no deletion of an open file is needed.
        store._path = str(root / "missing.sqlite3")
    elif damage == "malformed":
        database.write_bytes(b"test-owned invalid SQLite")
    else:
        import sqlite3
        # Bypass the read trap only to damage this test-owned fixture beforehand.
        with sqlite3.Connection(str(database)) as db:
            db.execute("UPDATE khipu SET digest='broken' WHERE seq=0")
    before = {str(p.relative_to(root)): p.read_bytes()
              for p in root.rglob("*") if p.is_file()}
    response = http.request(method, f"/api/a11oy/v1/{path}")
    assert response.status_code == (200 if damage == "broken-chain" else 503)
    assert response.headers["Cache-Control"] == "no-store"
    if method == "GET":
        body = _assert_unsigned_read(response)
        if damage == "broken-chain":
            assert body["statement"]["khipu_chain"]["chain_ok"] is False
            assert body["statement"]["khipu_chain"]["first_break_seq"] == 0
            assert body["statement"]["khipu_chain"]["depth"] == 1
            assert body["statement"]["khipu_chain"]["head"] == "broken"
            assert body["axes_present"]["runtime"] is False
        else:
            assert body["statement"] is None
            assert body["observation_state"] == "UNAVAILABLE"
    else:
        assert response.content == b""
    assert {str(p.relative_to(root)): p.read_bytes()
            for p in root.rglob("*") if p.is_file()} == before
    assert all(count == 0 for count in calls.values())


@pytest.mark.parametrize("state", ["unloaded", "no-ledger", "empty"])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_passive_energy_absent_or_empty_never_activates(passive_backend, monkeypatch, state, method):
    import sys

    _app, http, _store, module, ledger, calls, snapshot, _root = passive_backend
    if state == "unloaded":
        monkeypatch.delitem(sys.modules, "szl_cheapest_watt", raising=False)
    elif state == "no-ledger":
        monkeypatch.setattr(module, "_LEDGER", None)
    else:
        # Reset only test-owned constructor state; this is not a runtime reset.
        ledger._recent.clear()
        ledger._count = ledger._placed = ledger._no_choice = 0
        ledger._head = module.GENESIS_PREV
    before = snapshot()
    response = http.request(method, "/api/a11oy/v1/energy/cheapest-watt")
    assert response.status_code == 200
    if method == "GET":
        body = _assert_unsigned_read(response)
        assert body["latest_decision"] is None
        assert body["ledger_state"] == ("EMPTY" if state == "empty" else "UNAVAILABLE")
        if state == "empty":
            assert body["decisions_total"] == 0
        else:
            assert body["data_kind"] == "structural"
    else:
        assert response.content == b""
        assert response.headers["Cache-Control"] == "no-store"
    assert snapshot() == before
    assert all(count == 0 for count in calls.values())


@pytest.mark.parametrize("state", [None, [], {"recent_decisions": "bad"},
                                  {"recent_decisions": [None]},
                                  {"recent_decisions": [], "value": float("nan")},
                                  {"recent_decisions": [], "value": float("inf")}])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_passive_energy_invalid_existing_state_fails_closed(
    passive_backend, monkeypatch, state, method
):
    _app, http, _store, _module, ledger, calls, snapshot, _root = passive_backend
    monkeypatch.setattr(ledger, "status", lambda: state)
    before = snapshot()
    response = http.request(method, "/api/a11oy/v1/energy/cheapest-watt")
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    if method == "GET":
        body = _assert_unsigned_read(response)
        assert body["ledger_state"] == "UNAVAILABLE"
        assert body["latest_decision"] is None
    else:
        assert response.content == b""
    assert snapshot() == before
    assert all(count == 0 for count in calls.values())


def test_passive_energy_preserves_unverified_historical_payload(passive_backend):
    import copy

    _app, http, _store, _module, ledger, calls, snapshot, _root = passive_backend
    historical = ledger._recent[-1]["decision"]
    historical.update({"signed": True, "dsse": {"signatures": [{"sig": "historical-unverified"}]}})
    expected = copy.deepcopy(historical)
    before = snapshot()
    body = _assert_unsigned_read(http.get("/api/a11oy/v1/energy/cheapest-watt"))
    assert body["latest_decision"] == expected
    assert body["recent_decisions"][-1] == expected
    assert "no retained DSSE attestation retrieved or verified" in body["honesty_retained_attestation"]
    assert snapshot() == before
    assert all(count == 0 for count in calls.values())


def test_passive_attestation_keeps_explicit_receipt_writer(client):
    import sqlite3

    before = client.get(f"/api/{ORGAN}/v1/assurance/attest").json()
    assert before["statement"]["khipu_chain"]["depth"] == 0
    assert before["statement"]["khipu_chain"]["head"] == H._GENESIS
    response = client.post(f"/api/{ORGAN}/v1/be/khipu/append",
                           json={"action": "fixture.write", "payload": {"evidence_class": "SAMPLE"}})
    assert response.status_code == 200
    after = client.get(f"/api/{ORGAN}/v1/assurance/attest").json()
    assert after["statement"]["khipu_chain"]["depth"] == 1
    assert after["statement"]["khipu_chain"]["chain_ok"] is True
    with sqlite3.connect(client._db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM khipu").fetchone()[0] == 1


@pytest.mark.parametrize("path", ["assurance/attest", "assurance/attest/status"])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize("sidecars", ["present", "absent"])
def test_passive_attestation_wal_is_unavailable_without_sidecar_changes(
    passive_backend, path, method, sidecars
):
    import json
    from pathlib import Path
    import sqlite3

    _app, http, store, _module, _ledger, calls, _snapshot, root = passive_backend
    database = Path(store._path)
    writer = sqlite3.Connection(str(database))
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        writer.execute("PRAGMA wal_autocheckpoint=0")
        prev = writer.execute("SELECT digest FROM khipu WHERE seq=0").fetchone()[0]
        payload = {"evidence_class": "SAMPLE", "location": "uncheckpointed WAL fixture"}
        body = {"organ": store.organ, "ns": store.ns, "seq": 1,
                "action": "fixture.wal", "payload": payload, "prev": prev}
        writer.execute(
            "INSERT INTO khipu(seq,action,payload,prev,digest,ts) VALUES (?,?,?,?,?,?)",
            (1, body["action"], json.dumps(payload, sort_keys=True), prev,
             store._digest(body), 1.0),
        )
        writer.commit()
        assert writer.execute("SELECT COUNT(*) FROM khipu").fetchone()[0] == 2
        assert Path(str(database) + "-wal").stat().st_size > 32
        if sidecars == "absent":
            writer.close()  # Normal SQLite close/checkpoint of the test-owned writer.
            assert not Path(str(database) + "-wal").exists()
            assert not Path(str(database) + "-shm").exists()
        assert database.read_bytes()[18:20] == b"\x02\x02"
        before = {str(p.relative_to(root)): p.read_bytes()
                  for p in root.rglob("*") if p.is_file()}
        for _ in range(3):
            response = http.request(method, f"/api/a11oy/v1/{path}")
            assert response.status_code == 503
            assert response.headers["Cache-Control"] == "no-store"
            if method == "GET":
                result = _assert_unsigned_read(response)
                assert result["statement"] is None
                assert result["observation_state"] == "UNAVAILABLE"
            else:
                assert response.content == b""
            assert {str(p.relative_to(root)): p.read_bytes()
                    for p in root.rglob("*") if p.is_file()} == before
        assert all(count == 0 for count in calls.values())
    finally:
        writer.close()


@pytest.mark.parametrize("path", ["assurance/attest", "assurance/attest/status"])
def test_passive_attestation_keeps_one_snapshot_during_independent_append(
    client, monkeypatch, path
):
    from concurrent.futures import ThreadPoolExecutor

    store = client.app.state.be_khipu
    writer = H.DurableKhipu(ORGAN, path=client._db_path)
    first = writer.emit("fixture.before", {"evidence_class": "SAMPLE"})
    original_all = store._all
    snapshots = []
    committed = []

    with ThreadPoolExecutor(max_workers=1) as pool:
        def read_then_append(*, read_only=False):
            rows = original_all(read_only=read_only)
            snapshots.append(rows)
            assert read_only is True
            if len(snapshots) == 1:
                # A different store/lock and a different SQLite connection commit
                # after the observer's SELECT, before it produces the response.
                committed.append(pool.submit(
                    writer.emit, "fixture.concurrent", {"evidence_class": "SAMPLE"}
                ).result(timeout=5))
            return rows

        monkeypatch.setattr(store, "_all", read_then_append)
        response = client.get(f"/api/{ORGAN}/v1/{path}")

    body = _assert_unsigned_read(response)
    chain = body["statement"]["khipu_chain"]
    assert response.status_code == 200
    assert committed[0]["prev"] == first["digest"]
    assert writer.verify() == (True, 2, -1)
    assert writer.head() == committed[0]["digest"]
    assert chain["chain_ok"] is True
    assert chain["depth"] == 1
    assert chain["head"] == first["digest"]
    assert chain["head"] != writer.head()
    assert len(snapshots) == 1
