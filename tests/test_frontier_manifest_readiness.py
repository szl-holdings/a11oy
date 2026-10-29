"""Fail-closed contracts for Frontier reachability versus runtime readiness."""

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

import szl_energy_ledger
import szl_khipu
import szl_uds_fleet as uds

import a11oy_frontier_page as page
import szl_frontier_manifest as manifest


def _tile(name: str, **extra):
    tile = {
        "name": name,
        "category": "test",
        "status": "OK",
        "label": manifest.MEASURED,
        "ok": True,
        "provenance": {"kind": "test evidence"},
    }
    tile.update(extra)
    return tile


def test_reachable_sources_do_not_imply_operational_readiness(monkeypatch):
    """Stopped and unminted tiles keep the compatibility boolean false."""
    stopped = _tile(
        "operator",
        status="IDLE (operator stopped)",
        running=False,
        operational_evidence={
            "predicate": "operator reports running=true",
            "satisfied": False,
            "reasons": ["operator_stopped"],
        },
    )
    monkeypatch.setattr(
        manifest,
        "_TILE_SPECS",
        [(lambda: stopped, "operator", "test", {"kind": "test"})],
    )
    monkeypatch.setattr(
        manifest,
        "_concept_tile_inference_provenance",
        lambda: _tile(
            "composite",
            status="UNAVAILABLE (no receipt observed)",
            label=manifest.UNAVAILABLE,
            on_artifact_minted=False,
            operational_evidence={
                "predicate": "composite receipt exists and verifies",
                "satisfied": False,
                "reasons": ["artifact_not_minted"],
            },
        ),
    )

    summary = manifest._build_manifest()["summary"]

    assert summary["source_reachability"]["state"] == "REACHABLE"
    assert summary["source_reachability"]["all_sources_reachable"] is True
    assert summary["operational_readiness"]["state"] == "NOT_READY"
    assert summary["operational_readiness"]["ready"] is False
    reasons = {
        reason
        for row in summary["operational_readiness"]["blocked_tiles"]
        for reason in row["reasons"]
    }
    assert "operator_stopped" in reasons
    assert "artifact_not_minted" in reasons
    assert summary["all_sources_live"] is False
    assert summary["all_sources_live_compatibility"] == {
        "deprecated": True,
        "meaning": "legacy alias for operational_readiness.ready; not source reachability",
        "value": False,
    }


def test_readiness_can_only_be_true_when_every_tile_has_positive_evidence(monkeypatch):
    running = _tile(
        "operator",
        status="OK (operator running)",
        running=True,
        operational_evidence={
            "predicate": "operator reports running=true",
            "satisfied": True,
            "reasons": [],
        },
    )
    monkeypatch.setattr(
        manifest,
        "_TILE_SPECS",
        [(lambda: running, "operator", "test", {"kind": "test"})],
    )
    monkeypatch.setattr(
        manifest,
        "_concept_tile_inference_provenance",
        lambda: _tile(
            "composite",
            status="LIVE (receipt observed)",
            on_artifact_minted=True,
            chain_ok=True,
            chain_length=1,
            operational_evidence={
                "predicate": "composite receipt exists and verifies",
                "satisfied": True,
                "reasons": [],
            },
        ),
    )

    summary = manifest._build_manifest()["summary"]

    assert summary["source_reachability"]["all_sources_reachable"] is True
    assert summary["operational_readiness"]["ready"] is True
    assert summary["operational_readiness"]["blocked_tiles"] == []
    assert summary["all_sources_live"] is True


def test_generic_ok_measured_tile_is_not_positive_operational_evidence(monkeypatch):
    """An attractive status string cannot substitute for a bounded predicate."""
    generic = _tile("generic", status="OK")
    monkeypatch.setattr(
        manifest,
        "_TILE_SPECS",
        [(lambda: generic, "generic", "test", {"kind": "test"})],
    )
    monkeypatch.setattr(
        manifest,
        "_concept_tile_inference_provenance",
        lambda: _tile(
            "composite",
            status="LIVE",
            operational_evidence={
                "predicate": "receipt exists",
                "satisfied": True,
                "reasons": [],
            },
        ),
    )

    summary = manifest._build_manifest()["summary"]

    assert summary["source_reachability"]["all_sources_reachable"] is True
    assert summary["operational_readiness"]["ready"] is False
    blocked = summary["operational_readiness"]["blocked_tiles"]
    generic_row = next(row for row in blocked if row["name"] == "generic")
    assert generic_row["reasons"] == ["explicit_operational_evidence_missing"]
    assert summary["all_sources_live"] is False


