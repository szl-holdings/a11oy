# SPDX-License-Identifier: Apache-2.0
"""Civilian software fixture tests, not trained-model or field performance claims."""
import copy
import hashlib
import importlib.util
import json
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from civilian_observatory.app import register
from civilian_observatory import feeds
from civilian_observatory.core import API_PREFIX, Observatory, PublicCache, BusyError, ContractError, rank, dry_run, source_age, verify_package_manifest


def src(name):
    return {"name": name, "source_url": "https://example.org/SOFTWARE_TEST_FIXTURE",
            "fetched_at": "2026-10-01T00:00:00+00:00", "source_date": "2026-10-01",
            "sha256": "a" * 64, "status": "OBSERVED", "error": None}


def snapshot():
    return {"schema_version": "1.0", "generated_at": "2026-10-01T00:00:00+00:00",
            "kev": {"source": src("KEV FIXTURE"), "catalog_version": "FIXTURE",
                    "entries": [{"cveID": "CVE-2024-0001", "dateAdded": "2026-10-01",
                                 "vendorProject": "FIXTURE", "product": "TEST ONLY",
                                 "shortDescription": "SOFTWARE TEST", "requiredAction": "TEST ONLY",
                                 "vulnerabilityName": "FIXTURE", "knownRansomwareCampaignUse": "Unknown"}]},
            "epss": {"source": src("EPSS FIXTURE"), "requested": ["CVE-2024-0001", "CVE-2024-0002"],
                     "entries": [{"cve": "CVE-2024-0001", "epss": 0.0, "percentile": 0.0, "date": "2026-10-01"},
                                 {"cve": "CVE-2024-0002", "epss": 0.99, "percentile": 0.99, "date": "2026-10-01"}]}}


class FixtureProvider:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def get_feeds(self):
        self.calls += 1
        if self.fail:
            raise OSError("SOFTWARE_TEST_OUTAGE")
        return snapshot()

    def get_epss(self, ids):
        self.calls += 1
        value = snapshot()["epss"]
        value["entries"] = [r for r in value["entries"] if r["cve"] in ids]
        value["requested"] = ids
        return value

    def get_headers(self, target):
        self.calls += 1
        return {"target": target, "source": src("HEADER FIXTURE"), "headers": [], "http_status": 200}

    def get_weather(self, area):
        self.calls += 1
        return {"area": area, "source": src("WEATHER FIXTURE"), "alerts": [], "count": 0, "reported_count": 0}


@pytest.fixture
def prepared(tmp_path):
    root = tmp_path / "package"
    (root / "data").mkdir(parents=True)
    (root / "static").mkdir()
    (root / "data/estate.json").write_text(json.dumps({"summary": {"repo_count": 1}, "repositories": [{"visibility": "public", "name": "SOFTWARE_TEST_FIXTURE"}]}))
    (root / "static/index.html").write_text("<!doctype html><html>SOFTWARE_TEST_FIXTURE</html>")
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
    (root / "PAYLOAD_MANIFEST.json").write_text(json.dumps({"schema": "szl.civilian.payload.v1", "files": files}))
    provider = FixtureProvider()
    owner = Observatory(root, tmp_path / "cache.sqlite3", provider)
    owner.cache.save("feeds", snapshot())
    return root, owner, provider


@pytest.fixture
def client(prepared):
    _, owner, _ = prepared
    app = FastAPI()
    # A fallback sentinel would expose a routing regression.
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT"])
    def sentinel(path: str):
        return {"unexpected_fallback": True}
    register(app, lambda: owner)
    return TestClient(app)


def test_namespace_before_fallback(client):
    response = client.get(API_PREFIX + "/health")
    assert response.status_code == 200
    assert response.json()["model_loaded"] is False
    assert "unexpected_fallback" not in response.json()


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"])
def test_no_mutation_methods(client, prepared, method):
    count = prepared[2].calls
    response = client.request(method, API_PREFIX + "/refresh")
    assert response.status_code == 405
    assert prepared[2].calls == count


@pytest.mark.parametrize("path", ["/execute", "/train", "/unknown", "/observe/ports", "/secrets"])
def test_no_unknown_authority(client, path):
    assert client.get(API_PREFIX + path).status_code == 404


@pytest.mark.parametrize("query", [
    "cves=https://example.org", "cves=CVE-2024-0001&command=run",
    "cves=CVE-2024-0001&cves=CVE-2024-0002", "cves=",
])
def test_bad_analysis_rejected(client, query):
    assert client.get(API_PREFIX + "/analyze?" + query).status_code == 400


def test_known_exploitation_before_estimate():
    result = rank(["CVE-2024-0002", "CVE-2024-0001", "CVE-2099-9999999"], snapshot())
    assert result["rows"][0]["cve"] == "CVE-2024-0001"
    assert result["rows"][0]["epss"]["epss"] == 0
    assert result["rows"][-1]["epss"] is None
    assert all(r["exposure"] == "UNKNOWN" for r in result["rows"])


def test_source_outage_not_absence():
    data = snapshot()
    data["kev"]["source"]["status"] = "UNAVAILABLE"
    assert rank(["CVE-2024-0001"], data)["rows"][0]["kev_status"] == "UNKNOWN"


def test_no_header_scope_expansion(client, prepared):
    assert client.get(API_PREFIX + "/observe/headers?target=127.0.0.1").status_code == 400
    assert client.get(API_PREFIX + "/observe/headers?target=a-11-oy.com&command=x").status_code == 400
    assert prepared[2].calls == 0


def test_header_cache_is_reused(client, prepared):
    for _ in range(3):
        assert client.get(API_PREFIX + "/observe/headers?target=a-11-oy.com").status_code == 200
    assert prepared[2].calls == 1


