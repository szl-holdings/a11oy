"""Regression contract for the materialized SZL-Nemo v3 curriculum."""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "model_release" / "szl-nemo-v3" / "build_curriculum.py"
TRAIN = ROOT / "model_release" / "szl-nemo-v3" / "train.jsonl"


def test_nemo_v3_curriculum_is_deterministic_and_holdouts_are_frozen():
    if not TRAIN.is_file():
        pytest.skip("materialized curriculum is created by the reviewed protected-main generator")
    subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=ROOT, check=True)
