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


if __name__ == "__main__":
    unittest.main()
