# SPDX-License-Identifier: Apache-2.0
"""Empty kernel bind stays UNKNOWN. Not locked-8. Not LIVE. Not ADMIT."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import organ_integrity as oi  # noqa: E402
import szl_organ_integrity as surface  # noqa: E402


def test_unknown_bind_does_not_paint_live_or_locked8() -> None:
    packed = oi.unknown_bind("szl-kernel-probe")
    blob = json.dumps(packed)
    assert packed["decision"] == "UNKNOWN"
    assert packed["honesty"] == "UNKNOWN"
    assert packed["live"] is False
    assert packed["locked_8"] is False
    assert packed["admit"] is False
    assert packed["certified_production_ready"] is False
    assert packed["halt_drone"] == "BLOCKED"
    assert packed["signer"] == "UNSIGNED-honest"
    assert packed["body"]["organs"] == []
    assert packed["body"]["live_count"] is None
    assert "5/5 LIVE" not in blob
    assert packed["body"]["locked_proven_as_probe_decision"] is False


def test_empty_map_is_not_a_silhouette() -> None:
    assert oi.wants_silhouette({}) is False
    assert oi.wants_silhouette({"seed": 11}) is False
    assert oi.wants_silhouette({"silhouette": True}) is True
    assert oi.wants_silhouette({"zero_heart": True}) is True


def test_http_empty_json_is_unknown(monkeypatch=None) -> None:
    try:
        from fastapi import FastAPI
        from starlette.testclient import TestClient
    except ImportError:
        return
    app = FastAPI()
    surface.register(app, ns="a11oy")
    client = TestClient(app)
    for path in (
        "/api/a11oy/v1/kernel/probe",
        "/api/kernel/probe",
        "/kernel/probe",
        "/api/a11oy/v1/organs/integrity",
    ):
        for method in ("GET", "POST"):
            if method == "POST":
                resp = client.post(path, json={})
            else:
                resp = client.get(path)
            assert resp.status_code == 200, (path, method, resp.status_code, resp.text[:200])
            body = resp.json()
            assert body["decision"] == "UNKNOWN", (path, method, body)
            assert body["honesty"] == "UNKNOWN"
            assert body.get("live") is False
            assert body.get("admit") is False
            inner = body.get("body") or {}
            assert inner.get("organs") == []
            assert inner.get("verdict") == "UNKNOWN"


def test_silhouette_opt_in_still_runs_fail_closed_demo() -> None:
    try:
        from fastapi import FastAPI
        from starlette.testclient import TestClient
    except ImportError:
        return
    app = FastAPI()
    surface.register(app, ns="a11oy")
    client = TestClient(app)
    resp = client.post("/api/a11oy/v1/organs/integrity", json={"silhouette": True})
    assert resp.status_code == 200
    inner = resp.json()["body"]
    assert inner["live_count"] == 5
    assert inner["proven_trust"] is False
    assert inner["energy"] == "UNAVAILABLE"

    blocked = client.post("/api/a11oy/v1/organs/integrity", json={"zero_heart": True})
    assert blocked.json()["body"]["blocked"] is True
    assert blocked.json()["body"]["organs"][1]["status"] == "DOWN"
