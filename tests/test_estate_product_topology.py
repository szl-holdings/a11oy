# SPDX-License-Identifier: Apache-2.0
"""Deterministic contracts for the five-product estate witness."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "estate_product_topology.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("estate_product_topology", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


TOPOLOGY = load_module()
A11OY_SHA = "a" * 40
KILLINCHU_SHA = "b" * 40
VERTICAL_SERVICES_SHA = "c" * 40


def response(url: str, status: int, payload: object | str) -> object:
    if isinstance(payload, str):
        body = payload.encode()
        content_type = "text/html"
    else:
        body = json.dumps(payload).encode()
        content_type = "application/json"
    return TOPOLOGY.HttpResult(
        url=url,
        status=status,
        content_type=content_type,
        body=body,
        elapsed_ms=1.0,
        error=None if 200 <= status < 300 else f"HTTPError:{status}",
    )


def sha_for_repo(repository: str) -> str:
    return {
        "szl-holdings/a11oy": A11OY_SHA,
        "szl-holdings/killinchu": KILLINCHU_SHA,
        "szl-holdings/vertical-services": VERTICAL_SERVICES_SHA,
    }[repository]


def complete_fetch(url: str, timeout: float) -> object:  # noqa: ARG001
    for repository, branch_url in TOPOLOGY.GITHUB_BRANCH_URLS.items():
        if url == branch_url:
            return response(url, 200, {"commit": {"sha": sha_for_repo(repository)}})

    if url.startswith("https://huggingface.co/api/spaces/SZLHOLDINGS/"):
        slug = url.rsplit("/", 1)[-1]
        if slug in {"sentra", "vessels"}:
            return response(url, 404, {"error": "not found"})
        return response(
            url,
            200,
            {"sha": "d" * 40, "runtime": {"stage": "RUNNING"}},
        )

    if url.endswith("/api/build-info"):
        revision = A11OY_SHA
        if "killinchu" in url:
            revision = KILLINCHU_SHA
        elif "vertical-services" in url:
            revision = VERTICAL_SERVICES_SHA
        return response(url, 200, {"build": {"source_revision": revision}})

    if url.endswith("/api/defend/status"):
        return response(url, 200, {"status": "READY", "product": "killinchu"})
    if url.endswith("/api/defend/readyz"):
        return response(url, 200, {"ready": True, "product": "killinchu"})
    if url.endswith("/api/defend/source"):
        return response(
            url,
            200,
            {
                "product": "killinchu",
                "capability": "defend",
                "source_revision": KILLINCHU_SHA,
            },
        )
    if url.endswith("/api/source"):
        return response(url, 200, {"source_revision": A11OY_SHA})
    if url.endswith("/api/catalog"):
        return response(
            url,
            200,
            {
                "sentra_independent_public_vertical": False,
                "aegis_canonical_runtime": "killinchu:defend",
                "sentra_public_route": (
                    "https://szlholdings-killinchu.hf.space/defend"
                ),
                "immune_canonical_runtime": "MIGRATION_REQUIRED",
            },
        )
    if url.endswith("/healthz"):
        return response(url, 200, {"ok": True})
    if url.endswith("/defend") or url.endswith("/resilience"):
        return response(url, 200, "<html><title>Killinchu</title></html>")

    raise AssertionError(f"unexpected fixed-origin request: {url}")


def test_static_topology_is_exactly_five_products():
    slugs = tuple(item["slug"] for item in TOPOLOGY.PUBLIC_PRODUCTS)
    folded = {item["slug"] for item in TOPOLOGY.FOLDED_CAPABILITY_PLANES}
    assert slugs == ("killinchu", "terra", "counsel", "finance", "lyte")
    assert len(set(slugs)) == 5
    assert not (set(slugs) & folded)
    assert TOPOLOGY.PORTFOLIO_LABELS == ("aegis",)
    assert TOPOLOGY.MIGRATION_GATED == ("immune",)


def test_exact_sha_reads_nested_source_revision_only():
    assert TOPOLOGY.exact_sha({"build": {"source_revision": A11OY_SHA}}) == A11OY_SHA
    assert TOPOLOGY.exact_sha({"sha": A11OY_SHA}) is None
    assert TOPOLOGY.exact_sha({"source_revision": "not-a-sha"}) is None


def test_absent_folded_space_is_a_valid_retirement():
    item = TOPOLOGY.FOLDED_CAPABILITY_PLANES[0]

    def missing(url: str, timeout: float) -> object:  # noqa: ARG001
        return response(url, 404, {"error": "not found"})

    result = TOPOLOGY.folded_space_observation(item, missing)
    assert result["state"] == "ABSENT"
    assert result["pass"] is True


def test_complete_witness_requires_exact_sources_and_no_duplicate_spaces():
    receipt = TOPOLOGY.assess_once(complete_fetch)
    assert receipt["schema"] == TOPOLOGY.SCHEMA
    assert receipt["static_contract"]["public_product_count"] == 5
    assert receipt["complete"] is True
    assert receipt["truth_label"] == "MEASURED"
    assert all(item["pass"] for item in receipt["products"])
    assert receipt["internal_services"][0]["topology_contract"] is True
    assert all(item["state"] == "ABSENT" for item in receipt["folded_spaces"])
    assert receipt["authority"]["third_party_writes"] is False
    assert receipt["authority"]["remote_response_bodies_recorded"] is False


def test_stale_deployment_revision_fails_closed():
    def stale(url: str, timeout: float) -> object:
        result = complete_fetch(url, timeout)
        if url.endswith("/api/build-info") and "killinchu" in url:
            return response(url, 200, {"source_revision": "e" * 40})
        return result

    receipt = TOPOLOGY.assess_once(stale)
    killinchu = next(item for item in receipt["products"] if item["slug"] == "killinchu")
    assert killinchu["exact_source_revision"] is False
    assert killinchu["pass"] is False
    assert receipt["complete"] is False
    assert receipt["truth_label"] == "BLOCKED"


def test_active_folded_space_without_tombstone_fails_closed():
    item = TOPOLOGY.FOLDED_CAPABILITY_PLANES[0]

    def active(url: str, timeout: float) -> object:  # noqa: ARG001
        if "/api/spaces/" in url:
            return response(url, 200, {"runtime": {"stage": "RUNNING"}})
        return response(url, 200, "# Sentra\nIndependent product surface")

    result = TOPOLOGY.folded_space_observation(item, active)
    assert result["state"] == "RETIREMENT_REQUIRED"
    assert result["pass"] is False
