#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Qualify logical continuity of disposable candidates from a verified capture.

This helper has no provider mutation or restoration capability. It downloads
only exact preserved content identities, never opens captured originals with
SQLite, and never imports a runtime constructor. Candidate qualification is
not deployment admission, proof of prior completeness, or a storage contract.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import re
import shutil
import signal
import sqlite3
import stat
import struct
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import preserve_hf_gdw_store as preservation
import gdw_orphan_forensics as orphan_forensics

SCHEMA = "szl.gdw-store-recovery-qualification/v1"
DEADLINE_SECONDS = 90
MAX_REFERENCE_BYTES = 1024 * 1024
MAX_ROWS = 1_000_000
MAX_ROW_BYTES = 16 * 1024 * 1024
MAX_LOGICAL_BYTES = 1024 * 1024 * 1024
MAX_INTEGRITY_ERRORS = 100
INTERNAL_TABLES = {"sqlite_sequence", "sqlite_stat1", "sqlite_stat4"}
SERIES_RECEIPT_TYPE = "application/vnd.szl.series-a-receipt.v1+json"
HISTORICAL_SCHEMA = "szl.gdw-recovery-historical-anchors/v1"
PINNED_KEY_PATH = "ayllu/keys/council-runtime-2026-07-21.pub"
PINNED_KEY_DER_SHA256 = "8e2d106c6995e11dbf7cbedfa9e5800bb50c82a635756e40dcd330364f6ea8ba"
ROOT = Path(__file__).resolve().parents[1]
KHIPU_RECEIPT_TYPE = "application/vnd.szl.khipu+json"
AUDIT_PAYLOAD_FIELDS = {
    "schema", "operator", "recovery_id", "source_revision", "database_generation_id",
    "request_sha256", "outcome_sha256", "governance_sha256", "selection_sha256",
    "rescheduled_effects", "attempts_before", "attempts_after", "sequence",
    "previous_receipt_sha256", "previous_chain_sha256", "atomic_with_mutation",
    "created_at", "credential_values_recorded",
}
AUDIT_OUTCOME_FIELDS = {
    "schema", "status", "recovery_id", "source_revision", "requested_limit", "failure_class",
    "database_generation_id", "inspected_pending_effects", "eligible_effects", "rescheduled_effects",
    "attempts_before", "attempts_after", "selection", "selection_sha256", "sqlite_integrity",
    "claimed_effects", "dead_letter_effects", "invalid_effect_bindings", "invalid_exported_artifacts",
    "invalid_recovery_audits", "credential_values_recorded",
}


class RecoveryError(RuntimeError):
    def __init__(self, code: str):
        self.code = code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code) else "QUALIFICATION_UNAVAILABLE"
        super().__init__(self.code)


def check_budget(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise RecoveryError("QUALIFICATION_DEADLINE_EXHAUSTED")


def _json(data: bytes | str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise RecoveryError("JSON_DUPLICATE_KEY")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=unique,
                          parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()))
    except RecoveryError:
        raise
    except Exception:
        raise RecoveryError("JSON_UNAVAILABLE") from None


def _bounded_file(path: Path, limit: int, code: str) -> bytes:
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
            raise RecoveryError(code + "_BOUND_EXCEEDED")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            data = handle.read(limit + 1)
        if len(data) > limit:
            raise RecoveryError(code + "_BOUND_EXCEEDED")
        return data
    except RecoveryError:
        raise
    except Exception:
        raise RecoveryError(code + "_UNAVAILABLE") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_reference_bytes(path: Path) -> tuple[dict, bytes]:
    data = _bounded_file(path, MAX_REFERENCE_BYTES, "CAPTURE_REFERENCE")
    value = _json(data)
    if not isinstance(value, dict):
        raise RecoveryError("CAPTURE_REFERENCE_INVALID")
    return value, data


def read_reference(path: Path) -> dict:
    return read_reference_bytes(path)[0]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _native_digest(value: Any) -> str:
    # GDW's stored hashes use its original ASCII-escaped JSON encoding; DSSE
    # payload bytes and Series-A receipts use the UTF-8 encoding above.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode("utf-8")).hexdigest()


def _digest(value: Any, length: int = 64) -> bool:
    return type(value) is str and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None \
        and value != "0" * length


def validate_historical_anchors(anchors: dict, reference: dict, capture_report_sha256: str) -> None:
    """Bind the source-reviewed historical artifact to the exact capture file."""
    expected_fields = {"schema", "source_repository", "source_revision", "workflow_run_id",
                       "workflow_attempt", "artifact_id", "artifact_archive_sha256",
                       "capture_report_sha256", "gdw", "series_a", "scope"}
    if (type(anchors) is not dict or set(anchors) != expected_fields
            or anchors.get("schema") != HISTORICAL_SCHEMA
            or anchors.get("source_repository") != "szl-holdings/a11oy"
            or not _digest(anchors.get("source_revision"), 40)
            or any(type(anchors.get(key)) is not int or not 1 <= anchors[key] < 10**20
                   for key in ("workflow_run_id", "workflow_attempt", "artifact_id"))
            or not _digest(anchors.get("artifact_archive_sha256"))
            or type(anchors.get("scope")) is not str or not 1 <= len(anchors["scope"]) <= 200):
        raise RecoveryError("HISTORICAL_ANCHORS_INVALID")
    if not _digest(capture_report_sha256) or anchors.get("capture_report_sha256") != capture_report_sha256:
        raise RecoveryError("HISTORICAL_CAPTURE_BINDING_INVALID")
    gdw, series = anchors.get("gdw"), anchors.get("series_a")
    if (type(gdw) is not dict or set(gdw) != {"proof_sha256", "database_generation_id", "namespace",
            "owner_id", "recovery_id", "sequence", "receipt_sha256", "chain_sha256",
            "pinned_key_der_sha256", "pinned_key_path"}
            or type(series) is not dict or set(series) != {"proof_sha256", "database_generation_id",
            "storage_created_at", "sequence", "minimum_receipt_count", "receipt_sha256"}):
        raise RecoveryError("HISTORICAL_ANCHORS_INVALID")
    if (gdw.get("namespace") != "a11oy" or gdw.get("owner_id") != "gdw-operator"
            or type(gdw.get("recovery_id")) is not str
            or re.fullmatch(r"gdw-proof-[0-9a-f]{12}-[0-9a-f]{12}-[1-9][0-9]{0,5}", gdw["recovery_id"]) is None
            or gdw.get("pinned_key_path") != PINNED_KEY_PATH
            or gdw.get("pinned_key_der_sha256") != PINNED_KEY_DER_SHA256
            or not _digest(gdw.get("chain_sha256"))
            or type(series.get("storage_created_at")) is not str
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z",
                            series["storage_created_at"]) is None
            or type(series.get("minimum_receipt_count")) is not int
            or not 1 <= series["minimum_receipt_count"] <= MAX_ROWS):
        raise RecoveryError("HISTORICAL_ANCHORS_INVALID")
    for label, anchor in (("gdw", gdw), ("series_a", series)):
        pattern = r"[0-9a-f]{32}" if label == "gdw" else r"store_[0-9a-f]{32}"
        if (not _digest(anchor.get("proof_sha256")) or not _digest(anchor.get("receipt_sha256"))
                or type(anchor.get("sequence")) is not int or not 0 <= anchor["sequence"] <= MAX_ROWS
                or type(anchor.get("database_generation_id")) is not str
                or re.fullmatch(pattern, anchor["database_generation_id"]) is None):
            raise RecoveryError("HISTORICAL_ANCHORS_INVALID")
        expected = reference.get("databases", {}).get(label, {}).get("database_generation_id")
        if anchor["database_generation_id"] != expected:
            raise RecoveryError("HISTORICAL_CAPTURE_GENERATION_MISMATCH")
    if gdw["recovery_id"].split("-")[2:4] != [anchors["source_revision"][:12], gdw["database_generation_id"][:12]] \
            or series["sequence"] < 1:
        raise RecoveryError("HISTORICAL_ANCHORS_INVALID")


