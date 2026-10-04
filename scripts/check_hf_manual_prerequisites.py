#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Retain bounded prerequisite evidence; metadata alone cannot authorize publication.

Publication is admitted only when BOTH check-only reports are READY with
``credential_authority_state: VERIFIED`` produced by the installed-authority
verifier (live runtime public key equal to the pinned runtime key), each with
exit code 0. Every other report -- UNKNOWN, forged, malformed, oversized,
duplicate-field or wrongly typed -- stays SETUP_REQUIRED and exits 1.

``--admit-live-proofs`` consumes the two bounded post-deploy live-proof
reports (Series-A restart persistence, GDW write/drain/pinned receipt) and
exits 0 only when both are exact PASS reports with the reviewed bounds. The
retained ``--blocked-proof`` mode is still used by the standalone
``series-a-restart-proof.yml`` workflow and always exits 1.

Explicit ``--managed-acquisition`` additionally re-reads the immutable private
admission and each native dataset witness through the fixed reviewed helper.
Both proofs must bind the same source, qualification and database generations.
A managed configuration report cannot substitute for either live proof.
"""

import argparse
import importlib.util
import json
import re
import time
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


LIVE_PROOF_SCHEMAS = {
    "series_a": "szl.series-a-restart-proof/v1",
    "gdw": "szl.hf-gdw-live-proof/v1",
}
LIVE_PROOF_ADMISSION_SCHEMA = "szl.hf-live-proof-admission/v1"
CANONICAL_ORIGIN = "https://szlholdings-a11oy.hf.space"
PINNED_RUNTIME_KEY_PATH = "ayllu/keys/council-runtime-2026-07-21.pub"
SERIES_A_PROOF_FLAGS = (
    "source_stable", "activation_runtime_transition_observed", "runtime_boot_identity_changed",
    "public_signing_identity_stable", "database_instance_stable", "database_creation_identity_stable",
    "receipt_count_non_regressing", "pre_restart_chain_head_recovered", "activation_stop_the_world",
    "durability_stop_the_world", "writer_overlap_prevented", "running_stage_and_source_observed",
)


def _bounds_ok(value):
    return (
        type(value) is dict
        and value.get("max_attempts") == 8
        and value.get("retry_window_seconds") == 600
        and type(value.get("deadline_seconds")) is int
        and 1 <= value["deadline_seconds"] <= 1200
        and value.get("transient_http_statuses") == [429, 502, 503, 504]
        and value.get("redirects_allowed") is False
        and value.get("destinations") == [CANONICAL_ORIGIN,
                                          "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy"]
    )


def _series_a_passed(report):
    proof = report.get("proof")
    running = report.get("durability_running")
    effects = report.get("effects")
    return (
        report.get("secret_values_read") is False
        and report.get("secret_values_recorded") is False
        and type(proof) is dict
        and all(proof.get(flag) is True for flag in SERIES_A_PROOF_FLAGS)
        and type(running) is dict
        and running.get("stage") == "RUNNING"
        and running.get("git_sha") == report.get("source_revision")
        and type(effects) is list
        and 1 <= len(effects) <= 8
        and all(type(item) is dict and item.get("repo_id") == "SZLHOLDINGS/a11oy"
                and item.get("effect") in {"pause_space", "restart_space"} for item in effects)
    )


def _gdw_passed(report):
    evidence = report.get("evidence")
    receipt = evidence.get("signed_receipt") if type(evidence) is dict else None
    return (
        report.get("credential_values_recorded") is False
        and report.get("namespace") == "a11oy"
        and type(evidence) is dict
        and evidence.get("namespace") == "a11oy"
        and type(receipt) is dict
        and receipt.get("namespace") == "a11oy"
        and receipt.get("receipt_status") == "SIGNED_KHIPU_DSSE"
        and receipt.get("signature_verified") is True
        and receipt.get("verified_against") == PINNED_RUNTIME_KEY_PATH
        and receipt.get("pinned_key_der_sha256") == PINNED_SIGNING_KEY_DER_SHA256
    )


def load_managed_proof_context(receipt_path, *, source_revision, deadline):
    """Fixed sibling performs actual immutable dataset/admission readback."""
    path = Path(__file__).resolve().with_name("configure_hf_gdw_runtime.py")
    spec = importlib.util.spec_from_file_location("_hf_aggregate_managed_context", path)
    if spec is None or spec.loader is None:
        raise ValueError("managed admission is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_managed_proof_context(receipt_path, source_revision=source_revision,
                                            deadline=deadline)


def _managed_proof_binding(report, kind, context):
    payload = report if kind == "series_a" else report.get("evidence")
    present = (type(payload) is dict and any(key in payload for key in
               ("managed_identity", "managed_admission")))
    if context is None:
        return not present
    try:
        identity = context.identity
        if (not present or type(payload.get("managed_identity")) is not dict
                or payload["managed_identity"] != identity
                or report.get("source_revision") != identity["source_revision"]):
            return False
        generation = identity["generations"][kind]
        witness = context.validate(payload.get("managed_admission"), label=kind, generation=generation)
        if kind == "gdw":
            return (payload.get("database_generation_id") == generation
                    and payload.get("runtime_source_revision") == identity["source_revision"])
        # The top-level witness must be the exact final observation, and both
        # sides of the restart retain the admitted generation and native HEAD.
        for name in ("before", "after"):
            captured = report.get(name)
            storage = captured.get("storage") if type(captured) is dict else None
            if (type(storage) is not dict or storage.get("instance_id") != generation
                    or captured.get("source_revision") != identity["source_revision"]):
                return False
            observed = context.validate(storage.get("managed_admission"), label=kind, generation=generation)
            if name == "after" and observed != witness:
                return False
        return True
    except Exception:
        return False


def inspect_live_proof(path, kind, exit_code, source_sha, *, managed_context=None):
    """Admit one live-proof report only when it is a bounded, exact PASS."""
    passed = False
    valid = False
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_REPORT_BYTES + 1)
        if len(raw) > MAX_REPORT_BYTES:
            raise ValueError("oversized report")
        report = json.loads(raw, object_pairs_hook=unique_object)
        valid = (
            type(report) is dict
            and report.get("schema") == LIVE_PROOF_SCHEMAS[kind]
            and report.get("repo_id") == "SZLHOLDINGS/a11oy"
            and type(exit_code) is int
            and type(report.get("ok")) is bool
            and report.get("status") in {"PASS", "FAIL"}
        )
        passed = (
            valid
            and exit_code == 0
            and report.get("status") == "PASS"
            and report.get("ok") is True
            and report.get("state") == "PROVEN"
            and report.get("diagnostic_code") == "LIVE_PROOF_PASSED"
            and report.get("origin") == CANONICAL_ORIGIN
            and report.get("source_revision") == source_sha
            and report.get("credential_authority_state") == "VERIFIED"
            and _bounds_ok(report.get("bounds"))
            and (_series_a_passed(report) if kind == "series_a" else _gdw_passed(report))
            and _managed_proof_binding(report, kind, managed_context)
        )
    except (OSError, ValueError, UnicodeError, RecursionError, KeyError, TypeError):
        valid = passed = False
    return {"report_valid": bool(valid), "state": "PROVEN" if passed else "UNPROVEN"}


def live_proof_admission(series_a, gdw, source_sha, series_exit, gdw_exit, *, managed_context=None):
    source_valid = (type(source_sha) is str and re.fullmatch(r"[0-9a-f]{40}", source_sha) is not None
                    and source_sha != "0" * 40)
    series_result = inspect_live_proof(series_a, "series_a", series_exit, source_sha,
                                       managed_context=managed_context)
    gdw_result = inspect_live_proof(gdw, "gdw", gdw_exit, source_sha, managed_context=managed_context)
    admitted = (source_valid and series_result["state"] == "PROVEN"
                and gdw_result["state"] == "PROVEN")
    return {
        "schema": LIVE_PROOF_ADMISSION_SCHEMA,
        "repo_id": "SZLHOLDINGS/a11oy",
        "source_revision": source_sha if source_valid else "UNVALIDATED",
        "state": "ADMITTED" if admitted else "NOT_ADMITTED",
        "admitted": admitted,
        "source_revision_valid": source_valid,
        "series_a": series_result,
        "gdw": gdw_result,
        "secret_values_read": False,
        "secret_values_written": False,
        "diagnostic_code": "LIVE_PROOFS_ADMITTED" if admitted else "LIVE_PROOFS_UNPROVEN",
        **({"managed_identity": managed_context.identity} if admitted and managed_context is not None else {}),
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
    parser.add_argument("--admit-live-proofs", action="store_true")
    parser.add_argument("--series-a-proof")
    parser.add_argument("--gdw-proof")
    parser.add_argument("--series-a-proof-exit", type=int)
    parser.add_argument("--gdw-proof-exit", type=int)
    parser.add_argument("--managed-acquisition", type=Path)
    parser.add_argument("--managed-deadline-seconds", type=float, default=120)
    args = parser.parse_args(argv)
    if args.managed_acquisition is not None and not args.admit_live_proofs:
        parser.error("managed acquisition is valid only with actual live proof admission")
    if args.admit_live_proofs:
        if args.blocked_proof or args.series_a_proof is None or args.gdw_proof is None:
            parser.error("live proof admission requires both proof report paths")
        context = None
        try:
            if args.managed_acquisition is not None:
                if not 0 < args.managed_deadline_seconds <= 120:
                    raise ValueError("managed deadline is invalid")
                deadline = time.monotonic() + args.managed_deadline_seconds
                context = load_managed_proof_context(args.managed_acquisition,
                    source_revision=args.source_sha, deadline=deadline)
            report = live_proof_admission(args.series_a_proof, args.gdw_proof, args.source_sha,
                args.series_a_proof_exit, args.gdw_proof_exit, managed_context=context)
            if context is not None and time.monotonic() >= deadline:
                raise ValueError("managed deadline expired")
        except Exception:
            # Never fall back to legacy admission after an explicit managed
            # provider/record failure, or persist provider exception details.
            report = live_proof_admission(None, None, args.source_sha, 1, 1)
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception:
                    report = live_proof_admission(None, None, args.source_sha, 1, 1)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0 if report["admitted"] is True else 1
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
