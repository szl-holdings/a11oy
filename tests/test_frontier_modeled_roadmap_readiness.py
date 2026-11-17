"""Permanently-modeled roadmap tiles (doctrine v11) do not gate readiness.

The orbital tier declares permanently_modeled=True: no on-orbit hardware
exists and none is planned, so its unsatisfied evidence can never be remedied.
Counting it as "blocked" made operational readiness permanently NOT_READY and
/operator/recommend permanently DEGRADED - the structural verify deadlock in
issue #3654. These contracts pin the fix: a permanently-modeled tile is
reported transparently in modeled_roadmap_tiles and gates nothing, while any
tile that CAN become operational still blocks - including a MODELED tile that
does not declare itself permanently modeled.
"""
import ast
from pathlib import Path

import pytest
from fastapi import FastAPI

import szl_frontier_manifest as manifest


def _tile(name, ready=True, **extra):
    value = {
        "name": name, "category": "test", "status": "OK", "label": manifest.MEASURED,
        "ok": True, "provenance": {"kind": "test evidence"},
        "operational_evidence": {
            "predicate": "observed operating capability",
            "satisfied": ready, "reasons": [] if ready else ["evidence_missing"],
        },
    }
    value.update(extra)
    return value


def _produce(monkeypatch, *tiles, composite=None):
    monkeypatch.setattr(manifest, "_TILE_SPECS", [
        (lambda value=value: value, value["name"], "test", {}) for value in tiles])
    monkeypatch.setattr(manifest, "_concept_tile_inference_provenance",
                        lambda: composite if composite is not None else _tile("composite"))
    observed = manifest._build_manifest()
    monkeypatch.setattr(manifest, "build_manifest", lambda app: observed)
    return observed


def _orbital_like():
    return _tile(
        "Orbital compute tier", ready=False, label=manifest.MODELED,
        status="MODELED roadmap (no on-orbit hardware)",
        permanently_modeled=True, on_orbit_hardware=False,
        operational_evidence={
            "predicate": "at least one on-orbit hardware node is positively reachable",
            "satisfied": False,
            "reasons": ["hardware_not_present"],
        },
    )


def test_orbital_tile_declares_itself_permanently_modeled():
    tile = manifest._tile_orbital()
    assert tile["permanently_modeled"] is True
    assert tile["label"] == manifest.MODELED
    assert tile["on_orbit_hardware"] is False
    ready, reasons = manifest._tile_operational_readiness(tile)
    assert ready is False
    assert "hardware_not_present" in reasons


def test_permanently_modeled_tile_does_not_block_readiness(monkeypatch):
    observed = _produce(monkeypatch, _tile("operator"), _orbital_like())
    summary = observed["summary"]["operational_readiness"]

    assert summary["ready"] is True
    assert summary["state"] == "READY"
    assert summary["blocked_tiles"] == []
    assert summary["ready_tiles"] == ["operator", "composite"]
    assert [row["name"] for row in summary["modeled_roadmap_tiles"]] == ["Orbital compute tier"]
    assert "hardware_not_present" in summary["modeled_roadmap_tiles"][0]["reasons"]
    # The tile itself is never upgraded: still MODELED and NOT_READY on its card.
    card = next(t for t in observed["capabilities"]
                if t["name"] == "Orbital compute tier")
    assert card["label"] == manifest.MODELED
    assert card["operational_readiness"]["ready"] is False
    assert card["operational_readiness"]["state"] == "NOT_READY"
    assert observed["summary"]["all_sources_live"] is True


def test_modeled_tile_without_declaration_still_blocks(monkeypatch):
    modeled = _tile("modeled", ready=False, label=manifest.MODELED)
    observed = _produce(monkeypatch, _tile("operator"), modeled)
    summary = observed["summary"]["operational_readiness"]

    assert summary["ready"] is False
    assert [row["name"] for row in summary["blocked_tiles"]] == ["modeled"]
    assert summary["modeled_roadmap_tiles"] == []


@pytest.mark.parametrize("label", [manifest.MEASURED, manifest.UNAVAILABLE, manifest.SAMPLE])
def test_permanently_modeled_flag_cannot_unblock_operational_labels(monkeypatch, label):
    flagged = _tile("flagged", ready=False, label=label, permanently_modeled=True)
    observed = _produce(monkeypatch, _tile("operator"), flagged)
    summary = observed["summary"]["operational_readiness"]

    assert summary["ready"] is False
    assert [row["name"] for row in summary["blocked_tiles"]] == ["flagged"]
    assert summary["modeled_roadmap_tiles"] == []


def _serve_function(name, extra=None):
    path = Path(__file__).resolve().parents[1] / "serve.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(row for row in tree.body
                if isinstance(row, (ast.FunctionDef, ast.AsyncFunctionDef))
                and row.name == name)
    scope = {"app": FastAPI()}
    if extra:
        scope.update(extra)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    return scope[name]


def test_liveness_signal_counts_modeled_roadmap_without_blocking(monkeypatch):
    _produce(monkeypatch, _tile("operator"), _orbital_like())
    signal = _serve_function("_frontier_liveness_signal")

    result = signal()

    assert result["status"] == "ok"
    assert result["endpoints_total"] == 3
    assert result["endpoints_live"] == 2
    assert result["endpoints_degraded"] == 0
    assert result["modeled_roadmap_tiles"] == ["Orbital compute tier"]
    assert result["all_sources_live"] is True


def test_operator_recommend_projects_real_when_only_modeled_roadmap_remains():
    recommend = _serve_function("_sc_recommend", {"_sc_now": lambda: "2026-11-17T00:00:00Z"})
    health = {
        "service": "a11oy", "status": "ok", "degraded_reasons": [],
        "operational_readiness": {
            "ready": True, "status": "READY", "service_blockers": [],
            "frontier": {
                "ready": True, "state": "READY",
                "ready_tiles": ["operator"],
                "blocked_tiles": [],
                "modeled_roadmap_tiles": [{
                    "name": "Orbital compute tier", "ready": False,
                    "reasons": ["hardware_not_present"]}],
            },
        },
    }

    result = recommend(health, 200)

    assert result["status"] == "REAL"
    assert result["health_state"] == "OBSERVED"
    orbital = next(row for row in result["recommendations"]
                   if row["organ"] == "Orbital compute tier")
    assert orbital["severity"] == "info"
    assert "hardware_not_present" in orbital["finding"]


def test_operator_recommend_stays_degraded_while_a_real_tile_blocks():
    recommend = _serve_function("_sc_recommend", {"_sc_now": lambda: "2026-11-17T00:00:00Z"})
    health = {
        "service": "a11oy", "status": "ok", "degraded_reasons": [],
        "operational_readiness": {
            "ready": False, "status": "NOT_READY", "service_blockers": [],
            "frontier": {
                "ready": False, "state": "NOT_READY",
                "ready_tiles": ["operator"],
                "blocked_tiles": [{"name": "energy", "ready": False,
                                   "reasons": ["operator_stopped"]}],
                "modeled_roadmap_tiles": [{
                    "name": "Orbital compute tier", "ready": False,
                    "reasons": ["hardware_not_present"]}],
            },
        },
    }

    result = recommend(health, 200)

    assert result["status"] == "DEGRADED"
