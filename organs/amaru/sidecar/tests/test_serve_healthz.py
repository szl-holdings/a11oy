# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""Regression tests for the Hugging Face Space wrapper (deploy/huggingface/serve.py).

Part-A problems P05 + P02: a Space that boots green while its hero asset 404s
is a fake-green surface. serve.py adds an asset-presence preflight (refuses to
boot when a critical static asset is missing) and a /healthz probe that reports
the asset state. These tests pin that behaviour and guard the probe itself
against a regression: the /healthz body must be buildable without raising
(an earlier draft referenced an undefined name and would have crashed on every
call — a health endpoint that is itself unhealthy is exactly the trap the
probe exists to catch).

See warhacker/usb/WARHACKER_PROBLEM_SOLVER.md (P05, P02).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# deploy/huggingface lives two levels above this sidecar/tests/ file.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SERVE_DIR = _REPO_ROOT / "deploy" / "huggingface"


def _load_serve(monkeypatch, static_dir: Path, skip_preflight: bool = False):
    """Import deploy/huggingface/serve.py fresh against a given static dir."""
    monkeypatch.setenv("AMARU_STATIC_DIR", str(static_dir))
    if skip_preflight:
        monkeypatch.setenv("AMARU_SKIP_ASSET_PREFLIGHT", "1")
    else:
        monkeypatch.delenv("AMARU_SKIP_ASSET_PREFLIGHT", raising=False)
    monkeypatch.syspath_prepend(str(_SERVE_DIR))
    sys.modules.pop("serve", None)
    return importlib.import_module("serve")


def test_healthz_ok_when_api_alone(monkeypatch, tmp_path):
    """No static dir present -> valid API-alone deployment, status ok, HTTP 200.

    This also pins the probe against the undefined-name regression: building
    the response body must not raise.
    """
    serve = _load_serve(monkeypatch, tmp_path / "absent-static")
    client = TestClient(serve.app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["api_alone"] is True
    assert body["missing_assets"] == []


def test_healthz_degraded_lists_missing_assets(monkeypatch, tmp_path):
    """Static dir present but hero asset missing -> status degraded, asset listed.

    Preflight is skipped here so the module imports; the point of this test is
    that /healthz reports the degraded state rather than crashing or hiding it.
    """
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html></html>")
    serve = _load_serve(monkeypatch, static, skip_preflight=True)
    client = TestClient(serve.app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["api_alone"] is False
    assert any("amaru_hero.png" in p for p in body["missing_assets"])


def test_preflight_refuses_boot_when_hero_missing(monkeypatch, tmp_path):
    """The asset preflight must raise at import when a critical asset is absent.

    This is the loud, fail-closed behaviour that turns a silent 404ing hero
    into a deploy-time error before Warhacker, not during it.
    """
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html></html>")  # hero deliberately absent
    with pytest.raises(RuntimeError, match="critical asset"):
        _load_serve(monkeypatch, static, skip_preflight=False)


def test_preflight_passes_when_all_assets_present(monkeypatch, tmp_path):
    """With index.html and the hero present, the module imports and /healthz is ok."""
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html></html>")
    (static / "assets" / "amaru_hero.png").write_bytes(b"\x89PNG\r\n")
    serve = _load_serve(monkeypatch, static, skip_preflight=False)
    client = TestClient(serve.app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