def test_satisfied_flag_without_a_bounded_predicate_is_not_evidence():
    generic = _tile(
        "generic",
        operational_evidence={"satisfied": True, "reasons": []},
    )

    ready, reasons = manifest._tile_operational_readiness(generic)

    assert ready is False
    assert reasons == ["explicit_operational_predicate_missing"]


def test_signature_required_tile_blocks_without_crypto_verification():
    integrity_only = _tile(
        "integrity-only receipt",
        signature_required=True,
        signature_verified=False,
        operational_evidence={
            "predicate": "receipt exists and signature verifies",
            "satisfied": True,
            "reasons": [],
        },
    )

    ready, reasons = manifest._tile_operational_readiness(integrity_only)

    assert ready is False
    assert reasons == ["cryptographic_signature_not_verified"]


def test_static_governance_declaration_is_not_runtime_signer_evidence():
    ready, reasons, evidence = manifest._runtime_signature_readiness({
        "doctrine": {"signed_receipts": True, "version": "v11"},
    })

    assert ready is False
    assert "signer_health_not_observed" in reasons
    assert "cryptographic_signature_not_verified" in reasons
    assert evidence["cryptographically_verified"] is False


def test_governance_requires_observed_signer_and_crypto_receipt_verification():
    ready, reasons, evidence = manifest._runtime_signature_readiness({
        "signer_health": {
            "observed_this_process": True,
            "ready": True,
            "identity": "did:web:example.test",
        },
        "receipt_verification": {
            "observed_this_process": True,
            "cryptographically_verified": True,
            "signature_count": 1,
            "method": "ECDSA-P256-SHA256 DSSE PAE",
        },
    })

    assert ready is True
    assert reasons == []
    assert evidence["signer_identity"] == "did:web:example.test"


def test_energy_ledger_is_named_integrity_only_not_signed(monkeypatch):
    monkeypatch.setattr(
        szl_energy_ledger,
        "handle_ledger",
        lambda: {
            "chain": {"length": 1, "links_intact": True},
            "persistence": {"survives_redeploy": True, "label": manifest.MEASURED},
            "receipts": [{"entry_digest": "a" * 64}],
        },
    )

    tile = manifest._tile_energy_ledger()

    assert tile["name"] == "Tamper-evident energy ledger"
    assert "signed" not in tile["status"].lower()
    assert "integrity-only" in tile["provenance"]["kind"]
    assert tile["provenance"]["signature_status"] == "NOT_VERIFIED_INTEGRITY_ONLY"


def test_placeholder_composite_remains_integrity_only_and_not_ready(monkeypatch):
    class IntegrityOnlyDag:
        def verify_chain(self):
            return {"ok": True, "depth": 1, "broken_at": None}

        def depth(self):
            return 1

        def head(self):
            return "b" * 64

        def tail(self, _count):
            return [{
                "action": "provenance.composite",
                "digest": "c" * 64,
                "signature": "DSSE_PLACEHOLDER",
            }]

    monkeypatch.setattr(szl_khipu, "get_dag", lambda *_args, **_kwargs: IntegrityOnlyDag())

    tile = manifest._concept_tile_inference_provenance()
    ready, reasons = manifest._tile_operational_readiness(tile)

    assert tile["on_artifact_minted"] is True
    assert tile["label"] == manifest.UNAVAILABLE
    assert tile["signature_verified"] is False
    assert tile["provenance"]["signature_status"] == "NOT_VERIFIED_INTEGRITY_ONLY"
    assert "DSSE_PLACEHOLDER is not a signature" in tile["note"]
    assert ready is False
    assert "cryptographic_signature_not_verified" in reasons


