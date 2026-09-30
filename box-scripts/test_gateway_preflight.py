#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic contract regressions and actual loopback transport failures."""

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import yaml

import gateway_preflight as gp

ALIAS = "fixture-alias"
BACKEND = "fixture-backend:latest"
DIGEST = "a" * 64
ORIGIN = "http://127.0.0.1:11434"
PUBLIC = "https://gateway.example.test"
ENV_NAME = "FIXTURE_GATEWAY_KEY"


def good_config():
    return {"model_list": [{"model_name": ALIAS, "litellm_params": {
        "model": "ollama_chat/" + BACKEND, "api_base": ORIGIN}}],
        "general_settings": {"master_key": "os.environ/" + ENV_NAME}}


def probe(data, status=200):
    return {"status": status, "error": None, "data": data}


def good_inputs():
    return {"model": ALIAS, "backend_model": BACKEND, "backend_digest": DIGEST,
        "ollama_url": ORIGIN, "public_gateway": PUBLIC, "key_env": ENV_NAME,
        "environ": {ENV_NAME: "sk-" + secrets.token_hex(32)},
        "catalog": probe({"models": [{"name": BACKEND, "digest": DIGEST}]}),
        "consumer": probe({"configured_model": ALIAS, "requested_model": ALIAS,
            "url": PUBLIC, "base_url": PUBLIC, "api_style": "openai /v1"}),
        "anonymous": probe(None, 401), "invalid": probe(None, 403),
        "authenticated": probe({"data": [{"id": ALIAS}]})}


