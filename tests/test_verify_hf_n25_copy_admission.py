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
