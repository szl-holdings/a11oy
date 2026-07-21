"""Regression contract for manual Hugging Face reconciliation deploys."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"


def test_manual_dispatch_deploys_the_selected_commit() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch: {}" in text
    assert (
        "ref: ${{ github.event_name == 'workflow_dispatch' && github.sha || 'main' }}"
        in text
    )

