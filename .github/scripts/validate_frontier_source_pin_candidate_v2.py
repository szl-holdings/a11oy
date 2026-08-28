#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate the exact four-file Frontier source-pin transition with v2 authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Final


SCHEMA: Final = "a11oy.frontier-source-pin-authority/v2"
MAX_FILE_BYTES: Final = 512_000
REPOSITORY: Final = "szl-holdings/a11oy"
WORKFLOW_FILE_PATH: Final = ".github/workflows/frontier-source-pin-authority-v2.yml"
WORKFLOW_REF: Final = (
    f"{REPOSITORY}/{WORKFLOW_FILE_PATH}@refs/heads/main"
)
LOWER_SHA = re.compile(r"[0-9a-f]{40}\Z")
ORPHAN_DIGEST_LINE = re.compile(
    rb"^[ \t]*\$[0-9a-fA-F]+[ \t]*$", re.MULTILINE
)

SOLO_WORKFLOW: Final = ".github/workflows/frontier-solo-qualification.yml"
BUILDER_WORKFLOW: Final = (
    ".github/workflows/frontier-v16-7-exact-source-builder.yml"
)
CONTRACT: Final = "ops/frontier/v16_7/SOLO_EXECUTION_CONTRACT.json"
REPAIR_SCRIPT: Final = "ops/frontier/v16_7/apply_current_main_repairs.py"
SOURCE_TEST: Final = "ops/frontier/v16_7/test_frontier_v16_7_terminal_truth.py"
V1_AUTHORITY_WORKFLOW: Final = ".github/workflows/frontier-source-pin-authority.yml"
V1_VALIDATOR: Final = ".github/scripts/validate_frontier_source_pin_candidate.py"
V1_TEST: Final = "tests/test_validate_frontier_source_pin_candidate.py"

APPROVED_CANDIDATE_SHA256: Final = {
    SOLO_WORKFLOW: "8acce6dcf6bfb514f53d9a063ff314a0b4152dde9d0c6f82540dbf2dfe5b4ba3",
    BUILDER_WORKFLOW: "4ac6306328f41bf55faf63735f57be4e730823cc29abbccfecddba694df26254",
    CONTRACT: "3b8f3cff171631fdf4344b2cfdb8668cf4e92dadf2688f92a5ad4a0f53ad4a4d",
    V1_TEST: "277160852dabad5441c4b676e5ed96405c6ad9a85cebcbdf9c5c44eb089a22e6",
}
PROTECTED_INPUT_SHA256: Final = {
    REPAIR_SCRIPT: "003b709612d1d59fe0ce3b6316cd4a33273c5bd35237530c50e1f329f4ef0e59",
    SOURCE_TEST: "ee86e0eb880095686b204c89295c7b0f5912b937235675d72a412aeace44a3db",
    V1_AUTHORITY_WORKFLOW: "97d65580ca7ad98a7ba210e363eccbfe2ec6b19d8b950814717f01cd94e65049",
    V1_VALIDATOR: "622d60897cdd0e2a7c48adc97efa7effb1283f81af735c1eab02e54841c70245",
}


