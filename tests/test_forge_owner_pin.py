"""Owner-key pin contract for the forge-family wall (stdlib unittest, no network).

owner_pubkey.json and both signed receipts are fetched from the mutable public
Hugging Face head, so an unset A11OY_*_OWNER_KEYID must NOT mean "trust whatever
key was fetched". Synthetic ed25519 keys only; HTTP is stubbed, nothing reaches
huggingface.co. Target module: env FORGE_PIN_TARGET, default <repo>/a11oy_forge_family.py
(the target must sit in the repo root so model_release/ resolves).
"""
import asyncio
import base64
import hashlib
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
TARGET = os.environ.get("FORGE_PIN_TARGET") or str(ROOT / "a11oy_forge_family.py")
_spec = importlib.util.spec_from_file_location("forge_under_test", TARGET)
FORGE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FORGE)

KHIPU = next(m for m in FORGE._MODELS if m["model"] == "khipu")
RECEIPT_AGENT = next(m for m in FORGE._MODELS if m["model"] == "receiptagent")
ENV_NAMES = [m["pinEnv"] for m in FORGE._MODELS] + ["A11OY_TEST_UNPINNED_OWNER_KEYID"]


def _signed_files(private_key):
    spki = private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    spki_b64 = base64.b64encode(spki).decode("ascii")
    key_id = hashlib.sha256(spki).hexdigest()[:16]

    def receipt(payload):
        canonical = FORGE._canonical(payload)
        return {"payload": payload, "canonical": canonical,
                "signatureBase64": base64.b64encode(private_key.sign(canonical.encode("utf-8"))).decode("ascii"),
                "publicKeySpkiBase64": spki_b64, "keyId": key_id}

    training = receipt({"kind": "training-receipt", "keyId": key_id, "baseModel": "synthetic",
                        "trainedAt": "2026-11-03T00:00:00Z", "finalTrainLoss": 0.1})
    evaluation = receipt({"kind": "evaluation-receipt", "keyId": key_id,
                          "evaluatedAt": "2026-11-03T00:00:01Z",
                          "trainingReceiptSha256": hashlib.sha256(training["canonical"].encode("utf-8")).hexdigest(),
                          "planValid": 6, "planTotal": 6, "groundingCorrect": 6, "groundingTotal": 6,
                          "abstainCorrect": 6, "abstainTotal": 6, "hallucinatedCitationCount": 0})
    files = {"owner_pubkey.json": json.dumps({"algo": "ed25519", "keyId": key_id, "publicKeySpkiBase64": spki_b64}).encode(),
             "training_receipt.signed.json": json.dumps(training).encode(),
             "eval_receipt.signed.json": json.dumps(evaluation).encode()}
    return files, key_id


ATTACKER_FILES, ATTACKER_KEYID = _signed_files(Ed25519PrivateKey.generate())
NO_BUILTIN = {k: v for k, v in KHIPU.items() if k != "builtinKeyId"}
NO_BUILTIN["pinEnv"] = "A11OY_TEST_UNPINNED_OWNER_KEYID"


def _env(pin_env, value):
    env = {k: v for k, v in os.environ.items() if k not in ENV_NAMES}
    if value is not None:
        env[pin_env] = value
    return mock.patch.dict(os.environ, env, clear=True)


def _band(cfg, value, files=ATTACKER_FILES):
    with _env(cfg["pinEnv"], value):
        return FORGE._band_for_model(cfg, files, 0.0)


class _Resp:
    def __init__(self, content=None, payload=None):
        self.content, self._payload = content, payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _StubHub:
    """Serves attacker-controlled bytes for any repo; records every URL."""
    urls = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        _StubHub.urls.append(url)
        if "/api/models/" in url:
            return _Resp(payload={"sha": "c" * 40})
        return _Resp(content=ATTACKER_FILES[url.rsplit("/", 1)[1]])


