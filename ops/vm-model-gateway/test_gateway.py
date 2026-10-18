#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Loopback fixture tests for the isolated VM model gateway."""

import base64
import http.client
import importlib.util
import json
import os
import pathlib
import tempfile
import threading
import unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("vm_model_gateway", HERE / "gateway.py")
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)
KEY = "t" * 40


def completion(model=gateway.RAW_MODEL, content='{"ok":true}', finish="stop"):
    return {
        "id": "fixture-1", "object": "chat.completion", "created": 1, "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
    }


class UpstreamFixture(BaseHTTPRequestHandler):
    state = None
    def log_message(self, *_args):
        pass
    def respond(self, status, obj):
        raw = gateway.canonical(obj)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        self.state["gets"].append(self.path)
        if self.path == "/slots":
            return self.respond(200, [{"id": 0, "is_processing": self.state["busy"]}])
        if self.path == "/v1/models":
            return self.respond(200, {"data": [{"id": self.state["model_id"]}]})
        return self.respond(404, {"error": "unknown"})
    def do_POST(self):
        self.state["posts"] += 1
        self.state["request"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.state["redirect"]:
            self.send_response(307)
            self.send_header("Location", "http://127.0.0.1:9/elsewhere")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        return self.respond(200, self.state["response"])


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key = ec.generate_private_key(ec.SECP256R1())
        cls.old_pem = os.environ.get("SZL_COSIGN_PRIVATE_PEM")
        os.environ["SZL_COSIGN_PRIVATE_PEM"] = key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")

    @classmethod
    def tearDownClass(cls):
        if cls.old_pem is None:
            os.environ.pop("SZL_COSIGN_PRIVATE_PEM", None)
        else:
            os.environ["SZL_COSIGN_PRIVATE_PEM"] = cls.old_pem

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="szl-vm-gateway-test-")
        self.state = {"gets": [], "posts": 0, "request": None, "busy": False,
                      "redirect": False, "response": completion(), "model_id": gateway.RAW_MODEL}
        upstream_type = type("Fixture", (UpstreamFixture,), {"state": self.state})
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), upstream_type)
        self.upstream_thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.upstream_thread.start()
        self.adapter = gateway.Gateway(KEY, self.tmp.name, upstream_port=self.upstream.server_port)
        gateway_type = type("TestHandler", (gateway.Handler,), {"gateway": self.adapter})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), gateway_type)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.server_thread.join(2)
        self.upstream.shutdown(); self.upstream.server_close(); self.upstream_thread.join(2)
        self.tmp.cleanup()

    def request(self, method="POST", path="/v1/chat/completions", obj=None, auth=True, headers=None, raw=None):
        if obj is None:
            obj = {"model": gateway.ALIAS, "messages": [{"role": "user", "content": "hi"}],
                   "stream": False, "max_tokens": 8, "temperature": 0}
        body = gateway.canonical(obj) if raw is None else raw
        defaults = {"Content-Type": "application/json"}
        if auth:
            defaults["Authorization"] = "Bearer " + KEY
        if headers:
            defaults.update(headers)
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            conn.request(method, path, body=body if method == "POST" else None, headers=defaults)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def receipts(self):
        return sorted(pathlib.Path(self.tmp.name).glob("*.dsse.json"))

    def test_unauthorized_never_forwards_or_receipts(self):
        status, _ = self.request(auth=False)
        self.assertEqual(status, 401)
        self.assertEqual(self.state["gets"], [])
        self.assertEqual(self.state["posts"], 0)
        self.assertEqual(self.receipts(), [])

    def test_models_auth_and_exact_identity(self):
        self.assertEqual(self.request("GET", "/v1/models", auth=False)[0], 401)
        self.assertEqual(self.state["gets"], [])
        status, body = self.request("GET", "/v1/models")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"][0]["id"], gateway.ALIAS)
        self.assertEqual(self.receipts(), [])
        self.state["model_id"] = "wrong"
        self.assertEqual(self.request("GET", "/v1/models")[0], 503)

    def test_busy_slot_rejects_before_effect(self):
        self.state["busy"] = True
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.state["posts"], 0)
        self.assertEqual(self.receipts(), [])

    def test_unknown_model_and_request_fields_rejected(self):
        for changed in ({"model": "wrong"}, {"tools": []}, {"stream": True}, {"max_tokens": 1025}):
            request = {"model": gateway.ALIAS, "messages": [{"role": "user", "content": "hi"}],
                       "stream": False, "max_tokens": 8, "temperature": 0, **changed}
            self.assertEqual(self.request(obj=request)[0], 400)
        self.assertEqual(self.state["gets"], [])
        self.assertEqual(self.state["posts"], 0)

    def test_duplicate_json_nonfinite_and_oversize_rejected(self):
        self.assertEqual(self.request(raw=b'{"model":"a","model":"b"}')[0], 400)
        self.assertEqual(self.request(raw=b'{"model":NaN}')[0], 400)
        self.assertEqual(self.request(raw=b"x" * 65537)[0], 400)
        self.assertEqual(self.state["posts"], 0)

    def test_valid_forward_and_signed_hash_chain(self):
        status, body = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(body["model"], gateway.ALIAS)
        self.assertEqual(body["choices"][0]["message"], {"role": "assistant", "content": '{"ok":true}'})
        self.assertEqual(self.state["request"]["model"], gateway.RAW_MODEL)
        self.assertEqual(self.state["posts"], 1)
        receipts = self.receipts()
        self.assertEqual(len(receipts), 2)
        envelopes = [json.loads(path.read_bytes()) for path in receipts]
        for envelope in envelopes:
            self.assertTrue(gateway.szl_dsse.verify_envelope(envelope)["verified"])
            self.assertEqual(envelope["key_trust"], "REPO_DECLARED")
            self.assertNotIn("verify_key_url", envelope)
        by_phase = {json.loads(base64.b64decode(env["payload"]))["phase"]: env for env in envelopes}
        intent = json.loads(base64.b64decode(by_phase["intent"]["payload"]))
        outcome = json.loads(base64.b64decode(by_phase["outcome"]["payload"]))
        self.assertEqual(outcome["previous_sha256"], gateway.digest(gateway.canonical(by_phase["intent"])))
        self.assertEqual(intent["upstream_request_sha256"], gateway.digest(gateway.canonical(self.state["request"])))
        self.assertEqual(outcome["status"], "VALIDATED_RESPONSE")

    def test_wrong_upstream_echo_and_redirect_fail_closed_signed(self):
        self.state["response"] = completion(model="wrong")
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(len(self.receipts()), 2)
        self.state["redirect"] = True
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(len(self.receipts()), 4)
        self.assertEqual(self.state["posts"], 2)

    def test_signing_failure_prevents_forward(self):
        class BadSigner:
            @staticmethod
            def signing_available(): return True
            @staticmethod
            def sign_payload(*_args): raise RuntimeError("offline")
            @staticmethod
            def verify_envelope(*_args): return {"verified": False}
        self.adapter.signer = BadSigner()
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.state["posts"], 0)

    def test_health_public_minimal(self):
        status, body = self.request("GET", "/health", auth=False)
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "local_gateway", "evidence_class": "DECLARED", "instance_id": self.adapter.instance_id})
        self.assertEqual(self.request("GET", "/health", auth=False)[1], body)
        self.assertEqual(self.state["gets"], [])
        self.assertEqual(self.receipts(), [])

    def test_reopen_verifies_chain_and_rejects_tamper(self):
        self.assertEqual(self.request()[0], 200)
        self.assertIsNotNone(gateway.Gateway(KEY, self.tmp.name, upstream_port=self.upstream.server_port).previous)
        path = self.receipts()[0]
        raw = path.read_bytes()
        path.write_bytes(raw + b" ")
        with self.assertRaises(ValueError):
            gateway.Gateway(KEY, self.tmp.name, upstream_port=self.upstream.server_port)

    def test_intent_persist_failure_latches_without_forward(self):
        with mock.patch.object(gateway.os, "replace", side_effect=OSError("fixture")):
            self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.state["posts"], 0)
        self.assertFalse(self.adapter.signer.signing_available())
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.state["posts"], 0)

    def test_reopen_rejects_incomplete_intent_tail(self):
        self.adapter.append_receipt({"request_id": "a" * 32, "phase": "intent", "effect": "fixture"})
        with self.assertRaisesRegex(ValueError, "incomplete_effect"):
            gateway.Gateway(KEY, self.tmp.name, upstream_port=self.upstream.server_port)

    def test_response_completion_limit_rejected_with_signed_outcome(self):
        self.state["response"]["usage"] = {"prompt_tokens": 2, "completion_tokens": 9, "total_tokens": 11}
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.state["posts"], 1)
        self.assertEqual(len(self.receipts()), 2)

    def test_duplicate_auth_and_content_length_no_forward(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        body = gateway.canonical({"model": gateway.ALIAS, "messages": [{"role": "user", "content": "hi"}],
                                  "stream": False, "max_tokens": 8, "temperature": 0})
        conn.putrequest("POST", "/v1/chat/completions")
        conn.putheader("Authorization", "Bearer " + KEY)
        conn.putheader("Authorization", "Bearer " + KEY)
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        self.assertEqual(conn.getresponse().status, 401)
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        conn.putrequest("POST", "/v1/chat/completions")
        conn.putheader("Authorization", "Bearer " + KEY)
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(len(body)))
        conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        self.assertEqual(conn.getresponse().status, 400)
        conn.close()
        self.assertEqual(self.state["posts"], 0)


if __name__ == "__main__":
    unittest.main()
