from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "action-contract-promotion-guard.yml"


def test_promotion_guard_uses_protected_validator_and_untrusted_candidate_data() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request_target:" in text
    assert "permissions:\n  contents: read" in text
    assert "ref: ${{ github.event.pull_request.base.sha }}" in text
    assert "persist-credentials: false" in text
    assert "Checkout candidate as untrusted data" not in text
    assert "actions/github-script@" in text
    assert "ref: process.env.CANDIDATE_SHA" in text
    assert 'candidate.type !== "file"' in text
    assert 'candidate.encoding !== "base64"' in text
    assert "candidate manifest exceeds the 1 MiB validation limit" in text
    assert '"protected-base/docs/action-contract-manifest.json"' in text
    assert "python3 scripts/validate_action_contract_manifest.py" in text


def test_promotion_guard_never_executes_candidate_code() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    run_block = text.split("run: |", maxsplit=1)[1]
    assert "candidate/scripts/" not in run_block
    assert "cd candidate" not in run_block
    assert "python3 candidate/" not in run_block
    assert "actions/checkout@" not in text.split(
        "- name: Set up Python", maxsplit=1
    )[1]
