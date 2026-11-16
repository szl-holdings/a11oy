# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic observation and real-admission regression tests; no remote services.

Parser/provider tests run in a sparse checkout. Route tests require the product's
real operator and tenant modules and never substitute admission implementations.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.testclient import TestClient

from routers import training_observations as view


NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def sample(now=NOW):
    identity = "SZLHOLDINGS/synthetic-training-review"
    return {
        "schema": "szl.training-observation/v1",
        "observed_at_utc": view.iso(now),
        "started_at_utc": view.iso(now - timedelta(hours=1)),
        "cycle": 1,
        "stale_after_seconds": 660,
        "promotion_authorized": False,
        "training_complete_verified": False,
        "candidates": [{
            "repo": identity,
            "state": "CHECKPOINT_PROGRESS_OBSERVED",
            "observed_at_utc": view.iso(now - timedelta(seconds=30)),
            "target_steps": 200,
            "training_complete_verified": False,
            "promotion_authorized": False,
            "trainer_process_liveness_verified": False,
            "snapshot": {
                "id": identity,
                "status": "OBSERVED",
                "private": True,
                "revision": "a" * 40,
                "latest_checkpoint": 100,
                "artifact_integrity": "NOT_VERIFIED_BY_METADATA",
                "training_complete": "UNVERIFIED",
                "process_liveness_verified": False,
                "evaluation": "NOT_ASSESSED",
                "final_adapter": False,
                "final_config": False,
                "final_tokenizer": False,
            },
            "trainer_state": {
                "global_step": 100,
                "max_steps": 200,
                "trainer_state_sha256": "b" * 64,
                "integrity": "PINNED_OBJECT_BYTES_VERIFIED",
            },
            "provider": {
                "state": "OBSERVED", "instance_count": 2, "ready_count": 1,
                "trainer_process_liveness_verified": False,
            },
        }],
    }


def raw(value):
    return json.dumps(value, allow_nan=False, separators=(",", ":")).encode()


