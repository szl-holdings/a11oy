#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Retain bounded prerequisite evidence; metadata alone cannot authorize publication.

Publication is admitted only when BOTH check-only reports are READY with
``credential_authority_state: VERIFIED`` produced by the installed-authority
verifier (live runtime public key equal to the pinned runtime key), each with
exit code 0. Every other report -- UNKNOWN, forged, malformed, oversized,
duplicate-field or wrongly typed -- stays SETUP_REQUIRED and exits 1.
"""

import argparse
import json
import re
from pathlib import Path

MAX_REPORT_BYTES = 16 * 1024
SCHEMAS = {
    "series_a": "szl.hf-series-a-runtime-config/v1",
    "gdw": "szl.hf-gdw-runtime-config/v1",
}
AUTHORITY_SCHEMA = "szl.hf-installed-authority/v1"
# Independent copy of the pinned runtime key fingerprint (DER SHA-256) that
# scripts/verify_installed_authority.py checks against the committed pin.
PINNED_SIGNING_KEY_DER_SHA256 = "8e2d106c6995e11dbf7cbedfa9e5800bb50c82a635756e40dcd330364f6ea8ba"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def _verified_authority(report):
    authority = report.get("installed_authority")
    if type(authority) is not dict:
        return False
    signing = authority.get("signing")
    gdw = authority.get("gdw")
    return (
        authority.get("schema") == AUTHORITY_SCHEMA
        and authority.get("credential_authority_state") == "VERIFIED"
        and authority.get("diagnostic_code") == "INSTALLED_AUTHORITY_VERIFIED"
        and authority.get("public_variable_collision") is False
        and authority.get("signing_secret_name_present") is True
        and authority.get("secret_values_read") is False
        and authority.get("secret_values_written") is False
        and type(signing) is dict
        and signing.get("state") == "VERIFIED_PINNED_RUNTIME_KEY"
        and signing.get("served_fingerprint_sha256") == PINNED_SIGNING_KEY_DER_SHA256
        and signing.get("pinned_fingerprint_sha256") == PINNED_SIGNING_KEY_DER_SHA256
        and type(gdw) is dict
        and gdw.get("state") == "NAME_PRESENT_RUNTIME_PROVEN_DOWNSTREAM"
        and gdw.get("blocking") is False
    )


def inspect_report(path, schema, exit_code):
    # Do not echo arbitrary fields, provider errors, values, or supplied names.
    valid = False
    ready = False
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_REPORT_BYTES + 1)
        if len(raw) > MAX_REPORT_BYTES:
            raise ValueError("oversized report")
        report = json.loads(raw, object_pairs_hook=unique_object)
        common = (
            type(report) is dict
            and report.get("schema") == schema
            and report.get("repo_id") == "SZLHOLDINGS/a11oy"
            and report.get("secret_values_read") is False
            and report.get("secret_values_written") is False
            and type(exit_code) is int
        )
        valid = (
            common
            and report.get("state") == "SETUP_REQUIRED"
            and report.get("credential_authority_state") == "UNKNOWN"
            and report.get("converged") is False
            and exit_code == 1
        )
        ready = (
            common
            and not valid
            and report.get("state") == "READY"
            and report.get("credential_authority_state") == "VERIFIED"
            and report.get("diagnostic_code") == "INSTALLED_AUTHORITY_VERIFIED"
            and report.get("converged") is True
            and report.get("missing_secret_names") == []
            and exit_code == 0
            and _verified_authority(report)
        )
        valid = valid or ready
    except (OSError, ValueError, UnicodeError, RecursionError):
        valid = ready = False
    if ready:
        return {"report_valid": True, "state": "READY", "credential_authority_state": "VERIFIED"}
    return {"report_valid": valid, "state": "SETUP_REQUIRED",
            "credential_authority_state": "UNKNOWN"}


def prerequisite_report(series_a, gdw, source_sha, series_exit, gdw_exit):
    source_valid = type(source_sha) is str and re.fullmatch(r"[0-9a-f]{40}", source_sha) is not None
    series_result = inspect_report(series_a, SCHEMAS["series_a"], series_exit)
    gdw_result = inspect_report(gdw, SCHEMAS["gdw"], gdw_exit)
    ready = (source_valid
             and series_result == {"report_valid": True, "state": "READY", "credential_authority_state": "VERIFIED"}
             and gdw_result == {"report_valid": True, "state": "READY", "credential_authority_state": "VERIFIED"})
    return {
        "schema": "szl.hf-manual-prerequisites/v1",
        "repo_id": "SZLHOLDINGS/a11oy",
        "source_revision": source_sha if source_valid else "UNVALIDATED",
        "state": "READY" if ready else "SETUP_REQUIRED",
        "credential_authority_state": "VERIFIED" if ready else "UNKNOWN",
        "converged": ready,
        "source_revision_valid": source_valid,
        "series_a": series_result,
        "gdw": gdw_result,
        "secret_values_read": False,
        "secret_values_written": False,
        "diagnostic_code": "INSTALLED_AUTHORITY_VERIFIED" if ready else "INSTALLED_AUTHORITY_UNKNOWN",
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
    # Blocked live-proof reports always fail. The aggregate admits provider
    # writes only for two genuine READY/VERIFIED reports; there is no flag.
    if args.blocked_proof:
        return 1
    return 0 if report.get("state") == "READY" and report.get("converged") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
