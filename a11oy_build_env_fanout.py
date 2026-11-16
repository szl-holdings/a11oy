#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Opt-in, fixed-target health fan-out for the isolated five-service build environment.

Services/observability only: no model invocation, signing, state mutation, or
execution approval. An acknowledgement proves bounded health reads and trace
continuity, not collector delivery. The independent Jaeger gate remains required.
W3C propagation follows https://opentelemetry.io/docs/languages/python/propagation/.
"""
import asyncio
import json
import os
import threading

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from vsp_otel.middleware import parse_traceparent

SCHEMA = "szl.build-env.fanout-ack/v1"
FANOUT = ("sentra", "amaru", "killinchu", "rosie")
# Immutable infrastructure coordinates, not request-selected URLs or product names.
TARGETS = (
    ("sentra", "http://sentra.szl.svc:8080/healthz"),
    ("amaru", "http://amaru.szl.svc:8080/healthz"),
    ("killinchu", "http://killinchu.szl.svc:8080/api/killinchu/healthz"),
    ("rosie", "http://rosie.szl.svc:8080/healthz"),
)
QUERY = ("fanout=" + ",".join(FANOUT)).encode("ascii")
MAX_RESPONSE_BYTES = 16 * 1024
REQUEST_TIMEOUT_SECONDS = 2.0
TOTAL_TIMEOUT_SECONDS = 3.0
MAX_ACTIVE_FANOUTS = 2


def _response(status, *, reason=None, traceparent=None):
    body = {"schema": SCHEMA, "accepted": status == 200}
    if status == 200:
        body.update(traceparent=traceparent, fanout=list(FANOUT))
    else:
        body.update(reason=reason, execution_authorized=False, receipt_minted=False)
    headers = {
        "cache-control": "private, no-store",
        "x-szl-evidence-scope": "fixed-health-readback",
        "x-szl-collector-delivery": "unverified",
        "x-szl-execution-authority": "none",
    }
    if status == 405:
        headers["allow"] = "GET"
    return JSONResponse(body, status_code=status, headers=headers)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError("non-finite JSON value")


def _admitted_context(request):
    if os.environ.get("A11OY_BUILD_ENV_FANOUT") != "1":
        return "FANOUT_DISABLED", None, None
    app = request.app
    if (os.environ.get("OTEL_SERVICE_NAME") != "a11oy"
            or getattr(app, "_vsp_otel_service", None) != "a11oy"
            or getattr(app, "_vsp_otel_installed", False) is not True
            or not str(getattr(app, "_vsp_otel_exporter", "")).startswith("otlp-grpc:configured:")):
        return "TRACING_NOT_CONFIGURED", None, None
    values = request.headers.getlist("traceparent")
    if len(values) != 1 or values[0] != values[0].strip():
        return "TRACEPARENT_REQUIRED", None, None
    incoming = parse_traceparent(values[0])
    if not incoming or not incoming["sampled"]:
        return "TRACEPARENT_REQUIRED", None, None
    continuing = getattr(request.state, "traceparent", None)
    current = parse_traceparent(continuing)
    if (not current or not current["sampled"]
            or current["trace_id"] != incoming["trace_id"]
            or current["parent_id"] == incoming["parent_id"]
            or not str(getattr(request.state, "vsp_otel_exporter", "")).startswith("otlp-grpc:configured:")):
        return "TRACE_CONTEXT_UNAVAILABLE", None, None
    return None, values[0], continuing


async def _probe(client, url, traceparent):
    """One bounded GET; construct the request without client-cookie inheritance."""
    response = None
    try:
        # Do not use build_request/stream: those merge the shared client's cookie
        # jar. Direct Requests retain only this fixed, credential-free header set.
        request = httpx.Request("GET", url, headers={
            "accept": "application/json", "accept-encoding": "identity",
            "traceparent": traceparent,
        })
        response = await client.send(request, stream=True, follow_redirects=False)
        if response.status_code != 200:
            return "PEER_STATUS_UNAVAILABLE"
        if (response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json"
                or response.headers.get("content-encoding", "identity").lower() != "identity"):
            return "PEER_JSON_REQUIRED"
        declared = response.headers.get_list("content-length")
        if declared and (len(declared) != 1 or not declared[0].isascii()
                         or not declared[0].isdigit() or len(declared[0]) > 6
                         or not 0 < int(declared[0]) <= MAX_RESPONSE_BYTES):
            return "PEER_BODY_LIMIT"
        parent_values = response.headers.get_list("traceparent")
        outgoing = parse_traceparent(traceparent)
        echoed = parse_traceparent(parent_values[0]) if len(parent_values) == 1 else None
        if (not echoed or not echoed["sampled"]
                or parent_values[0] != parent_values[0].strip()
                or echoed["trace_id"] != outgoing["trace_id"]
                or echoed["parent_id"] == outgoing["parent_id"]):
            return "PEER_TRACE_UNAVAILABLE"
        raw = bytearray()
        async for chunk in response.aiter_raw():
            if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                return "PEER_BODY_LIMIT"
            raw.extend(chunk)
        if declared and len(raw) != int(declared[0]):
            return "PEER_BODY_LIMIT"
        body = json.loads(bytes(raw).decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
        if type(body) is not dict or not body:
            return "PEER_JSON_REQUIRED"
        return None
    except (ValueError, UnicodeError, RecursionError):
        return "PEER_JSON_REQUIRED"
    except httpx.TimeoutException:
        return "PEER_TIMEOUT"
    except Exception:
        # Provider exceptions and bodies may contain private data; never echo them.
        return "PEER_UNAVAILABLE"

    finally:
        if response is not None:
            await response.aclose()


def register(app):
    """Reserve the exact root contract before the SPA; disabled unless opted in."""
    if getattr(app.state, "build_env_fanout_registered", False):
        return
    slots = threading.BoundedSemaphore(MAX_ACTIVE_FANOUTS)

    async def fanout(request: Request):
        if request.method != "GET":
            return _response(405, reason="METHOD_NOT_ALLOWED")
        if request.scope.get("query_string", b"") != QUERY:
            return _response(400, reason="EXACT_FANOUT_REQUIRED")
        reason, incoming, continuing = _admitted_context(request)
        if reason:
            status = 400 if reason == "TRACEPARENT_REQUIRED" else 503
            return _response(status, reason=reason)
        if not slots.acquire(blocking=False):
            return _response(429, reason="FANOUT_BUSY")
        try:
            async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
                # One bounded pool avoids repeated synchronous client/TLS setup
                # consuming the whole deadline before any peer can respond.
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
                    limits=httpx.Limits(max_connections=len(TARGETS), max_keepalive_connections=0),
                    follow_redirects=False, trust_env=False,
                ) as client:
                    async with asyncio.TaskGroup() as group:
                        tasks = [group.create_task(_probe(client, url, continuing)) for _name, url in TARGETS]
            for task in tasks:
                if task.result() is not None:
                    return _response(503, reason=task.result())
            return _response(200, traceparent=incoming)
        except TimeoutError:
            return _response(504, reason="FANOUT_DEADLINE")
        except Exception:
            return _response(503, reason="FANOUT_UNAVAILABLE")
        finally:
            slots.release()

    app.add_api_route("/route", fanout, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                      include_in_schema=False)
    app.state.build_env_fanout_registered = True