def test_empty_compute_fabric_is_unavailable_not_idle_zero(monkeypatch):
    import szl_backend_hardening as bh

    monkeypatch.setattr(
        bh,
        "probe_fabric_pool",
        lambda: {"nodes": [{"reachable": False, "kind": "gpu"}], "cached_at": None},
    )
    tile = manifest._tile_compute_fabric()
    assert "UNAVAILABLE" in tile["status"]
    assert "IDLE" not in tile["status"]
    assert tile["nodes_reachable"] == 0


def test_non_sovereign_gpu_transport_does_not_establish_sovereign_readiness(monkeypatch):
    import szl_backend_hardening as bh

    monkeypatch.setattr(bh, "probe_fabric_pool", lambda: {
        "scope": "TRANSPORT_REACHABILITY",
        "nodes": [{"name": "chaski", "kind": "hf-gpu", "reachable": True,
                   "sovereign": False, "probe_kind": "TCP_CONNECT"}],
        "counts": {"nodes_total": 1, "nodes_reachable": 1,
                   "gpu_nodes_reachable": 1, "sovereign_gpu_nodes_reachable": 0},
    })

    tile = manifest._tile_compute_fabric()
    ready, reasons = manifest._tile_operational_readiness(tile)

    assert tile["gpu_reachable"] == 1
    assert tile["sovereign_gpu_reachable"] == 0
    assert tile["counts_consistent"] is True
    assert "0 configured sovereign GPU" in tile["status"]
    assert ready is False
    assert "no_sovereign_gpu_reachable" in reasons
    assert "model_inference_not_verified_by_transport_probe" in reasons


def test_sovereign_socket_is_transport_evidence_only(monkeypatch):
    import szl_backend_hardening as bh

    monkeypatch.setattr(bh, "probe_fabric_pool", lambda: {
        "scope": "TRANSPORT_REACHABILITY",
        "nodes": [{"name": "worker", "kind": "gpu", "reachable": True,
                   "sovereign": True, "probe_kind": "TCP_CONNECT",
                   "inference_verified": False, "ownership_verified": False}],
        "counts": {"nodes_total": 1, "nodes_reachable": 1,
                   "gpu_nodes_reachable": 1, "sovereign_gpu_nodes_reachable": 1,
                   "inference_verified_nodes": 0},
    })

    tile = manifest._tile_compute_fabric()
    ready, reasons = manifest._tile_operational_readiness(tile)

    assert tile["sovereign_gpu_reachable"] == 1
    assert tile["counts_consistent"] is True
    assert tile["measurement_scope"] == "TRANSPORT_REACHABILITY_ONLY"
    assert tile["inference_verified"] is False
    assert tile["ownership_verified"] is False
    assert ready is False
    assert "no_sovereign_gpu_reachable" not in reasons
    assert "sovereign_ownership_not_verified" in reasons
    assert "model_inference_not_verified_by_transport_probe" in reasons


def test_fabric_summary_flags_cannot_substitute_for_node_or_inference_evidence(monkeypatch):
    import szl_backend_hardening as bh

    monkeypatch.setattr(bh, "probe_fabric_pool", lambda: {
        "scope": "TRANSPORT_REACHABILITY",
        "nodes": [{"name": "service-host", "kind": "cpu-host", "reachable": True,
                   "sovereign": False, "probe_kind": "PROCESS_SELF"}],
        "counts": {"nodes_total": 1, "nodes_reachable": 1,
                   "gpu_nodes_reachable": 1, "sovereign_gpu_nodes_reachable": 1,
                   "inference_verified_nodes": 1},
        "inference_readiness": {"ready": True},
    })

    tile = manifest._tile_compute_fabric()
    ready, reasons = manifest._tile_operational_readiness(tile)

    assert tile["gpu_reachable"] == 0
    assert tile["sovereign_gpu_reachable"] == 0
    assert tile["inference_verified_nodes"] == 0
    assert tile["counts_consistent"] is False
    assert ready is False
    assert "fabric_probe_counts_missing_or_inconsistent" in reasons


_RENTED_NODE = "massed-a6000-test"


