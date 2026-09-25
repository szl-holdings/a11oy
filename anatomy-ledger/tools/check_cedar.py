#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Require real Cedar schema validation and typed authorization regression cases."""

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "policy" / "cedar"


def _run(cedar, *arguments):
    return subprocess.run(
        [str(cedar), *map(str, arguments)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def check(cedar):
    cedar = Path(cedar).resolve()
    lock = json.loads((ROOT / "toolchain-lock.json").read_text())
    version = _run(cedar, "--version")
    expected_version = "cedar-policy-cli " + lock["cedar"]["version"]
    if version.returncode or version.stdout.strip() != expected_version:
        raise RuntimeError("Cedar executable version does not match the toolchain lock")
    validations = []
    for schema_format, filename in (
        ("cedar", "intent-auth.cedarschema"),
        ("json", "intent-auth.schema.json"),
    ):
        result = _run(
            cedar,
            "validate",
            "--schema",
            POLICY / filename,
            "--schema-format",
            schema_format,
            "--policies",
            POLICY / "intent-auth.cedar",
            "--deny-warnings",
            "--error-format",
            "plain",
        )
        if result.returncode:
            raise RuntimeError(
                f"{schema_format} schema validation failed: {result.stdout}{result.stderr}"
            )
        validations.append({"format": schema_format, "validated": True})
    translated = _run(
        cedar,
        "translate-schema",
        "--direction",
        "cedar-to-json-with-resolved-types",
        "--schema",
        POLICY / "intent-auth.cedarschema",
    )
    if translated.returncode or json.loads(translated.stdout) != json.loads(
        (POLICY / "intent-auth.schema.json").read_text()
    ):
        raise RuntimeError("JSON schema differs from the canonical Cedar schema")

    request = json.loads((POLICY / "requests" / "deploy-allow.json").read_text())
    entities = json.loads((POLICY / "entities.json").read_text())
    cases = []

    def case(name, expected, request_update=None, entity_update=None):
        req, ents = copy.deepcopy(request), copy.deepcopy(entities)
        if request_update:
            request_update(req)
        if entity_update:
            entity_update(ents)
        cases.append((name, expected, req, ents))

    case("deploy-allow", "ALLOW")
    case(
        "untrusted-zone", "DENY", lambda r: r["context"].update(networkZone="untrusted")
    )
    case("unknown-zone", "DENY", lambda r: r["context"].update(networkZone="internet"))
    case("missing-approval", "DENY", lambda r: r["context"].update(humanApproval=False))
    case("missing-mfa", "DENY", lambda r: r["context"].update(mfa=False))
    case("missing-digest", "DENY", lambda r: r["context"].update(evidenceDigest=""))
    case("negative-risk", "DENY", lambda r: r["context"].update(riskScore=-1))
    case("excessive-risk", "DENY", lambda r: r["context"].update(riskScore=401))
    case("purpose-mismatch", "DENY", lambda r: r["context"].update(purpose="other"))
    case(
        "effect-mismatch", "DENY", lambda r: r["context"].update(intendedEffect="other")
    )
    case(
        "cross-tenant",
        "DENY",
        entity_update=lambda e: e[3]["attrs"].update(tenantId="foreign"),
    )
    case(
        "empty-tenant",
        "DENY",
        entity_update=lambda e: (
            e[0]["attrs"].update(tenantId=""),
            e[3]["attrs"].update(tenantId=""),
        ),
    )
    case(
        "disabled-principal",
        "DENY",
        entity_update=lambda e: e[0]["attrs"].update(disabled=True),
    )
    case(
        "insufficient-assurance",
        "DENY",
        entity_update=lambda e: e[0]["attrs"].update(assurance=0),
    )
    case(
        "tool-requires-approval",
        "DENY",
        lambda r: (
            r["action"].update(id="InvokeTool"),
            r["context"].update(humanApproval=False),
        ),
    )
    case(
        "read-resource-requires-approval",
        "DENY",
        lambda r: (
            r["action"].update(id="ReadResource"),
            r["context"].update(humanApproval=False),
        ),
    )
    case(
        "boolean-string-rejected",
        "INVALID",
        lambda r: r["context"].update(humanApproval="false"),
    )
    case("boolean-integer-rejected", "INVALID", lambda r: r["context"].update(mfa=1))
    case(
        "integer-boolean-rejected",
        "INVALID",
        lambda r: r["context"].update(riskScore=True),
    )
    case("float-risk-rejected", "INVALID", lambda r: r["context"].update(riskScore=1.9))
    case(
        "integer-overflow-rejected",
        "INVALID",
        lambda r: r["context"].update(riskScore=2**63),
    )
    case("missing-context-rejected", "INVALID", lambda r: r["context"].pop("riskScore"))
    case(
        "unknown-action-rejected", "INVALID", lambda r: r["action"].update(id="Unknown")
    )
    case(
        "unknown-type-rejected",
        "INVALID",
        lambda r: r["principal"].update(type="Unknown"),
    )
    case(
        "unknown-identity-denied", "DENY", lambda r: r["principal"].update(id="unknown")
    )
    case(
        "malformed-entity-rejected",
        "INVALID",
        entity_update=lambda e: e[0]["attrs"].update(disabled="false"),
    )

    spec = importlib.util.spec_from_file_location(
        "authorize_intent_check", ROOT / "tools" / "authorize_intent.py"
    )
    advisory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(advisory)
    results = []
    with tempfile.TemporaryDirectory(prefix="anatomy-cedar-") as temp:
        request_path, entities_path = (
            Path(temp) / "request.json",
            Path(temp) / "entities.json",
        )
        for name, expected, req, ents in cases:
            wire = copy.deepcopy(req)
            for field in ("principal", "action", "resource"):
                wire[field] = req[field]["type"] + "::" + json.dumps(req[field]["id"])
            request_path.write_text(json.dumps(wire), encoding="utf-8")
            entities_path.write_text(json.dumps(ents), encoding="utf-8")
            result = _run(
                cedar,
                "authorize",
                "--schema",
                POLICY / "intent-auth.cedarschema",
                "--policies",
                POLICY / "intent-auth.cedar",
                "--entities",
                entities_path,
                "--request-json",
                request_path,
                "--error-format",
                "plain",
            )
            lines = result.stdout.splitlines()
            allowed = result.returncode == 0 and "ALLOW" in lines
            denied = result.returncode == 2 and "DENY" in lines
            invalid = result.returncode not in (0, 2) and "ALLOW" not in lines
            matched = {"ALLOW": allowed, "DENY": denied, "INVALID": invalid}[expected]
            local = advisory.authorize(req, ents)["outcome"]
            if not matched or local != ("ALLOW" if expected == "ALLOW" else "BLOCK"):
                raise RuntimeError(
                    f"{name}: expected {expected}; exit={result.returncode}, Python={local}, "
                    f"stdout={result.stdout}, stderr={result.stderr}"
                )
            results.append(
                {
                    "id": name,
                    "expected": expected,
                    "exitCode": result.returncode,
                    "passed": True,
                }
            )
    return {
        "schema": "szl.anatomy.cedar-check.v1",
        "engine": version.stdout.strip(),
        "schemaValidations": validations,
        "passed": len(results),
        "failed": 0,
        "results": results,
        "disclosure": "Real Cedar CLI checks over local fixtures. This is not a trusted production authorization or identity integration.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cedar", required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.cedar), indent=2))


if __name__ == "__main__":
    main()
