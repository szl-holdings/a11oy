#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

BASE = pathlib.Path(__file__).resolve().parent
PUBLIC = BASE / "public"
LEDGER = PUBLIC / "data" / "ledger.json"


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


CEDAR = load("authorize_intent", BASE / "tools" / "authorize_intent.py")
REGO = load("evaluate_supply_chain", BASE / "tools" / "evaluate_supply_chain.py")
BIND = load("bind_anatomy", BASE / "tools" / "bind_anatomy.py")
LEDGER_LIB = load("build_ledger", BASE / "tools" / "build_ledger.py")

DIGEST = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
VALID_SLSA = {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [{"name": "anatomy-ledger.tar.gz", "digest": {"sha256": DIGEST}}],
    "predicateType": "https://slsa.dev/provenance/v1",
    "predicate": {
        "buildDefinition": {"buildType": "https://github.com/actions/attest-build-provenance"},
        "runDetails": {
            "builder": {
                "id": "https://github.com/szl-holdings/a11oy/.github/workflows/anatomy-ledger.yml"
            }
        },
    },
}


def prove_matrix() -> dict[str, Any]:
    deploy = BIND.intent_from_command(
        principal_id="agent:operator-01",
        action="DeployArtifact",
        resource_id="deployment:production",
        purpose="release-approved-artifact",
        intended_effect="deploy",
        risk_score=250,
        human_approval=True,
        mfa=True,
        evidence_digest=DIGEST,
    )
    read = BIND.intent_from_command(
        principal_id="agent:reader-01",
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

    cases = [
        {"id": "cedar-deploy-allow", "engine": "cedar", "expected": "ALLOW", "actual": CEDAR.authorize(deploy)["outcome"]},
        {"id": "cedar-read-allow", "engine": "cedar", "expected": "ALLOW", "actual": CEDAR.authorize(read)["outcome"]},
        {"id": "cedar-cross-tenant", "engine": "cedar", "expected": "BLOCK", "actual": CEDAR.authorize(foreign)["outcome"]},
        {"id": "cedar-untrusted", "engine": "cedar", "expected": "BLOCK", "actual": CEDAR.authorize(untrusted)["outcome"]},
        {
            "id": "rego-allow",
            "engine": "rego",
            "expected": "ALLOW",
            "actual": REGO.evaluate({"statement": VALID_SLSA, "verification": {"verified": True}})["outcome"],
        },
        {
            "id": "rego-unsigned",
            "engine": "rego",
            "expected": "REVIEW",
            "actual": REGO.evaluate({"statement": VALID_SLSA, "verification": {"verified": False}})["outcome"],
        },
        {
            "id": "rego-empty",
            "engine": "rego",
            "expected": "BLOCK",
            "actual": REGO.evaluate({})["outcome"],
        },
        {
            "id": "bind-review-executes",
            "engine": "bind",
            "expected": True,
            "actual": BIND.bind(command=deploy, statement=VALID_SLSA, verification={"verified": False})["executable"],
        },
        {
            "id": "bind-block-stops",
            "engine": "bind",
            "expected": False,
            "actual": BIND.bind(command=deploy, statement={}, verification={"verified": True})["executable"],
        },
        {
            "id": "bind-untrusted-halts",
            "engine": "bind",
            "expected": False,
            "actual": BIND.bind(command=untrusted, statement=VALID_SLSA, verification={"verified": True})["executable"],
        },
    ]
    for case in cases:
        case["pass"] = case["actual"] == case["expected"]
    passed = sum(1 for case in cases if case["pass"])
    return {
        "schema": "szl.anatomy.prove.v1",
        "passed": passed,
        "failed": len(cases) - passed,
        "results": cases,
        "disclosure": (
            "Browser/Python twins. Cedar CLI absence is REVIEW-grade authorization coverage. "
            "OPA, when present, is the CI authority for supply-chain outcomes."
        ),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys_stderr = __import__("sys").stderr
        sys_stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_json(self, status: int, value: object) -> None:
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            value = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            payload = self.read_json()
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
            return
        if self.path == "/api/authorize":
            self.send_json(200, CEDAR.authorize(payload.get("request") or payload))
            return
        if self.path == "/api/evaluate":
            statement, verification = LEDGER_LIB.decode_statement(payload)
            self.send_json(200, REGO.evaluate({"statement": statement or {}, "verification": verification}))
            return
        if self.path == "/api/bind":
            result = BIND.bind(
                command=payload.get("command") or payload.get("request") or payload,
                statement=payload.get("statement"),
                verification=payload.get("verification"),
            )
            self.send_json(200, result)
            return
        self.send_json(404, {"error": "unknown route"})

    def do_GET(self):
        if self.path == "/healthz":
            self.send_json(200, {
                "status": "ok",
                "service": "anatomy-ledger",
                "ledgerExists": LEDGER.exists(),
                "apis": ["/healthz", "/api/ledger", "/api/prove", "/api/authorize", "/api/evaluate", "/api/bind"],
            })
            return
        if self.path == "/api/ledger":
            if not LEDGER.exists():
                self.send_json(404, {"error": "ledger has not been built"})
                return
            self.send_json(200, json.loads(LEDGER.read_text(encoding="utf-8")))
            return
        if self.path == "/api/prove":
            self.send_json(200, prove_matrix())
            return
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Anatomy Ledger: http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