class ProjectionTests(unittest.TestCase):
    def invalid(self, mutate):
        value = sample()
        mutate(value)
        with self.assertRaises(view.ObservationError):
            view.project(raw(value), now=NOW)

    def test_observed_private_metadata_does_not_grant_authority(self):
        result = view.project(raw(sample()), now=NOW)
        row = result["candidates"][0]
        self.assertEqual(result["state"], "OBSERVED")
        self.assertEqual(row["state"], "OBSERVED")
        self.assertEqual(row["checkpointStep"], 100)
        self.assertEqual(row["trainerStateIntegrityReported"], "PINNED_OBJECT_BYTES_VERIFIED")
        self.assertEqual(row["providerReadyCount"], 1)
        self.assertTrue(all(value is False for value in result["authority"].values()))
        for name in ("signatureVerified", "producerAuthenticated", "durableRetentionVerified",
                     "trainingCompleteVerified", "promotionAuthorized", "trainerProcessLivenessVerified"):
            self.assertIs(result[name], False)
        for name in ("trainingCompleteVerified", "promotionAuthorized", "trainerProcessLivenessVerified",
                     "evaluationVerified", "artifactIntegrityVerified", "proofVerified"):
            self.assertIs(row[name], False)

    def test_terminal_step_and_files_remain_unverified(self):
        value = sample()
        row = value["candidates"][0]
        row["state"] = "TERMINAL_METADATA_PRESENT"
        row["snapshot"].update(latest_checkpoint=200, final_adapter=True,
                               final_config=True, final_tokenizer=True)
        row["trainer_state"]["global_step"] = 200
        result = view.project(raw(value), now=NOW)["candidates"][0]
        self.assertEqual(result["checkpointStep"], result["targetSteps"])
        self.assertTrue(all(result["finalFiles"].values()))
        self.assertTrue(all(result[key] is False for key in (
            "trainingCompleteVerified", "promotionAuthorized", "evaluationVerified",
            "artifactIntegrityVerified", "proofVerified")))

    def test_unknown_source_fields_never_escape_projection(self):
        value = sample()
        marker = "SYNTHETIC_PRIVATE_FIELD_MUST_NOT_ESCAPE"
        value["local_path"] = marker
        value["candidates"][0].update(log=marker, token=marker,
            artifact_url="https://example.invalid/" + marker, proofVerified=True)
        result = view.project(raw(value), now=NOW)
        self.assertNotIn(marker, json.dumps(result))
        self.assertNotIn("snapshot", result["candidates"][0])
        self.assertIs(result["candidates"][0]["proofVerified"], False)

    def test_report_refresh_cannot_revive_old_candidate(self):
        value = sample()
        observed = NOW - timedelta(seconds=700)
        value["candidates"][0]["observed_at_utc"] = view.iso(observed)
        result = view.project(raw(value), now=NOW)
        self.assertEqual(result["state"], "STALE")
        self.assertEqual(result["candidates"][0]["state"], "STALE")
        self.assertEqual(result["candidates"][0]["expiresAt"], view.iso(observed + timedelta(seconds=660)))
        self.assertEqual(result["candidates"][0]["observedAt"], view.iso(observed))

    def test_freshness_expires_at_exact_boundary(self):
        value = sample()
        expiry = NOW - timedelta(seconds=30) + timedelta(seconds=660)
        self.assertEqual(view.project(raw(value), now=expiry - timedelta(microseconds=1))
                         ["candidates"][0]["state"], "OBSERVED")
        self.assertEqual(view.project(raw(value), now=expiry)["candidates"][0]["state"], "STALE")

    def test_future_report_or_candidate_is_clock_skew(self):
        for candidate_future in (False, True):
            value = sample()
            value["observed_at_utc"] = view.iso(NOW + timedelta(seconds=10))
            if candidate_future:
                value["candidates"][0]["observed_at_utc"] = view.iso(NOW + timedelta(seconds=5))
            result = view.project(raw(value), now=NOW)
            self.assertEqual(result["state"], "CLOCK_SKEW")
            self.assertEqual(result["candidates"][0]["state"], "CLOCK_SKEW")

    def test_positive_producer_ttl_is_capped_and_bad_types_rejected(self):
        value = sample()
        value["stale_after_seconds"] = 7200
        result = view.project(raw(value), now=NOW)
        self.assertEqual(result["candidates"][0]["expiresAt"], view.iso(NOW + timedelta(seconds=630)))
        for ttl in (True, False, 0, -1, 1.5, "660", None, 2**53):
            with self.subTest(ttl=ttl):
                self.invalid(lambda value: value.update(stale_after_seconds=ttl))

    def test_wrong_schema_duplicate_keys_nonfinite_and_size_fail_closed(self):
        self.invalid(lambda value: value.update(schema="other/v1"))
        for body in (b"", b"[]", b"{", b"\xff", b'{"schema":1,"schema":2}',
                     b'{"extra":NaN}', b'{"extra":Infinity}',
                     raw(sample()).replace(b'"cycle":1', b'"cycle":1,"cycle":2'),
                     raw(sample())[:-1] + b',"extra":NaN}',
                     raw(sample())[:-1] + b',"extra":1e999}',
                     b"[" * 1200 + b"]" * 1200,
                     b" " * (view.MAX_BYTES + 1)):
            with self.subTest(prefix=body[:30]), self.assertRaises(view.ObservationError):
                view.project(body, now=NOW)

    def test_invalid_candidate_count_identity_and_duplicates_rejected(self):
        self.invalid(lambda value: value.update(candidates=[]))
        self.invalid(lambda value: value.update(candidates=value["candidates"] * 33))
        self.invalid(lambda value: value["candidates"].append(copy.deepcopy(value["candidates"][0])))
        for identity in ("other/model", "SZLHOLDINGS/../secret", "SZLHOLDINGS/" + "x" * 161):
            with self.subTest(identity=identity):
                self.invalid(lambda value: value["candidates"][0].update(repo=identity))

    def test_dates_require_timezone_and_causal_order(self):
        for value in ("2026-11-16T12:00:00", "bad", True):
            with self.subTest(value=value):
                self.invalid(lambda data: data.update(observed_at_utc=value))
        self.invalid(lambda value: value.update(started_at_utc=view.iso(NOW + timedelta(seconds=1))))
        self.invalid(lambda value: value["candidates"][0].update(observed_at_utc=view.iso(NOW + timedelta(seconds=1))))
        self.invalid(lambda value: value["candidates"][0].update(observed_at_utc=view.iso(NOW - timedelta(hours=2))))

    def test_verified_producer_claims_are_rejected(self):
        for key in ("training_complete_verified", "promotion_authorized"):
            with self.subTest(scope="report", key=key):
                self.invalid(lambda value: value.update({key: True}))
        for key in ("training_complete_verified", "promotion_authorized", "trainer_process_liveness_verified"):
            with self.subTest(scope="candidate", key=key):
                self.invalid(lambda value: value["candidates"][0].update({key: True}))

    def test_steps_revisions_and_provider_counts_are_consistent(self):
        changes = [
            lambda row: row.update(target_steps=True),
            lambda row: row["snapshot"].update(latest_checkpoint=-1),
            lambda row: row["snapshot"].update(revision="main"),
            lambda row: row["snapshot"].update(final_adapter=1),
            lambda row: row["trainer_state"].update(global_step=101),
            lambda row: row["trainer_state"].update(trainer_state_sha256="bad"),
            lambda row: row["trainer_state"].update(max_steps=201),
            lambda row: row["provider"].update(ready_count=3),
            lambda row: row["provider"].update(ready_count=True),
            lambda row: row["provider"].update(trainer_process_liveness_verified=True),
            lambda row: row.update(state="TERMINAL_METADATA_PRESENT"),
        ]
        for index, change in enumerate(changes):
            with self.subTest(case=index):
                self.invalid(lambda value: change(value["candidates"][0]))

    def test_missing_checkpoint_is_distinct_from_unavailable(self):
        value = sample()
        row = value["candidates"][0]
        row["state"] = "NO_CHECKPOINT_OBSERVED"
        row["snapshot"]["latest_checkpoint"] = None
        row["trainer_state"] = None
        result = view.project(raw(value), now=NOW)["candidates"][0]
        self.assertIsNone(result["checkpointStep"])
        self.assertEqual(result["producerState"], "NO_CHECKPOINT_OBSERVED")
        row.update(state="UNAVAILABLE", snapshot=None)
        result = view.project(raw(value), now=NOW)
        self.assertEqual(result["candidates"][0]["state"], "UNAVAILABLE")
        self.assertEqual(result["state"], "PARTIAL")


class FileProviderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "synthetic-observation.json"
        self.path.write_bytes(raw(sample()))

    def test_reads_current_file_without_writes_or_last_good_cache(self):
        source = view.FileObservation(str(self.path))
        first = self.path.read_bytes()
        self.assertEqual(source.read(), first)
        self.assertEqual(self.path.read_bytes(), first)
        self.path.write_bytes(b"{}")
        self.assertEqual(source.read(), b"{}")
        self.path.unlink()
        with self.assertRaises(OSError):
            source.read()

    def test_config_denies_urls_unc_relative_and_traversal(self):
        for value in ("https://example.invalid/report", "file:///private/report",
                      "//host/share/report", "\\\\host\\share\\report", "relative.json",
                      str(self.path.parent / ".." / "report.json"), "\n" + str(self.path)):
            with self.subTest(value=value):
                source = view.FileObservation(value)
                self.assertIsNone(source.path)
                with self.assertRaises(view.ObservationError):
                    source.read()

    def test_missing_empty_directory_and_oversize_are_unavailable(self):
        for content in (b"", b" " * (view.MAX_BYTES + 1)):
            self.path.write_bytes(content)
            with self.assertRaises(view.ObservationError):
                view.FileObservation(str(self.path)).read()
        with self.assertRaises((view.ObservationError, OSError)):
            view.FileObservation(str(self.path.parent)).read()
        with self.assertRaises(view.ObservationError):
            view.FileObservation(None).read()

    def test_symlink_source_is_rejected(self):
        alias = self.path.parent / "alias.json"
        try:
            alias.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable for this test account")
        with self.assertRaises((view.ObservationError, OSError)):
            view.FileObservation(str(alias)).read()

    @unittest.skipUnless(os.name == "posix", "POSIX directory descriptor race")
    def test_ancestor_swap_cannot_redirect_opened_input(self):
        """Swap a parent around the open window using only synthetic files.

        The stat hook schedules the vulnerable stat/open interleaving on older
        readers; the open hook schedules the same swap on a dir-fd reader.
        Neither hook fabricates metadata or substitutes bytes returned by read.
        """
        base = self.path.parent
        source_dir, moved_dir, foreign_dir = (base / name for name in ("input", "moved", "foreign"))
        source_dir.mkdir()
        foreign_dir.mkdir()
        source = source_dir / "report.json"
        expected = raw(sample())
        source.write_bytes(expected)
        (foreign_dir / source.name).write_bytes(b'{"foreign_private_report":true}')
        real_open, real_stat, real_fstat = os.open, Path.stat, os.fstat
        attempted = restored = False

        def swap():
            nonlocal attempted
            source_dir.rename(moved_dir)
            source_dir.symlink_to(foreign_dir, target_is_directory=True)
            attempted = True

        def restore():
            nonlocal restored
            if attempted and not restored:
                source_dir.unlink()
                moved_dir.rename(source_dir)
                restored = True

        def stat_hook(path, *args, **kwargs):
            if path == source and kwargs.get("follow_symlinks", True) and not attempted:
                swap()
            return real_stat(path, *args, **kwargs)

        def open_hook(path, flags, *args, **kwargs):
            if Path(path).name == source.name and kwargs.get("dir_fd") is not None and not attempted:
                swap()
            return real_open(path, flags, *args, **kwargs)

        def fstat_hook(fd):
            result = real_fstat(fd)
            restore()
            return result

        try:
            with patch.object(Path, "stat", stat_hook), patch.object(os, "open", open_hook), \
                    patch.object(os, "fstat", fstat_hook):
                result = view.FileObservation(str(source)).read()
            self.assertTrue(attempted, "The adversarial ancestor swap must actually execute")
            self.assertEqual(result, expected)
        finally:
            restore()

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO test")
    def test_fifo_is_rejected_without_waiting_for_writer(self):
        fifo = self.path.parent / "report.fifo"
        os.mkfifo(fifo)
        with self.assertRaises(view.ObservationError):
            view.FileObservation(str(fifo)).read()


