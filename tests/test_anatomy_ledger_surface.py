#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the real registrar ahead of an existing application catch-all."""

import importlib.util
from pathlib import Path
import unittest

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "anatomy_registrar_test", ROOT / "a11oy_anatomy_ledger.py"
)
registrar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registrar)


class AnatomySurfaceTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()

        @self.app.get("/{path:path}")
        def fallback(path):
            return HTMLResponse("existing SPA")

        registrar.register(self.app)
        self.client = TestClient(self.app)

    def test_registrar_wins_over_spa(self):
        response = self.client.get(registrar.PREFIX + "/status")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.headers["content-type"])
        self.assertEqual(self.client.get("/unrelated").text, "existing SPA")

    def test_idempotent(self):
        count = len(self.app.routes)
        registrar.register(self.app)
        self.assertEqual(len(self.app.routes), count)

    def test_dashboard_assets(self):
        page = self.client.get("/anatomy-ledger/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Anatomy", page.text)
        self.assertIn("Content-Security-Policy", page.headers)
        self.assertEqual(self.client.get("/anatomy-ledger/server.py").status_code, 404)

    def test_read_never_changes_ledger(self):
        ledger = ROOT / "anatomy-ledger/public/data/ledger.json"
        before = ledger.read_bytes()
        self.assertEqual(self.client.get(registrar.PREFIX + "/ledger").status_code, 200)
        self.assertEqual(self.client.get(registrar.PREFIX + "/prove").status_code, 200)
        self.assertEqual(before, ledger.read_bytes())

    def test_bind_cannot_authorize_execution(self):
        response = self.client.post(
            registrar.PREFIX + "/bind", json={"verification": {"verified": True}}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["executable"], False)

    def test_invalid_request(self):
        url = registrar.PREFIX + "/evaluate"
        for data in ("[]", "null", '{"x":NaN}', "{"):
            with self.subTest(data=data):
                self.assertEqual(
                    self.client.post(
                        url, content=data, headers={"content-type": "application/json"}
                    ).status_code,
                    400,
                )
        self.assertEqual(self.client.post(url, content="{}").status_code, 415)
        self.assertEqual(
            self.client.post(
                url, json={}, headers={"Origin": "https://foreign.invalid"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                url,
                content=b" " * (registrar.MAX_BODY + 1),
                headers={"content-type": "application/json"},
            ).status_code,
            413,
        )

    def test_decision_lab_and_replay_precede_spa(self):
        service = registrar.load_service()
        command = service.BIND.intent_from_command(
            principal_id="agent:sample",
            action="DeployArtifact",
            resource_id="deploy:sample",
            purpose="test",
            intended_effect="deploy",
            risk_score=10,
            human_approval=True,
            mfa=True,
            evidence_digest=service.DIGEST,
        )
        response = self.client.post(
            registrar.PREFIX + "/analyze",
            json={
                "command": command,
                "statement": service.VALID_SLSA,
                "verification": {"verified": True},
            },
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["schema"], "szl.anatomy.decision-lab.v1")
        self.assertFalse(result["executable"])
        replayed = self.client.post(
            registrar.PREFIX + "/replay", json=result["replayCapsule"]
        )
        self.assertEqual(replayed.status_code, 200)
        self.assertTrue(replayed.json()["valid"])
        self.assertFalse(replayed.json()["executable"])
        self.assertIn(
            "analyze",
            self.client.get(registrar.PREFIX + "/status").json()["capabilities"],
        )

    def test_decision_lab_rejects_invalid_and_cross_origin_inputs(self):
        self.assertEqual(
            self.client.post(
                registrar.PREFIX + "/analyze", json={"command": []}
            ).status_code,
            422,
        )
        for operation in ("analyze", "replay"):
            self.assertEqual(
                self.client.post(
                    registrar.PREFIX + "/" + operation,
                    json={},
                    headers={"Origin": "https://foreign.invalid"},
                ).status_code,
                403,
            )

    def test_serving_files_in_deployment(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY a11oy_anatomy_ledger.py", dockerfile)
        self.assertIn("COPY anatomy-ledger/", dockerfile)
        self.assertIn(
            "_anatomy_ledger_module.register(app)",
            (ROOT / "serve.py").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
