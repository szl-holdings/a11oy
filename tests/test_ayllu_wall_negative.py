"""Negative and positive controls for the Ayllu wall verifier.

Real P-256 ECDSA through `cryptography`, synthetic keys and synthetic decisions only.
The transport is faked (no network); no production key or signing secret is used.
Run: python -B -m pytest tests/test_ayllu_wall_negative.py -q
"""
import asyncio
import base64
import copy
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import a11oy_ayllu_wall as wall  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402

PTYPE = "application/vnd.szl.receipt+json"


def _pem(key):
    return key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


def _decision(key, ptype=PTYPE, keyid="szlholdings-cosign"):
    body = {"council_id": "c-synthetic", "chain": {"receipt_id": "r-1", "seq": 1},
            "mode": "synthetic", "decision_state": "ALLOW"}
    payload = {"body": body, "payload_digest": wall._sha256_hex(wall._canonical(body)),
               "receipt_id": "r-1"}
    raw = json.dumps(payload).encode()
    sign_type = PTYPE if ptype is None else ptype
    sig = key.sign(wall._pae(sign_type, raw), ec.ECDSA(hashes.SHA256()))
    env = {"payload": base64.b64encode(raw).decode(), "payloadType": ptype,
           "signatures": [{"keyid": keyid, "sig": base64.b64encode(sig).decode()}]}
    if ptype is None:
        env.pop("payloadType")
    return {"receipt": env}


class _Client:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class VerifyDecision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k1 = ec.generate_private_key(ec.SECP256R1())
        cls.k2 = ec.generate_private_key(ec.SECP256R1())
        cls.pk1 = wall.load_pem_public_key(_pem(cls.k1))
        cls.fpr = wall._sha256_hex(_pem(cls.k1))

    def verified(self, doc):
        return wall._verify_decision(doc, self.pk1, self.fpr)["verified"]

    def test_positive_control(self):
        out = wall._verify_decision(_decision(self.k1), self.pk1, self.fpr)
        self.assertTrue(out["verified"])
        self.assertEqual(out["derived"]["decisionState"], "ALLOW")

    def test_expected_type_matches_council_signer(self):
        signer = (ROOT / "a11oy_ayllu.py").read_text(encoding="utf-8")
        self.assertEqual(wall._EXPECTED_PAYLOAD_TYPE, PTYPE)
        self.assertIn('"' + PTYPE + '"', signer)

    def test_valid_signature_under_other_type_is_refused(self):
        for ptype in ("application/vnd.szl.khipu+json", "application/vnd.in-toto+json", ""):
            with self.subTest(ptype=ptype):
                out = wall._verify_decision(_decision(self.k1, ptype=ptype), self.pk1, self.fpr)
                self.assertFalse(out["verified"])
                self.assertFalse(out["checks"]["payloadTypeExpected"])
                self.assertIsNone(out["derived"])

    def test_missing_type_is_refused(self):
        self.assertFalse(self.verified(_decision(self.k1, ptype=None)))

    def test_type_swapped_after_signing(self):
        d = _decision(self.k1)
        d["receipt"]["payloadType"] = "application/vnd.other+json"
        self.assertFalse(self.verified(d))

    def test_altered_payload_with_recomputed_digest(self):
        d = copy.deepcopy(_decision(self.k1))
        pl = json.loads(base64.b64decode(d["receipt"]["payload"]))
        pl["body"]["decision_state"] = "DENY"
        pl["payload_digest"] = wall._sha256_hex(wall._canonical(pl["body"]))
        d["receipt"]["payload"] = base64.b64encode(json.dumps(pl).encode()).decode()
        self.assertFalse(self.verified(d))

    def test_invalid_signatures(self):
        bad = {
            "wrong key": _decision(self.k2),
            "no signatures": dict(_decision(self.k1), receipt=dict(_decision(self.k1)["receipt"], signatures=[])),
            "label only": dict(_decision(self.k1), receipt=dict(
                _decision(self.k1)["receipt"], signatures=[{"keyid": "SIGNED_VERIFIED", "sig": "a" * 64}])),
            "not base64": dict(_decision(self.k1), receipt=dict(
                _decision(self.k1)["receipt"], signatures=[{"keyid": "k", "sig": "%%%"}])),
        }
        for name, doc in bad.items():
            with self.subTest(name=name):
                self.assertFalse(self.verified(doc))

    def test_malformed_envelopes(self):
        good = _decision(self.k1)["receipt"]
        cases = {
            "empty document": {},
            "empty receipt": {"receipt": {}},
            "payload not base64": {"receipt": dict(good, payload="***")},
            "payload not json": {"receipt": dict(good, payload=base64.b64encode(b"not json").decode())},
        }
        for name, doc in cases.items():
            with self.subTest(name=name):
                out = wall._verify_decision(doc, self.pk1, self.fpr)
                self.assertFalse(out["verified"])
                self.assertIsNone(out["derived"])


