# SPDX-License-Identifier: Apache-2.0
"""Fail-closed receipt verification for the Rosie companion cross-link."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import szl_rosie_companion as rosie  # noqa: E402


class RosieReceiptIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.local = rosie.make_khipu_receipt(
            "a11oy", "ponder", "local query", [0.8] * 13, "trace-local"
        )

    @staticmethod
    def _unknown_schema_receipt() -> dict:
        body = {"schema": "example.forged/v1", "value": "forged"}
        return {**body, "node_digest": rosie._canonical_receipt_digest(body)}

    @staticmethod
    def _brain_jack_receipt(*, with_digest: bool = True,
                            src_space: str = "a11oy",
                            traceparent: str | None = "trace-local") -> dict:
        body = {
            "schema": "szl.brain_jack.receipt/v1",
            "wire": "G",
            "doctrine": "v11",
            "space": "rosie",
            "organ": "nervous",
            "src_space": src_space,
            "lambda_signal": 0.75,
            "axis_scores": [0.75] * 13,
            "traceparent": traceparent,
            "ts_utc": "2026-11-02T00:00:00+00:00",
        }
        if with_digest:
            body["node_digest"] = rosie._canonical_receipt_digest(body)
        body.update(rosie._unsigned_attestation(
            "application/vnd.szl.brain_jack.receipt+json"
        ))
        return body

    def _link(self, remote, local=None):
        return rosie.cross_link_receipt(
            "a11oy", remote, self.local if local is None else local
        )

    def test_local_receipt_digest_and_unsigned_attestation_are_honest(self) -> None:
        body = {
            key: value for key, value in self.local.items()
            if key not in rosie._DIGEST_EXCLUDED_FIELDS
        }
        self.assertEqual(
            self.local["node_digest"], rosie._canonical_receipt_digest(body)
        )
        self.assertEqual(self.local["dsse"]["signatures"], [])
        self.assertIsNone(self.local["signature"])
        self.assertEqual(self.local["signature_status"], "UNSIGNED")
        self.assertNotIn("PLACEHOLDER", repr(self.local))

    def test_valid_digests_do_not_claim_signature_or_chain_verification(self) -> None:
        remote = self._brain_jack_receipt()
        link = self._link(remote)

        self.assertTrue(link["chain_observed"])
        self.assertTrue(link["flagship_digest_verified"])
        self.assertTrue(link["rosie_digest_verified"])
        self.assertTrue(link["digest_verified"])
        self.assertFalse(link["signature_verified"])
        self.assertFalse(link["chain_verified"])
        self.assertEqual(
            link["khipu_root"],
            rosie._merkle_root([
                self.local["node_digest"], remote["node_digest"]
            ]),
        )
        self.assertEqual(link["dsse"]["signatures"], [])
        self.assertIsNone(link["signature"])

    def test_absent_and_malformed_receipts_never_verify(self) -> None:
        cases = (
            (None, False, "NOT_OBSERVED"),
            ({}, True, "MALFORMED_RECEIPT"),
            ([], True, "MALFORMED_RECEIPT"),
            ("receipt", True, "MALFORMED_RECEIPT"),
            ({"schema": []}, True, "INVALID_SCHEMA"),
            (self._unknown_schema_receipt(), True, "INVALID_SCHEMA"),
        )
        for remote, observed, status in cases:
            with self.subTest(remote=remote):
                link = self._link(remote)
                evidence = link["verification"]["rosie_receipt"]
                self.assertEqual(link["chain_observed"], observed)
                self.assertEqual(evidence["status"], status)
                self.assertFalse(evidence["accepted_as_digest_leaf"])
                self.assertFalse(link["rosie_digest_verified"])
                self.assertFalse(link["digest_verified"])
                self.assertFalse(link["signature_verified"])
                self.assertFalse(link["chain_verified"])
                self.assertIsNone(link["rosie_receipt"])
                self.assertEqual(link["khipu_root"], self.local["node_digest"])

    def test_bad_digest_formats_and_tampering_are_rejected(self) -> None:
        valid = self._brain_jack_receipt()
        cases = []
        for bad_digest in (123, "0" * 63, "A" * 64):
            forged = dict(valid)
            forged["node_digest"] = bad_digest
            cases.append((forged, "MALFORMED_DIGEST"))
        tampered = dict(valid)
        tampered["op"] = "changed-after-digest"
        cases.append((tampered, "DIGEST_MISMATCH"))

        for remote, status in cases:
            with self.subTest(status=status, digest=remote["node_digest"]):
                link = self._link(remote)
                evidence = link["verification"]["rosie_receipt"]
                self.assertEqual(evidence["status"], status)
                self.assertFalse(evidence["accepted_as_digest_leaf"])
                self.assertIsNone(link["rosie_receipt"])
                self.assertIsNone(link["chain"][1]["receipt_digest"])
                self.assertFalse(link["chain_verified"])
                self.assertEqual(link["khipu_root"], self.local["node_digest"])

    def test_forged_signature_is_observed_but_never_verified(self) -> None:
        remote = self._brain_jack_receipt()
        remote["dsse"] = {
            "payloadType": "application/vnd.szl.brain_jack.receipt+json",
            "signatures": [{"keyid": "forged", "sig": "PLACEHOLDER"}],
        }
        remote["signature"] = "PLACEHOLDER"
        remote["signature_status"] = "VERIFIED"

        link = self._link(remote)
        evidence = link["verification"]["rosie_receipt"]
        self.assertTrue(evidence["digest_verified"])
        self.assertTrue(evidence["signature_present"])
        self.assertFalse(evidence["signature_verified"])
        self.assertEqual(
            evidence["status"], "DIGEST_VERIFIED_SIGNATURE_UNVERIFIED"
        )
        self.assertFalse(link["signature_verified"])
        self.assertFalse(link["chain_verified"])
        self.assertEqual(link["rosie_receipt"]["dsse"]["signatures"], [])
        self.assertIsNone(link["rosie_receipt"]["signature"])
        self.assertEqual(
            link["rosie_receipt"]["signature_status"], "UNVERIFIED"
        )
        self.assertNotIn("PLACEHOLDER", repr(link["rosie_receipt"]))

    def test_non_json_and_non_finite_receipts_fail_without_crashing(self) -> None:
        for remote in (
            {"schema": "szl.brain_jack.receipt/v1", "value": math.nan},
            {"schema": "szl.brain_jack.receipt/v1", "value": object()},
            {"schema": "szl.brain_jack.receipt/v1", 1: "non-string-key"},
        ):
            with self.subTest(remote=repr(remote)):
                link = self._link(remote)
                self.assertEqual(
                    link["verification"]["rosie_receipt"]["status"],
                    "MALFORMED_RECEIPT",
                )
                self.assertIsNone(link["rosie_receipt"])
                self.assertFalse(link["chain_verified"])

        for field, value in (
            ("lambda_signal", 10 ** 400),
            ("axis_scores", [10 ** 400]),
        ):
            with self.subTest(field=field):
                remote = self._brain_jack_receipt()
                remote[field] = value
                link = self._link(remote)
                self.assertEqual(
                    link["verification"]["rosie_receipt"]["status"],
                    "INVALID_BINDING",
                )
                self.assertIsNone(link["rosie_receipt"])
                self.assertFalse(link["chain_verified"])

    def test_tampered_local_leaf_is_excluded_from_the_merkle_root(self) -> None:
        local = dict(self.local)
        local["op"] = "tampered"
        remote = self._brain_jack_receipt()
        link = self._link(remote, local=local)

        self.assertFalse(link["flagship_digest_verified"])
        self.assertTrue(link["rosie_digest_verified"])
        self.assertFalse(link["digest_verified"])
        self.assertEqual(link["khipu_root"], remote["node_digest"])
        self.assertIsNone(link["flagship_receipt"])

    def test_legacy_brain_jack_receipt_is_retained_only_as_untrusted_evidence(self) -> None:
        legacy = self._brain_jack_receipt(with_digest=False)
        legacy["dsse"]["signatures"] = [
            {"sig": "PLACEHOLDER", "keyid": "PENDING"}
        ]
        legacy["signature"] = "PLACEHOLDER"
        link = self._link(legacy)
        evidence = link["verification"]["rosie_receipt"]

        self.assertTrue(link["chain_observed"])
        self.assertTrue(evidence["shape_valid"])
        self.assertTrue(evidence["schema_valid"])
        self.assertEqual(evidence["status"], "MISSING_DIGEST")
        self.assertFalse(evidence["accepted_as_digest_leaf"])
        self.assertEqual(link["rosie_receipt"]["dsse"]["signatures"], [])
        self.assertIsNone(link["rosie_receipt"]["signature"])
        self.assertEqual(
            link["rosie_receipt"]["signature_status"], "UNVERIFIED"
        )
        self.assertEqual(link["khipu_root"], self.local["node_digest"])
        self.assertFalse(link["chain_verified"])

    def test_receipt_roles_and_flagship_identity_are_bound(self) -> None:
        minimal_body = {"schema": "szl.brain_jack.receipt/v1"}
        minimal = {
            **minimal_body,
            "node_digest": rosie._canonical_receipt_digest(minimal_body),
        }
        wrong_role = rosie.make_khipu_receipt(
            "a11oy", "ponder", "query", None, "trace-local"
        )
        replay = self._brain_jack_receipt(src_space="sentra")
        inconsistent = self._brain_jack_receipt()
        inconsistent["lambda_signal"] = 0.1
        inconsistent_body = {
            key: value for key, value in inconsistent.items()
            if key not in rosie._DIGEST_EXCLUDED_FIELDS
        }
        inconsistent["node_digest"] = rosie._canonical_receipt_digest(
            inconsistent_body
        )

        for remote in (minimal, wrong_role, replay, inconsistent):
            with self.subTest(remote=remote):
                link = self._link(remote)
                evidence = link["verification"]["rosie_receipt"]
                self.assertEqual(evidence["status"], "INVALID_BINDING")
                self.assertFalse(evidence["binding_valid"])
                self.assertFalse(evidence["accepted_as_digest_leaf"])
                self.assertIsNone(link["rosie_receipt"])
                self.assertEqual(link["khipu_root"], self.local["node_digest"])

        remote = self._brain_jack_receipt()
        local_brain_jack = self._brain_jack_receipt()
        link = self._link(remote, local=local_brain_jack)
        local_evidence = link["verification"]["flagship_receipt"]
        self.assertEqual(local_evidence["status"], "INVALID_BINDING")
        self.assertFalse(local_evidence["accepted_as_digest_leaf"])
        self.assertIsNone(link["flagship_receipt"])
        self.assertEqual(link["khipu_root"], remote["node_digest"])

    def test_recursive_brain_jack_preserves_each_hop_receipt_role(self) -> None:
        shadow = rosie.RosieShadow("a11oy")
        call_count = 0

        def fake_call(_op, _query, _axis_scores, traceparent, **_kwargs):
            nonlocal call_count
            call_count += 1
            receipt = self._brain_jack_receipt(
                with_digest=False, traceparent=traceparent
            )
            return ({
                "response_text": f"remote answer {call_count}",
                "lambda_signal": 0.75,
                "lambda_receipt": receipt,
            }, False, None)

        shadow._call_rosie_jack = fake_call
        response = shadow.brain_jack("query", depth=2, traceparent="trace-local")

        self.assertEqual(call_count, 2)
        self.assertEqual(response.cross_link["hop_count"], 2)
        self.assertEqual(
            response.rosie_receipt, response.cross_link["rosie_receipt"]
        )
        self.assertEqual(response.rosie_receipt["schema"],
                         "szl.brain_jack.receipt/v1")
        child = response.cross_link["next_hop"]
        self.assertEqual(child["rosie_receipt"]["schema"],
                         "szl.brain_jack.receipt/v1")
        self.assertEqual(child["flagship_receipt"]["schema"],
                         "szl.rosie_companion.receipt/v1")
        expected_leaves = [
            response.companion_receipt["node_digest"],
            response.extra["next_hop"]["companion_receipt"]["node_digest"],
        ]
        self.assertEqual(
            response.cross_link["validated_leaf_digests"], expected_leaves
        )
        self.assertEqual(
            response.cross_link["khipu_root"],
            rosie._merkle_root(expected_leaves),
        )
        self.assertFalse(response.cross_link["chain_verified"])

    def test_wrap_and_evolve_reject_malformed_remote_receipts(self) -> None:
        shadow = rosie.RosieShadow("a11oy")
        payload = {
            "response_text": "remote answer",
            "lambda_signal": 0.5,
            "lambda_receipt": {},
        }
        wrapped = shadow._wrap(
            "ponder", "query", None, None, payload, False, None
        )
        self.assertIsNone(wrapped.rosie_receipt)
        self.assertTrue(wrapped.cross_link["chain_observed"])
        self.assertFalse(wrapped.cross_link["chain_verified"])

        shadow._call_rosie_jack = lambda *args, **kwargs: (payload, False, None)
        proposal = shadow.evolve({"strategy": "observe"})
        self.assertIsNone(proposal.rosie_receipt)
        self.assertTrue(proposal.cross_link["chain_observed"])
        self.assertFalse(proposal.cross_link["chain_verified"])

    def test_canonical_and_deployed_mirrors_are_byte_identical(self) -> None:
        canonical = (ROOT / "szl_rosie_companion.py").read_bytes()
        for relative in (
            "organs/amaru/szl_rosie_companion.py",
            "organs/sentra/szl_rosie_companion.py",
        ):
            with self.subTest(relative=relative):
                self.assertEqual((ROOT / relative).read_bytes(), canonical)

    def test_empty_merkle_sentinel_remains_deterministic(self) -> None:
        local = dict(self.local)
        local["op"] = "tampered"
        link = self._link(None, local=local)
        self.assertEqual(
            link["khipu_root"], hashlib.sha256(b"empty").hexdigest()
        )


if __name__ == "__main__":
    unittest.main()