def _rented_pool(reachable=True, sovereign=False, reported_sovereign=0):
    return {
        "scope": "TRANSPORT_REACHABILITY",
        "cached_at": "2026-10-28T00:00:00Z",
        "nodes": [{"name": _RENTED_NODE, "kind": "rented-gpu", "reachable": reachable,
                   "sovereign": sovereign, "rented": True, "provider": "Massed Compute",
                   "endpoint": "rented GPU · Massed Compute", "probe_kind": "TCP_CONNECT",
                   "inference_verified": False, "ownership_verified": False}],
        "counts": {"nodes_total": 1, "nodes_reachable": int(reachable),
                   "gpu_nodes_reachable": int(reachable),
                   "sovereign_gpu_nodes_reachable": reported_sovereign,
                   "rented_gpu_nodes_reachable": int(reachable),
                   "inference_verified_nodes": 0},
    }


def _write_pool_receipt(tmp_path, monkeypatch, *, node_id=_RENTED_NODE, age=timedelta(0),
                        signer=None):
    """Write one compute-pool/v1 inference receipt signed by a synthetic attester key."""
    import szl_compute_pool_contract as contract
    import szl_dsse

    trusted = ec.generate_private_key(ec.SECP256R1())
    public = trusted.public_key()
    monkeypatch.setenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM", public.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode())
    monkeypatch.setenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256", hashlib.sha256(public.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest())
    monkeypatch.setenv("A11OY_COMPUTE_POOL_RECEIPT_DIR", str(tmp_path))
    observed = datetime.now(timezone.utc).replace(microsecond=0) - age
    payload = {
        "schema_version": contract.RECEIPT_SCHEMA,
        "node_id": node_id,
        "model_id": "qwen3-8b:test",
        "model_digest_sha256": "a" * 64,
        "observed_at": observed.isoformat().replace("+00:00", "Z"),
        "request_sha256": "b" * 64,
        "response_sha256": "c" * 64,
        "duration_ms": 41.5,
        "success": True,
        "serving": False,
        "bounds": {"timeout_ms": 5000, "max_input_tokens": 64, "max_output_tokens": 32},
        "issuer": "a11oy-pool-attester",
        "audience": "a11oy-compute-pool",
        "predicate_type": "szl.compute-pool.inference-qualification/v1",
        "measurement_contract": "szl.compute-pool.measurement-contract/v1",
    }
    body = szl_dsse.canonical_json(payload)
    signature = (signer or trusted).sign(
        szl_dsse.pae(contract.RECEIPT_PAYLOAD_TYPE, body), ec.ECDSA(hashes.SHA256()))
    (tmp_path / "receipt.dsse.json").write_text(json.dumps({
        "payloadType": contract.RECEIPT_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [{"keyid": "a11oy-pool-attester-v1",
                        "sig": base64.b64encode(signature).decode("ascii")}],
    }), encoding="utf-8")


def test_verified_inference_receipt_on_reachable_rented_gpu_clears_only_inference_reason(
        tmp_path, monkeypatch):
    import szl_backend_hardening as bh

    monkeypatch.setattr(bh, "probe_fabric_pool", lambda: _rented_pool())
    _write_pool_receipt(tmp_path, monkeypatch)

    tile = manifest._tile_compute_fabric()
    ready, reasons = manifest._tile_operational_readiness(tile)

    assert tile["inference_verified"] is True
    assert tile["inference_verified_nodes"] == 1
    assert tile["inference_evidence"][0]["node"] == _RENTED_NODE
    assert tile["inference_evidence"][0]["model_id"] == "qwen3-8b:test"
    assert "model_inference_not_verified_by_transport_probe" not in reasons
    # Rented capacity never satisfies sovereignty or ownership.
    assert tile["sovereign_gpu_reachable"] == 0
    assert tile["rented_gpu_reachable"] == 1
    assert tile["ownership_verified"] is False
    assert "no_sovereign_gpu_reachable" in reasons
    assert "sovereign_ownership_not_verified" in reasons
    assert ready is False


