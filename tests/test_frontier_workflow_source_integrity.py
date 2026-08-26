"""Regression coverage for protected Frontier workflow source constants."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPAIR_SCRIPT = ROOT / "ops/frontier/v16_7/apply_current_main_repairs.py"
SOURCE_TEST = ROOT / "ops/frontier/v16_7/test_frontier_v16_7_terminal_truth.py"
CONTRACT = ROOT / "ops/frontier/v16_7/SOLO_EXECUTION_CONTRACT.json"
WORKFLOWS = (
    ROOT / ".github/workflows/frontier-solo-qualification.yml",
    ROOT / ".github/workflows/frontier-v16-7-exact-source-builder.yml",
)
ORPHAN_DIGEST_LINE = re.compile(r"^\$[0-9a-fA-F]+$", re.MULTILINE)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frontier_workflows_bind_all_protected_inputs() -> None:
    expected = {
        "CONTRACT": _digest(CONTRACT),
        "REPAIR_SCRIPT": _digest(REPAIR_SCRIPT),
        "SOURCE_TEST": _digest(SOURCE_TEST),
    }

    for workflow in WORKFLOWS:
        source = workflow.read_text(encoding="utf-8")
        for name, digest in expected.items():
            matches = re.findall(
                rf"^      {name}_SHA256: ([0-9a-f]{{64}})$",
                source,
                re.MULTILINE,
            )
            assert matches == [digest], (workflow, name)
            assert source.count(f"${name}_SHA256") >= 1, (workflow, name)
        assert ORPHAN_DIGEST_LINE.search(source) is None, workflow