def _framed(value: Any) -> bytes:
    # Type and length framing distinguish NULL, TEXT, BLOB, integers and IEEE
    # floating-point values. No text normalization or JSON reserialization of
    # stored payloads is allowed in the logical continuity digest.
    if value is None:
        kind, payload = b"N", b""
    elif type(value) is int:
        kind, payload = b"I", str(value).encode("ascii")
    elif type(value) is float:
        kind, payload = b"F", struct.pack(">d", value)
    elif type(value) is str:
        kind, payload = b"T", value.encode("utf-8")
    elif type(value) is bytes:
        kind, payload = b"B", value
    else:
        raise RecoveryError("SQLITE_VALUE_TYPE_UNAVAILABLE")
    if len(payload) > MAX_ROW_BYTES:
        raise RecoveryError("SQLITE_ROW_BOUND_EXCEEDED")
    return kind + len(payload).to_bytes(8, "big") + payload


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def readonly(database: Path, deadline: float) -> sqlite3.Connection:
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2)
    connection.enable_load_extension(False)
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_ROW_BYTES)
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("PRAGMA query_only=ON")
    connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    return connection


def logical_fingerprint(connection: sqlite3.Connection, label: str, deadline: float) -> dict:
    schema = connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name,sql"
    ).fetchmany(1001)
    if len(schema) > 1000:
        raise RecoveryError("SQLITE_SCHEMA_BOUND_EXCEEDED")
    tables = {row[1] for row in schema if row[0] == "table"}
    expected = set(preservation.TABLES[label])
    if tables - INTERNAL_TABLES != expected:
        raise RecoveryError("UNQUALIFIED_STORE_SCHEMA")
    if any(row[0] == "table" and (not row[3] or not re.match(r"CREATE\s+TABLE\b", row[3], re.I))
           for row in schema):
        raise RecoveryError("UNQUALIFIED_STORE_SCHEMA")
    total_rows = total_bytes = 0
    reports = {}
    for table in sorted(tables):
        check_budget(deadline)
        columns = connection.execute(f"PRAGMA table_xinfo({_quote(table)})").fetchall()
        # Generated columns have no independently stored value. Reject them
        # until a reviewed schema contract explicitly describes their semantics.
        if not columns or any(row[6] != 0 for row in columns):
            raise RecoveryError("UNQUALIFIED_STORE_SCHEMA")
        if table in expected and not any(row[5] > 0 for row in columns):
            # VACUUM may change hidden rowids. Application identity must be
            # represented by declared keys that this fingerprint preserves.
            raise RecoveryError("UNQUALIFIED_STORE_SCHEMA")
        names = [row[1] for row in columns]
        hashes = []
        for row in connection.execute("SELECT " + ",".join(_quote(name) for name in names)
                                      + " FROM " + _quote(table)):
            check_budget(deadline)
            total_rows += 1
            if total_rows > MAX_ROWS:
                raise RecoveryError("SQLITE_ROW_COUNT_BOUND_EXCEEDED")
            encoded = b"".join(_framed(value) for value in row)
            total_bytes += len(encoded)
            if len(encoded) > MAX_ROW_BYTES or total_bytes > MAX_LOGICAL_BYTES:
                raise RecoveryError("SQLITE_LOGICAL_SIZE_BOUND_EXCEEDED")
            hashes.append(hashlib.sha256(encoded).digest())
        # The multiset includes duplicate rows while ignoring physical page
        # layout and hidden rowids; the current schemas use declared keys.
        digest = hashlib.sha256()
        digest.update(_canonical(names))
        for row_hash in sorted(hashes):
            digest.update(row_hash)
        reports[table] = {"row_count": len(hashes), "rows_sha256": digest.hexdigest(),
                          "columns_sha256": hashlib.sha256(_canonical(columns)).hexdigest()}
    result = {"schema_sha256": hashlib.sha256(_canonical(schema)).hexdigest(),
              "tables": reports, "row_count": total_rows,
              "user_version": connection.execute("PRAGMA user_version").fetchone()[0],
              "application_id": connection.execute("PRAGMA application_id").fetchone()[0]}
    result["logical_sha256"] = hashlib.sha256(_canonical(result)).hexdigest()
    return result


def generation(connection: sqlite3.Connection, label: str) -> str:
    if label == "gdw":
        rows = connection.execute(
            "SELECT schema_version,database_generation_id FROM schema_meta WHERE schema_name='gdw'"
        ).fetchmany(2)
        if len(rows) != 1 or rows[0][0] != 4 or not isinstance(rows[0][1], str) \
                or preservation.GENERATION.fullmatch(rows[0][1]) is None:
            raise RecoveryError("STORE_GENERATION_UNAVAILABLE")
        return rows[0][1]
    rows = connection.execute("SELECT value FROM metadata WHERE key='storage_instance_id'").fetchmany(2)
    if len(rows) != 1 or not isinstance(rows[0][0], str) or re.fullmatch(r"store_[0-9a-f]{32}", rows[0][0]) is None:
        raise RecoveryError("STORE_GENERATION_UNAVAILABLE")
    return rows[0][0]


