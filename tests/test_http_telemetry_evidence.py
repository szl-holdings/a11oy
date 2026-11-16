"""Behavioral regression checks for process-local HTTP telemetry evidence."""
from pathlib import Path
import json
import subprocess
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import szl_observability as obs

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def fresh_ring(monkeypatch):
    monkeypatch.setattr(obs, "TRACES", obs.TraceRing(20))
    trace_token = obs._CURRENT_TRACE.set(None)
    span_token = obs._CURRENT_SPAN.set(None)
    yield
    obs._CURRENT_SPAN.reset(span_token)
    obs._CURRENT_TRACE.reset(trace_token)


def make_app(kind, tmp_path, monkeypatch):
    import szl_be_hardening as be
    import szl_prod_hardening as prod
    monkeypatch.setenv("A11OY_HARDEN_CACHE", "0")
    monkeypatch.setenv("A11OY_HARDEN_RATELIMIT", "0")
    app = FastAPI()

    @app.get("/items/{item_id}")
    async def item(item_id: str):
        with obs.span("work"):
            return {"ok": True}

    @app.get("/failure")
    async def failure():
        return JSONResponse({"ok": False}, status_code=503)

    @app.get("/bad-request")
    async def bad_request():
        return JSONResponse({"ok": False}, status_code=404)

    @app.get("/explode")
    async def explode():
        raise RuntimeError("deliberate test failure")

    if kind in {"be", "both"}:
        be.harden(app, organ="unit", khipu_path=str(tmp_path / "khipu.sqlite"))
    if kind in {"prod", "both"}:
        prod.register(app, ns="unit")
    return app


@pytest.mark.parametrize("kind", ["be", "prod", "both"])
def test_request_trace_correlates_and_hides_private_path(kind, tmp_path, monkeypatch):
    app = make_app(kind, tmp_path, monkeypatch)
    trace_id = "a1" * 16
    with TestClient(app) as client:
        response = client.get("/items/private-account-id?token=private-query", headers={
            "traceparent": "00-" + trace_id + "-" + "b2" * 8 + "-01",
            "x-request-id": "private-request-id",
            "x-trace-id": "private-trace-header",
        })
    assert response.status_code == 200
    traces = obs.TRACES.all()
    assert len(traces) == 1
    tr = traces[0]
    assert tr.trace_id == trace_id
    assert tr.name == "GET /items/{item_id}"
    assert tr.duration_ms is not None and tr.duration_ms >= 0
    assert tr.root.attributes["http.response.status_code"] == 200
    assert tr.root.attributes["http.route"] == "/items/{item_id}"
    assert len(tr.spans) == 2
    blob = json.dumps(tr.to_dict())
    for private_value in ("private-account-id", "private-query", "private-request-id", "private-trace-header"):
        assert private_value not in blob


@pytest.mark.parametrize("kind", ["be", "prod", "both"])
def test_http_errors_and_unmatched_paths_are_honest(kind, tmp_path, monkeypatch):
    with TestClient(make_app(kind, tmp_path, monkeypatch), raise_server_exceptions=False) as client:
        for path, code, expected in [
            ("/failure", 503, "ERROR"),
            ("/bad-request", 404, "OK"),
            ("/explode", 500, "ERROR"),
            ("/unmatched-private-id", 404, "OK"),
        ]:
            response = client.get(path)
            assert response.status_code == code
            tr = obs.TRACES.all()[-1]
            assert tr.root.attributes["http.response.status_code"] == code
            assert tr.status() == expected
    assert len(obs.TRACES.all()) == 4
    assert obs.TRACES.all()[-1].name == "GET"
    assert "unmatched-private-id" not in json.dumps(obs.TRACES.all()[-1].to_dict())