REAL_ADMISSION_AVAILABLE = all(importlib.util.find_spec(name) is not None
    for name in ("szl_operator_auth", "a11oy_code_runloop"))
FULL_PRODUCT_ROOT = (Path(__file__).resolve().parents[1] / "serve.py").is_file()
if not REAL_ADMISSION_AVAILABLE and (FULL_PRODUCT_ROOT or os.environ.get("CI")):
    raise ImportError("The full product/CI must supply real operator and tenant admission modules")


@unittest.skipUnless(REAL_ADMISSION_AVAILABLE, "Requires the product's real admission modules")
class RouteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "synthetic-observation.json"
        self.path.write_bytes(raw(sample(datetime.now(timezone.utc))))
        self.token = "synthetic-observation-test-key-402fc991"
        self.tenant = "synthetic-observation-tenant"
        environment = patch.dict(os.environ, {
            view.FILE_ENV: str(self.path), "A11OY_CODE_ADMIN_KEY": self.token,
            "A11OY_CODE_TENANT": self.tenant,
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.app = FastAPI()
        view.register(self.app)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer " + self.token, "X-A11oy-Tenant": self.tenant}

    def denied_without_read(self, method, path, headers=None, **kwargs):
        with patch.object(view.FileObservation, "read", side_effect=AssertionError("Denied request touched source")) as read:
            response = self.client.request(method, path, headers=headers or {}, **kwargs)
            read.assert_not_called()
        return response

    def test_real_operator_and_tenant_admission_precede_every_read(self):
        for headers in ({}, {"Authorization": "Bearer wrong", "X-A11oy-Tenant": self.tenant},
                        {"Authorization": "Bearer " + self.token},
                        {**self.headers, "X-A11oy-Tenant": "wrong-tenant"}):
            with self.subTest(headers=list(headers)):
                response = self.denied_without_read("GET", view.API, headers)
                self.assertIn(response.status_code, (400, 401, 403))
                self.assertIn("no-store", response.headers["cache-control"])
                self.assertNotIn(str(self.path), response.text)

    def test_authorized_get_and_head_use_private_uncached_contract(self):
        response = self.client.get(view.API, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["schema"], view.SCHEMA)
        self.assertFalse(response.json()["producerAuthenticated"])
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertIn("Authorization", response.headers["vary"])
        self.assertIn("X-A11oy-Tenant", response.headers["vary"])
        head = self.client.head(view.API, headers=self.headers)
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b"")
        self.assertGreater(int(head.headers["content-length"]), 0)
        denied = self.denied_without_read("HEAD", view.API)
        self.assertEqual(denied.content, b"")

    def test_request_path_query_and_body_cannot_select_source(self):
        for suffix in ("?path=/private/other.json", "?url=https://example.invalid/report", "?tenant=other"):
            self.assertEqual(self.denied_without_read("GET", view.API + suffix, self.headers).status_code, 400)
        self.assertEqual(self.denied_without_read("GET", view.API, self.headers, content=b"{}").status_code, 400)
        self.assertEqual(self.denied_without_read("GET", view.API + "/private/other.json", self.headers).status_code, 404)

    def test_mutation_methods_never_read_source(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"):
            with self.subTest(method=method):
                response = self.denied_without_read(method, view.API, self.headers)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.headers["allow"], "GET, HEAD")

    def test_file_config_captured_at_registration(self):
        os.environ[view.FILE_ENV] = str(self.path.parent / "different.json")
        response = self.client.get(view.API, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)

    def test_corrupt_or_removed_source_never_reuses_success(self):
        self.assertEqual(self.client.get(view.API, headers=self.headers).status_code, 200)
        self.path.write_bytes(b"{")
        response = self.client.get(view.API, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertIsNone(response.json()["returned"])
        self.assertEqual(response.json()["candidates"], [])
        self.path.unlink()
        response = self.client.get(view.API, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(str(self.path), response.text)

    def test_registration_is_idempotent_and_catches_collision(self):
        count = len(self.app.routes)
        self.assertTrue(view.register(self.app)["alreadyRegistered"])
        self.assertEqual(len(self.app.routes), count)
        other = FastAPI()
        other.add_api_route(view.API, lambda: {}, methods=["GET"])
        with self.assertRaises(RuntimeError):
            view.register(other)

    def test_routes_precede_generic_proxy_fallback(self):
        app = FastAPI()
        fallback_calls = []

        @app.api_route("/{rest:path}", methods=sorted(view.METHODS))
        def fallback(rest: str):
            fallback_calls.append(rest)
            return {"fallback": True}

        view.register(app)
        with TestClient(app) as client:
            self.assertEqual(client.get(view.API, headers=self.headers).status_code, 200)
            self.assertEqual(client.get(view.API + "/other", headers=self.headers).status_code, 404)
            self.assertEqual(client.post(view.API, headers=self.headers).status_code, 405)
            self.assertEqual(fallback_calls, [])
            self.assertTrue(client.get("/unrelated").json()["fallback"])
            self.assertEqual(fallback_calls, ["unrelated"])


class FailClosedProxyTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_private_registration_never_forwards_to_backend(self):
        """Execute the real fallback guard without importing the service.

        Calling the extracted fallback directly models private-route registration
        failing. Only its backend transport is replaced, by an async call spy.
        """
        source = Path(__file__).resolve().parents[1] / "serve.py"
        if not source.is_file():
            if os.environ.get("CI"):
                self.fail("CI must include serve.py for the private proxy-boundary test")
            self.skipTest("Sparse checkout does not include serve.py")
        tree = ast.parse(source.read_bytes(), filename=str(source))
        constants = [node for node in tree.body
            if (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                and target.id == "_LOCAL_ONLY_A11OY_PREFIXES" for target in node.targets))
            or (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == "_LOCAL_ONLY_A11OY_PREFIXES")]
        functions = [node for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "api_proxy"]
        self.assertEqual(len(constants), 1, "Expected the real local-only prefix declaration")
        self.assertEqual(len(functions), 1, "Expected the real async API fallback")
        function = copy.deepcopy(functions[0])
        function.decorator_list = []
        selected = ast.fix_missing_locations(ast.Module(
            body=[copy.deepcopy(constants[0]), function], type_ignores=[]))
        forwarded = []

        async def proxy_spy(request, path):
            forwarded.append((request, path))
            return JSONResponse({"syntheticProxy": True}, status_code=207)

        namespace = {"Request": Request, "Response": Response, "JSONResponse": JSONResponse,
                     "proxy_to_backend": proxy_spy}
        exec(compile(selected, str(source), "exec"), namespace)

        def request_for(method, path):
            return Request({"type": "http", "method": method, "scheme": "http",
                "path": "/api/a11oy/" + path, "query_string": b"", "headers": []})

        private_path = "v1/models/training-observations"
        for path in (private_path, private_path + "/", private_path + "/private/report.json"):
            for method in sorted(view.METHODS):
                with self.subTest(path=path, method=method):
                    response = await namespace["api_proxy"](request=request_for(method, path), path=path)
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(forwarded, [], "Private requests must never reach backend transport")

        control = "v1/synthetic-unrelated-proxy-control"
        self.assertFalse(control.startswith(namespace["_LOCAL_ONLY_A11OY_PREFIXES"]))
        request = request_for("GET", control)
        response = await namespace["api_proxy"](request=request, path=control)
        self.assertEqual(response.status_code, 207)
        self.assertEqual(forwarded, [(request, "/" + control)])


if __name__ == "__main__":
    unittest.main()