def integrity(connection: sqlite3.Connection, *, unreferenced_pages: list[int] | None = None) -> dict:
    results = [row[0] for row in connection.execute(f"PRAGMA integrity_check({MAX_INTEGRITY_ERRORS})")]
    complete = True
    pages = []
    if results == ["ok"]:
        classification = "OK"
    else:
        lines = [line for value in results for line in value.splitlines()
                 if line != "*** in database main ***"]
        # SQLite may combine many findings in one row. A saturated diagnostic
        # cannot establish that every integrity error is an unreferenced page.
        complete = len(lines) < MAX_INTEGRITY_ERRORS
        matches = [re.fullmatch(r"Page ([0-9]+): never used", line) for line in lines]
        if not complete:
            classification = "INTEGRITY_RESULT_INCOMPLETE"
        elif matches and all(matches):
            classification = "UNREFERENCED_PAGES"
            pages = [int(match.group(1)) for match in matches]
        else:
            classification = "OTHER_SQLITE_INTEGRITY_ERROR"
    if unreferenced_pages is not None:
        unreferenced_pages.extend(pages)
    violations = connection.execute("PRAGMA foreign_key_check").fetchmany(1001)
    return {"classification": classification,
            "integrity_check_complete": complete, "unreferenced_page_count": len(pages),
            "result_sha256": hashlib.sha256(_canonical(results)).hexdigest(),
            "foreign_key_violation_count": min(len(violations), 1000),
            "foreign_key_check_complete": len(violations) < 1001}


