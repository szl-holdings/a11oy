#!/usr/bin/env python3
"""Materialize the exact protected N25 Dockerfile COPY successor.

This helper is inert control-branch tooling. It edits a clean checkout of the
pre-created target branch. The workflow validates the result and creates the
reviewable GitHub-native commit.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path.cwd()
CONTROLLER = ROOT / ".github" / "scripts" / "verify_hf_candidate_admission.py"
DOCKERFILE = ROOT / "Dockerfile"
TEST_FILE = ROOT / "tests" / "test_verify_hf_n25_copy_admission.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, observed {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


CONSTANT_MARKER = '''HEAD_SHARED_COPY_LINE = (
    BASE_SHARED_COPY_LINE[: -len(SHARED_COPY_DESTINATION)]
    + PINNED_COPY_INSERTION
    + SHARED_COPY_DESTINATION
)
REQUIRED_TEST_METHODS = frozenset(
'''
CONSTANT_REPLACEMENT = '''HEAD_SHARED_COPY_LINE = (
    BASE_SHARED_COPY_LINE[: -len(SHARED_COPY_DESTINATION)]
    + PINNED_COPY_INSERTION
    + SHARED_COPY_DESTINATION
)
N25_COPY_SOURCE = "a11oy_n25_organs.py"
N25_COPY_ANCHOR_LINE = b"COPY organ_integrity.py ./organ_integrity.py\\n"
N25_COPY_LINE = b"COPY a11oy_n25_organs.py ./a11oy_n25_organs.py\\n"
N25_HEAD_COPY_BLOCK = N25_COPY_ANCHOR_LINE + N25_COPY_LINE
REQUIRED_TEST_METHODS = frozenset(
'''
replace_once(CONTROLLER, CONSTANT_MARKER, CONSTANT_REPLACEMENT)

FUNCTION_MARKER = "\ndef read_github_file(\n"
FUNCTION_BLOCK = r'''

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
'''
replace_once(
    CONTROLLER,
    FUNCTION_MARKER,
    FUNCTION_BLOCK + FUNCTION_MARKER,
)

ROUTE_MARKER = '''            for path in report["review_bound_drift_paths"]:
                print(f"::notice title=Review-bound HF candidate drift::{path}")
            return 0
        return delegate_ordinary_candidate(
'''
ROUTE_REPLACEMENT = '''            for path in report["review_bound_drift_paths"]:
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
                json.dumps(report, indent=2, sort_keys=True) + "\\n",
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
'''
replace_once(CONTROLLER, ROUTE_MARKER, ROUTE_REPLACEMENT)

DOCKER_ANCHOR = "COPY organ_integrity.py ./organ_integrity.py\n"
DOCKER_REPLACEMENT = (
    DOCKER_ANCHOR
    + "COPY a11oy_n25_organs.py ./a11oy_n25_organs.py\n"
)
replace_once(DOCKERFILE, DOCKER_ANCHOR, DOCKER_REPLACEMENT)

if TEST_FILE.exists():
    raise SystemExit(f"refusing to overwrite existing test: {TEST_FILE}")
TEST_FILE.write_text(
    r'''from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "verify_hf_candidate_admission.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_hf_candidate_admission_n25",
    SCRIPT,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

CONTROLLER_SOURCE = b"protected controller\n"
DOCKERIGNORE_SOURCE = b"# build context\n"
VERIFIER_SOURCE = b"protected verifier\n"
SECURITY_SOURCE = b"Contact: security@example.invalid\n"
N25_SOURCE = b"# exact unchanged N25 source\n"
COMPAT_WARNING = {
    "kind": "missing-both",
    "path": "well-known/security.txt",
    "severity": "warn",
}
FAKE_VERIFIER_CONSTANTS = SimpleNamespace(
    EXPECTED_COMPATIBILITY_WARNING=COMPAT_WARNING,
    CANDIDATE_AHEAD_VALUES=frozenset(
        {"github", "github?", "huggingface", "huggingface?", "tied", "unknown"}
    ),
)


def oid(source: bytes) -> str:
    return MODULE.git_blob_oid(source)


def sample_dockerfiles() -> tuple[bytes, bytes]:
    prefix = b"FROM python:3.12-slim\n"
    suffix = b"EXPOSE 7860\n"
    return (
        prefix + MODULE.N25_COPY_ANCHOR_LINE + suffix,
        prefix + MODULE.N25_HEAD_COPY_BLOCK + suffix,
    )


def n25_pin_trees(
    *,
    extra_head: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str], bytes, bytes]:
    base_dockerfile, head_dockerfile = sample_dockerfiles()
    base = {
        MODULE.CONTROLLER_PATH: oid(CONTROLLER_SOURCE),
        ".dockerignore": oid(DOCKERIGNORE_SOURCE),
        MODULE.VERIFIER_PATH: oid(VERIFIER_SOURCE),
        MODULE.SECURITY_TXT_PATH: oid(SECURITY_SOURCE),
        MODULE.DOCKERFILE_PATH: oid(base_dockerfile),
        MODULE.N25_COPY_SOURCE: oid(N25_SOURCE),
    }
    head = dict(base)
    head[MODULE.DOCKERFILE_PATH] = oid(head_dockerfile)
    if extra_head:
        head.update(extra_head)
    return base, head, base_dockerfile, head_dockerfile


def candidate_report(
    *,
    github_ref: str,
    hf_ref: str,
    findings: list[dict[str, object]],
    files_compared: int,
) -> dict[str, object]:
    errors = list(findings)
    return {
        "schema": 1,
        "status": "drift" if errors else "ok",
        "error_count": len(errors),
        "warn_count": 1,
        "files_compared": files_compared,
        "github_ref": github_ref,
        "github_repo": "szl-holdings/a11oy",
        "hf_ref": hf_ref,
        "hf_repo": "SZLHOLDINGS/a11oy",
        "findings": [*errors, COMPAT_WARNING],
    }


class N25CandidateAdmissionTests(unittest.TestCase):
    def test_exact_n25_copy_insertion_is_byte_bound(self) -> None:
        base, head = sample_dockerfiles()
        report = MODULE.validate_n25_dockerfile_copy_transition(base, head)
        self.assertEqual(report["delta"], "exact-n25-copy-insertion")
        self.assertEqual(report["copy_source"], MODULE.N25_COPY_SOURCE)
        self.assertEqual(report["head_blob"], oid(head))

    def test_live_dockerfile_carries_exact_n25_copy_line(self) -> None:
        live = (ROOT / "Dockerfile").read_bytes()
        self.assertEqual(live.count(MODULE.N25_HEAD_COPY_BLOCK), 1)
        predecessor = live.replace(
            MODULE.N25_HEAD_COPY_BLOCK,
            MODULE.N25_COPY_ANCHOR_LINE,
            1,
        )
        report = MODULE.validate_n25_dockerfile_copy_transition(predecessor, live)
        self.assertEqual(report["delta"], "exact-n25-copy-insertion")
        self.assertTrue(MODULE.n25_dockerfile_copy_pin_applicable(predecessor))
        self.assertFalse(MODULE.n25_dockerfile_copy_pin_applicable(live))

    def test_transition_rejects_any_extra_dockerfile_change(self) -> None:
        base, head = sample_dockerfiles()
        with self.assertRaisesRegex(MODULE.AdmissionError, "changes beyond"):
            MODULE.validate_n25_dockerfile_copy_transition(
                base,
                head + b"# unrelated edit\n",
            )

    def test_pin_requires_unchanged_n25_source(self) -> None:
        base, head, base_source, head_source = n25_pin_trees()
        head[MODULE.N25_COPY_SOURCE] = oid(b"changed N25 source\n")
        with self.assertRaisesRegex(MODULE.AdmissionError, "must not change"):
            MODULE.validate_n25_dockerfile_copy_pin(
                base_tree=base,
                head_tree=head,
                base_source=base_source,
                head_source=head_source,
                n25_source=N25_SOURCE,
            )

    def test_pin_binds_transition_and_existing_source(self) -> None:
        base, head, base_source, head_source = n25_pin_trees()
        report = MODULE.validate_n25_dockerfile_copy_pin(
            base_tree=base,
            head_tree=head,
            base_source=base_source,
            head_source=head_source,
            n25_source=N25_SOURCE,
        )
        self.assertEqual(report["status"], "n25-dockerfile-copy-pin-validated")
        self.assertEqual(report["copy_source_blob"], oid(N25_SOURCE))

    def test_report_admits_n25_missing_hf_and_review_bound_drift(self) -> None:
        base, head, _, _ = n25_pin_trees(
            extra_head={"pages/console.html": "b" * 40}
        )
        base["pages/console.html"] = "a" * 40
        findings = [
            {
                "kind": "missing-hf",
                "path": MODULE.N25_COPY_SOURCE,
                "severity": "error",
                "ahead": "github",
                "github_sha": oid(N25_SOURCE),
                "hf_oid": None,
            },
            {
                "kind": "drift",
                "path": "pages/console.html",
                "severity": "error",
                "ahead": "github",
                "lineage_conflict": False,
                "github_sha": "b" * 40,
                "hf_oid": "a" * 40,
            },
        ]
        report = candidate_report(
            github_ref="2" * 40,
            hf_ref="3" * 40,
            findings=findings,
            files_compared=1181,
        )
        admitted = MODULE.validate_n25_dockerfile_copy_candidate_report(
            report,
            verifier=FAKE_VERIFIER_CONSTANTS,
            base_ref="1" * 40,
            github_repo="szl-holdings/a11oy",
            github_ref="2" * 40,
            hf_repo="SZLHOLDINGS/a11oy",
            hf_ref="3" * 40,
            base_tree=base,
            head_tree=head,
            expected_files_compared=1180,
        )
        self.assertEqual(admitted, ["pages/console.html"])

    def test_report_rejects_wrong_managed_file_count(self) -> None:
        base, head, _, _ = n25_pin_trees()
        report = candidate_report(
            github_ref="2" * 40,
            hf_ref="3" * 40,
            findings=[
                {
                    "kind": "missing-hf",
                    "path": MODULE.N25_COPY_SOURCE,
                    "severity": "error",
                    "ahead": "github",
                }
            ],
            files_compared=1180,
        )
        with self.assertRaisesRegex(MODULE.AdmissionError, "plus 1"):
            MODULE.validate_n25_dockerfile_copy_candidate_report(
                report,
                verifier=FAKE_VERIFIER_CONSTANTS,
                base_ref="1" * 40,
                github_repo="szl-holdings/a11oy",
                github_ref="2" * 40,
                hf_repo="SZLHOLDINGS/a11oy",
                hf_ref="3" * 40,
                base_tree=base,
                head_tree=head,
                expected_files_compared=1180,
            )

    def test_dockerfile_change_routes_to_n25_pin(self) -> None:
        base, head, base_source, _ = n25_pin_trees()
        fake = SimpleNamespace(
            verify_ancestry=mock.Mock(),
            github_blob_tree=mock.Mock(side_effect=[base, head]),
        )
        pin_report = {
            "schema": 1,
            "status": "n25-dockerfile-copy-pin-validated",
            "hf_ref": "3" * 40,
            "review_bound_drift_paths": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = root / "tools.py"
            tools.write_text("# comparator\n", encoding="utf-8")
            report_path = root / "report.json"
            with (
                mock.patch.object(MODULE, "load_verifier", return_value=fake),
                mock.patch.object(
                    MODULE,
                    "read_bound_github_file",
                    return_value=base_source,
                ),
                mock.patch.object(
                    MODULE,
                    "prove_n25_dockerfile_copy_pin",
                    return_value=pin_report,
                ) as prove,
                mock.patch.object(
                    MODULE,
                    "delegate_ordinary_candidate",
                    return_value=17,
                ) as delegate,
            ):
                result = MODULE.main(
                    [
                        "--tools-script",
                        str(tools),
                        "--github-repo",
                        "szl-holdings/a11oy",
                        "--base-ref",
                        "1" * 40,
                        "--github-ref",
                        "2" * 40,
                        "--hf-repo",
                        "SZLHOLDINGS/a11oy",
                        "--report-out",
                        str(report_path),
                    ]
                )
            self.assertEqual(result, 0)
            prove.assert_called_once()
            delegate.assert_not_called()
            self.assertEqual(
                json.loads(report_path.read_text(encoding="utf-8")),
                pin_report,
            )

    def test_spent_n25_pin_delegates_to_ordinary_admission(self) -> None:
        _, _, _, live_source = n25_pin_trees()
        base = {
            MODULE.CONTROLLER_PATH: oid(CONTROLLER_SOURCE),
            ".dockerignore": oid(DOCKERIGNORE_SOURCE),
            MODULE.VERIFIER_PATH: oid(VERIFIER_SOURCE),
            MODULE.SECURITY_TXT_PATH: oid(SECURITY_SOURCE),
            MODULE.DOCKERFILE_PATH: oid(live_source),
            MODULE.N25_COPY_SOURCE: oid(N25_SOURCE),
        }
        changed_source = live_source + b"# later reviewed change\n"
        head = dict(base)
        head[MODULE.DOCKERFILE_PATH] = oid(changed_source)
        fake = SimpleNamespace(
            verify_ancestry=mock.Mock(),
            github_blob_tree=mock.Mock(side_effect=[base, head]),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = root / "tools.py"
            tools.write_text("# comparator\n", encoding="utf-8")
            report_path = root / "report.json"
            with (
                mock.patch.object(MODULE, "load_verifier", return_value=fake),
                mock.patch.object(
                    MODULE,
                    "read_bound_github_file",
                    return_value=live_source,
                ),
                mock.patch.object(
                    MODULE,
                    "prove_n25_dockerfile_copy_pin",
                    return_value={
                        "hf_ref": "3" * 40,
                        "review_bound_drift_paths": [],
                    },
                ) as prove,
                mock.patch.object(
                    MODULE,
                    "delegate_ordinary_candidate",
                    return_value=17,
                ) as delegate,
            ):
                result = MODULE.main(
                    [
                        "--tools-script",
                        str(tools),
                        "--github-repo",
                        "szl-holdings/a11oy",
                        "--base-ref",
                        "1" * 40,
                        "--github-ref",
                        "2" * 40,
                        "--hf-repo",
                        "SZLHOLDINGS/a11oy",
                        "--report-out",
                        str(report_path),
                    ]
                )
            self.assertEqual(result, 17)
            prove.assert_not_called()
            delegate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
''',
    encoding="utf-8",
)

print("materialized exact N25 COPY successor")
