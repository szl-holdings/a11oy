#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Admission and restart check for the code run-loop only.

The signer double is unsigned and the receipt evidence class is SIMULATED.
SZL_SECOND_BRAIN_RAG stays unset. This file does not import serve.py.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

if not os.environ.get("A11OY_CODE_DB"):
    _TMP = tempfile.mkdtemp(prefix="a11oy-runloop-admission-")
    os.environ["A11OY_CODE_DB"] = str(Path(_TMP) / "code.db")
    os.environ["A11OY_CODE_SANDBOX"] = str(Path(_TMP) / "sandbox")
    os.environ["A11OY_REACT_DB"] = str(Path(_TMP) / "react.sqlite3")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from starlette.applications import Starlette  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import a11oy_code_engine as engine  # noqa: E402
import a11oy_code_runloop as runloop  # noqa: E402
import szl_operator_auth as opauth  # noqa: E402

OPERATOR = "op-test-secret-not-real"
APPROVER = "approver-test-secret-not-real"
TENANT = "synthetic-tenant"
PLAN = "/api/a11oy/v1/code/plan"
RUNSTEP = "/api/a11oy/v1/code/runstep"
_VERIFIER = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import a11oy_code_runloop as runloop\n"
    "print(json.dumps(runloop.verify_receipt_log(sys.argv[2])))\n"
)


def _unsigned(payload):
    return {"signed": False, "signatures": [], "payloadType": "application/test+json"}


def _forbid_turn(*_args, **_kwargs):
    raise AssertionError("governed_turn must not run before admission")


