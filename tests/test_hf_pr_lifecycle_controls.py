from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / ".github" / "workflows" / "hf-backup-restore.yml"
OPERATIONAL = ROOT / ".github" / "workflows" / "operational.yml"
DRIFT = ROOT / ".github" / "workflows" / "hf-ecosystem-drift.yml"


def test_dependabot_prs_run_a_secret_free_snapshot_contract() -> None:
    workflow = BACKUP.read_text(encoding="utf-8")
    pr_job, backup_job = workflow.split("\n  snapshot-backup:", 1)
    assert "pr-contract:" in pr_job
    assert "if: github.event_name == 'pull_request'" in pr_job
    assert "tests/test_hf_snapshot_restore.py" in pr_job
    assert "secrets." not in pr_job
    assert "Snapshot and restore both live Spaces" not in pr_job
    assert "if: github.event_name == 'workflow_dispatch'" in backup_job
    assert "HF_ORG_TOKEN || secrets.HF_TOKEN" in backup_job
    assert "Require the managed Hugging Face identity" in backup_job


def test_external_ecosystem_drift_does_not_deadlock_pull_requests() -> None:
    workflow = OPERATIONAL.read_text(encoding="utf-8")
    live_step = workflow.index("Verify live tracked Hugging Face ecosystem manifest")
    offline_step = workflow.index("Validate operational surfaces")
    assert live_step < offline_step
    assert "if: github.event_name != 'pull_request'" in workflow[live_step:offline_step]
    assert "pnpm hf:ecosystem:audit" in workflow[live_step:offline_step]
    assert "pnpm hf:ecosystem:audit" not in workflow[offline_step:]


def test_drift_controller_keeps_live_detection_and_deterministic_issue_evidence() -> None:
    workflow = DRIFT.read_text(encoding="utf-8")
    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "push:\n    branches: [main]" in workflow
    assert "issues: write" in workflow
    assert "huggingface-ecosystem-manifest.candidate.json" in workflow
    assert "[HF-ECOSYSTEM-DRIFT] Public manifest is stale" in workflow
    assert 'test "${STATE}" = "CURRENT"' in workflow
    assert "pull_request:" not in workflow
