"""Live operational files must not embed owner-home paths."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LIVE = [
    ROOT / "audit" / "release-gate.json",
    ROOT / "audit" / "frontier-command-probes.json",
    ROOT / "audit" / "frontier-convergence-manifest.json",
    ROOT / ".github" / "workflows" / "nemo-v3-isolated-owner-dispatch.yml",
    ROOT / "docs" / "SZL_NEMO_FINE_TUNING.md",
    ROOT / "model_release" / "szl-nemo" / "LOW_VRAM_CALIBRATION.md",
]

NEEDLES = (
    r"C:\Users\steph",
    r"C:/Users/steph",
    "/Users/steph",
    "/mnt/c/Users/steph",
)


def test_live_frontier_files_have_no_owner_home_paths() -> None:
    for path in LIVE:
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        for needle in NEEDLES:
            assert needle not in text, f"{path.name} still contains {needle!r}"


def test_live_audit_json_still_parses() -> None:
    for path in LIVE:
        if path.suffix != ".json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload
