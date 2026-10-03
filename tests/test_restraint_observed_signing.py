#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Operator and cryptographic proof boundaries for the restraint write route."""

import base64
import json
import os
import sys
import types
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import szl_frontier_manifest as frontier  # noqa: E402
import szl_operator_auth as auth  # noqa: E402
import szl_restraint as restraint  # noqa: E402


OPERATOR = "restraint-test-operator-not-real"
HEADERS = {"Authorization": f"Bearer {OPERATOR}"}
PATH = "/api/a11oy/v1/restraint/evaluate"


def _pae(payload_type, body):
    ptype = payload_type.encode("utf-8")
    return (b"DSSEv1 " + str(len(ptype)).encode() + b" " + ptype + b" "
            + str(len(body)).encode() + b" " + body)


class _TestKey:
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        public = self.key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.keyid = sha256(public.strip()).hexdigest()
        self.sign_calls = 0
        self.verify_calls = 0

    def sign(self, payload):
        self.sign_calls += 1
        body = json.dumps({**payload, "_signing_identity": {"keyid": self.keyid}},
                          sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")
        payload_type = "application/vnd.szl.receipt+json"
        signature = self.key.sign(_pae(payload_type, body), ec.ECDSA(hashes.SHA256()))
        return {
            "payloadType": payload_type,
            "payload": base64.b64encode(body).decode("ascii"),
            "_dsse": "DSSEv1",
            "signed": True,
            "signatures": [{"keyid": self.keyid,
                            "sig": base64.b64encode(signature).decode("ascii")}],
        }

    def verify(self, envelope):
        self.verify_calls += 1
        try:
            body = base64.b64decode(envelope["payload"], validate=True)
            signature = base64.b64decode(envelope["signatures"][0]["sig"], validate=True)
            self.key.public_key().verify(
                signature, _pae(envelope["payloadType"], body), ec.ECDSA(hashes.SHA256())
            )
            return {"signature_valid": True, "keyid_verified": self.keyid}
        except (InvalidSignature, ValueError, KeyError, IndexError):
            return {"signature_valid": False}


class _DeterministicCache:
    def __init__(self, ttl):
        self.ttl = ttl
        self.value = None
        self.compositions = 0

    def get_or_compute(self, producer):
        if self.value is None:
            self.value = producer()
            self.compositions += 1
        return self.value

    def invalidate(self):
        self.value = None


class RestraintObservedSigning(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {auth.OPERATOR_KEY_ENV: OPERATOR,
                                        "A11OY_CODE_AUTH_MODE": "lenient"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def _app(self, *, middleware=True):
        app = FastAPI()
        frontier.register(app)
        restraint.register(app)
        if middleware:
            auth.install_gate(app)
        return app, TestClient(app)

    @staticmethod
    def _governance(client):
        response = client.get("/api/a11oy/v1/frontier/manifest")
        assert response.status_code == 200, response.text
        return next(tile for tile in response.json()["capabilities"]
                    if tile["category"] == "governance")

    def test_operator_gate_precedes_body_and_signer_even_in_lenient_configuration(self):
        self.assertEqual(auth.protected_action("POST", PATH)[1], "sign")
        for middleware in (True, False):
            with self.subTest(middleware=middleware):
                app, client = self._app(middleware=middleware)
                key = _TestKey()
                app.state.szl_sign_receipt = key.sign
                app.state.szl_verify_receipt = key.verify
                for headers in ({}, {"Authorization": "Bearer wrong"}):
                    response = client.post(PATH, headers=headers, json={"task": "add a cache"})
                    self.assertEqual(response.status_code, 401, response.text)
                    self.assertEqual(response.json()["status"], "BLOCKED")
                self.assertEqual(key.sign_calls, 0)
                self.assertEqual(key.verify_calls, 0)
                self.assertFalse(client.get("/api/a11oy/v1/restraint/info").json()
                                 ["doctrine"]["signed_receipts"])
                with patch.dict(os.environ, {auth.OPERATOR_KEY_ENV: ""}):
                    self.assertEqual(client.post(PATH, headers=HEADERS,
                                                 json={"task": "add a cache"}).status_code, 401)
                self.assertEqual(key.sign_calls, 0)

    def test_late_bound_host_key_roundtrip_and_reads_never_sign(self):
        app, client = self._app()
        key = _TestKey()
        before = client.get("/api/a11oy/v1/restraint/info").json()
        self.assertFalse(before["signer_health"]["ready"])
        self.assertFalse(frontier._tile_governance(app)["signature_verified"])
        app.state.szl_sign_receipt = key.sign
        app.state.szl_verify_receipt = key.verify
        self.assertEqual(key.sign_calls, 0)

        response = client.post(PATH, headers=HEADERS, json={"task": "add a cache"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["signed_receipt"]["signed"])
        self.assertEqual((key.sign_calls, key.verify_calls), (1, 1))
        info = client.get("/api/a11oy/v1/restraint/info").json()
        self.assertTrue(info["signer_health"]["observed_this_process"])
        self.assertEqual(info["signer_health"]["identity"], key.keyid)
        self.assertTrue(info["receipt_verification"]["cryptographically_verified"])
        self.assertEqual(info["receipt_verification"]["signature_count"], 1)
        self.assertTrue(frontier._tile_governance(app)["signature_verified"])
        self.assertEqual((key.sign_calls, key.verify_calls), (1, 1))

        app.state.szl_verify_receipt = None
        self.assertFalse(client.get("/api/a11oy/v1/restraint/info").json()
                         ["receipt_verification"]["cryptographically_verified"])
        self.assertFalse(frontier._tile_governance(app)["signature_verified"])

    def test_missing_key_verifier_unsigned_and_tampering_all_block(self):
        app, client = self._app()
        key = _TestKey()
        missing = client.post(PATH, headers=HEADERS, json={"task": "add a cache"})
        self.assertEqual(missing.status_code, 503)
        self.assertEqual(missing.json()["reason"], "SIGNER_OR_VERIFIER_UNAVAILABLE")
        self.assertEqual(key.sign_calls, 0)

        app.state.szl_sign_receipt = key.sign
        no_verifier = client.post(PATH, headers=HEADERS, json={"task": "add a cache"})
        self.assertEqual(no_verifier.status_code, 503)
        self.assertEqual(key.sign_calls, 0)
        app.state.szl_verify_receipt = key.verify
        app.state.szl_sign_receipt = lambda payload: {"signed": False, "signatures": []}
        unsigned = client.post(PATH, headers=HEADERS, json={"task": "add a cache"})
        self.assertEqual(unsigned.status_code, 503)
        self.assertEqual(unsigned.json()["reason"], "SIGNED_RECEIPT_VERIFICATION_FAILED")

        def corrupt_signature(payload):
            envelope = key.sign(payload)
            envelope["signatures"][0]["sig"] = base64.b64encode(b"bad").decode("ascii")
            return envelope

        app.state.szl_sign_receipt = corrupt_signature
        tampered = client.post(PATH, headers=HEADERS, json={"task": "add a cache"})
        self.assertEqual(tampered.status_code, 503)
        self.assertFalse(client.get("/api/a11oy/v1/restraint/info").json()
                         ["signer_health"]["ready"])

        def change_payload(payload):
            return key.sign({**payload, "task_digest": "changed"})

        app.state.szl_sign_receipt = change_payload
        mismatch = client.post(PATH, headers=HEADERS, json={"task": "add a cache"})
        self.assertEqual(mismatch.status_code, 503)
        self.assertFalse(frontier._tile_governance(app)["signature_verified"])

    def test_new_app_process_observation_starts_unverified(self):
        app, client = self._app()
        key = _TestKey()
        app.state.szl_sign_receipt = key.sign
        app.state.szl_verify_receipt = key.verify
        self.assertEqual(client.post(PATH, headers=HEADERS,
                                     json={"task": "add a cache"}).status_code, 200)
        new_app, new_client = self._app()
        new_app.state.szl_sign_receipt = key.sign
        new_app.state.szl_verify_receipt = key.verify
        self.assertFalse(new_client.get("/api/a11oy/v1/restraint/info").json()
                         ["receipt_verification"]["cryptographically_verified"])
        self.assertFalse(frontier._tile_governance(new_app)["signature_verified"])

    def test_two_apps_keep_observations_and_cached_frontier_separate(self):
        cache_module = types.SimpleNamespace(TTLCache=_DeterministicCache)
        with patch.dict(sys.modules, {"szl_backend_hardening": cache_module}):
            app_a, client_a = self._app()
            app_b, client_b = self._app()
            self.assertFalse(self._governance(client_a)["signature_verified"])
            self.assertFalse(self._governance(client_b)["signature_verified"])
            cache_a = app_a.state.szl_frontier_manifest_cache
            cache_b = app_b.state.szl_frontier_manifest_cache
            self.assertIsNot(cache_a, cache_b)
            self.assertEqual((cache_a.compositions, cache_b.compositions), (1, 1))

            key = _TestKey()
            app_b.state.szl_sign_receipt = key.sign
            app_b.state.szl_verify_receipt = key.verify
            self.assertEqual(client_b.post(PATH, headers=HEADERS,
                                           json={"task": "add a cache"}).status_code, 200)
            self.assertTrue(self._governance(client_b)["signature_verified"])
            self.assertEqual(cache_b.compositions, 2)
            self.assertFalse(self._governance(client_a)["signature_verified"])
            self.assertEqual(cache_a.compositions, 1)

            app_b.state.szl_sign_receipt = lambda payload: {"signed": False, "signatures": []}
            self.assertEqual(client_b.post(PATH, headers=HEADERS,
                                           json={"task": "add a cache"}).status_code, 503)
            self.assertFalse(self._governance(client_b)["signature_verified"])
            self.assertEqual(cache_b.compositions, 3)
            self.assertFalse(self._governance(client_a)["signature_verified"])

    def test_real_ttl_cache_cannot_retain_ready_after_failure_or_verifier_loss(self):
        import szl_backend_hardening as hardening

        app_a, client_a = self._app()
        app_b, client_b = self._app()
        self.assertFalse(self._governance(client_a)["signature_verified"])
        self.assertFalse(self._governance(client_b)["signature_verified"])
        cache_a = app_a.state.szl_frontier_manifest_cache
        cache_b = app_b.state.szl_frontier_manifest_cache
        self.assertIsInstance(cache_a, hardening.TTLCache)
        self.assertIsInstance(cache_b, hardening.TTLCache)
        self.assertIsNot(cache_a, cache_b)
        self.assertIsNotNone(cache_b.peek())

        key = _TestKey()
        app_b.state.szl_sign_receipt = key.sign
        app_b.state.szl_verify_receipt = key.verify
        self.assertEqual(client_b.post(PATH, headers=HEADERS,
                                       json={"task": "add a cache"}).status_code, 200)
        self.assertTrue(self._governance(client_b)["signature_verified"])
        self.assertFalse(self._governance(client_a)["signature_verified"])
        sign_calls = key.sign_calls
        self.assertTrue(self._governance(client_b)["signature_verified"])
        self.assertEqual(key.sign_calls, sign_calls)

        app_b.state.szl_sign_receipt = lambda payload: {"signed": False, "signatures": []}
        self.assertEqual(client_b.post(PATH, headers=HEADERS,
                                       json={"task": "add a cache"}).status_code, 503)
        self.assertFalse(self._governance(client_b)["signature_verified"])
        self.assertFalse(self._governance(client_a)["signature_verified"])

        app_b.state.szl_sign_receipt = key.sign
        self.assertEqual(client_b.post(PATH, headers=HEADERS,
                                       json={"task": "add a cache"}).status_code, 200)
        self.assertTrue(self._governance(client_b)["signature_verified"])
        app_b.state.szl_verify_receipt = None
        self.assertFalse(self._governance(client_b)["signature_verified"])
        self.assertFalse(self._governance(client_a)["signature_verified"])
        self.assertEqual(key.sign_calls, sign_calls + 1)

    def test_frontier_reads_only_the_module_that_registered_the_route(self):
        def unrelated_info():
            raise AssertionError("unrelated substrate module must not be read")

        substrate = types.ModuleType("szl_substrate")
        substrate.szl_restraint = types.SimpleNamespace(info=unrelated_info)
        with patch.dict(sys.modules, {"szl_substrate": substrate}):
            app, client = self._app()
            key = _TestKey()
            app.state.szl_sign_receipt = key.sign
            app.state.szl_verify_receipt = key.verify
            self.assertEqual(client.post(PATH, headers=HEADERS,
                                         json={"task": "add a cache"}).status_code, 200)
            self.assertTrue(self._governance(client)["signature_verified"])

            unregistered = FastAPI()
            frontier.register(unregistered)
            self.assertFalse(self._governance(TestClient(unregistered))["signature_verified"])


if __name__ == "__main__":
    unittest.main()