class ContractTests(unittest.TestCase):
    def assert_blocked(self, config=None, inputs=None, failure=None):
        result = gp.evaluate(good_config() if config is None else config,
                             **(good_inputs() if inputs is None else inputs))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["production_ready"])
        self.assertFalse(result["activation_authorized"])
        if failure:
            self.assertIn(failure, result["failures"])
        return result

    def test_complete_fixture_is_only_local_pass(self):
        result = gp.evaluate(good_config(), **good_inputs())
        self.assertEqual(result["status"], "LOCAL_PREFLIGHT_PASS")
        self.assertEqual(result["failures"], [])
        self.assertFalse(result["production_ready"])
        self.assertFalse(result["activation_authorized"])
        self.assertIn("running_config_binding", result["not_verified"])
        self.assertIn("inference", result["not_verified"])

    def test_either_supported_ollama_provider(self):
        config = good_config()
        config["model_list"][0]["litellm_params"]["model"] = "ollama/" + BACKEND
        self.assertEqual(gp.evaluate(config, **good_inputs())["status"], "LOCAL_PREFLIGHT_PASS")

    def test_model_selection_never_falls_back(self):
        for field in ("model_name", "model"):
            with self.subTest(field=field):
                config = good_config()
                if field == "model_name":
                    config["model_list"][0][field] = "other-alias"
                else:
                    config["model_list"][0]["litellm_params"][field] = "ollama/other:latest"
                self.assert_blocked(config=config)

    def test_duplicate_gateway_alias_is_blocked(self):
        config = good_config()
        config["model_list"].append(copy.deepcopy(config["model_list"][0]))
        self.assert_blocked(config=config, failure="unique_gateway_alias")

    def test_static_profile_rejects_additional_settings(self):
        for level, field in (("root", "router_settings"), ("root", "environment_variables"),
                ("root", "custom_auth"), ("general", "custom_auth"),
                ("params", "api_key"), ("entry", "model_info")):
            with self.subTest(level=level, field=field):
                config = good_config()
                destination = {"root": config, "general": config["general_settings"],
                    "params": config["model_list"][0]["litellm_params"],
                    "entry": config["model_list"][0]}[level]
                destination[field] = "UNSUPPORTED_FIXTURE"
                self.assert_blocked(config=config, failure="static_config_only")

    def test_database_environment_blocks_static_claim(self):
        for name in ("DATABASE_URL", "STORE_MODEL_IN_DB"):
            with self.subTest(name=name):
                inputs = good_inputs()
                inputs["environ"][name] = "fixture"
                self.assert_blocked(inputs=inputs, failure="static_config_only")

    def test_inline_missing_wrong_reference_keys_blocked(self):
        for value in (None, True, 12, "INLINE_FIXTURE_SECRET", "os.environ/OTHER_KEY"):
            with self.subTest(value_type=type(value).__name__):
                config = good_config()
                config["general_settings"]["master_key"] = value
                result = self.assert_blocked(config=config, failure="auth_environment_reference")
                self.assertNotIn("INLINE_FIXTURE_SECRET", json.dumps(result))

    def test_invalid_environment_key_shapes(self):
        for key in (None, "", "short", "x" * 513, "x" * 16 + "\r\nheader: value", "x" * 16 + " "):
            with self.subTest(key_type=type(key).__name__):
                inputs = good_inputs()
                inputs["environ"][ENV_NAME] = key
                self.assert_blocked(inputs=inputs, failure="auth_key_available")

    def test_required_digest_is_independent_input(self):
        for pin in (None, "", "a" * 63, "A" * 64, True):
            with self.subTest(pin_type=type(pin).__name__):
                inputs = good_inputs()
                inputs["backend_digest"] = pin
                self.assert_blocked(inputs=inputs, failure="digest_pin_present")

    def test_wrong_missing_duplicate_catalog_model(self):
        for models in ([], [{"name": "other", "digest": DIGEST}],
                [{"name": BACKEND, "digest": "b" * 64}],
                [{"name": BACKEND, "digest": DIGEST}] * 2, None):
            with self.subTest(models=models):
                inputs = good_inputs()
                inputs["catalog"] = probe({"models": models})
                self.assert_blocked(inputs=inputs, failure="installed_model_digest")

    def test_consumer_contract_fields_are_all_required(self):
        for field in ("requested_model", "configured_model", "base_url", "url", "api_style"):
            with self.subTest(field=field):
                inputs = good_inputs()
                inputs["consumer"]["data"][field] = "other"
                self.assert_blocked(inputs=inputs)

    def test_backend_origin_must_match(self):
        config = good_config()
        config["model_list"][0]["litellm_params"]["api_base"] = "http://127.0.0.1:11435"
        self.assert_blocked(config=config, failure="backend_origin")

    def test_bad_auth_statuses_are_not_denial_proof(self):
        for name in ("anonymous", "invalid"):
            for status in (None, 200, 302, 400, 404, 500, 502, 530):
                with self.subTest(name=name, status=status):
                    inputs = good_inputs()
                    inputs[name] = probe(None, status)
                    self.assert_blocked(inputs=inputs)

    def test_positive_catalog_requires_exact_alias_once(self):
        for data in ([], [{"id": "other"}], [{"id": ALIAS}] * 2, None, "html"):
            with self.subTest(data=data):
                inputs = good_inputs()
                inputs["authenticated"] = probe({"data": data})
                self.assert_blocked(inputs=inputs, failure="authenticated_catalog_model")

    def test_missing_observations_are_not_tested(self):
        inputs = good_inputs()
        for name in ("catalog", "consumer", "anonymous", "invalid", "authenticated"):
            inputs[name] = None
        result = self.assert_blocked(inputs=inputs)
        self.assertTrue(all(p["error"] == "NOT_TESTED" for p in result["probes"].values()))

    def test_observation_bodies_and_secrets_never_emitted(self):
        inputs = good_inputs()
        sentinel = "PRIVATE_RESPONSE_SENTINEL"
        inputs["catalog"]["data"]["secret"] = sentinel
        inputs["consumer"]["data"]["secret"] = sentinel
        inputs["authenticated"]["data"]["secret"] = sentinel
        config = good_config()
        config["private"] = sentinel
        output = json.dumps(gp.evaluate(config, **inputs))
        self.assertNotIn(sentinel, output)
        self.assertNotIn(inputs["environ"][ENV_NAME], output)


