#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Loopback HTTP/OTLP integration with fixture peers, never a production proof."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import socket
import threading
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import grpc
import httpx
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2, trace_service_pb2_grpc
import uvicorn

import a11oy_build_env_fanout as fanout
from vsp_otel import middleware as vsp


class Collector(trace_service_pb2_grpc.TraceServiceServicer):
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = []

    def Export(self, request, context):
        copied = trace_service_pb2.ExportTraceServiceRequest()
        copied.CopyFrom(request)
        with self.lock:
            self.requests.append(copied)
        return trace_service_pb2.ExportTraceServiceResponse()


def test_native_fanout_exports_one_connected_five_service_trace(monkeypatch, tmp_path):
    collector = Collector()
    pool = ThreadPoolExecutor(max_workers=4)
    grpc_server = grpc.server(pool)
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(collector, grpc_server)
    grpc_port = grpc_server.add_insecure_port("127.0.0.1:0")
    assert grpc_port > 0
    grpc_server.start()
    endpoint = f"http://127.0.0.1:{grpc_port}"
    monkeypatch.setenv("A11OY_BUILD_ENV_FANOUT", "1")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "a11oy")
    original_client = httpx.AsyncClient
    peers, servers, threads, sockets, arrivals = {}, [], [], [], []
    timings = []
    app = FastAPI(title="a11oy")
    vsp.install(app, service_name="a11oy", endpoint=endpoint)
    fanout.register(app)
    try:
        for name, url in fanout.TARGETS:
            peer = FastAPI(title=name)
            async def health():
                return JSONResponse({"status": "fixture-health", "production_readiness": "UNVERIFIED"})
            peer.add_api_route(httpx.URL(url).path, health, methods=["GET"])
            vsp.install(peer, service_name=name, endpoint=endpoint)
            assert peer._vsp_otel_exporter.startswith("otlp-grpc:configured:")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            sock.listen(16)
            sockets.append(sock)
            port = sock.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(peer, host="127.0.0.1", port=port,
                                                  log_level="error", access_log=False, loop="asyncio", http="h11", ws="none"))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
            servers.append(server)
            threads.append(thread)
            thread.start()
            peers[httpx.URL(url).host] = (port, peer)
        deadline = time.monotonic() + 10
        while not all(server.started for server in servers):
            assert time.monotonic() < deadline, "loopback fixture peers did not start: " + repr([(s.started, t.is_alive()) for s, t in zip(servers, threads)])
            time.sleep(0.01)

        class LoopbackTransport(httpx.AsyncBaseTransport):
            def __init__(self):
                started = time.monotonic()
                self.inner = httpx.AsyncHTTPTransport(retries=0, trust_env=False)
                timings.append({"transport_setup_seconds": time.monotonic() - started})

            async def handle_async_request(self, request):
                assert request.url.host in peers
                assert request.method == "GET"
                assert "authorization" not in request.headers and "cookie" not in request.headers
                port, _peer = peers[request.url.host]
                arrivals.append({"host": request.url.host, "path": request.url.path,
                                 "traceparent": request.headers["traceparent"]})
                # Test-only DNS replacement. Real HTTP crosses loopback sockets;
                # the production selector still chooses the exact fixed hostname.
                mapped = request.url.copy_with(host="127.0.0.1", port=port)
                forwarded = httpx.Request("GET", mapped, headers={
                    "accept": "application/json", "accept-encoding": "identity",
                    "traceparent": request.headers["traceparent"],
                })
                forwarded.extensions.update(request.extensions)
                started = time.monotonic()
                result = await self.inner.handle_async_request(forwarded)
                timings.append({"peer": request.url.host, "header_seconds": time.monotonic() - started})
                return result

            async def aclose(self):
                await self.inner.aclose()

        def client_factory(**options):
            assert options["trust_env"] is False and options["follow_redirects"] is False
            return original_client(transport=LoopbackTransport(), **options)

        monkeypatch.setattr(fanout.httpx, "AsyncClient", client_factory)
        trace_id, root_id = "a" * 32, "b" * 16
        incoming = f"00-{trace_id}-{root_id}-01"
        seed_us = time.time_ns() // 1000
        with TestClient(app) as client:
            response = client.get("/route?fanout=sentra,amaru,killinchu,rosie",
                                  headers={"traceparent": incoming})
            assert response.status_code == 200, response.text + json.dumps({"arrivals": arrivals, "timings": timings})
            assert response.json() == {"schema": fanout.SCHEMA, "accepted": True,
                                       "fanout": list(fanout.FANOUT), "traceparent": incoming}
            assert response.headers["x-szl-collector-delivery"] == "unverified"
        assert len(arrivals) == 4
    finally:
        # Shut down the real native middleware providers: this flushes OTLP
        # batches instead of asserting on configured-but-unexported spans.
        app._vsp_otel_shutdown()
        for server in servers:
            server.should_exit = True
        for thread in threads:
            thread.join(timeout=10)
        for _port, peer in peers.values():
            peer._vsp_otel_shutdown()
        for sock in sockets:
            sock.close()
        grpc_server.stop(1).wait(timeout=5)
        pool.shutdown(wait=True)
    assert not any(thread.is_alive() for thread in threads), "fixture server leaked"
    spans = []
    for request in collector.requests:
        for resource in request.resource_spans:
            attributes = {a.key: a.value.string_value for a in resource.resource.attributes}
            service = attributes["service.name"]
            for scope in resource.scope_spans:
                for span in scope.spans:
                    spans.append({"traceID": span.trace_id.hex(), "spanID": span.span_id.hex(),
                                  "parent": span.parent_span_id.hex(), "service": service,
                                  "name": span.name, "startTime": span.start_time_unix_nano // 1000,
                                  "duration": (span.end_time_unix_nano - span.start_time_unix_nano) // 1000})
    assert len(spans) == 5
    assert {span["service"] for span in spans} == {"a11oy", *fanout.FANOUT}
    assert all(span["traceID"] == trace_id and span["startTime"] >= seed_us for span in spans)
    root_span = next(span for span in spans if span["service"] == "a11oy")
    assert root_span["parent"] == root_id
    assert all(span["parent"] == root_span["spanID"] for span in spans if span is not root_span)
    assert len({span["spanID"] for span in spans}) == 5
    for arrival in arrivals:
        assert arrival["traceparent"] == f"00-{trace_id}-{root_span['spanID']}-01"
    jaeger = {"data": [{"spans": [{
        "traceID": span["traceID"], "spanID": span["spanID"], "startTime": span["startTime"],
        "duration": span["duration"], "process": {"serviceName": span["service"]},
        "references": [{"refType": "CHILD_OF", "traceID": trace_id, "spanID": span["parent"]}],
    } for span in spans]}]}
    (tmp_path / "loopback-jaeger-shape.json").write_text(json.dumps(jaeger), encoding="utf-8")
    (tmp_path / "loopback-trace-witness.json").write_text(json.dumps({
        "schema": "szl.build-env-loopback-test/v1", "scope": "real-loopback-http-and-otlp-with-fixture-peers",
        "trace_id": trace_id, "injected_root_span_id": root_id, "seed_epoch_us": seed_us,
        "spans": spans, "requests": arrivals, "production_verified": False,
        "signature": "UNSIGNED", "receipt_minted": False,
    }, indent=2), encoding="utf-8")
