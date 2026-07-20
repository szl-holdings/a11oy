# SPDX-License-Identifier: Apache-2.0
"""Release-blocking provider honesty and durable-receipt tests.

Every network interaction is a fixture.  The suite never depends on a developer's
localhost, cloud credentials, or an external provider.
"""
from __future__ import annotations

import importlib
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_alloy_models as alloy
import szl_governed_infer as governed
import szl_llm_registry as registry


PROVIDER_ENV_NAMES = {name for name, _provider in registry._PROVIDER_ENV_VARS}
PROVIDER_ENV_NAMES.update({
    "A11OY_CODE_LLM_KEY",
    "A11OY_SOVEREIGN_GATEWAY_KEY",
    "A11OY_SOVEREIGN_GATEWAY_URL",
    "SZL_LOCAL_LLM_KEY",
    "SZL_LOCAL_LLM_MODEL",
    "SZL_LOCAL_LLM_URL",
    "SZL_SOVEREIGN_NODES",
})


@pytest.fixture
def clean_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    for name in PROVIDER_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    log_path = tmp_path / "provider-receipts.jsonl"
    monkeypatch.setenv("SZL_GOVERN_INFER_LOG", str(log_path))
    importlib.reload(governed)
    importlib.reload(registry)
    importlib.reload(alloy)
    yield registry, governed, alloy, log_path


def _client(reg) -> TestClient:
    app = FastAPI()
    reg.register(app)
    return TestClient(app)


def test_selected_model_reconciliation_is_exact_and_fail_closed(clean_runtime):
    reg, _gi, _alloy, _log = clean_runtime
    canonical = reg._SOVEREIGN_MODEL_TAG
    exact = reg._reconcile_sovereign_model(["other:latest", canonical])
    assert exact["selected_model"] == canonical
    assert exact["model_ready"] is True

    alias = reg._reconcile_sovereign_model(["szl1:latest", "other:latest"])
    assert alias["selected_model"] == "szl1:latest"
    assert alias["selection_basis"] == "declared SZL alias exact match"

    mismatch = reg._reconcile_sovereign_model(
        ["other:latest"], requested="szl-sovereign:latest")
    assert mismatch["selected_model"] is None
    assert mismatch["model_ready"] is False


def test_cloud_key_is_configured_not_operational(clean_runtime, monkeypatch):
    reg, _gi, _alloy, _log = clean_runtime
    monkeypatch.setenv("ANTHROPIC_API_KEY", "configured-test-value-not-a-real-key")
    client = _client(reg)

    status = client.get("/api/a11oy/v1/llm/router/status").json()
    anthropic = next(p for p in status["providers"]
                     if p["provider"] == "anthropic")
    assert anthropic["configured"] is True
    assert anthropic["authenticated"] is False
    assert anthropic["inference_receipted"] is False
    assert anthropic["operational"] is False
    assert anthropic["state"] == "CONFIGURED_UNVERIFIED"
    assert status["provider_configured_count"] >= 1
    assert status["provider_operational_count"] == 0
    assert status["provider_wired_count"] == 0
    assert "configured-test-value" not in json.dumps(status)

    roster = client.get("/api/a11oy/v1/llm/registry").json()
    claude = next(m for m in roster["models"]
                  if m["model_id"] == "claude_sonnet_4_6")
    assert claude["configured"] is True
    assert claude["wired"] is False
    assert claude["honest_stub"] is True
    assert claude["state"] == "CONFIGURED_UNVERIFIED"


def test_registry_alias_counts_and_boot_count_are_not_stale(clean_runtime):
    reg, _gi, all_models, _log = clean_runtime
    report = all_models.unify_into_registry()
    assert report["alloy_total"] == 10
    assert report["registry_total_after"] == 21
    client = _client(reg)
    roster = client.get("/api/a11oy/v1/llm/registry").json()

    assert roster["registry_record_count"] == 21
    assert roster["unique_backend_count"] == 20
    assert roster["alias_groups"] == [{
        "backend_id": "szl-sovereign-local",
        "aliases": ["sovereign_local"],
        "record_count": 2,
        "backend_count": 1,
    }]
    assert "7 models across 5 tiers" not in inspect.getsource(reg._seed_forum)


def test_alloy_catalog_never_clears_stub_from_weights_alone(
        clean_runtime, monkeypatch):
    reg, _gi, all_models, _log = clean_runtime
    monkeypatch.setattr(all_models, "backend_available", lambda: False)
    all_models.unify_into_registry()
    client = _client(reg)
    roster = client.get("/api/a11oy/v1/llm/registry").json()
    open_weight = [m for m in roster["models"] if m.get("open_weight")]
    assert len(open_weight) == len(all_models.ALLOY_ROSTER)
    assert all(m["honest_stub"] is True for m in open_weight)
    assert all(m["operational"] is False for m in open_weight)
    assert all(not m.get("runtime_available", False) for m in open_weight)


