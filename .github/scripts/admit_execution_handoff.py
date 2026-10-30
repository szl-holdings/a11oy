#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Freeze independently configured execution context; verify an unchanged runtime.

GET-only admission, not execution approval. Expected identities and public pins
come from repository configuration, never from a health response or export.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


class HandoffBlocked(ValueError):
    pass


def require(condition, code):
    if condition is not True:
        raise HandoffBlocked(code)


@lru_cache(maxsize=1)
def collector():
    spec = importlib.util.spec_from_file_location(
        "_handoff_execution_collector", ROOT / ".github/scripts/collect_execution_readiness.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_invocation(env):
    keys = ("VERIFY_CURRENT_DEPLOYMENT", "OPEN_DEPLOY_WINDOW", "PUBLISH_VERTICAL_FLAGSHIPS")
    require(all(env.get(key, "false") in ("true", "false") for key in keys),
            "INVALID_HANDOFF_MODE")
    verify = env.get("VERIFY_CURRENT_DEPLOYMENT", "false") == "true"
    if verify:
        require(env.get("GITHUB_EVENT_NAME") == "workflow_dispatch", "MANUAL_VERIFICATION_REQUIRED")
        require(env.get("OPEN_DEPLOY_WINDOW", "false") == "false"
                and env.get("PUBLISH_VERTICAL_FLAGSHIPS", "false") == "false"
                and not env.get("VERTICAL_PLAN_JSON", "").strip(),
                "VERIFICATION_MUTATION_INPUT_REFUSED")
    return verify


def independent_context(source, env):
    selected = [env.get(name, "") for name in (
        "A11OY_EXECUTION_HF_REVISION", "A11OY_EXECUTION_BOOT_ID", "A11OY_EXECUTION_RUN_NONCE")]
    require(all(type(value) is str and bool(value.strip()) for value in selected),
            "EXECUTION_CONTEXT_REQUIRED")
    gate = collector().gate
    raw = env.get("A11OY_EXECUTION_AUTHORITY_PINS_JSON", "").encode()
    require(0 < len(raw) <= 16384, "INDEPENDENT_AUTHORITY_PINS_REQUIRED")
    require("A11OY_EXECUTION_AUTHORITY_FILE" not in env, "INLINE_AUTHORITY_PINS_REQUIRED")
    pins = gate.acceptance.strict_json(raw)
    gate.acceptance.fields(pins, "schema approval_public_pem approval_key_id runtime_public_pem runtime_key_id",
                           "INVALID_AUTHORITY_CONFIGURATION")
    require(pins["schema"] == "szl.execution-authority-pins/v1", "AUTHORITY_SCHEMA_MISMATCH")
    context = gate.acceptance.AdmissionContext(source, *selected,
        pins["approval_public_pem"].encode(), pins["approval_key_id"],
        pins["runtime_public_pem"].encode(), pins["runtime_key_id"])
    gate._context(context, source)
    return context, pins


def admit(client, context, pins):
    read = collector()
    read.gate._context(context, context.source_revision)
    before = read.bracket(client, context)
    after = read.bracket(client, context)
    require(before == after, "SOURCE_RUNTIME_OR_STORAGE_CHANGED")
    return {
        "schema": "szl.execution-handoff-readback/v1", "evidence_class": "MEASURED",
        "checked_at": datetime.now(timezone.utc).isoformat(), "method": "GET_ONLY",
        "source_revision": context.source_revision, "hf_revision": context.runtime_revision,
        "runtime_boot_id": context.runtime_boot_id, "run_nonce": context.run_nonce,
        "authority_pins_sha256": hashlib.sha256(read.gate.acceptance.canonical(pins)).hexdigest(),
        "bracket": before, "execution_authorized": False, "export_collected": False,
        "provider_state_changed": False,
    }


def frozen_outputs(context, pins):
    # Validated values only: canonical JSON escapes PEM newlines. No credentials
    # are accepted or emitted, and no downstream job rereads mutable variables.
    collector().gate._context(context, context.source_revision)
    values = {"hf_revision": context.runtime_revision, "boot_id": context.runtime_boot_id,
              "run_nonce": context.run_nonce,
              "authority_pins": collector().gate.acceptance.canonical(pins).decode()}
    require(all("\n" not in value and "\r" not in value for value in values.values()),
            "HANDOFF_OUTPUT_INVALID")
    return "".join(key + "=" + value + "\n" for key, value in values.items())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-invocation", action="store_true")
    parser.add_argument("--source-sha")
    parser.add_argument("--output")
    parser.add_argument("--github-output")
    args = parser.parse_args(argv)
    try:
        validate_invocation(os.environ)
        if args.validate_invocation:
            print(json.dumps({"invocation_valid": True, "execution_authorized": False}))
            return 0
        require(bool(args.output) and bool(args.github_output), "HANDOFF_OUTPUT_REQUIRED")
        context, pins = independent_context(args.source_sha, os.environ)
        import httpx
        with httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False) as client:
            report = admit(client, context, pins)
        data = frozen_outputs(context, pins)
        with Path(args.output).open("xb") as stream:
            stream.write(collector().gate.acceptance.canonical(report))
        with Path(args.github_output).open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
        print(json.dumps({"context_frozen": True, "execution_authorized": False,
                          "provider_state_changed": False}))
        return 0
    except Exception as exc:
        # Keep caller/provider data out of logs, including malformed env values.
        code = str(exc) if isinstance(exc, HandoffBlocked) else "EXECUTION_HANDOFF_UNAVAILABLE"
        print(json.dumps({"context_frozen": False, "error": code,
                          "execution_authorized": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
