#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Real pinned public projection readers; no private source or write authority."""

import hashlib
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import a11oy_steward_surface as surface

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "a" * 40


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _timestamp(value):
    return value.isoformat().replace("+00:00", "Z")


def _projection(age_seconds=0):
    now = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return {
        "schema_version": "szl.frontier-steward.public/v1",
        "state": "CURRENT",
        "scope": "PUBLIC_READ_ONLY",
        "source": {"repository": surface.REPOSITORY, "revision": SOURCE_REVISION},
        "projected_at": _timestamp(now),
        "freshness": {"max_age_seconds": 7200, "valid_until": _timestamp(now + timedelta(seconds=7200))},
        "plan": {"id": "steward-plan-" + "b" * 24, "digest": "sha256:" + "c" * 64,
                 "artifact_sha256": "d" * 64, "receipt_id": "receipt-" + "e" * 32,
                 "receipt_hash": "f" * 64, "status": "PROPOSED"},
        "audit": {"id": "audit-" + "1" * 32, "observed_at": _timestamp(now),
                  "receipt_hash": "2" * 64,
                  "sources": [{"source": "github", "status": "MEASURED", "scope": "PUBLIC_ONLY"},
                              {"source": "huggingface", "status": "MEASURED", "scope": "PUBLIC_ONLY"},
                              {"source": "domains", "status": "MEASURED", "scope": "PUBLIC_NETWORK"}]},
        "integrity": {"kind": "UNSIGNED_HASH_CHAIN", "chain_valid": True,
                      "latest_hash": "3" * 64, "signature_status": "UNSIGNED",
                      "independent_witness": False},
        "provider": {"adapter": "deterministic", "runtime": "NO_MODEL_CALL", "model_invoked": False},
        "production_ready": False,
        "mutation_policy": "PROPOSAL_ONLY",
        "proposals": [{"title": "Public evidence coverage", "objective": "Measure coverage without executing changes.",
                       "hypothesis": "Typed coverage identifies missing evidence.",
                       "tests": ["Compare missing obligations with a frozen public snapshot."],
                       "success_metrics": ["Report the observed coverage and baseline."],
                       "stop_conditions": ["Stop when required evidence is missing."]}],
    }


class StewardSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="a11oy-steward-test-")
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name).absolute()
        self.module = self.base / "steward_public.py"
        self.lock_path = self.base / "steward-source-lock.json"
        self.projection_path = self.base / "steward-public.json"
        self.module.write_bytes((ROOT / "steward_public.py").read_bytes())
        self._write_projection(_projection())
        for name, value in (("BASE", self.base), ("MODULE_PATH", self.module),
                            ("LOCK_PATH", self.lock_path), ("PROJECTION_PATH", self.projection_path)):
            patched = patch.object(surface, name, value)
            patched.start()
            self.addCleanup(patched.stop)
        self.app = FastAPI()
        self.proxy_calls = []

        @self.app.api_route("/api/a11oy/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
        def proxy_fallback(path):
            self.proxy_calls.append(path)
            return HTMLResponse("existing proxy")

        @self.app.get("/{path:path}")
        def spa_fallback(path):
            return HTMLResponse("existing SPA")

        @self.app.websocket("/{path:path}")
        async def websocket_fallback(websocket: WebSocket, path):
            self.proxy_calls.append("websocket:" + path)
            await websocket.accept()
            await websocket.close()

        surface.register(self.app)
        self.client = TestClient(self.app)

    def _write_projection(self, projection):
        self.projection_path.write_bytes(_bytes(projection))
        self._write_lock()

    def _write_lock(self, **changes):
        lock = {"schema_version": surface.LOCK_SCHEMA, "repository": surface.REPOSITORY,
                "revision": SOURCE_REVISION,
                "module_sha256": hashlib.sha256(self.module.read_bytes()).hexdigest(),
                "projection_sha256": hashlib.sha256(self.projection_path.read_bytes()).hexdigest()}
        lock.update(changes)
        self.lock_path.write_bytes(_bytes(lock))

    def _fresh_client(self):
        app = FastAPI()
        surface.register(app)
        return TestClient(app)

    def _assert_closed(self, client=None, state=None):
        client = client or self.client
        for operation in ("status", "proposals"):
            response = client.get(surface.PREFIX + "/" + operation)
            self.assertEqual(response.status_code, 503, response.text)
            self.assertEqual(response.headers["cache-control"], "no-store")
            body = response.json()
            self.assertFalse(body["production_ready"])
            self.assertFalse(body["snapshot_current"])
            self.assertFalse(body["model_invoked"])
            if state:
                self.assertEqual(body["state"], state)
            if operation == "proposals":
                self.assertEqual(body["proposals"], [])

    def test_current_public_projection(self):
        status = self.client.get(surface.PREFIX + "/status")
        self.assertEqual(status.status_code, 200, status.text)
        self.assertIn("application/json", status.headers["content-type"])
        self.assertEqual(status.headers["x-content-type-options"], "nosniff")
        body = status.json()
        self.assertEqual(body["state"], "CURRENT")
        self.assertTrue(body["snapshot_current"])
        self.assertFalse(body["production_ready"])
        self.assertEqual(body["source"]["revision"], SOURCE_REVISION)
        self.assertNotIn("proposals", body)
        self.assertFalse(body["snapshot"]["integrity"]["independent_witness"])
        proposals = self.client.get(surface.PREFIX + "/proposals").json()
        self.assertEqual(len(proposals["proposals"]), 1)
        self.assertEqual(proposals["effectors"], 0)
        self.assertEqual(proposals["storage_writes"], 0)
        self.assertEqual(proposals["provider_calls"], 0)

    def test_routes_precede_proxy_and_spa_and_register_idempotent(self):
        count = len(self.app.routes)
        surface.register(self.app)
        self.assertEqual(len(self.app.routes), count)
        paths = [getattr(route, "path", "") for route in self.app.routes]
        self.assertLess(paths.index(surface.PREFIX + "/status"), paths.index("/api/a11oy/{path:path}"))
        self.assertLess(paths.index(surface.PREFIX + "/proposals"), paths.index("/{path:path}"))
        self.assertEqual(self.client.get("/unrelated").text, "existing SPA")
        self.assertEqual(self.client.get("/api/a11oy/unrelated").text, "existing proxy")

    def test_non_get_methods_rejected_before_proxy(self):
        for operation in ("status", "proposals"):
            for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
                response = self.client.request(method, surface.PREFIX + "/" + operation, json={"source": "private"})
                self.assertEqual(response.status_code, 405, (method, response.text))
                self.assertEqual(response.headers["allow"], "GET")
        self.assertEqual(self.proxy_calls, [])

    def test_queries_and_environment_cannot_select_sources(self):
        expected = self.client.get(surface.PREFIX + "/proposals").json()
        with patch.dict(os.environ, {"A11OY_STEWARD_SOURCE": "private.db", "SZL_STEWARD_PLAN_JSON": "private.json",
                                    "SZL_STEWARD_DB": "private.db", "HF_TOKEN": "test-only-not-used"}):
            response = self.client.get(surface.PREFIX + "/proposals?path=private.db&source=https://example.invalid&refresh=1")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), expected)

    def test_gets_do_not_write_network_or_initialize_code_again(self):
        before = {path.name: path.read_bytes() for path in self.base.iterdir()}
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("HTTP forbidden")), \
                patch.object(surface, "_initialize", side_effect=AssertionError("no initialization on GET")):
            for _ in range(5):
                self.assertEqual(self.client.get(surface.PREFIX + "/status").status_code, 200)
                self.assertEqual(self.client.get(surface.PREFIX + "/proposals").status_code, 200)
        after = {path.name: path.read_bytes() for path in self.base.iterdir()}
        self.assertEqual(before, after)
        self.assertFalse((self.base / "__pycache__").exists())

    def test_missing_projection(self):
        self.projection_path.unlink()
        self._assert_closed()

    def test_changed_projection_does_not_publish_unpinned_content(self):
        self.projection_path.write_bytes(b'{"private":"do not publish"}')
        self._assert_closed()
        self.assertNotIn("do not publish", self.client.get(surface.PREFIX + "/status").text)

    def test_stale_projection_returns_no_proposals(self):
        self._write_projection(_projection(age_seconds=7201))
        self._assert_closed(self._fresh_client(), "STALE")

    def test_invalid_projection_even_with_matching_content_pin(self):
        projection = _projection()
        projection["production_ready"] = True
        self._write_projection(projection)
        self._assert_closed(self._fresh_client())

    def test_private_scope_even_with_matching_pin(self):
        projection = _projection()
        projection["scope"] = "AUTHENTICATED_COMPLETE"
        self._write_projection(projection)
        self._assert_closed(self._fresh_client())

    def test_source_revision_mismatch(self):
        self._write_lock(revision="4" * 40)
        self._assert_closed(self._fresh_client())

    def test_module_mutation_does_not_reload_or_execute(self):
        self.module.write_bytes(b'raise RuntimeError("untrusted source executed")')
        self._assert_closed()
        self._assert_closed(self._fresh_client())

    def test_valid_package_lock_changed_after_initialization(self):
        self._write_lock(revision="4" * 40)
        self._assert_closed()

    def test_lock_unknown_duplicate_or_nonfinite_fields_fail(self):
        original = self.lock_path.read_bytes()
        for changed in (
            original[:-1] + b',"path":"private.db"}',
            original[:-1] + b',"revision":"' + SOURCE_REVISION.encode() + b'"}',
            original[:-1] + b',"x":NaN}',
            b'[]', b'{}', b'null',
        ):
            with self.subTest(changed=changed):
                self.lock_path.write_bytes(changed)
                self._assert_closed(self._fresh_client())

    def test_bad_lock_repository_revision_and_hash_formats(self):
        for changes in ({"repository": "untrusted/other"}, {"revision": "main"},
                        {"module_sha256": "5" * 63}, {"projection_sha256": True}):
            with self.subTest(changes=changes):
                self._write_lock(**changes)
                self._assert_closed(self._fresh_client())

    def test_oversized_lock_fails_without_reflecting_content(self):
        self.lock_path.write_bytes(b"private " * surface.MAX_LOCK_BYTES)
        client = self._fresh_client()
        self._assert_closed(client)
        self.assertNotIn("private", client.get(surface.PREFIX + "/status").text)

    def test_module_pin_checked_before_package_initialization(self):
        self.module.write_bytes(b'raise RuntimeError("must not execute")')
        # The preexisting lock intentionally does not match the changed module.
        with patch("builtins.compile", side_effect=AssertionError("no unverified compile")):
            with self.assertRaises(surface.PackageError):
                surface._initialize()

    def test_missing_package_initialization_stays_closed_until_restart(self):
        initial_lock = self.lock_path.read_bytes()
        self.lock_path.unlink()
        client = self._fresh_client()
        self.lock_path.write_bytes(initial_lock)
        self._assert_closed(client, "UNAVAILABLE")

    def test_unverified_bytecode_and_shadow_import_are_not_used(self):
        cache = self.base / "__pycache__"
        cache.mkdir()
        (cache / ("steward_public." + sys.implementation.cache_tag + ".pyc")).write_bytes(b"unverified cache")
        shadow = types.ModuleType("steward_public")
        shadow.load_public_projection = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("shadow import used")
        )
        with patch.dict(sys.modules, {"steward_public": shadow}):
            client = self._fresh_client()
            response = client.get(surface.PREFIX + "/proposals")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            (cache / ("steward_public." + sys.implementation.cache_tag + ".pyc")).read_bytes(),
            b"unverified cache",
        )

    def test_get_route_table_contains_no_mutation_methods(self):
        for route in self.app.routes:
            if getattr(route, "path", "") in {surface.PREFIX + "/status", surface.PREFIX + "/proposals"}:
                self.assertEqual(route.methods, {"GET"})

    def test_missing_module_does_not_remove_json_routes(self):
        self.module.unlink()
        client = self._fresh_client()
        self._assert_closed(client, "UNAVAILABLE")

    def test_reserved_aliases_and_unknown_paths_never_reach_proxy(self):
        for suffix in ("", "/", "/status/", "/proposals/", "/unknown", "/status/execute", "/status%2f"):
            for method, expected in (("GET", 404), ("POST", 405), ("PUT", 405)):
                response = self.client.request(method, surface.PREFIX + suffix)
                self.assertEqual(response.status_code, expected, (method, suffix, response.text))
                self.assertIn("application/json", response.headers["content-type"])
        self.assertEqual(self.proxy_calls, [])
        self.assertEqual(self.client.post(surface.PREFIX + "ly/status").text, "existing proxy")

    def test_reserved_websocket_is_closed_before_downstream(self):
        for suffix in ("/status", "/proposals", "/unknown", "/status%2f"):
            with self.subTest(suffix=suffix):
                with self.assertRaises(WebSocketDisconnect) as closed:
                    with self.client.websocket_connect(surface.PREFIX + suffix):
                        self.fail("reserved WebSocket accepted")
                self.assertEqual(closed.exception.code, 1008)
        self.assertEqual(self.proxy_calls, [])


if __name__ == "__main__":
    unittest.main()
