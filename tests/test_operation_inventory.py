# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
from scripts.generate_operation_inventory import action_inventory


def test_workflow_action_inventory_covers_every_uses_reference():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    expected = 0
    for workflow in (root / ".github" / "workflows").glob("*.y*ml"):
        expected += sum(1 for line in workflow.read_text(encoding="utf-8").splitlines() if "uses:" in line)
    inventory = action_inventory(root)
    assert len(inventory) == expected
    assert all(item["workflow"].startswith(".github/workflows/") for item in inventory)
    assert all(item["reference"] for item in inventory)
