#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the passive board with a fake local transport and no app startup."""

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EFFECT_ENDPOINTS = (
    "/api/a11oy/v1/eval/run",
    "/api/a11oy/v1/rag/query",
    "/api/a11oy/v1/agentloop/run",
    "/api/a11oy/v1/harness/apply",
    "/api/a11oy/v1/restraint/evaluate",
    "/api/a11oy/v1/pinn/residual/evaluate",
    "/api/a11oy/v1/loopforge/run",
)


@pytest.fixture
def run_board(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "verify_board_readonly_test", ROOT / "tools" / "verify_board.py"
    )
    board = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(board)
    calls = []
    responses = {}

    class Response:
        def __init__(self, code=200):
            self.status_code = code

        def json(self):
            return {"status": "SAMPLE"}

    class Client:
        def __init__(self, _app):
            pass

        def get(self, endpoint):
            calls.append(("GET", endpoint))
            response = responses.get(endpoint, 200)
            if isinstance(response, Exception):
                raise response
            return Response(response)

        def post(self, endpoint, **kwargs):
            calls.append(("POST", endpoint))
            return Response()

    fake_fastapi = types.ModuleType("fastapi")
    fake_testclient = types.ModuleType("fastapi.testclient")
    fake_testclient.TestClient = Client
    fake_serve = types.ModuleType("serve")
    fake_serve.app = object()
    fake_holo = types.ModuleType("szl3d_holographic")
    fake_holo.SURFACES = [{"id": "observed"}]
    monkeypatch.setitem(sys.modules, "fastapi", fake_fastapi)
    monkeypatch.setitem(sys.modules, "fastapi.testclient", fake_testclient)
    monkeypatch.setitem(sys.modules, "serve", fake_serve)
    monkeypatch.setitem(sys.modules, "szl3d_holographic", fake_holo)
    monkeypatch.setattr(board, "SURF_DIR", tmp_path)
    monkeypatch.setattr(board, "Path", lambda path: tmp_path / Path(path).name)

    def run(endpoints, status_codes=None):
        calls.clear()
        responses.clear()
        responses.update(status_codes or {})
        (tmp_path / "observed.js").write_text(
            "export default {endpoints: " + json.dumps(endpoints) + "};",
            encoding="utf-8",
        )
        board.main()
        matrix = json.loads((tmp_path / "board_matrix.json").read_text())
        return matrix, calls

    return run


@pytest.mark.parametrize("endpoint", EFFECT_ENDPOINTS)
def test_effect_endpoint_is_unprobed_without_any_request(run_board, endpoint):
    matrix, calls = run_board([endpoint])
    assert calls == []
    assert matrix["requiredNotProbed"] == 1
    row = matrix["rows"][0]
    assert row["status"] == "NOT_PROBED"
    observation = row["endpoints"][0]
    assert observation["code"] is None
    assert observation["live"] is False
    assert observation["status"] == "NOT_PROBED"
    assert "operator execution required" in observation["fields"]


def test_query_does_not_bypass_effect_endpoint_classification(run_board):
    endpoint = "/api/a11oy/v1/eval/run?view=summary"
    matrix, calls = run_board([endpoint])
    assert calls == []
    assert matrix["requiredNotProbed"] == 1
    assert matrix["rows"][0]["status"] == "NOT_PROBED"


def test_get_405_never_falls_back_to_post_or_becomes_live(run_board):
    endpoint = "/api/a11oy/v1/unlisted-action"
    matrix, calls = run_board([endpoint], {endpoint: 405})
    assert calls == [("GET", endpoint)]
    assert matrix["requiredNotProbed"] == 1
    row = matrix["rows"][0]
    assert row["status"] == "NOT_PROBED"
    assert row["endpoints"][0]["code"] == 405
    assert row["endpoints"][0]["live"] is False


@pytest.mark.parametrize("code", (200, 404, 500, 503))
def test_read_observation_keeps_original_get_result_without_writes(run_board, code):
    endpoint = "/api/a11oy/v1/honest"
    matrix, calls = run_board([endpoint], {endpoint: code})
    assert calls == [("GET", endpoint)]
    assert matrix["requiredNotProbed"] == 0
    row = matrix["rows"][0]
    assert row["endpoints"][0]["code"] == code
    assert row["endpoints"][0]["live"] is (code == 200)
    assert row["status"] == ("LIVE" if code == 200 else "404" if code == 404 else "BROKEN")


def test_successful_read_does_not_hide_unprobed_required_execution(run_board):
    read = "/api/a11oy/v1/honest"
    matrix, calls = run_board([read, EFFECT_ENDPOINTS[0]])
    assert calls == [("GET", read)]
    assert matrix["requiredNotProbed"] == 1
    assert matrix["counts"] == {"NOT_PROBED": 1}
    assert matrix["rows"][0]["status"] == "NOT_PROBED"


def test_genome_503_cannot_establish_live_runtime_from_docker_copy(run_board):
    endpoint = "/api/a11oy/v1/genome"
    matrix, calls = run_board([endpoint], {endpoint: 503})
    assert calls == [("GET", endpoint)]
    row = matrix["rows"][0]
    assert row["status"] == "BROKEN"
    observation = row["endpoints"][0]
    assert observation["code"] == 503
    assert observation["live"] is False
    assert observation["fields"] == "http503"


def test_get_exception_does_not_switch_to_execution(run_board):
    endpoint = "/api/a11oy/v1/honest"
    matrix, calls = run_board([endpoint], {endpoint: RuntimeError("offline")})
    assert calls == [("GET", endpoint)]
    observation = matrix["rows"][0]["endpoints"][0]
    assert observation["code"] == "EXC"
    assert observation["live"] is False
    assert matrix["rows"][0]["status"] == "BROKEN"


def test_documented_compute_get_alias_remains_observable(run_board):
    endpoint = "/api/a11oy/v1/counter-uas/compute"
    matrix, calls = run_board([endpoint])
    assert calls == [("GET", endpoint)]
    assert matrix["requiredNotProbed"] == 0
    assert matrix["rows"][0]["status"] == "LIVE"


def test_cross_repo_endpoint_is_recorded_without_network_or_live_claim(run_board):
    matrix, calls = run_board(["https://szlholdings-killinchu.hf.space/api/example"])
    assert calls == []
    assert matrix["requiredNotProbed"] == 0
    assert matrix["rows"][0]["status"] == "CROSS-REPO"
    assert matrix["rows"][0]["endpoints"][0]["live"] is None
