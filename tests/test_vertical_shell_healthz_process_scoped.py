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
import json
import sys
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
