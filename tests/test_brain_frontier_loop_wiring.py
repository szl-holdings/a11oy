#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Focused offline boundaries; HTTP and observed browser inputs are SIMULATED.

These tests exercise the real materializer, graph analyzer and client validator.
They do not execute a reviewer, a provider, a workflow, or the deferred integration
contract. Real captured artifact replay is a separately identified audit result.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import urllib.error
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path

import pytest

from scripts import materialize_brain_frontier_v7 as materializer
from scripts.observe_ouroboros_frontier import unavailable_observation
from tests.test_brain_frontier_v7 import dependencies, fixture

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 8, 21, 0, tzinfo=timezone.utc)


def packet():
    state_raw, candidates_raw = fixture()
    state, rows = materializer.validate_frontier(state_raw, candidates_raw)
    expected = {
        "controller_revision": dependencies()[materializer.OUROBOROS_REPOSITORY],
        "second_brain_revision": "5" * 40,
        "state_file_sha256": hashlib.sha256(state_raw).hexdigest(),
        "candidate_file_sha256": hashlib.sha256(candidates_raw).hexdigest(),
        "candidate_set_sha256": state["candidate_set_sha256"],
        "candidate_count": len(rows), "candidate_ids": [row["id"] for row in rows],
    }
    return state_raw, candidates_raw, expected


def run_metadata():
    repository = {"full_name": materializer.OUROBOROS_REPOSITORY, "id": 7}
    return {"repository": repository, "head_repository": dict(repository),
            "id": 99, "run_attempt": 1, "head_branch": "main", "event": "schedule",
            "path": materializer.OUROBOROS_WORKFLOW, "head_sha": "4" * 40,
            "status": "completed", "conclusion": "success", "updated_at": "2026-10-08T20:55:33Z"}


def instrument_transport(monkeypatch, *, run=None, artifacts=None, failure=False):
    requests = []
    metadata = run_metadata() if run is None else run
    def fake_json(url, token):
        requests.append(url)
        if failure:
            raise materializer.MaterializationError("SIMULATED transport failure")
        if "workflows/" in url:
            return {"total_count": 1, "workflow_runs": [metadata]}
        return {"total_count": len(artifacts or []), "artifacts": artifacts or []}
    monkeypatch.setattr(materializer, "github_json", fake_json)
    def forbidden_download(*args):
        pytest.fail("artifact download was not admitted by run preflight")
    monkeypatch.setattr(materializer, "download_ouroboros_artifact", forbidden_download)
    return requests


@pytest.mark.parametrize("change,expected_state", [
    ({"status": "in_progress", "conclusion": None}, "PENDING"),
    ({"conclusion": "failure"}, "FAILED"),
    ({"conclusion": "cancelled"}, "FAILED"),
    ({"head_sha": "9" * 40}, "STALE"),
    ({"updated_at": "2026-10-08T13:00:00Z"}, "STALE"),
    ({"id": True}, "REJECTED"),
    ({"head_branch": "feature"}, "REJECTED"),
])
def test_latest_non_success_never_uses_an_older_green_run(monkeypatch, change, expected_state):
    _, _, expected = packet()
    requests = instrument_transport(monkeypatch, run=run_metadata() | change)
    result = materializer.fetch_ouroboros_observation(expected, None, now=NOW)
    assert result["state"] == expected_state
    assert all(value is None for value in result["observation"].values())
    assert result["artifact"] is None and len(requests) == 1
    assert "status=success" not in requests[0]
    assert requests[0].endswith("/codex-continuous-frontier.yml/runs?branch=main&per_page=1")


def test_transport_failure_preserves_handles_and_unavailable_observation(monkeypatch):
    state_raw, candidates_raw, _ = packet()
    instrument_transport(monkeypatch, failure=True)
    result = materializer.build_snapshot("5" * 40, state_raw, candidates_raw, dependencies(),
                                         observe_ouroboros=True, now=NOW)
    assert len(result["handles"]) == 72
    assert result["ouroboros_observation"]["state"] == "UNAVAILABLE"
    assert result["ouroboros_observation"]["reason"] == "RUN_METADATA_UNAVAILABLE"
    assert "SIMULATED transport failure" not in json.dumps(result)


