# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
from pathlib import Path

SCRIPT = Path("scripts/hf_publish_vertical_flagships_v2.py")
WORKFLOW = Path(".github/workflows/hf-publish-vertical-flagships.yml")


def test_publisher_compiles_and_carries_public_experience_v3_contract() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    ast.parse(source)
    assert 'data-szl-public-experience-v3="true"' in source
    assert 'PUBLIC_EXPERIENCE_VERSION = "3.0.0"' in source
    assert "overflow-x:hidden" in source
    assert "overflow-wrap:anywhere" in source
    assert '"schema": "szl.hf-vertical-flagships/v3"' in source
    assert 'root.get("v3_marker") is True' in source


def test_archived_vertical_repositories_are_not_advertised_as_sources() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "https://github.com/szl-holdings/counsel" not in source
    assert "https://github.com/szl-holdings/szl-fleet-overlay" not in source
    assert "a11oy/tree/main/verticals/counsel" in source
    assert "a11oy/tree/main/verticals/vessels" in source


def test_execution_trigger_is_single_diff_and_protected_main_bound() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "exec/hf-publish-vertical-flagships-v3" in workflow
    assert "ops/hf-publish-vertical-flagships-v3.trigger" in workflow
    assert 'test "$EXPECTED_BASE" = "$current_main"' in workflow
    assert 'test "${#changed[@]}" -eq 1' in workflow
    assert "persist-credentials: false" in workflow
