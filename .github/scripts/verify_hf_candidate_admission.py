#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Base-controlled admission for Hugging Face deployment-contract successors.

Normal pull requests are delegated to the protected-base repository-parity
verifier. A pull request that changes that verifier cannot execute candidate
code as its own authority, so this controller admits one narrowly defined
successor: adding ``.dockerignore`` to ``PROTECTED_CANDIDATE_INPUTS`` together
with its focused adversarial regression.

The controller itself is always executed from the exact protected-base
checkout. Candidate source is treated only as untrusted data.
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


class AdmissionError(RuntimeError):
    """Raised when a candidate cannot be admitted by protected-base policy."""


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


def validate_base_controlled_inputs(
    base_tree: dict[str, str],
    head_tree: dict[str, str],
) -> None:
    """Keep controller and Docker build-context semantics base-controlled."""

    for path in (CONTROLLER_PATH, ".dockerignore"):
        base_sha = _require_blob(base_tree, path, revision="base")
        head_sha = _require_blob(head_tree, path, revision="candidate")
        if head_sha != base_sha:
            raise AdmissionError(
                f"candidate changed protected admission authority {path!r}; "
                "use a separately reviewed contract successor"
            )


def parse_protected_candidate_inputs(source: bytes) -> tuple[str, ...]:
    try:
        text = source.decode("utf-8", errors="strict")
        module = ast.parse(text)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise AdmissionError(
            f"verifier source is not strict valid Python/UTF-8: {exc}"
        ) from exc

    assignments: list[ast.AST] = []
    for statement in module.body:
        if not isinstance(statement, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name)
            and target.id == "PROTECTED_CANDIDATE_INPUTS"
            for target in statement.targets
        ):
            assignments.append(statement.value)
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


def validate_contract_test(source: bytes) -> dict[str, str]:
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
        node.attr
        for node in ast.walk(module)
        if isinstance(node, ast.Attribute)
    }
    missing_attributes = sorted(REQUIRED_TEST_ATTRIBUTES - attributes)
    if missing_attributes:
        raise AdmissionError(
            "contract test is missing required verifier calls: "
            f"{missing_attributes}"
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

    base_verifier_sha = _require_blob(base_tree, VERIFIER_PATH, revision="base")
    head_verifier_sha = _require_blob(
        head_tree,
        VERIFIER_PATH,
        revision="candidate",
    )
    if base_verifier_sha == head_verifier_sha:
        raise AdmissionError("candidate verifier blob did not change")
    if CONTRACT_TEST_PATH in base_tree:
        raise AdmissionError("contract regression must be a new candidate file")
    _require_blob(head_tree, CONTRACT_TEST_PATH, revision="candidate")

    transition = validate_verifier_transition(base_source, head_source)
    test = validate_contract_test(test_source)
    return {
        "schema": REPORT_SCHEMA,
        "status": "contract-successor-validated",
        "changed_paths": sorted(actual_changed),
        "verifier": transition,
        "regression": test,
    }


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
    base_source = read_github_file(
        verifier,
        github_repo=github_repo,
        github_ref=base_ref,
        path=VERIFIER_PATH,
    )
    head_source = read_github_file(
        verifier,
        github_repo=github_repo,
        github_ref=github_ref,
        path=VERIFIER_PATH,
    )
    test_source = read_github_file(
        verifier,
        github_repo=github_repo,
        github_ref=github_ref,
        path=CONTRACT_TEST_PATH,
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

    if base_tree.get(VERIFIER_PATH) == head_tree.get(VERIFIER_PATH):
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
