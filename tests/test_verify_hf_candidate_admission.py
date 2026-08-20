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


if __name__ == "__main__":
    unittest.main()
