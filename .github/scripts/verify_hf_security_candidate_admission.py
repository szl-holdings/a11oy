#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Base-controlled admission for the exact RFC 9116 security.txt successor.

This module is intended to execute only from an immutable protected-base
checkout. Candidate Python is never imported. Candidate bytes are fetched at
exact commit SHAs, rebound to their immutable Git tree object IDs, and treated
as inert data.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_CONTROLLER_PATH = SCRIPT_DIR / "verify_hf_candidate_admission.py"
SECURITY_PATH = ".well-known/security.txt"
SECURITY_CONTROLLER_REPO_PATH = (
    ".github/scripts/verify_hf_security_candidate_admission.py"
)
SELECTOR_REPO_PATH = ".github/scripts/select_hf_candidate_admission.py"
EXPECTED_BASE_SHA256 = (
    "7f947d80da93c571ca3a668dcc21ea71bddece1a0ae05ce8152739c7e34cff88"
)
EXPECTED_HEAD_SHA256 = (
    "4815756539b74623f7b4424b36edee4b3d34a6881e3f89179ed022224dd3c888"
)
EXPECTED_CONTACTS = (
    "Contact: https://github.com/szl-holdings/a11oy/security/advisories/new",
    "Contact: mailto:security@szlholdings.com",
)
EXPECTED_CANONICAL = "Canonical: https://a-11-oy.com/.well-known/security.txt"
EXPECTED_POLICY = (
    "Policy: https://github.com/szl-holdings/a11oy/blob/main/SECURITY.md"
)
DEAD_TOKENS = ("szlholdings.ai", "Encryption:", "Hiring:")
REPORT_SCHEMA = 1


class AdmissionError(RuntimeError):
    """Raised when the exact protected security-file successor cannot be proved."""


