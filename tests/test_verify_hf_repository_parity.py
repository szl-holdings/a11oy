from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "verify_hf_repository_parity.py"
GITHUB_REPO = "szl-holdings/a11oy"
HF_REPO = "SZLHOLDINGS/a11oy"
SPEC = importlib.util.spec_from_file_location("verify_hf_repository_parity", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QueueOpener:
    def __init__(self, payloads: list[bytes]) -> None:
        self.payloads = list(payloads)

    def __call__(self, _request, timeout: int):
        if timeout != 30 or not self.payloads:
            raise AssertionError("unexpected HTTP request")
        return io.BytesIO(self.payloads.pop(0))


class ImmutableRepositoryParityTests(unittest.TestCase):
    @staticmethod
    def candidate_report(
        *,
        github_ref: str,
        hf_ref: str,
        findings: list[dict[str, object]],
    ) -> dict[str, object]:
        warning = {
            "kind": "missing-both",
            "path": "well-known/security.txt",
            "severity": "warn",
        }
        return {
            "schema": 1,
            "status": "drift" if findings else "ok",
            "error_count": len(findings),
            "warn_count": 1,
            "files_compared": 1180,
            "github_ref": github_ref,
            "github_repo": GITHUB_REPO,
            "hf_ref": hf_ref,
            "hf_repo": HF_REPO,
            "findings": [*findings, warning],
        }

    def test_revision_must_be_exact_and_stable(self) -> None:
        revision = "1" * 40
        opener = QueueOpener([json.dumps({"sha": revision}).encode()] * 2)
        self.assertEqual(
            MODULE.resolve_stable_revision(
                "SZLHOLDINGS/a11oy", opener=opener, pause=lambda _: None
            ),
            revision,
        )

    def test_revision_movement_fails_closed(self) -> None:
        opener = QueueOpener(
            [
                json.dumps({"sha": "1" * 40}).encode(),
                json.dumps({"sha": "2" * 40}).encode(),
            ]
        )
        with self.assertRaisesRegex(MODULE.ParityError, "moved during admission"):
            MODULE.resolve_stable_revision(
                "SZLHOLDINGS/a11oy", opener=opener, pause=lambda _: None
            )

    def test_invalid_or_unavailable_revision_fails_closed(self) -> None:
        for payload in ({"sha": "main"}, {"sha": None}, []):
            with self.subTest(payload=payload):
                with self.assertRaises(MODULE.ParityError):
                    MODULE.resolve_stable_revision(
                        "SZLHOLDINGS/a11oy",
                        opener=QueueOpener([json.dumps(payload).encode()]),
                        pause=lambda _: None,
                    )

    def test_report_requires_exact_refs_and_only_guarded_dot_warning(self) -> None:
        github_ref = "a" * 40
        hf_ref = "b" * 40
        report = {
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
                    "detail": "covered separately",
                }
            ],
        }
        MODULE.validate_report(
            report,
            github_repo=GITHUB_REPO,
            github_ref=github_ref,
            hf_repo=HF_REPO,
            hf_ref=hf_ref,
        )
        for key, value in (
            ("status", "inconclusive"),
            ("hf_ref", "main"),
            ("warn_count", 0),
            ("schema", True),
            ("schema", 2),
            ("github_repo", "untrusted/example"),
            ("hf_repo", "untrusted/example"),
        ):
            broken = dict(report)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(MODULE.ParityError):
                MODULE.validate_report(
                    broken,
                    github_repo=GITHUB_REPO,
                    github_ref=github_ref,
                    hf_repo=HF_REPO,
                    hf_ref=hf_ref,
                )

        for counter in ("error_count", "warn_count", "files_compared"):
            broken = dict(report)
            broken[counter] = True
            with self.subTest(counter=counter), self.assertRaisesRegex(
                MODULE.ParityError, "exact integer"
            ):
                MODULE.validate_report(
                    broken,
                    github_repo=GITHUB_REPO,
                    github_ref=github_ref,
                    hf_repo=HF_REPO,
                    hf_ref=hf_ref,
                )

        for findings in (
            [],
            [report["findings"][0], "unexpected-malformed-entry"],
            ["unexpected-malformed-entry"],
        ):
            broken = dict(report)
            broken["findings"] = findings
            with self.subTest(findings=findings), self.assertRaises(
                MODULE.ParityError
            ):
                MODULE.validate_report(
                    broken,
                    github_repo=GITHUB_REPO,
                    github_ref=github_ref,
                    hf_repo=HF_REPO,
                    hf_ref=hf_ref,
                )

    def test_leading_dot_source_is_compared_byte_for_byte(self) -> None:
        payload = b"Contact: mailto:security@example.test\n"
        digest = MODULE.verify_leading_dot_copy(
            github_repo="szl-holdings/a11oy",
            github_ref="a" * 40,
            hf_repo="SZLHOLDINGS/a11oy",
            hf_ref="c" * 40,
            opener=QueueOpener([payload, payload]),
        )
        self.assertEqual(len(digest), 64)
        with self.assertRaisesRegex(
            MODULE.ParityError, "dot-prefixed COPY source drift"
        ):
            MODULE.verify_leading_dot_copy(
                github_repo="szl-holdings/a11oy",
                github_ref="a" * 40,
                hf_repo="SZLHOLDINGS/a11oy",
                hf_ref="c" * 40,
                opener=QueueOpener([payload, b"different"]),
            )

    def test_github_tree_must_be_complete_and_contain_dot_source(self) -> None:
        complete = {
            "truncated": False,
            "tree": [
                {"path": ".well-known/security.txt", "type": "blob", "sha": "1" * 40}
            ],
        }
        MODULE.verify_github_tree_complete(
            "szl-holdings/a11oy",
            github_ref="a" * 40,
            opener=QueueOpener([json.dumps(complete).encode()]),
        )
        for broken in (
            {"truncated": True, "tree": complete["tree"]},
            {"truncated": False, "tree": []},
        ):
            with self.subTest(broken=broken), self.assertRaises(MODULE.ParityError):
                MODULE.verify_github_tree_complete(
                    "szl-holdings/a11oy",
                    github_ref="a" * 40,
                    opener=QueueOpener([json.dumps(broken).encode()]),
                )

    def test_review_bound_candidate_byte_modification_is_admitted(self) -> None:
        base_ref = "1" * 40
        github_ref = "2" * 40
        hf_ref = "3" * 40
        path = "pages/verify.html"
        finding = {
            "kind": "drift",
            "path": path,
            "severity": "error",
            "ahead": "github",
            "lineage_conflict": False,
            "github_sha": "b" * 40,
            "hf_oid": "a" * 40,
        }
        report = self.candidate_report(
            github_ref=github_ref, hf_ref=hf_ref, findings=[finding]
        )
        admitted = MODULE.validate_candidate_report(
            report,
            base_ref=base_ref,
            github_repo=GITHUB_REPO,
            github_ref=github_ref,
            hf_repo=HF_REPO,
            hf_ref=hf_ref,
            base_tree={path: "a" * 40},
            head_tree={path: "b" * 40},
            expected_files_compared=1180,
        )
        self.assertEqual(admitted, [path])

    def test_candidate_drift_on_unchanged_path_fails(self) -> None:
        base_ref = "1" * 40
        github_ref = "2" * 40
        hf_ref = "3" * 40
        path = "pages/verify.html"
        report = self.candidate_report(
            github_ref=github_ref,
            hf_ref=hf_ref,
            findings=[
                {
                    "kind": "drift",
                    "path": path,
                    "severity": "error",
                    "ahead": "github",
                    "lineage_conflict": False,
                    "github_sha": "b" * 40,
                    "hf_oid": "a" * 40,
                }
            ],
        )
        with self.assertRaisesRegex(MODULE.ParityError, "not an exact reviewed"):
            MODULE.validate_candidate_report(
                report,
                base_ref=base_ref,
                github_repo=GITHUB_REPO,
                github_ref=github_ref,
                hf_repo=HF_REPO,
                hf_ref=hf_ref,
                base_tree={path: "a" * 40},
                head_tree={path: "a" * 40},
                expected_files_compared=1180,
            )

    def test_candidate_ahead_label_is_metadata_not_content_authority(self) -> None:
        base_ref = "1" * 40
        github_ref = "2" * 40
        hf_ref = "3" * 40
        path = "pages/verify.html"
        for ahead in MODULE.CANDIDATE_AHEAD_VALUES:
            finding = {
                "kind": "drift",
                "path": path,
                "severity": "error",
                "ahead": ahead,
                "lineage_conflict": False,
                "github_sha": "b" * 40,
                "hf_oid": "a" * 40,
            }
            report = self.candidate_report(
                github_ref=github_ref,
                hf_ref=hf_ref,
                findings=[finding],
            )
            with self.subTest(ahead=ahead):
                self.assertEqual(
                    MODULE.validate_candidate_report(
                        report,
                        base_ref=base_ref,
                        github_repo=GITHUB_REPO,
                        github_ref=github_ref,
                        hf_repo=HF_REPO,
                        hf_ref=hf_ref,
                        base_tree={path: "a" * 40},
                        head_tree={path: "b" * 40},
                        expected_files_compared=1180,
                    ),
                    [path],
                )

    def test_candidate_non_drift_invalid_ahead_or_lineage_findings_fail(self) -> None:
        base_ref = "1" * 40
        github_ref = "2" * 40
        hf_ref = "3" * 40
        path = "pages/verify.html"
        variants = (
            {"kind": "missing-hf", "ahead": "github", "lineage_conflict": False},
            {"kind": "drift", "ahead": "newest", "lineage_conflict": False},
            {"kind": "drift", "ahead": None, "lineage_conflict": False},
            {"kind": "drift", "ahead": "github", "lineage_conflict": True},
        )
        for variant in variants:
            finding = {"path": path, "severity": "error", **variant}
            report = self.candidate_report(
                github_ref=github_ref, hf_ref=hf_ref, findings=[finding]
            )
            with self.subTest(variant=variant), self.assertRaisesRegex(
                MODULE.ParityError, "unexplained candidate"
            ):
                MODULE.validate_candidate_report(
                    report,
                    base_ref=base_ref,
                    github_repo=GITHUB_REPO,
                    github_ref=github_ref,
                    hf_repo=HF_REPO,
                    hf_ref=hf_ref,
                    base_tree={path: "a" * 40},
                    head_tree={path: "b" * 40},
                    expected_files_compared=1180,
                )

    def test_candidate_finding_hashes_must_match_reviewed_trees(self) -> None:
        base_ref = "1" * 40
        github_ref = "2" * 40
        hf_ref = "3" * 40
        path = "pages/verify.html"
        finding = {
            "kind": "drift",
            "path": path,
            "severity": "error",
            "ahead": "github",
            "lineage_conflict": False,
            "github_sha": "b" * 40,
            "hf_oid": "a" * 40,
        }
        for key, value in (
            ("github_sha", "c" * 40),
            ("github_sha", None),
            ("hf_oid", "c" * 40),
            ("hf_oid", None),
        ):
            broken_finding = dict(finding)
            if value is None:
                broken_finding.pop(key)
            else:
                broken_finding[key] = value
            report = self.candidate_report(
                github_ref=github_ref, hf_ref=hf_ref, findings=[broken_finding]
            )
            with self.subTest(key=key, value=value), self.assertRaisesRegex(
                MODULE.ParityError, "hashes are not bound"
            ):
                MODULE.validate_candidate_report(
                    report,
                    base_ref=base_ref,
                    github_repo=GITHUB_REPO,
                    github_ref=github_ref,
                    hf_repo=HF_REPO,
                    hf_ref=hf_ref,
                    base_tree={path: "a" * 40},
                    head_tree={path: "b" * 40},
                    expected_files_compared=1180,
                )

    def test_candidate_comparator_exit_code_is_bound_to_validated_drift(self) -> None:
        MODULE.validate_candidate_exit_code(0, [])
        MODULE.validate_candidate_exit_code(1, ["pages/verify.html"])
        for returncode, admitted in (
            (1, []),
            (0, ["pages/verify.html"]),
            (2, []),
            (2, ["pages/verify.html"]),
        ):
            with self.subTest(
                returncode=returncode, admitted=admitted
            ), self.assertRaisesRegex(MODULE.ParityError, "exit/report mismatch"):
                MODULE.validate_candidate_exit_code(returncode, admitted)

        for returncode in (False, True, None, "1"):
            with self.subTest(returncode=returncode), self.assertRaisesRegex(
                MODULE.ParityError, "exact integer"
            ):
                MODULE.validate_candidate_exit_code(returncode, [])

    def test_candidate_report_refs_and_counters_remain_exact(self) -> None:
        base_ref = "1" * 40
        github_ref = "2" * 40
        hf_ref = "3" * 40
        report = self.candidate_report(
            github_ref=github_ref, hf_ref=hf_ref, findings=[]
        )
        MODULE.validate_candidate_report(
            report,
            base_ref=base_ref,
            github_repo=GITHUB_REPO,
            github_ref=github_ref,
            hf_repo=HF_REPO,
            hf_ref=hf_ref,
            base_tree={"Dockerfile": "a" * 40},
            head_tree={"Dockerfile": "a" * 40},
            expected_files_compared=1180,
        )
        for key, value in (
            ("github_ref", base_ref),
            ("hf_ref", base_ref),
            ("error_count", True),
            ("files_compared", 0),
            ("files_compared", 1),
            ("files_compared", -1),
            ("status", "inconclusive"),
            ("schema", True),
            ("schema", 2),
            ("github_repo", "untrusted/example"),
            ("hf_repo", "untrusted/example"),
        ):
            broken = dict(report)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(MODULE.ParityError):
                MODULE.validate_candidate_report(
                    broken,
                    base_ref=base_ref,
                    github_repo=GITHUB_REPO,
                    github_ref=github_ref,
                    hf_repo=HF_REPO,
                    hf_ref=hf_ref,
                    base_tree={"Dockerfile": "a" * 40},
                    head_tree={"Dockerfile": "a" * 40},
                    expected_files_compared=1180,
                )

    def test_candidate_additions_deletions_and_duplicate_findings_fail(self) -> None:
        base_ref = "1" * 40
        github_ref = "2" * 40
        hf_ref = "3" * 40
        path = "pages/verify.html"
        finding = {
            "kind": "drift",
            "path": path,
            "severity": "error",
            "ahead": "github",
            "lineage_conflict": False,
            "github_sha": "b" * 40,
            "hf_oid": "a" * 40,
        }
        variants = (
            ({}, {path: "b" * 40}, [finding]),
            ({path: "a" * 40}, {}, [finding]),
            ({path: "a" * 40}, {path: "b" * 40}, [finding, finding]),
        )
        for base_tree, head_tree, findings in variants:
            report = self.candidate_report(
                github_ref=github_ref, hf_ref=hf_ref, findings=findings
            )
            with self.subTest(
                base_tree=base_tree, head_tree=head_tree, count=len(findings)
            ), self.assertRaises(MODULE.ParityError):
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
                )

    def test_candidate_cannot_change_protected_admission_inputs(self) -> None:
        base_tree = {
            path: str(index) * 40
            for index, path in enumerate(MODULE.PROTECTED_CANDIDATE_INPUTS, start=1)
        }
        MODULE.validate_protected_candidate_inputs(base_tree, dict(base_tree))
        for path in MODULE.PROTECTED_CANDIDATE_INPUTS:
            changed = dict(base_tree)
            changed[path] = "f" * 40
            with self.subTest(path=path), self.assertRaisesRegex(
                MODULE.ParityError, "protected admission input"
            ):
                MODULE.validate_protected_candidate_inputs(base_tree, changed)
            for remove_from in ("base", "head", "both"):
                missing_base = dict(base_tree)
                missing_head = dict(base_tree)
                if remove_from in ("base", "both"):
                    missing_base.pop(path)
                if remove_from in ("head", "both"):
                    missing_head.pop(path)
                with self.subTest(
                    path=path, remove_from=remove_from
                ), self.assertRaisesRegex(
                    MODULE.ParityError, "protected admission input"
                ):
                    MODULE.validate_protected_candidate_inputs(
                        missing_base, missing_head
                    )

    def test_candidate_must_be_a_strict_descendant(self) -> None:
        base_ref = "1" * 40
        github_ref = "2" * 40
        with self.assertRaisesRegex(MODULE.ParityError, "strict descendant"):
            MODULE.verify_ancestry(
                GITHUB_REPO,
                base_ref=base_ref,
                github_ref=base_ref,
                opener=QueueOpener([]),
            )
        identical_report = self.candidate_report(
            github_ref=base_ref,
            hf_ref="3" * 40,
            findings=[],
        )
        with self.assertRaisesRegex(MODULE.ParityError, "strict descendant"):
            MODULE.validate_candidate_report(
                identical_report,
                base_ref=base_ref,
                github_repo=GITHUB_REPO,
                github_ref=base_ref,
                hf_repo=HF_REPO,
                hf_ref="3" * 40,
                base_tree={"Dockerfile": "a" * 40},
                head_tree={"Dockerfile": "a" * 40},
                expected_files_compared=1180,
            )
        MODULE.verify_ancestry(
            GITHUB_REPO,
            base_ref=base_ref,
            github_ref=github_ref,
            opener=QueueOpener([json.dumps({"status": "ahead"}).encode()]),
        )
        for status in ("identical", "behind", "diverged", None):
            with self.subTest(status=status), self.assertRaisesRegex(
                MODULE.ParityError, "not a strict descendant"
            ):
                MODULE.verify_ancestry(
                    GITHUB_REPO,
                    base_ref=base_ref,
                    github_ref=github_ref,
                    opener=QueueOpener(
                        [json.dumps({"status": status}).encode()]
                    ),
                )

    def test_candidate_main_runs_base_then_head_with_one_immutable_hf_ref(self) -> None:
        base_ref = "1" * 40
        github_ref = "2" * 40
        hf_ref = "3" * 40
        changed_path = "pages/verify.html"
        protected = {
            path: str(index) * 40
            for index, path in enumerate(MODULE.PROTECTED_CANDIDATE_INPUTS, start=4)
        }
        base_tree = {**protected, changed_path: "a" * 40}
        head_tree = {**protected, changed_path: "b" * 40}
        base_report = self.candidate_report(
            github_ref=base_ref,
            hf_ref=hf_ref,
            findings=[],
        )
        candidate_report = self.candidate_report(
            github_ref=github_ref,
            hf_ref=hf_ref,
            findings=[
                {
                    "kind": "drift",
                    "path": changed_path,
                    "severity": "error",
                    "ahead": "huggingface?",
                    "lineage_conflict": False,
                    "github_sha": head_tree[changed_path],
                    "hf_oid": base_tree[changed_path],
                }
            ],
        )

        def run_comparator(**kwargs):
            is_base = kwargs["github_ref"] == base_ref
            kwargs["report_out"].write_text(
                json.dumps(base_report if is_base else candidate_report),
                encoding="utf-8",
            )
            return MODULE.subprocess.CompletedProcess(
                [], 0 if is_base else 1, stdout=""
            )

        with tempfile.TemporaryDirectory() as temporary:
            report_out = Path(temporary) / "admission.json"
            with (
                mock.patch.object(
                    MODULE,
                    "resolve_stable_revision",
                    return_value=hf_ref,
                ) as resolve,
                mock.patch.object(
                    MODULE,
                    "github_blob_tree",
                    side_effect=[head_tree, base_tree],
                ) as trees,
                mock.patch.object(MODULE, "verify_ancestry") as ancestry,
                mock.patch.object(
                    MODULE,
                    "verify_leading_dot_copy",
                    return_value="d" * 64,
                ) as leading_dot,
                mock.patch.object(
                    MODULE,
                    "run_comparator",
                    side_effect=run_comparator,
                ) as comparator,
                mock.patch.object(MODULE.sys, "stdout", io.StringIO()),
            ):
                result = MODULE.main(
                    [
                        "--tools-script",
                        str(SCRIPT),
                        "--github-repo",
                        GITHUB_REPO,
                        "--base-ref",
                        base_ref,
                        "--github-ref",
                        github_ref,
                        "--hf-repo",
                        HF_REPO,
                        "--report-out",
                        str(report_out),
                    ]
                )
            output = json.loads(report_out.read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        resolve.assert_called_once_with(HF_REPO)
        self.assertEqual(
            [call.kwargs["github_ref"] for call in trees.call_args_list],
            [github_ref, base_ref],
        )
        ancestry.assert_called_once_with(
            GITHUB_REPO,
            base_ref=base_ref,
            github_ref=github_ref,
        )
        leading_dot.assert_called_once_with(
            github_repo=GITHUB_REPO,
            github_ref=base_ref,
            hf_repo=HF_REPO,
            hf_ref=hf_ref,
        )
        self.assertEqual(
            [call.kwargs["github_ref"] for call in comparator.call_args_list],
            [base_ref, github_ref],
        )
        self.assertTrue(
            all(
                call.kwargs["hf_ref"] == hf_ref
                and call.kwargs["capture"] is True
                for call in comparator.call_args_list
            )
        )
        self.assertEqual(output["base_ref"], base_ref)
        self.assertEqual(output["github_ref"], github_ref)
        self.assertEqual(output["immutable_hf_ref"], hf_ref)
        self.assertEqual(output["review_bound_drift_paths"], [changed_path])
        self.assertEqual(output["candidate_changed_path_count"], 1)
        self.assertEqual(output["admission_status"], "ok")
        self.assertEqual(output["proof_status"], "review-bound-candidate-delta")

    def test_comparator_invocation_is_immutable_and_has_no_allowlist(self) -> None:
        github_ref = "1" * 40
        hf_ref = "2" * 40
        tools_script = ROOT / ".github" / "scripts" / "comparator.py"
        report_out = ROOT / "candidate-report.json"
        completed = MODULE.subprocess.CompletedProcess([], 0, stdout="")
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed) as run:
            self.assertIs(
                MODULE.run_comparator(
                    tools_script=tools_script,
                    github_repo=GITHUB_REPO,
                    github_ref=github_ref,
                    hf_repo=HF_REPO,
                    hf_ref=hf_ref,
                    report_out=report_out,
                    capture=True,
                ),
                completed,
            )
        command = run.call_args.args[0]
        self.assertEqual(
            command,
            [
                MODULE.sys.executable,
                str(tools_script),
                "--github-remote",
                "--github-repo",
                GITHUB_REPO,
                "--hf-repo",
                HF_REPO,
                "--github-ref",
                github_ref,
                "--hf-ref",
                hf_ref,
                "--allow",
                "",
                "--report-out",
                str(report_out),
            ],
        )
        self.assertEqual(
            run.call_args.kwargs,
            {
                "check": False,
                "text": True,
                "stdout": MODULE.subprocess.PIPE,
                "stderr": MODULE.subprocess.STDOUT,
            },
        )


