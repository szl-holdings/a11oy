from __future__ import annotations

import importlib.util
import io
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "verify_hf_repository_parity.py"
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
            "status": "ok",
            "error_count": 0,
            "warn_count": 1,
            "files_compared": 1180,
            "github_ref": github_ref,
            "hf_ref": hf_ref,
            "findings": [
                {
                    "kind": "missing-both",
                    "path": "well-known/security.txt",
                    "severity": "warn",
                    "detail": "covered separately",
                }
            ],
        }
        MODULE.validate_report(report, github_ref=github_ref, hf_ref=hf_ref)
        for key, value in (
            ("status", "inconclusive"),
            ("hf_ref", "main"),
            ("warn_count", 0),
        ):
            broken = dict(report)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(MODULE.ParityError):
                MODULE.validate_report(broken, github_ref=github_ref, hf_ref=hf_ref)

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
                MODULE.validate_report(broken, github_ref=github_ref, hf_ref=hf_ref)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
