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
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
CONTEXT_VARIABLES = ("A11OY_EXECUTION_HF_REVISION", "A11OY_EXECUTION_BOOT_ID",
                     "A11OY_EXECUTION_RUN_NONCE")
FAILURE_SCHEMA = "szl.execution-handoff-failure/v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,95}$")
STEP_OUTCOMES = frozenset(("success", "failure", "cancelled", "skipped"))
CONTEXT_FAILURE_CODES = frozenset((
    "INDEPENDENT_EXECUTION_CONTEXT_REQUIRED", "EXECUTION_SOURCE_MISMATCH",
    "EXACT_EXECUTION_REVISIONS_REQUIRED", "RUNTIME_BOOT_REQUIRED", "RUN_NONCE_REQUIRED",
    "SEPARATE_APPROVAL_AUTHORITY_REQUIRED", "PUBLIC_KEY_PIN_REQUIRED", "INVALID_PUBLIC_KEY",
    "P256_KEY_REQUIRED", "PUBLIC_KEY_PIN_MISMATCH",
))


class HandoffBlocked(ValueError):
    def __init__(self, code, *, missing_variables=()):
        super().__init__(code)
        self.missing_variables = tuple(missing_variables)


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
    selected = [env.get(name, "") for name in CONTEXT_VARIABLES]
    missing = tuple(name for name, value in zip(CONTEXT_VARIABLES, selected)
                    if type(value) is not str or not value.strip())
    if missing:
        raise HandoffBlocked("EXECUTION_CONTEXT_REQUIRED", missing_variables=missing)
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
    try:
        gate._context(context, source)
    except (gate.CombinedEvidenceError, gate.acceptance.EvidenceError) as exc:
        # Preserve only fixed context diagnostics; never print caller data.
        code = str(exc)
        raise HandoffBlocked(code if code in CONTEXT_FAILURE_CODES
                             else "EXECUTION_HANDOFF_UNAVAILABLE") from exc
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


def failure_report(source, code, stage, *, missing_variables=()):
    safe_source = source if type(source) is str and SHA40.fullmatch(source) else None
    safe_code = code if type(code) is str and SAFE_CODE.fullmatch(code) else "EXECUTION_HANDOFF_UNAVAILABLE"
    safe_stage = stage if type(stage) is str and SAFE_CODE.fullmatch(stage) else "WORKFLOW_SETUP"
    missing = [name for name in CONTEXT_VARIABLES if name in set(missing_variables)]
    report = {
        "schema": FAILURE_SCHEMA,
        "source_revision": safe_source,
        "stage": safe_stage,
        "error": safe_code,
        "context_frozen": False,
        "execution_authorized": False,
        "export_collected": False,
        "provider_state_changed": False,
    }
    if safe_code == "EXECUTION_CONTEXT_REQUIRED":
        report["missing_variables"] = missing
    return report


