#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Vertical-shell /healthz is process-scoped and computed, never a constant ok:true.

The emitted shells (terra, sentra, counsel, finance, vessels, lyte) answered
/healthz with a hard-coded {"ok": true}. It stays HTTP 200 for orchestrators and
the finance container smoke (the /api/livez convention), but `ok` is now the
shell's own landing/panels integrity and the body states its scope.
"""
import hashlib
import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1" * 40


def load(name):
    # Same provider isolation as test_hf_publish_vertical_flagships_v4: the
    # renderer imports huggingface_hub, which the hash-locked CI closure omits.
    spec = importlib.util.spec_from_file_location("test_healthz_" + name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    fake_hub = ModuleType("huggingface_hub")
    fake_hub.HfApi = type("HfApi", (), {})
    previous = sys.modules.get("huggingface_hub")
    sys.modules["huggingface_hub"] = fake_hub
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop("huggingface_hub", None)
        else:
            sys.modules["huggingface_hub"] = previous
    return module


def _serve(tmp_path, monkeypatch, slug, *, tamper_landing=False):
    emit, r = load("materialize_finance_runtime"), load("hf_publish_vertical_flagships_v4_impl")
    files = emit.payloads(r, REVISION, 1)
    item = next(row for row in r.FLAGSHIPS if row["slug"] == slug)
    panels = r.html(item).encode()
    landing_sha = hashlib.sha256(panels).hexdigest()
    config = json.loads(files["config.json"])
    config.update(slug=slug, title=item["title"], vertical=item["vertical"],
                  product_source=item["source"], hf_repository=r.ORG + "/" + slug,
                  upstream=item["upstream"],
                  landing_sha256="0" * 64 if tamper_landing else landing_sha,
                  panels_sha256=landing_sha)
    files.update({"config.json": json.dumps(config).encode(),
                  "index.html": panels, "panels.html": panels})
    for name, raw in files.items():
        (tmp_path / name).write_bytes(raw)
    monkeypatch.chdir(tmp_path)
    ns = {"__name__": "generated_healthz_fixture_" + slug}
    with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
        exec(compile(r.APP, "generated-healthz.py", "exec"), ns)
    return ns["app"]


def test_emitted_app_has_no_unconditional_healthz():
    r = load("hf_publish_vertical_flagships_v4_impl")
    assert '"ok":True,"product"' not in r.APP
    assert r.APP.count('@app.get("/healthz")') == 1
    assert 'integrity=local_integrity()' in r.APP
    assert '"production_ready":False' in r.APP


@pytest.mark.parametrize("slug", ["finance", "terra", "counsel", "sentra"])
def test_healthz_is_process_scoped_and_ok_tracks_integrity(tmp_path, monkeypatch, slug):
    from fastapi.testclient import TestClient

    with TestClient(_serve(tmp_path, monkeypatch, slug)) as client:
        with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
            response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "PROCESS_ALIVE"
    assert body["production_ready"] is False
    assert body["integrity"]["state"] == "MEASURED"
    assert body["integrity"]["checks"] == {"landing_sha256": True, "panels_sha256": True}
    assert body["readiness"] == "/readyz" and body["upstream"] == "/api/live"
    assert "not upstream health" in body["scope"]
    assert body["domain"] == slug


@pytest.mark.parametrize("slug", ["finance", "sentra"])
def test_healthz_reports_not_ok_when_integrity_fails_but_stays_200(tmp_path, monkeypatch, slug):
    from fastapi.testclient import TestClient

    with TestClient(_serve(tmp_path, monkeypatch, slug, tamper_landing=True)) as client:
        with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
            health = client.get("/healthz")
            ready = client.get("/readyz")
    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is False
    assert body["status"] == "PROCESS_ALIVE"
    assert body["integrity"]["state"] == "INVALID"
    assert body["integrity"]["checks"]["landing_sha256"] is False
    assert ready.status_code == 503


class _Upstream:
    """Minimal httpx response double for the emitted shell's probe()."""

    def __init__(self, status_code, body, content_type="application/json"):
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300
        self.headers = {"content-type": content_type}
        self._body = body
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        return self._body


