# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from routers import atelier_frontier as frontier

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "third-party" / "meta-success-intake-v1.md"
WEB = ROOT / "routers" / "atelier_frontier_web"


def test_inventory_is_complete_unique_and_conservative() -> None:
    items = frontier.REFERENCE_REPOSITORIES
    assert len(items) == 26
    assert len({item["name"] for item in items}) == 26
    permissive = [item for item in items if item["reuse_policy"] == "ADAPT_WITH_NOTICE"]
    assert [item["name"] for item in permissive] == ["GPU-Accelerated-ML-Pipeline"]
    assert permissive[0]["license_state"] == "VERIFIED_MIT"
    for item in items:
        if item["license_state"] != "VERIFIED_MIT":
            assert item["reuse_policy"] != "ADAPT_WITH_NOTICE"


def test_registry_derives_counts_and_snapshot_digest() -> None:
    first = frontier.build_registry()
    second = frontier.build_registry()
    inventory = first["source_inventory"]
    assert inventory["observed_public_repository_count"] == 26
    assert inventory["source_copy_used"] is False
    assert inventory["visual_assets_copied"] is False
    assert inventory["brand_identity_reused"] is False
    assert inventory["reuse_policy_counts"]["ADAPT_WITH_NOTICE"] == 1
    assert first["snapshot_sha256"] == second["snapshot_sha256"]
    lane = next(item for item in first["capability_lanes"] if item["id"] == "gpu_lab")
    assert lane["reference_count"] == 1
    assert lane["references"] == ["GPU-Accelerated-ML-Pipeline"]


def test_safety_is_hard_zero_and_no_effectors_are_bound() -> None:
    result = frontier.evaluate_candidate(
        evidence=100,
        repeatability=100,
        coverage=100,
        governance=100,
        safety=0,
        energy=100,
        energy_state="REPORTED",
    )
    assert result["decision"]["state"] == "DENIED"
    assert result["decision"]["reason"] == "SAFETY_GATE_FAILED"
    assert result["formula"]["score"] == 0
    assert result["decision"]["external_writes"] == "DISABLED"
    assert result["decision"]["effectors"] == []


def test_score_is_capped_and_fingerprint_is_deterministic() -> None:
    kwargs = dict(
        evidence=100,
        repeatability=100,
        coverage=100,
        governance=100,
        safety=1,
        energy=100,
        energy_state="REPORTED",
    )
    first = frontier.evaluate_candidate(**kwargs)
    second = frontier.evaluate_candidate(**kwargs)
    assert first["formula"]["score"] == frontier.TRUST_CEILING
    assert first["decision"]["state"] == "SANDBOX_CANDIDATE"
    assert first["derivation_fingerprint"]["sha256"] == second["derivation_fingerprint"]["sha256"]
    assert first["derivation_fingerprint"]["persisted"] is False
    assert first["energy"]["measured_claim_permitted"] is False


def test_unavailable_energy_is_ignored() -> None:
    low = frontier.evaluate_candidate(
        evidence=80, repeatability=80, coverage=80, governance=80,
        safety=1, energy=0, energy_state="UNAVAILABLE",
    )
    high = frontier.evaluate_candidate(
        evidence=80, repeatability=80, coverage=80, governance=80,
        safety=1, energy=100, energy_state="UNAVAILABLE",
    )
    assert low["formula"] == high["formula"]
    assert low["energy"]["score_used"] is None


def _app() -> FastAPI:
    app = FastAPI()

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def catchall(full_path: str) -> PlainTextResponse:
        return PlainTextResponse(f"catchall:{full_path}")

    frontier.register(app)
    return app


def test_routes_win_before_spa_and_register_idempotently() -> None:
    app = _app()
    paths = [getattr(route, "path", None) for route in app.router.routes]
    catchall = paths.index("/{full_path:path}")
    for path in (
        "/atelier/frontier",
        "/api/a11oy/v1/atelier/frontier/registry",
        "/api/a11oy/v1/atelier/frontier/evaluate",
    ):
        assert paths.index(path) < catchall
        route = next(route for route in app.router.routes if getattr(route, "path", None) == path)
        assert route.endpoint.__module__ == "routers.atelier_frontier"
        assert {"GET", "HEAD"}.issubset(route.methods)
    assert frontier.register(app)["state"] == "ALREADY_REGISTERED"


def test_live_surface_headers_assets_and_api_contract() -> None:
    with TestClient(_app()) as client:
        page = client.get("/atelier/frontier")
        head = client.head("/atelier/frontier")
        registry = client.get("/api/a11oy/v1/atelier/frontier/registry")
        denied = client.get("/api/a11oy/v1/atelier/frontier/evaluate?safety=0")
        allowed = client.get(
            "/api/a11oy/v1/atelier/frontier/evaluate"
            "?evidence=90&repeatability=90&coverage=90&governance=90"
            "&safety=1&energy_state=UNAVAILABLE"
        )
    assert page.status_code == 200
    assert 'data-szl-public-experience-v3="true"' in page.text
    assert "default-src 'none'" in page.headers["content-security-policy"]
    assert "__APP_ASSET_DIGEST__" not in page.text
    assert head.status_code == 200 and head.content == b""
    assert registry.json()["source_inventory"]["observed_public_repository_count"] == 26
    assert denied.json()["decision"]["state"] == "DENIED"
    assert allowed.json()["decision"]["state"] == "SANDBOX_CANDIDATE"


@pytest.mark.parametrize(
    "query,status",
    [
        ("safety=2", 422),
        ("evidence=101", 422),
        ("evidence=abc", 400),
        ("energy_state=MEASURED", 422),
        ("evidence=10&evidence=20", 400),
    ],
)
def test_evaluator_rejects_ambiguous_or_unverifiable_input(query: str, status: int) -> None:
    with TestClient(_app()) as client:
        response = client.get(f"/api/a11oy/v1/atelier/frontier/evaluate?{query}")
    assert response.status_code == status


def test_assets_are_local_accessible_and_do_not_clone_reference_brand() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    combined = html + css + js
    assert "http://" not in combined
    assert "https://" not in combined
    assert "innerHTML" not in js
    assert "Nexus Agent" not in combined
    assert "mascot" not in combined.casefold()
    for token in (
        "data-szl-public-experience-v3",
        "prefers-reduced-motion",
        "min-height:44px",
        "overflow-x:hidden",
    ):
        assert token in combined
    assert css.count("{") == css.count("}")
    assert js.count("{") == js.count("}")


def test_notice_is_exact_and_digest_bound() -> None:
    text = DOC.read_text(encoding="utf-8")
    notice = text.split("```text\n", 1)[1].split("\n```", 1)[0] + "\n"
    assert notice.startswith("MIT License\n\nCopyright (c) 2026 meta-success")
    assert hashlib.sha256(notice.encode()).hexdigest() == frontier.MIT_NOTICE_SHA256
    assert "Affiliation:** none" in text
    assert "does **not** import" in text
