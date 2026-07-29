from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("prove_hf_gdw_runtime.py")
SPEC = importlib.util.spec_from_file_location("prove_hf_gdw_runtime", SCRIPT)
assert SPEC and SPEC.loader
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)


def test_require_source_revision_accepts_only_exact_observed_build(monkeypatch):
    source_sha = "a" * 40
    monkeypatch.setattr(
        proof,
        "request_json",
        lambda *args, **kwargs: {
            "status": "OBSERVED",
            "build": {"revision": source_sha},
        },
    )
    assert (
        proof.require_source_revision(
            origin="https://runtime.example",
            source_sha=source_sha,
        )
        == source_sha
    )


def test_require_source_revision_rejects_declared_or_different_build(monkeypatch):
    monkeypatch.setattr(
        proof,
        "request_json",
        lambda *args, **kwargs: {
            "status": "OBSERVED",
            "build": {"revision": "b" * 40},
        },
    )
    with pytest.raises(RuntimeError, match="does not match"):
        proof.require_source_revision(
            origin="https://runtime.example",
            source_sha="a" * 40,
        )