class ValidationError(RuntimeError):
    """The candidate is outside the exact protected repair contract."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_regular(root: Path, relative: str) -> bytes:
    if not relative or relative.startswith(("/", "\\")):
        raise ValidationError(f"invalid relative path: {relative!r}")
    parts = Path(relative).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValidationError(f"invalid relative path: {relative!r}")

    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValidationError(f"symlink is not admissible: {relative}")
    if not current.is_file():
        raise ValidationError(f"required regular file is missing: {relative}")
    if current.stat().st_size > MAX_FILE_BYTES:
        raise ValidationError(f"file exceeds bounded size: {relative}")
    return current.read_bytes()


def _require_exact_line(source: str, line: str, *, count: int = 1) -> None:
    observed = sum(1 for candidate in source.splitlines() if candidate == line)
    if observed != count:
        raise ValidationError(
            f"expected {count} exact executable line(s), found {observed}: {line}"
        )


def _validate_contract(data: bytes) -> None:
    try:
        contract = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Frontier contract is not canonical UTF-8 JSON") from exc
    source = contract.get("source")
    if not isinstance(source, dict):
        raise ValidationError("Frontier contract source object is missing")
    if source.get("repair_oracle") != {
        "path": REPAIR_SCRIPT,
        "sha256": PROTECTED_INPUT_SHA256[REPAIR_SCRIPT],
    }:
        raise ValidationError("contract repair_oracle does not bind protected bytes")
    if source.get("regression") != {
        "protected_template_path": SOURCE_TEST,
        "source_path": "tests/test_frontier_v16_7_terminal_truth.py",
        "sha256": PROTECTED_INPUT_SHA256[SOURCE_TEST],
    }:
        raise ValidationError("contract regression does not bind protected bytes")


def _validate_workflow(path: str, data: bytes, contract_digest: str) -> None:
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValidationError(f"UTF-8 BOM is not admissible: {path}")
    if b"\x00" in data:
        raise ValidationError(f"NUL is not admissible: {path}")
    if ORPHAN_DIGEST_LINE.search(data):
        raise ValidationError(f"orphan digest line remains: {path}")
    try:
        source = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"workflow is not UTF-8: {path}") from exc

    _require_exact_line(source, f"      CONTRACT_SHA256: {contract_digest}")
    _require_exact_line(
        source,
        "      REPAIR_SCRIPT_SHA256: "
        + PROTECTED_INPUT_SHA256[REPAIR_SCRIPT],
    )
    _require_exact_line(
        source,
        "      SOURCE_TEST_SHA256: " + PROTECTED_INPUT_SHA256[SOURCE_TEST],
    )

    if path == SOLO_WORKFLOW:
        _require_exact_line(
            source,
            '            test "$observed_repair_digest" = "$REPAIR_SCRIPT_SHA256"',
        )
        _require_exact_line(
            source,
            '            test "$contract_digest" = "$CONTRACT_SHA256"',
        )
        _require_exact_line(
            source,
            '            test "$test_digest" = "$SOURCE_TEST_SHA256"',
        )
        _require_exact_line(
            source,
            '              test "$test_digest" = "$SOURCE_TEST_SHA256"',
        )
    else:
        _require_exact_line(
            source,
            '          test "$contract" = "$CONTRACT_SHA256"',
        )
        _require_exact_line(
            source,
            '          test "$(sha256sum "$repair_script" | awk \'{print $1}\')" = "$REPAIR_SCRIPT_SHA256"',
        )
        _require_exact_line(
            source,
            '          test "$(sha256sum "$source_test" | awk \'{print $1}\')" = "$SOURCE_TEST_SHA256"',
        )


def _normalize_changed_paths(paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in paths:
        if not isinstance(value, str) or not value or "\\" in value:
            raise ValidationError("changed path is not canonical UTF-8 POSIX text")
        parts = Path(value).parts
        if value.startswith("/") or any(part in {"", ".", ".."} for part in parts):
            raise ValidationError(f"invalid changed path: {value!r}")
        normalized.append(value)
    if len(normalized) != len(set(normalized)):
        raise ValidationError("changed path list contains duplicates")
    return sorted(normalized)


def _validate_identity(
    *,
    workflow_repository: str,
    workflow_ref: str,
    workflow_file_path: str,
    workflow_sha: str,
    repository: str,
    protected_base_sha: str,
    candidate_sha: str,
) -> dict[str, str]:
    if workflow_repository != REPOSITORY or repository != REPOSITORY:
        raise ValidationError("workflow and candidate repository identity must be exact")
    if workflow_ref != WORKFLOW_REF:
        raise ValidationError("workflow ref is not the protected main authority")
    if workflow_file_path != WORKFLOW_FILE_PATH:
        raise ValidationError("workflow file path identity must be exact")
    for label, value in (
        ("workflow_sha", workflow_sha),
        ("protected_base_sha", protected_base_sha),
        ("candidate_sha", candidate_sha),
    ):
        if not LOWER_SHA.fullmatch(value):
            raise ValidationError(f"{label} must be an exact lowercase Git SHA")
    if workflow_sha != protected_base_sha:
        raise ValidationError("workflow SHA must equal the exact protected event base")
    return {
        "authority_state": "PROTECTED_REQUIRED",
        "workflow_repository": workflow_repository,
        "workflow_ref": workflow_ref,
        "workflow_file_path": workflow_file_path,
        "workflow_sha": workflow_sha,
        "repository": repository,
        "protected_base_sha": protected_base_sha,
        "candidate_sha": candidate_sha,
    }


def _read_changed_paths(path: Path) -> list[str]:
    raw = path.read_bytes()
    if len(raw) > 1_000_000:
        raise ValidationError("changed path list exceeds bounded size")
    if raw and not raw.endswith(b"\0"):
        raise ValidationError("changed path list is not NUL terminated")
    values: list[str] = []
    for item in raw.split(b"\0")[:-1]:
        try:
            values.append(item.decode("utf-8", errors="strict"))
        except UnicodeDecodeError as exc:
            raise ValidationError("changed path is not UTF-8") from exc
    return _normalize_changed_paths(values)


def validate(
    protected_root: Path,
    candidate_root: Path,
    repository_changed_paths: list[str] | None = None,
) -> dict[str, object]:
    protected_root = protected_root.resolve(strict=True)
    candidate_root = candidate_root.resolve(strict=True)

    for path, expected_digest in PROTECTED_INPUT_SHA256.items():
        protected = _read_regular(protected_root, path)
        candidate = _read_regular(candidate_root, path)
        observed = _sha256(protected)
        if observed != expected_digest:
            raise ValidationError(
                f"protected input digest drifted for {path}: {observed}"
            )
        if candidate != protected:
            raise ValidationError(f"candidate changed protected input: {path}")

    base_guarded = {
        path: _read_regular(protected_root, path)
        for path in APPROVED_CANDIDATE_SHA256
    }
    candidate_guarded = {
        path: _read_regular(candidate_root, path)
        for path in APPROVED_CANDIDATE_SHA256
    }
    guarded_changes = sorted(
        path
        for path in APPROVED_CANDIDATE_SHA256
        if base_guarded[path] != candidate_guarded[path]
    )
    reported_paths = _normalize_changed_paths(
        repository_changed_paths
        if repository_changed_paths is not None
        else guarded_changes
    )
    immutable_tree_changes = sorted(set(reported_paths) & set(PROTECTED_INPUT_SHA256))
    if immutable_tree_changes:
        raise ValidationError(
            "protected input tree changed: " + ", ".join(immutable_tree_changes)
        )
    if not guarded_changes:
        reported_guarded = sorted(
            set(reported_paths) & set(APPROVED_CANDIDATE_SHA256)
        )
        if reported_guarded:
            raise ValidationError(
                "reported guarded tree change has unchanged raw blob bytes: "
                + ", ".join(reported_guarded)
            )
        return {
            "schema": SCHEMA,
            "status": "NOT_APPLICABLE",
            "changed_paths": [],
            "repository_changed_paths": reported_paths,
            "candidate_payload_checkout_code_executed": False,
        }

    expected_paths = sorted(APPROVED_CANDIDATE_SHA256)
    if reported_paths != expected_paths:
        raise ValidationError(
            "complete repository diff must contain exactly: "
            + ", ".join(expected_paths)
        )
    if guarded_changes != expected_paths:
        raise ValidationError(
            "guarded repair must atomically change exactly: "
            + ", ".join(expected_paths)
        )

    observed_digests = {
        path: _sha256(candidate_guarded[path]) for path in expected_paths
    }
    for path, expected_digest in APPROVED_CANDIDATE_SHA256.items():
        if observed_digests[path] != expected_digest:
            raise ValidationError(
                f"candidate is not the approved exact repair for {path}: "
                f"{observed_digests[path]}"
            )

    contract_data = candidate_guarded[CONTRACT]
    _validate_contract(contract_data)
    contract_digest = _sha256(contract_data)
    _validate_workflow(
        SOLO_WORKFLOW, candidate_guarded[SOLO_WORKFLOW], contract_digest
    )
    _validate_workflow(
        BUILDER_WORKFLOW, candidate_guarded[BUILDER_WORKFLOW], contract_digest
    )

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "changed_paths": guarded_changes,
        "repository_changed_paths": reported_paths,
        "approved_candidate_sha256": observed_digests,
        "protected_input_sha256": dict(PROTECTED_INPUT_SHA256),
        "candidate_payload_checkout_code_executed": False,
    }


def _write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protected-root", required=True, type=Path)
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--changed-paths-file", required=True, type=Path)
    parser.add_argument("--workflow-repository", required=True)
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--workflow-file-path", required=True)
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--protected-base-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)

    identity: dict[str, str] | None = None
    try:
        identity = _validate_identity(
            workflow_repository=args.workflow_repository,
            workflow_ref=args.workflow_ref,
            workflow_file_path=args.workflow_file_path,
            workflow_sha=args.workflow_sha,
            repository=args.repository,
            protected_base_sha=args.protected_base_sha,
            candidate_sha=args.candidate_sha,
        )
        report = validate(
            args.protected_root,
            args.candidate_root,
            _read_changed_paths(args.changed_paths_file),
        )
        report["identity"] = identity
    except (OSError, ValidationError) as exc:
        report = {
            "schema": SCHEMA,
            "status": "FAIL",
            "reason": str(exc),
            "candidate_payload_checkout_code_executed": False,
        }
        if identity is not None:
            report["identity"] = identity
        _write_report(args.report, report)
        print(f"Frontier source-pin authority failed: {exc}", file=sys.stderr)
        return 1

    _write_report(args.report, report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
