from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".github" / "scripts"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SECURITY = load(
    "verify_hf_security_candidate_admission_test",
    SCRIPTS / "verify_hf_security_candidate_admission.py",
)
SELECTOR = load(
    "select_hf_candidate_admission_test",
    SCRIPTS / "select_hf_candidate_admission.py",
)

BASE_SECURITY = b"""Contact: mailto:security@szlholdings.ai
Expires: 2027-06-01T00:00:00.000Z
Preferred-Languages: en
Canonical: https://a-11-oy.com/.well-known/security.txt
Policy: https://github.com/szl-holdings/a11oy/blob/main/SECURITY.md
Acknowledgments: https://github.com/szl-holdings/a11oy/blob/main/SECURITY.md#acknowledgments
Hiring: https://szlholdings.ai/careers

# SZL Holdings â# SZL Holdings \xe2# SZL Holdings \xe2\x80# SZL Holdings \xe2\x80\x94 Doctrine v11 LOCKED | SLSA L1 honest | Section 889: 5 vendors
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
HEAD_SECURITY = b"""Contact: https://github.com/szl-holdings/a11oy/security/advisories/new
Contact: mailto:security@szlholdings.com
Expires: 2027-06-01T00:00:00.000Z
Preferred-Languages: en
Canonical: https://a-11-oy.com/.well-known/security.txt
Policy: https://github.com/szl-holdings/a11oy/blob/main/SECURITY.md
Acknowledgments: https://github.com/szl-holdings/a11oy/blob/main/SECURITY.md#acknowledgments