@pytest.mark.parametrize("artifacts,state", [
    ([], "UNAVAILABLE"),
    ([{"id": 20, "name": "ouroboros-frontier-98-1"}], "UNAVAILABLE"),
    ([{"id": 20, "name": "ouroboros-frontier-99-1", "expired": True}], "UNAVAILABLE"),
    ([{"id": 20, "name": "ouroboros-frontier-99-1"},
      {"id": 21, "name": "ouroboros-frontier-99-1"}], "REJECTED"),
])
def test_artifact_missing_expired_or_ambiguous_never_substitutes(monkeypatch, artifacts, state):
    _, _, expected = packet()
    requests = instrument_transport(monkeypatch, artifacts=artifacts)
    result = materializer.fetch_ouroboros_observation(expected, None, now=NOW)
    assert result["state"] == state and len(requests) == 2
    assert result["artifact"] is None


def test_archive_bytes_flow_to_real_validator_and_invalid_receipt_is_rejected(monkeypatch):
    _, _, expected = packet()
    instrument_transport(monkeypatch, artifacts=[{"id": 20, "name": "ouroboros-frontier-99-1"}])
    calls = []
    def download(artifact_id, token):
        calls.append(artifact_id)
        return b"SIMULATED malformed archive"
    monkeypatch.setattr(materializer, "download_ouroboros_artifact", download)
    result = materializer.fetch_ouroboros_observation(expected, None, now=NOW)
    assert result["state"] == "REJECTED" and calls == [20]
    assert result["reason"] == "REVIEW_RECEIPT_REJECTED"


def test_builder_default_is_offline_and_analyzes_real_plan(monkeypatch):
    state_raw, candidates_raw, _ = packet()
    monkeypatch.setattr(materializer, "fetch_ouroboros_observation", lambda *_args, **_kwargs: pytest.fail("network"))
    snapshot = materializer.build_snapshot("5" * 40, state_raw, candidates_raw, dependencies())
    assert snapshot["ouroboros_observation"]["state"] == "UNAVAILABLE"
    graph = snapshot["advisory_dag"]
    assert graph["execution"]["mode"] == "PLAN_ONLY" and graph["execution"]["authorized"] is False
    assert [graph["execution"][key] for key in ("writes", "effectors", "provider_calls")] == [0, 0, 0]
    assert graph["topology"]["critical_path"] == ["OBSERVE", "ORIENT", "PROPOSE", "VERIFY", "HOLD"]
    assert graph["topology"]["data_edge_count"] == 5 and graph["gates"]["blocker_count"] == 0
    assert graph["contracts"]["bounded_loop_iterations"] == 1
    assert graph["evidence_label"] == "MODELED"
    body = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    assert hashlib.sha256(materializer.canonical_bytes(body)).hexdigest() == snapshot["snapshot_sha256"]


