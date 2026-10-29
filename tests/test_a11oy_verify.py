""""Executable contracts for the checked-in offline receipt vectors."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VECTOR_ROOT = ROOT / "tests" / "test_vectors"
MANIFEST = json.loads((VECTOR_ROOT / "manifest.json").read_text(encoding="utf-8"))


def _verifier():
    spec = importlib.util.spec_from_file_location(
        "a11oy_verify_under_test", ROOT / "tools" / "a11oy_verify.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "vector", MANIFEST["vectors"], ids=lambda value: value["file"]
)
def test_manifest_vectors_match_verdict_and_exit_code(vector):
    verifier = _verifier()
    ledger, exit_code = verifier.verify_file(VECTOR_ROOT / vector["file"])
    expected = vector["expected_verdict"]
    expected_code = {
        "PASS": verifier.EXIT_PASS,
        "FAIL": verifier.EXIT_FAIL,
        "INCOMPLETE": verifier.EXIT_INCOMPLETE,
    }[expected]
    assert ledger.verdict == expected
    assert exit_code == expected_code


def test_duplicate_json_keys_are_rejected():
    verifier = _verifier()
    with pytest.raises(verifier._DuplicateKeyError):
        verifier.strict_json_loads('{"receipts":[],"receipts":[]}')
