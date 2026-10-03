"""Health rollup consumes the manifest's operational evidence, not source access."""
import ast
from pathlib import Path

import pytest
from fastapi import FastAPI

import szl_frontier_manifest as manifest


@pytest.fixture
def runtime_app():
    return FastAPI()


@pytest.fixture
def signal(runtime_app):
    # Isolate the production helper from serve.py's unrelated startup integrations.
    # Its real manifest import remains intact and each test supplies the real producer.
    path = Path(__file__).resolve().parents[1] / "serve.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(row for row in tree.body if isinstance(row, ast.FunctionDef)
                and row.name == "_frontier_liveness_signal")
    scope = {"app": runtime_app}
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
    monkeypatch.setattr(manifest, "build_manifest", lambda app: observed)
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


class DeterministicCache:
    """SIMULATED TTL cache makes composition reuse independent of test timing."""

    def __init__(self, ttl):
        self.ttl = ttl
        self.value = None
        self.compositions = 0

    def get_or_compute(self, producer):
        if self.value is None:
            self.value = producer()
            self.compositions += 1
        return self.value

    def invalidate(self):
        self.value = None


@pytest.fixture
def governance_observation(runtime_app, monkeypatch):
    """SIMULATED app observation; readiness comes from the real tile producer."""
    info = {
        "signer_health": {"observed_this_process": True, "ready": True,
                          "identity": "simulated-test-key"},
        "receipt_verification": {"observed_this_process": True,
                                 "cryptographically_verified": True,
                                 "signature_count": 1,
                                 "method": "ECDSA-P256-SHA256 DSSE PAE"},
    }
    reads = []
    runtime_app.state.szl_restraint_info_reader = lambda: reads.append(True) or info
    runtime_app.state.szl_frontier_manifest_cache = DeterministicCache(manifest._MANIFEST_TTL)
    monkeypatch.setattr(manifest, "_TILE_SPECS", [
        (manifest._tile_governance, "Governance / restraint", "governance", {})])
    monkeypatch.setattr(manifest, "_concept_tile_inference_provenance",
                        lambda: tile("composite"))
    return info, reads, runtime_app.state.szl_frontier_manifest_cache


def test_manifest_composition_is_reused_while_app_observation_is_unchanged(
        signal, governance_observation):
    _, reads, cache = governance_observation

    first = signal()
    second = signal()

    assert first == second
    assert first["all_sources_live"] is True
    assert cache.compositions == 1
    assert len(reads) >= 2, "each health read must recheck the current app observation"


@pytest.mark.parametrize("gate", ["qualified", "signer_unready", "unverified", "placeholder"])
def test_rollup_reads_registered_app_and_keeps_signature_gates(
        signal, governance_observation, gate):
    """SIMULATED observations exercise the real app-aware governance producer."""
    info, reads, _ = governance_observation
    if gate == "signer_unready":
        info["signer_health"]["ready"] = False
    elif gate == "unverified":
        info["receipt_verification"]["cryptographically_verified"] = False
    elif gate == "placeholder":
        info["receipt_verification"]["method"] = "DSSE_PLACEHOLDER"
    result = signal()

    assert reads, "health must read the restraint implementation registered on this app"
    assert result["status"] == ("ok" if gate == "qualified" else "degraded")
    assert result["all_sources_live"] is (gate == "qualified")
    assert result["degraded_tiles"] == ([] if gate == "qualified" else ["Governance / restraint"])


@pytest.mark.parametrize("change", ["signer_unready", "unverified", "placeholder",
                                    "identity_rotation"])
def test_health_rechecks_app_observation_before_reusing_composition(
        signal, governance_observation, change):
    """SIMULATED loss or rotation must invalidate without waiting for the TTL."""
    info, _, cache = governance_observation
    assert signal()["all_sources_live"] is True
    assert signal()["all_sources_live"] is True
    assert cache.compositions == 1

    if change == "signer_unready":
        info["signer_health"]["ready"] = False
    elif change == "unverified":
        info["receipt_verification"]["cryptographically_verified"] = False
    elif change == "placeholder":
        info["receipt_verification"]["method"] = "DSSE_PLACEHOLDER"
    else:
        # This fixture supplies a newly qualified observation under another key;
        # it does not keep an old receipt ready after a real runtime key rotation.
        info["signer_health"]["identity"] = "simulated-rotated-key"

    result = signal()

    assert cache.compositions == 2
    still_qualified = change == "identity_rotation"
    assert result["status"] == ("ok" if still_qualified else "degraded")
    assert result["all_sources_live"] is still_qualified
    assert result["degraded_tiles"] == ([] if still_qualified else ["Governance / restraint"])
    governance = next(row for row in cache.value["capabilities"]
                      if row["category"] == "governance")
    assert governance["signer_health"]["signer_identity"] == info["signer_health"]["identity"]
    assert signal() == result
    assert cache.compositions == 2
