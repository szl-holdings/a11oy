#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic offline crypto fixtures only: no runtime key, token or request."""
import base64
import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import szl_dsse  # Only its pure canonical JSON, PAE and public-key ID helpers are used.

SPEC = importlib.util.spec_from_file_location("execution_acceptance", ROOT / "tools/execution_acceptance.py")
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)
NOW = datetime(2026, 10, 15, 3, 0, tzinfo=timezone.utc)


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def keypair():
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                       serialization.PublicFormat.SubjectPublicKeyInfo)
    return key, pem, szl_dsse.keyid_for_public_pem(pem.decode())


def sign(payload, payload_type, key, key_id):
    body = szl_dsse.canonical_json(payload)
    pae = szl_dsse.pae(payload_type, body)
    return {"payloadType": payload_type, "payload": base64.b64encode(body).decode(),
            "signatures": [{"keyid": key_id, "sig": base64.b64encode(
                key.sign(pae, ec.ECDSA(hashes.SHA256()))).decode()}]}


@pytest.fixture
def sample():
    authority, authority_pem, authority_id = keypair()
    runtime, runtime_pem, runtime_id = keypair()
    context = module.AdmissionContext("a" * 40, "b" * 40, "synthetic-boot", "c" * 64,
                                      authority_pem, authority_id, runtime_pem, runtime_id)
    bindings = {"origin": module.ORIGIN, "source_revision": context.source_revision,
                "runtime_revision": context.runtime_revision,
                "runtime_boot_id": context.runtime_boot_id, "run_nonce": context.run_nonce}
    bodies = {case_id: {"fixture": "SYNTHETIC_NOT_EXECUTED"} for case_id in module.CONTRACTS}
    bodies["eval-run"] = {"model_id": "synthetic-model", "suite": "synthetic-suite",
                          "execution_mode": "live"}
    bodies["agentloop-run"] = {"model_id": "synthetic-model", "eval_suite": "synthetic-suite",
                               "task": "Synthetic no-request fixture", "mode": "chat",
                               "sandbox": False, "max_retries": 0,
                               "consult_brain": False, "allocate_energy": False}
    plan = {"schema": "szl.execution-acceptance-plan/v1", **bindings,
            "issued_at": stamp(NOW - timedelta(minutes=2)),
            "expires_at": stamp(NOW + timedelta(minutes=2)),
            "operator_reference": "synthetic-operator", "max_requests": 5, "retries": 0,
            "cases": [{"id": case_id, "method": "POST", "path": path, "body": bodies[case_id],
                       "expected_status": 200, "response_assertions": {"/synthetic": True},
                       "readback_assertions": {"/fixture": "NOT_A_LIVE_RECEIPT"}}
                      for case_id, path in module.CONTRACTS.items()]}
    response = module.canonical({"synthetic": True})
    readback = module.canonical({"fixture": "NOT_A_LIVE_RECEIPT"})
    receipts = [{"schema": "szl.execution-observation/v1", **bindings,
                 "receipt_id": "synthetic-" + case["id"], "case_id": case["id"],
                 "plan_sha256": module.digest(module.canonical(plan)),
                 "operator_reference": plan["operator_reference"],
                 "request_sha256": module.digest(module.canonical({k: case[k] for k in ("method", "path", "body")})),
                 "response_sha256": module.digest(response), "readback_sha256": module.digest(readback),
                 "response_status": 200, "started_at": stamp(NOW - timedelta(minutes=1)),
                 "completed_at": stamp(NOW - timedelta(seconds=20))}
                for case in plan["cases"]]

    def bundle(plan_override=None, receipts_override=None):
        chosen_plan = plan if plan_override is None else plan_override
        chosen_receipts = receipts if receipts_override is None else receipts_override
        return {"schema": "szl.execution-acceptance-bundle/v1",
                "plan": sign(chosen_plan, module.PLAN_TYPE, authority, authority_id),
                "observations": [{"receipt": sign(r, module.RECEIPT_TYPE, runtime, runtime_id),
                                  "response_b64": base64.b64encode(response).decode(),
                                  "readback_b64": base64.b64encode(readback).decode()}
                                 for r in chosen_receipts]}
    return context, plan, receipts, bundle


def test_valid_synthetic_signatures_do_not_authorize_execution_or_release(sample):
    context, _, _, bundle = sample
    result = module.validate(bundle(), context, now=NOW)
    assert result["binding_checks_passed"] is True
    assert len(result["cases"]) == 5
    assert result["status"] == "REPORTED"
    assert result["publication_eligible"] is False
    assert result["execution_authorized"] is False
    assert result["passive_probe_modified"] is False


