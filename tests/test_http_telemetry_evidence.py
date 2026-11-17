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


def test_entire_holographic_inline_javascript_parses():
    from html.parser import HTMLParser

    class InlineScripts(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.scripts = []
            self.parts = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "script" and not attrs.get("src") and attrs.get("type", "") in {
                "", "module", "text/javascript", "application/javascript"
            }:
                self.parts = []

        def handle_data(self, data):
            if self.parts is not None:
                self.parts.append(data)

        def handle_endtag(self, tag):
            if tag == "script" and self.parts is not None:
                self.scripts.append("".join(self.parts))
                self.parts = None

    parser = InlineScripts()
    parser.feed((ROOT / "static/3d/holographic.html").read_text(encoding="utf-8"))
    assert parser.scripts
    for index, javascript in enumerate(parser.scripts):
        result = subprocess.run(["node", "--check", "--input-type=module"],
                                input=javascript, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, f"inline script {index}: {result.stderr}"


def test_holographic_refresh_is_bounded_by_trace_expiry():
    html = (ROOT / "static/3d/holographic.html").read_text(encoding="utf-8")
    start = html.index("function _nextEvidenceRefreshDelay(")
    end = html.index("function _telemetryEvidenceText(", start)
    javascript = """
const assert = require("node:assert/strict");
const EVIDENCE_REFRESH_INTERVAL_MS = 300000;
const EVIDENCE_MAX_AGE_MS = 86400000;
let evidenceRefreshTimer = null;
let capturedDelay = null;
function clearTimeout() {}
function setTimeout(fn, delay) { capturedDelay = delay; return 1; }
function _updateEvidenceRail() {}
""" + html[start:end] + """
const near = {state: "OBSERVED", freshness: {age_s: 299, max_age_s: 300}};
assert.equal(_nextTelemetryRefreshDelay(near), 1050);
_scheduleEvidenceRefresh({}, null, near);
assert.equal(capturedDelay, 1050);
assert.equal(_nextTelemetryRefreshDelay({state: "OBSERVED", freshness: {age_s: 301, max_age_s: 300}}), 50);
assert.equal(_nextTelemetryRefreshDelay({state: "STALE", freshness: {age_s: 301, max_age_s: 300}}), 300000);
for (const bad of [null, "", "299", -1, Infinity, NaN]) {
  assert.equal(_nextTelemetryRefreshDelay({state: "OBSERVED", freshness: {age_s: bad, max_age_s: 300}}), 300000);
}
"""
    result = subprocess.run(["node", "-e", javascript], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr


def test_streaming_response_reports_middleware_timing_boundary(tmp_path, monkeypatch):
    import asyncio
    from fastapi.responses import StreamingResponse
    app = make_app("be", tmp_path, monkeypatch)

    @app.get("/stream")
    async def stream():
        async def chunks():
            yield b"first"
            await asyncio.sleep(0.02)
            yield b"last"
        return StreamingResponse(chunks())

    with TestClient(app) as client:
        response = client.get("/stream")
    assert response.content == b"firstlast"
    trace = obs.TRACES.all()[-1]
    assert trace.root.attributes["szl.timing_boundary"] == "middleware_response_ready"
    assert "streamed-body delivery is not measured" in obs.telemetry_summary()["http_duration_scope"]


def test_native_trace_owner_outvotes_untrusted_inbound_headers(tmp_path, monkeypatch):
    """A verified native server span owns correlation, not caller-supplied headers."""
    from types import MappingProxyType

    app = make_app("be", tmp_path, monkeypatch)
    native_trace = "a" * 32
    native_span = "b" * 16
    app._vsp_otel_context_reader = lambda request: MappingProxyType({
        "trace_id": native_trace, "span_id": native_span,
    })
    with TestClient(app) as client:
        response = client.get("/items/secret-value", headers={
            "traceparent": "00-" + "c" * 32 + "-" + "d" * 16 + "-01",
            "x-trace-id": "client-controlled-identifier",
        })
    assert response.status_code == 200
    assert response.headers["x-trace-id"] == native_trace
    assert response.headers["x-span-id"] == native_span
    assert len(obs.TRACES.all()) == 1
    assert obs.TRACES.all()[0].trace_id == native_trace
    assert obs.TRACES.all()[0].name == "GET /items/{item_id}"
    assert "secret-value" not in json.dumps(obs.TRACES.all()[0].to_dict())


def test_observability_routes_never_enter_shared_micro_cache(monkeypatch):
    """State may expire between requests; do not cache the ring or its details."""
    import szl_prod_hardening as prod

    monkeypatch.setenv("A11OY_HARDEN_CACHE", "1")
    monkeypatch.setenv("A11OY_HARDEN_RATELIMIT", "0")
    app = FastAPI()
    obs.register(app, ns="cachetest")
    prod.register(app, ns="cachetest")
    with TestClient(app) as client:
        paths = (
            "/api/cachetest/v1/observability/traces",
            "/api/cachetest/v1/observability/trace/" + "a" * 32,
            "/api/cachetest/v1/observability/health-summary",
            "/api/cachetest/v1/observability/workers-compute",
            "/api/cachetest/v1/telemetry/summary",
        )
        for path in paths:
            first = client.get(path)
            second = client.get(path)
            assert first.status_code == second.status_code
            assert first.headers.get("cache-control") == "no-store"
            assert second.headers.get("cache-control") == "no-store"
            assert first.headers.get("x-cache") != "HIT"
            assert second.headers.get("x-cache") != "HIT"
