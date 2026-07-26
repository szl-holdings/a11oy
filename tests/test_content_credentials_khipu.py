# SPDX-License-Identifier: Apache-2.0

import copy
import sqlite3
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import a11oy_code_orchestrator as orchestrator  # noqa: E402
from content_credentials import (  # noqa: E402
    CredentialSigner,
    KHIPU_ASSERTION_LABEL,
    KhipuAuthenticationUnavailable,
    TRUST_AUTH_UNAVAILABLE,
    TRUST_SELF_SIGNED,
    TRUST_STRUCTURAL_ONLY,
    TRUST_TAMPERED,
    _canon,
    build_manifest,
    sha256_bytes,
    verify,
    write_asset_with_credential,
)
from a11oy_code_orchestrator import (  # noqa: E402
    khipu_emit,
    khipu_verify_receipt,
)


def _authorized_write():
    return {
        "authorized": True,
        "has_provenance": True,
        "license_class": "GREEN",
        "two_person_attested": True,
    }


class ContentCredentialKhipuTests(unittest.TestCase):
    def setUp(self):
        self.state_directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(
            orchestrator,
            "DB_PATH",
            str(Path(self.state_directory.name) / "a11oy-code.db"),
        )
        self.db_patch.start()
        with orchestrator._khipu_lock:
            orchestrator._khipu_receipts.clear()
            orchestrator._khipu_tip = orchestrator._KHIPU_GENESIS
        orchestrator.init_db()

    def tearDown(self):
        self.db_patch.stop()
        self.state_directory.cleanup()

    def test_media_write_binds_the_actual_khipu_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            asset = Path(directory) / "governed-media.txt"
            result = write_asset_with_credential(
                asset_path=str(asset),
                asset_bytes=b"governed media bytes\n",
                asset_title=asset.name,
                asset_format="text/plain",
                ai_generated=True,
                model_id="szl/test-fixture",
                governance_context=_authorized_write(),
            )

            self.assertEqual(asset.read_bytes(), b"governed media bytes\n")
            receipt = result["khipu_receipt"]
            self.assertTrue(receipt["chain_verified"])
            self.assertEqual(len(receipt["hash"]), 64)
            self.assertTrue(receipt["receipt_id"])
            self.assertTrue(result["governance_decision"]["allow"])
            self.assertEqual(
                receipt["payload"]["asset_hash"], result["asset_hash"]
            )

            assertions = result["credential"]["active_manifest"]["claim"][
                "assertions"
            ]
            link = next(
                assertion["data"]
                for assertion in assertions
                if assertion["label"] == KHIPU_ASSERTION_LABEL
            )
            self.assertEqual(link["receipt_id"], receipt["receipt_id"])
            self.assertEqual(link["receipt_hash"], receipt["hash"])
            self.assertEqual(link["attested_execution"]["state"], "UNAVAILABLE")

            verification = verify(result["credential"], asset_path=str(asset))
            self.assertTrue(verification.ok)
            self.assertTrue(verification.claim_hash_ok)
            self.assertEqual(verification.trust_level, TRUST_STRUCTURAL_ONLY)

    def test_receipt_link_tampering_is_detected_even_when_unsigned(self):
        with tempfile.TemporaryDirectory() as directory:
            asset = Path(directory) / "governed-media.txt"
            result = write_asset_with_credential(
                asset_path=str(asset),
                asset_bytes=b"original\n",
                asset_title=asset.name,
                asset_format="text/plain",
                ai_generated=False,
                governance_context=_authorized_write(),
            )
            tampered = copy.deepcopy(result["credential"])
            tampered["active_manifest"]["claim"]["assertions"][-1]["data"][
                "receipt_id"
            ] = "fabricated-receipt"

            verification = verify(tampered, asset_path=str(asset))
            self.assertFalse(verification.ok)
            self.assertFalse(verification.claim_hash_ok)
            self.assertEqual(verification.trust_level, TRUST_TAMPERED)

    def test_signed_receipt_link_verifies_as_self_signed_not_trust_list(self):
        try:
            signer = CredentialSigner(CredentialSigner.generate_key_pem())
        except RuntimeError:
            self.skipTest("cryptography is unavailable")

        with tempfile.TemporaryDirectory() as directory:
            asset = Path(directory) / "signed-media.txt"
            result = write_asset_with_credential(
                asset_path=str(asset),
                asset_bytes=b"signed media\n",
                asset_title=asset.name,
                asset_format="text/plain",
                ai_generated=False,
                signer=signer,
                governance_context=_authorized_write(),
            )
            verification = verify(result["credential"], asset_path=str(asset))
            self.assertTrue(verification.ok)
            self.assertTrue(verification.signature_ok)
            self.assertEqual(verification.trust_level, TRUST_SELF_SIGNED)

    def test_manifest_rejects_a_fabricated_or_unattested_link(self):
        with self.assertRaises((ValueError, KhipuAuthenticationUnavailable)):
            build_manifest(
                asset_bytes=b"asset",
                asset_title="asset.txt",
                asset_format="text/plain",
                ai_generated=False,
                khipu_receipt={
                    "receipt_id": str(uuid.uuid4()),
                    "receipt_hash": "0" * 64,
                    "receipt_hash_alg": "sha256",
                    "chain_verified": True,
                    "dsse_signed": False,
                    "attested_execution": {
                        "state": "UNAVAILABLE",
                        "receipt_id": None,
                        "reason": (
                            "no independently verified attestation receipt supplied"
                        ),
                    },
                },
            )

    def test_denied_governance_cannot_mutate_an_existing_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            asset = Path(directory) / "protected-media.txt"
            asset.write_bytes(b"original bytes\n")

            with self.assertRaises(PermissionError):
                write_asset_with_credential(
                    asset_path=str(asset),
                    asset_bytes=b"unauthorized replacement\n",
                    asset_title=asset.name,
                    asset_format="text/plain",
                    ai_generated=False,
                )

            self.assertEqual(asset.read_bytes(), b"original bytes\n")
            self.assertFalse(Path(f"{asset}.c2pa.json").exists())

    def test_khipu_registry_freezes_payloads_and_validates_predecessors(self):
        payload = {"nested": {"state": "original"}}
        receipt = khipu_emit("test.freeze", payload)
        expected_payload = {"nested": {"state": "original"}}

        payload["nested"]["state"] = "caller-mutated"
        receipt["payload"]["nested"]["state"] = "return-mutated"

        self.assertTrue(
            khipu_verify_receipt(
                receipt["receipt_id"],
                receipt["hash"],
                expected_action="test.freeze",
                expected_payload=expected_payload,
            )
        )
        successor = khipu_emit("test.successor", {"ok": True})
        self.assertTrue(
            khipu_verify_receipt(successor["receipt_id"], successor["hash"])
        )

    def test_verify_rejects_a_rehashed_attacker_controlled_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            asset = Path(directory) / "governed-media.txt"
            result = write_asset_with_credential(
                asset_path=str(asset),
                asset_bytes=b"original\n",
                asset_title=asset.name,
                asset_format="text/plain",
                ai_generated=False,
                governance_context=_authorized_write(),
            )
            tampered = copy.deepcopy(result["credential"])
            fabricated = copy.deepcopy(
                tampered["active_manifest"]["khipu_receipt"]
            )
            fabricated["receipt_id"] = str(uuid.uuid4())
            fabricated["receipt_hash"] = "f" * 64
            tampered["active_manifest"]["khipu_receipt"] = fabricated
            tampered["active_manifest"]["claim"]["assertions"][-1]["data"] = (
                copy.deepcopy(fabricated)
            )
            tampered["claim_sha256"] = sha256_bytes(
                _canon(tampered["active_manifest"]["claim"])
            )

            verification = verify(tampered, asset_path=str(asset))
            self.assertFalse(verification.ok)
            self.assertTrue(verification.claim_hash_ok)
            self.assertEqual(verification.khipu_authentication, "UNAVAILABLE")
            self.assertEqual(verification.trust_level, TRUST_AUTH_UNAVAILABLE)

    def test_sidecar_failure_rolls_back_asset_and_existing_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            asset = Path(directory) / "governed-media.txt"
            sidecar = Path(f"{asset}.c2pa.json")
            asset.write_bytes(b"original asset\n")
            sidecar.write_bytes(b"original sidecar\n")

            with patch(
                "a11oy_code_orchestrator.khipu_emit",
                wraps=orchestrator.khipu_emit,
            ) as emit:
                with patch(
                    "content_credentials.write_sidecar",
                    side_effect=OSError("simulated sidecar failure"),
                ):
                    with self.assertRaises(OSError):
                        write_asset_with_credential(
                            asset_path=str(asset),
                            asset_bytes=b"replacement\n",
                            asset_title=asset.name,
                            asset_format="text/plain",
                            ai_generated=False,
                            governance_context=_authorized_write(),
                        )

            self.assertEqual(asset.read_bytes(), b"original asset\n")
            self.assertEqual(sidecar.read_bytes(), b"original sidecar\n")
            actions = [call.args[0] for call in emit.call_args_list]
            self.assertIn("content-credential.media.write.failed", actions)
            self.assertIn("content-credential.media.write.rollback", actions)

    def test_durable_receipt_verifies_after_cache_is_cleared(self):
        with tempfile.TemporaryDirectory() as directory:
            asset = Path(directory) / "durable-media.txt"
            result = write_asset_with_credential(
                asset_path=str(asset),
                asset_bytes=b"durable\n",
                asset_title=asset.name,
                asset_format="text/plain",
                ai_generated=False,
                governance_context=_authorized_write(),
            )
            with orchestrator._khipu_lock:
                orchestrator._khipu_receipts.clear()
                orchestrator._khipu_tip = orchestrator._KHIPU_GENESIS
            orchestrator.init_db()

            verification = verify(result["credential"], asset_path=str(asset))
            self.assertTrue(verification.ok)
            self.assertTrue(verification.claim_hash_ok)
            self.assertNotEqual(
                orchestrator._khipu_tip,
                orchestrator._KHIPU_GENESIS,
            )

    def test_receipt_cache_is_bounded_while_durable_history_still_verifies(self):
        with patch.object(orchestrator, "_KHIPU_CACHE_MAX", 3):
            receipts = [
                khipu_emit("test.cache", {"index": index})
                for index in range(6)
            ]
            self.assertLessEqual(len(orchestrator._khipu_receipts), 3)
            oldest = receipts[0]
            self.assertTrue(
                khipu_verify_receipt(
                    oldest["receipt_id"],
                    oldest["hash"],
                    expected_action="test.cache",
                    expected_payload={"index": 0},
                    require_durable=True,
                )
            )
            self.assertLessEqual(len(orchestrator._khipu_receipts), 3)

    def test_persistence_failure_does_not_advance_or_poison_chain_tip(self):
        original_tip = orchestrator._khipu_tip
        with patch.object(
            orchestrator,
            "_db_write_receipt",
            side_effect=sqlite3.OperationalError("simulated lock"),
        ):
            failed = khipu_emit("test.persistence.failure", {"ok": False})

        self.assertFalse(failed["chain_verified"])
        self.assertEqual(failed["persistence_state"], "UNAVAILABLE")
        self.assertEqual(orchestrator._khipu_tip, original_tip)
        self.assertNotIn(failed["receipt_id"], orchestrator._khipu_receipts)

        recovered = khipu_emit("test.persistence.recovered", {"ok": True})
        self.assertEqual(recovered["prev"], original_tip)
        self.assertTrue(recovered["chain_verified"])
        self.assertTrue(
            khipu_verify_receipt(
                recovered["receipt_id"],
                recovered["hash"],
                require_durable=True,
            )
        )

    def test_dsse_signed_status_is_authenticated(self):
        with tempfile.TemporaryDirectory() as directory:
            asset = Path(directory) / "unsigned-media.txt"
            result = write_asset_with_credential(
                asset_path=str(asset),
                asset_bytes=b"unsigned\n",
                asset_title=asset.name,
                asset_format="text/plain",
                ai_generated=False,
                governance_context=_authorized_write(),
            )
            tampered = copy.deepcopy(result["credential"])
            tampered["active_manifest"]["khipu_receipt"]["dsse_signed"] = True
            tampered["active_manifest"]["claim"]["assertions"][-1]["data"][
                "dsse_signed"
            ] = True
            tampered["claim_sha256"] = sha256_bytes(
                _canon(tampered["active_manifest"]["claim"])
            )

            verification = verify(tampered, asset_path=str(asset))
            self.assertFalse(verification.ok)
            self.assertEqual(verification.khipu_authentication, "INVALID")
            self.assertEqual(verification.trust_level, TRUST_TAMPERED)

    def test_missing_registry_is_unavailable_not_tampered(self):
        with tempfile.TemporaryDirectory() as directory:
            asset = Path(directory) / "portable-media.txt"
            result = write_asset_with_credential(
                asset_path=str(asset),
                asset_bytes=b"portable\n",
                asset_title=asset.name,
                asset_format="text/plain",
                ai_generated=False,
                governance_context=_authorized_write(),
            )
            with orchestrator._khipu_lock:
                orchestrator._khipu_receipts.clear()
            with patch.object(
                orchestrator,
                "DB_PATH",
                str(Path(directory) / "unavailable-host.db"),
            ):
                orchestrator.init_db()
                verification = verify(result["credential"], asset_path=str(asset))

            self.assertFalse(verification.ok)
            self.assertTrue(verification.hash_ok)
            self.assertTrue(verification.claim_hash_ok)
            self.assertEqual(verification.khipu_authentication, "UNAVAILABLE")
            self.assertEqual(verification.trust_level, TRUST_AUTH_UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
