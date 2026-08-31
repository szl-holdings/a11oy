#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Protected-base admission for narrowly reviewed HF contract successors.

The controller is intended to run from an exact protected-base checkout.
Candidate files are fetched at immutable commit SHAs, verified against the Git
blob identifiers reported by the immutable trees, and then treated as inert
data. Candidate Python is never imported or executed as admission authority.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import urllib.parse
from pathlib import Path
from types import ModuleType
from typing import Any

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPORT_SCHEMA = 1
SCRIPT_DIR = Path(__file__).resolve().parent
VERIFIER_PATH = ".github/scripts/verify_hf_repository_parity.py"
CONTROLLER_PATH = ".github/scripts/verify_hf_candidate_admission.py"
CONTRACT_TEST_PATH = "tests/test_hf_candidate_dockerignore_contract.py"
EXPECTED_BASE_INPUTS = (
    "Dockerfile",
    ".well-known/security.txt",
    VERIFIER_PATH,
)
EXPECTED_SUCCESSOR_INPUTS = (
    "Dockerfile",
    ".dockerignore",
    ".well-known/security.txt",
    VERIFIER_PATH,
)
EXPECTED_CHANGED_PATHS = frozenset({VERIFIER_PATH, CONTRACT_TEST_PATH})
DOCKERIGNORE_LINE = b'    ".dockerignore",\n'
DOCKERFILE_PATH = "Dockerfile"
SECURITY_TXT_PATH = ".well-known/security.txt"
PINNED_COPY_SOURCES = (
    "static/shared/szl_command_bar.js",
    "static/shared/szl_command_bar.css",
)
PINNED_COPY_INSERTION = (
    b" static/shared/szl_command_bar.js static/shared/szl_command_bar.css"
)
SHARED_COPY_DESTINATION = b" ./static/shared/\n"
BASE_SHARED_COPY_LINE = (
    b"COPY static/shared/szl_label_engine.js "
    b"static/shared/szl_receipt_cosign.js "
    b"static/shared/szl_codename_sanitizer.js "
    b"static/shared/szl_holo3d.js" + SHARED_COPY_DESTINATION
)
HEAD_SHARED_COPY_LINE = (
    BASE_SHARED_COPY_LINE[: -len(SHARED_COPY_DESTINATION)]
    + PINNED_COPY_INSERTION
    + SHARED_COPY_DESTINATION
)
N25_COPY_SOURCE = "a11oy_n25_organs.py"
N25_COPY_ANCHOR_LINE = b"COPY organ_integrity.py ./organ_integrity.py\n"
N25_COPY_LINE = b"COPY a11oy_n25_organs.py ./a11oy_n25_organs.py\n"
N25_HEAD_COPY_BLOCK = N25_COPY_ANCHOR_LINE + N25_COPY_LINE
REQUIRED_TEST_METHODS = frozenset(
    {
        "clean_candidate_report",
        "test_dockerignore_is_a_protected_candidate_input",
        "test_changed_or_missing_dockerignore_fails_closed",
        "test_dockerignore_cannot_hide_directory_copy_drift_behind_clean_report",
    }
)
REQUIRED_TEST_ATTRIBUTES = frozenset(
    {"validate_protected_candidate_inputs", "validate_candidate_report"}
)
NEGATIVE_ASSERT_ATTRIBUTES = frozenset({"assertRaises", "assertRaisesRegex"})


class AdmissionError(RuntimeError):
    """Raised when protected-base policy cannot admit a candidate."""


def load_verifier(path: Path | None = None) -> ModuleType:
    verifier_path = path or SCRIPT_DIR / "verify_hf_repository_parity.py"
    if not verifier_path.is_file():
        raise AdmissionError("protected-base repository-parity verifier is absent")
    spec = importlib.util.spec_from_file_location(
        "protected_base_verify_hf_repository_parity",
        verifier_path,
    )
    if spec is None or spec.loader is None:
        raise AdmissionError("cannot load protected-base repository-parity verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_blob_oid(source: bytes) -> str:
    """Return the SHA-1 object identifier Git assigns to exact blob bytes."""

    framed = f"blob {len(source)}\0".encode("ascii") + source
    try:
        return hashlib.sha1(framed, usedforsecurity=False).hexdigest()
    except TypeError:  # pragma: no cover - older compatible Python builds
        return hashlib.sha1(framed).hexdigest()


def changed_paths(
    base_tree: dict[str, str],
    head_tree: dict[str, str],
) -> frozenset[str]:
    return frozenset(
        path
        for path in set(base_tree) | set(head_tree)
        if base_tree.get(path) != head_tree.get(path)
    )


def _require_blob(
    tree: dict[str, str],
    path: str,
    *,
    revision: str,
) -> str:
    value = tree.get(path)
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise AdmissionError(f"{revision} tree is missing exact blob {path!r}")
    return value


def require_bound_blob(
    tree: dict[str, str],
    path: str,
    source: bytes,
    *,
    revision: str,
) -> str:
    """Bind fetched bytes to the immutable tree entry before parsing them."""

    expected = _require_blob(tree, path, revision=revision)
    actual = git_blob_oid(source)
    if actual != expected:
        raise AdmissionError(
            f"{revision} bytes for {path!r} do not match immutable tree blob: "
            f"expected={expected} actual={actual}"
        )
    return expected


def validate_base_controlled_inputs(
    base_tree: dict[str, str],
    head_tree: dict[str, str],
) -> None:
    """Keep the controller and Docker build context base-controlled."""

    for path in (CONTROLLER_PATH, ".dockerignore"):
        base_sha = _require_blob(base_tree, path, revision="base")
        head_sha = _require_blob(head_tree, path, revision="candidate")
        if head_sha != base_sha:
            raise AdmissionError(
                f"candidate changed protected admission authority {path!r}; "
                "use a separately reviewed contract successor"
            )


def _candidate_input_assignments(module: ast.Module) -> list[ast.AST]:
    assignments: list[ast.AST] = []
    for statement in module.body:
        if isinstance(statement, ast.Assign):
            if any(
                isinstance(target, ast.Name)
                and target.id == "PROTECTED_CANDIDATE_INPUTS"
                for target in statement.targets
            ):
                assignments.append(statement.value)
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "PROTECTED_CANDIDATE_INPUTS"
            and statement.value is not None
        ):
            assignments.append(statement.value)
    return assignments