def test_shared_plan_parser_preserves_full_five_observation_requirement(sample):
    context, plan, _, bundle = sample
    evidence = bundle()
    assert module.validate_plan(evidence["plan"], context, now=NOW) == plan
    evidence["observations"] = evidence["observations"][:3]
    with pytest.raises(module.EvidenceError, match="COMPLETE_EVIDENCE_REQUIRED"):
        module.validate(evidence, context, now=NOW)


@pytest.mark.parametrize("mutation", ["signature", "source", "runtime", "boot", "nonce",
                                     "expired", "missing_case", "extra_field", "same_key"])
def test_shared_plan_parser_and_bundle_reject_the_same_invalid_plan(sample, mutation):
    context, plan, _, bundle = sample
    changed = copy.deepcopy(plan)
    if mutation in ("source", "runtime"):
        changed[mutation + "_revision"] = "f" * 40
    elif mutation == "boot":
        changed["runtime_boot_id"] = "other-boot"
    elif mutation == "nonce":
        changed["run_nonce"] = "f" * 64
    elif mutation == "expired":
        changed["expires_at"] = stamp(NOW - timedelta(seconds=1))
    elif mutation == "missing_case":
        changed["cases"].pop()
    elif mutation == "extra_field":
        changed["authorized"] = True
    elif mutation == "same_key":
        context = replace(context, runtime_key_id=context.authority_key_id)
    evidence = bundle(plan_override=changed)
    if mutation == "signature":
        evidence["plan"]["signatures"][0]["sig"] = base64.b64encode(b"forged").decode()
    with pytest.raises(module.EvidenceError) as direct:
        module.validate_plan(evidence["plan"], context, now=NOW)
    with pytest.raises(module.EvidenceError) as full:
        module.validate(evidence, context, now=NOW)
    assert str(direct.value) == str(full.value)


@pytest.mark.parametrize("field,value", [
    ("source_revision", "d" * 40), ("runtime_revision", "d" * 40),
    ("runtime_boot_id", "other-boot"), ("run_nonce", "d" * 64),
    ("origin", "https://attacker.invalid"), ("origin", module.ORIGIN + "/"),
    ("operator_reference", "different-operator"), ("plan_sha256", "d" * 64),
    ("request_sha256", "d" * 64), ("response_sha256", "d" * 64),
    ("readback_sha256", "d" * 64), ("response_status", 503),
    ("response_status", True), ("case_id", "unknown"), ("receipt_id", ""),
    ("started_at", "2026-10-15T02:57:00Z"), ("completed_at", "2026-10-15T03:01:00Z"),
])
def test_even_correctly_signed_mismatched_receipts_fail(sample, field, value):
    context, _, receipts, bundle = sample
    changed = copy.deepcopy(receipts)
    changed[0][field] = value
    with pytest.raises(module.EvidenceError):
        module.validate(bundle(receipts_override=changed), context, now=NOW)


@pytest.mark.parametrize("field,value", [
    ("origin", "https://a-11-oy.com"), ("source_revision", "d" * 40),
    ("runtime_revision", "d" * 40), ("run_nonce", "d" * 64),
    ("max_requests", 6), ("max_requests", True), ("retries", 1),
    ("issued_at", "2026-10-15T03:00:01Z"), ("expires_at", "2026-10-15T02:59:00Z"),
    ("expires_at", "2026-10-16T03:00:00Z"), ("operator_reference", ""),
])
def test_signed_plan_still_must_match_independent_admission(sample, field, value):
    context, plan, _, bundle = sample
    changed = copy.deepcopy(plan)
    changed[field] = value
    with pytest.raises(module.EvidenceError):
        module.validate(bundle(plan_override=changed), context, now=NOW)


@pytest.mark.parametrize("target", ["plan", "receipt"])
def test_tampering_and_unknown_signers_are_rejected(sample, target):
    context, _, _, bundle = sample
    evidence = bundle()
    envelope = evidence["plan"] if target == "plan" else evidence["observations"][0]["receipt"]
    envelope["signatures"][0]["sig"] = base64.b64encode(b"forged").decode()
    with pytest.raises(module.EvidenceError, match="SIGNATURE_INVALID"):
        module.validate(evidence, context, now=NOW)
    envelope["signatures"][0]["keyid"] = "0" * 64
    with pytest.raises(module.EvidenceError, match="SIGNER_MISMATCH"):
        module.validate(evidence, context, now=NOW)


def test_keys_cannot_bootstrap_their_own_trust(sample):
    context, _, _, bundle = sample
    _, pem, _ = keypair()
    with pytest.raises(module.EvidenceError, match="PUBLIC_KEY_PIN_MISMATCH"):
        module.validate(bundle(), replace(context, authority_public_key=pem), now=NOW)
    with pytest.raises(module.EvidenceError, match="SEPARATE_AUTHORITY_REQUIRED"):
        module.validate(bundle(), replace(context, authority_key_id=context.runtime_key_id), now=NOW)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "receipt_duplicate", "extra", "claims"])
