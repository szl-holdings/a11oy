#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
from fastapi.testclient import TestClient


PUBLISHER = Path("scripts/hf_publish_vertical_flagships_v4_impl.py")
COMPATIBILITY_PATHS = (
    "/healthz",
    "/api/live",
    "/api/source",
    "/api/build-info",
    "/.well-known/szl-source.json",
)


def _publisher_literals() -> dict[str, str]:
    tree = ast.parse(PUBLISHER.read_text(encoding="utf-8"))
    values: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in {"APP", "SENTRA_PROXY_ROUTES"}:
            values[target.id] = ast.literal_eval(node.value)
    assert set(values) == {"APP", "SENTRA_PROXY_ROUTES"}
    return values


def _config() -> dict[str, Any]:
    return {
        "slug": "sentra",
        "title": "Sentra",
        "vertical": "ASSURANCE",
        "product_source": "https://github.com/szl-holdings/szl-defensive-control-plane",
        "source_repository": "szl-holdings/a11oy",
        "source_revision": "a" * 40,
        "workflow_run_id": 123,
        "hf_repository": "SZLHOLDINGS/sentra",
        "artifact_set_sha256": "b" * 64,
        "upstream": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/vert/cyber/feed",
        "assurance_upstream": "https://szlholdings-a11oy.hf.space",
        "public_experience": "4.0.0",
    }