class Response(io.BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


def fake_opener(monkeypatch, locations, payload=b"SIMULATED ZIP bytes"):
    requests = []
    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            if len(requests) <= len(locations):
                headers = Message()
                headers["Location"] = locations[len(requests) - 1]
                raise urllib.error.HTTPError(request.full_url, 302, "SIMULATED redirect", headers, None)
            return Response(payload)
    monkeypatch.setattr(materializer.urllib.request, "build_opener", lambda *args: Opener())
    return requests


def test_artifact_redirect_never_forwards_github_authorization(monkeypatch):
    requests = fake_opener(monkeypatch, ["https://example.blob.core.windows.net/artifacts/public.zip?test=1"])
    assert materializer.download_ouroboros_artifact(20, "SIMULATED_READ_TOKEN") == b"SIMULATED ZIP bytes"
    assert requests[0].full_url == "https://api.github.com/repos/szl-holdings/szl-ouroboros/actions/artifacts/20/zip"
    assert requests[0].get_header("Authorization") == "Bearer SIMULATED_READ_TOKEN"
    assert requests[1].get_header("Authorization") is None


@pytest.mark.parametrize("location", [
    "http://example.blob.core.windows.net/object", "https://attacker.invalid/object",
    "https://example.blob.core.windows.net.attacker.invalid/object",
    "https://user@example.blob.core.windows.net/object", "https://example.blob.core.windows.net:444/object",
    "https://example.blob.core.windows.net/object#fragment", "/relative/object",
])
def test_storage_redirect_rejects_unexpected_origins(monkeypatch, location):
    requests = fake_opener(monkeypatch, [location])
    with pytest.raises(materializer.MaterializationError):
        materializer.download_ouroboros_artifact(20, "SIMULATED_READ_TOKEN")
    assert len(requests) == 1


def test_artifact_redirect_and_response_size_are_bounded(monkeypatch):
    requests = fake_opener(monkeypatch, ["https://example.blob.core.windows.net/object"] * 5)
    with pytest.raises(materializer.MaterializationError):
        materializer.download_ouroboros_artifact(20, None)
    assert len(requests) == 4
    fake_opener(monkeypatch, [], b"x" * (materializer.MAX_REVIEW_ARCHIVE_BYTES + 1))
    with pytest.raises(materializer.MaterializationError, match="byte bound"):
        materializer.download_ouroboros_artifact(20, None)


def browser_snapshot():
    """Synthetic observation for client schema checks, never a hosted run receipt."""
    state_raw, candidates_raw, expected = packet()
    snapshot = materializer.build_snapshot("5" * 40, state_raw, candidates_raw, dependencies())
    observed = unavailable_observation(expected, state="UNAVAILABLE", reason="SIMULATED_BROWSER_CONTRACT_FIXTURE",
                                       run=run_metadata())
    observed.update({"state": "OBSERVED", "artifact": {"id": 20, "name": "ouroboros-frontier-99-1",
                     "archive_sha256": "a" * 64, "receipt_sha256": "b" * 64}})
    observed["observation"] = {"bounded": True, "terminated": True, "receipt_closed": True,
                               "steps": 1, "max_budget": 1, "wall_ms": 1234, "exit": "converged",
                               "review_state": "REVIEW_PROPOSED", "review_sha256": "c" * 64,
                               "recommendation_count": 1}
    observed["observation_sha256"] = hashlib.sha256(materializer.canonical_bytes(
        {key: value for key, value in observed.items() if key != "observation_sha256"})).hexdigest()
    snapshot["ouroboros_observation"] = observed
    snapshot["snapshot_sha256"] = hashlib.sha256(materializer.canonical_bytes(
        {key: value for key, value in snapshot.items() if key != "snapshot_sha256"})).hexdigest()
    return snapshot


def test_python_snapshot_replays_in_actual_browser_validator_and_expires():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable")
    source = (ROOT / "console/assets/brain-frontier-v7.js").read_text()
    source = source.replace("\n})();", "\n globalThis.__test = {validatePayload, verifySnapshot, effectiveObservationState, canonicalJson};\n})();")
    script = '''
import {webcrypto} from "node:crypto";
globalThis.window = {crypto:webcrypto, location:{origin:"https://a-11-oy.com"},
  matchMedia:()=>({matches:false,addEventListener(){}})};
globalThis.document = {readyState:"loading",addEventListener(){}};
''' + source + "\nconst packet = " + json.dumps(browser_snapshot(), ensure_ascii=False) + ''';
const {validatePayload,verifySnapshot,effectiveObservationState,canonicalJson} = globalThis.__test;
if (!validatePayload(packet) || !await verifySnapshot(packet)) throw new Error("Python snapshot rejected");
if (effectiveObservationState(packet,Date.parse("2026-10-08T21:00:00Z")) !== "OBSERVED") throw new Error("fresh state");
if (effectiveObservationState(packet,Date.parse("2026-10-09T03:00:00Z")) !== "STALE") throw new Error("expiry");
if (effectiveObservationState(packet,Date.parse("2026-10-08T19:00:00Z")) !== "REJECTED") throw new Error("future state");
for (const mutate of [
  p=>p.ouroboros_observation.claims.signature_verified=true,
  p=>p.ouroboros_observation.source.controller_revision="f".repeat(40),
  p=>p.ouroboros_observation.authority.execution="ALLOW",
  p=>p.advisory_dag.execution.authorized=true,
  p=>p.advisory_dag.normalized_contract.nodes[2].max_iterations=100,
  p=>p.advisory_dag.normalized_contract.nodes[4].writes.push("repo"),
  p=>p.advisory_dag.topology.edges[0].source="HOLD",
  p=>p.advisory_dag.contracts.hidden_resource_edges.push("unobserved"),
  p=>p.ouroboros_observation.source.private_rows=["forbidden"],
]) {
  const changed=structuredClone(packet); mutate(changed);
  if(validatePayload(changed)) throw new Error("invalid observation admitted");
}
const altered=structuredClone(packet);
altered.ouroboros_observation.observation.wall_ms += 1;
const {snapshot_sha256, ...body} = altered;
const digest = await webcrypto.subtle.digest("SHA-256",new TextEncoder().encode(canonicalJson(body)));
altered.snapshot_sha256 = [...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,"0")).join("");
if(await verifySnapshot(altered)) throw new Error("inner digest was not checked");
'''
    result = subprocess.run([node, "--input-type=module", "-"], input=script, text=True,
                            capture_output=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr or result.stdout
