#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Author: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
# Change-class: ADDITIVE — Doctrine v11 LOCKED 749/14/163 UNCHANGED.
"""a11oy-bridge — thin CLI over the Cross-Harness Receipt Bridge.

  Bring your own harness. We sign the truth.

Usage
-----
  # Sign a Hermes tool-call (reads tool-call JSON from a file or stdin):
  a11oy-bridge sign --from hermes --input call.json
  echo '{"name":"search","arguments":{"q":"x"}}' | a11oy-bridge sign --from hermes

  # Sign an OpenClaw tool event:
  a11oy-bridge sign --from openclaw --input event.json

  # Verify / fetch a public receipt by id:
  a11oy-bridge verify --receipt-id or-abcd1234

By default the CLI talks to the live Space (https://szlholdings-a11oy.hf.space).
Override with --base or env A11OY_BRIDGE_BASE. With --local it imports szl_bridge
in-process (no network) so it works air-gapped against the same signing code.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

DEFAULT_BASE = os.environ.get("A11OY_BRIDGE_BASE", "https://szlholdings-a11oy.hf.space")
API = "/api/a11oy/v4/bridge"


def _read_input(path: str | None) -> dict:
    raw = sys.stdin.read() if (path in (None, "-")) else open(path, encoding="utf-8").read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"a11oy-bridge: input is not valid JSON: {e}")


def _post(base: str, route: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{base}{API}/{route}", data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def _get(base: str, route: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"{base}{API}/{route}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def _local_app():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import szl_bridge as bridge
    app = FastAPI()
    bridge.register(app)
    return TestClient(app)


def cmd_sign(args: argparse.Namespace) -> int:
    harness = args.from_harness
    if harness not in ("hermes", "openclaw"):
        sys.exit("a11oy-bridge: --from must be 'hermes' or 'openclaw'")
    body = _read_input(args.input)
    if args.local:
        c = _local_app()
        r = c.post(f"{API}/{harness}", json=body)
        status, out = r.status_code, r.json()
    else:
        status, out = _post(args.base, harness, body)
    print(json.dumps(out, indent=2))
    if status == 200:
        print(f"\n✔ signed — receipt {out.get('receipt_id')}", file=sys.stderr)
        print(f"  {out.get('signed_url')}", file=sys.stderr)
        return 0
    print(f"\n✘ fail-closed (HTTP {status}) — {out.get('error')}", file=sys.stderr)
    return 1


def cmd_verify(args: argparse.Namespace) -> int:
    rid = args.receipt_id
    if args.local:
        c = _local_app()
        r = c.get(f"{API}/receipt/{rid}")
        status, out = r.status_code, r.json()
    else:
        status, out = _get(args.base, f"receipt/{rid}")
    print(json.dumps(out, indent=2))
    if status == 200 and out.get("receipt"):
        env = out["receipt"].get("envelope", {}).get("payload", {})
        print(f"\n✔ receipt {rid} found — kind={env.get('kind')!r}, public={out.get('public')}",
              file=sys.stderr)
        return 0
    print(f"\n✘ receipt {rid} not found (HTTP {status})", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="a11oy-bridge",
                                description="Cross-Harness Receipt Bridge CLI — sign / verify Khipu receipts.")
    p.add_argument("--base", default=DEFAULT_BASE, help=f"bridge base URL (default {DEFAULT_BASE})")
    p.add_argument("--local", action="store_true", help="run szl_bridge in-process (no network)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("sign", help="sign a harness tool call into a Khipu receipt")
    sp.add_argument("--from", dest="from_harness", required=True, choices=["hermes", "openclaw"])
    sp.add_argument("--input", "-i", default=None, help="JSON file (default: stdin)")
    sp.set_defaults(func=cmd_sign)

    vp = sub.add_parser("verify", help="fetch / verify a public receipt by id")
    vp.add_argument("--receipt-id", required=True)
    vp.set_defaults(func=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
