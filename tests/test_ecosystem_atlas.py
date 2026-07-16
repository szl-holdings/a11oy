# SPDX-License-Identifier: Apache-2.0
"""Focused, network-free contracts for the public ecosystem atlas.

The atlas is an evidence projection, not an alternate source of truth.  These
tests therefore pin the two easy-to-regress boundaries: live inventory rows are
projected without losing their immutable handles, and a degraded snapshot keeps
only observed counts instead of inventing resource rows.
"""
from __future__ import annotations

from typing import Any

import pytest

import a11oy_ecosystem_atlas as atlas


def _inventory_fixture() -> dict[str, Any]:
    return {
        "observed_at": "2026-07-16T16:00:00Z",
        "counts": {
            "models": 1,
            "datasets": 1,
            "spaces": 1,
            "collections": 1,
            "buckets": 1,
            "public_resources_total": 5,
        },
        "resources": {
            "models": [
                {
                    "id": "SZLHOLDINGS/szl-kernels",
                    "repository_sha": "a" * 40,
                    "last_modified": "2026-07-16T15:00:00Z",
                    "license": "apache-2.0",
                    "source_observation": {"state": "VERIFIED"},
                }
            ],
            "datasets": [
                {
                    "id": "SZLHOLDINGS/example-dataset",
                    "head": "b" * 40,
                    "last_updated": "2026-07-15T12:00:00Z",
                    "license": "cc-by-4.0",
                }
            ],
            "spaces": [
                {
                    "id": "SZLHOLDINGS/example-space",
                    "repository_sha": "c" * 40,
                    "runtime": {"stage": "RUNNING"},
                    "source_observation": "PUBLIC_API",
                }
            ],
            "collections": [
                {
                    "slug": "SZLHOLDINGS/example-collection-abc123",
                    "last_modified": "2026-07-14T10:30:00Z",
                }
            ],
            "buckets": [{"id": "SZLHOLDINGS/example-bucket"}],
        },
    }


def test_inventory_projection_preserves_handles_state_and_hub_links() -> None:
    payload = atlas.project_inventory(_inventory_fixture(), state="LIVE")

    assert payload["schema"] == "szl.ecosystem-atlas/v1"
    assert payload["state"] == "LIVE"
    assert payload["observed_at"] == "2026-07-16T16:00:00Z"
    assert payload["inventory_source"] == atlas.INVENTORY_URL
    assert payload["counts"] == {
        "models": 1,
        "datasets": 1,
        "spaces": 1,
        "collections": 1,
        "buckets": 1,
        "public_resources_total": 5,
        "kernels": 10,
    }

    model = payload["resources"]["models"][0]
    assert model == {
        "id": "SZLHOLDINGS/szl-kernels",
        "kind": "model",
        "href": "https://huggingface.co/SZLHOLDINGS/szl-kernels",
        "revision": "a" * 40,
        "last_modified": "2026-07-16T15:00:00Z",
        "license": "apache-2.0",
        "source_state": "VERIFIED",
        "owner": "szl-holdings/szl-kernels-live",
    }
    dataset = payload["resources"]["datasets"][0]
    assert dataset["href"] == (
        "https://huggingface.co/datasets/SZLHOLDINGS/example-dataset"
    )
    assert dataset["revision"] == "b" * 40
    assert dataset["last_modified"] == "2026-07-15T12:00:00Z"
    assert payload["resources"]["spaces"][0]["runtime_stage"] == "RUNNING"
    assert payload["resources"]["spaces"][0]["source_state"] == "PUBLIC_API"
    assert payload["resources"]["collections"][0]["href"] == (
        "https://huggingface.co/collections/"
        "SZLHOLDINGS/example-collection-abc123"
    )
    assert payload["resources"]["buckets"][0]["href"] == (
        "https://huggingface.co/buckets/SZLHOLDINGS/example-bucket"
    )


