# SPDX-License-Identifier: Apache-2.0
"""Zero-bandaid integrity contract for the runtime-boundary successor."""
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
)


def test_no_transient_repair_controller_or_import_shim_survives() -> None:
    assert [path.relative_to(ROOT).as_posix() for path in FORBIDDEN_TRANSIENTS if path.exists()] == []


def test_shared_runtime_manifest_matches_permanent_files() -> None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert value == {
        "files": {
            "szl_agentic_loop.py": "2d3805007919a677637bf9750869a2a29c5639feeb9da586534848f677de426c",
            "szl_immune.py": "fb244b7157ee5d1625f373b71826a12d0a77166ee946708b818dd5a42faa4f51",
        },
        "payload_id": "runtime-boundary-1994",
        "schema": "szl-shared-source-payload/v1",
    }
    for relative, expected in value["files"].items():
        observed = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert observed == expected