def parse_protected_candidate_inputs(source: bytes) -> tuple[str, ...]:
    try:
        text = source.decode("utf-8", errors="strict")
        module = ast.parse(text)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise AdmissionError(
            f"verifier source is not strict valid Python/UTF-8: {exc}"
        ) from exc

    assignments = _candidate_input_assignments(module)
    if len(assignments) != 1:
        raise AdmissionError(
            "verifier must contain exactly one top-level "
            "PROTECTED_CANDIDATE_INPUTS assignment"
        )
    try:
        value = ast.literal_eval(assignments[0])
    except (ValueError, TypeError, SyntaxError) as exc:
        raise AdmissionError(
            "PROTECTED_CANDIDATE_INPUTS must be a literal string tuple"
        ) from exc
    if (
        not isinstance(value, tuple)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise AdmissionError(
            "PROTECTED_CANDIDATE_INPUTS must be a non-empty literal string tuple"
        )
    return value


def validate_verifier_transition(
    base_source: bytes,
    head_source: bytes,
) -> dict[str, Any]:
    base_inputs = parse_protected_candidate_inputs(base_source)
    head_inputs = parse_protected_candidate_inputs(head_source)
    if base_inputs != EXPECTED_BASE_INPUTS:
        raise AdmissionError(
            "protected base does not match the reviewed predecessor input contract"
        )
    if head_inputs != EXPECTED_SUCCESSOR_INPUTS:
        raise AdmissionError(
            "candidate verifier is not the reviewed .dockerignore contract successor"
        )
    if base_source.count(DOCKERIGNORE_LINE) != 0:
        raise AdmissionError("protected base already contains the successor line")
    if head_source.count(DOCKERIGNORE_LINE) != 1:
        raise AdmissionError(
            "candidate must add exactly one canonical .dockerignore tuple line"
        )
    if head_source.replace(DOCKERIGNORE_LINE, b"", 1) != base_source:
        raise AdmissionError(
            "candidate verifier contains changes beyond the one reviewed "
            ".dockerignore line"
        )
    return {
        "base_inputs": list(base_inputs),
        "head_inputs": list(head_inputs),
        "base_sha256": hashlib.sha256(base_source).hexdigest(),
        "head_sha256": hashlib.sha256(head_source).hexdigest(),
        "delta": "exact-one-line-addition",
    }


def validate_contract_test(source: bytes) -> dict[str, str | int]:
    try:
        text = source.decode("utf-8", errors="strict")
        module = ast.parse(text)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise AdmissionError(
            f"contract test is not strict valid Python/UTF-8: {exc}"
        ) from exc

    methods = {
        node.name
        for node in ast.walk(module)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing_methods = sorted(REQUIRED_TEST_METHODS - methods)
    if missing_methods:
        raise AdmissionError(
            f"contract test is missing required methods: {missing_methods}"
        )

    attributes = {
        node.attr for node in ast.walk(module) if isinstance(node, ast.Attribute)
    }
    missing_attributes = sorted(REQUIRED_TEST_ATTRIBUTES - attributes)
    if missing_attributes:
        raise AdmissionError(
            "contract test is missing required verifier calls: "
            f"{missing_attributes}"
        )
    negative_assertions = len(attributes & NEGATIVE_ASSERT_ATTRIBUTES)
    if negative_assertions == 0:
        raise AdmissionError(
            "contract test lacks a fail-closed negative assertion"
        )

    strings = {
        node.value
        for node in ast.walk(module)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    if ".dockerignore" not in strings:
        raise AdmissionError("contract test does not bind the .dockerignore path")

    return {
        "path": CONTRACT_TEST_PATH,
        "sha256": hashlib.sha256(source).hexdigest(),
        "status": "present-and-parseable",
        "negative_assertion_kinds": negative_assertions,
    }


def validate_contract_successor(
    *,
    base_tree: dict[str, str],
    head_tree: dict[str, str],
    base_source: bytes,
    head_source: bytes,
    test_source: bytes,
) -> dict[str, Any]:
    validate_base_controlled_inputs(base_tree, head_tree)
    actual_changed = changed_paths(base_tree, head_tree)
    if actual_changed != EXPECTED_CHANGED_PATHS:
        raise AdmissionError(
            "deployment-contract successor changed an unexpected path set: "
            f"expected={sorted(EXPECTED_CHANGED_PATHS)!r} "
            f"actual={sorted(actual_changed)!r}"
        )

    require_bound_blob(
        base_tree,
        VERIFIER_PATH,
        base_source,
        revision="base",
    )
    require_bound_blob(
        head_tree,
        VERIFIER_PATH,
        head_source,
        revision="candidate",
    )
    if CONTRACT_TEST_PATH in base_tree:
        raise AdmissionError("contract regression must be a new candidate file")
    require_bound_blob(
        head_tree,
        CONTRACT_TEST_PATH,
        test_source,
        revision="candidate",
    )

    transition = validate_verifier_transition(base_source, head_source)
    test = validate_contract_test(test_source)
    return {
        "schema": REPORT_SCHEMA,
        "status": "contract-successor-validated",
        "changed_paths": sorted(actual_changed),
        "verifier": transition,
        "regression": test,
    }


def validate_dockerfile_copy_transition(
    base_source: bytes,
    head_source: bytes,
) -> dict[str, Any]:
    """Admit exactly ÑAWI's shared COPY-line insertion; reject every other edit."""

    if base_source.count(BASE_SHARED_COPY_LINE) != 1:
        raise AdmissionError(
            "protected-base Dockerfile does not contain exactly one pinned "
            "shared COPY line"
        )
    if PINNED_COPY_INSERTION in base_source:
        raise AdmissionError(
            "protected-base Dockerfile already contains the pinned COPY tokens"
        )
    if head_source.count(HEAD_SHARED_COPY_LINE) != 1:
        raise AdmissionError(
            "candidate Dockerfile must contain exactly one shared COPY line "
            "with static/shared/szl_command_bar.js and szl_command_bar.css"
        )
    if head_source.replace(HEAD_SHARED_COPY_LINE, BASE_SHARED_COPY_LINE, 1) != (
        base_source
    ):
        raise AdmissionError(
            "candidate Dockerfile contains changes beyond the pinned "
            "szl_command_bar shared COPY insertion"
        )
    return {
        "base_sha256": hashlib.sha256(base_source).hexdigest(),
        "head_sha256": hashlib.sha256(head_source).hexdigest(),
        "base_blob": git_blob_oid(base_source),
        "head_blob": git_blob_oid(head_source),
        "delta": "exact-shared-copy-insertion",
        "copy_sources": list(PINNED_COPY_SOURCES),
    }


def dockerfile_copy_pin_applicable(base_source: bytes) -> bool:
    """True only while protected base still lacks the two COPY tokens."""

    return (
        PINNED_COPY_INSERTION not in base_source
        and base_source.count(BASE_SHARED_COPY_LINE) == 1
    )


def validate_dockerfile_copy_pin(
    *,
    base_tree: dict[str, str],
    head_tree: dict[str, str],
    base_source: bytes,
    head_source: bytes,
    copy_sources: dict[str, bytes],
) -> dict[str, Any]:
    """Bind the Dockerfile pin and require the two COPY sources as new blobs."""

    validate_base_controlled_inputs(base_tree, head_tree)
    base_dockerfile = _require_blob(
        base_tree, DOCKERFILE_PATH, revision="base"
    )
    head_dockerfile = _require_blob(
        head_tree, DOCKERFILE_PATH, revision="candidate"
    )
    if head_dockerfile == base_dockerfile:
        raise AdmissionError(
            "Dockerfile COPY pin requires a Dockerfile blob change"
        )
    for path in (SECURITY_TXT_PATH, VERIFIER_PATH):
        base_sha = _require_blob(base_tree, path, revision="base")
        head_sha = _require_blob(head_tree, path, revision="candidate")
        if head_sha != base_sha:
            raise AdmissionError(
                f"Dockerfile COPY pin cannot change protected input {path!r}"
            )

    require_bound_blob(
        base_tree,
        DOCKERFILE_PATH,
        base_source,
        revision="base",
    )
    require_bound_blob(
        head_tree,
        DOCKERFILE_PATH,
        head_source,
        revision="candidate",
    )
    transition = validate_dockerfile_copy_transition(base_source, head_source)

    bound_sources: dict[str, str] = {}
    if set(copy_sources) != set(PINNED_COPY_SOURCES):
        raise AdmissionError(
            "Dockerfile COPY pin must bind exactly the two command-bar sources"
        )
    for path in PINNED_COPY_SOURCES:
        if path in base_tree:
            raise AdmissionError(
                f"pinned COPY source must be a new candidate file: {path!r}"
            )
        bound_sources[path] = require_bound_blob(
            head_tree,
            path,
            copy_sources[path],
            revision="candidate",
        )
    return {
        "schema": REPORT_SCHEMA,
        "status": "dockerfile-copy-pin-validated",
        "dockerfile": transition,
        "copy_sources": bound_sources,
    }


def validate_dockerfile_copy_candidate_report(
    report: object,
    *,
    verifier: ModuleType,
    base_ref: str,
    github_repo: str,
    github_ref: str,
    hf_repo: str,
    hf_ref: str,
    base_tree: dict[str, str],
    head_tree: dict[str, str],
    expected_files_compared: int,
) -> list[str]:
    """Admit pinned missing-hf COPY additions plus ordinary review-bound drift."""

    if not isinstance(report, dict):
        raise AdmissionError("candidate comparator report must be an object")
    if base_ref == github_ref:
        raise AdmissionError(
            "candidate head must be a strict descendant of the reviewed "
            "protected base"
        )
    if type(report.get("schema")) is not int or report["schema"] != REPORT_SCHEMA:
        raise AdmissionError(
            f"candidate comparator schema must be the exact integer {REPORT_SCHEMA}"
        )
    if (
        report.get("github_repo") != github_repo
        or report.get("hf_repo") != hf_repo
    ):
        raise AdmissionError(
            "candidate comparator report is not bound to the admitted repositories"
        )
    for counter in ("error_count", "warn_count", "files_compared"):
        if type(report.get(counter)) is not int:
            raise AdmissionError(
                f"candidate comparator {counter} must be an exact integer"
            )
    if report.get("github_ref") != github_ref or report.get("hf_ref") != hf_ref:
        raise AdmissionError(
            "candidate comparator report is not bound to the admitted "
            "immutable revisions"
        )
    expected_head_files = expected_files_compared + len(PINNED_COPY_SOURCES)
    if report["files_compared"] != expected_head_files:
        raise AdmissionError(
            "Dockerfile COPY pin managed-file count must be protected base "
            f"plus {len(PINNED_COPY_SOURCES)}: expected {expected_head_files}, "
            f"received {report['files_compared']}"
        )

    findings = report.get("findings")
    if not isinstance(findings, list) or not all(
        isinstance(finding, dict) for finding in findings
    ):
        raise AdmissionError("candidate comparator findings must be an object array")

    warnings = [finding for finding in findings if finding.get("severity") == "warn"]
    errors = [finding for finding in findings if finding.get("severity") == "error"]
    if len(warnings) != 1:
        raise AdmissionError(
            "candidate comparator must contain one guarded compatibility warning"
        )
    normalized_warning = {
        key: warnings[0].get(key) for key in ("kind", "path", "severity")
    }
    if normalized_warning != verifier.EXPECTED_COMPATIBILITY_WARNING:
        raise AdmissionError(
            f"unexpected candidate comparator warning: {normalized_warning!r}"
        )
    if report["warn_count"] != 1 or report["error_count"] != len(errors):
        raise AdmissionError("candidate comparator counters do not match its findings")
    if len(findings) != len(warnings) + len(errors):
        raise AdmissionError("candidate comparator contains an untyped finding")
    if report.get("status") != "drift" or not errors:
        raise AdmissionError(
            "Dockerfile COPY pin comparator status must be 'drift' with errors"
        )

    reviewed_paths = {
        path
        for path in set(base_tree) | set(head_tree)
        if base_tree.get(path) != head_tree.get(path)
    }
    pinned_missing: list[str] = []
    admitted: list[str] = []
    for finding in errors:
        path = finding.get("path")
        if (
            finding.get("kind") == "missing-hf"
            and finding.get("ahead") == "github"
            and isinstance(path, str)
            and path in PINNED_COPY_SOURCES
        ):
            if path in base_tree or path not in head_tree:
                raise AdmissionError(
                    f"pinned COPY source is not a new candidate blob: {path!r}"
                )
            github_sha = finding.get("github_sha")
            if github_sha is not None and github_sha != head_tree[path]:
                raise AdmissionError(
                    "pinned COPY source github_sha is not bound to the "
                    f"candidate tree: {path!r}"
                )
            if finding.get("hf_oid") not in (None, ""):
                raise AdmissionError(
                    f"pinned COPY source is not missing on Hugging Face: {path!r}"
                )
            pinned_missing.append(path)
            continue
        ahead = finding.get("ahead")
        if (
            finding.get("kind") != "drift"
            or not isinstance(ahead, str)
            or ahead not in verifier.CANDIDATE_AHEAD_VALUES
            or finding.get("lineage_conflict") is not False
            or not isinstance(path, str)
        ):
            raise AdmissionError(
                f"unexplained candidate comparator finding: {finding!r}"
            )
        if (
            path not in reviewed_paths
            or path not in base_tree
            or path not in head_tree
            or path == DOCKERFILE_PATH
            or path in PINNED_COPY_SOURCES
        ):
            raise AdmissionError(
                f"candidate drift is not an exact reviewed byte modification: {path!r}"
            )
        if (
            finding.get("github_sha") != head_tree[path]
            or finding.get("hf_oid") != base_tree[path]
        ):
            raise AdmissionError(
                f"candidate drift hashes are not bound to the reviewed trees: {path!r}"
            )
        admitted.append(path)

    if sorted(pinned_missing) != sorted(PINNED_COPY_SOURCES):
        raise AdmissionError(
            "Dockerfile COPY pin must report missing-hf for exactly "
            f"{list(PINNED_COPY_SOURCES)!r}; received {sorted(pinned_missing)!r}"
        )
    if len(admitted) != len(set(admitted)):
        raise AdmissionError("candidate comparator repeated a drift path")
    return sorted(admitted)



def validate_n25_dockerfile_copy_transition(
    base_source: bytes,
    head_source: bytes,
) -> dict[str, Any]:
    """Admit exactly the N25 module COPY insertion and no other Dockerfile edit."""

    if base_source.count(N25_COPY_ANCHOR_LINE) != 1:
        raise AdmissionError(
            "protected-base Dockerfile does not contain exactly one N25 COPY anchor"
        )
    if N25_COPY_LINE in base_source:
        raise AdmissionError(
            "protected-base Dockerfile already contains the N25 COPY line"
        )
    if head_source.count(N25_HEAD_COPY_BLOCK) != 1:
        raise AdmissionError(
            "candidate Dockerfile must place exactly one N25 COPY line after its anchor"
        )
    if head_source.replace(
        N25_HEAD_COPY_BLOCK,
        N25_COPY_ANCHOR_LINE,
        1,
    ) != base_source:
        raise AdmissionError(
            "candidate Dockerfile contains changes beyond the exact N25 COPY insertion"
        )
    return {
        "base_sha256": hashlib.sha256(base_source).hexdigest(),
        "head_sha256": hashlib.sha256(head_source).hexdigest(),
        "base_blob": git_blob_oid(base_source),
        "head_blob": git_blob_oid(head_source),
        "delta": "exact-n25-copy-insertion",
        "copy_source": N25_COPY_SOURCE,
    }


def n25_dockerfile_copy_pin_applicable(base_source: bytes) -> bool:
    """Return true only while protected base still lacks the N25 COPY line."""

    return (
        N25_COPY_LINE not in base_source
        and base_source.count(N25_COPY_ANCHOR_LINE) == 1
    )


def validate_n25_dockerfile_copy_pin(
    *,
    base_tree: dict[str, str],
    head_tree: dict[str, str],
    base_source: bytes,
    head_source: bytes,
    n25_source: bytes,
) -> dict[str, Any]:
    """Bind the exact Dockerfile transition and unchanged N25 source bytes."""

    validate_base_controlled_inputs(base_tree, head_tree)
    base_dockerfile = _require_blob(
        base_tree,
        DOCKERFILE_PATH,
        revision="base",
    )
    head_dockerfile = _require_blob(
        head_tree,
        DOCKERFILE_PATH,
        revision="candidate",
    )
    if head_dockerfile == base_dockerfile:
        raise AdmissionError("N25 COPY pin requires a Dockerfile blob change")

    for path in (SECURITY_TXT_PATH, VERIFIER_PATH):
        base_sha = _require_blob(base_tree, path, revision="base")
        head_sha = _require_blob(head_tree, path, revision="candidate")
        if head_sha != base_sha:
            raise AdmissionError(
                f"N25 COPY pin cannot change protected input {path!r}"
            )

    base_n25 = _require_blob(base_tree, N25_COPY_SOURCE, revision="base")
    head_n25 = _require_blob(head_tree, N25_COPY_SOURCE, revision="candidate")
    if head_n25 != base_n25:
        raise AdmissionError(
            "N25 COPY successor must not change a11oy_n25_organs.py bytes"
        )

    require_bound_blob(
        base_tree,
        DOCKERFILE_PATH,
        base_source,
        revision="base",
    )
    require_bound_blob(
        head_tree,
        DOCKERFILE_PATH,
        head_source,
        revision="candidate",
    )
    require_bound_blob(
        base_tree,
        N25_COPY_SOURCE,
        n25_source,
        revision="base",
    )
    require_bound_blob(
        head_tree,
        N25_COPY_SOURCE,
        n25_source,
        revision="candidate",
    )
    transition = validate_n25_dockerfile_copy_transition(
        base_source,
        head_source,
    )
    return {
        "schema": REPORT_SCHEMA,
        "status": "n25-dockerfile-copy-pin-validated",
        "dockerfile": transition,
        "copy_source_blob": head_n25,
    }


def validate_n25_dockerfile_copy_candidate_report(
    report: object,
    *,
    verifier: ModuleType,
    base_ref: str,
    github_repo: str,
    github_ref: str,
    hf_repo: str,
    hf_ref: str,
    base_tree: dict[str, str],
    head_tree: dict[str, str],
    expected_files_compared: int,
) -> list[str]:
    """Admit one N25 missing-HF row plus exact review-bound ordinary drift."""

    if not isinstance(report, dict):
        raise AdmissionError("candidate comparator report must be an object")
    if base_ref == github_ref:
        raise AdmissionError(
            "candidate head must be a strict descendant of the reviewed protected base"
        )
    if type(report.get("schema")) is not int or report["schema"] != REPORT_SCHEMA:
        raise AdmissionError(
            f"candidate comparator schema must be the exact integer {REPORT_SCHEMA}"
        )
    if report.get("github_repo") != github_repo or report.get("hf_repo") != hf_repo:
        raise AdmissionError(
            "candidate comparator report is not bound to the admitted repositories"
        )
    for counter in ("error_count", "warn_count", "files_compared"):
        if type(report.get(counter)) is not int:
            raise AdmissionError(
                f"candidate comparator {counter} must be an exact integer"
            )
    if report.get("github_ref") != github_ref or report.get("hf_ref") != hf_ref:
        raise AdmissionError(
            "candidate comparator report is not bound to the admitted immutable revisions"
        )
    expected_head_files = expected_files_compared + 1
    if report["files_compared"] != expected_head_files:
        raise AdmissionError(
            "N25 COPY pin managed-file count must be protected base plus 1: "
            f"expected {expected_head_files}, received {report['files_compared']}"
        )

    findings = report.get("findings")
    if not isinstance(findings, list) or not all(
        isinstance(finding, dict) for finding in findings
    ):
        raise AdmissionError("candidate comparator findings must be an object array")
    warnings = [finding for finding in findings if finding.get("severity") == "warn"]
    errors = [finding for finding in findings if finding.get("severity") == "error"]
    if len(warnings) != 1:
        raise AdmissionError(
            "candidate comparator must contain one guarded compatibility warning"
        )
    normalized_warning = {
        key: warnings[0].get(key) for key in ("kind", "path", "severity")
    }
    if normalized_warning != verifier.EXPECTED_COMPATIBILITY_WARNING:
        raise AdmissionError(
            f"unexpected candidate comparator warning: {normalized_warning!r}"
        )
    if report["warn_count"] != 1 or report["error_count"] != len(errors):
        raise AdmissionError("candidate comparator counters do not match its findings")
    if len(findings) != len(warnings) + len(errors):
        raise AdmissionError("candidate comparator contains an untyped finding")
    if report.get("status") != "drift" or not errors:
        raise AdmissionError(
            "N25 COPY pin comparator status must be 'drift' with errors"
        )

    reviewed_paths = {
        path
        for path in set(base_tree) | set(head_tree)
        if base_tree.get(path) != head_tree.get(path)
    }
    n25_missing: list[str] = []
    admitted: list[str] = []
    for finding in errors:
        path = finding.get("path")
        if (
            finding.get("kind") == "missing-hf"
            and finding.get("ahead") == "github"
            and path == N25_COPY_SOURCE
        ):
            if path not in base_tree or path not in head_tree:
                raise AdmissionError("N25 source must exist in both reviewed trees")
            if base_tree[path] != head_tree[path]:
                raise AdmissionError("N25 source bytes changed in the COPY successor")
            github_sha = finding.get("github_sha")
            if github_sha is not None and github_sha != head_tree[path]:
                raise AdmissionError(
                    "N25 missing-HF finding is not bound to the candidate source blob"
                )
            if finding.get("hf_oid") not in (None, ""):
                raise AdmissionError(
                    "N25 COPY source is not actually missing on Hugging Face"
                )
            n25_missing.append(str(path))
            continue

        ahead = finding.get("ahead")
        if (
            finding.get("kind") != "drift"
            or not isinstance(ahead, str)
            or ahead not in verifier.CANDIDATE_AHEAD_VALUES
            or finding.get("lineage_conflict") is not False
            or not isinstance(path, str)
        ):
            raise AdmissionError(
                f"unexplained candidate comparator finding: {finding!r}"
            )
        if (
            path not in reviewed_paths
            or path not in base_tree
            or path not in head_tree
            or path in {DOCKERFILE_PATH, N25_COPY_SOURCE}
        ):
            raise AdmissionError(
                f"candidate drift is not an exact reviewed byte modification: {path!r}"
            )
        if (
            finding.get("github_sha") != head_tree[path]
            or finding.get("hf_oid") != base_tree[path]
        ):
            raise AdmissionError(
                f"candidate drift hashes are not bound to the reviewed trees: {path!r}"
            )
        admitted.append(path)

    if n25_missing != [N25_COPY_SOURCE]:
        raise AdmissionError(
            "N25 COPY pin must report exactly one missing-HF N25 source row; "
            f"received {n25_missing!r}"
        )
    if len(admitted) != len(set(admitted)):
        raise AdmissionError("candidate comparator repeated a drift path")
    return sorted(admitted)


def prove_n25_dockerfile_copy_pin(
    verifier: ModuleType,
    *,
    tools_script: Path,
    github_repo: str,
    base_ref: str,
    github_ref: str,
    hf_repo: str,
    base_tree: dict[str, str],
    head_tree: dict[str, str],
) -> dict[str, Any]:
    base_source = read_bound_github_file(
        verifier,
        tree=base_tree,
        github_repo=github_repo,
        github_ref=base_ref,
        path=DOCKERFILE_PATH,
        revision="base",
    )
    head_source = read_bound_github_file(
        verifier,
        tree=head_tree,
        github_repo=github_repo,
        github_ref=github_ref,
        path=DOCKERFILE_PATH,
        revision="candidate",
    )
    n25_source = read_bound_github_file(
        verifier,
        tree=head_tree,
        github_repo=github_repo,
        github_ref=github_ref,
        path=N25_COPY_SOURCE,
        revision="candidate",
    )
    semantic = validate_n25_dockerfile_copy_pin(
        base_tree=base_tree,
        head_tree=head_tree,
        base_source=base_source,
        head_source=head_source,
        n25_source=n25_source,
    )

    hf_ref = verifier.resolve_stable_revision(hf_repo)
    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        base_report = run_strict_comparator(
            verifier,
            tools_script=tools_script,
            github_repo=github_repo,
            github_ref=base_ref,
            hf_repo=hf_repo,
            hf_ref=hf_ref,
            report_path=temporary_path / "base.json",
        )
        candidate_report_path = temporary_path / "head.json"
        candidate_run = verifier.run_comparator(
            tools_script=tools_script,
            github_repo=github_repo,
            github_ref=github_ref,
            hf_repo=hf_repo,
            hf_ref=hf_ref,
            report_out=candidate_report_path,
            capture=True,
        )
        try:
            head_report = json.loads(
                candidate_report_path.read_text(encoding="utf-8")
            )
            admitted = validate_n25_dockerfile_copy_candidate_report(
                head_report,
                verifier=verifier,
                base_ref=base_ref,
                github_repo=github_repo,
                github_ref=github_ref,
                hf_repo=hf_repo,
                hf_ref=hf_ref,
                base_tree=base_tree,
                head_tree=head_tree,
                expected_files_compared=base_report["files_compared"],
            )
        except (OSError, json.JSONDecodeError, AdmissionError) as exc:
            if candidate_run.stdout:
                print(candidate_run.stdout, file=sys.stderr)
            if isinstance(exc, AdmissionError):
                raise
            raise AdmissionError(
                f"N25 COPY pin comparator report is invalid: {exc}"
            ) from exc
    if candidate_run.returncode != 1:
        raise AdmissionError(
            "N25 COPY pin comparator exit/report mismatch: "
            f"expected 1, received {candidate_run.returncode}"
        )

    base_dot = verifier.verify_leading_dot_copy(
        github_repo=github_repo,
        github_ref=base_ref,
        hf_repo=hf_repo,
        hf_ref=hf_ref,
    )
    head_dot = verifier.verify_leading_dot_copy(
        github_repo=github_repo,
        github_ref=github_ref,
        hf_repo=hf_repo,
        hf_ref=hf_ref,
    )
    if base_dot != head_dot:
        raise AdmissionError(
            "N25 COPY pin changed the guarded dot-prefixed source"
        )

    semantic.update(
        {
            "base_ref": base_ref,
            "github_ref": github_ref,
            "github_repo": github_repo,
            "hf_ref": hf_ref,
            "hf_repo": hf_repo,
            "files_compared": head_report["files_compared"],
            "base_files_compared": base_report["files_compared"],
            "review_bound_drift_paths": admitted,
            "pinned_copy_source": N25_COPY_SOURCE,
            "leading_dot_sha256": base_dot,
            "proof_status": "base-controlled-n25-dockerfile-copy-pin",
            "admission_status": "ok",
        }
    )
    return semantic

def read_github_file(
    verifier: ModuleType,
    *,
    github_repo: str,
    github_ref: str,
    path: str,
) -> bytes:
    encoded = urllib.parse.quote(path, safe="/")
    url = (
        f"https://raw.githubusercontent.com/{github_repo}/"
        f"{github_ref}/{encoded}"
    )
    try:
        return verifier._read_url(url)
    except Exception as exc:
        raise AdmissionError(
            f"cannot read immutable GitHub source {path!r} "
            f"at {github_ref}: {exc}"
        ) from exc


def read_bound_github_file(
    verifier: ModuleType,
    *,
    tree: dict[str, str],
    github_repo: str,
    github_ref: str,
    path: str,
    revision: str,
) -> bytes:
    source = read_github_file(
        verifier,
        github_repo=github_repo,
        github_ref=github_ref,
        path=path,
    )
    require_bound_blob(tree, path, source, revision=revision)
    return source


def run_strict_comparator(
    verifier: ModuleType,
    *,
    tools_script: Path,
    github_repo: str,
    github_ref: str,
    hf_repo: str,
    hf_ref: str,
    report_path: Path,
) -> dict[str, Any]:
    run = verifier.run_comparator(
        tools_script=tools_script,
        github_repo=github_repo,
        github_ref=github_ref,
        hf_repo=hf_repo,
        hf_ref=hf_ref,
        report_out=report_path,
        capture=True,
    )
    if run.returncode != 0:
        if run.stdout:
            print(run.stdout, file=sys.stderr)
        raise AdmissionError(
            "strict comparator exited non-zero for immutable revision "
            f"{github_ref}"
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        verifier.validate_report(
            report,
            github_repo=github_repo,
            github_ref=github_ref,
            hf_repo=hf_repo,
            hf_ref=hf_ref,
        )
    except Exception as exc:
        if run.stdout:
            print(run.stdout, file=sys.stderr)
        raise AdmissionError(
            f"strict comparator report is invalid: {exc}"
        ) from exc
    return report


def prove_contract_successor(
    verifier: ModuleType,
    *,
    tools_script: Path,
    github_repo: str,
    base_ref: str,
    github_ref: str,
    hf_repo: str,
    base_tree: dict[str, str],
    head_tree: dict[str, str],
) -> dict[str, Any]:
    base_source = read_bound_github_file(
        verifier,
        tree=base_tree,
        github_repo=github_repo,
        github_ref=base_ref,
        path=VERIFIER_PATH,
        revision="base",
    )
    head_source = read_bound_github_file(
        verifier,
        tree=head_tree,
        github_repo=github_repo,
        github_ref=github_ref,
        path=VERIFIER_PATH,
        revision="candidate",
    )
    test_source = read_bound_github_file(
        verifier,
        tree=head_tree,
        github_repo=github_repo,
        github_ref=github_ref,
        path=CONTRACT_TEST_PATH,
        revision="candidate",
    )
    semantic = validate_contract_successor(
        base_tree=base_tree,
        head_tree=head_tree,
        base_source=base_source,
        head_source=head_source,
        test_source=test_source,
    )

    hf_ref = verifier.resolve_stable_revision(hf_repo)
    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        base_report = run_strict_comparator(
            verifier,
            tools_script=tools_script,
            github_repo=github_repo,
            github_ref=base_ref,
            hf_repo=hf_repo,
            hf_ref=hf_ref,
            report_path=temporary_path / "base.json",
        )
        head_report = run_strict_comparator(
            verifier,
            tools_script=tools_script,
            github_repo=github_repo,
            github_ref=github_ref,
            hf_repo=hf_repo,
            hf_ref=hf_ref,
            report_path=temporary_path / "head.json",
        )
    if head_report["files_compared"] != base_report["files_compared"]:
        raise AdmissionError(
            "contract successor changed the managed deployed-file cardinality"
        )

    base_dot = verifier.verify_leading_dot_copy(
        github_repo=github_repo,
        github_ref=base_ref,
        hf_repo=hf_repo,
        hf_ref=hf_ref,
    )
    head_dot = verifier.verify_leading_dot_copy(
        github_repo=github_repo,
        github_ref=github_ref,
        hf_repo=hf_repo,
        hf_ref=hf_ref,
    )
    if base_dot != head_dot:
        raise AdmissionError(
            "contract successor changed the guarded dot-prefixed source"
        )

    semantic.update(
        {
            "base_ref": base_ref,
            "github_ref": github_ref,
            "github_repo": github_repo,
            "hf_ref": hf_ref,
            "hf_repo": hf_repo,
            "files_compared": base_report["files_compared"],
            "leading_dot_sha256": base_dot,
            "proof_status": "base-controlled-protected-contract-successor",
        }
    )
    return semantic


def prove_dockerfile_copy_pin(
    verifier: ModuleType,
    *,
    tools_script: Path,
    github_repo: str,
    base_ref: str,
    github_ref: str,
    hf_repo: str,
    base_tree: dict[str, str],
    head_tree: dict[str, str],
) -> dict[str, Any]:
    base_source = read_bound_github_file(
        verifier,
        tree=base_tree,
        github_repo=github_repo,
        github_ref=base_ref,
        path=DOCKERFILE_PATH,
        revision="base",
    )
    head_source = read_bound_github_file(
        verifier,
        tree=head_tree,
        github_repo=github_repo,
        github_ref=github_ref,
        path=DOCKERFILE_PATH,
        revision="candidate",
    )
    copy_sources = {
        path: read_bound_github_file(
            verifier,
            tree=head_tree,
            github_repo=github_repo,
            github_ref=github_ref,
            path=path,
            revision="candidate",
        )
        for path in PINNED_COPY_SOURCES
    }
    semantic = validate_dockerfile_copy_pin(
        base_tree=base_tree,
        head_tree=head_tree,
        base_source=base_source,
        head_source=head_source,
        copy_sources=copy_sources,
    )

    hf_ref = verifier.resolve_stable_revision(hf_repo)
    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        base_report = run_strict_comparator(
            verifier,
            tools_script=tools_script,
            github_repo=github_repo,
            github_ref=base_ref,
            hf_repo=hf_repo,
            hf_ref=hf_ref,
            report_path=temporary_path / "base.json",
        )
        candidate_report_path = temporary_path / "head.json"
        candidate_run = verifier.run_comparator(
            tools_script=tools_script,
            github_repo=github_repo,
            github_ref=github_ref,
            hf_repo=hf_repo,
            hf_ref=hf_ref,
            report_out=candidate_report_path,
            capture=True,
        )
        try:
            head_report = json.loads(candidate_report_path.read_text(encoding="utf-8"))
            admitted = validate_dockerfile_copy_candidate_report(
                head_report,
                verifier=verifier,
                base_ref=base_ref,
                github_repo=github_repo,
                github_ref=github_ref,
                hf_repo=hf_repo,
                hf_ref=hf_ref,
                base_tree=base_tree,
                head_tree=head_tree,
                expected_files_compared=base_report["files_compared"],
            )
        except (OSError, json.JSONDecodeError, AdmissionError) as exc:
            if candidate_run.stdout:
                print(candidate_run.stdout, file=sys.stderr)
            if isinstance(exc, AdmissionError):
                raise
            raise AdmissionError(
                f"Dockerfile COPY pin comparator report is invalid: {exc}"
            ) from exc
    if candidate_run.returncode != 1:
        raise AdmissionError(
            "Dockerfile COPY pin comparator exit/report mismatch: "
            f"expected 1, received {candidate_run.returncode}"
        )

    base_dot = verifier.verify_leading_dot_copy(
        github_repo=github_repo,
        github_ref=base_ref,
        hf_repo=hf_repo,
        hf_ref=hf_ref,
    )
    head_dot = verifier.verify_leading_dot_copy(
        github_repo=github_repo,
        github_ref=github_ref,
        hf_repo=hf_repo,
        hf_ref=hf_ref,
    )
    if base_dot != head_dot:
        raise AdmissionError(
            "Dockerfile COPY pin changed the guarded dot-prefixed source"
        )

    semantic.update(
        {
            "base_ref": base_ref,
            "github_ref": github_ref,
            "github_repo": github_repo,
            "hf_ref": hf_ref,
            "hf_repo": hf_repo,
            "files_compared": head_report["files_compared"],
            "base_files_compared": base_report["files_compared"],
            "review_bound_drift_paths": admitted,
            "pinned_copy_sources": list(PINNED_COPY_SOURCES),
            "leading_dot_sha256": base_dot,
            "proof_status": "base-controlled-dockerfile-copy-pin",
            "admission_status": "ok",
        }
    )
    return semantic


def delegate_ordinary_candidate(
    verifier: ModuleType,
    *,
    tools_script: Path,
    github_repo: str,
    base_ref: str,
    github_ref: str,
    hf_repo: str,
    report_out: Path,
) -> int:
    return verifier.main(
        [
            "--tools-script",
            str(tools_script),
            "--github-repo",
            github_repo,
            "--base-ref",
            base_ref,
            "--github-ref",
            github_ref,
            "--hf-repo",
            hf_repo,
            "--report-out",
            str(report_out),
        ]
    )


def _write_failure_report(
    report_out: Path,
    *,
    base_ref: str,
    github_ref: str,
    error: Exception,
) -> None:
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(
        json.dumps(
            {
                "schema": REPORT_SCHEMA,
                "status": "rejected",
                "proof_status": "failed-closed",
                "base_ref": base_ref,
                "github_ref": github_ref,
                "error_type": type(error).__name__,
                "error": str(error),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _execute(args: argparse.Namespace) -> int:
    verifier = load_verifier()
    if not args.tools_script.is_file():
        raise AdmissionError("pinned comparator script is absent")
    if not SHA_RE.fullmatch(args.base_ref) or not SHA_RE.fullmatch(
        args.github_ref
    ):
        raise AdmissionError(
            "base and candidate refs must be exact lowercase "
            "40-character SHAs"
        )
    if args.base_ref == args.github_ref:
        raise AdmissionError(
            "candidate head must be a strict descendant of protected base"
        )

    args.report_out.unlink(missing_ok=True)
    verifier.verify_ancestry(
        args.github_repo,
        base_ref=args.base_ref,
        github_ref=args.github_ref,
    )
    base_tree = verifier.github_blob_tree(
        args.github_repo,
        github_ref=args.base_ref,
    )
    head_tree = verifier.github_blob_tree(
        args.github_repo,
        github_ref=args.github_ref,
    )
    validate_base_controlled_inputs(base_tree, head_tree)

    verifier_unchanged = base_tree.get(VERIFIER_PATH) == head_tree.get(
        VERIFIER_PATH
    )
    dockerfile_changed = base_tree.get(DOCKERFILE_PATH) != head_tree.get(
        DOCKERFILE_PATH
    )
    if verifier_unchanged and dockerfile_changed:
        base_dockerfile = read_bound_github_file(
            verifier,
            tree=base_tree,
            github_repo=args.github_repo,
            github_ref=args.base_ref,
            path=DOCKERFILE_PATH,
            revision="base",
        )
        if dockerfile_copy_pin_applicable(base_dockerfile):
            report = prove_dockerfile_copy_pin(
                verifier,
                tools_script=args.tools_script,
                github_repo=args.github_repo,
                base_ref=args.base_ref,
                github_ref=args.github_ref,
                hf_repo=args.hf_repo,
                base_tree=base_tree,
                head_tree=head_tree,
            )
            args.report_out.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(
                "HF Dockerfile COPY pin admitted: "
                f"base={args.base_ref} head={args.github_ref} "
                f"hf={report['hf_ref']} "
                f"copy_sources={len(PINNED_COPY_SOURCES)} "
                f"review_bound={len(report['review_bound_drift_paths'])}"
            )
            for path in PINNED_COPY_SOURCES:
                print(f"::notice title=Pinned HF Dockerfile COPY source::{path}")
            for path in report["review_bound_drift_paths"]:
                print(f"::notice title=Review-bound HF candidate drift::{path}")
            return 0
        if n25_dockerfile_copy_pin_applicable(base_dockerfile):
            report = prove_n25_dockerfile_copy_pin(
                verifier,
                tools_script=args.tools_script,
                github_repo=args.github_repo,
                base_ref=args.base_ref,
                github_ref=args.github_ref,
                hf_repo=args.hf_repo,
                base_tree=base_tree,
                head_tree=head_tree,
            )
            args.report_out.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(
                "HF N25 Dockerfile COPY pin admitted: "
                f"base={args.base_ref} head={args.github_ref} "
                f"hf={report['hf_ref']} "
                f"review_bound={len(report['review_bound_drift_paths'])}"
            )
            print(
                f"::notice title=Pinned HF N25 Dockerfile COPY source::{N25_COPY_SOURCE}"
            )
            for path in report["review_bound_drift_paths"]:
                print(f"::notice title=Review-bound HF candidate drift::{path}")
            return 0
        return delegate_ordinary_candidate(
            verifier,
            tools_script=args.tools_script,
            github_repo=args.github_repo,
            base_ref=args.base_ref,
            github_ref=args.github_ref,
            hf_repo=args.hf_repo,
            report_out=args.report_out,
        )

    if verifier_unchanged:
        return delegate_ordinary_candidate(
            verifier,
            tools_script=args.tools_script,
            github_repo=args.github_repo,
            base_ref=args.base_ref,
            github_ref=args.github_ref,
            hf_repo=args.hf_repo,
            report_out=args.report_out,
        )

    report = prove_contract_successor(
        verifier,
        tools_script=args.tools_script,
        github_repo=args.github_repo,
        base_ref=args.base_ref,
        github_ref=args.github_ref,
        hf_repo=args.hf_repo,
        base_tree=base_tree,
        head_tree=head_tree,
    )
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "HF protected-contract successor admitted: "
        f"base={args.base_ref} head={args.github_ref} "
        f"hf={report['hf_ref']}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools-script", type=Path, required=True)
    parser.add_argument("--github-repo", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--github-ref", required=True)
    parser.add_argument("--hf-repo", required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        return _execute(args)
    except Exception as exc:
        _write_failure_report(
            args.report_out,
            base_ref=args.base_ref,
            github_ref=args.github_ref,
            error=exc,
        )
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
