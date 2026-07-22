"""Read-only API tests for frontier adoption and live HF estate classification."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import a11oy_model_intel as intel
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_frontier_adoption_exposes_truth_without_authority() -> None:
    payload = intel.get_frontier_adoption()
    assert payload["state"] == "GOVERNED_PLAN_NOT_LOCAL_QUALIFICATION"
    assert payload["qualificationAuthority"] is False
    assert payload["promotionAuthority"] is False
    assert payload["deleteAuthority"] is False
    assert payload["externalMutationPerformed"] is False
    assert payload["registry"]["github_estate_strategy"]["inventory_complete"] is False
    assert payload["registry"]["github_estate_strategy"]["source_reported_repository_count"] == 54
    registry = payload["registry"]
    assert registry["brain_model_truth"]["raw_nodes_observed"] == 9464
    assert registry["brain_model_truth"]["raw_nodes_admitted_to_gradients"] == 0
    assert len(registry["candidates"]) == 9


def test_estate_merges_live_metadata_without_turning_downloads_into_quality(monkeypatch) -> None:
    live = [
        {
            "repository_id": "SZLHOLDINGS/SZL-Khipu-1.5B",
            "revision": "cb414ab3b7dd05b5c6622c1a9c4e50089c7c0b76",
            "downloads": 1033,
            "likes": 1,
            "last_modified": "2026-07-16T13:40:51.000Z",
            "pipeline_tag": "text-generation",
            "library_name": "transformers",
            "weight_bearing_from_filenames": True,
            "file_count": 29,
        },
        {
            "repository_id": "SZLHOLDINGS/new-unclassified-model",
            "revision": "f" * 40,
            "downloads": 9999,
            "likes": 100,
            "last_modified": "2026-07-16T00:00:00.000Z",
            "pipeline_tag": "text-generation",
            "library_name": "transformers",
            "weight_bearing_from_filenames": True,
            "file_count": 2,
        },
    ]
    monkeypatch.setattr(
        intel,
        "_cached_fetch",
        lambda *args, **kwargs: {
            "value": live,
            "freshness": {"status": "live", "age_s": 0.0},
        },
    )
    payload = intel.get_szl_estate()
    assert payload["state"] == "LIVE"
    assert payload["downloadsAreAdoptionSignalNotQuality"] is True
    assert payload["zeroDownloadsAuthorizeDeletion"] is False
    assert payload["deleteAuthority"] is False
    assert payload["summary"]["unclassified_live"] == 1
    unknown = next(
        item for item in payload["models"]
        if item["repository_id"] == "SZLHOLDINGS/new-unclassified-model"
    )
    assert unknown["classification_state"] == "UNCLASSIFIED_FAIL_CLOSED"
    assert unknown["delete_authorized"] is False
    khipu = next(
        item for item in payload["models"]
        if item["repository_id"] == "SZLHOLDINGS/SZL-Khipu-1.5B"
    )
    assert khipu["classification_state"] == "PIN_MATCH"
    assert khipu["strategy"] == "KEEP_FLAGSHIP_REPRO_TRUST_REVIEW_REQUIRED"


def test_estate_keeps_static_classification_when_hub_feed_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        intel,
        "_cached_fetch",
        lambda *args, **kwargs: {
            "value": None,
            "freshness": {"status": "unavailable", "error": "offline"},
        },
    )
    payload = intel.get_szl_estate()
    assert payload["state"] == "STATIC_CLASSIFICATION_LIVE_FEED_UNAVAILABLE"
    assert payload["summary"]["classified_repositories"] == 15
    assert payload["summary"]["live_repositories"] == 0
    assert all(item["delete_authorized"] is False for item in payload["models"])


def test_estate_does_not_label_stale_last_good_metadata_live(monkeypatch) -> None:
    live = [{
        "repository_id": "SZLHOLDINGS/SZL-Khipu-1.5B",
        "revision": "cb414ab3b7dd05b5c6622c1a9c4e50089c7c0b76",
        "downloads": 1033,
        "weight_bearing_from_filenames": True,
    }]
    monkeypatch.setattr(
        intel,
        "_cached_fetch",
        lambda *args, **kwargs: {
            "value": live,
            "freshness": {"status": "stale", "age_s": 3601.0, "error": "timeout"},
        },
    )
    payload = intel.get_szl_estate()
    assert payload["state"] == "STALE_LAST_GOOD"
    assert payload["freshness"]["status"] == "stale"
    assert payload["deleteAuthority"] is False


def test_hf_parser_ignores_malformed_rows() -> None:
    rows = intel._parse_hf_org_models([
        None,
        "not-a-model",
        {"id": {"not": "hashable"}, "sha": "a" * 40},
        {"id": ["not", "hashable"], "sha": "a" * 40},
        {"id": "OTHERORG/not-in-szl", "sha": "a" * 40},
        {
            "id": "SZLHOLDINGS/valid",
            "sha": "a" * 40,
            "siblings": [{"rfilename": "model.safetensors"}],
        },
    ])
    assert len(rows) == 1
    assert rows[0]["repository_id"] == "SZLHOLDINGS/valid"
    assert rows[0]["weight_bearing_from_filenames"] is True

    sharded = intel._parse_hf_org_models([{
        "id": "SZLHOLDINGS/sharded",
        "sha": "b" * 40,
        "siblings": [{"rfilename": "PYTORCH_MODEL-00001-OF-00002.BIN"}],
    }])
    assert sharded[0]["weight_bearing_from_filenames"] is True

    additional_formats = intel._parse_hf_org_models([{
        "id": "SZLHOLDINGS/additional-formats",
        "sha": "c" * 40,
        "siblings": [{"rfilename": "nested/weights/model.onnx"}],
    }])
    assert additional_formats[0]["weight_bearing_from_filenames"] is True

    invalid_revision = intel._parse_hf_org_models([{
        "id": "SZLHOLDINGS/invalid-revision",
        "sha": {"not": "a-sha"},
        "siblings": [],
    }])
    assert invalid_revision[0]["revision"] is None


def test_estate_sort_treats_malformed_download_count_as_zero(monkeypatch) -> None:
    live = [
        {
            "repository_id": "SZLHOLDINGS/SZL-Khipu-1.5B",
            "revision": "cb414ab3b7dd05b5c6622c1a9c4e50089c7c0b76",
            "downloads": "not-a-number",
        },
        {
            "repository_id": "SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent",
            "revision": "4cc1fc12f630feab487eed34b2bda9c7a14778d6",
            "downloads": 10,
        },
    ]
    monkeypatch.setattr(
        intel,
        "_cached_fetch",
        lambda *args, **kwargs: {
            "value": live,
            "freshness": {"status": "live", "age_s": 0.0},
        },
    )
    payload = intel.get_szl_estate()
    assert payload["state"] == "LIVE"
    assert payload["models"][0]["repository_id"] == (
        "SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent"
    )


def test_register_exposes_dual_aliases_and_fail_closed_status(monkeypatch) -> None:
    app = FastAPI()

    @app.api_route("/api/a11oy/{path:path}", methods=["GET"])
    async def proxy_catchall(path: str):
        return {"caught_by": "proxy", "path": path}

    @app.get("/{full_path:path}")
    async def spa_catchall(full_path: str):
        return {"caught_by": "spa", "path": full_path}

    intel.register(app)
    paths = {route.path for route in app.routes}
    assert "/api/a11oy/v1/models/frontier-adoption" in paths
    assert "/v1/models/frontier-adoption" in paths
    assert "/api/a11oy/v1/models/estate" in paths
    assert "/v1/models/estate" in paths

    route_order = [route.path for route in app.routes]
    assert route_order.index("/api/a11oy/v1/models/estate") < route_order.index(
        "/api/a11oy/{path:path}"
    )
    assert route_order.index("/v1/models/estate") < route_order.index("/{full_path:path}")
    estate_route = next(
        route for route in app.routes
        if route.path == "/api/a11oy/v1/models/estate"
    )
    assert not inspect.iscoroutinefunction(estate_route.endpoint)

    monkeypatch.setattr(
        intel,
        "get_frontier_adoption",
        lambda: {"state": "GOVERNED_PLAN_NOT_LOCAL_QUALIFICATION"},
    )
    monkeypatch.setattr(
        intel,
        "get_szl_estate",
        lambda: {"state": "LIVE"},
    )
    client = TestClient(app)
    for path in (
        "/api/a11oy/v1/models/frontier-adoption",
        "/v1/models/frontier-adoption",
        "/api/a11oy/v1/models/estate",
        "/v1/models/estate",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert "caught_by" not in response.json()
    info = client.get("/api/a11oy/v1/models/info")
    assert info.status_code == 200
    assert "/estate" in info.json()["endpoints"]

    monkeypatch.setattr(
        intel,
        "get_frontier_adoption",
        lambda: {"state": "UNAVAILABLE", "reason": "corrupt registry"},
    )
    monkeypatch.setattr(
        intel,
        "get_szl_estate",
        lambda: {"state": "UNAVAILABLE", "reason": "corrupt registry"},
    )
    for path in (
        "/api/a11oy/v1/models/frontier-adoption",
        "/v1/models/frontier-adoption",
        "/api/a11oy/v1/models/estate",
        "/v1/models/estate",
    ):
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["state"] == "UNAVAILABLE"


def test_real_assembled_serve_routes_precede_catchalls_and_respond_offline(monkeypatch) -> None:
    import serve

    route_paths = [getattr(route, "path", "") for route in serve.app.router.routes]
    proxy_index = route_paths.index("/api/a11oy/{path:path}")
    spa_index = route_paths.index("/{full_path:path}")
    for path in (
        "/api/a11oy/v1/models/frontier-adoption",
        "/v1/models/frontier-adoption",
        "/api/a11oy/v1/models/estate",
        "/v1/models/estate",
    ):
        assert path in route_paths
        assert route_paths.index(path) < min(proxy_index, spa_index)

    monkeypatch.setattr(
        intel,
        "_cached_fetch",
        lambda *args, **kwargs: {
            "value": None,
            "freshness": {"status": "unavailable", "error": "offline regression"},
        },
    )
    client = TestClient(serve.app)
    for path in (
        "/api/a11oy/v1/models/frontier-adoption",
        "/v1/models/frontier-adoption",
        "/api/a11oy/v1/models/estate",
        "/v1/models/estate",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert "caught_by" not in response.json()


def test_missing_registry_fails_closed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(intel, "_FRONTIER_REGISTRY", tmp_path / "missing.json")
    adoption = intel.get_frontier_adoption()
    estate = intel.get_szl_estate()
    assert adoption["state"] == "UNAVAILABLE"
    assert adoption["promotionAuthority"] is False
    assert estate["state"] == "UNAVAILABLE"
    assert estate["deleteAuthority"] is False


def test_malformed_or_mutated_registry_fails_closed(monkeypatch, tmp_path: Path) -> None:
    registry = json.loads(intel._FRONTIER_REGISTRY.read_text(encoding="utf-8"))
    registry.pop("hf_estate")
    malformed = tmp_path / "malformed.json"
    malformed.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(intel, "_FRONTIER_REGISTRY", malformed)
    assert intel.get_frontier_adoption()["state"] == "UNAVAILABLE"
    assert intel.get_szl_estate()["state"] == "UNAVAILABLE"

    registry = json.loads(
        (Path(__file__).resolve().parents[1]
         / "model_release" / "frontier-qualification" / "frontier-adoption.json")
        .read_text(encoding="utf-8")
    )
    registry["external_mutations"]["model_trained"] = True
    mutated = tmp_path / "mutated.json"
    mutated.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(intel, "_FRONTIER_REGISTRY", mutated)
    payload = intel.get_frontier_adoption()
    assert payload["state"] == "UNAVAILABLE"
    assert payload["externalMutationPerformed"] is False

    registry = json.loads(
        (Path(__file__).resolve().parents[1]
         / "model_release" / "frontier-qualification" / "frontier-adoption.json")
        .read_text(encoding="utf-8")
    )
    registry["github_estate_strategy"]["inventory_complete"] = True
    overclaimed = tmp_path / "overclaimed-github-estate.json"
    overclaimed.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(intel, "_FRONTIER_REGISTRY", overclaimed)
    assert intel.get_frontier_adoption()["state"] == "UNAVAILABLE"
    assert intel.get_szl_estate()["state"] == "UNAVAILABLE"
