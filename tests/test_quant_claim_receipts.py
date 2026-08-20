"""Fail-closed quant-claim receipt and public-surface regressions.

These tests create only ephemeral negative fixtures. They do not benchmark, use a
GPU/model/NIM endpoint, publish an artifact, or provide a positive production receipt.
"""

import base64
import copy
import hashlib
import importlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

import szl_dsse
import szl_gpu_quant
import szl_quant_claims as claims


_PRIV_ENV = "SZL_COSIGN_PRIVATE_KEY_PEM"
_LEGACY_ENV = "SZL_COSIGN_PRIVATE_PEM"
_HEX64 = "a" * 64


def _keypair() -> tuple[str, str]:
    private = ec.generate_private_key(ec.SECP256R1())
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return private_pem, public_pem


def _benchmark_run(claim: dict, *, protocol_id: str | None = None, hardware_class: str | None = None, fresh_until: datetime | None = None) -> dict:
    now = datetime.now(timezone.utc)
    freshness_deadline = fresh_until or (now + timedelta(hours=1))
    if freshness_deadline <= now:
        reviewed_at = freshness_deadline - timedelta(seconds=5)
    else:
        reviewed_at = now - timedelta(seconds=5)
    completed_at = reviewed_at - timedelta(seconds=5)
    started_at = completed_at - timedelta(minutes=2)
    preregistered_at = started_at - timedelta(minutes=1)
    unit = claim["protocol"]["unit"]
    dataset_digest = "sha256:" + _HEX64
    protocol_manifest = {
        "id": protocol_id or claim["protocol"]["id"],
        "version": "1.0.0",
        "metric": claim["protocol"]["metric"],
        "unit": unit,
        "preregistered_at": preregistered_at.isoformat(),
        "minimum_trials": 3,
        "hardware_class": hardware_class or claim["required_hardware_class"],
        "requires_energy": claim["protocol"]["requires_energy"],
        "dataset_manifest_sha256": dataset_digest,
    }
    protocol_digest = "sha256:" + hashlib.sha256(
        json.dumps(protocol_manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    run = {
        "schema_version": claims.RUN_SCHEMA_VERSION,
        "run_id": "negative-fixture-run-1",
        "claim_id": claim["claim_id"],
        "protocol": {
            "id": protocol_id or claim["protocol"]["id"],
            "version": "1.0.0",
            "sha256": protocol_digest,
            "preregistered_at": preregistered_at.isoformat(),
            "manifest": protocol_manifest,
        },
        "subject": {"artifact_id": "subject", "revision": "rev-1", "sha256": "sha256:" + _HEX64, "license": "Apache-2.0"},
        "baseline": {"artifact_id": "baseline", "revision": "rev-1", "sha256": "sha256:" + _HEX64, "license": "Apache-2.0"},
        "dataset": {"manifest_sha256": dataset_digest, "split": "held-out", "seeds": [7], "rights_admitted": True},
        "hardware": {
            "class": hardware_class or claim["required_hardware_class"],
            "devices": [{"kind": "GPU", "model": "negative-test-device", "count": 1}],
            "driver": "test-only",
            "cuda": "test-only",
        },
        "software": {"git_commit": "b" * 40, "container_digest": "sha256:" + _HEX64, "lock_sha256": "sha256:" + _HEX64},
        "execution": {
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "warmup_trials": 1,
            "measured_trials": 3,
            "config": {"fixture": "negative-only"},
        },
        "raw_trials": [
            {"trial": 1, "value": 1.0, "unit": unit},
            {"trial": 2, "value": 1.1, "unit": unit},
            {"trial": 3, "value": 1.2, "unit": unit},
        ],
        "measurement": {
            "metric": claim["protocol"]["metric"],
            "value": 1.1,
            "unit": unit,
            "estimator": "median",
            "confidence_interval": None,
            "summary_tolerance": 1e-12,
        },
        "correctness": {"passed": True, "checks": [{"name": "parity", "passed": True, "tolerance": "exact"}]},
        "energy": {"status": "NOT_OBSERVABLE", "blocker": "negative fixture has no real exporter delta"},
        "freshness": {"fresh_until": freshness_deadline.isoformat()},
        "review": {"status": "APPROVED", "reviewer": "negative-test", "reviewed_at": reviewed_at.isoformat()},
        "artifacts": {"result_sha256": "", "result_bundle": {}},
    }
    bundle = {
        "raw_trials": copy.deepcopy(run["raw_trials"]),
        "measurement": copy.deepcopy(run["measurement"]),
        "correctness": copy.deepcopy(run["correctness"]),
        "energy": copy.deepcopy(run["energy"]),
    }
    run["artifacts"]["result_bundle"] = bundle
    run["artifacts"]["result_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return run


def _signed_envelope(monkeypatch, payload: dict) -> dict:
    private_pem, public_pem = _keypair()
    monkeypatch.delenv(_LEGACY_ENV, raising=False)
    monkeypatch.setenv(_PRIV_ENV, private_pem)
    importlib.reload(szl_dsse)
    monkeypatch.setattr(szl_dsse, "COSIGN_PUBLIC_PEM", public_pem, raising=True)
    return szl_dsse.sign_payload(payload, claims.RUN_PAYLOAD_TYPE)


def _rebind_result_bundle(run: dict) -> None:
    bundle = {
        "raw_trials": copy.deepcopy(run["raw_trials"]),
        "measurement": copy.deepcopy(run["measurement"]),
        "correctness": copy.deepcopy(run["correctness"]),
        "energy": copy.deepcopy(run["energy"]),
    }
    run["artifacts"]["result_bundle"] = bundle
    run["artifacts"]["result_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _rebind_protocol_manifest(run: dict) -> None:
    manifest = run["protocol"]["manifest"]
    run["protocol"]["id"] = manifest["id"]
    run["protocol"]["version"] = manifest["version"]
    run["protocol"]["preregistered_at"] = manifest["preregistered_at"]
    run["protocol"]["sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _store(tmp_path: Path, envelope: dict) -> tuple[str, claims.DigestReceiptLoader]:
    raw = claims.canonical_envelope_bytes(envelope)
    receipt_id = "sha256:" + hashlib.sha256(raw).hexdigest()
    (tmp_path / (receipt_id.split(":", 1)[1] + ".json")).write_bytes(raw)
    return receipt_id, claims.DigestReceiptLoader(tmp_path)


def _bind(claim: dict, receipt_id: str) -> dict:
    bound = copy.deepcopy(claim)
    bound["measurement_receipt_id"] = receipt_id
    bound["measurement_gate"] = {"promoted": False, "reason": "PENDING_VERIFICATION", "receipt_id": receipt_id}
    return claims.validate_claim(bound)


def test_versioned_schemas_are_json_and_closed_at_the_root() -> None:
    root = Path(__file__).resolve().parents[1] / "schemas" / "quant-claims"
    claim_schema = json.loads((root / "claim.v1.schema.json").read_text(encoding="utf-8"))
    run_schema = json.loads((root / "benchmark-run.v1.schema.json").read_text(encoding="utf-8"))
    assert claim_schema["$schema"].endswith("2020-12/schema")
    assert run_schema["$schema"].endswith("2020-12/schema")
    assert claim_schema["additionalProperties"] is False
    assert run_schema["additionalProperties"] is False
    assert claim_schema["properties"]["external_report"]["additionalProperties"] is False
    assert run_schema["properties"]["measurement"]["$ref"] == "#/$defs/measurement"
    assert run_schema["$defs"]["measurement"]["additionalProperties"] is False
    assert run_schema["$defs"]["correctness"]["additionalProperties"] is False
    assert run_schema["properties"]["artifacts"]["properties"]["result_bundle"]["additionalProperties"] is False


def test_public_panel_defaults_every_claim_to_roadmap(monkeypatch) -> None:
    def _forbid_signing(*_args, **_kwargs):
        raise AssertionError("read-only claims GET attempted to sign")

    monkeypatch.setattr(szl_dsse, "sign_payload", _forbid_signing)
    monkeypatch.setattr(szl_gpu_quant, "_sign_payload", _forbid_signing)
    panel = szl_gpu_quant.verify_claims_panel()
    assert panel["schema_version"] == "szl.quant.claim-panel/v1"
    assert len(panel["rows"]) == 6
    assert all(row["szl_label"] == "ROADMAP" for row in panel["rows"])
    assert all(row["szl_measured"] is None for row in panel["rows"])
    assert all(row["measurement_receipt_id"] is None for row in panel["rows"])
    assert all("nvidia_datasheet" not in row for row in panel["rows"])
    assert "measured > datasheet" not in json.dumps(panel)


def test_external_claim_semantics_are_narrow_and_primary_sourced() -> None:
    registry = {claim["claim_id"]: claim for claim in claims.claim_registry()}
    assert registry["nemotron-ultra-cost-to-task"]["claim"].endswith("cost to task completion")
    assert "accuracy" not in registry["nemotron-ultra-cost-to-task"]["claim"].lower()
    assert "PinchBench" in registry["nemotron-ultra-pinchbench"]["claim"]
    assert "RULER at 1M" in registry["nemotron-ultra-ruler-1m"]["claim"]
    assert registry["ripserpp-speedup"]["external_report"]["source"]["kind"] == "ACADEMIC_PAPER"
    assert all(
        claim["external_report"]["source"]["url"].startswith("https://")
        for claim in registry.values()
    )


def test_absent_digest_addressed_receipt_remains_roadmap(tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    receipt_id = "sha256:" + ("0" * 64)
    result = claims.resolve_claim(_bind(claim, receipt_id), claims.DigestReceiptLoader(tmp_path))
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "RECEIPT_ABSENT"


def test_digest_mismatch_remains_roadmap(tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    receipt_id = "sha256:" + ("0" * 64)
    (tmp_path / (("0" * 64) + ".json")).write_text("{}", encoding="utf-8")
    result = claims.resolve_claim(_bind(claim, receipt_id), claims.DigestReceiptLoader(tmp_path))
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "RECEIPT_DIGEST_MISMATCH"


def test_symlink_receipt_is_rejected(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    payload = _benchmark_run(claim)
    target = tmp_path / "outside.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    receipt_id = "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest()
    link = tmp_path / (receipt_id.split(":", 1)[1] + ".json")
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("host does not permit symlink creation")
    result = claims.resolve_claim(_bind(claim, receipt_id), claims.DigestReceiptLoader(tmp_path))
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "RECEIPT_SYMLINK_REJECTED"


def test_opened_file_identity_swap_is_rejected(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    envelope = {
        "payloadType": claims.RUN_PAYLOAD_TYPE,
        "payload": base64.b64encode(b"{}").decode("ascii"),
        "signatures": [],
        "signed": False,
    }
    receipt_id, loader = _store(tmp_path, envelope)
    original_samestat = claims.os.path.samestat
    calls = {"count": 0}

    def _swap_on_open(left, right):
        calls["count"] += 1
        if calls["count"] == 2:
            return False
        return original_samestat(left, right)

    monkeypatch.setattr(claims.os.path, "samestat", _swap_on_open)
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "RECEIPT_IDENTITY_CHANGED"


def test_unsigned_receipt_remains_roadmap(tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    payload = _benchmark_run(claim)
    envelope = {
        "payloadType": claims.RUN_PAYLOAD_TYPE,
        "payload": base64.b64encode(szl_dsse.canonical_json(payload)).decode("ascii"),
        "signatures": [],
        "signed": False,
    }
    receipt_id, loader = _store(tmp_path, envelope)
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"].startswith("DSSE_")


def test_stale_signed_receipt_remains_roadmap(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    payload = _benchmark_run(claim, fresh_until=datetime.now(timezone.utc) - timedelta(seconds=1))
    receipt_id, loader = _store(tmp_path, _signed_envelope(monkeypatch, payload))
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "STALE_RECEIPT"


def test_tampered_signed_receipt_remains_roadmap(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    envelope = _signed_envelope(monkeypatch, _benchmark_run(claim))
    tampered = _benchmark_run(claim)
    tampered["measurement"]["value"] = 9999.0
    envelope["payload"] = base64.b64encode(szl_dsse.canonical_json(tampered)).decode("ascii")
    receipt_id, loader = _store(tmp_path, envelope)
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"].startswith("DSSE_")


def test_wrong_keyid_receipt_remains_roadmap(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    envelope = _signed_envelope(monkeypatch, _benchmark_run(claim))
    envelope["signatures"][0]["keyid"] = "wrong-key"
    receipt_id, loader = _store(tmp_path, envelope)
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "DSSE_VERIFICATION_FAILED"


def test_wrong_protocol_receipt_remains_roadmap(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    envelope = _signed_envelope(monkeypatch, _benchmark_run(claim, protocol_id="different-protocol-v1"))
    receipt_id, loader = _store(tmp_path, envelope)
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "WRONG_PROTOCOL"


def test_wrong_hardware_receipt_remains_roadmap(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    envelope = _signed_envelope(monkeypatch, _benchmark_run(claim, hardware_class="UNQUALIFIED_GPU"))
    receipt_id, loader = _store(tmp_path, envelope)
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "WRONG_HARDWARE_CLASS"


def test_result_bundle_digest_mismatch_remains_roadmap(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    payload = _benchmark_run(claim)
    payload["artifacts"]["result_sha256"] = "sha256:" + ("0" * 64)
    receipt_id, loader = _store(tmp_path, _signed_envelope(monkeypatch, payload))
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "RESULT_BUNDLE_DIGEST_MISMATCH"


def test_summary_recompute_mismatch_remains_roadmap(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    payload = _benchmark_run(claim)
    payload["measurement"]["value"] = 9.9
    _rebind_result_bundle(payload)
    receipt_id, loader = _store(tmp_path, _signed_envelope(monkeypatch, payload))
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "SUMMARY_RECOMPUTE_MISMATCH"


def test_duplicate_trial_id_remains_roadmap(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    payload = _benchmark_run(claim)
    payload["raw_trials"][2]["trial"] = 2
    _rebind_result_bundle(payload)
    receipt_id, loader = _store(tmp_path, _signed_envelope(monkeypatch, payload))
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "DUPLICATE_TRIAL_ID"


def test_protocol_registered_after_start_remains_roadmap(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    payload = _benchmark_run(claim)
    payload["protocol"]["manifest"]["preregistered_at"] = payload["execution"]["completed_at"]
    _rebind_protocol_manifest(payload)
    receipt_id, loader = _store(tmp_path, _signed_envelope(monkeypatch, payload))
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "PREREGISTRATION_AFTER_START"


def test_protocol_manifest_hash_mismatch_remains_roadmap(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    payload = _benchmark_run(claim)
    payload["protocol"]["sha256"] = "sha256:" + ("0" * 64)
    receipt_id, loader = _store(tmp_path, _signed_envelope(monkeypatch, payload))
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "PROTOCOL_MANIFEST_DIGEST_MISMATCH"


def test_energy_claim_requires_matched_observable_delta(monkeypatch, tmp_path: Path) -> None:
    claim = copy.deepcopy(claims.claim_registry()[0])
    claim["protocol"]["requires_energy"] = True
    claims.validate_claim(claim)
    payload = _benchmark_run(claim)
    receipt_id, loader = _store(tmp_path, _signed_envelope(monkeypatch, payload))
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "ENERGY_NOT_OBSERVABLE"


def test_invalid_energy_delta_remains_roadmap(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    payload = _benchmark_run(claim)
    payload["energy"] = {
        "status": "MEASURED_DELTA",
        "exporter_id": "test-exporter",
        "sampled_at_start": payload["execution"]["started_at"],
        "sampled_at_end": payload["execution"]["completed_at"],
        "joules_before": 10.0,
        "joules_after": 9.0,
        "work_units_before": 100.0,
        "work_units_after": 101.0,
        "work_unit": "tokens",
        "fresh": True,
    }
    receipt_id, loader = _store(tmp_path, _signed_envelope(monkeypatch, payload))
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "ENERGY_DELTA_INVALID"


def test_unknown_benchmark_field_is_rejected_before_promotion(monkeypatch, tmp_path: Path) -> None:
    claim = claims.claim_registry()[0]
    payload = _benchmark_run(claim)
    payload["unreviewed_extra"] = True
    envelope = _signed_envelope(monkeypatch, payload)
    receipt_id, loader = _store(tmp_path, envelope)
    result = claims.resolve_claim(_bind(claim, receipt_id), loader)
    assert result["szl_label"] == "ROADMAP"
    assert result["measurement_gate"]["reason"] == "BENCHMARK_SCHEMA_INVALID"