def test_projection_exposes_exactly_ten_governed_kernels_with_owners() -> None:
    payload = atlas.project_inventory(_inventory_fixture())
    kernels = payload["resources"]["kernels"]

    assert len(kernels) == 10
    assert {row["id"] for row in kernels} == set(atlas.KERNEL_OWNERS)
    for row in kernels:
        ownership = atlas.KERNEL_OWNERS[row["id"]]
        assert row["kind"] == "kernel"
        assert row["href"] == f"https://huggingface.co/{row['id']}"
        assert row["owner"] == ownership["owner"]
        if "owner_state" in ownership:
            assert row["owner_state"] == ownership["owner_state"]

    # An inventory-backed kernel keeps its immutable artifact evidence; missing
    # model rows are represented only by their real Hub handle and owner.
    by_id = {row["id"]: row for row in kernels}
    assert by_id["SZLHOLDINGS/szl-kernels"]["revision"] == "a" * 40
    assert "revision" not in by_id["SZLHOLDINGS/szl-provctl"]


def test_snapshot_fallback_keeps_counts_but_never_fabricates_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _offline() -> dict[str, Any]:
        raise TimeoutError("inventory unavailable in test")

    monkeypatch.setattr(atlas, "_fetch_inventory", _offline)
    monkeypatch.setitem(atlas._CACHE, "payload", None)
    monkeypatch.setitem(atlas._CACHE, "at", 0.0)

    payload = atlas.atlas_payload()

    assert payload["state"] == "SNAPSHOT"
    assert payload["degraded_reason"] == "TimeoutError"
    assert payload["counts"] == {
        **atlas.SNAPSHOT_COUNTS,
        "kernels": len(atlas.KERNEL_OWNERS),
    }
    assert set(payload["resources"]) == {
        "models",
        "datasets",
        "spaces",
        "collections",
        "buckets",
        "kernels",
    }
    assert all(rows == [] for rows in payload["resources"].values())
    assert "rows stay empty" in payload["limits"]["snapshot"]


def test_registration_serves_api_and_all_real_deep_links_before_catchall(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    ecosystem_html = b"<!doctype html><title>fixture ecosystem</title>"
    anatomy_html = b"<!doctype html><title>fixture anatomy v5</title>"
    (tmp_path / "ecosystem.html").write_bytes(ecosystem_html)
    (tmp_path / "anatomy-v5.html").write_bytes(anatomy_html)
    monkeypatch.setattr(atlas, "_PAGES_DIR", tmp_path)
    api_payload = {
        "schema": "szl.ecosystem-atlas/v1",
        "state": "SNAPSHOT",
        "resources": {},
    }
    monkeypatch.setattr(atlas, "atlas_payload", lambda: api_payload)

    async def _catchall(request: Any) -> PlainTextResponse:
        return PlainTextResponse("catchall")

    app = FastAPI()
    app.router.routes.append(Route("/{path:path}", _catchall, methods=["GET"]))
    status = atlas.register(app, ns="test")

    assert status == "ok: atlas API + 6 deep-link pages + Anatomy v5"
    paths = [getattr(route, "path", "") for route in app.router.routes]
    api_path = "/api/test/v1/ecosystem/atlas"
    page_paths = (
        "/ecosystem",
        "/models",
        "/kernels",
        "/ecosystem/brain",
        "/ecosystem/anatomy",
        "/ecosystem/holographic",
    )
    catchall_index = paths.index("/{path:path}")
    assert paths.index(api_path) < catchall_index
    assert all(paths.index(path) < catchall_index for path in page_paths)
    assert paths.index("/anatomy-v5") < catchall_index

    with TestClient(app) as client:
        response = client.get(api_path)
        assert response.status_code == 200
        assert response.json() == api_payload
        for path in page_paths:
            page = client.get(path)
            assert page.status_code == 200
            assert page.content == ecosystem_html
            assert page.headers["content-type"].startswith("text/html")
            assert client.head(path).status_code == 200
        anatomy_page = client.get("/anatomy-v5")
        assert anatomy_page.status_code == 200
        assert anatomy_page.content == anatomy_html
        assert client.head("/anatomy-v5").status_code == 200


def test_missing_deep_link_asset_is_an_honest_503(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    monkeypatch.setattr(atlas, "_PAGES_DIR", tmp_path)
    app = FastAPI()
    atlas.register(app)

    with TestClient(app) as client:
        missing_atlas = client.get("/ecosystem")
        missing_anatomy = client.get("/anatomy-v5")

    assert missing_atlas.status_code == 503
    assert missing_atlas.json() == {"error": "ecosystem page unavailable"}
    assert missing_anatomy.status_code == 503
    assert missing_anatomy.json() == {"error": "anatomy v5 page unavailable"}
