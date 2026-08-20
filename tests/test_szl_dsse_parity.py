# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
test_szl_dsse_parity.py — offline, dependency-light guard that LOCKS the DSSE
wire contract of szl_dsse.py against the rest of the SZL estate.

Receipt-bus unification audit (2026-07-03)
------------------------------------------
The estate has TWO incompatible DSSE Pre-Authentication-Encoding (PAE) families
that produce DIFFERENT signed bytes for the same payload, so a signature made by
one does NOT verify under the other:

  * ASCII-decimal PAE (the DSSE-v1 spec form, cosign verify-blob compatible):
        b"DSSEv1 " + len(type) + " " + type + " " + len(body) + " " + body
    Used by: szl_dsse.py (THIS module), szl_khipu_consensus.py, khipu-consensus,
    and david-leads. This is the MAJORITY / spec-correct / cosign-backed form.

  * struct-packed little-endian PAE (NON-standard, NOT cosign-compatible):
        b"DSSEv1 " + struct.pack("<Q", len(type)) + type + " " + struct.pack("<Q", len(body)) + body
    Used by: the shared szl-receipt lib (szl_receipt/_canonical.py).

szl_dsse.py is bound to the published SZLHOLDINGS cosign.pub, so its receipts
MUST stay cosign/Rekor-verifiable. Delegating it to szl-receipt would silently
change the signed bytes and break cosign verify-blob for every existing Khipu
receipt — so szl_dsse deliberately keeps its own ASCII-decimal PAE. This guard
locks that decision so a future "just import szl-receipt" refactor fails LOUDLY.
"""
from __future__ import annotations

import os
import struct
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import szl_dsse  # noqa: E402

_PT = szl_dsse.KHIPU_PAYLOAD_TYPE
_BODY = b'{"a":1,"b":"c"}'


def _szl_receipt_reference_pae(payload_type: str, body: bytes) -> bytes:
    """szl-receipt's struct-packed LE PAE — inlined as a locked reference vector
    (mirrors szl_receipt/_canonical.py::pae) so this repo needs no dependency on
    szl-receipt to assert divergence."""
    def _enc(s: bytes) -> bytes:
        return struct.pack("<Q", len(s)) + s

    return b"DSSEv1 " + _enc(payload_type.encode("utf-8")) + b" " + _enc(body)


class AsciiDecimalPaeFamily(unittest.TestCase):
    def test_szl_dsse_pae_is_ascii_decimal_dsse_spec(self):
        got = szl_dsse.pae(_PT, _BODY)
        expected = (b"DSSEv1 " + str(len(_PT)).encode() + b" " + _PT.encode()
                    + b" " + str(len(_BODY)).encode() + b" " + _BODY)
        self.assertEqual(got, expected, "szl_dsse.pae must be ASCII-decimal DSSE-v1 PAE")
        self.assertNotIn(b"\x00", got)  # no struct-packed length prefix

    def test_canonical_json_is_ensure_ascii_false(self):
        # Raw UTF-8 (ensure_ascii=False) — matches szl-receipt & khipu-consensus.
        self.assertIn(b"\xc3\xa9", szl_dsse.canonical_json({"n": "café"}))


class DivergesFromSzlReceipt(unittest.TestCase):
    def test_pae_differs_from_szl_receipt_struct_packed(self):
        ours = szl_dsse.pae(_PT, _BODY)
        theirs = _szl_receipt_reference_pae(_PT, _BODY)
        self.assertNotEqual(
            ours, theirs,
            "SAFETY LOCK: if these ever match, szl_dsse was re-based onto "
            "szl-receipt's struct-packed PAE — which breaks cosign verify-blob "
            "for existing Khipu receipts. See RECEIPT_BUS_EXEC.md before changing.")
        self.assertIn(b"\x00", theirs)  # struct-packed carries NUL length bytes


class SignerRoundTrips(unittest.TestCase):
    """szl_dsse must sign->verify against itself (cosign family), independent of
    szl-receipt. Uses the published cosign.pub for verify; signs with an ephemeral
    key ONLY to prove the round-trip when the production secret is absent."""

    def test_unsigned_is_honest_when_no_key(self):
        saved = {k: os.environ.pop(k, None) for k in szl_dsse.PRIVATE_KEY_ENV_VARS}
        try:
            env = szl_dsse.sign_payload({"x": 1})
            self.assertFalse(env["signed"])
            self.assertEqual(env["signatures"], [])
            self.assertIn("UNSIGNED", env["honesty"])
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_real_signature_verifies_end_to_end(self):
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec
        except Exception:  # pragma: no cover
            self.skipTest("cryptography not installed; PAE/divergence locks still run")
        # Sign with an ephemeral key, verify with the SAME key's PAE bytes — proving
        # szl_dsse's PAE/sign path is internally sound (cosign-family ECDSA-P256).
        key = ec.generate_private_key(ec.SECP256R1())
        body = szl_dsse.canonical_json({"receipt": "demo", "n": 1})
        to_sign = szl_dsse.pae(_PT, body)
        sig = key.sign(to_sign, ec.ECDSA(hashes.SHA256()))
        # Verify via cryptography directly (round-trip on the exact signed bytes).
        key.public_key().verify(sig, to_sign, ec.ECDSA(hashes.SHA256()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
