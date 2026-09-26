# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Golden verdicts for the deny-by-default operator gate on a11oy.code routes.

Anonymous callers must never execute code, run tools, write state, or read chat
history; a request body can never assert two-person attestation.
"""
import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="a11oy-opauth-")
os.environ.setdefault("A11OY_CODE_DB", str(Path(_TMP) / "code.db"))
os.environ.setdefault("A11OY_CODE_SANDBOX", str(Path(_TMP) / "sandbox"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import a11oy_code_orchestrator as orchestrator  # noqa: E402
import szl_operator_auth as opauth  # noqa: E402

OPERATOR = "op-test-secret-not-real"
APPROVER = "approver-test-secret-not-real"


def _client() -> TestClient:
    app = FastAPI()
    orchestrator.attach(app)
    return TestClient(app)


class PrincipalResolution(unittest.TestCase):
    def test_no_secrets_configured_nobody_is_operator(self):
        with patch.dict(os.environ, {opauth.OPERATOR_KEY_ENV: "", opauth.SECOND_APPROVER_KEY_ENV: ""}):
            who = opauth.principal_from_headers({"Authorization": "Bearer "})
        self.assertEqual(who, {"operator": False, "two_person_attested": False})

    def test_same_secret_twice_is_not_two_people(self):
        env = {opauth.OPERATOR_KEY_ENV: OPERATOR, opauth.SECOND_APPROVER_KEY_ENV: OPERATOR}
        with patch.dict(os.environ, env):
            who = opauth.principal_from_headers(
                {"Authorization": f"Bearer {OPERATOR}", opauth.SECOND_APPROVER_HEADER: OPERATOR})
        self.assertTrue(who["operator"])
        self.assertFalse(who["two_person_attested"])

    def test_operator_plus_distinct_approver_attests(self):
        env = {opauth.OPERATOR_KEY_ENV: OPERATOR, opauth.SECOND_APPROVER_KEY_ENV: APPROVER}
        with patch.dict(os.environ, env):
            who = opauth.principal_from_headers(
                {"authorization": f"bearer {OPERATOR}", "X-A11oy-Second-Approver": APPROVER})
        self.assertEqual(who, {"operator": True, "two_person_attested": True})


class AnonymousIsDenied(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {opauth.OPERATOR_KEY_ENV: OPERATOR,
                                           opauth.SECOND_APPROVER_KEY_ENV: APPROVER})
        self.env.start()
        self.client = _client()

    def tearDown(self):
        self.env.stop()

    def test_run_denied_even_when_body_claims_attestation(self):
        with patch.object(orchestrator, "run_code") as ran:
            r = self.client.post("/api/a11oy/code/run",
                                 json={"language": "python", "code": "print(1)",
                                       "two_person_attested": True})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["status"], "BLOCKED")
        ran.assert_not_called()

    def test_run_denied_for_operator_without_second_approver(self):
        with patch.object(orchestrator, "run_code") as ran:
            r = self.client.post("/api/a11oy/code/run",
                                 headers={"Authorization": f"Bearer {OPERATOR}"},
                                 json={"language": "python", "code": "print(1)"})
        self.assertEqual(r.status_code, 401)
        ran.assert_not_called()

    def test_run_allowed_with_both_credentials(self):
        fake = {"stdout": "1\n", "stderr": "", "code": 0}
        with patch.object(orchestrator, "run_code", return_value=dict(fake)) as ran:
            r = self.client.post("/api/a11oy/code/run",
                                 headers={"Authorization": f"Bearer {OPERATOR}",
                                          opauth.SECOND_APPROVER_HEADER: APPROVER},
                                 json={"language": "python", "code": "print(1)"})
        self.assertEqual(r.status_code, 200, r.text)
        ran.assert_called_once()

    def test_kernel_exec_denied_anonymous(self):
        r = self.client.post("/api/a11oy/code/kernel/run1/exec", json={"code": "print(1)"})
        self.assertEqual(r.status_code, 401)

    def test_kernel_exec_rejects_bad_run_id(self):
        r = self.client.post("/api/a11oy/code/kernel/..%2Fx/exec",
                             headers={"Authorization": f"Bearer {OPERATOR}",
                                      opauth.SECOND_APPROVER_HEADER: APPROVER},
                             json={"code": "print(1)"})
        self.assertIn(r.status_code, (400, 404))

    def test_state_and_history_routes_denied_anonymous(self):
        for method, path in [("post", "/api/a11oy/code/rag/index"),
                             ("post", "/api/a11oy/code/rag/refresh"),
                             ("post", "/api/a11oy/code/rag/seed"),
                             ("get", "/api/a11oy/code/conversations?user_id=founder"),
                             ("get", "/api/a11oy/code/conversations/x"),
                             ("get", "/api/a11oy/code/conversations/x/export"),
                             ("get", "/api/a11oy/code/profile/founder"),
                             ("post", "/api/a11oy/code/profile/founder")]:
            with self.subTest(path=path):
                r = getattr(self.client, method)(path, json={}) if method == "post" \
                    else self.client.get(path)
                self.assertEqual(r.status_code, 401, f"{method.upper()} {path} -> {r.status_code}")

    def test_issue_key_requires_operator(self):
        r = self.client.post("/api/a11oy/code/v1/keys", json={"owner": "x"})
        self.assertEqual(r.status_code, 403)


class ToolsNeedAuthorization(unittest.TestCase):
    def test_execute_tool_denies_unauthorized_before_dispatch(self):
        with patch.object(orchestrator, "_dispatch_tool") as dispatch:
            out = asyncio.run(orchestrator.execute_tool("fs_read", {"path": "x"}, None,
                                                        two_person_attested=True))
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "BLOCKED")
        dispatch.assert_not_called()

    def test_puriq_without_stated_authorization_denies(self):
        decision = orchestrator.puriq_decide("fs_read", {"risk": "low"})
        self.assertFalse(decision["allow"])

    def test_principal_runner_cannot_widen_attestation(self):
        seen = {}

        async def fake_execute(name, args, client, two_person_attested=False, authorized=False):
            seen.update(two_person_attested=two_person_attested, authorized=authorized)
            return {"ok": False}

        runner = orchestrator._principal_tool_runner(None, {"operator": False,
                                                            "two_person_attested": False})
        with patch.object(orchestrator, "execute_tool", fake_execute):
            asyncio.run(runner("shell_exec", {}, two_person_attested=True, authorized=True))
        self.assertEqual(seen, {"two_person_attested": False, "authorized": False})


if __name__ == "__main__":
    unittest.main()
