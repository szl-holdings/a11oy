# SPDX-License-Identifier: Apache-2.0
"""Fail-closed canonical deploy window. Fixtures are not live evidence."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
import importlib.util

spec = importlib.util.spec_from_file_location(
    "canonical_deploy_window",
    ROOT / ".github/scripts/canonical_deploy_window.py",
)
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)

SHA = "06fecb6a836d5c10d04e638ab91df4e6db79ce52"
OTHER = "0b5699d57a88d5b6e4d3971d6429fecb978d1c22"


def stores(origin="RESTORED"):
    return {
        label: {"kind": kind, "origin": origin, "health": "OK"}
        for label, kind in window.REQUIRED_STORES.items()
    }


def fenced(**overrides):
    status = {
        "schema": window.SCHEMA,
        "mode": "FENCED",
        "unfenced": False,
        "role": "WRITER",
        "epoch": 132,
        "durable_v1": {"status": "RETIRED", "env_ignored": False},
        "stores": stores(),
    }
    status.update(overrides)
    return status


def build(revision):
    return {"build": {"revision": revision}}


class DecideTests(unittest.TestCase):
    def test_paused_or_operator_dispatch_opens_without_storage(self):
        for stage, dispatch in (("PAUSED", False), ("RUNNING", True)):
            action, detail = window.decide(
                stage=stage, dispatch_window=dispatch, github_sha=SHA,
                build_info=None, storage_status=None,
            )
            self.assertEqual((action, detail), ("open", "operator-window"))

    def test_matching_live_revision_skips_even_when_storage_is_unfenced(self):
        action, detail = window.decide(
            stage="RUNNING", dispatch_window=False, github_sha=SHA,
            build_info=build(SHA), storage_status={"mode": "SNAPSHOT_ONLY_UNFENCED"},
        )
        self.assertEqual((action, detail), ("skip", SHA))

    def test_fenced_local_store_opens_a_running_space(self):
        action, detail = window.decide(
            stage="RUNNING", dispatch_window=False, github_sha=SHA,
            build_info=build(OTHER), storage_status=fenced(),
        )
        self.assertEqual((action, detail), ("open", "fenced-local"))

    def test_unproven_storage_stays_closed(self):
        cases = {
            "missing": None,
            "schema": fenced(schema="other"),
            "unfenced-flag": fenced(unfenced=True),
            "unfenced-mode": fenced(mode="SNAPSHOT_ONLY_UNFENCED"),
            "role": fenced(role="UNFENCED_WRITER"),
            "booting": fenced(role="BOOTING"),
            "inactive": fenced(role="NOT_ACTIVATED"),
            "epoch": fenced(epoch=None),
            "bool-epoch": fenced(epoch=True),
            "durable": fenced(durable_v1={"status": "ACTIVE", "env_ignored": False}),
            "ignored": fenced(durable_v1={"status": "RETIRED", "env_ignored": True}),
            "legacy": fenced(stores=stores("LEGACY_BOOTSTRAP")),
            "dropped-store": fenced(stores={k: v for k, v in stores().items() if k != "gdw"}),
            "html": "ok",
        }
        for name, status in cases.items():
            with self.subTest(name=name):
                action, _detail = window.decide(
                    stage="RUNNING", dispatch_window=False, github_sha=SHA,
                    build_info=build(OTHER), storage_status=status,
                )
                self.assertEqual(action, "block", name)

    def test_dispatch_string_other_than_true_does_not_open(self):
        action, _detail = window.decide(
            stage="RUNNING", dispatch_window=False, github_sha=SHA,
            build_info=None, storage_status=None,
        )
        self.assertEqual(action, "block")


class CliTests(unittest.TestCase):
    def test_cli_records_open_only_for_the_canonical_origin(self):
        seen = []

        def fetch(url):
            seen.append(url)
            if url.endswith("/api/build-info"):
                return build(OTHER)
            return fenced()

        output = Path(self.id().replace(".", "_") + ".txt")
        try:
            code = window.main([
                "--stage", "RUNNING", "--dispatch-window", "false",
                "--github-sha", SHA, "--origin", window.ALLOWED_ORIGIN,
                "--github-output", str(output),
            ], fetch=fetch)
            self.assertEqual(code, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "open=true\n")
            self.assertEqual(seen, [
                window.ALLOWED_ORIGIN + "/api/build-info",
                window.ALLOWED_ORIGIN + "/api/a11oy/v1/storage/status",
            ])
        finally:
            output.unlink(missing_ok=True)

    def test_cli_rejects_a_different_origin_without_fetching(self):
        def fetch(_url):
            raise AssertionError("fetch")

        output = Path(self.id().replace(".", "_") + ".txt")
        try:
            code = window.main([
                "--stage", "RUNNING", "--dispatch-window", "false",
                "--github-sha", SHA, "--origin", "https://example.invalid",
                "--github-output", str(output),
            ], fetch=fetch)
            self.assertEqual(code, 1)
            self.assertFalse(output.exists())
        finally:
            output.unlink(missing_ok=True)

    def test_anonymous_fetch_ignores_redirects_and_sends_no_authorization(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.server.headers = dict(self.headers)
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", window.ALLOWED_ORIGIN + "/api/build-info")
                    self.end_headers()
                    return
                body = json.dumps(fenced()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _fmt, *_args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            payload = window.fetch_json(f"http://127.0.0.1:{port}/status")
            self.assertEqual(payload["mode"], "FENCED")
            self.assertNotIn("Authorization", server.headers)
            self.assertIsNone(window.fetch_json(f"http://127.0.0.1:{port}/redirect"))
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
