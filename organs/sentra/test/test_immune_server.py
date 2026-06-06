#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. -- SZL Holdings
#
# Integration test for sentra's immune endpoint (Wire B, sentra side).
# Boots the REAL ThreadingHTTPServer on an ephemeral port in a background
# thread and hits it over real TCP/HTTP. No mocks: the verdict path runs the
# real sentra_inspect().
#
# Run: python3 test/test_immune_server.py

from __future__ import annotations

import json
import sys
import threading
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "runtime"))

from immune_server import make_server, is_valid_traceparent  # noqa: E402


def _post(base: str, path: str, body: dict, headers: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method="POST")
    req.add_header("content-type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _get(base: str, path: str) -> tuple[int, dict]:
    with urllib.request.urlopen(base + path, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def main() -> int:
    srv = make_server("127.0.0.1", 0)  # ephemeral
    host, port = srv.server_address
    base = f"http://{host}:{port}"
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()

    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        if cond:
            print(f"  ok  - {name}")
        else:
            print(f"  FAIL- {name} {detail}")
            failures.append(name)

    try:
        # healthz
        status, body = _get(base, "/healthz")
        check("healthz returns 200 ok", status == 200 and body.get("status") == "ok")

        # clean action -> allow
        parent = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
        status, body = _post(
            base, "/v1/inspect",
            {"actionId": "act-clean", "action": {"op": "promote", "target": "model-v3"}},
            headers={"traceparent": parent},
        )
        check("clean action returns 200", status == 200)
        check("clean action -> allow", body.get("decision") == "allow", str(body))
        check("decidedBy is sentra.immune", body.get("decidedBy") == "sentra.immune")
        check("response traceparent is valid", is_valid_traceparent(body.get("traceparent", "")))
        check(
            "response traceparent keeps parent trace-id",
            body.get("traceparent", "")[3:35] == parent[3:35],
            body.get("traceparent", ""),
        )
        check(
            "response traceparent has a NEW span-id",
            body.get("traceparent", "")[36:52] != parent[36:52],
        )

        # known-bad action (SQL injection signature) -> deny
        status, body = _post(
            base, "/v1/inspect",
            {"actionId": "act-bad", "action": {"sql": "DROP TABLE receipts;"}},
        )
        check("known-bad action returns 200", status == 200)
        check("known-bad action -> deny", body.get("decision") == "deny", str(body))
        check("deny lambdaScore is 0", body.get("lambdaScore") == 0)

        # rm -rf signature -> deny
        _, body = _post(base, "/v1/inspect", {"actionId": "act-rm", "action": {"cmd": "rm -rf /"}})
        check("rm -rf signature -> deny", body.get("decision") == "deny")

        # malformed body -> 400
        try:
            req = urllib.request.Request(
                base + "/v1/inspect", data=b"{not json", method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
            check("malformed JSON rejected", False, "expected HTTPError")
        except urllib.error.HTTPError as e:
            check("malformed JSON -> 400", e.code == 400)
    finally:
        srv.shutdown()

    print(f"\n{'PASS' if not failures else 'FAIL'}: "
          f"{0 if not failures else len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