def _source(status, *, value=True, age=60.0):
    import time

    return {"value": {"items": [{"id": 1}]} if value else None,
            "freshness": {"status": status, "age_s": age,
                          "fetched_at": (time.time() - age) if value else None}}


def _feed(slug, statuses):
    """The canonical feed shapes (a11oy_vertical_feeds.py): per-source freshness."""
    if slug == "terra":
        keys, vertical = ("hpd_litigations", "dob_violations", "rates"), "realestate"
    elif slug == "counsel":
        keys, vertical = ("federal_register", "court_filings"), "legal"
    else:
        return {"schema": "szl.public-receipt-verifier/manifest/v1", "state": "LIVE",
                "try": {"method": "POST", "endpoint": "/api/a11oy/v1/verify/receipt"},
                "evidence": ["signature", "payload_digest", "hash_chain"]}
    body = {"vertical": vertical, "sources_cited": [], "doctrine": None}
    for key, status in zip(keys, statuses):
        body[key] = _source(status, value=status != "unavailable")
    return body


def _all_live(slug):
    return _feed(slug, ("live", "live", "live"))


@pytest.mark.parametrize("slug", ["terra", "counsel", "sentra"])
@pytest.mark.parametrize("upstream, reason", [
    ((503, {"status": "UNAVAILABLE"}), "UPSTREAM_UNAVAILABLE"),
    ((200, {"status": "UNAVAILABLE", "ok": False}), "UPSTREAM_DATA_UNAVAILABLE"),
    ((200, {"state": "UNAVAILABLE"}), "UPSTREAM_DATA_UNAVAILABLE"),
    (None, "UPSTREAM_UNAVAILABLE"),
])
def test_live_and_readyz_are_503_when_upstream_is_not_accepted(tmp_path, monkeypatch, slug, upstream, reason):
    """HTTP 200 with an UNAVAILABLE body was previously painted as live."""
    from fastapi.testclient import TestClient
    import httpx

    def fake_get(url, **kwargs):
        if upstream is None:
            raise httpx.ConnectError("upstream down")
        return _Upstream(*upstream)

    monkeypatch.setattr(httpx, "get", fake_get)
    with TestClient(_serve(tmp_path, monkeypatch, slug)) as client:
        live = client.get("/api/live")
        ready = client.get("/readyz")
        health = client.get("/healthz")
    assert live.status_code == 503
    assert live.json()["status"] == "UNAVAILABLE"
    if upstream is not None:
        assert live.json()["reason"] == reason
    assert ready.status_code == 503
    body = ready.json()
    assert body["ready"] is False and body["state"] == "UPSTREAM_UNAVAILABLE"
    assert body["checks"] == {"landing_sha256": True, "panels_sha256": True, "upstream": False}
    assert body["upstream"]["accepted"] is False and body["upstream"]["reason"] == reason
    # Liveness stays process-scoped: the process is alive and its files intact.
    assert health.status_code == 200 and health.json()["ok"] is True


@pytest.mark.parametrize("slug", ["terra", "counsel", "sentra"])
def test_live_and_readyz_are_200_only_for_an_accepted_upstream_payload(tmp_path, monkeypatch, slug):
    from fastapi.testclient import TestClient
    import httpx

    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: _Upstream(200, _all_live(slug)))
    with TestClient(_serve(tmp_path, monkeypatch, slug)) as client:
        live = client.get("/api/live")
        ready = client.get("/readyz")
    assert live.status_code == 200
    assert live.json()["status"] == "REACHABLE"
    assert live.json()["evidence_state"] == "REACHABLE"
    assert live.json()["honesty"] == "HTTP success is reachability, not MEASURED"
    assert ready.status_code == 200
    body = ready.json()
    assert body["ready"] is True and body["state"] == "MEASURED"
    assert body["checks"] == {"landing_sha256": True, "panels_sha256": True, "upstream": True}
    assert body["upstream"]["state"] == ("SNAPSHOT" if slug == "sentra" else "REACHABLE")
    if slug == "sentra":
        assert body["upstream"]["receipt_verified"] is False
        assert body["upstream"]["observation"]["cached"] is True
        assert body["upstream"]["observation"]["ttl_seconds"] == 120


@pytest.mark.parametrize("slug", ["terra", "counsel"])
def test_feed_with_every_source_unavailable_is_not_ready(tmp_path, monkeypatch, slug):
    """The canonical feeds answer HTTP 200 and keep availability per source."""
    from fastapi.testclient import TestClient
    import httpx

    feed = _feed(slug, ("unavailable", "unavailable", "unavailable"))
    assert "status" not in feed and "state" not in feed and "ok" not in feed
    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: _Upstream(200, feed))
    with TestClient(_serve(tmp_path, monkeypatch, slug)) as client:
        live = client.get("/api/live")
        ready = client.get("/readyz")
    assert live.status_code == 503 and live.json()["status"] == "UNAVAILABLE"
    assert live.json()["reason"] == "UPSTREAM_SOURCES_UNAVAILABLE"
    assert ready.status_code == 503
    body = ready.json()
    assert body["ready"] is False and body["state"] == "UPSTREAM_UNAVAILABLE"
    assert body["upstream"]["state"] == "UNAVAILABLE"


@pytest.mark.parametrize("slug", ["terra", "counsel"])
@pytest.mark.parametrize("statuses", [("live", "unavailable", "live"), ("cached", "live", "stale")])
def test_partial_or_cached_feed_is_ready_and_labelled_partial(tmp_path, monkeypatch, slug, statuses):
    from fastapi.testclient import TestClient
    import httpx

    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: _Upstream(200, _feed(slug, statuses)))
    with TestClient(_serve(tmp_path, monkeypatch, slug)) as client:
        live = client.get("/api/live")
        ready = client.get("/readyz")
    assert live.status_code == 200 and live.json()["evidence_state"] == "PARTIAL"
    assert ready.status_code == 200 and ready.json()["upstream"]["state"] == "PARTIAL"


@pytest.mark.parametrize("slug, mutate, reason", [
    ("terra", lambda feed: feed.update(vertical="legal"), "UPSTREAM_VERTICAL_MISMATCH"),
    ("counsel", lambda feed: feed.pop("court_filings"), "UPSTREAM_SOURCE_EVIDENCE_MISSING"),
    ("counsel", lambda feed: feed["federal_register"]["freshness"].update(status="fresh"),
     "UPSTREAM_SOURCE_FRESHNESS_UNKNOWN"),
    ("terra", lambda feed: feed["rates"]["freshness"].update(fetched_at=None), "UPSTREAM_SOURCE_CLOCK_INVALID"),
    ("terra", lambda feed: feed["rates"]["freshness"].update(fetched_at=4e12), "UPSTREAM_SOURCE_CLOCK_INVALID"),
])
def test_feed_without_valid_source_evidence_is_not_accepted(tmp_path, monkeypatch, slug, mutate, reason):
    from fastapi.testclient import TestClient
    import httpx

    feed = _all_live(slug)
    mutate(feed)
    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: _Upstream(200, feed))
    with TestClient(_serve(tmp_path, monkeypatch, slug)) as client:
        live = client.get("/api/live")
        ready = client.get("/readyz")
    assert live.status_code == 503 and live.json()["reason"] == reason
    assert ready.status_code == 503 and ready.json()["ready"] is False


@pytest.mark.parametrize("slug", ["terra", "counsel", "sentra"])
def test_html_200_upstream_is_never_ready(tmp_path, monkeypatch, slug):
    """An unregistered route falls through to the SPA shell with HTML 200."""
    from fastapi.testclient import TestClient
    import httpx

    page = "<!doctype html><html><body>console</body></html>"
    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: _Upstream(200, page, "text/html; charset=utf-8"))
    with TestClient(_serve(tmp_path, monkeypatch, slug)) as client:
        live = client.get("/api/live")
        ready = client.get("/readyz")
    assert live.status_code == 503 and live.json()["reason"] == "UPSTREAM_NOT_JSON"
    assert ready.status_code == 503 and ready.json()["state"] == "UPSTREAM_UNAVAILABLE"