def test_real_generation_creates_durable_receipt_and_survives_restart(
        clean_runtime, monkeypatch):
    reg, gi, _alloy, log_path = clean_runtime
    canonical = reg._SOVEREIGN_MODEL_TAG
    monkeypatch.setenv("SZL_LOCAL_LLM_URL", "https://gpu.fixture.invalid/v1")
    monkeypatch.setenv("SZL_LOCAL_LLM_MODEL", canonical)
    calls: list[tuple[str, str]] = []

    def fixture_http(url, method="GET", body=None, timeout=4.0):
        calls.append((method, url))
        if url.endswith("/api/tags"):
            return {"models": [{"name": canonical}]}, None
        if url.endswith("/api/generate"):
            request = json.loads(body.decode("utf-8"))
            assert request["model"] == canonical
            return {"response": "fixture model output", "eval_count": 7}, None
        if url.endswith("/v1/models"):
            return {"data": [{"id": canonical}]}, None
        return None, "unexpected fixture URL"

    monkeypatch.setattr(reg, "_http_json", fixture_http)
    client = _client(reg)
    response = client.post(
        "/api/a11oy/v1/llm/route",
        json={"model_id": "szl-sovereign-local", "prompt": "receipt me"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "fixture model output"
    assert body["generated"] is True
    assert body["inference_receipted"] is True
    assert body["operational"] is True
    assert body["label"] == "LIVE_RECEIPTED"
    assert any(url.endswith("/api/generate") for _method, url in calls)

    before = gi.inference_receipt_status(canonical)
    assert before["successful_receipt_count"] == 1
    assert before["chain_ok"] is True
    assert log_path.is_file()

    # A separate interpreter is a real process restart, not an in-memory reload.
    env = dict(os.environ)
    env["SZL_GOVERN_INFER_LOG"] = str(log_path)
    restart = subprocess.check_output(
        [sys.executable, "-c",
         "import json,szl_governed_infer as g; "
         f"print(json.dumps(g.inference_receipt_status({canonical!r})))"],
        cwd=str(Path(__file__).resolve().parents[1]), env=env, text=True,
    )
    after = json.loads(restart)
    assert after["successful_receipt_count"] == 1
    assert after["inference_receipted"] is True
    assert after["chain_ok"] is True

    health = client.get("/api/a11oy/v1/llm/sovereign/health").json()
    assert health["selected_model"] == canonical
    assert health["inference_receipted"] is True
    assert health["operational"] is True
    assert health["wired"] is True


def test_model_mismatch_never_generates_or_receipts(clean_runtime, monkeypatch):
    reg, gi, _alloy, _log = clean_runtime
    monkeypatch.setenv("SZL_LOCAL_LLM_URL", "https://gpu.fixture.invalid/v1")
    monkeypatch.setenv("SZL_LOCAL_LLM_MODEL", reg._SOVEREIGN_MODEL_TAG)
    generated = []

    def fixture_http(url, method="GET", body=None, timeout=4.0):
        if url.endswith("/api/tags"):
            return {"models": [{"name": "unrelated:latest"}]}, None
        if url.endswith("/api/generate"):
            generated.append(url)
            return {"response": "must not be reached"}, None
        return None, "not available"

    monkeypatch.setattr(reg, "_http_json", fixture_http)
    client = _client(reg)
    body = client.post(
        "/api/a11oy/v1/llm/route",
        json={"model_id": "szl-sovereign-local", "prompt": "do not run"},
    ).json()
    assert generated == []
    assert body["generated"] is False
    assert body["inference_receipted"] is False
    assert body["operational"] is False
    assert body["label"] == "REACHABLE_MODEL_MISMATCH"
    assert gi.inference_receipt_status()["total_receipt_count"] == 0


def test_alloy_success_is_receipted_before_operational(
        clean_runtime, monkeypatch):
    _reg, gi, all_models, _log = clean_runtime
    demo_id = next(m["model_id"] for m in all_models.ALLOY_ROSTER
                   if m["tier_band"] == "demo_cpu")
    monkeypatch.setattr(
        all_models, "_local_generate",
        lambda prompt, max_tokens=256: {
            "served_locally": True,
            "text": "real fixture llama.cpp output",
            "backend": "llama.cpp",
            "tower_side": False,
        },
    )
    out = all_models.alloy_governed_suggest(
        "alloy receipt", force_tier="demo_cpu")
    assert out["served_locally"] is True
    assert out["inference_receipted"] is True
    assert out["operational"] is True
    assert out["honest_stub"] is False
    assert gi.inference_receipt_status(demo_id)["successful_receipt_count"] == 1


def test_release_artifacts_depend_on_provider_gate():
    workflow = (Path(__file__).resolve().parents[1]
                / ".github" / "workflows" / "release.yml").read_text("utf-8")
    assert "provider-gate:" in workflow
    assert "tests/test_provider_release_gate.py" in workflow
    assert "test_provider_http.py" in workflow
    assert "attach:\n    needs: [provider-gate, public-claim-gate]" in workflow
    assert "sign-receipts:\n    needs: [provider-gate, public-claim-gate]" in workflow