def _load_generated_app(tmp_path: Path, source: str) -> tuple[TestClient, dict[str, Any]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    index = "<main>compatibility</main>"
    panels = "<main>domain panels</main>"
    config = _config()
    config["landing_sha256"] = hashlib.sha256(index.encode("utf-8")).hexdigest()
    config["panels_sha256"] = hashlib.sha256(panels.encode("utf-8")).hexdigest()
    config["forge"] = None
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (tmp_path / "index.html").write_text(index, encoding="utf-8")
    (tmp_path / "panels.html").write_text(panels, encoding="utf-8")
    namespace: dict[str, Any] = {"__name__": "sentra_generated_test"}
    previous = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        exec(compile(source, "generated-sentra-app.py", "exec"), namespace)
    finally:
        os.chdir(previous)
    namespace["hf_revision"] = lambda: "c" * 40
    return TestClient(namespace["app"]), namespace


class _FeedResponse:
    status_code = 200
    is_success = True
    headers = {"content-type": "application/json"}
    text = '{"evidence":"MEASURED"}'

    @staticmethod
    def json() -> dict[str, str]:
        return {"evidence": "MEASURED"}


def test_sentra_overlay_preserves_five_compatibility_response_bytes(tmp_path: Path) -> None:
    literals = _publisher_literals()
    base_client, base_ns = _load_generated_app(tmp_path / "base", literals["APP"])
    sentra_client, sentra_ns = _load_generated_app(
        tmp_path / "sentra", literals["APP"] + literals["SENTRA_PROXY_ROUTES"]
    )
    deterministic_httpx = SimpleNamespace(get=lambda *args, **kwargs: _FeedResponse())
    deterministic_time = SimpleNamespace(time=lambda: 100.0)
    for namespace in (base_ns, sentra_ns):
        namespace["httpx"] = deterministic_httpx
        namespace["time"] = deterministic_time

    for path in COMPATIBILITY_PATHS:
        before = base_client.get(path)
        after = sentra_client.get(path)
        assert before.status_code == after.status_code == 200
        assert before.headers["content-type"] == after.headers["content-type"]
        assert before.content == after.content, path


class _ProxyClient:
    def __init__(
        self,
        calls: list[tuple[str, str, dict[str, Any]]],
        *,
        fail: bool = False,
        html: bool = False,
        malformed: bool = False,
        non_object: bool = False,
        invalid_contract: bool = False,
        error_status: bool = False,
        oversized: bool = False,
        **_: Any,
    ):
        self.calls = calls
        self.fail = fail
        self.html = html
        self.malformed = malformed
        self.non_object = non_object
        self.invalid_contract = invalid_contract
        self.error_status = error_status
        self.oversized = oversized

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    def stream(self, method: str, url: str, **kwargs: Any) -> "_ProxyStream":
        self.calls.append((method, url, kwargs))
        return _ProxyStream(self, method, url)


class _ProxyStream:
    def __init__(self, client: _ProxyClient, method: str, url: str):
        self.client = client
        self.method = method
        self.url = url
        self.status_code = 200
        self.is_success = True
        self.headers = {"content-type": "application/json"}
        self.content = b""

    async def __aenter__(self) -> "_ProxyStream":
        request = httpx.Request(self.method, self.url)
        if self.client.fail:
            raise httpx.ConnectError("offline", request=request)
        if self.client.html:
            self.headers = {"content-type": "text/html"}
            self.content = b"<html>catch-all</html>"
        elif self.client.malformed:
            self.content = b'{"broken":'
        elif self.client.non_object:
            self.content = b"[]"
        elif self.client.invalid_contract:
            self.content = b'{"status":"ok"}'
        elif self.client.error_status:
            self.status_code = 503
            self.is_success = False
            self.content = b'{"status":"UNAVAILABLE"}'
        elif self.client.oversized:
            self.content = b'{"blob":"' + b"x" * 1_000_001 + b'"}'
        else:
            self.content = (
                b'{"decision":"deny","fail_closed":true,"source":"canonical-a11oy"}'
                if self.method == "POST"
                else b'{"chain_verified":true,"source":"canonical-a11oy"}'
            )
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def aiter_bytes(self):
        for offset in range(0, len(self.content), 64 * 1024):
            yield self.content[offset : offset + 64 * 1024]


def _proxy_httpx(calls: list[tuple[str, str, dict[str, Any]]], **mode: bool) -> Any:
    return SimpleNamespace(
        AsyncClient=lambda **kwargs: _ProxyClient(calls, **mode, **kwargs),
        RequestError=httpx.RequestError,
    )


def test_sentra_gate_and_yawar_are_transparent_canonical_proxies(tmp_path: Path) -> None:
    literals = _publisher_literals()
    client, namespace = _load_generated_app(
        tmp_path, literals["APP"] + literals["SENTRA_PROXY_ROUTES"]
    )
    calls: list[tuple[str, str, dict[str, Any]]] = []
    namespace["httpx"] = _proxy_httpx(calls)

    gate = client.post("/api/sentra/gate", json={"action": {"value": "read_config"}})
    assert gate.status_code == 200
    assert gate.content == b'{"decision":"deny","fail_closed":true,"source":"canonical-a11oy"}'
    assert calls[0] == (
        "POST",
        "https://szlholdings-a11oy.hf.space/api/a11oy/v1/immune/verdict",
        {"json": {"action": {"value": "read_config"}}},
    )

    yawar = client.post("/api/sentra/yawar/verify", json={"ignored": "no local verifier"})
    assert yawar.status_code == 200
    assert yawar.content == b'{"chain_verified":true,"source":"canonical-a11oy"}'
    assert calls[1] == (
        "GET",
        "https://szlholdings-a11oy.hf.space/api/a11oy/v1/immune/verify",
        {},
    )

    planes = client.get("/api/sentra/planes")
    assert planes.status_code == 200
    body = planes.json()
    assert body["state"] == "DECLARED"
    assert body["role"] == "sole-assurance-command"
    assert body["compatibility_routes"] == list(COMPATIBILITY_PATHS)


def test_sentra_proxy_fails_closed_on_invalid_upstream_contracts(tmp_path: Path) -> None:
    literals = _publisher_literals()
    source = literals["APP"] + literals["SENTRA_PROXY_ROUTES"]

    offline_client, offline_ns = _load_generated_app(tmp_path / "offline", source)
    offline_calls: list[tuple[str, str, dict[str, Any]]] = []
    offline_ns["httpx"] = _proxy_httpx(offline_calls, fail=True)
    offline = offline_client.post("/api/sentra/gate", json={"action": "read_config"})
    assert offline.status_code == 502
    assert offline.json()["status"] == "UNAVAILABLE"
    assert offline.json()["data"] is None

    html_client, html_ns = _load_generated_app(tmp_path / "html", source)
    html_calls: list[tuple[str, str, dict[str, Any]]] = []
    html_ns["httpx"] = _proxy_httpx(html_calls, html=True)
    html = html_client.post("/api/sentra/yawar/verify")
    assert html.status_code == 502
    assert html.headers["content-type"].startswith("application/json")
    assert html.json()["status"] == "UNAVAILABLE"
    assert html.json()["upstream_content_type"] == "text/html"
    assert "catch-all" not in html.text

    malformed_client, malformed_ns = _load_generated_app(tmp_path / "malformed", source)
    malformed_calls: list[tuple[str, str, dict[str, Any]]] = []
    malformed_ns["httpx"] = _proxy_httpx(malformed_calls, malformed=True)
    malformed = malformed_client.post("/api/sentra/gate", json={"action": "read_config"})
    assert malformed.status_code == 502
    assert malformed.headers["content-type"].startswith("application/json")
    assert malformed.json()["status"] == "UNAVAILABLE"
    assert malformed.json()["upstream_json_status"] == "INVALID"
    assert "broken" not in malformed.text

    for mode, expected in (
        ({"non_object": True}, "OBJECT_REQUIRED"),
        ({"invalid_contract": True}, "VERDICT_CONTRACT_INVALID"),
        ({"error_status": True}, None),
        ({"oversized": True}, "RESPONSE_TOO_LARGE"),
    ):
        mode_name = next(iter(mode))
        mode_client, mode_ns = _load_generated_app(tmp_path / mode_name, source)
        mode_calls: list[tuple[str, str, dict[str, Any]]] = []
        mode_ns["httpx"] = _proxy_httpx(mode_calls, **mode)
        response = mode_client.post("/api/sentra/gate", json={"action": "read_config"})
        assert response.status_code == 502
        assert response.json()["status"] == "UNAVAILABLE"
        assert response.json()["data"] is None
        if expected is not None:
            assert response.json()["upstream_json_status"] == expected


def test_sentra_gate_bounds_and_validates_request_before_proxy(tmp_path: Path) -> None:
    literals = _publisher_literals()
    client, namespace = _load_generated_app(
        tmp_path, literals["APP"] + literals["SENTRA_PROXY_ROUTES"]
    )
    calls: list[tuple[str, str, dict[str, Any]]] = []
    namespace["httpx"] = _proxy_httpx(calls)

    for body in ({}, {"action": None}, {"action": {}}, {"action": "  "}):
        blocked = client.post("/api/sentra/gate", json=body)
        assert blocked.status_code == 400
        assert blocked.json() == {"status": "BLOCKED", "error": "ACTION_REQUIRED", "data": None}
    assert calls == []

    invalid = client.post(
        "/api/sentra/gate",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"] == "INVALID_JSON"

    too_large = client.post(
        "/api/sentra/gate",
        content=b'{"action":"' + b"x" * 1_000_001 + b'"}',
        headers={"content-type": "application/json"},
    )
    assert too_large.status_code == 413
    assert too_large.json()["error"] == "REQUEST_TOO_LARGE"
    assert calls == []