def test_weather_scope_and_real_zero_fixture(client):
    assert client.get(API_PREFIX + "/weather?area=ANY").status_code == 400
    response = client.get(API_PREFIX + "/weather?area=NY")
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_dry_plan_does_not_contact_a_provider(client, prepared):
    for scenario in ("cyber", "weather", "research"):
        for approval in ("true", "false"):
            response = client.get(API_PREFIX + f"/plan?scenario={scenario}&simulatedApproval={approval}&mode=dry-run")
            assert response.status_code == 200
            assert response.json()["external_calls"] == 0
            assert response.json()["executed"] is False
    assert prepared[2].calls == 0


def test_live_plan_rejected(client):
    assert client.get(API_PREFIX + "/plan?scenario=cyber&simulatedApproval=true&mode=execute").status_code == 400


def test_exact_static_manifest(client):
    assert client.get("/civilian/", follow_redirects=False).status_code == 200
    assert client.get("/civilian/unknown.js").status_code == 404
    assert client.post("/civilian/").status_code == 405


def test_runtime_static_tampering_fails(client, prepared):
    (prepared[0] / "static/index.html").write_text("tampered")
    assert client.get("/civilian/").status_code == 503


def test_manifest_tamper_rejected(prepared):
    root = prepared[0]
    (root / "data/estate.json").write_text("{}")
    with pytest.raises(ContractError):
        verify_package_manifest(root, root / "PAYLOAD_MANIFEST.json")


def test_budget_is_shared_and_bounded(tmp_path):
    first, second = PublicCache(tmp_path / "same.sqlite3"), PublicCache(tmp_path / "same.sqlite3")
    lease_owner = first.acquire("same")
    with pytest.raises(BusyError):
        second.acquire("same")
    first.acquire("two")
    first.acquire("three")
    with pytest.raises(BusyError):
        second.acquire("four")
    first.release("same", lease_owner)
    second.acquire("four")


def test_expired_worker_cannot_release_a_new_lease(tmp_path):
    cache = PublicCache(tmp_path / "leases.sqlite3")
    old_owner = cache.acquire("same")
    with cache.connect() as db:
        db.execute("UPDATE observation_leases SET expires=0 WHERE key='same'")
    new_owner = cache.acquire("same")
    assert new_owner != old_owner
    cache.release("same", old_owner)
    with pytest.raises(BusyError):
        cache.acquire("same")
    cache.release("same", new_owner)
    assert cache.acquire("same")


def test_cold_start_is_unavailable_not_a_fixture_observation(prepared, tmp_path):
    root, _, provider = prepared
    fresh = Observatory(root, tmp_path / "cold.sqlite3", provider)
    health = fresh.handle("health", {})
    assert health["source_states"] == {"kev": "UNAVAILABLE", "epss": "UNAVAILABLE"}
    assert fresh.get_feeds()["kev"]["entries"] == []
    assert fresh.get_feeds()["kev"]["source"]["fetched_at"] is None
    assert fresh.get_feeds()["kev"]["source"]["sha256"] is None
    assert provider.calls == 0


def test_health_uses_canonical_publisher_revision(prepared, monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    monkeypatch.setenv("A11OY_GIT_SHA", "unknown")
    assert prepared[1].handle("health", {})["source_revision"] == "a" * 40


def test_health_does_not_substitute_a_different_revision(prepared, monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", "unknown")
    monkeypatch.setenv("A11OY_GIT_SHA", "b" * 40)
    assert prepared[1].handle("health", {})["source_revision"] == "UNKNOWN"


def test_cache_does_not_grow_without_bound(tmp_path):
    cache = PublicCache(tmp_path / "cache.sqlite3")
    for i in range(110):
        cache.save(f"fixture:{i}", {"value": i})
    with cache.connect() as db:
        assert db.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 96


def test_failure_keeps_original_observation_time(prepared):
    _, owner, provider = prepared
    old = owner.get_feeds()["kev"]["source"]["fetched_at"]
    provider.fail = True
    result = owner.refresh(force=True)
    assert result["kev"]["source"]["status"] == "STALE"
    assert result["kev"]["source"]["fetched_at"] == old


def test_duplicate_registration_does_not_duplicate_routes(prepared):
    app = FastAPI()
    register(app, lambda: prepared[1])
    count = len(app.routes)
    register(app, lambda: prepared[1])
    assert len(app.routes) == count


def test_corrupt_startup_never_falls_back_to_spa():
    app = FastAPI()
    def broken():
        raise ContractError("SOFTWARE_TEST_INTEGRITY_FAILURE")
    register(app, broken)
    with TestClient(app) as client:
        assert client.get("/civilian/").status_code == 503
        assert client.get(API_PREFIX + "/health").status_code == 503


def test_unlisted_manifest_files_fail(prepared):
    root = prepared[0]
    (root / "static/unlisted.js").write_text("unlisted")
    with pytest.raises(ContractError):
        verify_package_manifest(root, root / "PAYLOAD_MANIFEST.json")


def test_request_body_not_accepted(client):
    assert client.request("GET", API_PREFIX + "/health", content=b"{}").status_code == 400


def test_non_ascii_cve_rejected():
    with pytest.raises(ValueError):
        feeds.valid_cves(["CVE-٢٠٢٤-٠٠٠١"])


@pytest.mark.parametrize("value", [True, False, "NaN", "Inf", -1, 1.01])
def test_invalid_probability_rejected(value):
    with pytest.raises(ValueError):
        feeds.probability(value)


def test_health_and_plan_do_not_refresh_sources(client, prepared):
    assert client.get(API_PREFIX + "/health").status_code == 200
    assert prepared[2].calls == 0
    assert client.get(API_PREFIX + "/plan?scenario=weather&simulatedApproval=false&mode=dry-run").status_code == 200
    assert prepared[2].calls == 0