class CodeRunloopAdmission(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a11oy-runloop-receipt-")
        self.log = Path(self.tmp.name) / "receipts.jsonl"
        self.saved_rag = os.environ.pop("SZL_SECOND_BRAIN_RAG", None)
        self.saved_log = os.environ.pop(runloop.RECEIPT_LOG_ENV, None)
        os.environ[runloop.RECEIPT_LOG_ENV] = str(self.log)
        self.env = patch.dict(os.environ, {
            opauth.OPERATOR_KEY_ENV: OPERATOR,
            opauth.SECOND_APPROVER_KEY_ENV: APPROVER,
            "A11OY_CODE_TENANT": TENANT,
        })
        self.env.start()
        self.model = patch.object(engine, "_model_configured", return_value=False)
        self.model.start()
        app = Starlette()
        runloop.register(app, "a11oy", _unsigned)
        self.client = TestClient(app)

    def tearDown(self):
        self.model.stop()
        self.env.stop()
        if self.saved_rag is None:
            os.environ.pop("SZL_SECOND_BRAIN_RAG", None)
        else:
            os.environ["SZL_SECOND_BRAIN_RAG"] = self.saved_rag
        if self.saved_log is None:
            os.environ.pop(runloop.RECEIPT_LOG_ENV, None)
        else:
            os.environ[runloop.RECEIPT_LOG_ENV] = self.saved_log
        self.tmp.cleanup()

    def _admitted(self):
        return {"Authorization": f"Bearer {OPERATOR}", "X-A11oy-Tenant": TENANT}

    def test_second_brain_flag_stays_off(self):
        self.assertNotIn((os.environ.get("SZL_SECOND_BRAIN_RAG") or "").strip().lower(),
                         {"1", "true", "yes"})

    def test_anonymous_is_refused_before_tenant_and_parse(self):
        with patch.object(runloop._engine, "governed_turn", _forbid_turn):
            response = self.client.post(RUNSTEP, content=b"{")
        self.assertEqual(response.status_code, 401, response.text[:400])
        self.assertEqual(response.json()["status"], "BLOCKED")
        self.assertFalse(self.log.exists())

    def test_wrong_tenant_refuses_before_parse(self):
        cases = (
            {"Authorization": f"Bearer {OPERATOR}", "X-A11oy-Tenant": "other-tenant"},
            {"Authorization": f"Bearer {OPERATOR}", "X-A11oy-Tenant": "synthetic-tenant-extra"},
            {"Authorization": f"Bearer {OPERATOR}"},
        )
        for headers in cases:
            with self.subTest(headers=sorted(headers)), \
                    patch.object(runloop._engine, "governed_turn", _forbid_turn):
                response = self.client.post(RUNSTEP, headers=headers, content=b"{")
            self.assertEqual(response.status_code, 403, response.text[:400])
            self.assertEqual(response.json()["status"], "BLOCKED")
            self.assertTrue(response.json()["tenant_configured"])
            self.assertFalse(self.log.exists())

    def test_unset_tenant_is_unavailable_before_parse(self):
        headers = {"Authorization": f"Bearer {OPERATOR}", "X-A11oy-Tenant": TENANT}
        with patch.dict(os.environ, {"A11OY_CODE_TENANT": ""}), \
                patch.object(runloop._engine, "governed_turn", _forbid_turn):
            response = self.client.post(RUNSTEP, headers=headers, content=b"{")
        self.assertEqual(response.status_code, 503, response.text[:400])
        self.assertFalse(response.json()["tenant_configured"])
        self.assertFalse(self.log.exists())

    def test_purpose_and_limits_refuse_before_the_engine(self):
        cases = (
            {"prompt": "synthetic fixture: deny-by-default gate"},
            {"prompt": "hello", "purpose": "chat", "mode": "code"},
            {"prompt": "x" * 2001, "purpose": "research"},
            {"prompt": 1, "purpose": "chat"},
            {"prompt": "   ", "purpose": "research"},
        )
        for body in cases:
            with self.subTest(body=body), \
                    patch.object(runloop._engine, "governed_turn", _forbid_turn):
                response = self.client.post(RUNSTEP, headers=self._admitted(), json=body)
            self.assertEqual(response.status_code, 400, response.text[:400])
            self.assertEqual(response.json()["status"], "BLOCKED")
            self.assertFalse(self.log.exists())

    def test_lone_surrogate_is_refused_before_the_engine(self):
        with patch.object(runloop._engine, "governed_turn", _forbid_turn):
            query, purpose, refusal = runloop._admit_query(
                {"prompt": "\ud800", "purpose": "research"}, "prompt")
        self.assertIsNone(query)
        self.assertIsNone(purpose)
        self.assertEqual(refusal.status_code, 400)
        self.assertFalse(self.log.exists())

    def test_chat_purpose_is_not_reclassified_as_code(self):
        response = self.client.post(PLAN, headers=self._admitted(), json={
            "task": "def f():\n    return 1",
            "purpose": "chat",
            "mode": "",
        })
        self.assertEqual(response.status_code, 200, response.text[:400])
        payload = response.json()
        self.assertEqual(payload["mode"], "chat")
        self.assertEqual(payload["purpose"], "chat")
        self.assertTrue(payload["plan"])
        self.assertTrue(all(step["mode"] == "chat" for step in payload["plan"]))

    def test_missing_engine_writes_no_receipt(self):
        os.environ[runloop.RECEIPT_LOG_ENV] = str(self.log)
        with patch.object(runloop, "_ENGINE_OK", False), \
                patch.object(runloop, "_ENGINE_ERR", "hidden", create=True):
            response = self.client.post(RUNSTEP, headers=self._admitted(), json={
                "purpose": "research",
                "mode": "research",
                "prompt": runloop.FIXED_SYNTHETIC_QUERY,
                "sandbox": False,
            })
        self.assertEqual(response.status_code, 200, response.text[:400])
        self.assertFalse(response.json()["ok"])
        self.assertNotIn("restart_receipt", response.json())
        self.assertFalse(self.log.exists())

    def test_invalid_json_is_refused_before_the_engine(self):
        with patch.object(runloop._engine, "governed_turn", _forbid_turn):
            response = self.client.post(RUNSTEP, headers=self._admitted(), content=b"{")
        self.assertEqual(response.status_code, 400, response.text[:400])
        self.assertEqual(response.json()["error"], "JSON object required")
        self.assertFalse(self.log.exists())

    def test_unset_log_does_not_claim_restart_verification(self):
        os.environ.pop(runloop.RECEIPT_LOG_ENV, None)
        response = self.client.post(RUNSTEP, headers=self._admitted(), json={
            "purpose": "research",
            "mode": "research",
            "prompt": runloop.FIXED_SYNTHETIC_QUERY,
            "sandbox": False,
            "state_changing": False,
        })
        self.assertEqual(response.status_code, 200, response.text[:500])
        receipt = response.json()["restart_receipt"]
        self.assertEqual(receipt["evidence_class"], "SIMULATED")
        self.assertFalse(receipt["persisted"])
        self.assertFalse(receipt["restart_verifiable"])
        self.assertFalse(self.log.exists())

    def test_fixed_query_receipt_checks_in_a_new_process(self):
        os.environ[runloop.RECEIPT_LOG_ENV] = str(self.log)
        response = self.client.post(RUNSTEP, headers=self._admitted(), json={
            "purpose": "research",
            "mode": "research",
            "prompt": runloop.FIXED_SYNTHETIC_QUERY,
            "sandbox": False,
            "state_changing": False,
        })
        self.assertEqual(response.status_code, 200, response.text[:500])
        receipt = response.json()["restart_receipt"]
        self.assertEqual(receipt["evidence_class"], "SIMULATED")
        self.assertEqual(receipt["signer"], "SIMULATED")
        self.assertTrue(receipt["persisted"])
        self.assertTrue(receipt["restart_verifiable"])
        raw = self.log.read_bytes()
        self.assertNotIn(TENANT.encode("utf-8"), raw)
        self.assertNotIn(OPERATOR.encode("utf-8"), raw)
        script = Path(self.tmp.name) / "check_receipt_log.py"
        script.write_text(_VERIFIER, encoding="utf-8")
        child_env = os.environ.copy()
        child_env.pop("SZL_SECOND_BRAIN_RAG", None)
        for key in (opauth.OPERATOR_KEY_ENV, opauth.SECOND_APPROVER_KEY_ENV,
                    "A11OY_CODE_TENANT", runloop.RECEIPT_LOG_ENV):
            child_env.pop(key, None)
        proc = subprocess.run(
            [sys.executable, str(script), str(ROOT), str(self.log)],
            capture_output=True, text=True, env=child_env, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        verdict = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertTrue(verdict["ok"])
        self.assertEqual(verdict["status"], "CHECKED")
        checked = verdict["receipts"][0]
        self.assertEqual(checked["evidence_class"], "SIMULATED")
        self.assertEqual(checked["signer"], "SIMULATED")
        self.assertTrue(checked["chain_intact"])
        self.assertFalse(checked["signature_valid"])
        self.assertEqual(checked["purpose"], "research")
        self.assertEqual(
            checked["query_sha256"],
            hashlib.sha256(runloop.FIXED_SYNTHETIC_QUERY.encode("utf-8")).hexdigest(),
        )

    def test_frontend_posts_the_fixed_query_through_runstep(self):
        html = (ROOT / "web" / "code.html").read_text(encoding="utf-8")
        self.assertIn(runloop.FIXED_SYNTHETIC_QUERY, html)
        self.assertIn('headers["X-A11oy-Tenant"]', html)
        self.assertIn('id="purpose"', html)
        self.assertIn('id="tenant"', html)
        self.assertIn('autocomplete="off"', html)
        self.assertIn('jpost("/runstep"', html)
        self.assertIn("prompt: FIXED_SYNTHETIC_QUERY", html)
        self.assertIn('purpose: "research"', html)
        self.assertIn('mode: "research"', html)
        self.assertIn("sandbox: false", html)
        self.assertIn("state_changing: false", html)
        self.assertNotIn(TENANT, html)


if __name__ == "__main__":
    unittest.main()
