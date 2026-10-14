#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline contract for the shared evaluation middleware boundary."""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import unittest
from pathlib import Path
from unittest.mock import patch

from szl_operator_auth import OPERATOR_KEY_ENV, OperatorGateMiddleware, protected_action

EVAL_PATH = "/api/a11oy/v1/eval/run"


class EvalOperatorGateTests(unittest.TestCase):
    def invoke(self, *, method="POST", path=EVAL_PATH, authorization=None):
        downstream = []
        messages = []

        async def app(scope, receive, send):
            downstream.append(scope["path"])

        async def receive():
            self.fail("the refusal gate must never read the request body")

        async def send(message):
            messages.append(message)

        headers = []
        if authorization is not None:
            headers.append((b"authorization", authorization.encode("ascii")))
        scope = {"type": "http", "method": method, "path": path, "headers": headers}
        asyncio.run(OperatorGateMiddleware(app)(scope, receive, send))
        return downstream, messages

    def assert_refused(self, **kwargs):
        downstream, messages = self.invoke(**kwargs)
        self.assertEqual(downstream, [])
        self.assertEqual(messages[0]["status"], 401)
        self.assertEqual(dict(messages[0]["headers"])[b"cache-control"], b"no-store")
        self.assertEqual(json.loads(messages[1]["body"])["status"], "BLOCKED")

    def test_anonymous_evaluation_stops_before_body_or_handler(self):
        with patch.dict(os.environ, {OPERATOR_KEY_ENV: secrets.token_urlsafe(32)}):
            self.assert_refused()

    def test_incorrect_operator_stops_before_body_or_handler(self):
        with patch.dict(os.environ, {OPERATOR_KEY_ENV: secrets.token_urlsafe(32)}):
            self.assert_refused(authorization="Bearer " + secrets.token_urlsafe(32))

    def test_unconfigured_operator_denies_every_caller(self):
        with patch.dict(os.environ, {OPERATOR_KEY_ENV: ""}):
            self.assert_refused(authorization="Bearer " + secrets.token_urlsafe(32))

    def test_matching_operator_reaches_only_the_stub_handler(self):
        token = secrets.token_urlsafe(32)
        with patch.dict(os.environ, {OPERATOR_KEY_ENV: token}):
            downstream, messages = self.invoke(authorization="Bearer " + token)
        self.assertEqual(downstream, [EVAL_PATH])
        self.assertEqual(messages, [])

    def test_read_methods_remain_passive_and_ungated(self):
        for method in ("GET", "HEAD", "OPTIONS"):
            with self.subTest(method=method):
                self.assertIsNone(protected_action(method, EVAL_PATH))
                downstream, messages = self.invoke(method=method)
                self.assertEqual(downstream, [EVAL_PATH])
                self.assertEqual(messages, [])

    def test_normalized_evaluation_paths_are_protected(self):
        for path in (EVAL_PATH, EVAL_PATH + "/", "/api//a11oy/v1/eval/run"):
            with self.subTest(path=path):
                self.assertEqual(
                    protected_action("POST", path),
                    ("Evaluation and receipt publication", "tool"),
                )
                self.assert_refused(path=path)


class EvalClientContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.console = (root / "pages/console.html").read_text(encoding="utf-8")
        cls.arena = (root / "static/3d/surfaces/evalarena.js").read_text(encoding="utf-8")

    def test_console_uses_explicit_bounded_one_shot_operator_flow(self):
        source = self.console
        self.assertIn('id="fe-token"', source)
        self.assertIn("operator credential (one-shot)", source)
        self.assertIn("FLYEVAL_RUN_PATH='/api/a11oy/v1/eval/run'", source)
        self.assertIn("authorization':'Bearer '+token", source)
        self.assertIn("redirect:'error'", source)
        self.assertIn("credentials:'same-origin'", source)
        self.assertIn("cache:'no-store'", source)
        self.assertIn("AbortController", source)
        self.assertIn("payload.length>16384", source)
        self.assertIn("automatic retry is disabled", source)
        self.assertIn("tokenNode.value=''", source)
        self.assertNotIn("localStorage.setItem('fe-token'", source)
        self.assertNotIn("sessionStorage.setItem('fe-token'", source)

    def test_arena_never_posts_on_mount_or_poll_and_runs_once_on_click(self):
        source = self.arena
        self.assertNotIn("ctx.live.poll(EP_RUN", source)
        self.assertIn('id="ea-token"', source)
        self.assertIn('id="ea-run-once"', source)
        self.assertIn('run.addEventListener("click",_runEvalOnce)', source)
        self.assertIn('redirect:"error"', source)
        self.assertIn('credentials:"same-origin"', source)
        self.assertIn('cache:"no-store"', source)
        self.assertIn('"authorization":"Bearer "+token', source)
        self.assertIn("body.length>16384", source)
        self.assertIn("outcome UNKNOWN and automatic retry disabled", source)
        self.assertIn('tokenNode.value=""', source)
        self.assertNotIn("localStorage.setItem", source)
        self.assertNotIn("sessionStorage.setItem", source)
        self.assertNotIn("value=\"'+S.modelId+'\"", source)
        self.assertIn('modelInput.value=String(S.modelId||"").slice(0,240)', source)
        self.assertIn('label.textContent=String(S.label||"MODELED")', source)



if __name__ == "__main__":
    unittest.main()
