#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Missing, partial, and failed inventory reads stay denied. They do not raise or admit."""

import importlib.util
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_model_intel as intel
import a11oy_model_support as support

_SPEC = importlib.util.spec_from_file_location(
    "support_collector", Path(__file__).resolve().parents[1] / "scripts/collect_model_inference_support.py")
_collector = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_collector)
refresh = _collector.refresh


def _ids(document):
    return [row["id"] for row in document["models"]]


def _inventory(ids):
    return {"inventory": {"models": [{"id": model_id, "repoType": "model"} for model_id in ids]}}


def _write(tmp_path, name, payload):
    path = tmp_path / name
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    path.write_bytes(raw)
    return path


def _denied(result, state, reason):
    assert result["state"] == state
    assert result["reason"] == reason
    assert result["admission"] == "DENIED"
    assert result["models"] == []
    assert result["authority"] == support.AUTHORITY
    assert all(value is False for value in result["authority"].values())


def test_current_inventory_gap_is_blocked_without_an_index_error():
    result = support.public_status()
    _denied(result, "BLOCKED", "INVENTORY_COVERAGE_REVIEW_REQUIRED")
    assert intel.inference_support_http_status(result) == 403


def test_exact_inventory_still_projects_observations(tmp_path):
    document = support.read_json(support.STATUS_PATH)
    inventory = _write(tmp_path, "exact.json", _inventory(_ids(document)))
    result = support.public_status(inventory_path=inventory, now=document["generated_at"])
    assert result["state"] == "SOURCE_OBSERVATIONS"
    assert result["authority"] == support.AUTHORITY
    assert [row["id"] for row in result["models"]] == _ids(document)
    assert "admission" not in result


def test_partial_inventory_blocks_without_filling_the_gap(tmp_path):
    document = support.read_json(support.STATUS_PATH)
    kept = _ids(document)[:-1]
    dropped = _ids(document)[-1]
    inventory = _write(tmp_path, "partial.json", _inventory(kept))
    result = support.public_status(inventory_path=inventory, now=document["generated_at"])
    _denied(result, "BLOCKED", "INVENTORY_COVERAGE_REVIEW_REQUIRED")
    assert dropped not in json.dumps(result)


def test_unknown_inventory_model_is_not_admitted(tmp_path):
    document = support.read_json(support.STATUS_PATH)
    unknown = "SZLHOLDINGS/unreviewed-model"
    inventory = _write(tmp_path, "unknown.json", _inventory([*_ids(document), unknown]))
    result = support.public_status(inventory_path=inventory, now=document["generated_at"])
    _denied(result, "BLOCKED", "INVENTORY_COVERAGE_REVIEW_REQUIRED")
    assert unknown not in json.dumps(result)


def test_missing_and_malformed_inventory_are_unavailable(tmp_path):
    missing = support.public_status(inventory_path=tmp_path / "absent.json")
    _denied(missing, "UNAVAILABLE", "INVENTORY_UNAVAILABLE")
    malformed = _write(tmp_path, "broken.json", b"\xff")
    _denied(support.public_status(inventory_path=malformed), "UNAVAILABLE", "INVENTORY_MALFORMED")
    partial_row = _write(tmp_path, "row.json", {"inventory": {"models": ["SZLHOLDINGS/A11OY-MINI"]}})
    _denied(support.public_status(inventory_path=partial_row), "UNAVAILABLE", "INVENTORY_MALFORMED")
    assert intel.inference_support_http_status(missing) == 503


def test_unreadable_inventory_is_a_dependency_failure(tmp_path):
    blocked = tmp_path / "not-a-file"
    blocked.mkdir()
    result = support.public_status(inventory_path=blocked)
    _denied(result, "UNAVAILABLE", "INVENTORY_UNAVAILABLE")


def test_fetcher_index_error_becomes_unavailable_and_does_not_admit(tmp_path):
    document = support.read_json(support.STATUS_PATH)
    ids = _ids(document)
    inventory = json.dumps(_inventory(ids)).encode()

    def fetcher(model_id):
        if model_id == ids[0]:
            raise IndexError("provider payload had no row")
        return support.unavailable_observation(model_id, "2026-10-04T12:00:00Z", "HTTP_ERROR")

    result = refresh(document, inventory, fetcher)
    failed = next(row for row in result["models"] if row["id"] == ids[0])
    assert failed["inference"]["state"] == "UNAVAILABLE"
    assert failed["inference"]["error"] == "INVALID_RESPONSE"
    assert failed["inference"]["providers"] == []
    assert result["authority"] == support.AUTHORITY
    assert document == support.read_json(support.STATUS_PATH)


def test_blocked_route_is_403_and_unavailable_route_stays_503(monkeypatch):
    app = FastAPI()
    intel.register(app)
    client = TestClient(app)
    blocked = client.get("/api/a11oy/v1/models/inference-support")
    assert blocked.status_code == 403
    body = blocked.json()
    assert body["state"] == "BLOCKED"
    assert body["reason"] == "INVENTORY_COVERAGE_REVIEW_REQUIRED"
    assert body["models"] == []
    assert body["admission"] == "DENIED"
    monkeypatch.setattr(intel, "get_inference_support", lambda: {
        "state": "UNAVAILABLE", "reason": "INVENTORY_UNAVAILABLE",
        "models": [], "authority": dict(support.AUTHORITY), "admission": "DENIED",
    })
    unavailable = client.get("/v1/models/inference-support")
    assert unavailable.status_code == 503
    assert unavailable.json()["state"] == "UNAVAILABLE"
