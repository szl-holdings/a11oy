#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Observation must not initialize, write-probe, or recover an energy ledger.

Run the production GET handlers and transitive ledger readers. Unrelated network
and capability sources are explicit fixtures; the ledger, recovery, storage, and
readiness projection under test are the production implementations.
"""
import ast
import builtins
import copy
import datetime
import io
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

import szl_brain_command as command
import szl_brain_hub as hub
import szl_energy_ledger as ledger_module
import szl_frontier_manifest as manifest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "serve.py"
FUNCTIONS = {
    node.name: node for node in ast.walk(ast.parse(SOURCE.read_text(encoding="utf-8")))
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}
NOW = 1_000_000.0
TS = datetime.datetime.fromtimestamp(NOW - 1, tz=datetime.timezone.utc).isoformat()


def job(index):
    return ledger_module.JobRecord(
        node=f"fixture-{index}", joules_measured=0.0, joules_label="sample",
        tokens=index, wall_s=1.0, ts=TS, model="fixture-model", nvml_age_s=None,
    )


def install_functions(scope, names):
    needed = set(names)
    pending = list(needed)
    while pending:
        for part in ast.walk(FUNCTIONS[pending.pop()]):
            name = part.id if isinstance(part, ast.Name) else None
            if (name in FUNCTIONS and name not in scope and name not in needed
                    and (name.startswith(("_sc_", "_gov_")) or name == "gov_envelope")):
                needed.add(name)
                pending.append(name)
    selected = []
    for name in sorted(needed):
        node = copy.deepcopy(FUNCTIONS[name])
        node.decorator_list = []
        selected.append(node)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), scope)


@pytest.fixture
def runtime(monkeypatch):
    app = FastAPI()
    monkeypatch.setitem(sys.modules, "szl_energy_ledger", ledger_module)
    monkeypatch.setitem(sys.modules, "szl_brain", SimpleNamespace(
        mcp_inventory_snapshot=lambda _: {"count": None, "label": "UNAVAILABLE"}))
    monkeypatch.setattr(command, "_knowledge_summary", lambda *_: {
        "label": "MODELED", "distinct_artifacts": 0})
    monkeypatch.setattr(command, "_surfaces_lit", lambda: {
        "label": "MODELED", "count": 0, "source": "fixture"})
    monkeypatch.setattr(hub, "knowledge_summary", lambda *_: {
        "label": "MODELED", "distinct_artifacts": 0, "sources": {}})
    monkeypatch.setattr(manifest, "_TILE_SPECS", [
        (manifest._tile_energy_ledger, "Tamper-evident energy ledger", "energy", {})])
    monkeypatch.setattr(manifest, "_concept_tile_inference_provenance", lambda: {
        "name": "fixture capability", "category": "test", "status": "OK",
        "label": "MEASURED", "ok": True, "provenance": {},
        "operational_evidence": {"predicate": "fixture only", "satisfied": True,
                                 "reasons": []}})
    monkeypatch.setattr(manifest, "build_manifest", lambda app=None: manifest._build_manifest(app))

    async def dependency():
        return {"status": "ok", "backend_alive": True, "checked_at": time.time()}

    scope = {
        "app": app, "sys": sys, "_hz_time": time,
        "_LEDGER_STORAGE_CACHE": {}, "_BRAIN_HZ_CACHE": {},
        "_healthz_dep_ping": dependency, "_signer_availability_signal": lambda: {"status": "ABSENT"},
        "_sovereign_health_signal": lambda: {},
        "_preflight_signal": lambda: {"overall": "DEGRADED"},
        "_A11OY_START_TIME": time.time(), "_gates_list": [],
        "JSONResponse": JSONResponse, "_SCJSON": JSONResponse,
        "_sc_json": json, "_sc_datetime": datetime,
    }
    install_functions(scope, {
        "_ledger_storage_signal", "_frontier_liveness_signal", "_brain_health_signal",
        "healthz", "_sc_rosie_recommend", "_sc_cap_recommend",
    })
    for path, name in (
        ("/api/a11oy/healthz", "healthz"),
        ("/api/a11oy/v1/companion/recommend", "_sc_rosie_recommend"),
        ("/api/a11oy/v1/operator/recommend", "_sc_cap_recommend"),
    ):
        app.add_api_route(path, scope[name], methods=["GET"])
    ledger_module.register(app)
    command.register(app)
    hub.register(app)
    manifest.register(app)
    return TestClient(app), scope


def tree_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
            for path in root.rglob("*")}


@contextmanager
def forbid_observation_mutations(monkeypatch):
    calls = []

    def forbidden(name):
        def fail(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError(f"observation attempted {name}")
        return fail

    def guarded_open(original):
        def read_only(file, mode="r", *args, **kwargs):
            if isinstance(mode, str) and any(flag in mode for flag in "wax+"):
                return forbidden("file write")(file, mode)
            return original(file, mode, *args, **kwargs)
        return read_only

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", guarded_open(builtins.open))
        guard.setattr(io, "open", guarded_open(io.open))
        for name in ("mkdir", "makedirs", "remove", "unlink", "rename", "replace", "write"):
            guard.setattr(os, name, forbidden(name))
        for name in ("get_ledger", "_strict_read", "_exclusive_writer_lock",
                     "_quarantine_generation", "_dir_is_writable"):
            guard.setattr(ledger_module, name, forbidden(name))
        for name in ("__init__", "_load", "_persist_entry", "_build_reset_entry"):
            guard.setattr(ledger_module.EnergyLedger, name, forbidden(name))
        guard.setattr(ledger_module._DurableStore, "_is_writable_now", forbidden("write probe"))
        guard.setattr(command, "_sign", forbidden("command receipt"))
        guard.setattr(hub, "_sign", forbidden("hub receipt"))
        yield calls
    assert calls == []


def assert_unavailable_reads(client):
    for path in ("/api/a11oy/v1/energy/ledger", "/api/a11oy/v1/energy/ledger/summary",
                 "/api/a11oy/v1/energy/receipt/example", "/energy/receipt/example"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "UNAVAILABLE" and body["ok"] is False
        assert body["chain"] is None and body["receipts"] is None

    for path in ("/api/a11oy/v1/brain/command", "/api/a11oy/v1/brain/pulse"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert body["energy"]["label"] == "UNAVAILABLE"
        assert body["read_only"] is True
        assert body["receipt"]["signed"] is False

    response = client.get("/api/a11oy/v1/frontier/manifest")
    assert response.status_code == 200
    frontier = response.json()
    energy = next(tile for tile in frontier["capabilities"] if tile["category"] == "energy")
    assert energy["label"] == "UNAVAILABLE" and energy["ok"] is False
    assert energy["operational_readiness"]["ready"] is False
    assert frontier["summary"]["operational_readiness"]["ready"] is False

    response = client.get("/api/a11oy/healthz")
    assert response.status_code == 200
    health = response.json()
    assert health["status"] == "degraded"
    assert health["storage"]["status"] == "unavailable"
    assert "storage-unavailable" in health["degraded_reasons"]
    for path in ("/api/a11oy/v1/companion/recommend", "/api/a11oy/v1/operator/recommend"):
        response = client.get(path)
        assert response.status_code == 200
        report = response.json()
        assert report["status"] == "DEGRADED"
        assert report["operational_readiness"]["ready"] is False
        assert "storage-unavailable" in report["operational_readiness"]["service_blockers"]
        assert report["counts"]["critical"] >= 1


@pytest.mark.parametrize("state", ["missing", "partial", "forked"])
def test_cold_gets_preserve_files_and_cannot_recover(tmp_path, monkeypatch, runtime, state):
    path = tmp_path / "absent" / "energy.jsonl" if state == "missing" else tmp_path / "energy.jsonl"
    if state == "partial":
        path.write_bytes(b'{"partial":true')
    elif state == "forked":
        original = ledger_module.EnergyLedger(path=str(path))
        for index in (1, 2):
            assert original.append_job(job(index), now=NOW)["appended"] is True
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]["prev_digest"] = "0" * 64
        rows[1]["entry_digest"] = ledger_module._entry_digest(
            rows[1]["seq"], rows[1]["prev_digest"], rows[1]["receipt"]["payload_digest"])
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setattr(ledger_module, "DEFAULT_LEDGER_PATH", str(path))
    monkeypatch.setattr(ledger_module, "_LEDGER", None)
    before = tree_bytes(tmp_path)
    client, _scope = runtime

    with forbid_observation_mutations(monkeypatch):
        with pytest.raises(ledger_module.LedgerObservationUnavailable, match="LEDGER_NOT_INITIALIZED"):
            ledger_module.observe_ledger()
        assert_unavailable_reads(client)
        assert ledger_module._LEDGER is None
    assert tree_bytes(tmp_path) == before

    # Explicit writer initialization still owns the original recovery behavior.
    writer = ledger_module.get_ledger()
    assert writer.verify()["ok"] is True
    assert ledger_module.observe_ledger() is writer
    if state != "missing":
        assert len(writer.entries()) == 1
        decision = writer.entries()[0]["receipt"]["decision"]
        assert decision["schema"] == "SZL.Energy.LedgerReset.v1"
        assert list(Path(str(path) + ".quarantine").glob("*/manifest.json"))
    assert writer.append_job(job(3), now=NOW)["appended"] is True


@pytest.mark.parametrize("module_state", ["absent", "partial"])
def test_observation_never_imports_an_uninitialized_ledger(monkeypatch, runtime, module_state):
    client, _scope = runtime
    monkeypatch.setattr(ledger_module, "_LEDGER", None)
    if module_state == "absent":
        monkeypatch.delitem(sys.modules, "szl_energy_ledger")
    else:
        monkeypatch.setitem(sys.modules, "szl_energy_ledger", SimpleNamespace())
    imports = []
    original = builtins.__import__

    def no_ledger_import(name, *args, **kwargs):
        if name == "szl_energy_ledger":
            imports.append(name)
            raise AssertionError("observation imported the writer ledger")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_ledger_import)
    with forbid_observation_mutations(monkeypatch):
        assert_unavailable_reads(client)
    assert imports == []


def test_initialized_load_failure_stays_unavailable(monkeypatch, runtime):
    monkeypatch.setattr(ledger_module, "_LEDGER", SimpleNamespace(
        _load_error={"code": "LEDGER_RECOVERY_FAILED"}))
    with forbid_observation_mutations(monkeypatch):
        with pytest.raises(ledger_module.LedgerObservationUnavailable, match="LEDGER_LOAD_UNAVAILABLE"):
            ledger_module.observe_ledger()
        assert_unavailable_reads(runtime[0])


def test_warm_storage_observation_uses_one_nonwriting_status_call(tmp_path, monkeypatch, runtime):
    writer = ledger_module.EnergyLedger(path=str(tmp_path / "energy.jsonl"))
    assert writer.append_job(job(1), now=NOW)["appended"] is True
    monkeypatch.setattr(ledger_module, "_LEDGER", writer)
    original_status = writer._store.status
    probes = []

    def status(probe=True):
        probes.append(probe)
        return original_status(probe=probe)

    monkeypatch.setattr(writer._store, "status", status)
    before = tree_bytes(tmp_path)
    entries = copy.deepcopy(writer.entries())
    counters = copy.deepcopy(vars(writer._store._counters))
    with forbid_observation_mutations(monkeypatch):
        health = runtime[1]["_ledger_storage_signal"]()
        assert health["status"] in {"ok", "pressure"}
        assert health["writable"] is None
        assert health["write_probe_performed"] is False
        assert health["fresh_writability_asserted"] is False
        assert probes == [False]
        summary = ledger_module.handle_ledger()
        assert summary["chain"]["length"] == 1 and summary["ok"] is True
        assert probes == [False, False]
        receipt = ledger_module.handle_receipt(entries[0]["idempotency_key"])
        assert receipt["ok"] is True and receipt["rehash"]["matches"] is True
    assert writer.entries() == entries
    assert vars(writer._store._counters) == counters
    assert tree_bytes(tmp_path) == before


def test_observation_preserves_a_failed_write_after_success(tmp_path, monkeypatch):
    path = tmp_path / "energy.jsonl"
    writer = ledger_module.EnergyLedger(path=str(path))
    monkeypatch.setattr(ledger_module, "_LEDGER", writer)
    assert writer.append_job(job(1), now=NOW)["appended"] is True
    original_open = builtins.open

    def refuse_append(file, mode="r", *args, **kwargs):
        if os.fspath(file) == str(path) and "a" in mode:
            raise OSError("fixture write failure")
        return original_open(file, mode, *args, **kwargs)

    with monkeypatch.context() as writer_fault:
        writer_fault.setattr(builtins, "open", refuse_append)
        refused = writer.append_job(job(2), now=NOW)
    assert refused["appended"] is False and refused["error"] == "STORAGE_UNAVAILABLE"
    assert writer._store._counters.appended == 1
    assert writer._store._counters.write_failures == 1
    before = tree_bytes(tmp_path)
    with forbid_observation_mutations(monkeypatch):
        health = ledger_module.ledger_storage_health()
        assert health["status"] == "unavailable"
        assert health["writable"] is False
        assert health["write_probe_performed"] is False
        assert health["fresh_writability_asserted"] is False
        assert health["status_scope"] == "TRACKED_STORAGE_STATUS"
        assert ledger_module.handle_ledger()["chain"]["length"] == 1
    assert tree_bytes(tmp_path) == before

    diagnostic = writer.storage_health(probe=True)
    assert diagnostic["status"] == "unavailable"  # the failed writer has not recovered
    assert diagnostic["writable"] is True  # the explicit new directory probe succeeded
    assert diagnostic["write_probe_performed"] is True
    assert diagnostic["fresh_writability_asserted"] is True
    assert writer.append_job(job(2), now=NOW)["appended"] is True
    with forbid_observation_mutations(monkeypatch):
        health = ledger_module.ledger_storage_health()
        assert health["status"] in {"ok", "pressure"}
        assert health["writable"] is None and health["write_probe_performed"] is False
