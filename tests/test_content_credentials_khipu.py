# SPDX-License-Identifier: Apache-2.0

import copy
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from content_credentials import (  # noqa: E402
    CredentialSigner,
    KHIPU_ASSERTION_LABEL,
    TRUST_SELF_SIGNED,
    TRUST_STRUCTURAL_ONLY,
    TRUST_TAMPERED,
    build_manifest,
    verify,
    write_asset_with_credential,
)


def _authorized_write():
    return {
        "authorized": True,
        "has_provenance": True,
        "license_class": "GREEN",
        "two_person_attested": True,
    }


class ContentCredentialKhipuTests(unittest.TestCase):
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
        with self.assertRaises(ValueError):
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


if __name__ == "__main__":
    unittest.main()
