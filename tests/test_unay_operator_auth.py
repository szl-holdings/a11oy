#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Real route authorization with synthetic stores; no model, database or network."""

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.applications import Starlette

import szl_operator_auth as opauth

ROOT = Path(__file__).resolve().parents[1]
OPERATOR = "unay-fixture-operator-not-real"
TENANT = "observer-fixture-tenant-not-real"
HEADERS = {"authorization": f"Bearer {OPERATOR}"}
WRITE_SUFFIXES = ("unay/remember", "khipu/lmdb/append", "khipu/replicate")


class UnayOperatorAuthorization(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="a11oy-unay-auth-")
        self.addCleanup(self.temporary.cleanup)
        self.store = MagicMock(backend="fixture-memory")
        self.store.remember.return_value = {"digest": "fixture-memory-receipt"}
        self.store.stats.return_value = {"entries": 0}
        self.store.verify_chain.return_value = {"ok": True}
        self.store.recall.return_value = []
        self.primary, self.replica = MagicMock(), MagicMock()
        for store in (self.primary, self.replica):
            store.stats.return_value = {"entries": 0}
            store.verify.return_value = {"ok": True}
            store.tail.return_value = []
            store.append.return_value = {"digest": "fixture-lmdb-receipt"}
            store.append_replicated.return_value = {"receipt": {}, "duplicate": False}
            store.get_by_receipt.return_value = None
        self.verify = MagicMock(return_value=True)
        replicator = MagicMock(enabled=False)
        replicator.status.return_value = {"enabled": False}
        self.dependencies = {
            "szl_unay": types.SimpleNamespace(__version__="fixture", UnayStore=MagicMock(return_value=self.store)),
            "szl_khipu_lmdb": types.SimpleNamespace(KhipuLMDB=MagicMock(side_effect=[self.primary, self.replica])),
            "szl_khipu_replicate": types.SimpleNamespace(
                Replicator=MagicMock(return_value=replicator), verify_inbound=self.verify),
            "lmdb": types.SimpleNamespace(version=lambda: (0, 0, 0)),
        }
        environment = patch.dict(os.environ, {opauth.OPERATOR_KEY_ENV: OPERATOR, "GDW_DURABLE_STORAGE": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def _app(self, namespace):
        # Only persistence boundaries are synthetic. The route module and its
        # configured credential resolver are the actual implementation.
        spec = importlib.util.spec_from_file_location("_unay_auth_route_fixture", ROOT / "szl_unay_routes.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {**self.dependencies, spec.name: module}):
            spec.loader.exec_module(module)
            with patch.object(module, "_pick_data_dir", return_value=self.temporary.name), \
                    patch.object(module, "_restore_snapshot", return_value=False):
                app = FastAPI()
                module.register(app, ns=namespace)
        return app

    def _assert_no_writes(self):
        self.store.remember.assert_not_called()
        self.primary.append.assert_not_called()
        self.replica.append.assert_not_called()
        self.replica.append_replicated.assert_not_called()
        self.verify.assert_not_called()

    def test_unauthorized_requests_never_parse_body_or_reach_stores(self):
        app = self._app("a11oy")
        spoof = {"operator": True, "two_person_attested": True,
                 "authorization": f"Bearer {OPERATOR}", "text": "untrusted", "receipts": []}
        for suffix in WRITE_SUFFIXES:
            endpoint = next(route.endpoint for route in app.routes if route.path.endswith("/" + suffix))
            for headers in ({}, {"authorization": "Bearer wrong"}, {"authorization": "Basic " + OPERATOR}):
                with self.subTest(path=suffix, headers=tuple(headers)):
                    request = types.SimpleNamespace(headers=headers, json=AsyncMock(return_value=spoof))
                    response = asyncio.run(endpoint(request))
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(json.loads(response.body)["status"], "BLOCKED")
                    request.json.assert_not_awaited()
        self._assert_no_writes()

    def test_missing_configuration_denies_even_presented_operator(self):
        app = self._app("a11oy")
        with patch.dict(os.environ, {opauth.OPERATOR_KEY_ENV: ""}):
            for suffix in WRITE_SUFFIXES:
                response = TestClient(app).post("/api/a11oy/v2/" + suffix, headers=HEADERS, content=b"{")
                self.assertEqual(response.status_code, 401)
                self.assertFalse(response.json()["credential_configured"])
        self._assert_no_writes()

    def test_resolver_errors_deny_before_body_or_effects(self):
        app = self._app("a11oy")
        with patch.object(opauth, "principal", side_effect=RuntimeError("fixture resolver failure")):
            for suffix in WRITE_SUFFIXES:
                endpoint = next(route.endpoint for route in app.routes if route.path.endswith("/" + suffix))
                request = types.SimpleNamespace(headers=HEADERS, json=AsyncMock())
                response = asyncio.run(endpoint(request))
                self.assertEqual(response.status_code, 401)
                request.json.assert_not_awaited()
        self._assert_no_writes()

    def test_standalone_namespace_refuses_anonymous_without_global_middleware(self):
        app = self._app("fixture-peer")
        self.assertEqual(app.user_middleware, [])
        with TestClient(app) as client:
            for suffix in WRITE_SUFFIXES:
                response = client.post("/api/fixture-peer/v2/" + suffix, content=b"{")
                self.assertEqual(response.status_code, 401)
        self._assert_no_writes()

    def test_valid_operator_retains_existing_write_behavior(self):
        app = self._app("fixture-peer")
        with TestClient(app) as client:
            response = client.post("/api/fixture-peer/v2/unay/remember", headers=HEADERS,
                                   json={"text": "fixture", "meta": {"kind": "test"}, "vector": [1.0]})
            self.assertEqual(response.status_code, 200)
            self.store.remember.assert_called_once_with("fixture", meta={"kind": "test"}, vector=[1.0])
            response = client.post("/api/fixture-peer/v2/khipu/lmdb/append", headers=HEADERS,
                                   json={"action": "fixture", "payload": {"value": 1}})
            self.assertEqual(response.status_code, 200)
            self.primary.append.assert_called_once_with("fixture", payload={"value": 1})
            receipt = {"digest": "fixture-origin"}
            response = client.post("/api/fixture-peer/v2/khipu/replicate", headers=HEADERS,
                                   json={"receipts": [receipt]})
            self.assertEqual(response.status_code, 200)
            self.verify.assert_called_once_with(receipt)
            self.replica.append_replicated.assert_called_once_with(receipt)
            self.replica.append.assert_not_called()
            self.replica.get_by_receipt.assert_not_called()

    def test_public_reads_remain_available_without_writes(self):
        app = self._app("a11oy")
        with TestClient(app) as client:
            for suffix in ("unay/healthz", "unay/stats", "unay/verify", "unay/recall?q=fixture",
                           "khipu/lmdb/stats", "khipu/lmdb/verify", "khipu/lmdb/tail",
                           "khipu/replicate/status"):
                response = client.get("/api/a11oy/v2/" + suffix)
                self.assertEqual(response.status_code, 200, suffix)
            response = client.post("/api/a11oy/v2/unay/recall", json={"q": "fixture"})
            self.assertEqual(response.status_code, 200)
        self._assert_no_writes()

    def test_application_gate_covers_all_three_writes_but_not_reads(self):
        for suffix in WRITE_SUFFIXES:
            path = "/api/a11oy/v2/" + suffix
            self.assertIsNotNone(opauth.protected_action("POST", path))
            self.assertIsNone(opauth.protected_action("GET", path))
        self.assertIsNone(opauth.protected_action("POST", "/api/a11oy/v2/unay/recall"))


class ObserverOwnerAuthorization(unittest.TestCase):
    def setUp(self):
        # The unused Series-A storage owner imports POSIX fcntl. Keep this
        # authorization-only fixture portable without replacing either real
        # credential resolver; the full observer suite exercises real storage.
        spec = importlib.util.spec_from_file_location("_observer_auth_route_fixture", ROOT / "observer_runtime.py")
        observer = importlib.util.module_from_spec(spec)
        self.service_owner = types.SimpleNamespace(Service=MagicMock(), Store=MagicMock(), _git_revision=MagicMock())
        with patch.dict(sys.modules, {spec.name: observer, "routers.series_a_control_plane": self.service_owner}):
            spec.loader.exec_module(observer)
        self.observer = observer
        # Real _caller and HTTP handlers, no Service constructor or storage.
        self.subject = object.__new__(observer.Observer)
        self.subject.challenge = MagicMock()
        self.subject.run = AsyncMock()
        self.subject.cancel = MagicMock()
        self.app = Starlette()
        observer.register(self.app, self.subject)
        environment = patch.dict(os.environ, {opauth.OPERATOR_KEY_ENV: OPERATOR, "A11OY_CODE_TENANT": TENANT})
        environment.start()
        self.addCleanup(environment.stop)

    def _assert_denied_before_body(self, headers, expected_error):
        for route in self.app.routes:
            if "POST" not in route.methods:
                continue
            request = types.SimpleNamespace(headers=headers,
                stream=MagicMock(side_effect=AssertionError("unauthorized body must not be read")),
                path_params={"nonce": "0" * 64})
            response = asyncio.run(route.endpoint(request))
            self.assertIn(response.status_code, (403, 409))
            self.assertEqual(json.loads(response.body), {"status": "BLOCKED", "error": expected_error})
            request.stream.assert_not_called()
        self.subject.challenge.assert_not_called()
        self.subject.run.assert_not_awaited()
        self.subject.cancel.assert_not_called()
        self.service_owner.Service.assert_not_called()
        self.service_owner.Store.assert_not_called()
        self.service_owner._git_revision.assert_not_called()

    def test_absent_or_wrong_operator_never_reaches_effects(self):
        for headers in ({}, {"authorization": "Bearer wrong", "x-a11oy-tenant": TENANT}):
            self._assert_denied_before_body(headers, "OPERATOR_REQUIRED")

    def test_missing_configured_operator_denies_presented_secret(self):
        with patch.dict(os.environ, {opauth.OPERATOR_KEY_ENV: ""}):
            self._assert_denied_before_body({**HEADERS, "x-a11oy-tenant": TENANT}, "OPERATOR_REQUIRED")

    def test_operator_alone_or_wrong_tenant_is_not_admitted(self):
        self._assert_denied_before_body(HEADERS, "TENANT_REQUIRED")
        self._assert_denied_before_body({**HEADERS, "x-a11oy-tenant": "wrong"}, "TENANT_REQUIRED")

    def test_missing_configured_tenant_is_not_admitted(self):
        with patch.dict(os.environ, {"A11OY_CODE_TENANT": ""}):
            self._assert_denied_before_body({**HEADERS, "x-a11oy-tenant": TENANT}, "TENANT_REQUIRED")

    def test_resolver_exception_never_parses_body_or_dispatches(self):
        with patch.object(self.observer, "principal_from_headers", side_effect=RuntimeError("fixture failure")):
            self._assert_denied_before_body({**HEADERS, "x-a11oy-tenant": TENANT}, "OBSERVATION_UNAVAILABLE")