def test_readyz_reports_invalid_not_upstream_when_local_integrity_fails(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import httpx

    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: _Upstream(200, _all_live("terra")))
    with TestClient(_serve(tmp_path, monkeypatch, "terra", tamper_landing=True)) as client:
        ready = client.get("/readyz")
    assert ready.status_code == 503
    assert ready.json()["state"] == "INVALID"
    assert ready.json()["checks"]["upstream"] is True


def test_finance_live_and_readyz_are_503_without_its_canonical_upstream(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    with TestClient(_serve(tmp_path, monkeypatch, "finance")) as client:
        with patch("socket.socket.connect", side_effect=OSError("network forbidden")):
            live = client.get("/api/live")
            ready = client.get("/readyz")
    assert live.status_code == 503 and live.json()["status"] == "UNAVAILABLE"
    assert ready.status_code == 503
    body = ready.json()
    # Finance may own a more specific readiness route; whichever answers, local
    # artifacts verify and the canonical data path is reported unavailable.
    assert body["ready"] is False and body["state"] != "MEASURED"
    assert body["checks"]["landing_sha256"] is True and body["checks"]["panels_sha256"] is True
    upstream = {k: v for k, v in body["checks"].items() if k not in ("landing_sha256", "panels_sha256")}
    assert upstream and all(value is False for value in upstream.values())


def test_panel_livebar_requires_http_success_before_reachable():
    r = load("hf_publish_vertical_flagships_v4_impl")
    for row in r.FLAGSHIPS:
        page = r.html(row)
        assert ("const reachable=r.ok&&(j.status==='REACHABLE'||j.status==='LIVE'"
                "||j.status==='SNAPSHOT');") in page
        # An accepted Finance snapshot keeps its non-live label.
        assert "(j.status==='SNAPSHOT'?'SNAPSHOT':'REACHABLE')" in page
        assert "s.className='status '+(j.status==='LIVE'?'is-live':'')" not in page


def test_publication_admission_separates_upstream_outage_from_artifact_integrity():
    r = load("hf_publish_vertical_flagships_v4_impl")
    revision, run_id = "a" * 40, "12345"
    row = {
        "slug": "terra", "artifact_set_sha256": "c" * 64, "landing_sha256": "d" * 64,
        "panels_sha256": "e" * 64, "forge": None,
        "root": {"http_status": 200, "marker_present": True},
        "panels": {"http_status": 200, "marker_present": True},
        "build_info_http": 200,
        "build_info": {"schema": "szl.build-info/v1", "source_repository": "szl-holdings/a11oy",
                       "source_revision": revision, "workflow_run_id": int(run_id),
                       "artifact_set_sha256": "c" * 64, "hf_revision": "f" * 40, "forge": None},
        "readyz_http": 503,
        "readyz": {"schema": "szl.vertical-shell-readiness/v1", "ready": False,
                   "state": "UPSTREAM_UNAVAILABLE",
                   "checks": {"landing_sha256": True, "panels_sha256": True, "upstream": False},
                   "upstream": {"accepted": False, "status": "UNAVAILABLE", "reason": "UPSTREAM_UNAVAILABLE"}},
        "deployment_receipt_http": 200,
        "deployment_receipt": {"schema": "szl.vertical-shell-deployment/v1",
                               "state": "VERIFIED_RUNTIME_ARTIFACTS", "source_revision": revision,
                               "workflow_run_id": int(run_id), "artifact_set_sha256": "c" * 64,
                               "landing_sha256": "d" * 64, "panels_sha256": "e" * 64, "forge": None},
    }
    assert r.observation_passes(row, source_revision=revision, workflow_run_id=run_id)
    # The upstream outage is recorded on the row, never hidden.
    assert row["upstream_readiness"]["accepted"] is False
    assert row["upstream_readiness"]["http_status"] == 503
    assert row["readyz_http"] == 503 and row["readyz"]["ready"] is False
    # Local integrity failure is never admitted, whatever the upstream says.
    row["readyz"]["checks"]["panels_sha256"] = False
    assert not r.observation_passes(row, source_revision=revision, workflow_run_id=run_id)
    row["readyz"]["checks"]["panels_sha256"] = True
    row["readyz"]["state"] = "INVALID"
    assert not r.observation_passes(row, source_revision=revision, workflow_run_id=run_id)


class _ObservationBody(io.BytesIO):
    def __init__(self, raw, status):
        super().__init__(raw)
        self.status = status
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


@pytest.mark.parametrize("status", [200, 503])
def test_publication_http_json_preserves_response_status_and_body(monkeypatch, status):
    r = load("hf_publish_vertical_flagships_v4_impl")
    url = "https://szlholdings-terra.hf.space/readyz"
    payload = {"ready": status == 200, "state": "UPSTREAM_UNAVAILABLE" if status == 503 else "MEASURED"}
    body = _ObservationBody(json.dumps(payload).encode(), status)
    calls = []

    def open_response(request, *, timeout):
        calls.append((request, timeout))
        if status == 503:
            raise urllib.error.HTTPError(url, status, "Service Unavailable", {}, body)
        return body

    monkeypatch.setattr(r.urllib.request, "urlopen", open_response)
    assert r.get_json(url, timeout=7) == (status, payload)
    assert len(calls) == 1
    request, timeout = calls[0]
    assert request.full_url == url and timeout == 7
    assert request.get_method() == "GET"
    assert {name.lower(): value for name, value in request.header_items()} == {
        "user-agent": r.USER_AGENT, "cache-control": "no-cache"}
    assert body.read_sizes == [1024 * 1024 + 1]
    assert body.closed
    assert r._BASE.get_json is r.get_json


@pytest.mark.parametrize("status", [200, 503])
@pytest.mark.parametrize("raw, error", [
    (b'{"ready":false,"reason":"\xff"}', "UnicodeDecodeError"),
    (b"<!doctype html><html>unavailable</html>", "JSONDecodeError"),
    (b" " * (1024 * 1024) + b"{}", "ObservationBodyTooLarge"),
], ids=["invalid-utf8", "html-body", "oversized-body"])
def test_publication_http_invalid_body_keeps_real_status_and_cannot_admit(monkeypatch, status, raw, error):
    r = load("hf_publish_vertical_flagships_v4_impl")
    url = "https://szlholdings-terra.hf.space/readyz"
    body = _ObservationBody(raw, status)

    def open_response(request, *, timeout):
        if status == 503:
            raise urllib.error.HTTPError(url, status, "Service Unavailable", {}, body)
        return body

    monkeypatch.setattr(r.urllib.request, "urlopen", open_response)
    observed_status, payload = r.get_json(url)
    assert observed_status == status and payload == {"error": error}
    assert body.read_sizes == [1024 * 1024 + 1]
    assert body.closed
    row = {"slug": "terra", "readyz_http": observed_status, "readyz": payload}
    assert r._publication_view(row)["readyz"] == {"error": error}
    assert not r.observation_passes(row, source_revision=REVISION, workflow_run_id="1")


def test_publication_http_transport_failure_is_not_an_http_response(monkeypatch):
    r = load("hf_publish_vertical_flagships_v4_impl")

    def unavailable(request, *, timeout):
        raise urllib.error.URLError("private transport details must not be copied")

    monkeypatch.setattr(r.urllib.request, "urlopen", unavailable)
    assert r.get_json("https://szlholdings-terra.hf.space/readyz") == (None, {"error": "URLError"})


def test_publication_base_observer_retains_503_json_for_integrity_admission(monkeypatch):
    r = load("hf_publish_vertical_flagships_v4_impl")
    revision, run_id = "a" * 40, "12345"
    ready = {"schema": "szl.vertical-shell-readiness/v1", "ready": False,
             "state": "UPSTREAM_UNAVAILABLE",
             "checks": {"landing_sha256": True, "panels_sha256": True, "upstream": False},
             "upstream": {"accepted": False, "status": "UNAVAILABLE", "reason": "UPSTREAM_UNAVAILABLE"}}
    build = {"schema": "szl.build-info/v1", "source_repository": "szl-holdings/a11oy",
             "source_revision": revision, "workflow_run_id": int(run_id),
             "artifact_set_sha256": "c" * 64, "hf_revision": "f" * 40, "forge": None}
    deployment = {"schema": "szl.vertical-shell-deployment/v1", "state": "VERIFIED_RUNTIME_ARTIFACTS",
                  "source_revision": revision, "workflow_run_id": int(run_id),
                  "artifact_set_sha256": "c" * 64, "landing_sha256": "d" * 64,
                  "panels_sha256": "e" * 64, "forge": None}
    responses = {"/api/build-info": (200, build), "/readyz": (503, ready),
                 "/build-receipt.json": (200, deployment)}
    requests = []

    def open_response(request, *, timeout):
        path = request.full_url.removeprefix("https://szlholdings-terra.hf.space")
        requests.append(path)
        status, payload = responses[path]
        body = _ObservationBody(json.dumps(payload).encode(), status)
        if status == 503:
            raise urllib.error.HTTPError(request.full_url, status, "Service Unavailable", {}, body)
        return body

    monkeypatch.setattr(r.urllib.request, "urlopen", open_response)
    monkeypatch.setattr(r._BASE, "probe_html", lambda *args, **kwargs: {
        "http_status": 200, "marker_present": True})
    row = {"slug": "terra", "root_marker": "fixture-root", "artifact_set_sha256": "c" * 64,
           "landing_sha256": "d" * 64, "panels_sha256": "e" * 64, "forge": None}
    r._base_observe_flagship(row)
    assert requests == list(responses)
    assert row["readyz_http"] == 503 and row["readyz"] == ready
    assert r.observation_passes(row, source_revision=revision, workflow_run_id=run_id)
    assert row["readyz_http"] == 503 and row["readyz"]["ready"] is False
    assert row["upstream_readiness"] == {
        "accepted": False, "status": "UNAVAILABLE", "reason": "UPSTREAM_UNAVAILABLE", "http_status": 503}
    row["build_info"]["source_revision"] = "b" * 40
    assert not r.observation_passes(row, source_revision=revision, workflow_run_id=run_id)
    row["build_info"]["source_revision"] = revision
    row["readyz"]["checks"]["panels_sha256"] = False
    assert not r.observation_passes(row, source_revision=revision, workflow_run_id=run_id)


def test_publication_admission_accepts_the_emitted_finance_readiness_shape(tmp_path, monkeypatch):
    """Finance owns its /readyz (contract-versioned projection); an unreachable
    canonical A11oy is still an upstream outage, not a failed publication."""
    from fastapi.testclient import TestClient

    r = load("hf_publish_vertical_flagships_v4_impl")
    with TestClient(_serve(tmp_path, monkeypatch, "finance")) as client:
        with patch("socket.socket.connect", side_effect=OSError("network forbidden")):
            ready = client.get("/readyz")
    assert ready.status_code == 503
    row = {"slug": "finance", "readyz_http": ready.status_code, "readyz": ready.json()}
    view = r._publication_view(row)
    assert view["readyz_http"] == 200 and view["readyz"]["ready"] is True
    assert row["upstream_readiness"]["accepted"] is False
    assert row["upstream_readiness"]["http_status"] == 503
    # An incompatible canonical contract is not an outage and is never admitted.
    incompatible = {"slug": "finance", "readyz_http": 503,
                    "readyz": {**ready.json(), "state": "INCOMPATIBLE"}}
    assert r._publication_view(incompatible)["readyz_http"] == 503
