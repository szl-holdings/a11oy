import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (
    ROOT / ".github" / "workflows" / "nemo-v3-isolated-owner-dispatch.yml"
).read_text(encoding="utf-8")
VALIDATOR = (
    ROOT / "scripts" / "validate_nemo_v3_owner_dispatch.py"
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


def test_every_generated_powershell_script_uses_explicit_process_bypass() -> None:
    shell = (
        "shell: powershell -NoLogo -NoProfile -NonInteractive "
        "-ExecutionPolicy Bypass -File {0}"
    )
    assert WORKFLOW.count(shell) == 8
    assert "\n        shell: powershell\n" not in WORKFLOW


def test_dispatch_selection_is_explicit_and_validated_before_bridge_use() -> None:
    checkout = WORKFLOW.index(
        "- name: Check out the exact dispatched default-branch revision"
    )
    selection = WORKFLOW.index(
        "- name: Validate explicit owner dispatch selection"
    )
    bridge = WORKFLOW.index(
        "- name: Verify exact signed envelope as data"
    )
    assert checkout < selection < bridge
    selection_step = WORKFLOW[selection:bridge]
    assert "OWNER_DISPATCH_V3_JSON" in WORKFLOW
    assert "toJson(github.event.client_payload)" in WORKFLOW
    assert "client_payload.selection" in WORKFLOW
    assert "validate_nemo_v3_owner_dispatch.py" in selection_step
    assert "select `" in selection_step
    assert '--github-sha "${{ github.sha }}"' in selection_step
    assert "rev-parse (" in selection_step
    assert "--workflow-blob $workflowBlob" in selection_step
    assert "--github-env $env:GITHUB_ENV" in selection_step
    assert "job-2026-nemo-v3-governed-attempt-1" not in WORKFLOW
    assert "38ba3100b2e20075b6ac0c3e62745c0f811de370" not in WORKFLOW
    assert 'DISPATCH_CONTRACT_VERSION = "szl-nemo-owner-dispatch.v3"' in VALIDATOR
    assert 'WORKFLOW_VERSION = "nemo-v3-owner-dispatch.v4"' in VALIDATOR
    assert '_CLIENT_PAYLOAD_FIELDS = {"selection"}' in VALIDATOR


def test_envelope_data_and_signed_execution_source_are_separate() -> None:
    envelope = _step(
        "Verify exact signed envelope as data",
        "Prepare signed execution source and GPU image",
    )
    runtime = _step(
        "Prepare signed execution source and GPU image",
        "Prefetch exact authenticated inputs without executing model code",
    )
    assert "ls-remote `" in envelope
    assert "$remoteMain -cne $env:ENVELOPE_REVISION" in envelope
    assert "--envelope-source $envelopeSource" in envelope
    assert "--github-env $env:GITHUB_ENV" in envelope
    assert "EXECUTION_BRIDGE_REVISION" not in envelope.split(
        "verify-envelope `", 1
    )[0]
    assert "szl-gpu-bridge-envelope-" in envelope
    assert "szl-gpu-bridge-runtime-" in runtime
    assert "verify-history `" in runtime
    assert "--remote-main $confirmedMain" in runtime
    assert "--execution-source $source" in runtime
    assert "--envelope-source $env:ENVELOPE_SOURCE" in runtime
    assert "--untracked-files=all" in WORKFLOW
    assert "merge-base" in VALIDATOR
    assert "--is-ancestor" in VALIDATOR
    assert "refs/remotes/origin/main" in VALIDATOR
    assert "BRIDGE_REPOSITORY_URL" in VALIDATOR
    assert runtime.index("verify-history `") < runtime.index(
        "& $docker pull $env:TRAINING_IMAGE"
    )


def test_successor_lineage_is_bound_to_immutable_predecessor_evidence() -> None:
    assert "QUARANTINED_JOB_ID =" not in VALIDATOR
    assert "_verify_predecessor_lineage(" in VALIDATOR
    assert "predecessor quarantine record" in VALIDATOR
    assert "predecessor_generation + 1 != current_generation" in VALIDATOR
    assert '"NEVER_DISPATCH" not in statuses' in VALIDATOR
    assert "protected predecessor envelope history" in VALIDATOR


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
    assert "create-claim `" in claim_step
    assert "--envelope-source $env:ENVELOPE_SOURCE" in claim_step
    assert "--execution-source $env:BRIDGE_SOURCE" in claim_step
    assert "$claimMain -cne $env:PROTECTED_BRIDGE_MAIN" in claim_step
    assert "--remote-main $claimMain" in claim_step
    assert "--git-executable $env:GIT_EXECUTABLE" in claim_step
    assert "--bridge-root $env:BRIDGE_ROOT" in claim_step
    assert '--run-id "${{ github.run_id }}"' in claim_step
    assert '--run-attempt "${{ github.run_attempt }}"' in claim_step
    assert "os.O_EXCL" in VALIDATOR
    assert "os.O_CREAT" in VALIDATOR
    assert "os.fsync(descriptor)" in VALIDATOR


def test_trusted_prefetch_cannot_dirty_execution_source_with_bytecode(
    tmp_path: Path,
) -> None:
    prefetch = _step(
        "Prefetch exact authenticated inputs without executing model code",
        "Atomically claim the single governed attempt",
    )
    invocation = (
        "& $env:CONTROL_PYTHON `\n"
        "            -B `\n"
        "            (Join-Path $env:BRIDGE_SOURCE "
        '"laptop\\prefetch_nemo_v3.py") `'
    )
    assert invocation in prefetch
    assert "--job-id $env:JOB_ID" in prefetch
    assert '--source-revision "${{ github.sha }}"' in prefetch
    assert "--workflow-blob $env:EXPECTED_WORKFLOW_BLOB" in prefetch
    assert "--execution-bridge-revision $env:EXECUTION_BRIDGE_REVISION" in prefetch

    source = tmp_path / "execution-source"
    package = source / "laptop"
    package.mkdir(parents=True)
    (package / "contract.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "prefetch.py").write_text(
        "from contract import VALUE\nraise SystemExit(0 if VALUE == 1 else 1)\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-B", str(package / "prefetch.py")],
        cwd=source,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not list(source.rglob("__pycache__"))
    assert not list(source.rglob("*.pyc"))


def test_remote_code_step_has_no_token_or_signing_input() -> None:
    execute = _step(
        "Execute remote model code without network, credentials, or signing key",
        "Sign, upload, and immutably read back the fresh receipt",
    )
    assert "HF_TOKEN" not in execute
    assert "laptop_key.pem" not in execute
    assert "-BridgeRevision $env:EXECUTION_BRIDGE_REVISION" in execute
    assert "-EnvelopePath $env:VERIFIED_ENVELOPE_PATH" in execute
    assert "-Image $env:TRAINING_IMAGE" in execute


def test_helpers_consume_verified_envelope_and_signed_engine_key() -> None:
    prefetch = _step(
        "Prefetch exact authenticated inputs without executing model code",
        "Atomically claim the single governed attempt",
    )
    finalizer = _step(
        "Sign, upload, and immutably read back the fresh receipt",
        "Remove per-run trusted source and control runtime",
    )
    for step in (prefetch, finalizer):
        assert "$env:VERIFIED_ENVELOPE_PATH" in step
        assert '"keys\\engine_pubkey_" + $env:ENGINE_KEY_ID + ".json"' in step
        assert "--execution-bridge-revision $env:EXECUTION_BRIDGE_REVISION" in step
    assert '"queue\\pending\\" + $env:JOB_ID' not in prefetch
    assert '"queue\\pending\\" + $env:JOB_ID' not in finalizer


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


def test_workflow_pins_image_and_never_dispatches_or_publishes_candidates() -> None:
    assert (
        "unsloth/unsloth@sha256:"
        "9cc97606fc386b4b13455285eb7bd2668f51530988a9c2578707fe6cdfc46123"
        in WORKFLOW
    )
    assert "workflow_dispatch:" not in WORKFLOW
    assert "repository_dispatch:" in WORKFLOW
    assert "candidateUpload" not in WORKFLOW
    assert "modelCardUpload" not in WORKFLOW
    assert "datasetUpload" not in WORKFLOW
    assert "candidateUpload" in VALIDATOR
    assert "modelCardUpload" in VALIDATOR
    assert "datasetUpload" in VALIDATOR
    assert "SZLHOLDINGS/szl-training-receipts" in VALIDATOR


def test_cleanup_is_always_run_and_confined_to_runner_temp() -> None:
    cleanup = WORKFLOW.split(
        "- name: Remove per-run trusted source and control runtime", 1
    )[1]
    assert "if: ${{ always() }}" in cleanup
    assert "[IO.Path]::GetFullPath" in cleanup
    assert "[StringComparison]::OrdinalIgnoreCase" in cleanup
    assert (
        "^szl-(gpu-bridge-(envelope|runtime)|nemo-control)-[0-9]+$"
        in cleanup
    )
    assert "Remove-Item -LiteralPath $resolved -Recurse -Force" in cleanup
