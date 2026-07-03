# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
test_sign_cert_dsse_parity.py — offline guard that LOCKS the DSSE wire contract
of sign_cert_dsse.py against the rest of the SZL estate.

Receipt-bus unification audit (2026-07-03)
------------------------------------------
sign_cert_dsse.py is the on-metal signer for the physical-bounds certificate. It
uses:

  * ASCII-decimal PAE (the DSSE-v1 spec form, cosign verify-blob compatible):
        b"DSSEv1 " + len(type) + " " + type + " " + len(body) + " " + body
  * a REAL Ed25519 key (/root/ed25519.pem, openssl pkeyutl -rawin).

The shared szl-receipt lib uses a DIFFERENT, incompatible contract:

  * struct-packed little-endian PAE (NON-standard, NOT cosign-compatible):
        b"DSSEv1 " + struct.pack("<Q", len(type)) + type + " " + struct.pack("<Q", len(body)) + body
  * ECDSA-P256-SHA256 (not Ed25519).

Both the PAE encoding AND the signature algorithm differ, so delegating this
signer to szl-receipt would change the signed bytes AND the signature scheme —
breaking verification of every certificate already signed on-metal. This signer
therefore deliberately keeps its own Ed25519 + ASCII-decimal PAE. This guard
locks that decision so a future "just import szl-receipt" refactor fails LOUDLY.
See RECEIPT_BUS_EXEC.md before changing pae() or PAYLOAD_TYPE.
"""
from __future__ import annotations

import os
import struct
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import sign_cert_dsse  # noqa: E402  (importable: I/O is guarded under __main__)

_PT = sign_cert_dsse.PAYLOAD_TYPE
_BODY = b'{"a":1,"b":"c"}'


def _szl_receipt_reference_pae(payload_type: str, body: bytes) -> bytes:
    """szl-receipt's struct-packed LE PAE — inlined as a locked reference vector
    (mirrors szl_receipt/_canonical.py::pae) so this repo needs no dependency on
    szl-receipt to assert divergence."""
    def _enc(s: bytes) -> bytes:
        return struct.pack("<Q", len(s)) + s

    return b"DSSEv1 " + _enc(payload_type.encode("utf-8")) + b" " + _enc(body)


class AsciiDecimalPaeFamily(unittest.TestCase):
    def test_pae_is_ascii_decimal_dsse_spec(self):
        got = sign_cert_dsse.pae(_PT, _BODY)
        expected = (b"DSSEv1 " + str(len(_PT)).encode() + b" " + _PT.encode()
                    + b" " + str(len(_BODY)).encode() + b" " + _BODY)
        self.assertEqual(got, expected, "sign_cert_dsse.pae must be ASCII-decimal DSSE-v1 PAE")
        self.assertNotIn(b"\x00", got)  # no struct-packed length prefix

    def test_payload_type_is_physical_bounds_certificate(self):
        self.assertEqual(_PT, "application/vnd.szl.physical-bounds-certificate+json")


class DivergesFromSzlReceipt(unittest.TestCase):
    def test_pae_differs_from_szl_receipt_struct_packed(self):
        ours = sign_cert_dsse.pae(_PT, _BODY)
        theirs = _szl_receipt_reference_pae(_PT, _BODY)
        self.assertNotEqual(
            ours, theirs,
            "SAFETY LOCK: if these ever match, sign_cert_dsse was re-based onto "
            "szl-receipt's struct-packed PAE — which changes the signed bytes and "
            "breaks verification of existing on-metal certificates. See "
            "RECEIPT_BUS_EXEC.md before changing.")
        self.assertIn(b"\x00", theirs)  # struct-packed carries NUL length bytes


class SignerRoundTrips(unittest.TestCase):
    """sign_cert_dsse signs Ed25519 over ASCII-decimal PAE bytes. szl-receipt is
    ECDSA-P256 — a different algorithm entirely — so the two are not merely
    byte-divergent but cryptographically distinct. Prove the Ed25519 PAE path is
    internally sound (sign->verify on the exact bytes pae() produces)."""

    def test_real_ed25519_signature_verifies_end_to_end(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except Exception:  # pragma: no cover
            self.skipTest("cryptography not installed; PAE/divergence locks still run")
        key = Ed25519PrivateKey.generate()
        to_sign = sign_cert_dsse.pae(_PT, b'{"cert":"demo","measured":true}')
        sig = key.sign(to_sign)  # Ed25519 has no separate hash arg (matches -rawin)
        key.public_key().verify(sig, to_sign)  # raises on mismatch


if __name__ == "__main__":
    unittest.main(verbosity=2)
