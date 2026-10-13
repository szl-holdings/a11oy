"""Regression contract for manual Hugging Face reconciliation deploys."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"


def test_manual_dispatch_deploys_the_selected_commit() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    triggers = text.split("\non:\n", 1)[1].split("\npermissions:\n", 1)[0]
    assert "  workflow_dispatch:\n    inputs:\n" in triggers

    deploy = text.split("\n  deploy:\n", 1)[1].split("\n  runtime-config:\n", 1)[0]
    assert "      ref: ${{ github.sha }}\n" in deploy
    assert "|| 'main'" not in deploy