class WallPin(unittest.TestCase):
    def run_wall(self, served_pem, builtin, doc, env_pin=None):
        index = json.dumps({"decisions": ["d1.json"]}).encode()

        async def fake_fetch(client, path):
            if path == wall._KEY_PATH:
                return served_pem
            if path == wall._INDEX_PATH:
                return index
            return doc if isinstance(doc, bytes) else json.dumps(doc).encode()

        env = {k: v for k, v in os.environ.items() if k != wall._PIN_ENV}
        if env_pin is not None:
            env[wall._PIN_ENV] = env_pin
        with mock.patch.object(wall, "_fetch", fake_fetch), \
                mock.patch.object(wall, "_BUILTIN_PIN", builtin), \
                mock.patch.object(wall.httpx, "AsyncClient", _Client), \
                mock.patch.dict(os.environ, env, clear=True):
            return asyncio.run(wall._wall_payload())["decisions"][0]

    @classmethod
    def setUpClass(cls):
        cls.k1 = ec.generate_private_key(ec.SECP256R1())
        cls.k2 = ec.generate_private_key(ec.SECP256R1())
        cls.pem1, cls.pem2 = _pem(cls.k1), _pem(cls.k2)
        cls.fpr1 = wall._sha256_hex(cls.pem1)

    def test_pinned_key_positive_control(self):
        band = self.run_wall(self.pem1, self.fpr1, _decision(self.k1))
        self.assertTrue(band["verified"])
        self.assertNotIn("untrustedDiagnostics", band)

    def test_swapped_key_isolates_untrusted_results(self):
        band = self.run_wall(self.pem2, self.fpr1, _decision(self.k2))
        self.assertFalse(band["verified"])
        self.assertEqual(band["status"], "PIN_MISMATCH_FAILED_CLOSED")
        self.assertIsNone(band["derived"])
        self.assertEqual(band["checks"], {"keyPinned": False})
        diag = band["untrustedDiagnostics"]
        self.assertTrue(diag["label"].startswith("UNTRUSTED"))
        self.assertTrue(diag["checksAgainstUnpinnedKey"]["ecdsaSignatureVerifiesOverPae"])
        self.assertNotIn("ALLOW", json.dumps(band))

    def test_wrong_env_pin_fails_closed(self):
        band = self.run_wall(self.pem1, self.fpr1, _decision(self.k1), env_pin="0" * 64)
        self.assertFalse(band["verified"])
        self.assertIsNone(band["derived"])

    def test_malformed_decision_file_fails_closed(self):
        band = self.run_wall(self.pem1, self.fpr1, b"[1, 2")
        self.assertFalse(band["verified"])
        self.assertEqual(band["status"], "UNAVAILABLE")

    def test_receipt_of_wrong_shape_fails_closed(self):
        band = self.run_wall(self.pem1, self.fpr1, {"receipt": ["not", "a", "mapping"]})
        self.assertFalse(band["verified"])


if __name__ == "__main__":
    unittest.main()
