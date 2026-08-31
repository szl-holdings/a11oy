from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "verify_hf_repository_parity.py"
GITHUB_REPO = "szl-holdings/a11oy"
HF_REPO = "SZLHOLDINGS/a11oy"
SPEC = importlib.util.spec_from_file_location("verify_hf_repository_parity", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DockerignoreCandidateContractTests(unittest.TestCase):
    @staticmethod
    def protected_tree(sha: str = "a" * 40) -> dict[str, str]:
        return {path: sha for path in MODULE.PROTECTED_CANDIDATE_INPUTS}

    @staticmethod
    def clean_candidate_report(
        *, github_ref: str, hf_ref: str
    ) -> dict[str, object]:
        return {
            "schema": 1,
            "status": "ok",
            "error_count": 0,
            "warn_count": 1,
            "files_compared": 1180,
            "github_ref": github_ref,
            "github_repo": GITHUB_REPO,
            "hf_ref": hf_ref,
            "hf_repo": HF_REPO,
            "findings": [
                {
                    "kind": "missing-both",
                    "path": "well-known/security.txt",
                    "severity": "warn",
                }
            ],
        }

    def test_dockerignore_is_a_protected_candidate_input(self) -> None:
        self.assertIn("Dockerfile", MODULE.PROTECTED_CANDIDATE_INPUTS)
        self.assertIn(".dockerignore", MODULE.PROTECTED_CANDIDATE_INPUTS)

    def test_unchanged_dockerignore_contract_is_admitted(self) -> None:
        base_tree = self.protected_tree()
        MODULE.validate_protected_candidate_inputs(base_tree, dict(base_tree))

    def test_changed_or_missing_dockerignore_fails_closed(self) -> None:
        base_tree = self.protected_tree()
        for mutation in ("changed", "missing"):
            head_tree = dict(base_tree)
            if mutation == "changed":
                head_tree[".dockerignore"] = "b" * 40
            else:
                head_tree.pop(".dockerignore")
            with self.subTest(mutation=mutation), self.assertRaisesRegex(
                MODULE.ParityError,
                r"protected admission input is missing or changed: '\.dockerignore'",
            ):
                MODULE.validate_protected_candidate_inputs(base_tree, head_tree)

    def test_dockerignore_cannot_hide_directory_copy_drift_behind_clean_report(self) -> None:
        base_ref = "1" * 40
        github_ref = "2" * 40
        hf_ref = "3" * 40
        base_tree = self.protected_tree()
        base_tree["pages/verify.html"] = "c" * 40
        head_tree = dict(base_tree)

        # An attacker-controlled candidate can add `pages/verify.html` to
        # `.dockerignore`. The external comparator may then report the same
        # managed-file count and no drift because the directory-COPY source
        # disappeared before comparison. The protected-input gate must reject
        # that candidate before the clean comparator report can authorize it.
        head_tree[".dockerignore"] = "d" * 40
        report = self.clean_candidate_report(
            github_ref=github_ref,
            hf_ref=hf_ref,
        )

        self.assertEqual(
            MODULE.validate_candidate_report(
                report,
                base_ref=base_ref,
                github_repo=GITHUB_REPO,
                github_ref=github_ref,
                hf_repo=HF_REPO,
                hf_ref=hf_ref,
                base_tree=base_tree,
                head_tree=head_tree,
                expected_files_compared=1180,
            ),
            [],
        )
        with self.assertRaisesRegex(MODULE.ParityError, r"'\.dockerignore'"):
            MODULE.validate_protected_candidate_inputs(base_tree, head_tree)


if __name__ == "__main__":
    unittest.main()
