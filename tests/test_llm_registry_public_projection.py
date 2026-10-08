# SPDX-License-Identifier: Apache-2.0
"""Anonymous registry rows are bounded; internal routing retains full data."""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_dsse
import szl_governed_infer
import szl_llm_registry as registry


def _client() -> TestClient:
    app = FastAPI()
    registry.register(app)
    return TestClient(app)


def test_registry_list_probe_and_detail_do_not_publish_private_routing_data(monkeypatch):
    tunnel = "https://hidden-tunnel.example.invalid/v1"
    private_tag = "private-served-model-123"
    token = "private-token-123456789"
    canonical = registry._SOVEREIGN_MODEL_TAG
    monkeypatch.setenv("SZL_LOCAL_LLM_URL", tunnel)
    monkeypatch.setenv("SZL_LOCAL_LLM_MODEL", canonical)
    monkeypatch.setenv("A11OY_SOVEREIGN_GATEWAY_KEY", token)
    sovereign = registry._MODEL_BY_ID[registry._SOVEREIGN_BACKEND_ID]
    monkeypatch.setitem(sovereign, "notes", "secret-note 10.77.0.8")
    monkeypatch.setitem(sovereign, "api_base", "http://10.77.0.8:11434")
    monkeypatch.setitem(sovereign, "model_slug", "private-catalog-slug")
    cloud = registry._MODEL_BY_ID["claude_sonnet_4_6"]
    monkeypatch.setitem(cloud, "api_base", "https://private-cloud-endpoint.invalid")

    requests = []

    def metadata_only(url, *, method="GET", body=None, timeout=4.0):
        requests.append((method, url))
        assert method == "GET" and body is None
        if url.endswith("/api/tags"):
            return {"models": [{"name": canonical}, {"name": private_tag}]}, None
        return None, "unexpected metadata route"

    def forbidden(*_args, **_kwargs):
        raise AssertionError("anonymous GET attempted generation or receipt write")

    monkeypatch.setattr(registry, "_http_json", metadata_only)
    monkeypatch.setattr(registry, "sovereign_generate", forbidden)
    monkeypatch.setattr(szl_governed_infer, "_append", forbidden)
    monkeypatch.setattr(szl_governed_infer, "_maybe_dsse", forbidden)
    monkeypatch.setattr(szl_dsse, "sign_payload", forbidden)
    monkeypatch.setattr(registry, "_inference_receipt_state", lambda model="": {
        "inference_receipted": True,
        "successful_receipt_count": 1,
        "latest_receipt_hash": "historical-hash-123",
        "chain_ok": True,
    })

    # The private internal row still has the exact routing and probe data.
    internal = registry._enrich_model(sovereign, probe_local=True)
    assert internal["base_url"] == tunnel
    assert private_tag in internal["local_models"]
    assert internal["operational"] is True  # historical receipt + metadata, internally

    client = _client()
    for path in (
        "/api/a11oy/v1/llm/registry",
        "/api/a11oy/v1/llm/registry?probe=1",
        "/api/a11oy/v1/llm/registry/szl-sovereign-local",
        "/api/a11oy/v1/llm/registry/claude_sonnet_4_6",
    ):
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        serialized = json.dumps(body)
        for secret in (tunnel, "hidden-tunnel.example.invalid", "10.77.0.8",
                       private_tag, "private-catalog-slug",
                       "private-cloud-endpoint.invalid", token, "secret-note",
                       "historical-hash-123"):
            assert secret not in serialized
        for private_key in ("base_url", "api_base", "url", "local_models",
                            "served_models", "selected_model", "requested_model",
                            "env_used", "local_probe_note", "receipt_state"):
            assert '"%s"' % private_key not in serialized

    probed = client.get("/api/a11oy/v1/llm/registry?probe=1").json()
    model = next(m for m in probed["models"]
                 if m["model_id"] == registry._SOVEREIGN_BACKEND_ID)
    badge = next(b for b in probed["badges"]
                 if b["model_id"] == registry._SOVEREIGN_BACKEND_ID)
    for row in (model, badge, probed["sovereign"]):
        assert row["operational"] is False
        assert row["inference_receipted"] is False
        assert row["historical_inference_receipted"] is True
        assert row["receipt_binding"] == "UNKNOWN"
        assert row["label"] == "UNKNOWN"
    assert model["wired"] is False and badge["wired"] is False
    assert model["api_key_wired"] is False
    assert model["configured"] is True
    assert probed["wired_count"] == probed["operational_count"] == 0
    assert probed["inference_receipted_count"] == 0
    assert probed["historical_inference_receipted_count"] >= 1
    assert probed["sovereign"]["endpoint_reachable"] is True
    assert probed["sovereign"]["gpu_verified"] is False
    assert probed["sovereign"]["ownership_proof"] == "UNAVAILABLE"
    assert requests and all(method == "GET" for method, _ in requests)

    missing = client.get("/api/a11oy/v1/llm/registry/private-token-123456789")
    assert missing.status_code == 404
    assert token not in missing.text


def test_registry_catalog_keeps_cloud_configuration_separate_from_operation(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "configured-but-not-authenticated")
    client = _client()
    body = client.get("/api/a11oy/v1/llm/registry").json()
    model = next(m for m in body["models"] if m["model_id"] == "claude_sonnet_4_6")
    assert model["configured"] is True
    assert model["api_key_wired"] is True  # legacy config bit, not operation
    assert model["wired"] is False
    assert model["operational"] is False
    assert model["state"] == "CONFIGURED_UNVERIFIED"
    assert model["label"] == "UNKNOWN"
    assert "configured-but-not-authenticated" not in json.dumps(body)
