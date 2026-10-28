"""Focused source and route contracts for the A11oy wake-receipt repair.

The platform warm-flagships workflow already owns the caller contract. These
tests prove that the canonical A11oy source image contains the reviewed module,
that ``serve.py`` registers it before the fallback routes, and that the route
keeps its authentication and bounded receipt behavior when exercised in
isolation. No network, HF mutation, secret provisioning, or background loop is
performed here.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import time
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "szl_kernels_organ.py"
ENDPOINT = "/api/a11oy/v3/kernels/wake-receipt"
TOKEN = "wake-receipt-test-token-32-bytes-minimum"


class _Response:
    def __init__(self, content, status_code=200, headers=None):
        self.content = content
        self.status_code = status_code
        self.headers = {key.lower(): value for key, value in (headers or {}).items()}

    def json(self):
        return self.content


class _Request:
    def __init__(self, body, headers=None):
        self._body = body
        self.headers = {key.lower(): value for key, value in (headers or {}).items()}

    async def stream(self):
        yield self._body


class _App:
    def __init__(self):
        self.routes = {}

    def _route(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler

        return decorator

    def get(self, path):
        return self._route("GET", path)

    def post(self, path):
        return self._route("POST", path)

    def on_event(self, _event):
        return lambda handler: handler


def _framework_stubs():
    fastapi = types.ModuleType("fastapi")
    fastapi.__path__ = []
    responses = types.ModuleType("fastapi.responses")
    responses.JSONResponse = _Response
    responses.StreamingResponse = _Response
    fastapi.responses = responses
    starlette = types.ModuleType("starlette")
    starlette.__path__ = []
    requests = types.ModuleType("starlette.requests")
    requests.Request = _Request
    starlette.requests = requests
    return {
        "fastapi": fastapi,
        "fastapi.responses": responses,
        "starlette": starlette,
        "starlette.requests": requests,
    }


def _load_module():
    spec = importlib.util.spec_from_file_location("a11oy_wake_contract_module", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _payload():
    return {
        "source": "github-actions/warm-flagships",
        "repository": "szl-holdings/platform",
        "run": "123456789",
        "run_attempt": "1",
        "sha": "a" * 40,
        "event": "schedule",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _request(module, payload, token=None):
    body = json.dumps(payload).encode("utf-8")
    headers = {"content-type": "application/json", "content-length": str(len(body))}
    if token is not None:
        headers["authorization"] = f"Bearer {token}"
    return _Request(body, headers)


def test_source_wires_reviewed_module_before_fallback_and_into_image():
    serve_source = (ROOT / "serve.py").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    registration = serve_source.index("import szl_kernels_organ")
    proxy = serve_source.index('@app.api_route("/api/a11oy/{path:path}"')
    assert registration < proxy
    assert "_kernels.register(app, organ=\"a11oy\")" in serve_source
    assert any(
        line.startswith("COPY ") and "szl_kernels_organ.py" in line
        for line in dockerfile.splitlines()
    )
    assert MODULE_PATH.is_file()


def test_wake_receipt_requires_bearer_and_appends_one_bounded_entry(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setenv("SZL_CODEX_DIR", str(tmp_path))
    app = _App()
    with monkeypatch.context() as context:
        context.setitem(sys.modules, "fastapi", _framework_stubs()["fastapi"])
        context.setitem(sys.modules, "fastapi.responses", _framework_stubs()["fastapi.responses"])
        context.setitem(sys.modules, "starlette", _framework_stubs()["starlette"])
        context.setitem(sys.modules, "starlette.requests", _framework_stubs()["starlette.requests"])
        manager = module.register(app, organ="a11oy", wake_receipt_token=TOKEN)

    handler = app.routes[("POST", ENDPOINT)]
    denied = asyncio.run(handler(_request(module, _payload())))
    assert denied.status_code == 401
    assert manager.get("sign").codex.count() == 0

    accepted = asyncio.run(handler(_request(module, _payload(), TOKEN)))
    assert accepted.status_code == 200
    assert accepted.json()["ok"] is True
    assert accepted.json()["replay"] is False
    assert accepted.json()["entry_hash"] == accepted.json()["codex_head"]
    assert manager.get("sign").codex.count() == 1
    manager.get("sign").codex._conn.close()


def test_wake_receipt_fails_closed_without_server_secret(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setenv("SZL_CODEX_DIR", str(tmp_path))
    app = _App()
    stubs = _framework_stubs()
    monkeypatch.setitem(sys.modules, "fastapi", stubs["fastapi"])
    monkeypatch.setitem(sys.modules, "fastapi.responses", stubs["fastapi.responses"])
    monkeypatch.setitem(sys.modules, "starlette", stubs["starlette"])
    monkeypatch.setitem(sys.modules, "starlette.requests", stubs["starlette.requests"])
    manager = module.register(app, organ="a11oy", wake_receipt_token="")
    response = asyncio.run(app.routes[("POST", ENDPOINT)](_request(module, _payload(), TOKEN)))
    assert response.status_code == 503
    assert manager.get("sign").codex.count() == 0
    manager.get("sign").codex._conn.close()
