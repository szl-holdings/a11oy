from __future__ import annotations

import importlib.util
import json
import re
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

BASE_SECURITY = """Contact: mailto:security@szlholdings.ai
Expires: 2027-06-01T00:00:00.000Z
Preferred-Languages: en
Canonical: https://a-11-oy.com/.well-known/security.txt
Policy: https://github.com/szl-holdings/a11oy/blob/main/SECURITY.md
Acknowledgments: https://github.com/szl-holdings/a11oy/blob/main/SECURITY.md#acknowledgments
Hiring: https://szlholdings.ai/careers

# SZL Holdings — Doctrine v11 LOCKED | SLSA L1 honest | Section 889: 5 vendors
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
""".encode("utf-8")
HEAD_SECURITY = """Contact: https://github.com/szl-holdings/a11oy/security/advisories/new
Contact: mailto:security@szlholdings.com
Expires: 2027-06-01T00:00:00.000Z
Preferred-Languages: en
Canonical: https://a-11-oy.com/.well-known/security.txt
Policy: https://github.com/szl-holdings/a11oy/blob/main/SECURITY.md
Acknowledgments: https://github.com/szl-holdings/a11oy/blob/main/SECURITY.md#acknowledgments

# SZL Holdings — Doctrine v11 LOCKED | SLSA L1 honest | Section 889: 5 vendors
# RFC 9116 https://www.rfc-editor.org/rfc/rfc9116
# Contact fields are listed in order of preference. Both channels are verified
# reachable: GitHub private vulnerability reporting (HTTP 200) and the
# szlholdings.com mailbox (MX -> smtp.google.com).
# Honest UNKNOWN over fabricated green: no Encryption field is advertised
# because no published PGP key exists.
""".encode("utf-8")
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

    def test_clean_candidate_report_admits_only_explicit_dot_proof(self) -> None:
        verifier = SimpleNamespace(
            EXPECTED_COMPATIBILITY_WARNING=COMPAT_WARNING,
        )
        base_tree = {
            SECURITY.SECURITY_PATH: "1" * 40,
            "SECURITY.md": "2" * 40,
        }
        head_tree = {
            SECURITY.SECURITY_PATH: "3" * 40,
            "SECURITY.md": "2" * 40,
        }
        report = {
            "schema": 1,
            "status": "ok",
            "error_count": 0,
            "warn_count": 1,
            "files_compared": 17,
            "github_repo": "szl-holdings/a11oy",
            "github_ref": "b" * 40,
            "hf_repo": "SZLHOLDINGS/a11oy",
            "hf_ref": "c" * 40,
            "findings": [COMPAT_WARNING],
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
        self.assertEqual(admitted, [])

    def test_candidate_report_rejects_any_comparator_visible_drift(self) -> None:
        verifier = SimpleNamespace(
            EXPECTED_COMPATIBILITY_WARNING=COMPAT_WARNING,
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
            "drift outside the explicit dot-prefixed security proof",
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

    def test_successor_proves_base_dot_parity_and_records_evidence(self) -> None:
        base_ref = "a" * 40
        github_ref = "b" * 40
        hf_ref = "c" * 40
        dot_sha256 = "d" * 64
        base_tree = {SECURITY.SECURITY_PATH: "1" * 40}
        head_tree = {SECURITY.SECURITY_PATH: "2" * 40}
        candidate_report = {
            "schema": 1,
            "status": "ok",
            "error_count": 0,
            "warn_count": 1,
            "files_compared": 17,
            "github_repo": "szl-holdings/a11oy",
            "github_ref": github_ref,
            "hf_repo": "SZLHOLDINGS/a11oy",
            "hf_ref": hf_ref,
            "findings": [COMPAT_WARNING],
        }

        def run_comparator(**kwargs):
            kwargs["report_out"].write_text(
                json.dumps(candidate_report),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="")

        verifier = SimpleNamespace(
            EXPECTED_COMPATIBILITY_WARNING=COMPAT_WARNING,
            verify_ancestry=mock.Mock(),
            github_blob_tree=mock.Mock(side_effect=[base_tree, head_tree]),
            resolve_stable_revision=mock.Mock(return_value=hf_ref),
            verify_leading_dot_copy=mock.Mock(return_value=dot_sha256),
            run_comparator=mock.Mock(side_effect=run_comparator),
        )
        base_controller = SimpleNamespace(
            SHA_RE=re.compile(r"[0-9a-f]{40}"),
            load_verifier=mock.Mock(return_value=verifier),
            read_bound_github_file=mock.Mock(
                side_effect=[BASE_SECURITY, HEAD_SECURITY]
            ),
            run_strict_comparator=mock.Mock(
                return_value={"files_compared": 17}
            ),
        )

        with tempfile.TemporaryDirectory() as temporary:
            tools_script = Path(temporary) / "tools.py"
            tools_script.write_text("# pinned comparator\n", encoding="utf-8")
            with (
                mock.patch.object(
                    SECURITY,
                    "load_base_controller",
                    return_value=base_controller,
                ),
                mock.patch.object(SECURITY, "validate_control_plane"),
            ):
                report = SECURITY.prove_security_successor(
                    tools_script=tools_script,
                    github_repo="szl-holdings/a11oy",
                    base_ref=base_ref,
                    github_ref=github_ref,
                    hf_repo="SZLHOLDINGS/a11oy",
                )

        verifier.verify_leading_dot_copy.assert_called_once_with(
            github_repo="szl-holdings/a11oy",
            github_ref=base_ref,
            hf_repo="SZLHOLDINGS/a11oy",
            hf_ref=hf_ref,
        )
        self.assertEqual(
            report["base_leading_dot_copy"],
            {
                "path": SECURITY.SECURITY_PATH,
                "sha256": dot_sha256,
                "status": "exact",
            },
        )
        self.assertEqual(report["comparator_drift_paths"], [])
        self.assertEqual(
            report["review_bound_drift_paths"],
            [SECURITY.SECURITY_PATH],
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

    def test_selector_setup_failure_writes_canonical_rejection_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path = root / "report.json"
            report_path.write_text("stale\n", encoding="utf-8")
            with mock.patch.object(
                SELECTOR,
                "load_controllers",
                side_effect=SELECTOR.SelectionError("controller setup failed"),
            ), self.assertRaisesRegex(
                SELECTOR.SelectionError,
                "controller setup failed",
            ):
                SELECTOR.main(self.args(root))

            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(
            report,
            {
                "schema": 1,
                "status": "rejected",
                "proof_status": "failed-closed",
                "base_ref": "a" * 40,
                "github_ref": "b" * 40,
                "error_type": "SelectionError",
                "error": "controller setup failed",
            },
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
