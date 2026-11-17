# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Retired brainserve routes cannot generate, forward, or mint a receipt."""
import socket
import urllib.request

import httpx
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import szl_brainserve as bs


@pytest.fixture(autouse=True)
def no_egress(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("retired brainserve attempted outbound transport")
    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def test_committed_default_and_override_are_metadata_only():
    cfg = bs.read_env(environ={})
    assert cfg["url"] == bs.DEFAULT_URL and cfg["model"] == bs.DEFAULT_MODEL
    assert cfg["source"] == "committed-default"
    cfg2 = bs.read_env(environ={bs.ENV_URL: "https://x", bs.ENV_MODEL: "m"})
    assert cfg2["url"] == "https://x" and cfg2["source"] == "operator-override"
    assert bs.probe(environ={bs.ENV_URL: "https://x"})["state"] == "RETIRED"


def _assert_retired(body):
    assert body["state"] == body["verdict"] == "RETIRED"
    assert body["label"] == bs.LBL_UNAVAILABLE
    for flag in ("ok", "measured", "answered", "operational", "inference_performed",
                 "receipt_emitted", "automatically_forwarded"):
        assert body[flag] is False
    assert "receipt" not in body and "answer_sample" not in body
    assert body["successor"]["path"] == "/api/a11oy/v1/atelier/cpu-lab/turn"
    assert body["successor"]["operator_authentication_required"] is True
    assert body["successor"]["public_share_acknowledged"] is True
    assert body["successor"]["declared"] == "PUBLIC"
    assert body["successor"]["grounding_required"] is True
    assert body["successor"]["ui"] == "/command-centre#cpu-work"


@pytest.mark.parametrize("handler", [bs.probe, bs.handle_serve, bs.handle_receipt])
def test_legacy_functions_never_call_model_or_emit_receipt(monkeypatch, handler):
    def forbidden(*args, **kwargs):
        pytest.fail("retired handler called model or receipt hook")
    monkeypatch.setattr(bs, "_call_model", forbidden)
    monkeypatch.setattr(bs, "content_receipt", forbidden)
    _assert_retired(handler())


def test_low_level_legacy_transport_is_inert():
    data, error = bs._call_model("https://example.invalid", "m", "private prompt")
    assert data is None and "RETIRED" in error
    assert "private prompt" not in error


@pytest.mark.parametrize("method,path,status", [
    ("GET", "/api/a11oy/v1/brain/serve/info", 200),
    ("GET", "/api/a11oy/v1/brain/brainserve/manifest", 200),
    ("GET", "/api/a11oy/v1/brain/serve", 410),
    ("HEAD", "/api/a11oy/v1/brain/serve", 410),
    ("POST", "/api/a11oy/v1/brain/serve/receipt", 410),
])
def test_registered_routes_are_inert(monkeypatch, method, path, status):
    def forbidden(*args, **kwargs):
        pytest.fail("route triggered generation or receipt emission")
    monkeypatch.setattr(bs, "_call_model", forbidden)
    monkeypatch.setattr(bs, "content_receipt", forbidden)
    app = FastAPI()
    bs.register(app)
    bs.register(app)
    assert len([r for r in app.router.routes if getattr(r, "path", None) == path]) == 1
    with TestClient(app) as client:
        for _ in range(2):
            response = client.request(method, path, content=b"private prompt",
                                      headers={"Authorization": "Bearer test-only"})
            assert response.status_code == status
            assert response.headers["cache-control"] == "no-store"
            assert "location" not in response.headers
            if method != "HEAD":
                body = response.json()
                assert body["state"] == "RETIRED"
                assert body["inference_performed"] is False
                assert body["receipt_emitted"] is False
                assert "receipt" not in body
                assert "private prompt" not in response.text


def test_unsigned_historical_receipt_helper_never_claims_output_signature():
    sample = {"label": bs.LBL_MEASURED,
              "provenance": {"output_signature_status": "UNSIGNED"}}
    first = bs.content_receipt(sample)
    second = bs.content_receipt(sample)
    assert first["content_sha256"] == second["content_sha256"]
    assert first["signed"] is False
    assert "does NOT sign the model" in first["note"]


def test_manifest_and_locked_math_unchanged():
    man = bs.handle_manifest()
    assert man["state"] == "RETIRED" and man["data_label"] == bs.LBL_MODELED
    assert all(man["honesty_invariants"].values())
    d = man["doctrine"]
    assert d["locked_proven"] == 8
    assert set(d["locked_set"]) == {"F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"}
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["adds_to_locked_8"] == 0 and d["admits_to_gradients"] == 0
    assert d["is_model_training"] is False


def test_selftest_passes_without_network():
    out = bs._selftest()
    assert out["ok"] is True and out["checks"] >= 5


def test_holographic_catalog_discloses_retired_brainserve():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "szl3d_holographic.py").read_text(encoding="utf-8")
    row = next(line for line in source.splitlines() if '"id": "brainserve"' in line)
    assert "RETIRED inference bridge" in row
    assert "reads never generate or mint receipts" in row
    assert "/command-centre#cpu-work" in row
    assert "on each read it POSTs" not in row
