# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings — Yachay (CTO) + Perplexity Computer Agent
# Doctrine v11 LOCKED — 749/14/163 · Λ = Conjecture 1
"""Integration test: a REAL span crosses the OTLP/gRPC wire and arrives.

Two real paths, in order of availability:

  A. **In-process OTLP/gRPC receiver** (default, no Docker needed): we bind a
     real ``TraceServiceServicer`` to a localhost gRPC port, point the real
     ``OTLPSpanExporter`` at it, emit a span through the full SDK pipeline
     (TracerProvider -> DSSE/Khipu processor -> BatchSpanProcessor -> OTLP gRPC),
     flush, and assert the span arrived on the wire AND was Khipu-chained.

  B. **Docker OTLP Collector** (when ``VSP_OTEL_IT_DOCKER=1`` and docker present):
     spins up ``otel/opentelemetry-collector`` with a debug exporter and asserts
     the span shows up — the closest thing to production.

Path A is a genuine gRPC round-trip (not a mock), so the test is real even in a
Docker-less CI runner. The test SKIPS (not fails) only if the OTel SDK / OTLP
gRPC packages are entirely absent.
"""

from __future__ import annotations

import os
import time

import pytest

otel = pytest.importorskip("opentelemetry.sdk.trace")
grpc = pytest.importorskip("grpc")
pb = pytest.importorskip(
    "opentelemetry.proto.collector.trace.v1.trace_service_pb2")
pb_grpc = pytest.importorskip(
    "opentelemetry.proto.collector.trace.v1.trace_service_pb2_grpc")


class _CollectingTraceService(pb_grpc.TraceServiceServicer):
    """A real in-process OTLP TraceService that records what it receives."""

    def __init__(self):
        self.requests = []

    def Export(self, request, context):
        self.requests.append(request)
        return pb.ExportTraceServiceResponse()

    def span_names(self):
        names = []
        for req in self.requests:
            for rs in req.resource_spans:
                for ss in rs.scope_spans:
                    for sp in ss.spans:
                        names.append(sp.name)
        return names


@pytest.fixture
def otlp_receiver():
    from concurrent import futures

    servicer = _CollectingTraceService()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    pb_grpc.add_TraceServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield servicer, f"127.0.0.1:{port}"
    finally:
        server.stop(grace=1).wait(timeout=3)


def test_span_crosses_otlp_grpc_wire_and_is_khipu_chained(otlp_receiver):
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    from vsp_otel.dsse_processor import DSSEKhipuSpanProcessor, KhipuChain
    from vsp_otel.exporter import VSPExporterConfig, build_exporter

    servicer, addr = otlp_receiver

    chain = KhipuChain()
    provider = TracerProvider(resource=Resource.create({"service.name": "it"}))
    # DSSE/Khipu binding processor.
    provider.add_span_processor(DSSEKhipuSpanProcessor(chain=chain))
    # Real OTLP/gRPC exporter pointed at the in-process receiver.
    exporter = build_exporter(VSPExporterConfig(endpoint=f"http://{addr}",
                                                insecure=True))
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    tracer = provider.get_tracer("vsp-otel-it")
    with tracer.start_as_current_span("verifiable-span") as span:
        span.set_attribute("szl.test", "real-wire")

    provider.force_flush()
    provider.shutdown()

    # Give the server a brief moment to record the export.
    deadline = time.time() + 3
    while time.time() < deadline and "verifiable-span" not in servicer.span_names():
        time.sleep(0.05)

    # The span actually crossed the OTLP/gRPC wire.
    assert "verifiable-span" in servicer.span_names()
    # ...and it was bound into the Khipu chain.
    assert len(chain) >= 1
    assert chain.verify() is True


@pytest.mark.skipif(os.environ.get("VSP_OTEL_IT_DOCKER") != "1",
                    reason="Docker collector path opt-in via VSP_OTEL_IT_DOCKER=1")
def test_span_arrives_at_real_collector_container():
    """Opt-in: stand up a real otel-collector container and export to it."""
    import shutil
    import subprocess

    if not shutil.which("docker"):
        pytest.skip("docker not available")

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    from vsp_otel.exporter import VSPExporterConfig, build_exporter

    name = "vsp-otel-it-collector"
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    up = subprocess.run(
        ["docker", "run", "-d", "--name", name, "-p", "4317:4317",
         "otel/opentelemetry-collector:latest"],
        capture_output=True, text=True)
    assert up.returncode == 0, up.stderr
    try:
        time.sleep(4)  # collector boot
        provider = TracerProvider(
            resource=Resource.create({"service.name": "it-docker"}))
        exporter = build_exporter(
            VSPExporterConfig(endpoint="http://127.0.0.1:4317", insecure=True))
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("vsp-otel-it-docker")
        with tracer.start_as_current_span("docker-span"):
            pass
        provider.force_flush()
        provider.shutdown()
        time.sleep(1)
        logs = subprocess.run(["docker", "logs", name],
                              capture_output=True, text=True)
        assert "docker-span" in (logs.stdout + logs.stderr)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
