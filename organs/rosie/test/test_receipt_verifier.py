"""Tests for rosie.console.receipt_verifier — DSSE/PAE v1 HMAC verification.

The Receipt Verifier is the operator console's strongest demo asset, so it
gets the deepest coverage: the three terminal verdicts (valid / tampered /
malformed), every documented degradation path, round-trip signing, and a
fuzz that asserts any single-bit payload mutation is detected.
"""

import base64
import json
import random

import pytest

from src.console.receipt_verifier import (
    DEV_HMAC_KEY,
    Verdict,
    pae,
    sign_payload,
    verify_envelope,
    verify_receipt_json,
)

SAMPLE_PAYLOAD = {
    "spec": "szl.receipt/v1",
    "receipt_id": "rcpt-0001",
    "final_hash": "f" * 64,
    "prior_hash": "GENESIS",
    "chain_position": 1,
    "timestamp_utc": "2026-05-30T22:00:00Z",
}


class TestPae:
    def test_pae_format_matches_dsse_spec(self):
        out = pae("application/x.foo", b"hello")
        # "DSSEv1 <len(type)> <type> <len(payload)> <payload>"
        assert out == b"DSSEv1 17 application/x.foo 5 hello"

    def test_pae_is_deterministic(self):
        assert pae("t", b"abc") == pae("t", b"abc")

    def test_pae_length_prefixes_track_byte_length(self):
        # A 2-byte multibyte payload must be prefixed with its byte length.
        payload = "é".encode("utf-8")  # 2 bytes
        assert b" 2 " in pae("t", payload)


class TestVerifyValid:
    def test_signed_envelope_is_valid(self):
        env = sign_payload(SAMPLE_PAYLOAD)
        result = verify_envelope(env)
        assert result.verdict is Verdict.VALID
        assert result.ok is True
        assert result.payload == SAMPLE_PAYLOAD
        assert result.keyid == "szl-dev-hmac-v1"

    def test_valid_message_mentions_pae(self):
        result = verify_envelope(sign_payload(SAMPLE_PAYLOAD))
        assert "PAE" in result.message

    def test_json_string_round_trip_valid(self):
        env_json = json.dumps(sign_payload(SAMPLE_PAYLOAD))
        result = verify_receipt_json(env_json)
        assert result.ok is True
        assert result.payload["receipt_id"] == "rcpt-0001"

    def test_bytes_payload_round_trip(self):
        raw = b"not-json-but-signed-bytes"
        env = sign_payload(raw)
        # Signature is valid, but payload is not JSON -> MALFORMED, not VALID.
        result = verify_envelope(env)
        assert result.verdict is Verdict.MALFORMED
        assert "not JSON" in result.message


class TestVerifyTampered:
    def test_payload_mutated_after_signing_is_tampered(self):
        env = sign_payload(SAMPLE_PAYLOAD)
        mutated = dict(SAMPLE_PAYLOAD, receipt_id="rcpt-9999")
        env["payload"] = base64.b64encode(
            json.dumps(mutated, sort_keys=True, separators=(",", ":")).encode()
        ).decode()
        result = verify_envelope(env)
        assert result.verdict is Verdict.TAMPERED
        assert result.ok is False
        assert result.payload is None

    def test_wrong_key_is_tampered(self):
        env = sign_payload(SAMPLE_PAYLOAD, key=b"some-other-key")
        result = verify_envelope(env)  # verified against DEV_HMAC_KEY
        assert result.verdict is Verdict.TAMPERED

    def test_no_signatures_is_tampered(self):
        env = sign_payload(SAMPLE_PAYLOAD)
        env["signatures"] = []
        assert verify_envelope(env).verdict is Verdict.TAMPERED

    def test_signatures_key_missing_is_tampered(self):
        env = sign_payload(SAMPLE_PAYLOAD)
        del env["signatures"]
        assert verify_envelope(env).verdict is Verdict.TAMPERED

    def test_payload_type_mutation_breaks_pae(self):
        env = sign_payload(SAMPLE_PAYLOAD)
        env["payloadType"] = "application/x.different"
        # PAE binds the payload type, so a type swap must invalidate the sig.
        assert verify_envelope(env).verdict is Verdict.TAMPERED


class TestVerifyMalformed:
    def test_empty_input_is_malformed(self):
        assert verify_receipt_json("").verdict is Verdict.MALFORMED
        assert verify_receipt_json("   \n ").verdict is Verdict.MALFORMED

    def test_invalid_json_is_malformed(self):
        result = verify_receipt_json("{ this is not json")
        assert result.verdict is Verdict.MALFORMED
        assert "parse error" in result.message

    def test_non_object_envelope_is_malformed(self):
        assert verify_envelope(["not", "a", "dict"]).verdict is Verdict.MALFORMED

    def test_missing_payload_field_is_malformed(self):
        assert verify_envelope({"payloadType": "t", "signatures": []}).verdict is Verdict.MALFORMED

    def test_bad_base64_payload_is_malformed(self):
        env = {"payloadType": "t", "payload": "!!!not-base64!!!", "signatures": [{"sig": "AA=="}]}
        assert verify_envelope(env).verdict is Verdict.MALFORMED

    def test_bad_base64_signature_skipped_not_crash(self):
        env = sign_payload(SAMPLE_PAYLOAD)
        env["signatures"].insert(0, {"keyid": "junk", "sig": "!!!bad!!!"})
        # The bad sig is skipped; the real one still verifies.
        assert verify_envelope(env).verdict is Verdict.VALID


class TestConstantTimeAndKey:
    def test_dev_key_is_labelled_not_for_production(self):
        assert b"not-for-production" in DEV_HMAC_KEY


class TestFuzzMutationDetection:
    def test_single_bit_payload_mutation_always_detected(self):
        random.seed(1234)
        for _ in range(1000):
            payload = {"receipt_id": f"r-{random.randint(0, 10**9)}", "n": random.random()}
            env = sign_payload(payload)
            raw = bytearray(base64.b64decode(env["payload"]))
            # Flip one random bit in the payload bytes.
            byte_idx = random.randrange(len(raw))
            raw[byte_idx] ^= 1 << random.randrange(8)
            env["payload"] = base64.b64encode(bytes(raw)).decode()
            result = verify_envelope(env)
            assert result.verdict is Verdict.TAMPERED, "mutation went undetected"

    def test_unmodified_envelopes_always_valid(self):
        random.seed(5678)
        for _ in range(500):
            payload = {"receipt_id": f"r-{random.randint(0, 10**9)}"}
            assert verify_envelope(sign_payload(payload)).ok is True
