# SPDX-License-Identifier: Apache-2.0
"""HTTP integration checks for passive ORO evidence observations.

These tests exercise the public route with real ASGI dispatch. Synthetic rows
establish boundary behavior only; they do not establish production availability.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from oro import evidence_api


API_PATH = "/api/a11oy/v1/oro/evidence"
ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def khipu_rows(count):
    rows = []
    for index in range(count):
        rows.append({
            "index": index,
            "space": "a11oy",
            "wire": "F",
            "digest": digest(index),
            "parents": [rows[-1]["digest"]] if rows else [],
            "receipt": {"note": "owner-payload-must-not-leave"},
            "dsse": {"signatures": [{"sig": "owner-signature-must-not-leave"}]},
        })
    return rows


class ExistingDag:
    def __init__(self, rows=None, error=None):
        self.rows = list(rows or [])
        self.error = error
        self.calls = []
        self.read_threads = []

    def recent(self, count):
        raise AssertionError("HTTP inspection must not read unbounded history")

    def evidence_window(self, count):
        self.calls.append(count)
        self.read_threads.append(threading.get_ident())
        if self.error is not None:
            raise self.error
        return self.rows[-count:]

    def append_signed(self, *_args, **_kwargs):
        raise AssertionError("passive evidence must not append")

    def checkpoint(self, *_args, **_kwargs):
        raise AssertionError("passive evidence must not checkpoint")

    def verify(self, *_args, **_kwargs):
        raise AssertionError("passive evidence must not invoke owner verification")


def anatomy_summary():
    return {
        "schema": "szl.anatomy.evidence/v6",
        "evidence_class": "MODELED",
        "mode": "READ_ONLY",
        "content_access": "SUMMARY_ONLY",
        "storage_writes": 0,
        "receipt_minted_on_get": False,
        "model_invoked": False,
        "gradient_training": False,
        "authority": {
            "training": "NONE", "promotion": "NONE",
            "execution": "NONE", "provider_write": "NONE",
        },
        "audit": {
            "chain_ok": True, "receipts_checked": 2,
            "broken_receipts": 0, "proposed_demotions": 0,
        },
        "overlay": {"nodes": 1, "reinforced_edges": 0},
        "computed_at": "2026-11-16T23:00:00+00:00",
        "scope": "Synthetic owner summary for boundary testing.",
    }


def make_app(owner=None):
    app = FastAPI()
    if owner is not None:
        app.state.szl_khipu_dag = owner
    evidence_api.register(app, namespace="a11oy")

    @app.api_route("/{path:path}", methods=[
        "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS",
    ])
    def downstream_catchall(path: str):
        return {"fell_through": True, "path": path}

    return app


def assert_no_authority(testcase, body):
    for key in ("execution_authority", "promotion_authority", "signing_authority"):
        testcase.assertIs(body[key], False)
    testcase.assertIs(body["capabilities"]["execution"]["available"], False)
    testcase.assertTrue(body["capabilities"]["execution"].get("reasons"))
    for node in body["projection"]["nodes"]:
        testcase.assertEqual(node["evidence"]["proof_status"], "UNVERIFIED")
        testcase.assertIs(node["evidence"]["execution_authority"], False)
        testcase.assertIs(node["evidence"]["promotion_authority"], False)


class EvidenceApiTests(unittest.TestCase):
    def setUp(self):
        self.anatomy = patch.object(
            evidence_api, "_read_anatomy_snapshot", return_value=anatomy_summary()
        )
        self.anatomy_reader = self.anatomy.start()
        self.addCleanup(self.anatomy.stop)

    def test_registration_is_idempotent_and_does_not_duplicate_source_reads(self):
        owner = ExistingDag(khipu_rows(1))
        app = make_app(owner)
        before = list(app.routes)
        first = evidence_api.register(app, namespace="a11oy")
        second = evidence_api.register(app, namespace="a11oy")
        self.assertEqual(app.routes, before)
        self.assertIs(first["already_registered"], True)
        self.assertIs(second["already_registered"], True)
        self.anatomy_reader.assert_not_called()
        with TestClient(app) as client:
            response = client.get(API_PATH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(owner.calls, [33])
        self.anatomy_reader.assert_called_once_with()

    def test_recent_only_owner_is_refused_without_unbounded_fallback(self):
        class RecentOnly:
            def recent(self, _count):
                raise AssertionError("unbounded reader was called")
        with TestClient(make_app(RecentOnly())) as client:
            response = client.get(API_PATH)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["sources"]["canonical_khipu"]["reason"],
                         "OWNER_CONTRACT_INVALID")
        self.assertEqual(response.json()["projection"]["nodes"], [])

    def test_other_namespaces_are_refused_before_routes_are_added(self):
        for namespace in ("sentra", "../a11oy", "a11oy/child", ""):
            with self.subTest(namespace=namespace):
                app = FastAPI()
                before = list(app.routes)
                with self.assertRaises(ValueError):
                    evidence_api.register(app, namespace=namespace)
                self.assertEqual(app.routes, before)
        self.anatomy_reader.assert_not_called()

    def test_foreign_routes_cannot_be_misidentified_as_our_registration(self):
        collisions = [
            (API_PATH, "GET"),
            (API_PATH, "POST"),
            (API_PATH + "/{path:path}", "GET"),
            ("/oro/evidence", "GET"),
            ("/oro/evidence/", "GET"),
            ("/oro/evidence/{path:path}", "GET"),
            ("/oro/evidence/assets/app.js", "GET"),
            ("/oro/evidence/assets/styles.css", "GET"),
        ]
        for path, method in collisions:
            with self.subTest(path=path, method=method):
                app = FastAPI()

                def foreign_endpoint():
                    return {"foreign": True}

                app.add_api_route(path, foreign_endpoint, methods=[method])
                before = list(app.routes)
                with self.assertRaisesRegex(RuntimeError, "ORO_EVIDENCE_ROUTE_COLLISION"):
                    evidence_api.register(app, namespace="a11oy")
                self.assertEqual(app.routes, before)
        self.anatomy_reader.assert_not_called()

    def test_registration_is_passive_and_owner_is_resolved_at_request_time(self):
        app = make_app()
        self.anatomy_reader.assert_not_called()
        owner = ExistingDag(khipu_rows(2))
        app.state.szl_khipu_dag = owner
        with TestClient(app) as client:
            first = client.get(API_PATH)
            app.state.szl_khipu_dag = ExistingDag(khipu_rows(3))
            second = client.get(API_PATH)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(owner.calls, [33])
        self.assertEqual(first.json()["sources"]["canonical_khipu"]["count"], 2)
        self.assertEqual(second.json()["sources"]["canonical_khipu"]["count"], 3)
        self.assertEqual(second.json()["status"], "OBSERVED")

    def test_bounded_tail_keeps_chain_boundary_and_excludes_owner_content(self):
        rows = khipu_rows(34)
        owner = ExistingDag(rows)
        with TestClient(make_app(owner)) as client:
            response = client.get(API_PATH)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/json"))
        self.assertIn("no-store", response.headers.get("cache-control", ""))
        body = response.json()
        self.assertEqual(body["schema"], "szl.oro-evidence-observation/v1")
        self.assertEqual(body["freshness"], "NOT_ASSERTED")
        self.assertTrue(body["collected_at"])
        self.assertEqual(owner.calls, [33])
        self.assertEqual(len(body["projection"]["nodes"]), 32)
        state = body["sources"]["canonical_khipu"]
        self.assertEqual(state["count"], 32)
        self.assertIs(state["window_complete"], False)
        self.assertEqual(state["omitted_parent_digests"], [rows[1]["digest"]])
        self.assertEqual(state["signature_verification"], "UNKNOWN")
        self.assertNotIn("owner-payload-must-not-leave", response.text)
        self.assertNotIn("owner-signature-must-not-leave", response.text)
        assert_no_authority(self, body)

    def test_absent_owner_is_unavailable_without_fabricated_zero_observation(self):
        with TestClient(make_app()) as client:
            response = client.get(API_PATH)
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["status"], "UNAVAILABLE")
        self.assertEqual(body["sources"]["canonical_khipu"]["state"], "UNKNOWN")
        self.assertIsNone(body["sources"]["canonical_khipu"]["count"])
        self.assertEqual(body["projection"]["nodes"], [])
        for source in ("second_brain", "hatun"):
            self.assertEqual(body["sources"][source]["state"], "UNKNOWN")
            self.assertIsNone(body["sources"][source]["count"])
        assert_no_authority(self, body)

    def test_observed_empty_owner_is_distinct_from_absent_owner(self):
        with TestClient(make_app(ExistingDag())) as client:
            response = client.get(API_PATH)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "OBSERVED")
        self.assertEqual(body["sources"]["canonical_khipu"]["state"], "UNKNOWN")
        self.assertEqual(body["sources"]["canonical_khipu"]["count"], 0)
        self.assertEqual(body["projection"]["nodes"], [])
        assert_no_authority(self, body)

    def test_owner_read_error_is_sanitized_and_never_successful_empty_data(self):
        owner = ExistingDag(error=RuntimeError("private-path-and-owner-error-marker"))
        with TestClient(make_app(owner)) as client:
            response = client.get(API_PATH)
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["status"], "UNAVAILABLE")
        self.assertEqual(body["sources"]["canonical_khipu"]["state"], "UNAVAILABLE")
        self.assertIsNone(body["sources"]["canonical_khipu"]["count"])
        self.assertNotIn("private-path-and-owner-error-marker", response.text)
        self.assertNotIn("Traceback", response.text)
        assert_no_authority(self, body)

    def test_malformed_chain_is_unavailable_and_retains_no_partial_projection(self):
        rows = khipu_rows(3)
        rows[-1]["parents"] = [rows[0]["digest"]]
        with TestClient(make_app(ExistingDag(rows))) as client:
            response = client.get(API_PATH)
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["status"], "UNAVAILABLE")
        self.assertEqual(body["sources"]["canonical_khipu"]["state"], "UNAVAILABLE")
        self.assertEqual(body["projection"]["nodes"], [])
        assert_no_authority(self, body)

    def test_anatomy_failure_is_isolated_from_valid_khipu_observation(self):
        self.anatomy_reader.side_effect = OSError("private-overlay-path-marker")
        with TestClient(make_app(ExistingDag(khipu_rows(2)))) as client:
            response = client.get(API_PATH)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "PARTIAL")
        self.assertEqual(body["sources"]["canonical_khipu"]["count"], 2)
        self.assertEqual(len(body["projection"]["nodes"]), 2)
        self.assertEqual(body["sources"]["anatomy"]["state"], "UNAVAILABLE")
        self.assertNotIn("private-overlay-path-marker", response.text)
        assert_no_authority(self, body)

    def test_anatomy_summary_is_whitelisted_and_not_promoted_to_v7_dag(self):
        summary = anatomy_summary()
        summary["private_note"] = "anatomy-private-field-must-not-leave"
        summary["audit"]["private_note"] = "anatomy-private-field-must-not-leave"
        self.anatomy_reader.return_value = summary
        with TestClient(make_app(ExistingDag(khipu_rows(1)))) as client:
            response = client.get(API_PATH)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn("anatomy-private-field-must-not-leave", response.text)
        self.assertEqual(len(body["projection"]["nodes"]), 1)
        self.assertTrue(all(
            node["node_id"].startswith("khipu:")
            for node in body["projection"]["nodes"]
        ))
        assert_no_authority(self, body)

    def test_malformed_anatomy_summary_cannot_claim_observed(self):
        summary = anatomy_summary()
        summary["receipt_minted_on_get"] = True
        self.anatomy_reader.return_value = summary
        with TestClient(make_app(ExistingDag(khipu_rows(1)))) as client:
            response = client.get(API_PATH)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "PARTIAL")
        self.assertEqual(body["sources"]["anatomy"]["state"], "UNAVAILABLE")
        self.assertEqual(len(body["projection"]["nodes"]), 1)

    def test_blocking_owner_reads_execute_off_the_asgi_event_loop(self):
        owner = ExistingDag(khipu_rows(1))
        app = make_app(owner)
        event_loop_threads = []
        anatomy_threads = []

        @app.middleware("http")
        async def observe_loop(request: Request, call_next):
            event_loop_threads.append(threading.get_ident())
            return await call_next(request)

        def read_anatomy():
            anatomy_threads.append(threading.get_ident())
            return anatomy_summary()

        self.anatomy_reader.side_effect = read_anatomy
        with TestClient(app) as client:
            response = client.get(API_PATH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(owner.read_threads), 1)
        self.assertEqual(len(anatomy_threads), 1)
        self.assertNotEqual(owner.read_threads[0], event_loop_threads[0])
        self.assertNotEqual(anatomy_threads[0], event_loop_threads[0])

    def test_mutating_methods_and_descendants_never_reach_downstream_proxy(self):
        owner = ExistingDag(khipu_rows(1))
        with TestClient(make_app(owner)) as client:
            for path in (API_PATH, API_PATH + "/plans", API_PATH + "/plans/execute"):
                for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"):
                    with self.subTest(path=path, method=method):
                        response = client.request(method, path, json={"run": True})
                        self.assertEqual(response.status_code, 405)
                        self.assertNotIn("fell_through", response.text)
            response = client.get(API_PATH + "/plans")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("fell_through", response.text)
        self.assertEqual(owner.calls, [])
        self.anatomy_reader.assert_not_called()

    def test_head_uses_same_read_contract_without_response_body(self):
        with TestClient(make_app(ExistingDag(khipu_rows(1)))) as client:
            response = client.head(API_PATH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertIn("no-store", response.headers.get("cache-control", ""))

    def test_source_revision_is_an_observation_and_never_echoes_invalid_environment(self):
        app = make_app(ExistingDag(khipu_rows(1)))
        with TestClient(app) as client:
            with patch.dict(os.environ, {"SZL_GIT_SHA": "a" * 40}):
                response = client.get(API_PATH)
                self.assertEqual(response.json()["source_revision"], "a" * 40)
            with patch.dict(os.environ, {"SZL_GIT_SHA": "invalid-sensitive-value-marker"}):
                response = client.get(API_PATH)
                self.assertIsNone(response.json()["source_revision"])
                self.assertNotIn("invalid-sensitive-value-marker", response.text)
        self.assertEqual(response.json()["freshness"], "NOT_ASSERTED")

    def test_real_wire_f_owner_does_not_append_or_sign_on_repeated_get(self):
        import szl_provenance

        with patch.dict(os.environ, {"A11OY_STATE_STORE": ""}), patch.object(
            szl_provenance, "_state_store", None
        ):
            owner = szl_provenance._KhipuDAG("a11oy")
        with patch.object(
            szl_provenance.szl_dsse, "sign_payload",
            return_value={"signed": False, "signatures": []},
        ):
            owner.append_signed({"schema": "test.passive-read", "note": "real-owner-only"})
        before = json.dumps(owner.nodes, sort_keys=True)
        with patch.object(
            szl_provenance.szl_dsse, "sign_payload",
            side_effect=AssertionError("GET must not sign"),
        ) as signer, patch.object(
            owner, "append_signed", side_effect=AssertionError("GET must not append")
        ) as appender:
            with TestClient(make_app(owner)) as client:
                first = client.get(API_PATH)
                second = client.get(API_PATH)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(json.dumps(owner.nodes, sort_keys=True), before)
        signer.assert_not_called()
        appender.assert_not_called()
        self.assertNotIn("real-owner-only", second.text)
        assert_no_authority(self, second.json())

    def test_import_and_registration_do_not_construct_execution_runtime(self):
        script = """
import importlib.abc
import sys
from unittest.mock import patch
from fastapi import FastAPI
class RefuseExecutionRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'oro.api', 'oro.signing'}:
            raise AssertionError('passive route imported an execution runtime')
sys.meta_path.insert(0, RefuseExecutionRuntime())
with patch('sqlite3.connect', side_effect=AssertionError('database opened')), \\
     patch('pathlib.Path.mkdir', side_effect=AssertionError('directory created')), \\
     patch('socket.create_connection', side_effect=AssertionError('network called')):
    from oro.evidence_api import register
    register(FastAPI(), namespace='a11oy')
print('passive-registration-ok')
"""
        completed = subprocess.run(
            [sys.executable, "-B", "-c", script],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("passive-registration-ok", completed.stdout)


if __name__ == "__main__":
    unittest.main()
