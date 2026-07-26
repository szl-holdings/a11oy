"""Contract tests for fail-closed TEE evidence handling.

SPDX-License-Identifier: Apache-2.0
Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""

import base64
import ctypes
import hashlib
import json
import struct
from datetime import datetime, timedelta, timezone

import szl_attested_inference
import szl_dsse
import szl_tee_attest


def _synthetic_tdx_quote(report_data, *, version=4, body_type=2):
    """Minimal structurally valid quote fixture; never presented as real evidence."""
    header = struct.pack("<HHI", version, 2, 0x81) + bytes(40)
    body = bytearray(584 if body_type == 2 else 648)
    body[520:584] = report_data
    signature = bytes([0xA5]) * 64
    if version == 4:
        return header + body[:584] + struct.pack("<I", len(signature)) + signature
    return (
        header
        + struct.pack("<HI", body_type, len(body))
        + body
        + struct.pack("<I", len(signature))
        + signature
    )


def test_absent_runtime_emits_complete_v2_unavailable_contract(monkeypatch):
    monkeypatch.setattr(szl_tee_attest, "_probe_tdx", lambda **_kwargs: None)
    monkeypatch.setattr(szl_tee_attest, "_probe_nitro", lambda **_kwargs: None)

    record = szl_tee_attest.get_tee_attestation()

    assert record["schema"] == "szl.tee-attestation/v2"
    assert record["present"] is False
    assert record["verified"] is False
    assert record["label"] == "UNAVAILABLE"
    assert record["evidence_tier"] == "UNAVAILABLE"
    assert record["quote_digest"] is None
    assert record["verified_at"] is None
    assert record["verifier"] is None


def test_operator_report_is_observed_not_measured(tmp_path):
    report = bytes(range(256)) * 4
    report_path = tmp_path / "tdreport.bin"
    report_path.write_bytes(report)

    parsed = szl_tee_attest._tdx_read_mrtd_file(str(report_path))
    record = szl_tee_attest._observed_attestation(parsed)

    assert record["present"] is True
    assert record["verified"] is False
    assert record["label"] == "SAMPLE"
    assert record["evidence_tier"] == "SAMPLE_UNVERIFIED"
    assert record["quote_digest"] == hashlib.sha256(report).hexdigest()
    assert record["measurement"] == report[128:176].hex()
    assert record["verifier"] is None


def test_high_consequence_policy_blocks_unverified_evidence():
    observed = {
        "schema": "szl.tee-attestation/v2",
        "present": True,
        "verified": False,
        "type": "nitro",
        "quote_digest": "a" * 64,
        "label": "SAMPLE",
        "evidence_tier": "SAMPLE_UNVERIFIED",
        "verified_at": None,
        "verifier": None,
    }

    policy = szl_tee_attest.evaluate_attestation_policy(
        observed, high_consequence=True
    )

    assert policy["verdict"] == "BLOCK"
    assert policy["allowed"] is False
    assert policy["verified_evidence"] is False


def _signed_verifier_record(monkeypatch, *, verified_at=None, tee_type="nitro"):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    now = verified_at or datetime.now(timezone.utc)
    quote_digest = "b" * 64
    measurement = "c" * 96
    nonce = "request-nonce-0001"
    workload_digest = "d" * 96
    verifier = "test-trust-root"
    payload = {
        "schema": "szl.tee-verifier-result/v1",
        "verdict": "VERIFIED",
        "verifier": verifier,
        "tee_type": tee_type,
        "quote_digest": quote_digest,
        "measurement": measurement,
        "nonce": nonce,
        "workload_digest": workload_digest,
        "verified_at": now.isoformat(),
        "quote_signature_verified": True,
        "certificate_chain_verified": True,
    }
    payload_type = "application/vnd.szl.tee-verifier-result+json"
    body = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    signature = private_key.sign(
        szl_dsse.pae(payload_type, body),
        ec.ECDSA(hashes.SHA256()),
    )
    envelope = {
        "_dsse": "DSSEv1",
        "payloadType": payload_type,
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [
            {
                "keyid": verifier,
                "sig": base64.b64encode(signature).decode("ascii"),
            }
        ],
    }
    record = {
        "schema": "szl.tee-attestation/v2",
        "present": True,
        "verified": True,
        "type": tee_type,
        "quote_digest": quote_digest,
        "measurement": measurement,
        "label": "MEASURED",
        "evidence_tier": "MEASURED_VERIFIED",
        "verified_at": now.isoformat(),
        "verifier": verifier,
        "verifier_envelope": envelope,
    }
    return record, nonce, workload_digest, measurement, now, public_pem


def test_truthy_verified_metadata_without_authenticated_envelope_is_blocked():
    verified = {
        "schema": "szl.tee-attestation/v2",
        "present": True,
        "verified": True,
        "type": "nitro",
        "quote_digest": "b" * 64,
        "label": "MEASURED",
        "evidence_tier": "MEASURED_VERIFIED",
        "verified_at": "2026-07-25T00:00:00+00:00",
        "verifier": "aws-nitro-pki",
    }

    policy = szl_tee_attest.evaluate_attestation_policy(
        verified, high_consequence=True
    )
    assert policy["allowed"] is False
    assert policy["checks"]["authenticated_verifier"] is False


def test_high_consequence_policy_accepts_real_signature_and_all_bindings(monkeypatch):
    record, nonce, workload, measurement, now, public_pem = _signed_verifier_record(
        monkeypatch
    )

    policy = szl_tee_attest.evaluate_attestation_policy(
        record,
        high_consequence=True,
        expected_nonce=nonce,
        expected_workload_digest=workload,
        reference_measurements={measurement},
        trusted_verifiers={"test-trust-root"},
        verifier_public_keys={"test-trust-root": public_pem},
        now=now,
    )

    assert policy["allowed"] is True
    assert policy["verdict"] == "ALLOW"
    assert all(policy["checks"].values())


def test_high_consequence_policy_rejects_replay_staleness_and_reference_drift(monkeypatch):
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    record, nonce, workload, measurement, now, public_pem = _signed_verifier_record(
        monkeypatch, verified_at=stale_time
    )

    stale = szl_tee_attest.evaluate_attestation_policy(
        record,
        high_consequence=True,
        expected_nonce=nonce,
        expected_workload_digest=workload,
        reference_measurements={measurement},
        trusted_verifiers={"test-trust-root"},
        verifier_public_keys={"test-trust-root": public_pem},
        now=now + timedelta(minutes=10),
    )
    replay = szl_tee_attest.evaluate_attestation_policy(
        record,
        high_consequence=True,
        expected_nonce="different-request",
        expected_workload_digest=workload,
        reference_measurements={measurement},
        trusted_verifiers={"test-trust-root"},
        verifier_public_keys={"test-trust-root": public_pem},
        now=stale_time,
    )
    drift = szl_tee_attest.evaluate_attestation_policy(
        record,
        high_consequence=True,
        expected_nonce=nonce,
        expected_workload_digest=workload,
        reference_measurements={"e" * 96},
        trusted_verifiers={"test-trust-root"},
        verifier_public_keys={"test-trust-root": public_pem},
        now=stale_time,
    )
    untrusted = szl_tee_attest.evaluate_attestation_policy(
        record,
        high_consequence=True,
        expected_nonce=nonce,
        expected_workload_digest=workload,
        reference_measurements={measurement},
        trusted_verifiers={"different-trust-root"},
        verifier_public_keys={"test-trust-root": public_pem},
        now=stale_time,
    )

    assert stale["allowed"] is False
    assert stale["checks"]["fresh"] is False
    assert replay["allowed"] is False
    assert replay["checks"]["request_bound"] is False
    assert drift["allowed"] is False
    assert drift["checks"]["reference_measurement"] is False
    assert untrusted["allowed"] is False
    assert untrusted["checks"]["trusted_verifier"] is False


def test_allowlisted_verifier_cannot_reuse_a_different_trust_root(monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    record, nonce, workload, measurement, now, _ = _signed_verifier_record(
        monkeypatch
    )
    unrelated_public_pem = (
        ec.generate_private_key(ec.SECP256R1())
        .public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    policy = szl_tee_attest.evaluate_attestation_policy(
        record,
        high_consequence=True,
        expected_nonce=nonce,
        expected_workload_digest=workload,
        reference_measurements={measurement},
        trusted_verifiers={"test-trust-root"},
        verifier_public_keys={"test-trust-root": unrelated_public_pem},
        now=now,
    )

    assert policy["allowed"] is False
    assert policy["checks"]["authenticated_verifier"] is False


def test_live_probe_promotes_only_external_verifier_authenticated_evidence(monkeypatch):
    (
        signed_record,
        nonce,
        workload,
        measurement,
        now,
        public_pem,
    ) = _signed_verifier_record(monkeypatch)
    probe_result = {
        "type": "nitro",
        "measurement": measurement,
        "measurement_field": "PCR0",
        "quote_digest": signed_record["quote_digest"],
        "quote_bytes": b"request-bound-hardware-quote",
        "source": "nsm:AttestationDoc",
        "request_binding_observed": True,
    }
    monkeypatch.setenv(
        "SZL_TEE_VERIFIER_PUBLIC_KEYS_JSON",
        json.dumps({"test-trust-root": public_pem}),
    )
    monkeypatch.setenv("SZL_TEE_TRUSTED_VERIFIERS", "test-trust-root")
    monkeypatch.setattr(
        szl_tee_attest,
        "_probe_tdx",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        szl_tee_attest,
        "_probe_nitro",
        lambda **_kwargs: probe_result,
    )
    monkeypatch.setattr(
        szl_tee_attest,
        "_submit_to_verifier",
        lambda _result, **_kwargs: (
            signed_record["verifier_envelope"],
            "test verifier",
        ),
    )

    attestation = szl_tee_attest.get_tee_attestation(
        nonce=nonce,
        workload_digest=workload,
        verify_external=True,
    )
    policy = szl_tee_attest.evaluate_attestation_policy(
        attestation,
        high_consequence=True,
        expected_nonce=nonce,
        expected_workload_digest=workload,
        reference_measurements={measurement},
        trusted_verifiers={"test-trust-root"},
        verifier_public_keys={"test-trust-root": public_pem},
        now=now,
    )

    assert attestation["verified"] is True
    assert attestation["label"] == "MEASURED"
    assert attestation["evidence_tier"] == "MEASURED_VERIFIED"
    assert policy["verdict"] == "ALLOW"


def test_tdx_quote_uses_authenticated_verifier_measurement(monkeypatch):
    (
        signed_record,
        nonce,
        workload,
        measurement,
        _now,
        public_pem,
    ) = _signed_verifier_record(monkeypatch, tee_type="tdx")
    monkeypatch.setenv(
        "SZL_TEE_VERIFIER_PUBLIC_KEYS_JSON",
        json.dumps({"test-trust-root": public_pem}),
    )
    monkeypatch.setenv("SZL_TEE_TRUSTED_VERIFIERS", "test-trust-root")
    quote_result = {
        "type": "tdx",
        "measurement": None,
        "measurement_field": "MRTD",
        "quote_digest": signed_record["quote_digest"],
        "quote_bytes": b"request-bound-tdquote",
        "source": "intel-libtdx-attest:qgs",
        "evidence_format": "TDQUOTE_V4",
        "request_binding_digest": "a" * 128,
    }

    attestation, reason = szl_tee_attest._verified_attestation(
        quote_result,
        signed_record["verifier_envelope"],
        nonce=nonce,
        workload_digest=workload,
    )

    assert reason == "external verifier evidence authenticated"
    assert attestation["verified"] is True
    assert attestation["measurement"] == measurement
    assert attestation["label"] == "MEASURED"


def test_live_probe_keeps_stale_authenticated_evidence_as_sample(monkeypatch):
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    (
        signed_record,
        nonce,
        workload,
        measurement,
        _now,
        public_pem,
    ) = _signed_verifier_record(monkeypatch, verified_at=stale_time)
    monkeypatch.setenv(
        "SZL_TEE_VERIFIER_PUBLIC_KEYS_JSON",
        json.dumps({"test-trust-root": public_pem}),
    )
    monkeypatch.setenv("SZL_TEE_TRUSTED_VERIFIERS", "test-trust-root")
    monkeypatch.setattr(
        szl_tee_attest,
        "_probe_tdx",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        szl_tee_attest,
        "_probe_nitro",
        lambda **_kwargs: {
            "type": "nitro",
            "measurement": measurement,
            "measurement_field": "PCR0",
            "quote_digest": signed_record["quote_digest"],
            "quote_bytes": b"stale-request-bound-hardware-quote",
            "source": "nsm:AttestationDoc",
            "request_binding_observed": True,
        },
    )
    monkeypatch.setattr(
        szl_tee_attest,
        "_submit_to_verifier",
        lambda _result, **_kwargs: (
            signed_record["verifier_envelope"],
            "test verifier",
        ),
    )

    attestation = szl_tee_attest.get_tee_attestation(
        nonce=nonce,
        workload_digest=workload,
        verify_external=True,
    )

    assert attestation["verified"] is False
    assert attestation["label"] == "SAMPLE"
    assert attestation["evidence_tier"] == "SAMPLE_UNVERIFIED"
    assert "stale or future-dated" in attestation["verifier_note"]


def test_future_authenticated_evidence_never_promotes_to_measured(monkeypatch):
    future_time = datetime.now(timezone.utc) + timedelta(minutes=1)
    (
        signed_record,
        nonce,
        workload,
        measurement,
        _future,
        public_pem,
    ) = _signed_verifier_record(monkeypatch, verified_at=future_time)
    monkeypatch.setenv(
        "SZL_TEE_VERIFIER_PUBLIC_KEYS_JSON",
        json.dumps({"test-trust-root": public_pem}),
    )
    monkeypatch.setenv("SZL_TEE_TRUSTED_VERIFIERS", "test-trust-root")
    quote_result = {
        "type": "nitro",
        "measurement": measurement,
        "measurement_field": "PCR0",
        "quote_digest": signed_record["quote_digest"],
        "quote_bytes": b"future-request-bound-hardware-quote",
        "source": "nsm:AttestationDoc",
        "request_binding_observed": True,
    }

    attestation, reason = szl_tee_attest._verified_attestation(
        quote_result,
        signed_record["verifier_envelope"],
        nonce=nonce,
        workload_digest=workload,
    )
    policy = szl_tee_attest.evaluate_attestation_policy(
        signed_record,
        high_consequence=True,
        expected_nonce=nonce,
        expected_workload_digest=workload,
        reference_measurements={measurement},
        trusted_verifiers={"test-trust-root"},
        verifier_public_keys={"test-trust-root": public_pem},
        now=future_time - timedelta(seconds=1),
    )

    assert attestation is None
    assert "future-dated" in reason
    assert policy["checks"]["fresh"] is False
    assert policy["allowed"] is False


def test_bound_tdx_request_never_uses_a_cached_report_file(monkeypatch, tmp_path):
    report_path = tmp_path / "cached-tdreport.bin"
    report_path.write_bytes(bytes(1024))
    monkeypatch.setenv("SZL_TDX_DEVICE", str(tmp_path / "missing-tdx-device"))
    monkeypatch.setenv("SZL_TDX_REPORT_PATH", str(report_path))
    monkeypatch.setattr(
        szl_tee_attest,
        "_tdx_read_mrtd_file",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("cached report must not satisfy a bound request")
        ),
    )

    result = szl_tee_attest._probe_tdx(
        nonce="a" * 64,
        workload_digest="b" * 96,
    )

    assert result is None


def test_bound_tdx_request_uses_quote_generation_not_local_tdreport(monkeypatch):
    report_data = szl_tee_attest._request_binding("a" * 64, "b" * 96)[2]
    expected = {
        "type": "tdx",
        "measurement": None,
        "measurement_field": "MRTD",
        "quote_digest": hashlib.sha256(b"tdquote").hexdigest(),
        "quote_bytes": b"tdquote",
        "source": "intel-libtdx-attest:qgs",
        "evidence_format": "TDQUOTE_V4",
        "request_binding_digest": report_data.hex(),
    }
    monkeypatch.setattr(
        szl_tee_attest,
        "_tdx_read_quote_qgl",
        lambda value: expected if value == report_data else None,
    )
    monkeypatch.setattr(
        szl_tee_attest,
        "_tdx_read_mrtd_ioctl",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("bound requests must not use local TDREPORT")
        ),
    )

    result = szl_tee_attest._probe_tdx(
        nonce="a" * 64,
        workload_digest="b" * 96,
    )

    assert result == expected
    assert result["evidence_format"] == "TDQUOTE_V4"


def test_qgl_quote_is_signed_structure_and_request_bound(monkeypatch):
    report_data = bytes(range(64))
    quote = _synthetic_tdx_quote(report_data)
    monkeypatch.setattr(
        szl_tee_attest,
        "_tdx_qgl_quote_bytes",
        lambda value: quote if value == report_data else b"",
    )

    result = szl_tee_attest._tdx_read_quote_qgl(report_data)

    assert result["quote_bytes"] == quote
    assert result["quote_digest"] == hashlib.sha256(quote).hexdigest()
    assert result["request_binding_digest"] == report_data.hex()
    assert result["source"] == "intel-libtdx-attest:qgs"
    assert result["evidence_format"] == "TDQUOTE_V4"
    assert result["measurement"] is None


def test_qgl_rejects_a_local_tdreport_relabel(monkeypatch):
    monkeypatch.setattr(
        szl_tee_attest,
        "_tdx_qgl_quote_bytes",
        lambda _report_data: bytes(1024),
    )

    try:
        szl_tee_attest._tdx_read_quote_qgl(bytes(64))
    except RuntimeError as exc:
        assert "signed TD Quote" in str(exc) or "Quote version" in str(exc)
    else:
        raise AssertionError("a local TDREPORT must never be relabeled as a TD Quote")


def test_qgl_wrapper_calls_intel_quote_api_and_frees_buffer(monkeypatch):
    report_data = bytes(range(64))
    quote = _synthetic_tdx_quote(report_data, version=5, body_type=3)
    calls = []

    class _FakeFunction:
        def __init__(self, callback):
            self.callback = callback
            self.argtypes = None
            self.restype = None

        def __call__(self, *args):
            return self.callback(*args)

    class _FakeLibrary:
        pass

    library = _FakeLibrary()
    retained = ctypes.create_string_buffer(quote)

    def fake_get_quote(report, _keys, count, _selected, quote_out, size_out, flags):
        assert ctypes.string_at(report, 64) == report_data
        assert count == 0
        assert flags == 0
        quote_pointer = ctypes.cast(retained, ctypes.POINTER(ctypes.c_uint8))
        ctypes.cast(
            quote_out,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
        )[0] = quote_pointer
        ctypes.cast(size_out, ctypes.POINTER(ctypes.c_uint32))[0] = len(quote)
        calls.append("get")
        return 0

    def fake_free_quote(_quote_pointer):
        calls.append("free")
        return 0

    library.tdx_att_get_quote = _FakeFunction(fake_get_quote)
    library.tdx_att_free_quote = _FakeFunction(fake_free_quote)
    monkeypatch.setattr(
        szl_tee_attest,
        "_load_tdx_attest_library",
        lambda: library,
    )

    assert szl_tee_attest._tdx_qgl_quote_bytes(report_data) == quote
    assert calls == ["get", "free"]


def test_read_only_get_never_invokes_external_verifier(monkeypatch):
    from types import SimpleNamespace

    probe_calls = []

    def local_observation_only(**kwargs):
        probe_calls.append(kwargs)
        return {
            "type": "tdx",
            "measurement": "c" * 96,
            "measurement_field": "MRTD",
            "quote_digest": hashlib.sha256(b"local-tdreport").hexdigest(),
            "source": "ioctl:TDX_CMD_GET_REPORT0",
            "evidence_format": "TDREPORT_LOCAL_ONLY",
            "request_binding_digest": None,
        }

    monkeypatch.setattr(
        szl_tee_attest,
        "_probe_tdx",
        local_observation_only,
    )
    monkeypatch.setattr(szl_tee_attest, "_probe_nitro", lambda **_kwargs: None)
    monkeypatch.setattr(
        szl_tee_attest,
        "_submit_to_verifier",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("GET must never invoke the signing verifier")
        ),
    )

    response = szl_attested_inference._h_attest_infer(
        SimpleNamespace(
            query_params={"seed": "42", "model": "szl-modeled-lm"}
        )
    )
    body = json.loads(response.body)

    assert body["receipt"]["external_verification_requested"] is False
    assert probe_calls == [{"nonce": None, "workload_digest": None}]
    assert body["tee_attestation"]["verified"] is False
    assert body["tee_attestation"]["evidence_tier"] == "SAMPLE_UNVERIFIED"
    assert "disabled for read-only observation" in body["tee_attestation"][
        "verifier_note"
    ]
    assert body["attestation_policy"]["verdict"] == "BLOCK"
    assert body["inference"]["released"] is False


def test_status_get_and_receipt_helper_default_to_observation_only(monkeypatch):
    probe_calls = []

    def local_observation_only(**kwargs):
        probe_calls.append(kwargs)
        return {
            "type": "tdx",
            "measurement": "c" * 96,
            "measurement_field": "MRTD",
            "quote_digest": hashlib.sha256(b"local-tdreport").hexdigest(),
            "source": "ioctl:TDX_CMD_GET_REPORT0",
            "evidence_format": "TDREPORT_LOCAL_ONLY",
            "request_binding_digest": None,
        }

    monkeypatch.setattr(
        szl_tee_attest,
        "_probe_tdx",
        local_observation_only,
    )
    monkeypatch.setattr(szl_tee_attest, "_probe_nitro", lambda **_kwargs: None)
    monkeypatch.setattr(
        szl_tee_attest,
        "_submit_to_verifier",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("read helpers must not invoke the signing verifier")
        ),
    )

    status_response = szl_tee_attest._h_tee_status(None)
    status_body = json.loads(status_response.body)
    receipt_field = szl_tee_attest.tee_attestation_field()

    assert probe_calls == [
        {"nonce": None, "workload_digest": None},
        {"nonce": None, "workload_digest": None},
    ]
    assert status_body["verified"] is False
    assert receipt_field["verified"] is False
    assert "disabled for read-only observation" in status_body["verifier_note"]
    assert "disabled for read-only observation" in receipt_field["verifier_note"]


def test_inference_helper_defaults_external_verification_to_opt_in(monkeypatch):
    requested = []
    monkeypatch.setattr(
        szl_attested_inference,
        "_tee_attestation",
        lambda _nonce, _workload, *, verify_external: (
            requested.append(verify_external)
            or {
                "schema": "szl.tee-attestation/v2",
                "present": False,
                "verified": False,
                "label": "UNAVAILABLE",
            }
        ),
    )

    result = szl_attested_inference.run_attested_inference(
        42,
        "szl-modeled-lm",
        high_consequence=True,
    )

    assert requested == [False]
    assert result["receipt"]["external_verification_requested"] is False
    assert result["attestation_policy"]["verdict"] == "BLOCK"
    assert result["inference"]["released"] is False


def test_non_consequential_modeled_read_is_explicitly_advisory():
    unavailable = {
        "schema": "szl.tee-attestation/v2",
        "present": False,
        "verified": False,
        "label": "UNAVAILABLE",
    }

    policy = szl_tee_attest.evaluate_attestation_policy(
        unavailable, high_consequence=False
    )

    assert policy["allowed"] is True
    assert policy["high_consequence"] is False
    assert "modeled" in policy["reason"]


def test_attested_inference_blocks_high_consequence_without_verified_quote(monkeypatch):
    unavailable = {
        "schema": "szl.tee-attestation/v2",
        "present": False,
        "verified": False,
        "type": None,
        "quote_digest": None,
        "measurement": None,
        "verified_at": None,
        "verifier": None,
        "evidence_tier": "UNAVAILABLE",
        "label": "UNAVAILABLE",
    }
    monkeypatch.setattr(
        szl_attested_inference, "_tee_attestation", lambda *_args, **_kwargs: unavailable
    )

    result = szl_attested_inference.run_attested_inference(
        42, "szl-modeled-lm", high_consequence=True
    )

    assert result["attestation_policy"]["verdict"] == "BLOCK"
    assert result["inference"]["released"] is False
    assert result["receipt"]["schema"] == "szl.attested-inference/v2"
    assert result["receipt"]["tee_attestation"]["verified"] is False
    assert result["dsse"]["signed"] is False
    assert result["dsse"]["local_label"] == "UNSIGNED-READ"


def test_high_consequence_requests_use_unique_unpredictable_challenges(monkeypatch):
    unavailable = {
        "schema": "szl.tee-attestation/v2",
        "present": False,
        "verified": False,
        "label": "UNAVAILABLE",
    }
    seen_bindings = []
    monkeypatch.setattr(
        szl_attested_inference,
        "_tee_attestation",
        lambda nonce, workload, **_kwargs: (
            seen_bindings.append((nonce, workload)) or unavailable
        ),
    )

    first = szl_attested_inference.run_attested_inference(
        42, "szl-modeled-lm", high_consequence=True
    )
    second = szl_attested_inference.run_attested_inference(
        42, "szl-modeled-lm", high_consequence=True
    )
    first_nonce = first["attestation_quote"]["quote_body"]["nonce"]
    second_nonce = second["attestation_quote"]["quote_body"]["nonce"]

    assert len(first_nonce) == 64
    assert len(second_nonce) == 64
    assert first_nonce != second_nonce
    assert seen_bindings == [
        (
            first_nonce,
            first["inference"]["prompt_digest"],
        ),
        (
            second_nonce,
            second["inference"]["prompt_digest"],
        ),
    ]
    assert first["attestation_policy"]["verdict"] == "BLOCK"
    assert second["attestation_policy"]["verdict"] == "BLOCK"


def test_public_route_cannot_downgrade_attestation_with_query_input(monkeypatch):
    from types import SimpleNamespace

    unavailable = {
        "schema": "szl.tee-attestation/v2",
        "present": False,
        "verified": False,
        "type": None,
        "quote_digest": None,
        "measurement": None,
        "verified_at": None,
        "verifier": None,
        "evidence_tier": "UNAVAILABLE",
        "label": "UNAVAILABLE",
    }
    monkeypatch.setattr(
        szl_attested_inference, "_tee_attestation", lambda *_args, **_kwargs: unavailable
    )

    response = szl_attested_inference._h_attest_infer(
        SimpleNamespace(
            query_params={
                "seed": "42",
                "model": "szl-modeled-lm",
                "high_consequence": "false",
            }
        )
    )
    body = json.loads(response.body)

    assert body["receipt"]["high_consequence"] is True
    assert body["attestation_policy"]["verdict"] == "BLOCK"
    assert body["inference"]["released"] is False


def test_unsigned_read_envelope_preserves_canonical_payload(monkeypatch):
    monkeypatch.setattr(
        szl_attested_inference,
        "_tee_attestation",
        lambda *_args, **_kwargs: {
            "schema": "szl.tee-attestation/v2",
            "present": False,
            "verified": False,
            "label": "UNAVAILABLE",
        },
    )

    result = szl_attested_inference.run_attested_inference(
        42, "szl-modeled-lm", high_consequence=False
    )
    envelope = result["dsse"]
    payload = json.loads(base64.b64decode(envelope["payload"]))

    assert envelope["_dsse"] == "DSSEv1"
    assert payload == result["receipt"]
    verdict = szl_dsse.verify_envelope(envelope)
    assert verdict["verified"] is False
    assert verdict["reason"] == "no signatures (unsigned envelope)"


def test_ledger_uses_effective_combined_block_verdict(monkeypatch):
    import szl_org_lambda

    emitted = []
    monkeypatch.setattr(
        szl_org_lambda,
        "emit",
        lambda *args, **kwargs: emitted.append((args, kwargs)),
    )
    monkeypatch.setattr(
        szl_attested_inference,
        "_tee_attestation",
        lambda *_args, **_kwargs: {
            "schema": "szl.tee-attestation/v2",
            "present": False,
            "verified": False,
            "label": "UNAVAILABLE",
        },
    )

    result = szl_attested_inference.run_attested_inference(
        42, "szl-modeled-lm", high_consequence=True
    )

    assert result["lambda"]["pass"] is True
    assert result["attestation_policy"]["verdict"] == "BLOCK"
    assert result["inference"]["released"] is False
    assert emitted[-1][1]["decision"] == "BLOCK"


def test_library_defaults_to_high_consequence_and_blocks_without_evidence(monkeypatch):
    monkeypatch.setattr(
        szl_attested_inference,
        "_tee_attestation",
        lambda *_args, **_kwargs: {
            "schema": "szl.tee-attestation/v2",
            "present": False,
            "verified": False,
            "label": "UNAVAILABLE",
        },
    )

    result = szl_attested_inference.run_attested_inference(
        42, "szl-modeled-lm"
    )

    assert result["receipt"]["high_consequence"] is True
    assert result["receipt"]["external_verification_requested"] is False
    assert result["attestation_policy"]["verdict"] == "BLOCK"
    assert result["inference"]["released"] is False


def test_inference_helper_requires_explicit_verifier_opt_in(monkeypatch):
    calls = []

    def observation_only(nonce, workload, *, verify_external=False):
        calls.append((nonce, workload, verify_external))
        return {
            "schema": "szl.tee-attestation/v2",
            "present": False,
            "verified": False,
            "label": "UNAVAILABLE",
        }

    monkeypatch.setattr(
        szl_attested_inference,
        "_tee_attestation",
        observation_only,
    )

    default_result = szl_attested_inference.run_attested_inference(
        42,
        "szl-modeled-lm",
    )
    explicit_result = szl_attested_inference.run_attested_inference(
        43,
        "szl-modeled-lm",
        verify_external=True,
    )

    assert calls[0][2] is False
    assert calls[1][2] is True
    assert default_result["receipt"]["external_verification_requested"] is False
    assert explicit_result["receipt"]["external_verification_requested"] is True


def test_http_consequence_class_is_server_owned(monkeypatch):
    monkeypatch.setattr(
        szl_attested_inference,
        "HTTP_READ_CONSEQUENCE_CLASS",
        "HIGH_CONSEQUENCE",
    )

    assert szl_attested_inference._http_read_requires_attestation({}) is True
    assert (
        szl_attested_inference._http_read_requires_attestation(
            {"high_consequence": "flase"}
        )
        is True
    )
    assert (
        szl_attested_inference._http_read_requires_attestation(
            {"high_consequence": "false"}
        )
        is True
    )


def test_advisory_http_read_can_only_be_strengthened_by_the_caller(monkeypatch):
    monkeypatch.setattr(
        szl_attested_inference,
        "HTTP_READ_CONSEQUENCE_CLASS",
        "ADVISORY_READ",
    )

    assert szl_attested_inference._http_read_requires_attestation({}) is False
    assert (
        szl_attested_inference._http_read_requires_attestation(
            {"high_consequence": "false"}
        )
        is False
    )
    assert (
        szl_attested_inference._http_read_requires_attestation(
            {"high_consequence": "true"}
        )
        is True
    )


def test_live_surface_never_claims_get_receipt_is_signed():
    surface = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "static"
        / "3d"
        / "surfaces"
        / "attestinfer.js"
    ).read_text(encoding="utf-8")

    assert "signed receipt (live)" not in surface
    assert "DSSE is REAL ECDSA-P256 in-Space" not in surface
    assert "signed for real" not in surface
    assert "UNSIGNED-READ" in surface