def _load_module(name: str, path: Path) -> ModuleType:
    if not path.is_file():
        raise AdmissionError(f"protected-base module is absent: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AdmissionError(f"cannot load protected-base module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_base_controller() -> ModuleType:
    return _load_module(
        "protected_base_verify_hf_candidate_admission",
        BASE_CONTROLLER_PATH,
    )


def sha256(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def validate_exact_security_transition(
    base_source: bytes,
    head_source: bytes,
) -> dict[str, Any]:
    """Admit exactly the reviewed dead-contact -> reachable-contact transition."""

    base_digest = sha256(base_source)
    head_digest = sha256(head_source)
    if base_digest != EXPECTED_BASE_SHA256:
        raise AdmissionError(
            "protected base security.txt is not the reviewed predecessor: "
            f"expected={EXPECTED_BASE_SHA256} actual={base_digest}"
        )
    if head_digest != EXPECTED_HEAD_SHA256:
        raise AdmissionError(
            "candidate security.txt is not the reviewed RFC 9116 successor: "
            f"expected={EXPECTED_HEAD_SHA256} actual={head_digest}"
        )

    try:
        text = head_source.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AdmissionError("candidate security.txt is not strict UTF-8") from exc
    lines = text.splitlines()
    contacts = tuple(line for line in lines if line.startswith("Contact:"))
    if contacts != EXPECTED_CONTACTS:
        raise AdmissionError(
            "candidate security.txt contacts are not the reviewed preference order"
        )
    if EXPECTED_CANONICAL not in lines or EXPECTED_POLICY not in lines:
        raise AdmissionError(
            "candidate security.txt lost the canonical origin or disclosure policy"
        )
    for token in DEAD_TOKENS:
        if token in text:
            raise AdmissionError(
                f"candidate security.txt retains forbidden unavailable field {token!r}"
            )
    if not text.endswith("\n"):
        raise AdmissionError("candidate security.txt must end with one LF")

    return {
        "path": SECURITY_PATH,
        "base_sha256": base_digest,
        "head_sha256": head_digest,
        "transition": "exact-reviewed-rfc9116-contact-successor",
        "contacts": list(contacts),
        "canonical": EXPECTED_CANONICAL.removeprefix("Canonical: "),
        "policy": EXPECTED_POLICY.removeprefix("Policy: "),
        "encryption_advertised": False,
    }


def validate_control_plane(
    base_controller: ModuleType,
    verifier: ModuleType,
    *,
    base_tree: dict[str, str],
    head_tree: dict[str, str],
) -> None:
    """Require every admission authority to remain byte-identical to base."""

    base_controller.validate_base_controlled_inputs(base_tree, head_tree)
    immutable_paths = (
        base_controller.VERIFIER_PATH,
        base_controller.CONTROLLER_PATH,
        SECURITY_CONTROLLER_REPO_PATH,
        SELECTOR_REPO_PATH,
        ".dockerignore",
        "Dockerfile",
    )
    for path in immutable_paths:
        base_blob = base_controller._require_blob(
            base_tree, path, revision="base"
        )
        head_blob = base_controller._require_blob(
            head_tree, path, revision="candidate"
        )
        if head_blob != base_blob:
            raise AdmissionError(
                f"security successor changed protected admission authority {path!r}"
            )

    protected_inputs = tuple(verifier.PROTECTED_CANDIDATE_INPUTS)
    changed_protected = sorted(
        path
        for path in protected_inputs
        if base_tree.get(path) != head_tree.get(path)
    )
    if changed_protected != [SECURITY_PATH]:
        raise AdmissionError(
            "security successor must change exactly one protected input: "
            f"expected={[SECURITY_PATH]!r} actual={changed_protected!r}"
        )


def validate_candidate_report(
    report: object,
    *,
    verifier: ModuleType,
    github_repo: str,
    base_ref: str,
    github_ref: str,
    hf_repo: str,
    hf_ref: str,
    base_tree: dict[str, str],
    head_tree: dict[str, str],
    expected_files_compared: int,
) -> list[str]:
    """Require every comparator-visible source to remain exactly at base parity.

    The pinned comparator retains a guarded compatibility warning for the
    dot-prefixed security source.  Its bytes are therefore proved separately
    with ``verify_leading_dot_copy`` before this report is admitted.
    """

    if not isinstance(report, dict):
        raise AdmissionError("candidate comparator report must be an object")
    expected_identity = {
        "schema": REPORT_SCHEMA,
        "github_repo": github_repo,
        "github_ref": github_ref,
        "hf_repo": hf_repo,
        "hf_ref": hf_ref,
    }
    for key, expected in expected_identity.items():
        if report.get(key) != expected:
            raise AdmissionError(
                f"candidate comparator {key} is not bound to the admitted identity"
            )
    for counter in ("error_count", "warn_count", "files_compared"):
        if type(report.get(counter)) is not int:
            raise AdmissionError(
                f"candidate comparator {counter} must be an exact integer"
            )
    if report["files_compared"] != expected_files_compared:
        raise AdmissionError(
            "security successor changed managed-file cardinality: "
            f"expected={expected_files_compared} actual={report['files_compared']}"
        )

    findings = report.get("findings")
    if not isinstance(findings, list) or not all(
        isinstance(item, dict) for item in findings
    ):
        raise AdmissionError("candidate comparator findings must be an object array")
    warnings = [item for item in findings if item.get("severity") == "warn"]
    errors = [item for item in findings if item.get("severity") == "error"]
    if len(warnings) != 1:
        raise AdmissionError(
            "candidate comparator must retain exactly one compatibility warning"
        )
    normalized_warning = {
        key: warnings[0].get(key) for key in ("kind", "path", "severity")
    }
    if normalized_warning != verifier.EXPECTED_COMPATIBILITY_WARNING:
        raise AdmissionError(
            f"candidate comparator returned an unexpected warning: {normalized_warning!r}"
        )
    if report["warn_count"] != 1 or report["error_count"] != len(errors):
        raise AdmissionError("candidate comparator counters do not match findings")
    if len(findings) != len(warnings) + len(errors):
        raise AdmissionError("candidate comparator contains an untyped finding")
    if errors:
        raise AdmissionError(
            "security successor comparator reported drift outside the explicit "
            "dot-prefixed security proof"
        )
    if report.get("status") != "ok":
        raise AdmissionError(
            "security successor comparator must remain clean outside the explicit "
            "dot-prefixed security proof"
        )
    base_security = base_tree.get(SECURITY_PATH)
    head_security = head_tree.get(SECURITY_PATH)
    if (
        not isinstance(base_security, str)
        or not isinstance(head_security, str)
        or base_security == head_security
    ):
        raise AdmissionError(
            "security successor trees do not bind one changed dot-prefixed source"
        )
    return []


def prove_security_successor(
    *,
    tools_script: Path,
    github_repo: str,
    base_ref: str,
    github_ref: str,
    hf_repo: str,
) -> dict[str, Any]:
    base_controller = load_base_controller()
    verifier = base_controller.load_verifier()
    if not base_controller.SHA_RE.fullmatch(base_ref) or not (
        base_controller.SHA_RE.fullmatch(github_ref)
    ):
        raise AdmissionError("base and candidate refs must be exact lowercase SHAs")
    if base_ref == github_ref:
        raise AdmissionError("candidate head must descend from protected base")
    if not tools_script.is_file():
        raise AdmissionError("pinned comparator script is absent")

    verifier.verify_ancestry(
        github_repo,
        base_ref=base_ref,
        github_ref=github_ref,
    )
    base_tree = verifier.github_blob_tree(github_repo, github_ref=base_ref)
    head_tree = verifier.github_blob_tree(github_repo, github_ref=github_ref)
    validate_control_plane(
        base_controller,
        verifier,
        base_tree=base_tree,
        head_tree=head_tree,
    )

    base_source = base_controller.read_bound_github_file(
        verifier,
        tree=base_tree,
        github_repo=github_repo,
        github_ref=base_ref,
        path=SECURITY_PATH,
        revision="base",
    )
    head_source = base_controller.read_bound_github_file(
        verifier,
        tree=head_tree,
        github_repo=github_repo,
        github_ref=github_ref,
        path=SECURITY_PATH,
        revision="candidate",
    )
    transition = validate_exact_security_transition(base_source, head_source)

    hf_ref = verifier.resolve_stable_revision(hf_repo)
    base_dot_sha256 = verifier.verify_leading_dot_copy(
        github_repo=github_repo,
        github_ref=base_ref,
        hf_repo=hf_repo,
        hf_ref=hf_ref,
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        base_report = base_controller.run_strict_comparator(
            verifier,
            tools_script=tools_script,
            github_repo=github_repo,
            github_ref=base_ref,
            hf_repo=hf_repo,
            hf_ref=hf_ref,
            report_path=root / "base.json",
        )
        candidate_path = root / "candidate.json"
        candidate_run = verifier.run_comparator(
            tools_script=tools_script,
            github_repo=github_repo,
            github_ref=github_ref,
            hf_repo=hf_repo,
            hf_ref=hf_ref,
            report_out=candidate_path,
            capture=True,
        )
        try:
            candidate_report = json.loads(
                candidate_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            if candidate_run.stdout:
                print(candidate_run.stdout)
            raise AdmissionError(
                f"candidate comparator report is unreadable: {exc}"
            ) from exc
        comparator_drift_paths = validate_candidate_report(
            candidate_report,
            verifier=verifier,
            github_repo=github_repo,
            base_ref=base_ref,
            github_ref=github_ref,
            hf_repo=hf_repo,
            hf_ref=hf_ref,
            base_tree=base_tree,
            head_tree=head_tree,
            expected_files_compared=base_report["files_compared"],
        )
    if candidate_run.returncode != 0:
        raise AdmissionError(
            "security successor comparator exit/report mismatch: "
            f"expected=0 actual={candidate_run.returncode}"
        )

    return {
        "schema": REPORT_SCHEMA,
        "status": "security-successor-validated",
        "proof_status": "base-controlled-protected-security-successor",
        "admission_status": "ok",
        "github_repo": github_repo,
        "base_ref": base_ref,
        "github_ref": github_ref,
        "hf_repo": hf_repo,
        "hf_ref": hf_ref,
        "files_compared": base_report["files_compared"],
        "base_leading_dot_copy": {
            "path": SECURITY_PATH,
            "sha256": base_dot_sha256,
            "status": "exact",
        },
        "security_transition": transition,
        "comparator_drift_paths": comparator_drift_paths,
        "review_bound_drift_paths": [SECURITY_PATH],
    }


def _write_failure(
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools-script", type=Path, required=True)
    parser.add_argument("--github-repo", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--github-ref", required=True)
    parser.add_argument("--hf-repo", required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args(argv)

    args.report_out.unlink(missing_ok=True)
    try:
        report = prove_security_successor(
            tools_script=args.tools_script,
            github_repo=args.github_repo,
            base_ref=args.base_ref,
            github_ref=args.github_ref,
            hf_repo=args.hf_repo,
        )
    except Exception as exc:
        _write_failure(
            args.report_out,
            base_ref=args.base_ref,
            github_ref=args.github_ref,
            error=exc,
        )
        raise
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "HF protected security successor admitted: "
        f"base={args.base_ref} head={args.github_ref} hf={report['hf_ref']}"
    )
    for path in report["review_bound_drift_paths"]:
        print(f"::notice title=Review-bound HF security successor drift::{path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
