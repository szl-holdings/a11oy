# SPDX-License-Identifier: Apache-2.0
"""Offline regression controls for the bounded keeper-policy grammar."""
from pathlib import Path
import tempfile
import unittest

from scripts.hf_keep_policy import KeepPolicyError, load_keep_ids


class KeepPolicyContinuationTests(unittest.TestCase):
    def parse(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keep.yaml"
            path.write_text(text, encoding="utf-8")
            return load_keep_ids(path)

    def test_metadata_and_nested_lists_preserve_only_keeper_ids(self) -> None:
        policy = (
            'as_of: "2026-09-05"\n'
            "keep:\n"
            "  - id: SZLHOLDINGS/killinchu\n"
            "    role: cyber_physical_resilience\n"
            "    dest: https://example.invalid/command\n"
            "    capability_planes:\n"
            "      - evidence\n"
            "      - counter-uas\n"
            "    dependencies:\n"
            "      - szl-holdings/szl-second-brain\n"
            "  - id: SZLHOLDINGS/a11oy\n"
            "    role: command\n"
            "retire_into_killinchu:\n"
            "  - id: SZLHOLDINGS/ayllu\n"
        )
        self.assertEqual(
            self.parse(policy),
            ["SZLHOLDINGS/a11oy", "SZLHOLDINGS/killinchu"],
        )

    def test_plain_scalar_continuations_fail_closed(self) -> None:
        for indentation in (3, 4, 5, 6, 8, 12):
            for separator in ("", "\n", "    # retained comment\n"):
                with self.subTest(indentation=indentation, separator=separator):
                    policy = (
                        "keep:\n  - id: SZLHOLDINGS/a11oy\n"
                        + separator
                        + " " * indentation
                        + "continuation\n"
                    )
                    with self.assertRaisesRegex(
                        KeepPolicyError, "unsupported keeper continuation"
                    ):
                        self.parse(policy)

    def test_metadata_scalar_continuations_fail_closed(self) -> None:
        with self.assertRaisesRegex(
            KeepPolicyError, "unsupported keeper continuation"
        ):
            self.parse(
                "keep:\n  - id: SZLHOLDINGS/a11oy\n"
                "    role: command\n      continuation\n"
            )

    def test_nested_list_requires_an_empty_sibling_field(self) -> None:
        for prefix in (
            "",
            "    role: command\n",
            "    dependencies:\n      - first\n  - id: SZLHOLDINGS/terra\n",
        ):
            with self.subTest(prefix=prefix):
                with self.assertRaisesRegex(
                    KeepPolicyError, "unsupported keeper continuation"
                ):
                    self.parse(
                        "keep:\n  - id: SZLHOLDINGS/a11oy\n"
                        + prefix
                        + "      - orphan\n"
                    )

    def test_duplicate_id_and_metadata_are_rejected(self) -> None:
        for fields in (
            "    id: SZLHOLDINGS/terra\n",
            "    role: command\n    role: changed\n",
        ):
            with self.subTest(fields=fields):
                with self.assertRaisesRegex(
                    KeepPolicyError, "duplicate keeper metadata"
                ):
                    self.parse("keep:\n  - id: SZLHOLDINGS/a11oy\n" + fields)

    def test_comments_and_quoted_ids_retain_valid_projection(self) -> None:
        self.assertEqual(
            self.parse(
                "keep:\n"
                '  - id: "SZLHOLDINGS/a11oy"\n'
                "# top-level comments do not end the section\n"
                "\n"
                "    dependencies:\n"
                "      # nested comments do not close the list\n"
                "      - szl-holdings/szl-second-brain\n"
                "  - id: 'SZLHOLDINGS/terra'\n"
                "    role: real_estate\n"
            ),
            ["SZLHOLDINGS/a11oy", "SZLHOLDINGS/terra"],
        )

    def test_metadata_before_first_keeper_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            KeepPolicyError, "unsupported keeper continuation"
        ):
            self.parse("keep:\n    role: command\n  - id: SZLHOLDINGS/a11oy\n")

    def test_prior_invalid_id_and_duplicate_controls_remain_rejected(self) -> None:
        for policy in (
            "keep:\n  - id: [SZLHOLDINGS/a11oy]\n",
            "keep:\n  - {id: SZLHOLDINGS/a11oy}\n",
            "keep:\n  - id: SZLHOLDINGS/a11oy\n  - id: SZLHOLDINGS/a11oy\n",
            "keep:\n  - id: SZLHOLDINGS/a11oy\n\tcontinuation\n",
            "keep:\n  - id: SZLHOLDINGS/a11oy\n    dependencies:\n"
            "      - first\n        continuation\n",
        ):
            with self.subTest(policy=policy):
                with self.assertRaises(KeepPolicyError):
                    self.parse(policy)


if __name__ == "__main__":
    unittest.main()
