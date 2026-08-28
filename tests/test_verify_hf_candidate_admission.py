from __future__ import annotations

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
    "verify_hf_candidate_admission",
    SCRIPT,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

BASE_SOURCE = b'''PROTECTED_CANDIDATE_INPUTS = (
    "Dockerfile",
    ".well-known/security.txt",
    ".github/scripts/verify_hf_repository_parity.py",
)
'''
HEAD_SOURCE = b'''PROTECTED_CANDIDATE_INPUTS = (
    "Dockerfile",
    ".dockerignore",
    ".well-known/security.txt",
    ".github/scripts/verify_hf_repository_parity.py",
)
'''
TEST_SOURCE = b'''
class Contract:
    @staticmethod
    def clean_candidate_report():
        return {".dockerignore": "clean"}

    def test_dockerignore_is_a_protected_candidate_input(self):
        MODULE.validate_protected_candidate_inputs({}, {})

    def test_changed_or_missing_dockerignore_fails_closed(self):
        with self.assertRaises(ValueError):
            raise ValueError(".dockerignore")
        MODULE.validate_protected_candidate_inputs({}, {})

    def test_dockerignore_cannot_hide_directory_copy_drift_behind_clean_report(self):
        with self.assertRaisesRegex(ValueError, "drift"):
            raise ValueError("drift")
        MODULE.validate_candidate_report({})
'''
CONTROLLER_SOURCE = b"protected controller"
DOCKERIGNORE_SOURCE = b"# build context\n"
SECURITY_SOURCE = b"Contact: security@example.invalid\n"
JS_SOURCE = b"/* command bar */\n"
CSS_SOURCE = b"/* command bar */\n"
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


def base_tree() -> dict[str, str]:
    return {
        MODULE.CONTROLLER_PATH: oid(CONTROLLER_SOURCE),
        ".dockerignore": oid(DOCKERIGNORE_SOURCE),
        MODULE.VERIFIER_PATH: oid(BASE_SOURCE),
    }


def successor_trees() -> tuple[dict[str, str], dict[str, str]]:
    base = base_tree()
    head = dict(base)
    head[MODULE.VERIFIER_PATH] = oid(HEAD_SOURCE)
    head[MODULE.CONTRACT_TEST_PATH] = oid(TEST_SOURCE)
    return base, head


def sample_dockerfiles() -> tuple[bytes, bytes]:
    prefix = b"FROM python:3.12-slim\n"
    return (
        prefix + MODULE.BASE_SHARED_COPY_LINE,
        prefix + MODULE.HEAD_SHARED_COPY_LINE,
    )


def dockerfile_pin_trees(
    *, extra_head: dict[str, str] | None = None
) -> tuple[dict[str, str], dict[str, str], bytes, bytes]:
    base_dockerfile, head_dockerfile = sample_dockerfiles()
    base = base_tree()
    base[MODULE.DOCKERFILE_PATH] = oid(base_dockerfile)
    base[MODULE.SECURITY_TXT_PATH] = oid(SECURITY_SOURCE)
    head = dict(base)
    head[MODULE.DOCKERFILE_PATH] = oid(head_dockerfile)
    head[MODULE.PINNED_COPY_SOURCES[0]] = oid(JS_SOURCE)
    head[MODULE.PINNED_COPY_SOURCES[1]] = oid(CSS_SOURCE)
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