def canonical_failure(report):
    return (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_failure(path, report):
    with Path(path).open("xb") as stream:
        stream.write(canonical_failure(report))


def read_failure(path):
    raw = Path(path).read_bytes()
    require(0 < len(raw) <= 16384, "FAILURE_REPORT_INVALID")
    try:
        report = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffBlocked("FAILURE_REPORT_INVALID") from exc
    require(type(report) is dict and report.get("schema") == FAILURE_SCHEMA,
            "FAILURE_REPORT_INVALID")
    require(SAFE_CODE.fullmatch(str(report.get("stage", ""))) is not None
            and SAFE_CODE.fullmatch(str(report.get("error", ""))) is not None,
            "FAILURE_REPORT_INVALID")
    require(report.get("context_frozen") is False
            and report.get("execution_authorized") is False
            and report.get("export_collected") is False
            and report.get("provider_state_changed") is False,
            "FAILURE_REPORT_INVALID")
    missing = report.get("missing_variables", [])
    require(type(missing) is list and all(name in CONTEXT_VARIABLES for name in missing),
            "FAILURE_REPORT_INVALID")
    return report


def workflow_failure(env, source):
    before = env.get("HANDOFF_OWNER_BEFORE_OUTCOME", "")
    context = env.get("HANDOFF_CONTEXT_OUTCOME", "")
    after = env.get("HANDOFF_OWNER_AFTER_OUTCOME", "")
    require(all(value in STEP_OUTCOMES or value == "" for value in (before, context, after)),
            "WORKFLOW_OUTCOME_INVALID")
    if before == "failure":
        status = env.get("HANDOFF_OWNER_BEFORE_STATUS", "")
        code = ("SUPERSEDED_BY_NEWER_MAIN" if status == "SUPERSEDED_BY_NEWER_MAIN"
                else "SOURCE_OWNERSHIP_UNAVAILABLE")
        return failure_report(source, code, "SOURCE_OWNERSHIP_BEFORE")
    if context == "failure":
        return failure_report(source, "EXECUTION_HANDOFF_UNAVAILABLE", "RUNTIME_READBACK")
    if after == "failure":
        status = env.get("HANDOFF_OWNER_AFTER_STATUS", "")
        code = ("SUPERSEDED_BY_NEWER_MAIN" if status == "SUPERSEDED_BY_NEWER_MAIN"
                else "SOURCE_OWNERSHIP_UNAVAILABLE")
        return failure_report(source, code, "SOURCE_OWNERSHIP_AFTER")
    return failure_report(source, "EXECUTION_HANDOFF_UNAVAILABLE", "WORKFLOW_SETUP")


def summary(report):
    code = report["error"]
    if code == "EXECUTION_CONTEXT_REQUIRED":
        names = ", ".join("`" + name + "`" for name in report.get("missing_variables", []))
        return ("Execution handoff blocked: independently admitted context is missing. "
                f"Missing configured names: {names}. Preserve the final runtime boot, complete "
                "the approved bounded execution through the established independent authority, "
                "then dispatch verification with `verify_current_deployment=true` on the unchanged "
                "protected main. Runtime responses and exports cannot select these values.\n")
    if code == "SUPERSEDED_BY_NEWER_MAIN":
        return ("Execution handoff stopped with `SUPERSEDED_BY_NEWER_MAIN`. A newer protected "
                "main owns the next deployment and verification. No execution-context action is "
                "requested for this superseded source.\n")
    return (f"Execution handoff blocked during `{report['stage']}` with sanitized code `{code}`. "
            "Inspect the retained failure and ownership receipts before retrying. This GET-only "
            "handoff changed no provider state and grants no execution authority.\n")


def record_workflow_failure(args):
    path = Path(args.failure_output)
    if path.exists():
        report = read_failure(path)
    else:
        report = workflow_failure(os.environ, args.source_sha)
        write_failure(path, report)
    with Path(args.summary_output).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(summary(report))
    print(json.dumps({"failure_evidence_retained": True, "error": report["error"],
                      "execution_authorized": False, "provider_state_changed": False}))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-invocation", action="store_true")
    parser.add_argument("--record-workflow-failure", action="store_true")
    parser.add_argument("--source-sha")
    parser.add_argument("--output")
    parser.add_argument("--failure-output")
    parser.add_argument("--github-output")
    parser.add_argument("--summary-output")
    args = parser.parse_args(argv)
    if args.record_workflow_failure:
        require(bool(args.source_sha) and bool(args.failure_output) and bool(args.summary_output),
                "FAILURE_OUTPUT_REQUIRED")
        return record_workflow_failure(args)
    stage = "INVOCATION"
    try:
        validate_invocation(os.environ)
        if args.validate_invocation:
            print(json.dumps({"invocation_valid": True, "execution_authorized": False}))
            return 0
        require(bool(args.output) and bool(args.failure_output) and bool(args.github_output),
                "HANDOFF_OUTPUT_REQUIRED")
        stage = "CONTEXT_CONFIGURATION"
        context, pins = independent_context(args.source_sha, os.environ)
        stage = "RUNTIME_READBACK"
        import httpx
        with httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False) as client:
            report = admit(client, context, pins)
        stage = "OUTPUT_PUBLICATION"
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
        missing = exc.missing_variables if isinstance(exc, HandoffBlocked) else ()
        report = failure_report(args.source_sha, code, stage, missing_variables=missing)
        if args.failure_output:
            try:
                write_failure(args.failure_output, report)
            except (FileExistsError, OSError):
                pass
        print(json.dumps(report), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
