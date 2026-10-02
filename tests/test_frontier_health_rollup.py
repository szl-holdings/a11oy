"""Health rollup consumes the manifest's operational evidence, not source access."""
import ast
from pathlib import Path
import time

import pytest

import szl_frontier_manifest as manifest


@pytest.fixture
def signal():
    # Isolate the production helper from serve.py's unrelated startup integrations.
    # Its real manifest import remains intact and each test supplies the real producer.
    path = Path(__file__).resolve().parents[1] / "serve.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(row for row in tree.body if isinstance(row, ast.FunctionDef)
                and row.name == "_frontier_liveness_signal")
    scope = {"_hz_time": time, "_FRONTIER_HEALTH_CACHE": {}}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    return scope["_frontier_liveness_signal"]


def tile(name, ready=True, **extra):
    value = {"name": name, "category": "test", "status": "OK", "label": "MEASURED",
             "ok": True, "provenance": {"kind": "test evidence"},
             "operational_evidence": {"predicate": "observed operating capability",
                                      "satisfied": ready, "reasons": [] if ready else ["stopped"]}}
    value.update(extra)
    return value


def producer(monkeypatch, *tiles, composite=None):
    monkeypatch.setattr(manifest, "_TILE_SPECS", [
        (lambda value=value: value, value["name"], "test", {}) for value in tiles])
    monkeypatch.setattr(manifest, "_concept_tile_inference_provenance",
                        lambda: composite if composite is not None else tile("composite"))
    observed = manifest._build_manifest()
    monkeypatch.setattr(manifest, "build_manifest", lambda: observed)
    return observed


def test_readable_stopped_and_modeled_sources_are_not_live(signal, monkeypatch):
    observed = producer(monkeypatch, tile("operator", ready=False, running=False),
                        tile("orbital", label="MODELED"), tile("running"))
    assert observed["summary"]["degraded_tiles"] == []
    result = signal()
    assert result["status"] == "degraded"
    assert result["endpoints_total"] == 4
    assert result["endpoints_live"] == 2
    assert result["endpoints_degraded"] == 2
    assert result["degraded_tiles"] == ["operator", "orbital"]
    assert result["all_sources_live"] is False
    assert result["source_reachability"]["all_sources_reachable"] is True
    assert result["operational_readiness"] == observed["summary"]["operational_readiness"]


def test_positive_operational_evidence_remains_ok(signal, monkeypatch):
    producer(monkeypatch, tile("running"))
    result = signal()
    assert result["status"] == "ok"
    assert result["endpoints_live"] == result["endpoints_total"] == 2
    assert result["endpoints_degraded"] == 0
    assert result["all_sources_live"] is True


def test_unminted_composite_preserves_blocker_reasons(signal, monkeypatch):
    producer(monkeypatch, tile("running"), composite=tile("composite", ready=False,
             status="UNAVAILABLE (unminted)", label="UNAVAILABLE", on_artifact_minted=False))
    result = signal()
    assert result["status"] == "degraded"
    assert result["endpoints_live"] == 1
    assert result["degraded_tiles"] == ["composite"]
    assert "artifact_not_minted" in result["operational_readiness"]["blocked_tiles"][0]["reasons"]


@pytest.mark.parametrize("mutation", [
    lambda summary: summary.pop("operational_readiness"),
    lambda summary: summary.update(tiles=99),
    lambda summary: summary.update(tiles=True),
    lambda summary: summary["operational_readiness"].update(ready="true"),
    lambda summary: summary["operational_readiness"].update(ready=False),
])
def test_missing_or_inconsistent_readiness_is_unavailable(signal, monkeypatch, mutation):
    observed = producer(monkeypatch, tile("running"))
    mutation(observed["summary"])
    result = signal()
    assert result["status"] == "unavailable"
    assert result["endpoints_live"] is None


def test_cache_does_not_create_an_extra_manifest_read(signal, monkeypatch):
    observed = producer(monkeypatch, tile("running"))
    calls = []
    monkeypatch.setattr(manifest, "build_manifest", lambda: calls.append(True) or observed)
    first = signal()
    assert signal() is first
    assert calls == [True]
