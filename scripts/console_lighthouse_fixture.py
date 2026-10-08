#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Loopback-only, labelled fixture transport. Importing never binds a socket.

Execution remains subject to the coordinator's browser/resource-slot release.
This supplies fixture HTTP responses, not an application-readiness verdict.
"""
import argparse
import ast
import base64
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from urllib.parse import parse_qs, unquote, urlsplit

from test_console_mobile_integrity import (
    ROOT, fixture_payload, fixture_receipts, initial_fixture_state, static_fixture_path,
)

SOURCE_REVISION = "a84879d3c29bf9f6905fba365d15416a79170788"
CONSOLE_SHA256 = "ba1e455069836ae92ff7f571932f95021617f7bd3f02e88f0b7d476791960b37"
VENDOR_SOURCE_SHA256 = "5b8436f8048ebdbf2f649c0321df5dc5b0b3e3a16bfb0326b9fb2e754eee4f55"
FONT_SHA256 = {
    "fonts/SpaceGrotesk.woff2": "8e085aa438094f11487a836652edd5c054fa6a96f63fc7c282105ee3a4b08c07",
    "fonts/JetBrainsMono.woff2": "31ec365b93e4bad6f202ce23352a56d01ca4462b2afc782ed2cf6fa42ca9ac0e",
}
VIEWS = ("fleet", "readiness", "estate")
CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; "
    "connect-src 'self'; worker-src 'none'; frame-src 'none'; "
    "object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


@dataclass(frozen=True)
class FixtureResponse:
    status: int
    body: bytes
    content_type: str = "application/json"


def json_response(status, payload):
    return FixtureResponse(status, json.dumps(payload).encode("utf-8"))


@lru_cache(maxsize=2)
def pinned_fonts(root):
    """Read the two real font literals without importing or executing backend code."""
    try:
        root = root.resolve()
        source = (root / "_vendor_blobs.py").resolve()
        if not source.is_relative_to(root):
            raise ValueError("Vendor source escapes fixture root")
        body = source.read_bytes()
        if hashlib.sha256(body).hexdigest() != VENDOR_SOURCE_SHA256:
            raise ValueError("Pinned vendor source mismatch")
        dictionaries = [stmt.value for stmt in ast.parse(body).body
                        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == "_B64"]
        if len(dictionaries) != 1 or not isinstance(dictionaries[0], ast.Dict):
            raise ValueError("Missing vendor literals")
        literals = ast.literal_eval(dictionaries[0])
        fonts = {name: base64.b64decode(literals[name], validate=True) for name in FONT_SHA256}
        if any(not body.startswith(b"wOF2") or hashlib.sha256(body).hexdigest() != FONT_SHA256[name]
               for name, body in fonts.items()):
            raise ValueError("Pinned font bytes mismatch")
        return fonts, None
    except (OSError, ValueError, SyntaxError, TypeError, KeyError) as error:
        return {}, str(error)


def response_headers(response):
    return {
        "Content-Type": response.content_type,
        "Content-Length": str(len(response.body)),
        "Content-Security-Policy": CSP,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
        "X-SZL-Evidence-Source": "LOCAL TEST FIXTURE; NOT PRODUCTION",
    }


def resolve_request(target, method, host, port, *, root=ROOT, state=None):
    """Pure request routing: no sockets, forwarding, credentials or mutations."""
    denied = {"state": "UNAVAILABLE", "source": "LOCAL TEST FIXTURE", "reason": "Blocked fixture request"}
    if host != f"127.0.0.1:{port}":
        return json_response(403, denied)
    if method != "GET":
        return json_response(405, denied)
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.fragment or not target.startswith("/"):
        return json_response(403, denied)
    path = unquote(parsed.path)
    if "\\" in path or "\x00" in path or any(p in (".", "..") for p in path.split("/")):
        return json_response(403, denied)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if path in ("/console", "/console/"):
        if set(query) != {"view"} or len(query["view"]) != 1 or query["view"][0] not in VIEWS:
            return json_response(403, denied)
    payload = fixture_payload(path, parsed.query, method, state or initial_fixture_state(), fixture_receipts(), True)
    if path.startswith("/api/") or path == "/healthz":
        if payload is None:
            return json_response(503, denied)
        return json_response(200, payload)
    if path == "/__fixture__/manifest":
        console = static_fixture_path("/console", root)
        verified = console is not None and hashlib.sha256(console.read_bytes()).hexdigest() == CONSOLE_SHA256
        fonts, font_error = pinned_fonts(root)
        if not verified:
            return json_response(409, {**denied, "reason": "Pinned console source mismatch"})
        if font_error:
            return json_response(409, {**denied, "reason": font_error})
        return json_response(200, {
            "source": "LOCAL TEST FIXTURE", "source_revision": SOURCE_REVISION,
            "console_sha256": CONSOLE_SHA256, "views": VIEWS,
            "vendor_source_sha256": VENDOR_SOURCE_SHA256, "font_sha256": FONT_SHA256,
            "source_pin_verified": True, "runtime_qualified": False,
        })
    font_name = path.removeprefix("/vendor/") if path.startswith("/vendor/") else None
    if font_name in FONT_SHA256:
        fonts, error = pinned_fonts(root)
        if error:
            return json_response(409, {**denied, "reason": error})
        return FixtureResponse(200, fonts[font_name], "font/woff2")
    file = static_fixture_path(path, root)
    if file is None:
        return json_response(404, denied)
    body = file.read_bytes()
    if path in ("/console", "/console/") and hashlib.sha256(body).hexdigest() != CONSOLE_SHA256:
        return json_response(409, {**denied, "reason": "Pinned console source mismatch"})
    return FixtureResponse(200, body, mimetypes.guess_type(file)[0] or "application/octet-stream")


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def handle_fixture(self):
        response = resolve_request(self.path, self.command, self.headers.get("Host"), self.server.server_port)
        self.send_response(response.status)
        for key, value in response_headers(response).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response.body)

    do_GET = handle_fixture
    do_POST = handle_fixture
    do_PUT = handle_fixture
    do_PATCH = handle_fixture
    do_DELETE = handle_fixture
    do_HEAD = handle_fixture
    do_OPTIONS = handle_fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="Explicitly bind loopback after resource-slot release")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    if not args.serve:
        parser.error("No server started. --serve requires coordinator release.")
    if not 0 <= args.port <= 65535:
        parser.error("Invalid port")
    with ThreadingHTTPServer(("127.0.0.1", args.port), FixtureHandler) as server:
        print(json.dumps({"origin": f"http://127.0.0.1:{server.server_port}", "source": "LOCAL TEST FIXTURE"}), flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
