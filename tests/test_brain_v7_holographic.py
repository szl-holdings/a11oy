from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from brain_v7_holographic import (
    AUTHORITY,
    ANATOMY_ORIGIN,
    BrainV7ProxyError,
    FixedBrainV7Proxy,
    create_brain_v7_router,
    validate_payload,
)


REVISION = "a" * 40
DIGEST = "b" * 64
CANDIDATE_SET = "c" * 64


def handle(*, kind: str = "attributed-formula", repository: str = "szl-holdings/szl-formulas") -> dict:
    return {
        "nodeId": "frontier:" + "1" * 32,
        "title": "Fisher-Rao information geometry",
        "sha256": DIGEST,
        "repository": repository,
        "revision": REVISION,
        "path": "atlas/formula-atlas.v1.json",
        "kind": kind,
        "admission": "REFERENCE_AND_CONSTRAINT_INPUT_ONLY",
        "candidateState": "DISCOVERED_REVIEW_REQUIRED",
        "contentAccess": "HANDLES_ONLY",
        "quantDomain": "information_geometry",
    }


def payload(*, include_handles: bool = True) -> dict:
    return {
        "schema": "szl.anatomy.frontier-handles/v1",
        "state": "REVIEW_REQUIRED",
        "ready": True,
        "candidate_count": 1,
        "candidate_set_sha256": CANDIDATE_SET,
        "content_access": "HANDLES_ONLY",
        "handles": [handle()] if include_handles else [],
        "scores": [1.0] if include_handles else [],
        "training_authority": "NONE",
        "promotion_authority": "NONE",
        "execution_authority": "NONE",
    }


def test_validate_payload_accepts_exact_handles_only_state() -> None:
    result = validate_payload("frontier", payload())
    assert result["state"] == "REVIEW_REQUIRED"
    assert result["handles"][0]["contentAccess"] == "HANDLES_ONLY"


def test_validate_payload_rejects_candidate_content() -> None:
    value = payload()
    value["handles"][0]["content"] = "must not cross the public boundary"
    with pytest.raises(BrainV7ProxyError, match="exposed candidate content"):
        validate_payload("frontier", value)


def test_validate_payload_rejects_promotion_and_execution_authority() -> None:
    promoted = payload()
    promoted["handles"][0]["candidateState"] = "PROMOTED"
    with pytest.raises(BrainV7ProxyError, match="candidate state was promoted"):
        validate_payload("frontier", promoted)

    executable = payload()
    executable["execution_authority"] = "GRANTED"
    with pytest.raises(BrainV7ProxyError, match="grants execution_authority"):
        validate_payload("frontier", executable)


def test_proxy_caches_fixed_plane_and_emits_source_digest() -> None:
    calls: list[str] = []

    def fetcher(name: str) -> dict:
        calls.append(name)
        return payload()

    proxy = FixedBrainV7Proxy(fetcher, ttl_seconds=60, clock=lambda: 10.0)
    first = proxy.get("frontier")
    second = proxy.get("frontier")
    assert calls == ["frontier"]
    assert first == second
    assert first is not second
    assert first["source_origin"] == ANATOMY_ORIGIN
    assert first["authority"] == AUTHORITY
    assert len(first["payload_sha256"]) == 64
    assert '"content"' not in json.dumps(first).lower()


def test_unknown_plane_is_not_caller_redirectable() -> None:
    proxy = FixedBrainV7Proxy(lambda _name: payload())
    with pytest.raises(BrainV7ProxyError, match="unknown fixed route"):
        proxy.get("https://example.com/private")


def test_router_exposes_contract_and_same_origin_envelopes() -> None:
    def fetcher(name: str) -> dict:
        result = payload(include_handles=name != "health")
        if name == "health":
            result["schema"] = "szl.anatomy.frontier-health/v1"
        return result

    app = FastAPI()
    app.include_router(create_brain_v7_router(FixedBrainV7Proxy(fetcher)))
    client = TestClient(app)

    contract = client.get("/api/a11oy/v1/holographic/brain-v7/contract")
    assert contract.status_code == 200
    contract_body = contract.json()
    assert contract_body["upstream_origin"] == ANATOMY_ORIGIN
    assert contract_body["public_content_access"] == "HANDLES_ONLY"
    assert contract_body["locked_proven_count"] == 8
    assert contract_body["f_number_mapping"] == "UNKNOWN_NOT_INFERRED"
    assert contract_body["lambda"] == "CONJECTURE_1"
    assert contract_body["authority"] == AUTHORITY

    for plane in ("health", "frontier", "formulas", "quant", "ouroboros"):
        response = client.get(f"/api/a11oy/v1/holographic/brain-v7/{plane}")
        assert response.status_code == 200
        body = response.json()
        assert body["plane"] == plane
        assert body["source_origin"] == ANATOMY_ORIGIN
        assert body["authority"] == AUTHORITY
        assert '"content"' not in response.text.lower()


def test_router_fails_closed_when_source_is_unavailable() -> None:
    def failed(_name: str) -> dict:
        raise BrainV7ProxyError("unavailable")

    app = FastAPI()
    app.include_router(create_brain_v7_router(FixedBrainV7Proxy(failed)))
    response = TestClient(app).get(
        "/api/a11oy/v1/holographic/brain-v7/frontier"
    )
    assert response.status_code == 503
    body = response.json()
    assert body["state"] == "UNAVAILABLE"
    assert body["payload"]["handles"] == []
    assert body["payload"]["content_access"] == "HANDLES_ONLY"
    assert body["authority"] == AUTHORITY


def test_holographic_shell_loads_exactly_one_local_brain_v7_bundle() -> None:
    html = Path("static/3d/holographic.html").read_text(encoding="utf-8")
    assert html.count('data-szl-brain-v7="style"') == 1
    assert html.count('data-szl-brain-v7="script"') == 1
    assert 'href="/static/3d/brain-v7.css"' in html
    assert 'src="/static/3d/brain-v7.js"' in html


def test_holographic_assets_are_same_origin_mobile_and_accessible() -> None:
    script = Path("static/3d/brain-v7.js").read_text(encoding="utf-8")
    style = Path("static/3d/brain-v7.css").read_text(encoding="utf-8")
    assert "https://" not in script
    assert "http://" not in script
    assert 'credentials: "same-origin"' in script
    assert 'redirect: "error"' in script
    assert "CONTENT_BOUNDARY_VIOLATION" in script
    assert "aria-modal" in script
    assert "prefers-reduced-motion" in script
    assert "env(safe-area-inset-bottom)" in style
    assert "@media (max-width: 640px)" in style
    assert "@media (forced-colors: active)" in style
    assert "@media (prefers-reduced-motion: reduce)" in style


def test_runtime_installs_brain_v7_router_once() -> None:
    candidate_files = [
        path
        for path in Path(".").glob("*.py")
        if path.name != "brain_v7_holographic.py"
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in candidate_files)
    assert combined.count("install_brain_v7_holographic_routes(") == 1
    assert "from brain_v7_holographic import install_brain_v7_holographic_routes" in combined