@pytest.mark.parametrize("kind", ["be", "prod"])
def test_trace_failure_keeps_request_available(kind, tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("tracing unavailable")
    monkeypatch.setattr(obs, "start_http_trace", broken)
    with TestClient(make_app(kind, tmp_path, monkeypatch)) as client:
        assert client.get("/items/one").status_code == 200
    assert len(obs.TRACES) == 0


def test_summary_empty_unfinished_stale_and_read_only(monkeypatch):
    monkeypatch.delenv("SZL_GIT_SHA", raising=False)
    monkeypatch.delenv("A11OY_GIT_SHA", raising=False)
    app = FastAPI()
    paths = obs.register(app, ns="unit")
    assert "/api/unit/v1/telemetry/summary" in paths
    with TestClient(app) as client:
        empty = client.get("/api/unit/v1/telemetry/summary")
        assert empty.headers["cache-control"] == "no-store"
        body = empty.json()
        assert body["state"] == "UNAVAILABLE"
        assert body["observed_at"] is None
        assert body["freshness"]["age_s"] is None
        assert body["counts"]["trace_count"] == 0
        assert body["coverage"]["dataset_count"] is None
        assert body["receipt_minted"] is False
        assert body["export_delivery_asserted"] is False
        assert len(obs.TRACES) == 0
        unfinished = obs.Trace("unfinished")
        obs.TRACES.add(unfinished)
        assert client.get("/api/unit/v1/telemetry/summary").json()["state"] == "UNAVAILABLE"
        completed = obs.Trace("GET /items/{item_id}")
        completed.end()
        obs.TRACES.add(completed)
        fresh = client.get("/api/unit/v1/telemetry/summary").json()
        assert fresh["state"] == "OBSERVED"
        assert fresh["counts"]["trace_count"] == 1
        assert fresh["source_revision"] is None
        monkeypatch.setattr(obs.time, "perf_counter", lambda: completed.root._t_end + 301)
        stale = client.get("/api/unit/v1/telemetry/summary").json()
        assert stale["state"] == "STALE"
        assert stale["freshness"]["age_s"] == 301
        assert len(obs.TRACES) == 2


def test_context_restored_and_duplicate_finish_not_recorded():
    parent = obs.start_trace("parent")
    request = SimpleNamespace(
        state=SimpleNamespace(),
        headers={},
        method="GET",
        scope={"route": SimpleNamespace(path="/items/{item_id}")},
    )
    trace = obs.start_http_trace(request)
    obs.finish_http_trace(trace, request, 200)
    assert obs.current_trace() is parent
    assert obs.current_span() is parent.root
    obs.finish_http_trace(trace, request, 200)
    assert len(obs.TRACES) == 1


def test_holographic_evidence_does_not_coerce_null_freshness():
    html = (ROOT / "static/3d/holographic.html").read_text(encoding="utf-8")
    start = html.index("function _telemetryEvidenceText(")
    end = html.index("function _updateEvidenceRail(", start)
    javascript = html[start:end] + """
const assert = require("node:assert/strict");
const unavailable = _telemetryEvidenceText(null, {collector: {age_s: null}});
assert.equal(unavailable.freshness, "UNAVAILABLE");
assert.ok(unavailable.telemetry.includes("traces UNAVAILABLE"));
const zero = _telemetryEvidenceText({state: "OBSERVED", counts: {trace_count: 0}}, {collector: {age_s: 0}});
assert.equal(zero.freshness, "collector age 0s");
const stale = _telemetryEvidenceText({state: "STALE", counts: {trace_count: 3}, freshness: {age_s: 301}}, null);
assert.ok(stale.freshness.includes("STALE"));
assert.ok(stale.coverage.includes("datasets UNAVAILABLE"));
for (const bad of [null, "", "0", -1, Infinity, NaN]) {
  assert.equal(_telemetryEvidenceText(null, {collector: {age_s: bad}}).freshness, "UNAVAILABLE");
}
"""
    result = subprocess.run(["node", "-e", javascript], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_root_request_uses_installed_w3c_trace_id(tmp_path, monkeypatch):
    from vsp_otel.middleware import install, parse_traceparent
    app = make_app("be", tmp_path, monkeypatch)
    install(app, service_name="unit", endpoint=None)
    with TestClient(app) as client:
        response = client.get("/items/one")
    outgoing = parse_traceparent(response.headers["traceparent"])
    trace = obs.TRACES.all()[-1]
    assert outgoing["trace_id"] == trace.trace_id == response.headers["x-trace-id"]


def test_summary_distinguishes_server_failures_from_handled_child_errors():
    handled = obs.Trace("GET /handled")
    handled.root.set_attribute("http.response.status_code", 200)
    child = handled.start_span("upstream", parent_id=handled.root.span_id)
    child.set_status("ERROR")
    child.end()
    handled.end()
    obs.TRACES.add(handled)
    server = obs.Trace("GET /server-error")
    server.root.set_attribute("http.response.status_code", 503)
    server.root.set_status("ERROR")
    server.end()
    obs.TRACES.add(server)
    counts = obs.telemetry_summary()["counts"]
    assert counts["trace_count"] == 2
    assert counts["error_trace_count"] == 2
    assert counts["server_error_count"] == 1
