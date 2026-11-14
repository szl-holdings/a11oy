#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Fail-closed coverage for the shared-module SHA-256 lock.

The workflow command checks the tree. These cases also prove a drifted or
unknown module cannot pass, so regenerating the lock stays a reviewed act.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


CHECKER = Path(__file__).resolve().parent / "shared-module-hash-check.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("shared_module_hash_check", CHECKER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {CHECKER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SharedModuleHashLockTests(unittest.TestCase):
    def test_committed_lock_matches_the_tree(self) -> None:
        checker = load_checker()
        self.assertEqual(checker._verify(checker._current_hashes()), 0)

    def test_a_changed_agent_loop_digest_fails_closed(self) -> None:
        checker = load_checker()
        current = checker._current_hashes()
        current["a11oy_agent_loop.py"] = "0" * 64
        self.assertEqual(checker._verify(current), 1)

    def test_an_unlisted_module_fails_closed(self) -> None:
        checker = load_checker()
        current = checker._current_hashes()
        current["not_a_shared_module.py"] = "ab" * 32
        self.assertEqual(checker._verify(current), 1)


if __name__ == "__main__":
    unittest.main()