class OwnerPin(unittest.TestCase):
    def assertRefused(self, band, trust, boundary):
        self.assertIs(band["verified"], False)
        self.assertEqual(band["keyTrust"], trust)
        layer = band["verificationLayers"]["receiptSignatureValidity"]
        self.assertEqual(layer["trustBoundary"], boundary)
        self.assertIs(layer["training"], False)
        self.assertIs(layer["evaluation"], False)
        self.assertIs(layer["verified"], False)
        self.assertIn("TRAINING_RECEIPT_FAILED", band["status"])
        self.assertIn("EVAL_RECEIPT_FAILED", band["status"])

    # reproduction: passes only on a fail-closed module, FAILS on the unpatched file
    def test_repro_unset_pin_refuses_attacker_owner_key(self):
        self.assertRefused(_band(KHIPU, None), "PIN_MISMATCH", "PIN_MISMATCH_FAIL_CLOSED")

    def test_repro_handler_with_stubbed_hub_refuses_attacker_key(self):
        _StubHub.urls = []
        FORGE._byte_cache.clear()
        with _env("UNUSED", None), mock.patch.object(FORGE, "_MODELS", (KHIPU,)), \
                mock.patch.object(FORGE.httpx, "AsyncClient", _StubHub):
            out = asyncio.run(FORGE._forge_family_handler())
        self.assertTrue(_StubHub.urls, "stub must have served the fetches")
        self.assertIs(out["ok"], False)
        self.assertEqual(len(out["models"]), 1)
        self.assertNotIn("error", out["models"][0], "refusal must be visible, not an exception band")
        self.assertRefused(out["models"][0], "PIN_MISMATCH", "PIN_MISMATCH_FAIL_CLOSED")

    def test_empty_and_whitespace_pin_refuse_attacker_key(self):
        for value in ("", "   ", "\n"):
            with self.subTest(pin=repr(value)):
                self.assertRefused(_band(KHIPU, value), "PIN_MISMATCH", "PIN_MISMATCH_FAIL_CLOSED")

    def test_malformed_pin_refuses(self):
        for value in ("abc", "Z" * 16, ATTACKER_KEYID.upper() if ATTACKER_KEYID.upper() != ATTACKER_KEYID else "X" + ATTACKER_KEYID[1:],
                      ATTACKER_KEYID + "0", ATTACKER_KEYID[:15]):
            with self.subTest(pin=value):
                self.assertRefused(_band(KHIPU, value), "PIN_MISMATCH", "PIN_MISMATCH_FAIL_CLOSED")

    def test_wrong_pin_refuses(self):
        self.assertRefused(_band(KHIPU, "0" * 16), "PIN_MISMATCH", "PIN_MISMATCH_FAIL_CLOSED")

    def test_unpinned_without_builtin_is_refused(self):
        for value in (None, "", "  "):
            with self.subTest(pin=repr(value)):
                self.assertRefused(_band(NO_BUILTIN, value), "UNPINNED_REFUSED", "UNPINNED_OWNER_KEY_FAIL_CLOSED")

    def test_correct_env_pin_verifies(self):
        for cfg in (KHIPU, NO_BUILTIN):
            with self.subTest(model=cfg["pinEnv"]):
                band = _band(cfg, ATTACKER_KEYID)
                self.assertEqual(band["keyTrust"], "PINNED")
                self.assertEqual(band["verificationLayers"]["receiptSignatureValidity"]["trustBoundary"], "PINNED_OWNER_KEY")
                self.assertIs(band["verified"], True)

    def test_unset_pin_falls_back_to_code_pin(self):
        cfg = dict(KHIPU, builtinKeyId=ATTACKER_KEYID)
        for value in (None, "", "  "):
            with self.subTest(pin=repr(value)):
                band = _band(cfg, value)
                self.assertEqual(band["keyTrust"], "CODE_PINNED")
                self.assertEqual(band["verificationLayers"]["receiptSignatureValidity"]["trustBoundary"], "CODE_PINNED_OWNER_KEY")
                self.assertIs(band["verified"], True)

    def test_env_pin_overrides_code_pin(self):
        cfg = dict(KHIPU, builtinKeyId=ATTACKER_KEYID)
        self.assertRefused(_band(cfg, "0" * 16), "PIN_MISMATCH", "PIN_MISMATCH_FAIL_CLOSED")

    def test_builtin_pins_match_committed_owner_keyids(self):
        recon = json.loads(FORGE._RECONCILIATION_PATH.read_text(encoding="utf-8"))
        committed = json.dumps(recon)
        self.assertEqual(RECEIPT_AGENT["builtinKeyId"], "e7f01810aaa97394")
        self.assertIn('"key_id": "%s"' % RECEIPT_AGENT["builtinKeyId"], committed)
        self.assertEqual(KHIPU["builtinKeyId"], "89540347a69b789e")
        for cfg in FORGE._MODELS:
            self.assertIn("owner keyId %s)" % cfg["builtinKeyId"], FORGE.__doc__)


if __name__ == "__main__":
    unittest.main(verbosity=2)
