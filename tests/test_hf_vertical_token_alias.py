#!/usr/bin/env python3
"""Regression contract for the combined vertical publisher token bridge."""
from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "hf_publish_vertical_flagships_v4.py"
SPEC = importlib.util.spec_from_file_location("hf_publish_vertical_flagships_v4", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load vertical publisher entrypoint")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VerticalPublisherTokenAliasContract(unittest.TestCase):
    def setUp(self) -> None:
        self.original = {
            name: os.environ.get(name)
            for name in ("GITHUB_TOKEN", "GH_TOKEN")
        }
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GH_TOKEN", None)

    def tearDown(self) -> None:
        for name, value in self.original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_existing_canonical_token_wins(self) -> None:
        os.environ["GITHUB_TOKEN"] = "canonical-test-token"
        os.environ["GH_TOKEN"] = "cli-test-token"
        self.assertEqual(MODULE.normalize_github_token_alias(), "GITHUB_TOKEN")
        self.assertEqual(os.environ["GITHUB_TOKEN"], "canonical-test-token")

    def test_cli_token_is_normalized_in_process(self) -> None:
        os.environ["GH_TOKEN"] = "cli-test-token"
        self.assertEqual(MODULE.normalize_github_token_alias(), "GH_TOKEN")
        self.assertEqual(os.environ["GITHUB_TOKEN"], "cli-test-token")

    def test_missing_tokens_remain_explicitly_unavailable(self) -> None:
        self.assertEqual(MODULE.normalize_github_token_alias(), "unavailable")
        self.assertNotIn("GITHUB_TOKEN", os.environ)

    def test_entrypoint_records_source_name_not_value(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn('combined["github_token_source_name"]', source)
        self.assertIn('combined["github_token_value_recorded"] = False', source)
        self.assertNotIn("canonical-test-token", source)
        self.assertNotIn("cli-test-token", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
