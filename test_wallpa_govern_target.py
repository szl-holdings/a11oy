# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory).
"""pytest suite for Wallpa govern/infer target resolution (loopback root-cause fix).

ADDITIVE ONLY · locked-8 untouched · Λ = Conjecture 1.
"""
from __future__ import annotations

import importlib

import szl_wallpa as wallpa


def _reset_env(monkeypatch):
    monkeypatch.delenv("A11OY_GOVERN_URL", raising=False)
    monkeypatch.delenv("A11OY_GOVERN_LOOPBACK", raising=False)


def test_default_target_is_external_public_endpoint(monkeypatch):
    """Default govern target is the EXTERNAL public endpoint, not loopback —
    loopback cannot reach the externally-listening brain from inside the Space."""
    _reset_env(monkeypatch)
    targets = wallpa._govern_targets()
    assert targets == [wallpa.DEFAULT_GOVERN_URL]
    assert targets[0].startswith("https://a-11-oy.com/")
    assert all("127.0.0.1" not in t for t in targets)


def test_loopback_is_opt_in_only(monkeypatch):
    """Loopback targets appear only when A11OY_GOVERN_LOOPBACK is opted in."""
    _reset_env(monkeypatch)
    monkeypatch.setenv("A11OY_GOVERN_LOOPBACK", "1")
    targets = wallpa._govern_targets()
    assert targets[0] == wallpa.DEFAULT_GOVERN_URL
    assert any("127.0.0.1:7860" in t for t in targets)
    assert any("127.0.0.1:8000" in t for t in targets)


def test_custom_govern_url_overrides_default(monkeypatch):
    _reset_env(monkeypatch)
    monkeypatch.setenv("A11OY_GOVERN_URL", "https://brain.example/api/a11oy/v1/govern/infer")
    assert wallpa._govern_targets() == ["https://brain.example/api/a11oy/v1/govern/infer"]


def test_unreachable_brain_returns_honest_unavailable(monkeypatch):
    """On unreachable brain Wallpa never fabricates — honest UNAVAILABLE."""
    _reset_env(monkeypatch)
    # point at an unroutable target so the call fails fast and deterministically
    monkeypatch.setenv("A11OY_GOVERN_URL", "http://127.0.0.1:1/api/a11oy/v1/govern/infer")
    out = wallpa._call_govern_infer("hello", timeout=0.5)
    assert out["decision"] == "UNAVAILABLE"
    assert "honest" in out["honest_note"].lower()


def test_governed_speak_accepts_prompt_alias(monkeypatch):
    """`text` is canonical; `prompt` is accepted as an ergonomic alias."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    _reset_env(monkeypatch)
    # unreachable brain → honest UNAVAILABLE, but the request must be ACCEPTED
    # (200, not 400) when only `prompt` is supplied.
    monkeypatch.setenv("A11OY_GOVERN_URL", "http://127.0.0.1:1/api/a11oy/v1/govern/infer")
    importlib.reload(wallpa)
    app = FastAPI()
    wallpa.register(app)
    client = TestClient(app)
    r = client.post("/api/a11oy/wallpa/governed-speak",
                    json={"prompt": "say hello", "include_audio": False})
    assert r.status_code == 200
    assert r.json()["govern_decision"] == "UNAVAILABLE"

    r400 = client.post("/api/a11oy/wallpa/governed-speak", json={})
    assert r400.status_code == 400
