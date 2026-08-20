"""Fail-closed contracts for Frontier reachability versus runtime readiness."""

import szl_energy_ledger
import szl_khipu

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


def test_frontier_page_renders_both_contracts_without_legacy_live_inference():
    html = page._page_html("a11oy")

    assert "source reachability" in html
    assert "operational readiness" in html
    assert "all sources live:" not in html
    assert "all_sources_live=" not in html
    assert "s.source_reachability" in html
    assert "s.operational_readiness" in html
