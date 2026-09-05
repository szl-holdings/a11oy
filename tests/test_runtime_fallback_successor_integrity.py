# SPDX-License-Identifier: Apache-2.0
"""Zero-bandaid and content-address integrity for the fallback successor."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".github" / "shared-source-payload-manifest.json"
FORBIDDEN_TRANSIENTS = (
    ROOT / "sitecustomize.py",
    ROOT / ".github" / "workflows" / "_sync_runtime_boundary_attribution_once.yml",
    ROOT / ".github" / "workflows" / "_sync_runtime_boundary_attribution_v2_once.yml",
    ROOT / ".github" / "workflows" / "_sync_runtime_boundary_attribution_v3_once.yml",
    ROOT / ".github" / "workflows" / "_materialize_runtime_boundary_current_main_once.yml",
    ROOT / ".github" / "workflows" / "_reconcile_runtime_fallback_current_main_once.yml",
    ROOT / "scripts" / "_materialize_runtime_boundary_successor.py",
)
EXPECTED_FILES = {
    "szl_agentic_loop.py": "2d3805007919a677637bf9750869a2a29c5639feeb9da586534848f677de426c",
    "szl_immune.py": "6047e4c3ac016650789a07405464a0c3bfedd14dac0cac3cc8e7327857b8893d",
}


def test_no_transient_controller_or_import_shim_survives() -> None:
    observed = [
        path.relative_to(ROOT).as_posix()
        for path in FORBIDDEN_TRANSIENTS
        if path.exists()
    ]
    assert observed == []


def test_shared_runtime_manifest_matches_permanent_files() -> None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert value == {
        "files": EXPECTED_FILES,
        "payload_id": "runtime-boundary-1994-v2",
        "schema": "szl-shared-source-payload/v1",
    }
    for relative, expected in EXPECTED_FILES.items():
        observed = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert observed == expected
