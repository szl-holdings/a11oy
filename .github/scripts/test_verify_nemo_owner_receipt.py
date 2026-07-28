#!/usr/bin/env python3
"""Offline tests for the owner-GPU receipt verifier."""

import base64
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from nacl.signing import SigningKey


SCRIPT = pathlib.Path(__file__).with_name("verify_nemo_owner_receipt.py")
SPEC = importlib.util.spec_from_file_location("verify_nemo_owner_receipt", SCRIPT)
assert SPEC and SPEC.loader
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class ReceiptVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tempdir.name)
        self.signing_key = SigningKey.generate()
        self.spki = (
            b"\x30\x2a\x30\x05\x06\x03\x2b\x65\x70\x03\x21\x00"
            + bytes(self.signing_key.verify_key)
        )
        self.key_id = hashlib.sha256(self.spki).hexdigest()[:16]
        self.key_path = self.root / "laptop_pubkey.json"
        self.key_path.write_text(
            json.dumps(
                {
                    "keyId": self.key_id,
                    "publicKeySpkiBase64": base64.b64encode(self.spki).decode(),
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def signed_receipt(self) -> pathlib.Path:
        receipt = {
            "kind": "szl-nemo-v3-governed-training",
            "v": 1,
            "jobId": "job-2026-nemo-v3-governed-attempt-1",
            "state": "QUALIFIED_FOR_SEPARATE_PROMOTION_REVIEW",
            "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        body = VERIFIER.canonicalize(receipt)
        path = self.root / "nemo-v3-qualified.signed.json"
        path.write_text(
            json.dumps(
                {
                    "receipt": receipt,
                    "bodyBase64": base64.b64encode(body).decode(),
                    "signatureBase64": base64.b64encode(
                        self.signing_key.sign(body).signature
                    ).decode(),
                    "publicKeySpkiBase64": base64.b64encode(self.spki).decode(),
                    "keyId": self.key_id,
                    "scheme": "ed25519-over-exact-bytes-v2",
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_accepts_fresh_key_pinned_terminal_receipt(self) -> None:
        result = VERIFIER.verify_local_receipt(
            self.signed_receipt(),
            self.key_path,
            "job-2026-nemo-v3-governed-attempt-1",
            datetime.now(timezone.utc) - timedelta(seconds=5),
        )
        self.assertEqual(result["state"], "QUALIFIED_FOR_SEPARATE_PROMOTION_REVIEW")
        self.assertEqual(result["keyId"], self.key_id)

    def test_rejects_tampered_signature(self) -> None:
        path = self.signed_receipt()
        signed = json.loads(path.read_text(encoding="utf-8"))
        signed["receipt"]["state"] = "BLOCKED"
        path.write_text(json.dumps(signed), encoding="utf-8")
        with self.assertRaisesRegex(
            VERIFIER.VerificationError, "byte-identical"
        ):
            VERIFIER.verify_local_receipt(
                path,
                self.key_path,
                "job-2026-nemo-v3-governed-attempt-1",
                datetime.now(timezone.utc) - timedelta(seconds=5),
            )


if __name__ == "__main__":
    unittest.main()