class CandidateAdmissionTests(unittest.TestCase):
    def test_git_blob_oid_matches_known_empty_blob(self) -> None:
        self.assertEqual(
            MODULE.git_blob_oid(b""),
            "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
        )

    def test_exact_verifier_transition_is_byte_bound(self) -> None:
        report = MODULE.validate_verifier_transition(BASE_SOURCE, HEAD_SOURCE)
        self.assertEqual(
            report["head_inputs"],
            list(MODULE.EXPECTED_SUCCESSOR_INPUTS),
        )
        self.assertEqual(report["delta"], "exact-one-line-addition")

    def test_verifier_transition_rejects_any_extra_change(self) -> None:
        tampered = HEAD_SOURCE + b"# unrelated candidate edit\n"
        with self.assertRaisesRegex(MODULE.AdmissionError, "changes beyond"):
            MODULE.validate_verifier_transition(BASE_SOURCE, tampered)

    def test_controller_and_dockerignore_remain_base_controlled(self) -> None:
        for path in (MODULE.CONTROLLER_PATH, ".dockerignore"):
            base = base_tree()
            head = dict(base)
            head[path] = "f" * 40
            with self.subTest(path=path), self.assertRaisesRegex(
                MODULE.AdmissionError,
                "protected admission authority",
            ):
                MODULE.validate_base_controlled_inputs(base, head)

    def test_contract_successor_requires_exact_two_path_delta(self) -> None:
        base, head = successor_trees()
        head["README.md"] = "1" * 40
        with self.assertRaisesRegex(MODULE.AdmissionError, "unexpected path set"):
            MODULE.validate_contract_successor(
                base_tree=base,
                head_tree=head,
                base_source=BASE_SOURCE,
                head_source=HEAD_SOURCE,
                test_source=TEST_SOURCE,
            )

    def test_fetched_bytes_must_match_tree_blob(self) -> None:
        base, head = successor_trees()
        with self.assertRaisesRegex(MODULE.AdmissionError, "immutable tree blob"):
            MODULE.validate_contract_successor(
                base_tree=base,
                head_tree=head,
                base_source=BASE_SOURCE,
                head_source=HEAD_SOURCE + b"# tampered\n",
                test_source=TEST_SOURCE,
            )

    def test_contract_successor_records_semantic_evidence(self) -> None:
        base, head = successor_trees()
        report = MODULE.validate_contract_successor(
            base_tree=base,
            head_tree=head,
            base_source=BASE_SOURCE,
            head_source=HEAD_SOURCE,
            test_source=TEST_SOURCE,
        )
        self.assertEqual(report["status"], "contract-successor-validated")
        self.assertEqual(
            report["changed_paths"],
            sorted(MODULE.EXPECTED_CHANGED_PATHS),
        )
        self.assertEqual(
            report["regression"]["status"],
            "present-and-parseable",
        )

    def test_contract_test_requires_negative_assertion(self) -> None:
        weak = TEST_SOURCE.replace(b"assertRaises", b"weakAssertion")
        with self.assertRaisesRegex(MODULE.AdmissionError, "negative assertion"):
            MODULE.validate_contract_test(weak)

    def test_read_bound_github_file_rejects_wrong_bytes(self) -> None:
        fake = SimpleNamespace(_read_url=mock.Mock(return_value=b"wrong"))
        tree = {MODULE.VERIFIER_PATH: oid(BASE_SOURCE)}
        with self.assertRaisesRegex(MODULE.AdmissionError, "immutable tree blob"):
            MODULE.read_bound_github_file(
                fake,
                tree=tree,
                github_repo="szl-holdings/a11oy",
                github_ref="1" * 40,
                path=MODULE.VERIFIER_PATH,
                revision="base",
            )

    def test_ordinary_candidate_delegates_to_existing_verifier(self) -> None:
        base = base_tree()
        head = dict(base)
        fake = SimpleNamespace(
            verify_ancestry=mock.Mock(),
            github_blob_tree=mock.Mock(side_effect=[base, head]),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = root / "tools.py"
            tools.write_text("# comparator\n", encoding="utf-8")
            report = root / "report.json"
            with (
                mock.patch.object(MODULE, "load_verifier", return_value=fake),
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
                        str(report),
                    ]
                )
            self.assertEqual(result, 17)
            delegate.assert_called_once()

    def test_verifier_change_routes_to_contract_successor(self) -> None:
        base, head = successor_trees()
        fake = SimpleNamespace(
            verify_ancestry=mock.Mock(),
            github_blob_tree=mock.Mock(side_effect=[base, head]),
        )
        successor_report = {
            "schema": 1,
            "status": "contract-successor-validated",
            "hf_ref": "3" * 40,
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
                    "prove_contract_successor",
                    return_value=successor_report,
                ) as prove,
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
            self.assertEqual(
                json.loads(report_path.read_text(encoding="utf-8")),
                successor_report,
            )

    def test_rejection_writes_a_machine_readable_report(self) -> None:
        base = base_tree()
        head = dict(base)
        head[".dockerignore"] = "f" * 40
        fake = SimpleNamespace(
            verify_ancestry=mock.Mock(),
            github_blob_tree=mock.Mock(side_effect=[base, head]),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = root / "tools.py"
            tools.write_text("# comparator\n", encoding="utf-8")
            report_path = root / "report.json"
            with mock.patch.object(MODULE, "load_verifier", return_value=fake):
                with self.assertRaises(MODULE.AdmissionError):
                    MODULE.main(
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
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "rejected")
            self.assertEqual(report["proof_status"], "failed-closed")
            self.assertIn(".dockerignore", report["error"])

    def test_exact_dockerfile_copy_insertion_is_byte_bound(self) -> None:
        base, head = sample_dockerfiles()
        report = MODULE.validate_dockerfile_copy_transition(base, head)
        self.assertEqual(report["delta"], "exact-shared-copy-insertion")
        self.assertEqual(report["copy_sources"], list(MODULE.PINNED_COPY_SOURCES))
        self.assertEqual(report["head_blob"], oid(head))

    def test_live_dockerfile_carries_1396_shared_copy_line(self) -> None:
        live = (ROOT / "Dockerfile").read_bytes()
        self.assertEqual(live.count(MODULE.HEAD_SHARED_COPY_LINE), 1)
        self.assertEqual(live.count(MODULE.BASE_SHARED_COPY_LINE), 0)
        predecessor = live.replace(
            MODULE.HEAD_SHARED_COPY_LINE,
            MODULE.BASE_SHARED_COPY_LINE,
            1,
        )
        report = MODULE.validate_dockerfile_copy_transition(predecessor, live)
        self.assertEqual(report["delta"], "exact-shared-copy-insertion")
        self.assertEqual(
            report["head_blob"],
            "cb5eb49b1c3b38e9150d6085013b979a11e1e9fd",
        )
        self.assertFalse(MODULE.dockerfile_copy_pin_applicable(live))
        self.assertTrue(MODULE.dockerfile_copy_pin_applicable(predecessor))

    def test_dockerfile_copy_transition_rejects_any_extra_change(self) -> None:
        base, head = sample_dockerfiles()
        with self.assertRaisesRegex(MODULE.AdmissionError, "changes beyond"):
            MODULE.validate_dockerfile_copy_transition(
                base, head + b"# unrelated candidate edit\n"
            )

    def test_dockerfile_copy_pin_requires_new_command_bar_blobs(self) -> None:
        base, head, base_source, head_source = dockerfile_pin_trees()
        report = MODULE.validate_dockerfile_copy_pin(
            base_tree=base,
            head_tree=head,
            base_source=base_source,
            head_source=head_source,
            copy_sources={
                MODULE.PINNED_COPY_SOURCES[0]: JS_SOURCE,
                MODULE.PINNED_COPY_SOURCES[1]: CSS_SOURCE,
            },
        )
        self.assertEqual(report["status"], "dockerfile-copy-pin-validated")
        self.assertEqual(
            set(report["copy_sources"]),
            set(MODULE.PINNED_COPY_SOURCES),
        )

    def test_dockerfile_copy_pin_rejects_source_already_on_base(self) -> None:
        base, head, base_source, head_source = dockerfile_pin_trees()
        base[MODULE.PINNED_COPY_SOURCES[0]] = oid(JS_SOURCE)
        with self.assertRaisesRegex(MODULE.AdmissionError, "new candidate file"):
            MODULE.validate_dockerfile_copy_pin(
                base_tree=base,
                head_tree=head,
                base_source=base_source,
                head_source=head_source,
                copy_sources={
                    MODULE.PINNED_COPY_SOURCES[0]: JS_SOURCE,
                    MODULE.PINNED_COPY_SOURCES[1]: CSS_SOURCE,
                },
            )

    def test_dockerfile_copy_pin_rejects_security_txt_mutation(self) -> None:
        base, head, base_source, head_source = dockerfile_pin_trees()
        head[MODULE.SECURITY_TXT_PATH] = oid(b"mutated security\n")
        with self.assertRaisesRegex(MODULE.AdmissionError, "protected input"):
            MODULE.validate_dockerfile_copy_pin(
                base_tree=base,
                head_tree=head,
                base_source=base_source,
                head_source=head_source,
                copy_sources={
                    MODULE.PINNED_COPY_SOURCES[0]: JS_SOURCE,
                    MODULE.PINNED_COPY_SOURCES[1]: CSS_SOURCE,
                },
            )

    def test_dockerignore_successor_does_not_admit_dockerfile_mutation(self) -> None:
        base, head = successor_trees()
        base[MODULE.DOCKERFILE_PATH] = oid(sample_dockerfiles()[0])
        head[MODULE.DOCKERFILE_PATH] = oid(sample_dockerfiles()[1])
        with self.assertRaisesRegex(MODULE.AdmissionError, "unexpected path set"):
            MODULE.validate_contract_successor(
                base_tree=base,
                head_tree=head,
                base_source=BASE_SOURCE,
                head_source=HEAD_SOURCE,
                test_source=TEST_SOURCE,
            )

    def test_dockerfile_copy_report_admits_missing_hf_and_review_bound_drift(
        self,
    ) -> None:
        base, head, _, _ = dockerfile_pin_trees(
            extra_head={"pages/console.html": "b" * 40}
        )
        base["pages/console.html"] = "a" * 40
        findings = [
            {
                "kind": "missing-hf",
                "path": MODULE.PINNED_COPY_SOURCES[0],
                "severity": "error",
                "ahead": "github",
            },
            {
                "kind": "missing-hf",
                "path": MODULE.PINNED_COPY_SOURCES[1],
                "severity": "error",
                "ahead": "github",
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
            files_compared=1182,
        )
        admitted = MODULE.validate_dockerfile_copy_candidate_report(
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

    def test_dockerfile_copy_report_rejects_wrong_managed_file_count(self) -> None:
        base, head, _, _ = dockerfile_pin_trees()
        findings = [
            {
                "kind": "missing-hf",
                "path": path,
                "severity": "error",
                "ahead": "github",
            }
            for path in MODULE.PINNED_COPY_SOURCES
        ]
        report = candidate_report(
            github_ref="2" * 40,
            hf_ref="3" * 40,
            findings=findings,
            files_compared=1180,
        )
        with self.assertRaisesRegex(MODULE.AdmissionError, "plus 2"):
            MODULE.validate_dockerfile_copy_candidate_report(
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

    def test_dockerfile_copy_report_rejects_unexplained_missing_hf(self) -> None:
        base, head, _, _ = dockerfile_pin_trees()
        findings = [
            {
                "kind": "missing-hf",
                "path": MODULE.PINNED_COPY_SOURCES[0],
                "severity": "error",
                "ahead": "github",
            },
            {
                "kind": "missing-hf",
                "path": "static/shared/szl_holo3d.js",
                "severity": "error",
                "ahead": "github",
            },
        ]
        report = candidate_report(
            github_ref="2" * 40,
            hf_ref="3" * 40,
            findings=findings,
            files_compared=1182,
        )
        with self.assertRaisesRegex(MODULE.AdmissionError, "unexplained candidate"):
            MODULE.validate_dockerfile_copy_candidate_report(
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

    def test_dockerfile_change_routes_to_copy_pin(self) -> None:
        base, head, base_source, _ = dockerfile_pin_trees()
        fake = SimpleNamespace(
            verify_ancestry=mock.Mock(),
            github_blob_tree=mock.Mock(side_effect=[base, head]),
        )
        pin_report = {
            "schema": 1,
            "status": "dockerfile-copy-pin-validated",
            "hf_ref": "3" * 40,
            "review_bound_drift_paths": ["pages/console.html"],
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
                    "prove_dockerfile_copy_pin",
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

    def test_spent_copy_pin_does_not_intercept_later_dockerfile_edits(self) -> None:
        base, head, _, head_source = dockerfile_pin_trees()
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
                    return_value=head_source,
                ),
                mock.patch.object(
                    MODULE,
                    "prove_dockerfile_copy_pin",
                    return_value={"hf_ref": "3" * 40, "review_bound_drift_paths": []},
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

    def test_verifier_and_dockerfile_change_does_not_use_the_copy_pin(self) -> None:
        base, head = successor_trees()
        base[MODULE.DOCKERFILE_PATH] = "a" * 40
        head[MODULE.DOCKERFILE_PATH] = "b" * 40
        fake = SimpleNamespace(
            verify_ancestry=mock.Mock(),
            github_blob_tree=mock.Mock(side_effect=[base, head]),
        )
        successor_report = {
            "schema": 1,
            "status": "contract-successor-validated",
            "hf_ref": "3" * 40,
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
                    "prove_contract_successor",
                    return_value=successor_report,
                ) as prove_successor,
                mock.patch.object(
                    MODULE,
                    "prove_dockerfile_copy_pin",
                    return_value={"hf_ref": "3" * 40, "review_bound_drift_paths": []},
                ) as prove_pin,
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
            prove_successor.assert_called_once()
            prove_pin.assert_not_called()


if __name__ == "__main__":
    unittest.main()