def test_missing_duplicate_partial_or_self_asserted_evidence_fails(sample, mutation):
    context, _, receipts, bundle = sample
    changed = copy.deepcopy(receipts)
    if mutation == "missing":
        changed.pop()
    elif mutation == "duplicate":
        changed[1] = changed[0]
    elif mutation == "receipt_duplicate":
        changed[1]["receipt_id"] = changed[0]["receipt_id"]
    elif mutation == "extra":
        changed.append(changed[0])
    else:
        changed[0]["authorized"] = True
        changed[0]["receipt_verified"] = True
    with pytest.raises(module.EvidenceError):
        module.validate(bundle(receipts_override=changed), context, now=NOW)


@pytest.mark.parametrize("body_change", ["modeled", "sandbox", "retry", "brain", "approval", "model"])
def test_reference_runs_or_unreviewed_agent_effects_do_not_qualify(sample, body_change):
    context, plan, _, bundle = sample
    changed = copy.deepcopy(plan)
    cases = {case["id"]: case for case in changed["cases"]}
    if body_change == "modeled":
        cases["eval-run"]["body"]["execution_mode"] = "modeled"
    else:
        key, value = {"sandbox": ("sandbox", True), "retry": ("max_retries", 1),
                      "brain": ("consult_brain", True), "approval": ("approval", {}),
                      "model": ("model_id", None)}[body_change]
        cases["agentloop-run"]["body"][key] = value
    with pytest.raises(module.EvidenceError):
        module.validate(bundle(plan_override=changed), context, now=NOW)


def test_signed_hashes_are_checked_against_bytes_and_assertions(sample):
    context, _, receipts, bundle = sample
    evidence = bundle()
    evidence["observations"][0]["response_b64"] = base64.b64encode(b'{"synthetic":false}').decode()
    with pytest.raises(module.EvidenceError, match="RESPONSE_HASH_MISMATCH"):
        module.validate(evidence, context, now=NOW)
    changed = copy.deepcopy(receipts)
    changed[0]["response_sha256"] = module.digest(b'{"synthetic":1}')
    evidence = bundle(receipts_override=changed)
    evidence["observations"][0]["response_b64"] = base64.b64encode(b'{"synthetic":1}').decode()
    with pytest.raises(module.EvidenceError, match="ASSERTION_MISMATCH"):
        module.validate(evidence, context, now=NOW)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff', b'{' ])
def test_untrusted_json_rejects_ambiguity(raw):
    with pytest.raises(module.EvidenceError):
        module.strict_json(raw)


def test_offline_validation_never_uses_network_or_private_key_environment(sample, monkeypatch):
    import socket
    import os
    def forbidden(*args, **kwargs):
        raise AssertionError("offline validator crossed its boundary")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    context, _, _, bundle = sample
    assert module.validate(bundle(), context, now=NOW)["binding_checks_passed"]


def test_cli_help_is_independent_of_runtime_imports():
    result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "tools/execution_acceptance.py"),
                             "--help"], capture_output=True, timeout=10)
    assert result.returncode == 0
    assert b"--authority-key-id" in result.stdout


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "empty_assertions", "invalid_pointer"])
def test_incomplete_or_ambiguous_approved_plan_fails(sample, mutation):
    context, plan, _, bundle = sample
    changed = copy.deepcopy(plan)
    if mutation == "duplicate":
        changed["cases"][1] = changed["cases"][0]
    elif mutation == "missing":
        changed["cases"].pop()
    elif mutation == "empty_assertions":
        changed["cases"][0]["readback_assertions"] = {}
    else:
        changed["cases"][0]["response_assertions"] = {"/malformed~2pointer": True}
    with pytest.raises(module.EvidenceError):
        module.validate(bundle(plan_override=changed), context, now=NOW)


def test_cli_missing_public_inputs_blocks_without_disclosing_paths():
    missing_root = ROOT / ("never-created-" + str(uuid4()))
    assert not missing_root.exists()
    args = [sys.executable, "-I", "-B", str(ROOT / "tools/execution_acceptance.py"),
            str(missing_root / "missing-bundle.json")]
    values = {"source-revision": "a" * 40, "runtime-revision": "b" * 40,
              "runtime-boot-id": "synthetic-boot", "run-nonce": "c" * 64,
              "authority-key": str(missing_root / "absent-public.pem"),
              "authority-key-id": "d" * 64, "runtime-key": str(missing_root / "absent-runtime.pem"),
              "runtime-key-id": "e" * 64}
    for name, value in values.items():
        args.extend(["--" + name, value])
    result = subprocess.run(args, capture_output=True, timeout=10)
    assert result.returncode == 1
    payload = module.strict_json(result.stdout)
    assert payload == {"status": "BLOCKED", "reason": "FileNotFoundError",
                       "publication_eligible": False, "execution_authorized": False}
    assert not result.stderr
