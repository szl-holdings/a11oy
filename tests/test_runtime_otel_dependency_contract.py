#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Installed native OTLP capability; loopback fixture evidence, not production."""
import importlib.metadata
from pathlib import Path
import re
import sys
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
NAMES = ("opentelemetry-sdk", "opentelemetry-exporter-otlp")


def runtime_pins():
    pins = {}
    for line in (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==([^\s]+)", line.strip())
        if match is None:
            raise ValueError("runtime dependency must be an exact pin")
        name, version = match.groups()
        name = name.lower().replace("_", "-")
        if name in pins:
            raise ValueError("duplicate runtime dependency")
        pins[name] = version
    return pins


class SourceContractTests(unittest.TestCase):
    def test_native_export_dependencies_are_exact_runtime_pins(self):
        pins = runtime_pins()
        self.assertTrue(set(NAMES) <= set(pins), "OTLP dependencies absent from the installed runtime closure")
        self.assertEqual(pins[NAMES[0]], pins[NAMES[1]])
        self.assertRegex(pins[NAMES[0]], r"^\d+\.\d+\.\d+$")

    def test_audit_includes_runtime_without_duplicate_telemetry_pins(self):
        lines = (ROOT / "requirements-audit.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sum(line.strip() == "-r requirements-runtime.txt" for line in lines), 1)
        for name in NAMES:
            self.assertFalse(any(re.match(re.escape(name) + r"(?:\[|[=<>!~])", line.strip()) for line in lines))

    def test_image_installs_canonical_runtime_manifest(self):
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY requirements-runtime.txt /tmp/requirements-runtime.txt", docker)
        self.assertIn("pip install --no-cache-dir -r /tmp/requirements-runtime.txt", docker)
        for name in NAMES:
            self.assertNotRegex(docker, re.escape(name) + r"\s*==")


class InstalledRuntimeTests(unittest.TestCase):
    def test_installed_versions_match_runtime_pins(self):
        pins = runtime_pins()
        for name in NAMES:
            self.assertEqual(importlib.metadata.version(name), pins[name])
        self.assertEqual(importlib.metadata.version("opentelemetry-exporter-otlp-proto-grpc"), pins[NAMES[1]])

    def test_no_exporter_without_an_admitted_endpoint(self):
        from vsp_otel.middleware import _Tracer
        for endpoint in (None, "http://169.254.169.254:4317", "http://8.8.8.8:4317"):
            with self.subTest(endpoint=endpoint):
                tracer = _Tracer("fixture", endpoint=endpoint)
                try:
                    self.assertIsNone(tracer._provider)
                    self.assertIsNone(tracer._tracer)
                    self.assertTrue(tracer.exporter.startswith("in-process-only"))
                finally:
                    tracer.shutdown()

    def test_native_provider_exports_a_real_span_to_loopback(self):
        from concurrent.futures import ThreadPoolExecutor
        import grpc
        from opentelemetry import trace
        from opentelemetry.proto.collector.trace.v1 import trace_service_pb2, trace_service_pb2_grpc
        from vsp_otel.middleware import _Tracer

        received, ready, lock = [], threading.Event(), threading.Lock()

        class Receiver(trace_service_pb2_grpc.TraceServiceServicer):
            def Export(self, request, context):
                copy = trace_service_pb2.ExportTraceServiceRequest()
                copy.CopyFrom(request)
                with lock:
                    received.append(copy)
                ready.set()
                return trace_service_pb2.ExportTraceServiceResponse()

        pool = ThreadPoolExecutor(max_workers=2)
        server = grpc.server(pool)
        trace_service_pb2_grpc.add_TraceServiceServicer_to_server(Receiver(), server)
        port = server.add_insecure_port("127.0.0.1:0")
        self.assertGreater(port, 0)
        server.start()
        before = trace.get_tracer_provider()
        tracer = None
        try:
            with mock.patch.dict("os.environ", {"OTEL_TRACES_SAMPLER": "always_on"}):
                tracer = _Tracer("a11oy-runtime-ci", endpoint=f"http://127.0.0.1:{port}")
            self.assertTrue(tracer.exporter.startswith("otlp-grpc:configured:"), tracer.exporter)
            self.assertIsNotNone(tracer._provider)
            parent = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
            with tracer.server_span("runtime-otlp-fixture", parent, {"szl.test.scope": "loopback-fixture"}) as span:
                self.assertIsNotNone(span)
            tracer.shutdown()
            self.assertTrue(ready.wait(5), "configured exporter produced no loopback delivery")
            self.assertIs(trace.get_tracer_provider(), before, "native tracer replaced the global provider")
        finally:
            if tracer is not None:
                tracer.shutdown()
            server.stop(0).wait(timeout=5)
            pool.shutdown(wait=True)
        spans = []
        for request in received:
            for resource in request.resource_spans:
                attributes = {item.key: item.value.string_value for item in resource.resource.attributes}
                self.assertEqual(attributes["service.name"], "a11oy-runtime-ci")
                for scope in resource.scope_spans:
                    spans.extend(scope.spans)
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].name, "runtime-otlp-fixture")
        self.assertEqual(spans[0].trace_id.hex(), "a" * 32)
        self.assertEqual(spans[0].parent_span_id.hex(), "b" * 16)
        self.assertNotEqual(spans[0].span_id.hex(), "b" * 16)
        self.assertGreaterEqual(spans[0].end_time_unix_nano, spans[0].start_time_unix_nano)


if __name__ == "__main__":
    unittest.main(verbosity=2)
