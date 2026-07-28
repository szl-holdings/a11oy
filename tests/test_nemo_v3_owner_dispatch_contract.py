from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (
    ROOT / ".github" / "workflows" / "nemo-v3-isolated-owner-dispatch.yml"
).read_text(encoding="utf-8")


def _step(name: str, next_name: str) -> str:
    return WORKFLOW.split(f"- name: {name}", 1)[1].split(
        f"- name: {next_name}", 1
    )[0]


def test_dispatch_requires_protected_default_branch_and_same_owner_on_rerun() -> None:
    admission = WORKFLOW.split("runs-on:", 1)[0]
    assert "github.event.repository.default_branch" in admission
    assert "github.ref_protected" in admission
    assert "github.actor == 'stephenlutar2-hash'" in admission
    assert "github.triggering_actor == 'stephenlutar2-hash'" in admission


def test_single_attempt_is_atomically_claimed_after_verified_prefetch() -> None:
    prefetch = WORKFLOW.index(
        "- name: Prefetch exact authenticated inputs without executing model code"
    )
    claim = WORKFLOW.index("- name: Atomically claim the single governed attempt")
    execute = WORKFLOW.index(
        "- name: Execute remote model code without network, credentials, or signing key"
    )
    assert prefetch < claim < execute
    claim_step = WORKFLOW[claim:execute]
    assert "[IO.FileMode]::CreateNew" in claim_step
    assert "envelopeSha256 = $specDigest" in claim_step
    assert '"${{ github.sha }}"' in claim_step
    assert '"${{ github.run_attempt }}"' in claim_step


def test_remote_code_step_has_no_token_or_signing_input() -> None:
    execute = _step(
        "Execute remote model code without network, credentials, or signing key",
        "Sign, upload, and immutably read back the fresh receipt",
    )
    assert "HF_TOKEN" not in execute
    assert "laptop_key.pem" not in execute
    assert "-BridgeRevision $env:BRIDGE_REVISION" in execute
    assert "-Image $env:TRAINING_IMAGE" in execute


def test_finalizer_binds_allowed_receipt_name_to_exact_intent_name() -> None:
    finalizer = _step(
        "Sign, upload, and immutably read back the fresh receipt",
        "Remove per-run trusted source and control runtime",
    )
    for name in (
        "blocked_receipt.signed.json",
        "nemo-v3-qualified.signed.json",
        "nemo-v3-terminal.signed.json",
    ):
        assert name in finalizer
    assert "$intents[0].Name -cne $expectedIntentName" in finalizer
    assert "--not-before $notBefore.Trim()" in finalizer
    assert '"control\\attempt-claims\\" + $env:JOB_ID + ".json"' in finalizer
    assert '--ledger (Join-Path $env:BRIDGE_ROOT "jobs\\seen.txt")' in finalizer


def test_workflow_pins_the_merged_attempt_claim_bridge() -> None:
    assert (
        "BRIDGE_REVISION: 38ba3100b2e20075b6ac0c3e62745c0f811de370"
        in WORKFLOW
    )


def test_cleanup_is_always_run_and_confined_to_runner_temp() -> None:
    cleanup = WORKFLOW.split(
        "- name: Remove per-run trusted source and control runtime", 1
    )[1]
    assert "if: ${{ always() }}" in cleanup
    assert "[IO.Path]::GetFullPath" in cleanup
    assert "[StringComparison]::OrdinalIgnoreCase" in cleanup
    assert '^szl-(gpu-bridge|nemo-control)-[0-9]+$' in cleanup
    assert "Remove-Item -LiteralPath $resolved -Recurse -Force" in cleanup
