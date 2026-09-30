#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Loopback-only preview: candidate UI, allowlisted public GETs, no credentials.

This does not start the application or any operator daemon. Fixture mode is
explicit software QA, never hardware/runtime evidence. All writes are rejected.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://a-11-oy.com"
ASSETS = {
    "/assets/szl/szl-design-system.css": ("szl-design-system.css", "text/css"),
    "/assets/szl/szl-console.css": ("szl-console.css", "text/css"),
    "/assets/szl/logos/szl_favicon_square.svg": ("logos/szl_favicon_square.svg", "image/svg+xml"),
}
READ_PATHS = frozenset({
    "/api/a11oy/v1/honest", "/api/a11oy/v1/lambda", "/api/a11oy/v1/version",
    "/api/a11oy/v1/ledger", "/api/a11oy/v1/signing-status",
    "/api/a11oy/v1/mesh/state", "/api/a11oy/v1/series-a/status",
    "/api/hatun/evidence", "/healthz",
    "/api/a11oy/v1/readiness/tab-matrix?view=summary", "/api/build-info",
})


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, new_url):
        return None


class PreviewServer(ThreadingHTTPServer):
    request_queue_size = 32


class Preview(BaseHTTPRequestHandler):
    source = "fixture"

    def reply(self, status, body, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            self.reply(403, b'{"error":"host_not_allowed"}')
            return
        if self.path in ("/", "/command-v2"):
            self.reply(200, (ROOT / "pages/command-v2.html").read_bytes(), "text/html; charset=utf-8")
            return
        if self.path in ASSETS:
            name, content_type = ASSETS[self.path]
            self.reply(200, (ROOT / "console/assets/szl" / name).read_bytes(), content_type)
            return
        if self.path not in READ_PATHS:
            self.reply(404, b'{"error":"preview_path_not_allowed"}')
            return
        if self.source == "unavailable":
            self.reply(503, b'{"error":"software_qa_unavailable_fixture"}')
            return
        if self.source == "fixture":
            body = {"preview": "SYNTHETIC SOFTWARE QA", "status": "DEGRADED"}
            if self.path.endswith("/ledger"):
                body.update(count=0, signature_state="UNSIGNED", chain_verified=False)
            elif self.path.endswith("/lambda"):
                body.update({"lambda": None})
            elif self.path == "/healthz":
                body.update(signer={"status": "ABSENT"})
            self.reply(200, json.dumps(body).encode())
            return
        try:
            with build_opener(NoRedirect).open(ORIGIN + self.path, timeout=8) as response:
                body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    self.reply(502, b'{"error":"upstream_body_too_large"}')
                else:
                    self.reply(response.status, body, response.headers.get("Content-Type", "application/octet-stream"))
        except HTTPError as error:
            self.reply(error.code, b'{"error":"upstream_http_error"}')
        except (URLError, TimeoutError, OSError):
            self.reply(502, b'{"error":"upstream_unavailable"}')

    def do_POST(self):
        self.reply(405, b'{"error":"read_only_preview"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--source", choices=("live", "fixture", "unavailable"), default="fixture")
    args = parser.parse_args()
    Preview.source = args.source
    server = PreviewServer(("127.0.0.1", args.port), Preview)
    print(f"Preview http://127.0.0.1:{args.port}/command-v2 source={args.source}; writes rejected", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
