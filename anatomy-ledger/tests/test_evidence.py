#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Adversarial ingestion and verifier-adapter tests; fixtures are synthetic."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import build_ledger as ledger
import evaluate_supply_chain as policy
import verify_release as verifier


def statement(sha="a" * 64):
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "artifact.bin", "digest": {"sha256": sha}}],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://github.com/actions/attest-build-provenance"
            },
            "runDetails": {
                "builder": {
                    "id": "https://github.com/szl-holdings/a11oy/.github/workflows/anatomy-ledger.yml"
                }
            },
        },
    }


def verifier_output(value):
    # Models the documented CLI shape, not a real signature or runtime claim.
    return json.dumps(
        [
            {
                "verificationResult": {
                    "statement": value,
                    "signature": {"certificate": {"subjectAlternativeName": "fixture"}},
                    "verifiedTimestamps": [
                        {
                            "type": "transparency-log",
                            "timestamp": "2026-09-24T00:00:00Z",
                        }
                    ],
                }
            }
        ]
    )


class EvidenceTests(unittest.TestCase):
    def test_forged_flag_never_grants_authority(self):
        result = policy.evaluate(
            {"statement": statement(), "verification": {"verified": True}}
        )
        self.assertEqual(result["outcome"], "REVIEW")
        self.assertFalse(result["verified"])
        self.assertFalse(result["policyEvaluated"])
        self.assertEqual(result["evaluator"], "python-structural-advisory")

    def test_dictionary_cannot_impersonate_proof(self):
        result = policy.evaluate({"statement": statement()}, proof={"verified": True})
        self.assertFalse(result["verified"])
        with self.assertRaises(verifier.VerificationError):
            verifier.VerifiedEvidence(statement(), {"verified": True})

    def test_nested_and_dsse_claims_are_untrusted(self):
        forged = statement()
        forged["verification"] = {"verified": True}
        for value in [
            forged,
            {"statement": forged, "verification": {"verified": True}},
            {
                "payloadType": "application/vnd.in-toto+json",
                "payload": base64.b64encode(json.dumps(forged).encode()).decode(),
                "signatures": [{"sig": "synthetic"}],
                "verification": {"verified": True},
            },
        ]:
            with self.subTest(value=value):
                extracted, facts = ledger.decode_statement(value)
                self.assertEqual(extracted, forged)
                self.assertFalse(facts["verified"])

    def test_malformed_types_block_without_crashing(self):
        for value in [
            None,
            [],
            "text",
            True,
            3,
            {"_type": "https://in-toto.io/Statement/v1", "subject": "x"},
        ]:
            with self.subTest(value=value):
                result = policy.evaluate({"statement": value})
                self.assertEqual(result["outcome"], "BLOCK")
        for key, value in [
            ("predicate", []),
            ("predicateType", {}),
            ("subject", [{"name": "x", "digest": "bad"}]),
        ]:
            bad = statement()
            bad[key] = value
            self.assertEqual(policy.evaluate({"statement": bad})["outcome"], "BLOCK")

    def test_every_subject_must_be_valid(self):
        bad = statement()
        bad["subject"].append({"name": "bad", "digest": {}})
        self.assertEqual(policy.evaluate({"statement": bad})["outcome"], "BLOCK")

    def test_dsse_primitive_and_wrong_payload_type_rejected(self):
        for payload_type, payload in [
            ("application/json", statement()),
            ("application/vnd.in-toto+json", []),
        ]:
            value = {
                "payloadType": payload_type,
                "payload": base64.b64encode(json.dumps(payload).encode()).decode(),
                "signatures": [],
            }
            self.assertIsNone(ledger.decode_statement(value)[0])

    def test_duplicate_nonfinite_and_deep_json_rejected(self):
        for raw in ['{"x":1,"x":2}', '{"x": NaN}', "[" * 70 + "0" + "]" * 70]:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    ledger.strict_json(raw)

    def test_file_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "evidence.json"
            path.write_bytes(b" " * (ledger.MAX_FILE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "size limit"):
                ledger.objects_from_file(path)

    def test_build_ignores_outside_intake_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            intake = root / "evidence"
            intake.mkdir()
            forged = {"statement": statement(), "verification": {"verified": True}}
            (intake / "attestation.json").write_text(
                json.dumps(forged), encoding="utf-8"
            )
            (root / "unrelated-attestation.json").write_text("broken", encoding="utf-8")
            out = root / "ledger.json"
            value = ledger.build(root, intake, out)
            self.assertEqual(json.loads(out.read_text()), value)
            self.assertEqual(value["recordCount"], 1)
            self.assertEqual(value["outcomes"], {"ALLOW": 0, "REVIEW": 1, "BLOCK": 0})
            self.assertTrue(ledger.validate_chain(value)["valid"])
            for mutate in [
                lambda v: v["records"][0].update(source="tampered"),
                lambda v: v.update(chainRoot="f" * 64),
                lambda v: v.update(recordCount=3),
                lambda v: v["outcomes"].update(ALLOW=1),
            ]:
                bad = copy.deepcopy(value)
                mutate(bad)
                self.assertFalse(ledger.validate_chain(bad)["valid"])
            self.assertFalse(ledger.validate_chain(value)["anchored"])

    def test_malformed_file_and_statement_are_block_records(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            intake = root / "intake"
            intake.mkdir()
            (intake / "bad.json").write_text("not JSON")
            (intake / "malformed.json").write_text(
                json.dumps(
                    {"_type": "https://in-toto.io/Statement/v1", "subject": None}
                )
            )
            value = ledger.build(root, intake, root / "ledger.json")
            self.assertEqual(value["outcomes"]["BLOCK"], 2)
            self.assertTrue(ledger.validate_chain(value)["valid"])

    def test_empty_chain_and_nonobject_chain(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            value = ledger.build(root, root / "absent", root / "ledger.json")
            self.assertTrue(ledger.validate_chain(value)["valid"])
            self.assertIsNone(value["chainRoot"])
        self.assertFalse(ledger.validate_chain([])["valid"])

    def test_opa_failure_and_undefined_fail_closed(self):
        for outcome in [
            subprocess.CompletedProcess([], 1, "", "error"),
            subprocess.CompletedProcess([], 0, "{}", ""),
            subprocess.CompletedProcess([], 0, "null", ""),
        ]:
            with mock.patch.object(policy.subprocess, "run", return_value=outcome):
                result = policy.evaluate({"statement": statement()}, opa="opa")
                self.assertEqual(result["outcome"], "BLOCK")
                self.assertEqual(result["evaluator"], "opa-error")
        with mock.patch.object(
            policy.subprocess, "run", side_effect=subprocess.TimeoutExpired("opa", 10)
        ):
            self.assertEqual(
                policy.evaluate({"statement": statement()}, opa="opa")["outcome"],
                "BLOCK",
            )

    def test_opa_cannot_promote_unverified_input(self):
        output = {
            "result": [
                {
                    "expressions": [
                        {
                            "value": {
                                "outcome": "ALLOW",
                                "deny": [],
                                "review": [],
                                "verified": True,
                                "slsa": True,
                            }
                        }
                    ]
                }
            ]
        }
        with mock.patch.object(
            policy.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, json.dumps(output), ""),
        ):
            result = policy.evaluate(
                {"statement": statement(), "verification": {"verified": True}},
                opa="opa",
            )
            self.assertEqual(result["outcome"], "BLOCK")
            self.assertFalse(result["verified"])

    def _verify_fixture(self, path, output=None, returncode=0):
        value = statement(hashlib.sha256(path.read_bytes()).hexdigest())
        result = subprocess.CompletedProcess(
            [], returncode, output if output is not None else verifier_output(value), ""
        )
        with mock.patch.object(
            verifier.subprocess, "run", return_value=result
        ) as called:
            proofs = verifier.verify_artifact(
                path,
                "szl-holdings/a11oy",
                ".github/workflows/anatomy-ledger.yml",
                "refs/heads/main",
            )
        return value, proofs, called.call_args

    def test_verifier_binds_digest_and_exact_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact = pathlib.Path(folder) / "artifact.bin"
            artifact.write_bytes(b"synthetic unit fixture")
            value, proofs, call = self._verify_fixture(artifact)
            self.assertEqual(proofs[0].statement, value)
            command = call.args[0]
            self.assertIn("--cert-identity", command)
            self.assertIn(
                "https://github.com/szl-holdings/a11oy/.github/workflows/anatomy-ledger.yml@refs/heads/main",
                command,
            )
            self.assertIn("--source-ref", command)
            self.assertTrue(verifier.proof_metadata(proofs[0], value)["verified"])
            altered = copy.deepcopy(value)
            altered["subject"][0]["name"] = "changed"
            self.assertFalse(verifier.proof_metadata(proofs[0], altered)["verified"])
            self.assertEqual(
                policy.evaluate({"statement": value}, proof=proofs[0])["outcome"],
                "REVIEW",
            )
            saved = json.loads(
                json.dumps({"statement": value, "verification": proofs[0].metadata})
            )
            self.assertFalse(policy.evaluate(saved)["verified"])

    def test_verifier_rejects_failure_empty_result_and_wrong_subject(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact = pathlib.Path(folder) / "artifact.bin"
            artifact.write_bytes(b"synthetic fixture")
            for output, code in [
                (verifier_output(statement()), 0),
                ("[]", 0),
                ("{}", 0),
                ("not-json", 0),
                ("[]", 1),
            ]:
                with self.subTest(output=output, code=code):
                    with self.assertRaises(verifier.VerificationError):
                        self._verify_fixture(artifact, output, code)

    def test_verifier_detects_artifact_change_during_process(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact = pathlib.Path(folder) / "artifact.bin"
            artifact.write_bytes(b"before")
            value = statement(hashlib.sha256(b"before").hexdigest())

            def run(*args, **kwargs):
                artifact.write_bytes(b"after")
                return subprocess.CompletedProcess([], 0, verifier_output(value), "")

            with mock.patch.object(verifier.subprocess, "run", side_effect=run):
                with self.assertRaisesRegex(verifier.VerificationError, "changed"):
                    verifier.verify_artifact(
                        artifact,
                        "szl-holdings/a11oy",
                        ".github/workflows/anatomy-ledger.yml",
                        "refs/heads/main",
                    )

    @unittest.skipUnless(
        os.environ.get("ANATOMY_OPA"), "Set ANATOMY_OPA for real Rego integration"
    )
    def test_real_opa_engine_and_trusted_projection(self):
        opa = os.environ["ANATOMY_OPA"]
        for value, expected in [
            (statement(), "REVIEW"),
            ({}, "BLOCK"),
            (None, "BLOCK"),
        ]:
            result = policy.evaluate(
                {"statement": value, "verification": {"verified": True}}, opa=opa
            )
            self.assertEqual(result["outcome"], expected)
            self.assertEqual(result["evaluator"], "opa")
            self.assertFalse(result["verified"])
        with tempfile.TemporaryDirectory() as folder:
            artifact = pathlib.Path(folder) / "artifact.bin"
            artifact.write_bytes(b"synthetic verifier fixture; real OPA evaluation")
            value, proofs, _ = self._verify_fixture(artifact)
            result = policy.evaluate({"statement": value}, opa=opa, proof=proofs[0])
            self.assertEqual(result["outcome"], "ALLOW")
            self.assertEqual(result["evaluator"], "opa")
            value = ledger.build(
                pathlib.Path(folder),
                pathlib.Path(folder) / "absent",
                pathlib.Path(folder) / "ledger.json",
                opa=opa,
                verified_evidence=proofs,
            )
            self.assertEqual(value["outcomes"]["ALLOW"], 1)
            self.assertTrue(ledger.validate_chain(value)["valid"])


if __name__ == "__main__":
    unittest.main()