class InputTests(unittest.TestCase):
    def load(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_bytes(content)
            return gp.read_config(path)

    def test_plain_config_reads(self):
        self.assertEqual(self.load(yaml.safe_dump(good_config()).encode()), good_config())

    def test_malformed_yaml_inputs(self):
        for content in (b"a: 1\na: 2\n", b"a:\n  b: 1\n  b: 2\n", b"[]", b"null",
                b"1: value", b"a: &anchor {x: 1}\nb: *anchor", b"a: !!python/object/apply:os.system ['never']",
                b"a: [", b"a: " + b"x" * gp.MAX_BYTES):
            with self.subTest(size=len(content)):
                with self.assertRaises((gp.InvalidInput, yaml.YAMLError, ValueError)):
                    self.load(content)

    def test_json_duplicate_nonfinite_and_oversized(self):
        for content in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b"x" * (gp.MAX_BYTES + 1)):
            with self.subTest(content=content[:20]):
                with self.assertRaises(ValueError):
                    gp.parse_json(content)

    def test_only_literal_loopback_with_port(self):
        for url in ("http://127.0.0.1:1234", "http://[::1]:1234/"):
            self.assertEqual(gp.base_url(url, loopback=True), url.rstrip("/"))
        for url in ("http://localhost:1234", "http://0.0.0.0:1234", "http://127.0.0.2:1234",
                "http://example.test:1234", "https://127.0.0.1:1234", "http://127.0.0.1",
                "http://user:password@127.0.0.1:1234", "http://127.0.0.1:0", "http://127.0.0.1:65536"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    gp.base_url(url, loopback=True)

    def test_empty_and_nonempty_query_fragment_rejected(self):
        for url in ("http://127.0.0.1:1234", "https://example.test"):
            for suffix in ("?", "#", "?q=1", "#fragment", "/api", "\n"):
                with self.subTest(url=url, suffix=suffix):
                    with self.assertRaises(ValueError):
                        gp.base_url(url + suffix, loopback=url.startswith("http:"))

    def test_public_base_requires_https(self):
        self.assertEqual(gp.base_url("https://example.test/"), "https://example.test")
        with self.assertRaises(ValueError):
            gp.base_url("http://example.test")

    def test_key_cannot_be_sent_to_nonloopback(self):
        for url in ("https://example.test/v1/models", "http://localhost:1234/v1/models"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                gp.get_json(url, bearer="x" * 32)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.requests.append((self.path, self.headers.get("Authorization")))
        content_type = "application/json"
        status = 200
        headers = {}
        responses = {
            "/json": b'{"data":[{"id":"fixture-alias"}]}',
            "/duplicate": b'{"x":1,"x":2}', "/invalid": b"PRIVATE_RESPONSE_SENTINEL",
            "/oversized": b"x" * (gp.MAX_BYTES + 1), "/html": b"<html>ok</html>"}
        body = responses.get(self.path, b"{}")
        if self.path == "/html":
            content_type = "text/html"
        if self.path == "/redirect":
            status, headers = 302, {"Location": "/json"}
        if self.path == "/denied":
            status, body = 401, b"PRIVATE_RESPONSE_SENTINEL"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.daemon_threads = True
        cls.server.requests = []
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.server.requests.clear()

    def test_real_json_get(self):
        result = gp.get_json(self.base + "/json", timeout=1)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["data"]["data"][0]["id"], ALIAS)

    def test_redirect_never_followed_or_credentials_forwarded(self):
        key = "sk-" + secrets.token_hex(32)
        result = gp.get_json(self.base + "/redirect", timeout=1, bearer=key)
        self.assertEqual(result["status"], 302)
        self.assertEqual(self.server.requests, [("/redirect", "Bearer " + key)])
        self.assertNotIn(key, json.dumps(result))

    def test_environment_proxy_is_ignored(self):
        with mock.patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "http_proxy": "http://127.0.0.1:1", "NO_PROXY": "", "no_proxy": ""}):
            self.assertEqual(gp.get_json(self.base + "/json", timeout=1)["status"], 200)

    def test_response_content_limits_and_json_rules(self):
        for path in ("/duplicate", "/invalid", "/oversized", "/html"):
            with self.subTest(path=path):
                result = gp.get_json(self.base + path, timeout=1)
                self.assertIsNone(result["data"])
                self.assertIsNotNone(result["error"])
                self.assertNotIn("PRIVATE_RESPONSE_SENTINEL", json.dumps(result))

    def test_denial_body_never_read_into_evidence(self):
        result = gp.get_json(self.base + "/denied", timeout=1)
        self.assertEqual(result, {"status": 401, "error": "HTTP_STATUS", "data": None})

    def raw_result(self, wire):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(2)
            port = listener.getsockname()[1]
            def respond():
                with listener.accept()[0] as connection:
                    connection.recv(8192)
                    connection.sendall(wire)
            thread = threading.Thread(target=respond, daemon=True)
            thread.start()
            result = gp.get_json(f"http://127.0.0.1:{port}/v1/models", timeout=1)
            thread.join(timeout=2)
            return result

    def test_malformed_status_never_leaks_upstream(self):
        result = self.raw_result(b"PRIVATE_RESPONSE_SENTINEL\r\n\r\n")
        self.assertEqual(result["error"], "PROBE_FAILED")
        self.assertNotIn("PRIVATE_RESPONSE_SENTINEL", json.dumps(result))

    def test_malformed_chunked_body_is_fixed_failure(self):
        result = self.raw_result(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\nPRIVATE_RESPONSE_SENTINEL\r\n")
        self.assertEqual(result["error"], "PROBE_FAILED")
        self.assertIsNone(result["data"])

    def test_valid_json_prefix_with_truncated_framing_is_rejected(self):
        result = self.raw_result(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 20\r\n\r\n{}")
        self.assertEqual(result["error"], "INCOMPLETE_BODY")
        self.assertIsNone(result["data"])


class CliTests(unittest.TestCase):
    def args(self, path):
        return ["--config", str(path), "--model", ALIAS, "--backend-model", BACKEND,
                "--backend-digest", DIGEST, "--key-env", ENV_NAME]

    def test_real_subprocess_static_check_is_json_exit_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(yaml.safe_dump(good_config()), encoding="utf-8")
            key = "sk-" + secrets.token_hex(32)
            env = dict(os.environ, **{ENV_NAME: key})
            result = subprocess.run([sys.executable, str(Path(gp.__file__).resolve()), *self.args(path)],
                capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "BLOCKED")
        self.assertEqual(result.stderr, "")
        self.assertNotIn(key, result.stdout)

    def test_invalid_input_outputs_no_exception_or_config_value(self):
        for content in ("secret: PRIVATE_RESPONSE_SENTINEL\nsecret: duplicate", "[", "null"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "config.yaml"
                path.write_text(content, encoding="utf-8")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = gp.main(self.args(path))
                result = json.loads(output.getvalue())
                self.assertEqual(code, 2)
                self.assertEqual(result["error"], "INPUT_INVALID")
                self.assertNotIn("PRIVATE_RESPONSE_SENTINEL", output.getvalue())

    def test_bad_timeout_urls_digest_environment_name(self):
        for extra in (["--timeout", "nan"], ["--timeout", "0"], ["--timeout", "11"],
                ["--gateway-origin", "http://127.0.0.1:4000?"], ["--backend-digest", "B" * 64],
                ["--key-env", "bad-name"]):
            with self.subTest(extra=extra):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(gp.main(self.args("nonexistent") + extra), 2)
                self.assertEqual(json.loads(output.getvalue())["error"], "INPUT_INVALID")

    def test_unusable_key_is_not_sent_in_probe_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            config = good_config()
            config["general_settings"]["master_key"] = "INLINE_FIXTURE_SECRET"
            path.write_text(yaml.safe_dump(config), encoding="utf-8")
            responses = [probe({"models": []}), probe({}), probe(None, 401), probe(None, 403)]
            with mock.patch.object(gp, "get_json", side_effect=responses) as getter, contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(gp.main(self.args(path) + ["--probe"]), 2)
            self.assertEqual(getter.call_count, 4)
            self.assertNotIn("INLINE_FIXTURE_SECRET", output.getvalue())


if __name__ == "__main__":
    unittest.main()
