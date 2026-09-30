#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Retain bounded prerequisite evidence; metadata cannot authorize publication."""

import argparse
import json
import re
from pathlib import Path

MAX_REPORT_BYTES = 16 * 1024
SCHEMAS = {
    "series_a": "szl.hf-series-a-runtime-config/v1",
    "gdw": "szl.hf-gdw-runtime-config/v1",
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def inspect_report(path, schema, exit_code):
    # Do not echo arbitrary fields, provider errors, values, or supplied names.
    valid = False
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_REPORT_BYTES + 1)
        if len(raw) > MAX_REPORT_BYTES:
            raise ValueError("oversized report")
        report = json.loads(raw, object_pairs_hook=unique_object)
        valid = (
            type(report) is dict
            and report.get("schema") == schema
            and report.get("repo_id") == "SZLHOLDINGS/a11oy"
            and report.get("state") == "SETUP_REQUIRED"
            and report.get("credential_authority_state") == "UNKNOWN"
            and report.get("converged") is False
            and report.get("secret_values_read") is False
            and report.get("secret_values_written") is False
            and type(exit_code) is int
            and exit_code == 1
        )
    except (OSError, ValueError, UnicodeError, RecursionError):
        pass
    return {"report_valid": valid, "state": "SETUP_REQUIRED",
            "credential_authority_state": "UNKNOWN"}


def prerequisite_report(series_a, gdw, source_sha, series_exit, gdw_exit):
    source_valid = type(source_sha) is str and re.fullmatch(r"[0-9a-f]{40}", source_sha) is not None
    return {
        "schema": "szl.hf-manual-prerequisites/v1",
        "repo_id": "SZLHOLDINGS/a11oy",
        "source_revision": source_sha if source_valid else "UNVALIDATED",
        "state": "SETUP_REQUIRED",
        "credential_authority_state": "UNKNOWN",
        "converged": False,
        "source_revision_valid": source_valid,
        "series_a": inspect_report(series_a, SCHEMAS["series_a"], series_exit),
        "gdw": inspect_report(gdw, SCHEMAS["gdw"], gdw_exit),
        "secret_values_read": False,
        "secret_values_written": False,
        "diagnostic_code": "INSTALLED_AUTHORITY_UNKNOWN",
    }


def blocked_proof_report(kind, source_sha):
    valid = type(source_sha) is str and re.fullmatch(r"[0-9a-f]{40}", source_sha) is not None
    return {
        "schema": "szl.series-a-restart-proof/v1" if kind == "series-a" else "szl.hf-gdw-live-proof/v1",
        "source_revision": source_sha if valid else "UNVALIDATED",
        "status": "FAIL", "ok": False, "evidence": {},
        "credential_authority_state": "UNKNOWN",
        "error": {"type": "RuntimeError", "message": "SETUP_REQUIRED: live proof effects remain unreviewed"},
        ("secret_values_recorded" if kind == "series-a" else "credential_values_recorded"): False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--series-a")
    parser.add_argument("--gdw")
    parser.add_argument("--series-a-exit", type=int)
    parser.add_argument("--gdw-exit", type=int)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--blocked-proof", choices=("series-a", "gdw"))
    args = parser.parse_args(argv)
    if args.blocked_proof:
        report = blocked_proof_report(args.blocked_proof, args.source_sha)
    else:
        if args.series_a is None or args.gdw is None:
            parser.error("both prerequisite report paths are required")
        report = prerequisite_report(args.series_a, args.gdw, args.source_sha,
                                     args.series_a_exit, args.gdw_exit)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # There is deliberately no installed-authority consumer or enabling flag.
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
