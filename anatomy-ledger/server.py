#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Local, read-only evidence inspection and advisory policy evaluation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import socket
import stat
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

BASE = pathlib.Path(__file__).resolve().parent
PUBLIC = BASE / "public"
LEDGER = PUBLIC / "data" / "ledger.json"
MAX_REQUEST_BYTES = 256 * 1024
MAX_LEDGER_BYTES = 8 * 1024 * 1024
REQUEST_TIMEOUT = 5.0
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; img-src 'self'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'none'"
    ),
}
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Anatomy evaluator could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CEDAR = load("authorize_intent", BASE / "tools" / "authorize_intent.py")
REGO = load("evaluate_supply_chain", BASE / "tools" / "evaluate_supply_chain.py")
BIND = load("bind_anatomy", BASE / "tools" / "bind_anatomy.py")
LEDGER_LIB = load("build_ledger", BASE / "tools" / "build_ledger.py")
LAB = load("decision_lab", BASE / "tools" / "decision_lab.py")

VALID_SLSA = {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [{"name": "sample-artifact.tar.gz", "digest": {"sha256": "a" * 64}}],
    "predicateType": "https://slsa.dev/provenance/v1",
    "predicate": {
        "buildDefinition": {
            "buildType": "https://github.com/actions/attest-build-provenance"
        },
        "runDetails": {
            "builder": {
                "id": "https://github.com/szl-holdings/a11oy/.github/workflows/anatomy-ledger.yml"
            }
        },
    },
}
DIGEST = hashlib.sha256(
    json.dumps(
        VALID_SLSA, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
).hexdigest()


def prove_matrix() -> dict[str, Any]:
    """Run synthetic software regression cases; these are not trust evidence."""
    deploy = BIND.intent_from_command(
        principal_id="agent:sample-operator",
        action="DeployArtifact",
        resource_id="deployment:sample",
        purpose="release-approved-artifact",
        intended_effect="deploy",
        risk_score=250,
        human_approval=True,
        mfa=True,
        evidence_digest=DIGEST,
    )
    read = BIND.intent_from_command(
        principal_id="agent:sample-reader",
        action="ReadResource",
        resource_id="ledger:anatomy",
        purpose="inspect-evidence",
        intended_effect="read",
        risk_score=10,
        human_approval=False,
        mfa=False,
    )
    untrusted = json.loads(json.dumps(deploy))
    untrusted["context"]["networkZone"] = "untrusted"
    foreign = json.loads(json.dumps(deploy))
    foreign["resource"]["attrs"]["tenantId"] = "foreign"
    foreign["resource"]["tenantId"] = "foreign"
    forged = REGO.evaluate(
        {"statement": VALID_SLSA, "verification": {"verified": True}}
    )
    cases = [
        (
            "intent-deploy-policy-allow",
            "python-intent",
            "ALLOW",
            CEDAR.authorize(deploy)["outcome"],
        ),
        (
            "intent-read-policy-allow",
            "python-intent",
            "ALLOW",
            CEDAR.authorize(read)["outcome"],
        ),
        (
            "intent-cross-tenant-block",
            "python-intent",
            "BLOCK",
            CEDAR.authorize(foreign)["outcome"],
        ),
        (
            "intent-untrusted-block",
            "python-intent",
            "BLOCK",
            CEDAR.authorize(untrusted)["outcome"],
        ),
        (
            "evidence-forged-verification-review",
            "python-evidence",
            "REVIEW",
            forged["outcome"],
        ),
        (
            "evidence-forged-verification-false",
            "python-evidence",
            False,
            forged["verified"],
        ),
        (
            "evidence-unsigned-review",
            "python-evidence",
            "REVIEW",
            REGO.evaluate(
                {"statement": VALID_SLSA, "verification": {"verified": False}}
            )["outcome"],
        ),
        (
            "evidence-empty-block",
            "python-evidence",
            "BLOCK",
            REGO.evaluate({})["outcome"],
        ),
        (
            "bind-review-cannot-execute",
            "bind",
            False,
            BIND.bind(
                command=deploy, statement=VALID_SLSA, verification={"verified": False}
            )["executable"],
        ),
        (
            "bind-forged-verification-cannot-execute",
            "bind",
            False,
            BIND.bind(
                command=deploy, statement=VALID_SLSA, verification={"verified": True}
            )["executable"],
        ),
        (
            "bind-empty-cannot-execute",
            "bind",
            False,
            BIND.bind(command=deploy, statement={}, verification={"verified": True})[
                "executable"
            ],
        ),
        (
            "bind-untrusted-cannot-execute",
            "bind",
            False,
            BIND.bind(
                command=untrusted, statement=VALID_SLSA, verification={"verified": True}
            )["executable"],
        ),
    ]
    results = [
        {
            "id": key,
            "engine": engine,
            "expected": expected,
            "actual": actual,
            "pass": actual == expected,
        }
        for key, engine, expected, actual in cases
    ]
    passed = sum(case["pass"] for case in results)
    return {
        "schema": "szl.anatomy.prove.v1",
        "evidenceClass": "synthetic-software-qa",
        "evaluationOnly": True,
        "executable": False,
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
        "disclosure": "SAMPLE fixtures exercising local Python advisory evaluators. "
        "Passing cases do not establish native Cedar/OPA execution, cryptographic trust, "
        "production readiness, or a completed deployment.",
    }


def _reject_constant(value: str):
    raise ValueError("JSON constants must be finite")


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON keys are not accepted")
        value[key] = item
    return value


def decode_json(raw: bytes) -> dict[str, Any]:
    value = json.loads(
        raw.decode("utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_object,
    )
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def status_snapshot() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "anatomy-ledger",
        "evaluationOnly": True,
        "executable": False,
        "ledgerExists": LEDGER.is_file(),
        "evaluator": "python-advisory",
        "requestLimitBytes": MAX_REQUEST_BYTES,
        "decisionLabPolicyDigest": LAB.POLICY_AT_LOAD["digest"],
        "scenarioLimit": LAB.MAX_SCENARIOS,
        "capabilities": [
            "ledger",
            "authorize",
            "evaluate",
            "bind",
            "analyze",
            "replay",
        ],
        "disclosure": "Local inspection service. Health indicates HTTP availability only.",
    }


def _is_link(path: pathlib.Path) -> bool:
    try:
        metadata = path.lstat()
        return stat.S_ISLNK(metadata.st_mode) or bool(
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
    except FileNotFoundError:
        return False


def ledger_snapshot() -> tuple[int, dict[str, Any]]:
    try:
        if _is_link(LEDGER) or any(_is_link(parent) for parent in LEDGER.parents):
            return 503, {
                "error": "ledger symlinks are not served",
                "evaluationOnly": True,
            }
        with LEDGER.open("rb") as handle:
            raw = handle.read(MAX_LEDGER_BYTES + 1)
        if len(raw) > MAX_LEDGER_BYTES:
            return 503, {
                "error": "ledger exceeds the local inspection limit",
                "evaluationOnly": True,
            }
        ledger = decode_json(raw)
        integrity = LEDGER_LIB.validate_chain(ledger)
        return 200, {
            **ledger,
            "chainIntegrity": integrity,
            "evaluationOnly": True,
            "executable": False,
        }
    except FileNotFoundError:
        return 404, {"error": "ledger has not been built", "evaluationOnly": True}
    except (ValueError, UnicodeError, RecursionError):
        return 503, {
            "error": "ledger is not a valid JSON object",
            "evaluationOnly": True,
        }
    except OSError:
        return 503, {"error": "ledger could not be read", "evaluationOnly": True}


def evaluate_request(route: str, payload: Any) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {"error": "JSON object required", "evaluationOnly": True}
    route = route.rsplit("/", 1)[-1]
    if route not in {"authorize", "evaluate", "bind", "analyze", "replay"}:
        return 404, {"error": "unknown route", "evaluationOnly": True}
    try:
        if route == "analyze":
            result = LAB.analyze(payload)
        elif route == "replay":
            result = LAB.replay(payload)
        elif route == "authorize":
            request = payload.get("request", payload)
            if not isinstance(request, dict):
                return 422, {
                    "error": "request must be an object",
                    "evaluationOnly": True,
                }
            result = CEDAR.authorize(request)
        elif route == "evaluate":
            statement, verification = LEDGER_LIB.decode_statement(payload)
            result = REGO.evaluate(
                {"statement": statement or {}, "verification": verification}
            )
        else:
            command = payload.get("command", payload.get("request", payload))
            if not isinstance(command, dict):
                return 422, {
                    "error": "command must be an object",
                    "evaluationOnly": True,
                }
            raw_statement = payload.get("statement")
            if raw_statement is not None and not isinstance(raw_statement, dict):
                return 422, {
                    "error": "statement must be an object",
                    "evaluationOnly": True,
                }
            statement, verification = LEDGER_LIB.decode_statement(
                {
                    "statement": raw_statement,
                    "verification": payload.get("verification"),
                }
            )
            result = BIND.bind(
                command=command, statement=statement, verification=verification
            )
        return 200, {**result, "evaluationOnly": True, "executable": False}
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        return 422, {
            "error": str(exc)[:240]
            if route in {"analyze", "replay"} and isinstance(exc, ValueError)
            else "invalid evaluation input",
            "evaluationOnly": True,
            "executable": False,
        }


def read_static(route: str) -> tuple[bytes, str]:
    entry = STATIC_ROUTES.get(route)
    if entry is None:
        raise FileNotFoundError("unknown static route")
    path = PUBLIC / entry[0]
    if _is_link(path) or any(_is_link(parent) for parent in path.parents):
        raise FileNotFoundError("static symlinks are not served")
    if not path.resolve().is_relative_to(PUBLIC.resolve()) or not path.is_file():
        raise FileNotFoundError("static file unavailable")
    return path.read_bytes(), entry[1]


class RequestError(ValueError):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


class Handler(BaseHTTPRequestHandler):
    server_version = "AnatomyLocal/1"
    sys_version = ""

    def setup(self):
        self.request.settimeout(REQUEST_TIMEOUT)
        super().setup()

    def send_body(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        self.close_connection = True
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, status: int, value: object):
        self.send_body(
            status,
            json.dumps(value, ensure_ascii=False, allow_nan=False).encode(),
            "application/json; charset=utf-8",
        )

    def send_error(self, code, message=None, explain=None):
        self.send_json(
            code,
            {
                "error": message or self.responses.get(code, ("request failed",))[0],
                "evaluationOnly": True,
            },
        )

    def validate_target(self) -> str:
        try:
            target = urlsplit(self.path)
            if target.scheme or target.netloc or not target.path.startswith("/"):
                raise ValueError("relative request path required")
            hosts = self.headers.get_all("Host", [])
            if len(hosts) != 1:
                raise ValueError("one Host header is required")
            host = urlsplit("http://" + hosts[0])
            allowed = {"127.0.0.1", "localhost", "::1", self.server.server_address[0]}
            if (
                host.hostname not in allowed
                or host.username
                or host.password
                or host.path
                or host.query
                or host.fragment
            ):
                raise ValueError("host is not served by this local service")
            if (host.port or 80) != self.server.server_address[1]:
                raise ValueError("host port does not match this local service")
            origins = self.headers.get_all("Origin", [])
            if origins and (len(origins) != 1 or origins[0] != "http://" + hosts[0]):
                raise RequestError(403, "cross-origin requests are not accepted")
            return target.path
        except ValueError as exc:
            if isinstance(exc, RequestError):
                raise
            raise RequestError(421, "request host or target is not accepted") from exc

    def read_json(self) -> dict[str, Any]:
        if self.headers.get("Transfer-Encoding") is not None:
            raise RequestError(400, "transfer encoding is not supported")
        lengths = self.headers.get_all("Content-Length", [])
        if not lengths:
            raise RequestError(411, "Content-Length is required")
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
            raise RequestError(400, "Content-Length must be one nonnegative integer")
        if len(lengths[0]) > 12 or int(lengths[0]) > MAX_REQUEST_BYTES:
            raise RequestError(413, "JSON body exceeds the request limit")
        length = int(lengths[0])
        if length == 0:
            raise RequestError(400, "JSON body required")
        types = self.headers.get_all("Content-Type", [])
        if len(types) != 1 or self.headers.get_content_type() != "application/json":
            raise RequestError(415, "Content-Type must be application/json")
        if self.headers.get_content_charset("utf-8").lower() != "utf-8":
            raise RequestError(415, "JSON must use UTF-8")
        try:
            raw = self.rfile.read(length)
        except (TimeoutError, socket.timeout) as exc:
            raise RequestError(408, "request body timed out") from exc
        if len(raw) != length:
            raise RequestError(400, "request body is incomplete")
        try:
            return decode_json(raw)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise RequestError(
                400, "body must be a valid UTF-8 JSON object with unique keys"
            ) from exc

    def do_GET(self):
        try:
            path = self.validate_target()
            if path in {"/healthz", "/api/status"}:
                self.send_json(200, status_snapshot())
            elif path == "/api/ledger":
                self.send_json(*ledger_snapshot())
            elif path == "/api/prove":
                self.send_json(200, prove_matrix())
            else:
                body, content_type = read_static(path)
                self.send_body(200, body, content_type)
        except RequestError as exc:
            self.send_json(exc.status, {"error": str(exc), "evaluationOnly": True})
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            self.send_json(404, {"error": "unknown route", "evaluationOnly": True})
        except (ConnectionError, TimeoutError):
            self.close_connection = True
        except Exception as exc:
            self.log_error("local read failed: %s", type(exc).__name__)
            self.send_json(
                500, {"error": "local inspection failed", "evaluationOnly": True}
            )

    def do_POST(self):
        try:
            path = self.validate_target()
            if path not in {
                "/api/authorize",
                "/api/evaluate",
                "/api/bind",
                "/api/analyze",
                "/api/replay",
            }:
                self.send_json(404, {"error": "unknown route", "evaluationOnly": True})
                return
            self.send_json(*evaluate_request(path, self.read_json()))
        except RequestError as exc:
            self.send_json(exc.status, {"error": str(exc), "evaluationOnly": True})
        except (ConnectionError, TimeoutError):
            self.close_connection = True
        except Exception as exc:
            self.log_error("local evaluation failed: %s", type(exc).__name__)
            self.send_json(
                500,
                {
                    "error": "local evaluation failed",
                    "evaluationOnly": True,
                    "executable": False,
                },
            )

    def do_HEAD(self):
        self.do_GET()

    def do_OPTIONS(self):
        self.send_json(
            405,
            {
                "error": "only GET, HEAD and evaluation POST are supported",
                "evaluationOnly": True,
            },
        )


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, *args, **kwargs):
        self._workers = threading.BoundedSemaphore(32)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._workers.acquire(blocking=False):
            try:
                request.settimeout(1)
                body = b'{"error":"local service is busy","evaluationOnly":true}'
                request.sendall(
                    b"HTTP/1.0 503 Service Unavailable\r\nContent-Type: application/json\r\n"
                    b"Connection: close\r\nContent-Length: "
                    + str(len(body)).encode()
                    + b"\r\n\r\n"
                    + body
                )
                request.shutdown(socket.SHUT_WR)
                # Bounded draining avoids a TCP reset discarding the 503 on Windows.
                request.settimeout(0.05)
                drained = 0
                while drained < 65536:
                    chunk = request.recv(min(8192, 65536 - drained))
                    if not chunk:
                        break
                    drained += len(chunk)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._workers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._workers.release()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    with LocalServer((args.host, args.port), Handler) as server:
        print(
            f"Anatomy Ledger (evaluation only): http://{args.host}:{server.server_port}",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
