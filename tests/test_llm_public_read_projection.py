# SPDX-License-Identifier: Apache-2.0
"""Anonymous mirror/forum GETs are catalog views, not runtime or receipt proof."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_llm_registry as registry


def _client() -> TestClient:
    app = FastAPI()
    registry.register(app)
    return TestClient(app)


def _unexpected(*args, **kwargs):
    raise AssertionError("anonymous GET invoked a runtime provider or weight loader")


def test_mirror_is_declared_catalog_and_never_loads_or_probes(monkeypatch):
    monkeypatch.setenv("SZL_LOCAL_LLM_URL", "http://10.1.2.3:11434/v1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "private-test-token")
    monkeypatch.setenv("A11OY_ALLOY_GGUF", "C:/private/model.gguf")
    monkeypatch.setattr(registry, "_enrich_model", _unexpected)
    monkeypatch.setattr(registry, "_inference_receipt_state", _unexpected)
    monkeypatch.setattr(registry, "sovereign_probe", _unexpected)
    monkeypatch.setattr(registry, "_api_key_wired", _unexpected)
    monkeypatch.setitem(sys.modules, "szl_alloy_models", SimpleNamespace(backend_available=_unexpected))

    response = _client().get("/api/a11oy/v1/llm/ecosystem-mirror")

    assert response.status_code == 200
    body = response.json()
    assert body["catalog_evidence_class"] == "DECLARED"
    assert body["runtime_state"] == "UNKNOWN"
    assert body["public_projection"] is True
    assert body["total_models"] == len(registry.MODEL_REGISTRY)
    for organ in body["ecosystem"].values():
        assert organ["receipt_ingest_path"].startswith("/api/a11oy/")
        for model in organ["models"]:
            assert set(model) == {"model_id", "tier", "evidence_class"}
            assert model["evidence_class"] == "DECLARED"
    serialized = response.text
    for forbidden in (
        "10.1.2.3", "private-test-token", "C:/private", "base_url",
        "api_base", "local_models", "selected_model", "receipt_state",
        "receipt_hash", "prompt_preview", "operational", "runtime_available",
    ):
        assert forbidden not in serialized


def test_mirror_fails_closed_on_malformed_catalog_identity(monkeypatch):
    monkeypatch.setattr(registry, "MODEL_REGISTRY", [
        {"model_id": "http://10.1.2.3/private", "tier": 1, "ecosystem_mirror": ["policy"]}
    ])

    response = _client().get("/api/a11oy/v1/llm/ecosystem-mirror")

    assert response.status_code == 503
    assert response.json() == {"state": "UNAVAILABLE", "reason": "invalid_catalog"}
    assert "10.1.2.3" not in response.text


def test_mirror_drops_runtime_fields_from_valid_catalog_entry(monkeypatch):
    monkeypatch.setattr(registry, "MODEL_REGISTRY", [{
        "model_id": "catalog-id", "tier": 1, "ecosystem_mirror": ["policy"],
        "operator_mirrored": True, "base_url": "http://10.1.2.3:11434/v1",
        "local_models": ["served-private-model"],
        "receipt_state": {"inference_receipted": True,
                          "latest_receipt_hash": "private-receipt-hash"},
        "prompt_preview": "private-prompt", "operational": True,
    }])

    response = _client().get("/api/a11oy/v1/llm/ecosystem-mirror")

    assert response.status_code == 200
    assert response.json()["ecosystem"]["policy"]["models"] == [
        {"model_id": "catalog-id", "tier": 1, "evidence_class": "DECLARED"}
    ]
    assert response.json()["runtime_state"] == "UNKNOWN"
    for forbidden in ("10.1.2.3", "served-private-model", "private-receipt-hash",
                      "private-prompt", "operational"):
        assert forbidden not in response.text


def test_forum_projects_only_bounded_non_receipt_records(monkeypatch):
    raw = [
        {"source": "a11oy", "event": "registry_boot", "ts": "private-time"},
        {
            "source": "operator", "ingested_by": "a11oy", "event": "route",
            "prompt_preview": "private-prompt", "model_id": "private-served-model",
            "receipt_state": {"operational": True, "latest_receipt_hash": "private-hash"},
            "base_url": "http://10.1.2.3:11434/v1", "token": "private-token",
        },
        {"source": "http://10.1.2.4", "event": "private-event", "payload": "private-payload"},
    ]
    monkeypatch.setattr(registry, "_FORUM_LOG", raw)
    monkeypatch.setattr(registry, "_forum_append", _unexpected)
    client = _client()

    response = client.get("/api/a11oy/v1/llm/forum?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["total_events"] == 3
    assert body["returned"] == 2
    assert body["receipt_verification"] == "UNAVAILABLE"
    assert body["public_projection"] is True
    assert body["events"] == [
        {"source": "other", "kind": "forum_record", "verification": "UNAVAILABLE"},
        {"source": "external", "kind": "forum_record", "verification": "UNAVAILABLE"},
    ]
    assert raw[1]["prompt_preview"] == "private-prompt"  # GET did not mutate the ring
    for forbidden in (
        "private-prompt", "private-served-model", "private-hash", "private-token",
        "10.1.2.3", "10.1.2.4", "private-event", "private-payload", "operational",
    ):
        assert forbidden not in response.text
    assert client.get("/api/a11oy/v1/llm/forum?limit=101").status_code == 422
    rejected = client.get("/api/a11oy/v1/llm/forum?source=http://10.1.2.4")
    assert rejected.status_code == 400
    assert "10.1.2.4" not in rejected.text
    assert client.get("/api/a11oy/v1/llm/forum?source=external").json()["returned"] == 1