@pytest.mark.parametrize("case", ["unreachable", "untrusted_key", "stale", "other_node"])
def test_inference_reason_stays_without_bound_fresh_verified_receipt(tmp_path, monkeypatch, case):
    import szl_backend_hardening as bh

    monkeypatch.setattr(bh, "probe_fabric_pool",
                        lambda: _rented_pool(reachable=case != "unreachable"))
    _write_pool_receipt(
        tmp_path, monkeypatch,
        node_id="some-other-node" if case == "other_node" else _RENTED_NODE,
        age=timedelta(hours=2) if case == "stale" else timedelta(0),
        signer=ec.generate_private_key(ec.SECP256R1()) if case == "untrusted_key" else None)

    tile = manifest._tile_compute_fabric()
    _ready, reasons = manifest._tile_operational_readiness(tile)

    assert tile["inference_verified"] is False
    assert tile["inference_verified_nodes"] == 0
    assert "model_inference_not_verified_by_transport_probe" in reasons


def test_rented_gpu_marked_sovereign_never_counts_as_sovereign(monkeypatch):
    import szl_backend_hardening as bh

    monkeypatch.setattr(bh, "probe_fabric_pool",
                        lambda: _rented_pool(sovereign=True, reported_sovereign=1))

    tile = manifest._tile_compute_fabric()
    _ready, reasons = manifest._tile_operational_readiness(tile)

    assert tile["sovereign_gpu_reachable"] == 0
    assert "no_sovereign_gpu_reachable" in reasons
    assert "sovereign_ownership_not_verified" in reasons


def test_importable_uds_source_does_not_establish_signed_bundle(monkeypatch):
    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("a UDS capability read must not fetch or mint an artifact")

    monkeypatch.setattr(uds.urllib.request, "urlopen", unexpected_network)
    tile = manifest._tile_uds_bundle()
    ready, reasons = manifest._tile_operational_readiness(tile)

    assert tile["ok"] is True  # The narrative source is available.
    assert tile["label"] == manifest.UNAVAILABLE
    assert tile["signature_verified"] is False
    assert tile["artifact_observed"] is False
    assert tile["provenance"]["artifact_digest"] is None
    assert tile["provenance"]["signature_status"] == "NOT_OBSERVED"
    assert tile["provenance"]["verification_required"]
    assert ready is False
    assert "runtime_attestation_receipt_not_observed" in reasons


