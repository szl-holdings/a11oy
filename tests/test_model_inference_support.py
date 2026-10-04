#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Provider observations never turn requests or stale metadata into serving authority."""

import copy
import importlib.util
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

import a11oy_model_intel as intel
import a11oy_model_support as support

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("support_collector", ROOT / "scripts/collect_model_inference_support.py")
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


@pytest.fixture
def document():
    return support.read_json(support.STATUS_PATH)


def _published(tmp_path, document):
    path = tmp_path / "support.json"
    path.write_text(collector.render(document), encoding="utf-8")
    return path


def _now(document, hours=0):
    return (support._stamp(document["generated_at"]) + timedelta(hours=hours)).isoformat()


def test_committed_source_matches_schema_inventory_and_actual_request_evidence(document):
    schema = support.read_json(ROOT / "docs/model-inference-support.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)
    support.validate_document(document, support.read_json(support.INVENTORY_PATH))
    assert len(document["models"]) == 47
    assert len({r["id"] for r in document["models"]}) == 47
    assert all(r["inference"]["state"] == "NO_PROVIDER_MAPPING" for r in document["models"])
    requests = [request for row in document["models"] for request in row["support"]["requests"]]
    submitted = [r for r in requests if r["evidence_kind"] == "VERIFIED_SUBMISSION"]
    assert {r["discussion_number"] for r in submitted} == set(range(12781, 12791))
    assert len([r for r in requests if r["evidence_kind"] == "PRIOR_DISCUSSION"]) == 5
    assert document["unmatched_prior_requests"][0]["model_id"] == "SZLHOLDINGS/SZL-Khipu-1.5B-BrainNavigator"
    assert document["unmatched_prior_requests"][0]["discussion_number"] == 11072
    assert all(r["model_revision"] is None for r in requests if r["evidence_kind"] == "PRIOR_DISCUSSION")
    assert collector.main(["--check"]) == 0


@pytest.mark.parametrize("path,value", [
    (("authority", "qualification"), True),
    (("authority", "routing"), 0),
    (("inventory_source", "model_ids_sha256"), "0" * 64),
    (("max_observation_age_seconds",), 86401),
    (("scope",), "ALL_HUB_ASSETS"),
    (("models", 0, "repo_type"), "kernel"),
    (("models", 0, "id"), "SZLHOLDINGS/a11oy-mini"),
    (("models", 0, "assessment", "source_url"), "https://untrusted.invalid/README.md"),
    (("models", 0, "assessment", "artifact_class"), []),
    (("models", 0, "assessment", "qualification_note"), "x" * 1001),
    (("models", 0, "inference", "state"), "PROVIDER_MAPPING_REPORTED"),
    (("models", 0, "inference", "capture_sha256"), "0" * 64),
    (("models", 0, "inference", "source_url"), "http://127.0.0.1/metadata"),
    (("models", 0, "inference", "hub_revision"), "main"),
    (("models", 0, "inference", "providers"), {}),
    (("models", 0, "inference", "observed_at"), "2099-01-01T00:00:00Z"),
    (("models", 0, "support", "state"), "REQUESTED"),
])
def test_invalid_source_is_rejected_without_authority(document, path, value, tmp_path):
    node = document
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(support.SupportDataError):
        support.validate_document(document)
    result = support.public_status(_published(tmp_path, document))
    assert result["state"] == "UNAVAILABLE"
    assert result["models"] == []
    assert result["authority"] == support.AUTHORITY


def test_inventory_other_namespaces_cannot_substitute_for_models(document):
    inventory = support.read_json(support.INVENTORY_PATH)
    inventory["inventory"]["models"].pop()
    inventory["inventory"]["kernels"] = [document["models"][-1]]
    with pytest.raises(support.SupportDataError, match="coverage"):
        support.validate_document(document, inventory)


@pytest.mark.parametrize("key,value", [
    ("model_id", "SZLHOLDINGS/not-the-requested-model"),
    ("url", support.SUPPORT_PREFIX + "1"),
    ("url", "https://untrusted.invalid/discussions/12781"),
    ("readback_at", "2020-01-01T00:00:00Z"),
    ("readback_body_sha256", "missing"),
    ("evidence_kind", "PROVIDER_APPROVED"),
    ("recorded_status", []),
])
def test_submission_proof_stays_exact_and_bounded(document, key, value):
    request = next(r for row in document["models"] for r in row["support"]["requests"]
                   if r["evidence_kind"] == "VERIFIED_SUBMISSION")
    request[key] = value
    with pytest.raises(support.SupportDataError):
        support.validate_document(document)


def test_prior_request_cannot_gain_invented_revision_and_duplicate_models_fail(document):
    document["unmatched_prior_requests"][0]["model_revision"] = "a" * 40
    with pytest.raises(support.SupportDataError):
        support.validate_document(document)
    document["unmatched_prior_requests"][0]["model_revision"] = None
    document["models"].append(copy.deepcopy(document["models"][0]))
    with pytest.raises(support.SupportDataError):
        support.validate_document(document)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"value":NaN}', b'\xff', b'[' * 1200])
def test_json_decoder_rejects_ambiguous_or_invalid_input(raw):
    with pytest.raises(support.SupportDataError):
        support.decode_json(raw)


@pytest.mark.parametrize("payload", [
    {"id": "SZLHOLDINGS/other", "sha": "a" * 40, "inferenceProviderMapping": {}},
    {"id": "SZLHOLDINGS/A11OY-MINI", "sha": "a" * 40},
    {"id": "SZLHOLDINGS/A11OY-MINI", "sha": "a" * 40, "inferenceProviderMapping": None},
    {"id": "SZLHOLDINGS/A11OY-MINI", "sha": "a" * 40, "inferenceProviderMapping": {"provider": {"status": []}}},
])
def test_missing_or_malformed_provider_mapping_is_not_an_empty_mapping(payload):
    with pytest.raises(support.SupportDataError):
        support.observation_from_mapping("SZLHOLDINGS/A11OY-MINI", payload, "2026-10-04T12:00:00Z")


@pytest.mark.parametrize("status", ["live", "staging"])
def test_provider_report_and_requests_never_grant_model_authority(document, tmp_path, status):
    row = document["models"][0]
    row["inference"] = support.observation_from_mapping(row["id"], {
        "id": row["id"], "sha": "a" * 40,
        "inferenceProviderMapping": {"example-provider": {
            "status": status, "task": "conversational", "providerId": "example/model",
        }},
    }, row["inference"]["observed_at"])
    path = _published(tmp_path, document)
    fresh = support.public_status(path, now=_now(document))
    assert fresh["models"][0]["inference"]["state"] == "PROVIDER_MAPPING_REPORTED"
    assert fresh["models"][0]["assessment"] == row["assessment"]
    assert fresh["authority"] == support.AUTHORITY
    assert fresh["runtime_qualification"] == "NOT_ASSESSED_BY_PROVIDER_STATUS"
    stale = support.public_status(path, now=_now(document, 25))
    observed = stale["models"][0]["inference"]
    assert observed["state"] == "UNAVAILABLE"
    assert observed["providers"] == []
    assert observed["last_observed_providers"][0]["status"] == status
    assert observed["freshness"] == "STALE_OBSERVATION"
    assert stale["summary"]["verified_submissions"] == 10


def test_clock_mismatch_and_missing_file_are_unavailable(document, tmp_path):
    result = support.public_status(_published(tmp_path, document), now="2020-01-01T00:00:00Z")
    assert all(row["inference"]["state"] == "UNAVAILABLE" for row in result["models"])
    assert support.public_status(tmp_path / "absent.json")["state"] == "UNAVAILABLE"
    assert not (tmp_path / "absent.json").exists()


def test_refresh_retains_requests_and_assessments_when_api_is_unavailable(document):
    original = copy.deepcopy(document)
    result = collector.refresh(document, support.INVENTORY_PATH.read_bytes(),
                               lambda model_id: support.unavailable_observation(model_id, support.utc_now(), "HTTP_ERROR"))
    assert document == original
    assert all(row["inference"]["state"] == "UNAVAILABLE" for row in result["models"])
    for before, after in zip(original["models"], result["models"]):
        assert before["assessment"] == after["assessment"]
        assert before["support"] == after["support"]


def test_collector_rejects_redirects_and_oversized_response(monkeypatch):
    class Response:
        status = 200

        def __enter__(self): return self
        def __exit__(self, *_): return None
        def geturl(self): return support.mapping_url("SZLHOLDINGS/A11OY-MINI")
        def read(self, limit):
            assert limit == support.MAX_RESPONSE_BYTES + 1
            return b" " * limit

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == support.mapping_url("SZLHOLDINGS/A11OY-MINI")
            assert timeout == 8
            assert not request.has_header("Authorization")
            return Response()

    monkeypatch.setattr(collector.urllib.request, "build_opener", lambda handler: Opener())
    result = collector.fetch_observation("SZLHOLDINGS/A11OY-MINI")
    assert result["state"] == "UNAVAILABLE"
    assert result["error"] == "INVALID_RESPONSE"
    assert collector.NoRedirect().redirect_request(None, None, 302, None, None, "https://other.invalid") is None


def test_read_only_dual_route_and_catalog_join(document, monkeypatch):
    app = FastAPI()

    @app.get("/{rest:path}")
    def catchall(rest): return {"caught": rest}

    intel.register(app)
    snapshot = support.public_status(now=_now(document))
    monkeypatch.setattr(intel, "get_inference_support", lambda: snapshot)

    def no_write(*args, **kwargs):
        raise AssertionError("read-only provider catalog attempted a write")

    for method in ("write_text", "write_bytes", "mkdir"):
        monkeypatch.setattr(Path, method, no_write)
    client = TestClient(app)
    for path in ("/api/a11oy/v1/models/inference-support", "/v1/models/inference-support"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert len(response.json()["models"]) == 47
        assert response.json()["authority"] == support.AUTHORITY
    monkeypatch.setattr(intel, "_cached_fetch", lambda *args, **kwargs: {
        "value": None, "freshness": {"status": "unavailable"},
    })
    estate = intel.get_szl_estate()
    record = next(row for row in estate["models"] if row["repository_id"] == "SZLHOLDINGS/SZL-Khipu-1.5B")
    assert record["inference_support"]["support"]["requests"][0]["discussion_number"] == 12781
    assert record["classification_state"] == "NOT_OBSERVED_LIVE"
    assert estate["qualificationAuthority"] is False
    monkeypatch.setattr(intel, "get_inference_support", lambda: {
        "state": "UNAVAILABLE", "models": [], "authority": dict(support.AUTHORITY),
    })
    response = client.get("/api/a11oy/v1/models/inference-support")
    assert response.status_code == 503
    assert response.json()["models"] == []
