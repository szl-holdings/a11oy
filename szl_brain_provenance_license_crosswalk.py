#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deterministic, fail-closed Brain provenance/license crosswalk.

Logical taxonomy: ``provenance/``.  The flat-root module belongs to the
provenance layer because it produces evidence-gap receipts and never performs
agent reasoning, governance authorization, or training.

The crosswalk binds the frozen M1 ledger, its snapshot, and the repository
license to one exact Git commit.  It records row-level evidence gaps without
copying row content or identifiers into the output.  Repository membership or
a domain name never establishes origin rights, privacy clearance, consent,
semantic deduplication, independent review, or training authorization.

This tool does not create admission candidates, sign evidence, train, publish,
or promote a model.  Its output is an unsigned evidence-gap receipt for the
existing signed admission pipeline.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Any, Callable, Mapping, Sequence


EXPECTED_ROWS = 9_464
LEDGER_SCHEMA = "szl.m1-brain-ingest-decision/v1"
SNAPSHOT_SCHEMA = "szl.brain-raw-snapshot.v1"
CROSSWALK_ROW_SCHEMA = "szl.brain-row-provenance-license-crosswalk.v1"
RECEIPT_SCHEMA = "szl.brain-row-provenance-license-crosswalk-receipt.v1"
AUTHORIZED_REPOSITORY = "https://github.com/szl-holdings/a11oy"
LEDGER_REPOSITORY_PATH = "model_release/m1/brain-ingest-ledger.jsonl"
SNAPSHOT_REPOSITORY_PATH = "model_release/brain-row-admission/raw-snapshot.json"
LICENSE_REPOSITORY_PATH = "LICENSE"
MAX_LEDGER_BYTES = 128 * 1024 * 1024
MAX_LEDGER_LINE_BYTES = 256 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_LICENSE_BYTES = 256 * 1024
MAX_CONTENT_BYTES = 64 * 1024
APPROVED_APACHE_2_LICENSE_SHA256 = (
    "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_REVISION_RE = re.compile(r"^git:([0-9a-f]{40})$")


class CrosswalkRefused(RuntimeError):
    """The crosswalk could not prove one of its immutable input boundaries."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _opaque_row_key(node_id: str, content_sha256: str) -> str:
    return _sha256_bytes(
        b"szl.brain-row-crosswalk-key.v1\0"
        + _canonical_bytes(
            {"node_id": node_id, "content_sha256": content_sha256}
        )
    )


def _no_duplicate_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise CrosswalkRefused(f"duplicate JSON object key: {key}")
        out[key] = value
    return out


def _strict_json_loads(value: str | bytes, label: str) -> Any:
    try:
        return json.loads(
            value,
            object_pairs_hook=_no_duplicate_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {token}")
            ),
        )
    except CrosswalkRefused:
        raise
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise CrosswalkRefused(f"{label} is not strict UTF-8 JSON") from exc


def _read_stable_regular_file(
    path: pathlib.Path, maximum: int, label: str
) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        raise CrosswalkRefused(f"{label} is not readable") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise CrosswalkRefused(f"{label} must be a regular non-symlink file")
    if before.st_size <= 0 or before.st_size > maximum:
        raise CrosswalkRefused(f"{label} is outside the bounded size policy")
    try:
        with path.open("rb") as handle:
            descriptor_before = os.fstat(handle.fileno())
            data = handle.read(maximum + 1)
            descriptor_after = os.fstat(handle.fileno())
        after = path.lstat()
    except OSError as exc:
        raise CrosswalkRefused(f"{label} changed while read") from exc
    identity = lambda item: (
        item.st_dev,
        item.st_ino,
        item.st_size,
        item.st_mtime_ns,
    )
    if (
        identity(before) != identity(descriptor_before)
        or identity(descriptor_before) != identity(descriptor_after)
        or identity(descriptor_after) != identity(after)
        or len(data) != descriptor_after.st_size
        or not data
        or len(data) > maximum
    ):
        raise CrosswalkRefused(f"{label} changed while read")
    return data


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise CrosswalkRefused(f"{label} is not a lowercase SHA-256")
    return value


def _require_text(value: Any, label: str, maximum: int = 2048) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 for character in value)
    ):
        raise CrosswalkRefused(f"{label} is not a bounded non-empty string")
    return value


def _git_blob_reader(
    repository_root: pathlib.Path,
    revision: str,
    *,
    git_executable: str | None = None,
) -> Callable[[str], bytes]:
    match = _GIT_REVISION_RE.fullmatch(revision)
    if match is None:
        raise CrosswalkRefused("repository revision must be git:<40 lowercase hex>")
    commit = match.group(1)
    git = git_executable or shutil.which("git")
    if not git or not pathlib.Path(git).is_file():
        raise CrosswalkRefused("git executable is unavailable")

    environment = {
        "PATH": os.environ.get("PATH", ""),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
    }

    def run(arguments: Sequence[str], maximum: int, label: str) -> bytes:
        try:
            completed = subprocess.run(
                [git, "-C", str(repository_root), *arguments],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CrosswalkRefused(f"git could not read {label}") from exc
        if completed.returncode != 0 or not completed.stdout:
            raise CrosswalkRefused(f"git could not read {label}")
        if len(completed.stdout) > maximum or len(completed.stderr) > 64 * 1024:
            raise CrosswalkRefused(f"git output for {label} exceeded policy")
        return completed.stdout

    observed_commit = run(
        ["rev-parse", "--verify", f"{commit}^{{commit}}"], 128, "commit"
    ).decode("ascii", errors="strict").strip()
    if observed_commit != commit:
        raise CrosswalkRefused("repository revision did not resolve exactly")
    origin_url = run(
        ["config", "--get", "remote.origin.url"], 2048, "origin URL"
    ).decode("utf-8", errors="strict").strip()
    if origin_url not in {
        "https://github.com/szl-holdings/a11oy.git",
        "git@github.com:szl-holdings/a11oy.git",
    }:
        raise CrosswalkRefused("repository origin is not the authorized a11oy source")
    origin_main = run(
        ["rev-parse", "--verify", "refs/remotes/origin/main^{commit}"],
        128,
        "origin/main",
    ).decode("ascii", errors="strict").strip()
    if origin_main != commit:
        raise CrosswalkRefused("repository revision is not the fetched origin/main commit")

    maxima = {
        LEDGER_REPOSITORY_PATH: MAX_LEDGER_BYTES,
        SNAPSHOT_REPOSITORY_PATH: MAX_JSON_BYTES,
        LICENSE_REPOSITORY_PATH: MAX_LICENSE_BYTES,
    }

    def read(path: str) -> bytes:
        if path not in maxima:
            raise CrosswalkRefused("git blob path is outside the fixed source set")
        object_type = run(
            ["cat-file", "-t", f"{commit}:{path}"], 64, f"{path} type"
        ).decode("ascii", errors="strict").strip()
        if object_type != "blob":
            raise CrosswalkRefused(f"{path} is not a Git blob")
        return run(
            ["cat-file", "blob", f"{commit}:{path}"], maxima[path], path
        )

    return read


def _load_ledger(data: bytes, expected_rows: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    content_hashes: set[str] = set()
    for line_number, raw_line in enumerate(data.splitlines(keepends=True), 1):
        if not raw_line.endswith(b"\n"):
            raise CrosswalkRefused(f"ledger line {line_number} lacks terminal newline")
        if not raw_line.strip() or len(raw_line) > MAX_LEDGER_LINE_BYTES:
            raise CrosswalkRefused(f"ledger line {line_number} violates bounds")
        raw = _strict_json_loads(raw_line, f"ledger line {line_number}")
        if not isinstance(raw, Mapping) or raw.get("schema") != LEDGER_SCHEMA:
            raise CrosswalkRefused(f"ledger line {line_number} schema is unsupported")
        node_id = _require_text(raw.get("node_id"), f"ledger line {line_number}.node_id", 256)
        content = raw.get("canonical_text")
        if (
            not isinstance(content, str)
            or not content
            or "\x00" in content
            or len(content.encode("utf-8")) > MAX_CONTENT_BYTES
        ):
            raise CrosswalkRefused(
                f"ledger line {line_number}.canonical_text is invalid"
            )
        content_sha = _require_sha256(
            raw.get("canonical_text_sha256"),
            f"ledger line {line_number}.canonical_text_sha256",
        )
        if _sha256_bytes(content.encode("utf-8")) != content_sha:
            raise CrosswalkRefused(f"ledger line {line_number} content hash mismatch")
        if node_id in node_ids or content_sha in content_hashes:
            raise CrosswalkRefused("ledger does not have unique node/content identities")
        if raw.get("training_decision") != "QUARANTINE" or raw.get("training_eligible") is not False:
            raise CrosswalkRefused("ledger contains a pre-admitted row")
        provenance = raw.get("provenance")
        license_record = raw.get("license")
        if not isinstance(provenance, Mapping) or not isinstance(license_record, Mapping):
            raise CrosswalkRefused(f"ledger line {line_number} evidence metadata is invalid")
        node_ids.add(node_id)
        content_hashes.add(content_sha)
        rows.append(dict(raw))
    if len(rows) != expected_rows:
        raise CrosswalkRefused(
            f"ledger has {len(rows)} rows; expected exactly {expected_rows}"
        )
    return rows


def _verify_snapshot(
    snapshot_bytes: bytes,
    ledger_bytes: bytes,
    rows: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    snapshot = _strict_json_loads(snapshot_bytes, "raw snapshot")
    if not isinstance(snapshot, Mapping) or snapshot.get("schema_version") != SNAPSHOT_SCHEMA:
        raise CrosswalkRefused("raw snapshot schema is unsupported")
    counts = snapshot.get("counts")
    source = snapshot.get("source")
    claims = snapshot.get("claims_boundary")
    if not all(isinstance(item, Mapping) for item in (counts, source, claims)):
        raise CrosswalkRefused("raw snapshot evidence sections are missing")
    ledger_sha = _sha256_bytes(ledger_bytes)
    if source.get("path") != LEDGER_REPOSITORY_PATH or source.get("sha256") != ledger_sha:
        raise CrosswalkRefused("raw snapshot is not bound to this ledger")
    expected = len(rows)
    if any(counts.get(field) != expected for field in ("rows", "unique_node_ids", "distinct_content_sha256")):
        raise CrosswalkRefused("raw snapshot count partition does not match the ledger")
    if counts.get("training_eligible_rows") != 0 or counts.get("duplicate_content_rows") != 0:
        raise CrosswalkRefused("raw snapshot contains admission or duplicate-content claims")
    for field in (
        "model_promotion_allowed",
        "privacy_clearance_established",
        "rights_established",
        "training_authorized",
        "training_triggered",
    ):
        if claims.get(field) is not False:
            raise CrosswalkRefused(f"raw snapshot claim {field} is not fail-closed")
    return snapshot


def _license_binding(row: Mapping[str, Any], *, license_sha256: str) -> bool:
    license_record = row["license"]
    return (
        license_sha256 == APPROVED_APACHE_2_LICENSE_SHA256
        and row.get("source_family")
        in {"a11oy-versioned-runtime", "brain-raw-formula-index"}
        and isinstance(row.get("canonical_artifact_id"), str)
        and bool(row.get("canonical_artifact_id"))
        and license_record.get("state") == "VERSIONED_REPOSITORY_LICENSE"
        and license_record.get("spdx") == "Apache-2.0"
        and license_record.get("evidence") == LICENSE_REPOSITORY_PATH
    )


def _crosswalk_row(
    row: Mapping[str, Any],
    *,
    repository_revision: str,
    ledger_sha256: str,
    license_sha256: str,
    git_blob_verified: bool,
) -> dict[str, Any]:
    license_bound = _license_binding(row, license_sha256=license_sha256)
    semantic_duplicate = row.get("safety_decision") == "QUARANTINE_RAW_GRAPH_DUPLICATE_FORMULA"
    blockers = {
        "IMMUTABLE_ITEM_ORIGIN_EVIDENCE_MISSING",
        "SIGNED_PRIVACY_CLEARANCE_MISSING",
        "SIGNED_CONSENT_OR_PERMISSION_EVIDENCE_MISSING",
        "SIGNED_INDEPENDENT_REVIEW_MISSING",
    }
    if not git_blob_verified:
        blockers.add("IMMUTABLE_LEDGER_BINDING_UNVERIFIED")
    if not license_bound:
        blockers.add("VERSION_BOUND_ITEM_LICENSE_EVIDENCE_MISSING")
    blockers.add(
        "SEMANTIC_DUPLICATE_FLAGGED"
        if semantic_duplicate
        else "SEMANTIC_DUPLICATION_EVIDENCE_MISSING"
    )
    return {
        "schema_version": CROSSWALK_ROW_SCHEMA,
        "row_key_sha256": _opaque_row_key(
            str(row["node_id"]), str(row["canonical_text_sha256"])
        ),
        "ledger_binding": {
            "state": "PASS" if git_blob_verified else "UNVERIFIED",
            "repository": AUTHORIZED_REPOSITORY,
            "revision": repository_revision,
            "ledger_sha256": ledger_sha256,
        },
        "immutable_item_origin": {
            "state": "MISSING",
            "reason": "NO_ITEM_LEVEL_IMMUTABLE_SOURCE_REVISION",
        },
        "license": {
            "state": "PASS" if license_bound else "MISSING",
            "spdx": "Apache-2.0" if license_bound else None,
            "license_file_sha256": license_sha256 if license_bound else None,
            "reason": (
                "VERSIONED_REPOSITORY_LICENSE_BOUND"
                if license_bound
                else "NO_ITEM_LEVEL_VERSION_BOUND_LICENSE"
            ),
        },
        "privacy": {
            "state": "MISSING",
            "reason": (
                "PERSON_METADATA_REQUIRES_EXPLICIT_CLEARANCE"
                if row.get("kind") == "person"
                else "NO_SIGNED_ITEM_LEVEL_PRIVACY_CLEARANCE"
            ),
        },
        "duplication": {
            "state": "BLOCKED",
            "exact_content": "PASS_UNIQUE_SHA256",
            "semantic": (
                "DUPLICATE_FLAGGED"
                if semantic_duplicate
                else "MISSING_INDEPENDENT_EVIDENCE"
            ),
        },
        "consent": {
            "state": "MISSING",
            "reason": "NO_SIGNED_ITEM_LEVEL_CONSENT_OR_PERMISSION_SCOPE",
        },
        "independent_review": {
            "state": "MISSING",
            "reason": "NO_ALLOWLISTED_SIGNED_ROW_REVIEW",
        },
        "admission": {
            "state": "QUARANTINE",
            "training_eligible": False,
            "blockers": sorted(blockers),
        },
    }


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_bytes(row) + b"\n" for row in rows)


def _atomic_write(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise CrosswalkRefused("output directory must not be a symlink")
    temporary_handle = tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    )
    temporary = pathlib.Path(temporary_handle.name)
    try:
        with temporary_handle:
            temporary_handle.write(data)
            temporary_handle.flush()
            os.fsync(temporary_handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _build_crosswalk(
    repository_root: pathlib.Path | str,
    repository_revision: str,
    output_dir: pathlib.Path | str,
    *,
    expected_rows: int = EXPECTED_ROWS,
    git_executable: str | None = None,
    blob_reader: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    """Internal implementation with explicit verification provenance."""

    if not isinstance(expected_rows, int) or not 1 <= expected_rows <= EXPECTED_ROWS:
        raise CrosswalkRefused("expected row count is outside policy")
    if _GIT_REVISION_RE.fullmatch(repository_revision) is None:
        raise CrosswalkRefused("repository revision must be git:<40 lowercase hex>")
    root = pathlib.Path(repository_root).resolve()
    output = pathlib.Path(output_dir)
    if not root.is_dir():
        raise CrosswalkRefused("repository root is unavailable")
    if output.exists() and (output.is_symlink() or not output.is_dir()):
        raise CrosswalkRefused("output directory must be a regular directory")
    git_blob_verified = blob_reader is None
    read_blob = blob_reader or _git_blob_reader(
        root, repository_revision, git_executable=git_executable
    )
    local_paths = {
        LEDGER_REPOSITORY_PATH: root / LEDGER_REPOSITORY_PATH,
        SNAPSHOT_REPOSITORY_PATH: root / SNAPSHOT_REPOSITORY_PATH,
        LICENSE_REPOSITORY_PATH: root / LICENSE_REPOSITORY_PATH,
    }
    maxima = {
        LEDGER_REPOSITORY_PATH: MAX_LEDGER_BYTES,
        SNAPSHOT_REPOSITORY_PATH: MAX_JSON_BYTES,
        LICENSE_REPOSITORY_PATH: MAX_LICENSE_BYTES,
    }
    local_bytes: dict[str, bytes] = {}
    for path, local_path in local_paths.items():
        observed = _read_stable_regular_file(local_path, maxima[path], path)
        if observed != read_blob(path):
            raise CrosswalkRefused(f"working {path} differs from the pinned Git blob")
        local_bytes[path] = observed
    ledger_bytes = local_bytes[LEDGER_REPOSITORY_PATH]
    rows = _load_ledger(ledger_bytes, expected_rows)
    _verify_snapshot(
        local_bytes[SNAPSHOT_REPOSITORY_PATH], ledger_bytes, rows
    )
    ledger_sha = _sha256_bytes(ledger_bytes)
    license_sha = _sha256_bytes(local_bytes[LICENSE_REPOSITORY_PATH])
    crosswalk = sorted(
        (
            _crosswalk_row(
                row,
                repository_revision=repository_revision,
                ledger_sha256=ledger_sha,
                license_sha256=license_sha,
                git_blob_verified=git_blob_verified,
            )
            for row in rows
        ),
        key=lambda item: item["row_key_sha256"],
    )
    body = _jsonl_bytes(crosswalk)
    blocker_counts: collections.Counter[str] = collections.Counter()
    for item in crosswalk:
        blocker_counts.update(item["admission"]["blockers"])
    license_pass = sum(item["license"]["state"] == "PASS" for item in crosswalk)
    core = {
        "schema_version": RECEIPT_SCHEMA,
        "operation": "EVIDENCE_CROSSWALK_NOT_ADMISSION",
        "repository": {
            "uri": AUTHORIZED_REPOSITORY,
            "revision": repository_revision,
        },
        "inputs": {
            "ledger": {
                "path": LEDGER_REPOSITORY_PATH,
                "sha256": ledger_sha,
                "rows": len(rows),
                "git_blob_verified": git_blob_verified,
            },
            "snapshot": {
                "path": SNAPSHOT_REPOSITORY_PATH,
                "sha256": _sha256_bytes(local_bytes[SNAPSHOT_REPOSITORY_PATH]),
                "git_blob_verified": git_blob_verified,
            },
            "license": {
                "path": LICENSE_REPOSITORY_PATH,
                "sha256": license_sha,
                "git_blob_verified": git_blob_verified,
            },
        },
        "output": {
            "path": "brain-row-provenance-license-crosswalk.v1.jsonl",
            "sha256": _sha256_bytes(body),
            "rows": len(crosswalk),
            "content_policy": "OPAQUE_ROW_KEY_AND_EVIDENCE_STATES_ONLY",
        },
        "coverage": {
            "immutable_ledger_binding_pass": len(crosswalk) if git_blob_verified else 0,
            "immutable_item_origin_pass": 0,
            "version_bound_license_pass": license_pass,
            "signed_privacy_clearance_pass": 0,
            "semantic_duplication_evidence_pass": 0,
            "signed_consent_or_permission_pass": 0,
            "signed_independent_review_pass": 0,
            "admitted_rows": 0,
            "quarantined_rows": len(crosswalk),
        },
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "authorization": {
            "signature_state": "UNSIGNED_NO_APPROVED_KEY",
            "training_authorized": False,
            "training_triggered": False,
            "model_promotion_allowed": False,
        },
        "non_claims": [
            "NO_LICENSE_INFERENCE_FROM_DOMAIN_OR_REPOSITORY_NAME",
            "NO_HUGGING_FACE_CARD_LICENSE_INFERENCE",
            "NO_PRIVACY_OR_CONSENT_INFERENCE",
            "NO_SEMANTIC_DEDUPLICATION_INFERENCE",
            "NO_TRAINING_ADMISSION",
        ],
    }
    receipt = {**core, "receipt_sha256": _sha256_bytes(_canonical_bytes(core))}
    _atomic_write(output / core["output"]["path"], body)
    _atomic_write(
        output / "brain-row-provenance-license-crosswalk-receipt.v1.json",
        _canonical_bytes(receipt) + b"\n",
    )
    return receipt


def build_crosswalk(
    repository_root: pathlib.Path | str,
    repository_revision: str,
    output_dir: pathlib.Path | str,
    *,
    expected_rows: int = EXPECTED_ROWS,
    git_executable: str | None = None,
) -> dict[str, Any]:
    """Build a Git-verified unsigned crosswalk receipt for one exact commit."""

    return _build_crosswalk(
        repository_root,
        repository_revision,
        output_dir,
        expected_rows=expected_rows,
        git_executable=git_executable,
        blob_reader=None,
    )


def _build_crosswalk_for_test(
    repository_root: pathlib.Path | str,
    repository_revision: str,
    output_dir: pathlib.Path | str,
    *,
    expected_rows: int,
    blob_reader: Callable[[str], bytes],
) -> dict[str, Any]:
    """Run parser fixtures while explicitly refusing Git-verification claims.

    This helper is private and excluded from ``__all__``.  Production callers
    use :func:`build_crosswalk`, which always invokes the authorized-origin Git
    reader.  Injected fixture bytes produce UNVERIFIED ledger bindings and zero
    immutable-ledger coverage.
    """

    return _build_crosswalk(
        repository_root,
        repository_revision,
        output_dir,
        expected_rows=expected_rows,
        git_executable=None,
        blob_reader=blob_reader,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--repository-revision", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--git-executable")
    args = parser.parse_args(argv)
    try:
        receipt = build_crosswalk(
            args.repository_root,
            args.repository_revision,
            args.output_dir,
            git_executable=args.git_executable,
        )
    except CrosswalkRefused as exc:
        parser.exit(2, f"REFUSED: {exc}\n")
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AUTHORIZED_REPOSITORY",
    "CROSSWALK_ROW_SCHEMA",
    "CrosswalkRefused",
    "EXPECTED_ROWS",
    "RECEIPT_SCHEMA",
    "build_crosswalk",
]