# SZL Holdings â# SZL Holdings \xe2# SZL Holdings \xe2\x80# SZL Holdings \xe2\x80\x94 Doctrine v11 LOCKED | SLSA L1 honest | Section 889: 5 vendors
# RFC 9116 https://www.rfc-editor.org/rfc/rfc9116
# Contact fields are listed in order of preference. Both channels are verified
# reachable: GitHub private vulnerability reporting (HTTP 200) and the
# szlholdings.com mailbox (MX -> smtp.google.com).
# Honest UNKNOWN over fabricated green: no Encryption field is advertised
# because no published PGP key exists.
"""
COMPAT_WARNING = {
    "kind": "missing-both",
    "path": "well-known/security.txt",
    "severity": "warn",
}


class SecurityTransitionTests(unittest.TestCase):
    def test_exact_reviewed_transition_is_admitted(self) -> None:
        report = SECURITY.validate_exact_security_transition(
            BASE_SECURITY,
            HEAD_SECURITY,
        )
        self.assertEqual(
            report["transition"],
            "exact-reviewed-rfc9116-contact-successor",
        )
        self.assertFalse(report["encryption_advertised"])
        self.assertEqual(report["contacts"], list(SECURITY.EXPECTED_CONTACTS))

    def test_any_predecessor_or_successor_byte_drift_fails_closed(self) -> None:
        for base, head in (
            (BASE_SECURITY + b"# drift\n", HEAD_SECURITY),
            (BASE_SECURITY, HEAD_SECURITY + b"# drift\n"),
        ):
            with self.subTest(base=len(base), head=len(head)), self.assertRaises(
                SECURITY.AdmissionError
            ):
                SECURITY.validate_exact_security_transition(base, head)

    def test_unavailable_contact_or_phantom_fields_are_rejected(self) -> None:
        for token in (b"szlholdings.ai", b"Encryption:", b"Hiring:"):
            tampered = HEAD_SECURITY + token + b" unavailable\n"
            with self.subTest(token=token), self.assertRaises(
                SECURITY.AdmissionError
            ):
                SECURITY.validate_exact_security_transition(
                    BASE_SECURITY,
                    tampered,
                )

    def test_candidate_report_binds_security_and_all_other_drift_to_tree(self) -> None:
        verifier = SimpleNamespace(
            EXPECTED_COMPATIBILITY_WARNING=COMPAT_WARNING,
            CANDIDATE_AHEAD_VALUES=frozenset({"github", "github?"}),
        )
        base_tree = {
            SECURITY.SECURITY_PATH: "1" * 40,
            "SECURITY.md": "2" * 40,
        }
        head_tree = {
            SECURITY.SECURITY_PATH: "3" * 40,
            "SECURITY.md": "4" * 40,
        }
        errors = [
            {
                "kind": "drift",
                "path": path,
                "severity": "error",
                "ahead": "github",
                "lineage_conflict": False,
                "github_sha": head_tree[path],
                "hf_oid": base_tree[path],
            }
            for path in (SECURITY.SECURITY_PATH, "SECURITY.md")
        ]
        report = {
            "schema": 1,
            "status": "drift",
            "error_count": 2,
            "warn_count": 1,
            "files_compared": 17,
            "github_repo": "szl-holdings/a11oy",
            "github_ref": "b" * 40,
            "hf_repo": "SZLHOLDINGS/a11oy",
            "hf_ref": "c" * 40,
            "findings": [*errors, COMPAT_WARNING],
        }
        admitted = SECURITY.validate_candidate_report(
            report,
            verifier=verifier,
            github_repo="szl-holdings/a11oy",
            base_ref="a" * 40,
            github_ref="b" * 40,
            hf_repo="SZLHOLDINGS/a11oy",
            hf_ref="c" * 40,
            base_tree=base_tree,
            head_tree=head_tree,
            expected_files_compared=17,
        )
        self.assertEqual(
            admitted,
            [SECURITY.SECURITY_PATH, "SECURITY.md"],
        )

    def test_candidate_report_without_bound_security_row_fails_closed(self) -> None:
        verifier = SimpleNamespace(
            EXPECTED_COMPATIBILITY_WARNING=COMPAT_WARNING,
            CANDIDATE_AHEAD_VALUES=frozenset({"github"}),
        )
        base_tree = {SECURITY.SECURITY_PATH: "1" * 40, "README.md": "2" * 40}
        head_tree = {SECURITY.SECURITY_PATH: "3" * 40, "README.md": "4" * 40}
        report = {
            "schema": 1,
            "status": "drift",
            "error_count": 1,
            "warn_count": 1,
            "files_compared": 2,
            "github_repo": "szl-holdings/a11oy",
            "github_ref": "b" * 40,
            "hf_repo": "SZLHOLDINGS/a11oy",
            "hf_ref": "c" * 40,
            "findings": [
                {
                    "kind": "drift",
                    "path": "README.md",
                    "severity": "error",
                    "ahead": "github",
                    "lineage_conflict": False,
                    "github_sha": "4" * 40,
                    "hf_oid": "2" * 40,
                },
                COMPAT_WARNING,
            ],
        }
        with self.assertRaisesRegex(
            SECURITY.AdmissionError,
            "security.txt drift row",
        ):
            SECURITY.validate_candidate_report(
                report,
                verifier=verifier,
                github_repo="szl-holdings/a11oy",
                base_ref="a" * 40,
                github_ref="b" * 40,
                hf_repo="SZLHOLDINGS/a11oy",
                hf_ref="c" * 40,
                base_tree=base_tree,
                head_tree=head_tree,
                expected_files_compared=2,
            )


class SelectorTests(unittest.TestCase):
    def args(self, root: Path) -> list[str]:
        tools = root / "tools.py"
        tools.write_text("# comparator\n", encoding="utf-8")
        return [
            "--tools-script",
            str(tools),
            "--github-repo",
            "szl-holdings/a11oy",
            "--base-ref",
            "a" * 40,
            "--github-ref",
            "b" * 40,
            "--hf-repo",
            "SZLHOLDINGS/a11oy",
            "--report-out",
            str(root / "report.json"),
        ]

    def fake_verifier(self, protected_change: bool):
        base = {
            "Dockerfile": "1" * 40,
            ".dockerignore": "2" * 40,
            SECURITY.SECURITY_PATH: "3" * 40,
            ".github/scripts/verify_hf_repository_parity.py": "4" * 40,
        }
        head = dict(base)
        if protected_change:
            head[SECURITY.SECURITY_PATH] = "5" * 40
        return SimpleNamespace(
            PROTECTED_CANDIDATE_INPUTS=tuple(base),
            verify_ancestry=mock.Mock(),
            github_blob_tree=mock.Mock(side_effect=[base, head]),
        )

    def test_exact_security_protected_delta_routes_to_security_controller(self) -> None:
        base_controller = SimpleNamespace(
            load_verifier=mock.Mock(return_value=self.fake_verifier(True)),
            main=mock.Mock(return_value=19),
        )
        security_controller = SimpleNamespace(main=mock.Mock(return_value=7))
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            SELECTOR,
            "load_controllers",
            return_value=(base_controller, security_controller),
        ):
            result = SELECTOR.main(self.args(Path(temporary)))
        self.assertEqual(result, 7)
        security_controller.main.assert_called_once()
        base_controller.main.assert_not_called()

    def test_ordinary_candidate_remains_on_established_controller(self) -> None:
        base_controller = SimpleNamespace(
            load_verifier=mock.Mock(return_value=self.fake_verifier(False)),
            main=mock.Mock(return_value=19),
        )
        security_controller = SimpleNamespace(main=mock.Mock(return_value=7))
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            SELECTOR,
            "load_controllers",
            return_value=(base_controller, security_controller),
        ):
            result = SELECTOR.main(self.args(Path(temporary)))
        self.assertEqual(result, 19)
        base_controller.main.assert_called_once()
        security_controller.main.assert_not_called()


if __name__ == "__main__":
    unittest.main()