def test_reachable_uds_references_do_not_upgrade_runtime_evidence(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setattr(uds, "_start_warmer", lambda: None)
    monkeypatch.setattr(uds, "_sources_live", lambda sources: [
        {"reachable": True, "mode": "live"} for _source in sources
    ])
    app = FastAPI()
    uds.register(app)
    client = TestClient(app)

    index = client.get("/api/a11oy/v1/uds")
    sources = client.get("/api/a11oy/v1/uds/sources/live")

    assert index.status_code == sources.status_code == 200
    assert "Ed25519" not in index.text
    assert "Every a11oy deploy emits" not in index.text
    for response in (index, sources):
        for gap in response.json()["gaps"]:
            assert gap["capability_status"] == "UNAVAILABLE"
            assert gap["runtime_evidence"]["state"] == "UNOBSERVED"
            assert gap["runtime_evidence"]["observed_this_process"] is False
            assert gap["runtime_evidence"]["verification_required"]
    for gap in sources.json()["gaps"]:
        assert gap["sources_reachable"] == gap["sources_total"] > 0


def test_frontier_page_renders_both_contracts_without_legacy_live_inference():
    html = page._page_html("a11oy")

    assert "source reachability" in html
    assert "operational readiness" in html
    assert "all sources live:" not in html
    assert "all_sources_live=" not in html
    assert "s.source_reachability" in html
    assert "s.operational_readiness" in html


def test_anonymous_anatomy_loop_read_does_not_append_energy_provenance(monkeypatch):
    """A public GET must not mint the receipts the provenance tile counts."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import szl_anatomy_loop as anatomy
    import szl_energy_provenance as ep

    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("an anatomy read must stay offline in this test")

    monkeypatch.setattr(anatomy.urllib.request, "urlopen", unexpected_network)
    monkeypatch.setattr(anatomy, "_read_intake", lambda: anatomy._sample_posture())
    monkeypatch.setattr(anatomy, "_probe_merged_meter_joules", lambda: None)
    monkeypatch.setattr(ep, "_CHAIN", ep.EnergyProvenanceChain())
    app = FastAPI()
    anatomy.register(app)
    client = TestClient(app)

    for _ in range(2):
        response = client.get("/api/a11oy/v1/anatomy/loop")
        assert response.status_code == 200
        assert response.json()["last_receipt_id"]

    tile = manifest._tile_energy_provenance()
    ready, reasons = manifest._tile_operational_readiness(tile)

    assert len(ep._CHAIN) == 0
    assert ready is False
    assert "no_chain_entries" in reasons


def test_sample_provenance_receipts_never_satisfy_the_provenance_tile(monkeypatch):
    import szl_energy_provenance as ep

    chain = ep.EnergyProvenanceChain()
    chain.append(output="cycle", energy_source="curtailed-sample", joules_est=0.0)
    chain.append(output="job", energy_source="grid", joules_est=1.5)
    monkeypatch.setattr(ep, "_CHAIN", chain)

    tile = manifest._tile_energy_provenance()
    ready, reasons = manifest._tile_operational_readiness(tile)

    assert chain.verify()["ok"] is True
    assert ready is False
    assert tile["operational_evidence"]["satisfied"] is False
    assert "no_measured_entries" in reasons
    assert tile["length"] == 2
    assert tile["measured_entries"] == 0


def test_provenance_tile_counts_only_measured_non_sample_entries(monkeypatch):
    import szl_energy_provenance as ep

    class Chain:
        def __init__(self, entries):
            self._entries = entries

        def summary(self):
            return {"length": len(self._entries), "verify": {"ok": True},
                    "status": "VERIFIED", "head_hash": "d" * 64, "link_rule": "test"}

        def entries(self):
            return list(self._entries)

    mislabeled = {"energy_source": "curtailed-sample", "joules_est_label": "MEASURED"}
    measured = {"energy_source": "grid", "joules_est_label": "MEASURED"}

    monkeypatch.setattr(ep, "_CHAIN", Chain([mislabeled]))
    blocked = manifest._tile_energy_provenance()
    monkeypatch.setattr(ep, "_CHAIN", Chain([mislabeled, measured]))
    satisfied = manifest._tile_energy_provenance()

    assert blocked["measured_entries"] == 0
    assert manifest._tile_operational_readiness(blocked)[0] is False
    assert satisfied["measured_entries"] == 1
    assert manifest._tile_operational_readiness(satisfied) == (True, [])


def _operator_status(**overrides):
    status = {
        "running": True,
        "stub_mode": False,
        "jobs_done": 4,
        "joules_measured_total": 0.0,
        "measured_jobs": 0,
        "node_status": {"rtx": "computing"},
    }
    status.update(overrides)
    return status


def test_running_stub_operator_without_a_gpu_is_not_ready(monkeypatch):
    import szl_energy_operator as eo

    monkeypatch.setattr(eo, "handle_status", lambda: _operator_status(
        stub_mode=True,
        node_status={"rtx": "DEGRADED", "local-stub": "computing (STUB)"},
    ))

    tile = manifest._tile_energy_operator()
    ready, reasons = manifest._tile_operational_readiness(tile)

    assert ready is False
    assert "no_gpu_reachable" in reasons
    assert "no_measured_jobs" in reasons
    assert tile["gpu_nodes_reachable"] == 0


def test_running_operator_with_a_gpu_needs_a_measured_job(monkeypatch):
    import szl_energy_operator as eo

    monkeypatch.setattr(eo, "handle_status", lambda: _operator_status())
    tile = manifest._tile_energy_operator()
    ready, reasons = manifest._tile_operational_readiness(tile)

    assert ready is False
    assert reasons == ["no_measured_jobs"]
    assert tile["gpu_nodes_reachable"] == 1

    monkeypatch.setattr(eo, "handle_status", lambda: _operator_status(
        measured_jobs=1, joules_measured_total=2.5))
    measured = manifest._tile_energy_operator()

    assert manifest._tile_operational_readiness(measured) == (True, [])