def unreferenced_page_contents(database: Path, pages: list[int], deadline: float) -> dict:
    """Inspect only bounded orphan pages in the disposable copy; expose no bytes."""
    if (not pages or len(pages) >= MAX_INTEGRITY_ERRORS
            or any(type(page) is not int for page in pages) or len(set(pages)) != len(pages)):
        raise RecoveryError("UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW")
    descriptor = os.open(database, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > preservation.MAX_FILE_BYTES:
            raise RecoveryError("UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW")
        header = os.read(descriptor, 100)
        if len(header) != 100 or header[:16] != b"SQLite format 3\x00":
            raise RecoveryError("UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW")
        page_size = int.from_bytes(header[16:18], "big")
        page_size = 65536 if page_size == 1 else page_size
        page_count = int.from_bytes(header[28:32], "big")
        if (not 512 <= page_size <= 65536 or page_size & (page_size - 1)
                or metadata.st_size != page_count * page_size
                or any(not 1 <= page <= page_count for page in pages)):
            raise RecoveryError("UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW")
        digest = hashlib.sha256()
        all_zero = True
        for page in sorted(pages):
            check_budget(deadline)
            os.lseek(descriptor, (page - 1) * page_size, os.SEEK_SET)
            contents = os.read(descriptor, page_size)
            if len(contents) != page_size:
                raise RecoveryError("UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW")
            digest.update(page.to_bytes(8, "big"))
            digest.update(contents)
            all_zero = all_zero and not any(contents)
        check_budget(deadline)
        return {"page_count": len(pages), "byte_count": len(pages) * page_size,
                "contents_sha256": digest.hexdigest(), "all_zero": all_zero}
    finally:
        os.close(descriptor)


def orphan_forensic_observation(database: Path, pages: list[int], deadline: float,
                               expected_sha256: str, contents: dict) -> dict:
    """Bind descriptive evidence to the same bytes without changing admission."""
    report = orphan_forensics.inspect_orphan_pages(database, pages, deadline=deadline)
    held_fields = {"schema", "state", "analysis_state", "diagnostic_code", "hold_reason",
                   "candidate_created", "discard_admitted", "restore_admitted", "deployment_admitted",
                   "provider_writes_performed", "private_payloads_emitted", "record_comparison",
                   "record_equivalence_verified", "all_bytes_semantically_explained"}
    observed_fields = {"inspection_sha256", "database_header", "orphan_page_count", "orphan_byte_count",
                       "orphan_contents_sha256", "pages", "native_reachability", "companions",
                       "inspection_copy_unchanged"}
    if (type(report) is not dict or not held_fields <= set(report)
            or set(report) - held_fields - observed_fields
            or report["schema"] != "szl.gdw-orphan-page-forensics/v1"
            or report["state"] != "HELD" or report["hold_reason"] != "UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW"
            or report["analysis_state"] not in {"COMPLETE", "PARTIAL", "UNAVAILABLE"}
            or report["record_comparison"] != "UNAVAILABLE"
            or any(report[key] is not False for key in (
                "candidate_created", "discard_admitted", "restore_admitted", "deployment_admitted",
                "provider_writes_performed", "private_payloads_emitted", "record_equivalence_verified",
                "all_bytes_semantically_explained"))):
        raise RecoveryError("ORPHAN_FORENSIC_RESULT_UNQUALIFIED")
    if report["analysis_state"] == "UNAVAILABLE":
        if set(report) != held_fields:
            raise RecoveryError("ORPHAN_FORENSIC_RESULT_UNQUALIFIED")
    elif (set(report) != held_fields | observed_fields or report["inspection_sha256"] != expected_sha256
            or report["orphan_contents_sha256"] != contents["contents_sha256"]
            or type(report["orphan_page_count"]) is not int
            or report["orphan_page_count"] != contents["page_count"]
            or type(report["orphan_byte_count"]) is not int
            or report["orphan_byte_count"] != contents["byte_count"]
            or report["inspection_copy_unchanged"] is not True):
        raise RecoveryError("ORPHAN_FORENSIC_INPUT_IDENTITY_MISMATCH")
    check_budget(deadline)
    return report


def _bindings_match(value: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    return all(key in value and type(value[key]) is type(item) and value[key] == item
               for key, item in expected.items())


def _verify_anchor_envelope(envelope: dict, payload: dict, deadline: float) -> dict:
    """Verify with one source-pinned public key, without any signer imports."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        check_budget(deadline)
        if (type(envelope) is not dict or envelope.get("signed") is not True
                or envelope.get("payloadType") != KHIPU_RECEIPT_TYPE
                or type(envelope.get("signatures")) is not list or len(envelope["signatures"]) != 1
                or type(envelope["signatures"][0]) is not dict):
            raise RecoveryError("HISTORICAL_SIGNATURE_INVALID")
        body = base64.b64decode(envelope["payload"], validate=True)
        signature = base64.b64decode(envelope["signatures"][0]["sig"], validate=True)
        if body != _canonical(payload) or not 1 <= len(signature) <= 256:
            raise RecoveryError("HISTORICAL_SIGNATURE_PAYLOAD_INVALID")
        pem = _bounded_file(ROOT / PINNED_KEY_PATH, 4096, "HISTORICAL_PUBLIC_KEY")
        public_key = serialization.load_pem_public_key(pem)
        if not isinstance(public_key, ec.EllipticCurvePublicKey) or public_key.curve.name != "secp256r1":
            raise RecoveryError("HISTORICAL_PUBLIC_KEY_INVALID")
        der = public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        if hashlib.sha256(der).hexdigest() != PINNED_KEY_DER_SHA256:
            raise RecoveryError("HISTORICAL_PUBLIC_KEY_PIN_MISMATCH")
        ptype = KHIPU_RECEIPT_TYPE.encode("ascii")
        pae = b"DSSEv1 " + str(len(ptype)).encode() + b" " + ptype + b" " \
            + str(len(body)).encode() + b" " + body
        public_key.verify(signature, pae, ec.ECDSA(hashes.SHA256()))
        payload_sha256 = hashlib.sha256(body).hexdigest()
        check_budget(deadline)
        return {"signature_verification": "VERIFIED_PINNED_PUBLIC_KEY",
                "pinned_key_der_sha256": PINNED_KEY_DER_SHA256,
                "payload_sha256": payload_sha256}
    except RecoveryError:
        raise
    except Exception:
        raise RecoveryError("HISTORICAL_SIGNATURE_INVALID") from None


def historical_anchor(connection: sqlite3.Connection, label: str, store_generation: str,
                      anchors: dict | None, deadline: float) -> dict:
    if anchors is None:
        return {"state": "NOT_CHECKED", "signature_verification": "NOT_PERFORMED"}
    check_budget(deadline)
    anchor = anchors[label]
    if anchor["database_generation_id"] != store_generation:
        raise RecoveryError("HISTORICAL_GENERATION_MISMATCH")
    if label == "series_a":
        created = connection.execute("SELECT value FROM metadata WHERE key='storage_created_at'").fetchmany(2)
        count = connection.execute("SELECT count(*) FROM receipts").fetchone()[0]
        rows = connection.execute("SELECT sequence,receipt_hash FROM receipts WHERE sequence=?",
                                  (anchor["sequence"],)).fetchmany(2)
        if (created != [(anchor["storage_created_at"],)] or count < anchor["minimum_receipt_count"]
                or len(rows) != 1 or type(rows[0][0]) is not int
                or rows[0] != (anchor["sequence"], anchor["receipt_sha256"])):
            raise RecoveryError("HISTORICAL_SERIES_A_ANCHOR_MISMATCH")
        check_budget(deadline)
        return {"state": "VERIFIED", "sequence": anchor["sequence"], "receipt_count": count,
                "minimum_receipt_count": anchor["minimum_receipt_count"],
                "receipt_sha256": anchor["receipt_sha256"], "generation_unchanged": True,
                "storage_created_at_unchanged": True, "signature_verification": "NOT_PERFORMED"}
    columns = ("namespace", "owner_id", "recovery_id", "sequence", "credential_key_id",
               "database_generation_id", "request_sha256", "outcome_sha256", "governance_sha256",
               "receipt_sha256", "previous_receipt_sha256", "previous_chain_sha256", "chain_sha256",
               "dsse_envelope_sha256", "report_json", "created_at")
    rows = connection.execute("SELECT " + ",".join(columns) + " FROM effect_recovery_audit "
                              "WHERE namespace=? AND owner_id=? AND recovery_id=?",
                              (anchor["namespace"], anchor["owner_id"], anchor["recovery_id"])).fetchmany(2)
    if len(rows) != 1:
        raise RecoveryError("HISTORICAL_GDW_ANCHOR_MISSING")
    row = dict(zip(columns, rows[0]))
    if (not _bindings_match(row, {key: anchor[key] for key in (
            "namespace", "owner_id", "recovery_id", "sequence", "database_generation_id",
            "receipt_sha256", "chain_sha256")}) or type(row["credential_key_id"]) is not str
            or not 1 <= len(row["credential_key_id"]) <= 256 or type(row["created_at"]) is not str):
        raise RecoveryError("HISTORICAL_GDW_ANCHOR_MISMATCH")
    report = _json(row["report_json"])
    if (type(report) is not dict or set(report) != AUDIT_OUTCOME_FIELDS | {"governance", "audit_receipt", "replayed"}
            or type(report.get("governance")) is not dict or type(report.get("audit_receipt")) is not dict
            or report.get("replayed") is not False):
        raise RecoveryError("HISTORICAL_AUDIT_REPORT_INVALID")
    outcome = {key: report[key] for key in AUDIT_OUTCOME_FIELDS}
    receipt = report["audit_receipt"]
    if set(receipt) != AUDIT_PAYLOAD_FIELDS | {"receipt_status", "receipt_sha256", "dsse_envelope_sha256",
                                             "chain_sha256", "dsse_envelope"}:
        raise RecoveryError("HISTORICAL_AUDIT_REPORT_INVALID")
    payload = {key: receipt[key] for key in AUDIT_PAYLOAD_FIELDS}
    count_fields = ("requested_limit", "inspected_pending_effects", "eligible_effects", "rescheduled_effects",
                    "attempts_before", "attempts_after", "claimed_effects", "dead_letter_effects",
                    "invalid_effect_bindings", "invalid_exported_artifacts", "invalid_recovery_audits")
    expected_outcome = {"schema": "szl.gdw.transient-effect-recovery/v2", "recovery_id": row["recovery_id"],
                        "source_revision": anchors["source_revision"], "database_generation_id": store_generation,
                        "failure_class": "hf-hard-link-enotsup/v1", "sqlite_integrity": "ok",
                        "credential_values_recorded": False}
    if (not _bindings_match(outcome, expected_outcome)
            or any(type(outcome[key]) is not int or outcome[key] < 0 for key in count_fields)
            or not 1 <= outcome["requested_limit"] <= 1000
            or type(outcome["selection"]) is not list
            or _native_digest(outcome["selection"]) != outcome["selection_sha256"]
            or _native_digest(outcome) != row["outcome_sha256"]
            or _native_digest(report["governance"]) != row["governance_sha256"]):
        raise RecoveryError("HISTORICAL_AUDIT_REPORT_BINDING_INVALID")
    request = {"schema": "szl.gdw.transient-effect-recovery-request/v1",
               **{key: row[key] for key in ("namespace", "owner_id", "credential_key_id", "recovery_id",
                                            "database_generation_id")},
               "source_revision": anchors["source_revision"], "limit": outcome["requested_limit"],
               "failure_class": outcome["failure_class"],
               "governance_binding_sha256": report["governance"].get("binding_sha256")}
    expected_receipt = {key: row[key] for key in ("recovery_id", "database_generation_id", "sequence",
                         "request_sha256", "outcome_sha256", "governance_sha256", "receipt_sha256",
                         "previous_receipt_sha256", "previous_chain_sha256", "chain_sha256",
                         "dsse_envelope_sha256", "created_at")}
    expected_receipt.update(schema="szl.gdw.transient-effect-recovery-receipt/v2",
                            source_revision=anchors["source_revision"], atomic_with_mutation=True,
                            credential_values_recorded=False, receipt_status="SIGNED_KHIPU_DSSE")
    expected_receipt.update({key: outcome[key] for key in (
        "selection_sha256", "rescheduled_effects", "attempts_before", "attempts_after")})
    operator = {key: row[key] for key in ("namespace", "owner_id", "credential_key_id")}
    if (not _bindings_match(receipt, expected_receipt) or _canonical(receipt["operator"]) != _canonical(operator)
            or _native_digest(request) != row["request_sha256"]
            or not _digest(request["governance_binding_sha256"])
            or _native_digest(payload) != row["receipt_sha256"]
            or _native_digest(receipt["dsse_envelope"]) != row["dsse_envelope_sha256"]
            or _native_digest({key: receipt[key] for key in ("previous_chain_sha256", "receipt_sha256",
                                                           "receipt_status", "dsse_envelope_sha256")}) != row["chain_sha256"]):
        raise RecoveryError("HISTORICAL_AUDIT_RECEIPT_BINDING_INVALID")
    verified = _verify_anchor_envelope(receipt["dsse_envelope"], payload, deadline)
    check_budget(deadline)
    return {"state": "VERIFIED", "sequence": anchor["sequence"],
            "receipt_sha256": anchor["receipt_sha256"], "chain_sha256": anchor["chain_sha256"],
            "generation_unchanged": True, "audit_scope_unchanged": True,
            "report_payload_bindings_verified": True, **verified}


def receipt_continuity(connection: sqlite3.Connection, label: str, store_generation: str,
                       deadline: float) -> dict:
    counts = {"row_count": 0, "digest_errors": 0, "binding_errors": 0,
              "chain_link_errors": 0, "tombstoned_receipts": 0}
    if label == "gdw":
        for ns, owner, request, session, step, payload, claimed in connection.execute(
                "SELECT namespace,owner_id,request_id,session_id,step,receipt_json,receipt_hash FROM receipts"):
            check_budget(deadline)
            counts["row_count"] += 1
            if payload is None:
                counts["tombstoned_receipts"] += 1
                continue
            value = _json(payload)
            if not isinstance(value, dict):
                raise RecoveryError("RECEIPT_SHAPE_UNAVAILABLE")
            unsigned = dict(value)
            unsigned.pop("receipt_hash", None)
            observed = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"),
                                                allow_nan=False).encode()).hexdigest()
            if claimed != observed or value.get("receipt_hash") != claimed:
                counts["digest_errors"] += 1
            expected = {"namespace": ns, "owner_id": owner, "request_id": request,
                        "session_id": session, "step": step, "database_generation_id": store_generation}
            if not _bindings_match(value, expected):
                counts["binding_errors"] += 1
        counts["signature_verification"] = "NOT_PERFORMED"
        return counts
    previous = "0" * 64
    last_sequence = 0
    counts.update(signed_envelopes=0, unsigned_envelopes=0)
    for sequence, receipt_id, kind, payload, envelope, prior, claimed, created in connection.execute(
            "SELECT sequence,receipt_id,kind,payload,envelope,previous_hash,receipt_hash,created_at "
            "FROM receipts ORDER BY sequence"):
        check_budget(deadline)
        counts["row_count"] += 1
        value, signed = _json(payload), _json(envelope)
        if (not isinstance(value, dict) or not isinstance(signed, dict)
                or type(sequence) is not int or sequence <= last_sequence
                or not isinstance(claimed, str) or preservation.HEX64.fullmatch(claimed) is None):
            raise RecoveryError("RECEIPT_SHAPE_UNAVAILABLE")
        if hashlib.sha256(_canonical(signed)).hexdigest() != claimed:
            counts["digest_errors"] += 1
        if prior != previous or not _bindings_match(value, {"previous_receipt_hash": prior}):
            counts["chain_link_errors"] += 1
        try:
            encoded_payload = base64.b64decode(signed.get("payload", ""), validate=True)
            ptype = SERIES_RECEIPT_TYPE.encode()
            pae = b"DSSEv1 " + str(len(ptype)).encode() + b" " + ptype + b" " \
                + str(len(encoded_payload)).encode() + b" " + encoded_payload
            payload_ok = (encoded_payload == _canonical(value)
                          and signed.get("payloadType") == SERIES_RECEIPT_TYPE
                          and signed.get("pae_sha256") == hashlib.sha256(pae).hexdigest())
        except Exception:
            payload_ok = False
        if (not payload_ok or value.get("schema") != "szl.series-a-receipt/v1"
                or not _bindings_match(value, {"receipt_id": receipt_id, "kind": kind,
                                              "created_at": created})):
            counts["binding_errors"] += 1
        if signed.get("signature_status") == "SIGNED":
            counts["signed_envelopes"] += 1
        else:
            counts["unsigned_envelopes"] += 1
        previous, last_sequence = claimed, sequence
    counts.update(chain_head=previous, last_sequence=last_sequence,
                  signature_verification="NOT_PERFORMED")
    return counts


def qualify_database(label: str, original: Path, working: Path, expected_generation: str,
                     deadline: float, *, historical_anchors: dict | None = None) -> dict:
    result: dict[str, Any] = {"state": "UNQUALIFIED", "restore_admitted": False,
                             "historical_anchor_state": "NOT_CHECKED" if historical_anchors is None else "UNQUALIFIED",
                             "diagnostic_code": "QUALIFICATION_NOT_RUN"}
    try:
        check_budget(deadline)
        working.mkdir(mode=0o700, parents=True, exist_ok=False)
        inspected = working / "inspection" / original.name
        inspected.parent.mkdir(mode=0o700)
        originals = {}
        companions = {suffix: {"present": False} for suffix in preservation.SUFFIXES if suffix}
        result["companions"] = companions
        for suffix in preservation.SUFFIXES:
            source = original.with_name(original.name + suffix)
            try:
                metadata = source.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > preservation.MAX_FILE_BYTES:
                raise RecoveryError("CAPTURED_FILE_UNAVAILABLE")
            originals[source] = preservation._sha(source)
            if suffix:
                companions[suffix] = {"present": True, "size": metadata.st_size,
                                      "sha256": originals[source]}
            shutil.copyfile(source, inspected.with_name(inspected.name + suffix))
        check_budget(deadline)
        # This incident evaluator admits only absent or empty companions.
        # Nonempty journals and WAL/SHM require a separate recovery contract,
        # even when SQLite would silently ignore their bytes.
        if any(item["present"] and item["size"] > 0 for item in companions.values()):
            raise RecoveryError("SIDECAR_REVIEW_REQUIRED")
        connection = readonly(inspected, deadline)
        try:
            result["original_header"] = preservation.sqlite_header(inspected)
            unreferenced_pages = []
            result["original_integrity"] = integrity(connection, unreferenced_pages=unreferenced_pages)
            status = result["original_integrity"]
            if status["classification"] not in {"OK", "UNREFERENCED_PAGES"} \
                    or status["foreign_key_violation_count"] or not status["foreign_key_check_complete"]:
                raise RecoveryError("ORIGINAL_NOT_ELIGIBLE_FOR_CANDIDATE")
            if status["classification"] == "UNREFERENCED_PAGES":
                result["unreferenced_page_contents"] = unreferenced_page_contents(
                    inspected, unreferenced_pages, deadline)
            observed_generation = generation(connection, label)
            if observed_generation != expected_generation:
                raise RecoveryError("CAPTURE_GENERATION_MISMATCH")
            result["database_generation_id"] = observed_generation
            original_fingerprint = logical_fingerprint(connection, label, deadline)
            original_receipts = receipt_continuity(connection, label, observed_generation, deadline)
            result["original_logical_state"] = original_fingerprint
            result["original_receipts"] = original_receipts
            if any(original_receipts[key] for key in ("digest_errors", "binding_errors", "chain_link_errors")):
                raise RecoveryError("ORIGINAL_RECEIPT_BINDINGS_INVALID")
            original_anchor = historical_anchor(connection, label, observed_generation, historical_anchors, deadline)
            result["original_historical_anchor"] = original_anchor
            # Retained rows and the historical anchor remain useful evidence
            # even when nonzero orphan contents forbid candidate evaluation.
            if status["classification"] == "UNREFERENCED_PAGES" \
                    and not result["unreferenced_page_contents"]["all_zero"]:
                result["unreferenced_page_forensics"] = orphan_forensic_observation(
                    inspected, unreferenced_pages, deadline, originals[original],
                    result["unreferenced_page_contents"])
                raise RecoveryError("UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW")
            candidate = working / "candidate.sqlite3"
            if candidate.exists():
                raise RecoveryError("CANDIDATE_DESTINATION_EXISTS")
            check_budget(deadline)
            if status["classification"] == "OK":
                result["candidate_method"] = "SQLITE_NATIVE_BACKUP"
                target = sqlite3.connect(candidate)
                try:
                    connection.backup(target, pages=128,
                                      progress=lambda *_args: check_budget(deadline))
                finally:
                    target.close()
            else:
                result["candidate_method"] = "SQLITE_VACUUM_INTO_DISPOSABLE_EVALUATION"
                # URI mode=ro still protects this disposable source. query_only
                # must be disabled for SQLite to create a distinct INTO file.
                connection.execute("PRAGMA query_only=OFF")
                connection.execute("VACUUM INTO ?", (str(candidate),))
        finally:
            connection.close()
        check_budget(deadline)
        candidate_connection = readonly(candidate, deadline)
        try:
            candidate_integrity = integrity(candidate_connection)
            candidate_generation = generation(candidate_connection, label)
            candidate_fingerprint = logical_fingerprint(candidate_connection, label, deadline)
            candidate_receipts = receipt_continuity(candidate_connection, label, candidate_generation, deadline)
            candidate_anchor = historical_anchor(candidate_connection, label, candidate_generation, historical_anchors, deadline)
        finally:
            candidate_connection.close()
        if candidate_integrity["classification"] != "OK" or candidate_integrity["foreign_key_violation_count"] \
                or not candidate_integrity["foreign_key_check_complete"]:
            raise RecoveryError("CANDIDATE_INTEGRITY_FAILED")
        if candidate_fingerprint != original_fingerprint or candidate_generation != observed_generation \
                or candidate_receipts != original_receipts or candidate_anchor != original_anchor:
            raise RecoveryError("CANDIDATE_LOGICAL_CONTINUITY_FAILED")
        if any(preservation._sha(path) != digest for path, digest in originals.items()):
            raise RecoveryError("CAPTURED_ORIGINAL_CHANGED")
        check_budget(deadline)
        candidate_sha256 = preservation._sha(candidate)
        candidate_bytes = candidate.stat().st_size
        check_budget(deadline)
        result.update(state="LOGICAL_CONTINUITY_VERIFIED", diagnostic_code="RESTORE_CONTRACT_REQUIRED",
                      historical_anchor_state=original_anchor["state"], candidate_historical_anchor=candidate_anchor,
                      candidate_integrity=candidate_integrity,
                      candidate_sha256=candidate_sha256, candidate_bytes=candidate_bytes,
                      captured_originals_unchanged=True, all_declared_stored_values_unchanged=True,
                      schema_unchanged=True, receipt_bytes_unchanged=True,
                      database_generation_unchanged=True, inspector_sqlite_version=sqlite3.sqlite_version,
                      external_artifact_verification="NOT_CAPTURED", durable_storage_qualified=False)
    except RecoveryError as exc:
        result["diagnostic_code"] = exc.code
    except Exception:
        result["diagnostic_code"] = "QUALIFICATION_UNAVAILABLE"
    return result


class ReadOnlyCaptureHub:
    """Capture reads and one metadata-only versioned-fence lookup; no writes."""
    def __init__(self, api: Any):
        self._api = api
        self.endpoint = api.endpoint

    def bucket_info(self, **kwargs: Any) -> Any:
        return self._api.bucket_info(**kwargs)

    def get_bucket_paths_info(self, **kwargs: Any) -> Any:
        return self._api.get_bucket_paths_info(**kwargs)

    def download_bucket_files(self, **kwargs: Any) -> Any:
        return self._api.download_bucket_files(**kwargs)

    def dataset_info(self, **kwargs: Any) -> Any:
        return self._api.dataset_info(**kwargs)


def fence_metadata(api: ReadOnlyCaptureHub, deadline: float) -> dict:
    """Observe the existing private dataset without fetching any dataset file.

    Missing metadata does not turn captured logical continuity into a failure.
    It leaves the independent durable-storage admission unqualified. A missing
    resource-group value is recorded as NONE_RETURNED; it never establishes the
    dataset and bucket have identical audiences or grants write permission.
    """
    result = {"state": "UNQUALIFIED", "repo_id": preservation.BUCKET, "repo_type": "dataset",
              "diagnostic_code": "FENCE_METADATA_UNAVAILABLE", "provider_writes_performed": False,
              "write_capability": "NOT_TESTED", "cas_live_verification": "NOT_PERFORMED"}
    check_budget(deadline)
    try:
        info = preservation._call(api.dataset_info, repo_id=preservation.BUCKET, revision="main",
                                 expand=["sha", "private", "resourceGroup"])
        revision = preservation._value(info, "sha")
        group = preservation._value(info, "resource_group", preservation._value(info, "resourceGroup"))
        if (preservation._value(info, "id") != preservation.BUCKET
                or preservation._value(info, "private") is not True
                or type(revision) is not str or preservation.HEX40.fullmatch(revision) is None
                or revision == "0" * 40 or (group is not None and type(group) is not dict)):
            raise RecoveryError("FENCE_METADATA_UNQUALIFIED")
        encoded_group = preservation._json_bytes(group)
        _json(encoded_group)  # Reject non-finite or otherwise invalid JSON metadata.
        if len(encoded_group) > 16 * 1024:
            raise RecoveryError("FENCE_METADATA_UNQUALIFIED")
        result.update(state="METADATA_ONLY_OBSERVED", diagnostic_code="FENCE_METADATA_OBSERVED",
                      private=True, revision=revision, resource_group_present=group is not None,
                      resource_group_observation="PRESENT" if group is not None else "NONE_RETURNED",
                      resource_group_observation_sha256=hashlib.sha256(encoded_group).hexdigest(),
                      bucket_dataset_audience_equivalence="NOT_ESTABLISHED")
    except (RecoveryError, preservation.PreservationError):
        pass
    except Exception:
        pass
    check_budget(deadline)
    return result


def qualify_capture(api: ReadOnlyCaptureHub, reference: dict, workspace: Path,
                    require_owned_source: Callable[[], None], deadline: float, *,
                    historical_anchors: dict | None = None,
                    capture_report_sha256: str | None = None) -> dict:
    report: dict[str, Any] = {"schema": SCHEMA, "state": "BLOCKED", "deployment_admitted": False,
        "restore_admitted": False, "diagnostic_code": "CAPTURE_REFERENCE_UNAVAILABLE",
        "provider_writes_performed": False, "originals_mutated": False,
        "secret_values_recorded": False, "private_bytes_in_public_artifacts": False,
        "historical_anchor_state": "NOT_CHECKED" if historical_anchors is None else "UNQUALIFIED",
        "later_acknowledged_writes_verified": False}
    try:
        check_budget(deadline)
        if historical_anchors is not None:
            validate_historical_anchors(historical_anchors, reference, capture_report_sha256)
            report["historical_anchor_reference"] = {
                key: historical_anchors[key] for key in ("source_revision", "workflow_run_id", "workflow_attempt",
                    "artifact_id", "artifact_archive_sha256", "capture_report_sha256")}
        if (reference.get("schema") != preservation.SCHEMA or reference.get("space") != preservation.SPACE
                or reference.get("bucket") != preservation.BUCKET or reference.get("state") != "BLOCKED"
                or reference.get("preservation_state") != "VERIFIED"
                or reference.get("deployment_admitted") is not False
                or reference.get("restore_admitted") is not False):
            raise RecoveryError("CAPTURE_NOT_VERIFIED")
        capture_id = reference.get("capture_id", "")
        match = re.fullmatch(r"[1-9][0-9]{0,19}-[1-9][0-9]{0,5}-([0-9a-f]{40})-[0-9a-f]{32}", capture_id)
        prefix = f"{preservation.PRIVATE_PREFIX}/{capture_id}"
        manifest = reference.get("private_manifest")
        if not match or reference.get("source_revision") != match.group(1) \
                or not isinstance(manifest, dict) or manifest.get("path") != prefix + "/preservation-manifest.json" \
                or preservation.HEX64.fullmatch(manifest.get("sha256", "")) is None \
                or preservation.HEX64.fullmatch(manifest.get("xet_hash", "")) is None:
            raise RecoveryError("CAPTURE_REFERENCE_INVALID")
        rows = reference.get("files")
        if not isinstance(rows, list) or len(rows) != len(preservation.SOURCE_PATHS):
            raise RecoveryError("CAPTURE_REFERENCE_INVALID")
        files = {}
        seen = set()
        for row in rows:
            path = row.get("source_path")
            if path not in preservation.SOURCE_PATHS or path in seen or type(row.get("present")) is not bool:
                raise RecoveryError("CAPTURE_REFERENCE_INVALID")
            seen.add(path)
            if row["present"]:
                if (row.get("private_copy_path") != prefix + "/originals/" + path
                        or type(row.get("size")) is not int or not 0 <= row["size"] <= preservation.MAX_FILE_BYTES
                        or preservation.HEX64.fullmatch(row.get("sha256", "")) is None
                        or preservation.HEX64.fullmatch(row.get("xet_hash", "")) is None):
                    raise RecoveryError("CAPTURE_REFERENCE_INVALID")
                files[path] = row
        if not all(path in files for path in preservation.DATABASES.values()) \
                or sum(row["size"] for row in files.values()) > preservation.MAX_TOTAL_BYTES:
            raise RecoveryError("CAPTURE_REFERENCE_INVALID")
        require_owned_source()
        if api.endpoint != preservation.ENDPOINT:
            raise RecoveryError("NONCANONICAL_ENDPOINT")
        bucket = preservation._call(api.bucket_info, bucket_id=preservation.BUCKET)
        if preservation._value(bucket, "id") != preservation.BUCKET \
                or preservation._value(bucket, "private") is not True:
            raise RecoveryError("PRIVATE_BUCKET_REQUIRED")
        report["durable_fence_metadata"] = fence_metadata(api, deadline)
        remote_paths = tuple(row["private_copy_path"] for row in files.values()) + (manifest["path"],)
        raw, identities = preservation.paths_info(api, remote_paths)
        if set(identities) != set(remote_paths):
            raise RecoveryError("PRESERVED_OBJECT_UNAVAILABLE")
        for row in files.values():
            if any(identities[row["private_copy_path"]][key] != row[key] for key in ("size", "xet_hash")):
                raise RecoveryError("PRESERVED_OBJECT_IDENTITY_CHANGED")
        if identities[manifest["path"]]["xet_hash"] != manifest["xet_hash"] \
                or identities[manifest["path"]]["size"] > MAX_REFERENCE_BYTES:
            raise RecoveryError("PRESERVED_MANIFEST_IDENTITY_CHANGED")
        workspace.mkdir(mode=0o700, parents=True, exist_ok=False)
        captured = workspace / "captured"
        captured.mkdir(mode=0o700)
        local_paths = {row["private_copy_path"]: captured / path for path, row in files.items()}
        local_paths[manifest["path"]] = captured / "preservation-manifest.json"
        for path in local_paths.values():
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        preservation._call(api.download_bucket_files, bucket_id=preservation.BUCKET,
                           files=[(raw[path], local_paths[path]) for path in remote_paths],
                           raise_on_missing_files=True)
        digests = preservation._local_files(captured, identities, local_paths)
        if digests[manifest["path"]] != manifest["sha256"] or any(
                digests[row["private_copy_path"]] != row["sha256"] for row in files.values()):
            raise RecoveryError("PRESERVED_OBJECT_DIGEST_MISMATCH")
        saved = _json(local_paths[manifest["path"]].read_bytes())
        if not isinstance(saved, dict) or any(saved.get(key) != reference.get(key) for key in
                ("schema", "space", "bucket", "capture_id", "source_revision", "files", "databases")) \
                or saved.get("preservation_state") != "PRIVATE_OBJECTS_VERIFIED" \
                or saved.get("deployment_admitted") is not False or saved.get("restore_admitted") is not False:
            raise RecoveryError("PRESERVED_MANIFEST_BINDING_INVALID")
        report.update(capture_id=capture_id, capture_source_revision=reference["source_revision"],
                      preservation_manifest_sha256=manifest["sha256"])
        report["databases"] = {}
        for label, path in preservation.DATABASES.items():
            check_budget(deadline)
            expected = reference.get("databases", {}).get(label, {}).get("database_generation_id")
            if not isinstance(expected, str):
                raise RecoveryError("CAPTURE_GENERATION_UNAVAILABLE")
            report["databases"][label] = qualify_database(
                label, local_paths[files[path]["private_copy_path"]], workspace / "working" / label,
                expected, deadline, historical_anchors=historical_anchors)
        check_budget(deadline)
        require_owned_source()
        _, after = preservation.paths_info(api, remote_paths)
        if after != identities:
            raise RecoveryError("PRESERVED_OBJECT_IDENTITIES_CHANGED")
        if preservation._local_files(captured, identities, local_paths) != digests:
            raise RecoveryError("CAPTURED_ORIGINAL_CHANGED")
        check_budget(deadline)
        if historical_anchors is not None:
            report["captured_historical_anchor_state"] = "VERIFIED" if all(
                item.get("original_historical_anchor", {}).get("state") == "VERIFIED"
                for item in report["databases"].values()) else "UNQUALIFIED"
            report["historical_anchor_state"] = "VERIFIED" if all(
                item["historical_anchor_state"] == "VERIFIED" for item in report["databases"].values()) else "UNQUALIFIED"
        if all(item["state"] == "LOGICAL_CONTINUITY_VERIFIED" for item in report["databases"].values()):
            if historical_anchors is not None and report["historical_anchor_state"] != "VERIFIED":
                raise RecoveryError("HISTORICAL_ANCHORS_NOT_VERIFIED")
            report.update(state="LOGICAL_CONTINUITY_VERIFIED", diagnostic_code="RESTORE_CONTRACT_REQUIRED")
        else:
            report["diagnostic_code"] = "CANDIDATE_NOT_QUALIFIED"
    except (RecoveryError, preservation.PreservationError) as exc:
        report["diagnostic_code"] = exc.code
    except Exception:
        report["diagnostic_code"] = "QUALIFICATION_UNAVAILABLE"
    report["completed_at"] = preservation._utc()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-report", type=Path, required=True)
    parser.add_argument("--historical-anchors", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report: dict[str, Any] = {"schema": SCHEMA, "state": "BLOCKED", "deployment_admitted": False,
                             "restore_admitted": False, "diagnostic_code": "SOURCE_CONTEXT_INVALID"}
    previous_alarm = None
    try:
        if (os.environ.get("GITHUB_ACTIONS") != "true"
                or os.environ.get("GITHUB_REPOSITORY") != "szl-holdings/a11oy"
                or os.environ.get("GITHUB_REF") != "refs/heads/main"):
            raise RecoveryError("SOURCE_CONTEXT_INVALID")
        source = os.environ.get("GITHUB_SHA", "")
        token, github_token = os.environ.get("HF_TOKEN", ""), os.environ.get("GH_TOKEN", "")
        if preservation.HEX40.fullmatch(source) is None or not token or not github_token:
            raise RecoveryError("SOURCE_CONTEXT_INVALID")
        reference, capture_report_bytes = read_reference_bytes(args.capture_report)
        anchors = read_reference(args.historical_anchors)
        capture_report_sha256 = hashlib.sha256(capture_report_bytes).hexdigest()
        validate_historical_anchors(anchors, reference, capture_report_sha256)
        from hf_exact_main_ownership import fetch_main_sha

        def ownership() -> None:
            if preservation._call(fetch_main_sha, "szl-holdings/a11oy", github_token) != source:
                raise RecoveryError("SOURCE_NO_LONGER_CURRENT_MAIN")

        def timeout_handler(_signal: int, _frame: Any) -> None:
            raise RecoveryError("QUALIFICATION_DEADLINE_EXHAUSTED")

        previous_alarm = signal.signal(signal.SIGALRM, timeout_handler)
        deadline = time.monotonic() + DEADLINE_SECONDS
        signal.alarm(DEADLINE_SECONDS)
        os.umask(0o077)
        logging.disable(logging.CRITICAL)
        os.environ.pop("HF_DEBUG", None)
        os.environ.update(HF_HUB_DISABLE_PROGRESS_BARS="1", HF_HUB_DISABLE_TELEMETRY="1",
                          HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
        with tempfile.TemporaryDirectory(prefix="szl-private-qualification-") as temporary:
            for name, suffix in (("HF_HOME", "cache"), ("HF_HUB_CACHE", "cache/hub"),
                                 ("HF_XET_CACHE", "cache/xet")):
                os.environ[name] = str(Path(temporary) / suffix)
            with preservation._private_output():
                import huggingface_hub
                from huggingface_hub.utils import set_client_factory
                if huggingface_hub.__version__ != preservation.SDK_VERSION:
                    raise RecoveryError("SDK_VERSION_MISMATCH")
                set_client_factory(preservation.hub_http_client)
                api = ReadOnlyCaptureHub(huggingface_hub.HfApi(endpoint=preservation.ENDPOINT, token=token))
                report = qualify_capture(api, reference, Path(temporary) / "capture", ownership, deadline,
                                         historical_anchors=anchors, capture_report_sha256=capture_report_sha256)
                report["inspector_source_revision"] = source
        check_budget(deadline)
        if report["state"] == "LOGICAL_CONTINUITY_VERIFIED" and report.get("historical_anchor_state") != "VERIFIED":
            raise RecoveryError("HISTORICAL_ANCHORS_NOT_VERIFIED")
    except (RecoveryError, preservation.PreservationError) as exc:
        report["state"] = "BLOCKED"
        report["diagnostic_code"] = exc.code
    except Exception:
        report["state"] = "BLOCKED"
        report["diagnostic_code"] = "QUALIFICATION_UNAVAILABLE"
    finally:
        if previous_alarm is not None:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_alarm)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(preservation._json_bytes(report))
    print(json.dumps({"schema": SCHEMA, "state": report["state"],
                      "diagnostic_code": report["diagnostic_code"], "deployment_admitted": False}))
    return 0 if report["state"] == "LOGICAL_CONTINUITY_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