class FailedParityReceiptTests(unittest.TestCase):
    def exercise_failure(self, raw=None, *, resolve_error=None, returncode=1):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'failure.json'
            output.write_text('{"proof_status":"exact","stale":true}')
            def comparator(**arguments):
                if raw is not None:
                    arguments['report_out'].write_bytes(raw)
                return MODULE.subprocess.CompletedProcess([],returncode,stdout='bounded comparator failure')
            with mock.patch.object(MODULE,'resolve_stable_revision',side_effect=resolve_error,return_value='b'*40), \
                    mock.patch.object(MODULE,'github_blob_tree',return_value={}), \
                    mock.patch.object(MODULE,'run_comparator',side_effect=comparator), \
                    mock.patch.object(MODULE.sys,'stderr',io.StringIO()):
                with self.assertRaises((MODULE.ParityError,OSError,json.JSONDecodeError,UnicodeError,RecursionError)):
                    MODULE.main(['--tools-script',str(SCRIPT),'--github-repo',GITHUB_REPO,
                                 '--github-ref','a'*40,'--hf-repo',HF_REPO,'--report-out',str(output)])
            value=json.loads(output.read_text())
        self.assertEqual(value['schema'],'szl.hf-repository-parity-failure/v1')
        self.assertEqual(value['status'],'blocked')
        self.assertEqual(value['proof_status'],'unproved')
        self.assertIs(value['complete'],False)
        self.assertEqual(value['github_ref'],'a'*40)
        self.assertEqual(value['hf_repo'],HF_REPO)
        self.assertNotIn('stale',value)
        self.assertNotIn('leading_dot_copy',value)
        self.assertIn('observed_at',value)
        return value

    def test_nonzero_comparator_retains_drift_and_digest_then_fails(self):
        raw=json.dumps({'status':'drift','error_count':1,'findings':[{'path':'routers/data/model-pretraining-snapshot.json'}]}).encode()
        value=self.exercise_failure(raw)
        self.assertEqual(value['immutable_hf_ref'],'b'*40)
        self.assertEqual(value['comparators']['strict']['report'],json.loads(raw))
        self.assertEqual(value['comparators']['strict']['sha256'],MODULE.hashlib.sha256(raw).hexdigest())
        self.assertIn('non-zero',value['reason'])

    def test_invalid_json_retains_digest_and_stays_unproved(self):
        raw=b'{"partial":'
        value=self.exercise_failure(raw)
        self.assertEqual(value['error_type'],'JSONDecodeError')
        self.assertEqual(value['comparators']['strict']['sha256'],MODULE.hashlib.sha256(raw).hexdigest())
        self.assertNotIn('report',value['comparators']['strict'])

    def test_missing_report_does_not_leave_stale_success(self):
        value=self.exercise_failure()
        self.assertEqual(value['error_type'],'FileNotFoundError')
        self.assertEqual(value['comparators'],{})

    def test_invalid_utf8_retains_digest_and_stays_unproved(self):
        value=self.exercise_failure(b'\xff')
        self.assertEqual(value['error_type'],'UnicodeDecodeError')
        self.assertNotIn('report',value['comparators']['strict'])

    def test_json_decoder_recursion_failure_retains_digest(self):
        raw=b'['*10000+b'0'+b']'*10000
        value=self.exercise_failure(raw)
        self.assertEqual(value['error_type'],'RecursionError')
        self.assertEqual(value['comparators']['strict']['sha256'],MODULE.hashlib.sha256(raw).hexdigest())
        self.assertNotIn('report',value['comparators']['strict'])

    def test_deep_valid_json_cannot_break_failure_receipt_encoding(self):
        value=self.exercise_failure(b'['*64+b'0'+b']'*64)
        self.assertEqual(value['error_type'],'ParityError')
        self.assertIn('nesting',value['reason'])
        self.assertNotIn('report',value['comparators']['strict'])

    def test_unavailable_hub_does_not_invent_revision(self):
        value=self.exercise_failure(resolve_error=MODULE.ParityError('Hub unavailable'))
        self.assertIsNone(value['immutable_hf_ref'])
        self.assertEqual(value['reason'],'Hub unavailable')

    def test_zero_exit_invalid_report_still_fails_and_retains_evidence(self):
        value=self.exercise_failure(b'{"status":"ok"}',returncode=0)
        self.assertEqual(value['error_type'],'ParityError')
        self.assertEqual(value['comparators']['strict']['report'],{'status':'ok'})


if __name__ == "__main__":
    unittest.main(verbosity=2)
