# SPDX-License-Identifier: Apache-2.0
# Wave 30 Dev2 verification — sovereign_local wiring + honest registry + router status.
# Network-free: mocks _http_json so the node "responds live" offline.
import os
import sys
import json

# ensure repo root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.testclient import TestClient
import szl_llm_registry as reg


def _fresh_client():
    app = FastAPI()
    reg.register(app)
    return TestClient(app)


def test_no_env_all_stubs():
    for ev, _ in reg._PROVIDER_ENV_VARS:
        os.environ.pop(ev, None)
    os.environ.pop("SZL_LOCAL_LLM_URL", None)
    os.environ.pop("A11OY_CODE_LLM_KEY", None)
    c = _fresh_client()
    r = c.get("/api/a11oy/v1/llm/registry")
    assert r.status_code == 200, r.status_code
    d = r.json()
    assert d["wired_count"] == 0, d["wired_count"]
    assert all(b["honest_stub"] for b in d["badges"]), "expected all honest stubs"
    assert all(not b["wired"] for b in d["badges"]), "expected all wired=false"
    # sovereign health honest
    h = c.get("/api/a11oy/v1/llm/sovereign/health").json()
    assert h["env_present"] is False and h["live"] is False and h["honest_stub"] is True
    # router status: no keys, no local node
    rs = c.get("/api/a11oy/v1/llm/router/status").json()
    assert rs["provider_wired_count"] == 0, rs["provider_wired_count"]
    assert rs["any_cloud_key_present"] is False
    assert rs["local_nodes"][0]["env_present"] is False
    # route falls to stub
    rt = c.post("/api/a11oy/v1/llm/route", json={"prompt": "hi"}).json()
    assert "[HONEST STUB]" in rt["response"], rt["response"]
    print("PASS test_no_env_all_stubs: wired_count=0, all honest stubs")


def test_fake_keys_flip_wired():
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-FAKEKEY-000000000000"
    os.environ["OPENAI_API_KEY"] = "sk-openai-FAKEKEY-0000000000"
    try:
        c = _fresh_client()
        d = c.get("/api/a11oy/v1/llm/registry").json()
        assert d["wired_count"] >= 2, d["wired_count"]
        # anthropic-gated models must now be wired
        by = {b["model_id"]: b for b in d["badges"]}
        assert by["claude_sonnet_4_6"]["wired"] is True
        assert by["claude_sonnet_4_6"]["honest_stub"] is False
        assert by["gpt_5_4"]["wired"] is True
        # router status names present (never secret)
        rs = c.get("/api/a11oy/v1/llm/router/status").json()
        assert "anthropic" in rs["provider_keys_present"]
        assert "openai" in rs["provider_keys_present"]
        blob = json.dumps(rs)
        assert "FAKEKEY" not in blob, "SECRET LEAKED INTO ROUTER STATUS"
        print("PASS test_fake_keys_flip_wired: wired_count=%d, names-only, no secret leak"
              % d["wired_count"])
    finally:
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)


def test_sovereign_wired_with_mock_node():
    """Fake SZL_LOCAL_LLM_URL + mock the node call so it 'responds live' offline."""
    os.environ["SZL_LOCAL_LLM_URL"] = "https://gpu.a-11-oy.com"
    for ev, _ in reg._PROVIDER_ENV_VARS:
        os.environ.pop(ev, None)  # no cloud keys => offline preference path viable

    orig = reg._http_json

    def _mock_http_json(url, method="GET", body=None, timeout=4.0):
        if url.endswith("/api/tags"):
            return {"models": [{"name": "llama3.1:8b"}]}, None
        if url.endswith("/api/generate"):
            return {"response": "Sovereign local says: measured joules matter.",
                    "eval_count": 21}, None
        if url.endswith("/v1/models"):
            return {"data": [{"id": "llama3.1:8b"}]}, None
        return None, "unexpected url"

    reg._http_json = _mock_http_json
    try:
        c = _fresh_client()
        # sovereign health: env present + node live + model list real
        h = c.get("/api/a11oy/v1/llm/sovereign/health").json()
        assert h["env_present"] is True, h
        assert h["live"] is True, h
        assert "llama3.1:8b" in h["served_models"], h
        assert h["honest_stub"] is False, h
        # registry with probe=1: sovereign badge honest_stub clears
        d = c.get("/api/a11oy/v1/llm/registry?probe=1").json()
        sov = next(b for b in d["badges"] if b["model_id"] == "sovereign_local")
        assert sov["wired"] is True, sov
        assert sov["is_local"] is True, sov
        assert sov["env_used"] == "SZL_LOCAL_LLM_URL", sov
        assert d["wired_count"] >= 1, d["wired_count"]
        # route: explicit sovereign selection => REAL text, wired=true
        rt = c.post("/api/a11oy/v1/llm/route",
                    json={"prompt": "why sovereign?", "model_id": "sovereign_local"}).json()
        assert rt["model_selected"]["model_id"] == "sovereign_local", rt["model_selected"]
        assert rt["model_selected"]["wired"] is True, rt["model_selected"]
        assert rt["local"]["live"] is True, rt["local"]
        assert "Sovereign local says" in rt["response"], rt["response"]
        assert "[HONEST STUB]" not in rt["response"], rt["response"]
        # router status probe: local node live
        rs = c.get("/api/a11oy/v1/llm/router/status?probe=1").json()
        assert rs["local_nodes"][0]["live"] is True, rs["local_nodes"]
        assert "llama3.1:8b" in rs["local_nodes"][0]["served_models"], rs["local_nodes"]
        print("PASS test_sovereign_wired_with_mock_node: sovereign wired+live, REAL text")
    finally:
        reg._http_json = orig
        os.environ.pop("SZL_LOCAL_LLM_URL", None)


def test_sovereign_env_set_but_node_dead():
    """Env set but node unreachable => wired reflects env (registry) but route text is honest stub."""
    os.environ["SZL_LOCAL_LLM_URL"] = "http://127.0.0.1:1/nope"
    orig = reg._http_json
    reg._http_json = lambda url, method="GET", body=None, timeout=4.0: (None, "unreachable")
    try:
        c = _fresh_client()
        h = c.get("/api/a11oy/v1/llm/sovereign/health").json()
        assert h["env_present"] is True and h["live"] is False and h["honest_stub"] is True, h
        rt = c.post("/api/a11oy/v1/llm/route",
                    json={"prompt": "x", "model_id": "sovereign_local"}).json()
        assert rt["local"]["wired"] is False, rt["local"]
        assert "[HONEST STUB]" in rt["response"], rt["response"]
        print("PASS test_sovereign_env_set_but_node_dead: env present, node dead => honest stub")
    finally:
        reg._http_json = orig
        os.environ.pop("SZL_LOCAL_LLM_URL", None)


if __name__ == "__main__":
    test_no_env_all_stubs()
    test_fake_keys_flip_wired()
    test_sovereign_wired_with_mock_node()
    test_sovereign_env_set_but_node_dead()
    print("\nALL DEV2 CHECKS PASS")
