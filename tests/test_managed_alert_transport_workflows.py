from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
SECRET_LINE = "SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}"
PRELUDE = "source scripts/managed_alert_env.sh &&"
EXPECTED = {
    "a11oy-api-health.yml",
    "alert-channel-watch.yml",
    "alert-relay-worker.yml",
    "dsse-receipts.yml",
    "gguf-weight-guard.yml",
    "hf-corpus-card-honesty.yml",
    "hf-corpus-freshness.yml",
    "hf-corpus-reverify.yml",
    "hf-drift-check.yml",
    "kev-feed-guard.yml",
    "llama-wheel-guard.yml",
    "phantom-required-check-guard.yml",
    "rekor-recheck.yml",
    "release-receipt-summary-guard.yml",
    "release-receipt-verify.yml",
    "scap-scan.yml",
    "sovereign-node-drop.yml",
}


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _step_bounds(lines: list[str], index: int) -> tuple[int, int]:
    secret_indent = _indent(lines[index])
    start = None
    for position in range(index, -1, -1):
        stripped = lines[position].lstrip()
        if stripped.startswith("- ") and _indent(lines[position]) < secret_indent:
            start = position
            break
    assert start is not None
    step_indent = _indent(lines[start])
    end = len(lines)
    for position in range(start + 1, len(lines)):
        if not lines[position].strip():
            continue
        current_indent = _indent(lines[position])
        if current_indent < step_indent or (
            current_indent == step_indent and lines[position].lstrip().startswith("- ")
        ):
            end = position
            break
    return start, end


def test_every_managed_secret_consumer_uses_the_normalizer_in_its_own_step() -> None:
    actual = set()
    for path in sorted(WORKFLOW_DIR.glob("*.yml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        secret_indexes = [
            index for index, line in enumerate(lines) if SECRET_LINE in line
        ]
        if not secret_indexes:
            continue
        actual.add(path.name)
        for index in secret_indexes:
            start, end = _step_bounds(lines, index)
            block = "\n".join(lines[start:end])
            assert PRELUDE in block, f"{path}: unmanaged alert secret consumer"
            before = "\n".join(lines[:start])
            # Either the same job already checked out the repository or the
            # repair inserted a dedicated immutable checkout before this step.
            assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in before
    assert actual == EXPECTED


WRANGLER_ACTION = "cloudflare/wrangler-action@9acf94ace14e7dc412b076f2c5c20b8ce93c79cd # v3.15.0"


def _relay_workflow() -> str:
    return (WORKFLOW_DIR / "alert-relay-worker.yml").read_text(encoding="utf-8")


def _relay_deploy_job() -> str:
    return _relay_workflow().split("\n  deploy:\n", 1)[1]


def test_relay_workflow_deploys_and_requires_a_real_post_deploy_canary() -> None:
    value = _relay_workflow()
    assert WRANGLER_ACTION in value
    assert "npm ci --ignore-scripts" in value
    assert "npx --yes" not in value
    assert "CLOUDFLARE_API_TOKEN" in value
    assert "ntfy.a11oy.net" in value
    assert "alert_channel_canary.py" in value
    assert "--send" in value
    # The canary's own exit status fails the job; nothing masks it.
    assert "continue-on-error" not in value
    assert "set +e" not in value
    assert "exit 0" not in value


@pytest.mark.parametrize("worker", ("alert-relay-worker", "email-sender-worker"))
def test_worker_actions_use_the_verified_lockfile_version(worker: str) -> None:
    value = (WORKFLOW_DIR / f"{worker}.yml").read_text(encoding="utf-8")
    lines = value.split("\n  deploy:\n", 1)[1].splitlines()
    install_index = next(
        index for index, line in enumerate(lines) if line.strip() == "id: wrangler"
    )
    start, install_end = _step_bounds(lines, install_index)
    install = "\n".join(lines[start:install_end])
    assert f"working-directory: ops/{worker}" in install
    order = [
        "npm ci --ignore-scripts --no-audit --no-fund",
        "locked_version=",
        "require('./package-lock.json').packages['node_modules/wrangler'].version",
        "require('./node_modules/wrangler/package.json').version",
        '= "$locked_version"',
        "printf 'version=%s\\n' \"$locked_version\" >> \"$GITHUB_OUTPUT\"",
    ]
    positions = [install.index(marker) for marker in order]
    assert positions == sorted(positions)

    # A separate action pin would replace the npm-ci installation on mismatch.
    version_inputs = [
        (index, line.strip())
        for index, line in enumerate(lines)
        if line.lstrip().startswith("wranglerVersion:")
    ]
    assert len(version_inputs) == 1
    action_index, version_input = version_inputs[0]
    assert version_input == "wranglerVersion: ${{ steps.wrangler.outputs.version }}"
    action_start, action_end = _step_bounds(lines, action_index)
    assert install_end <= action_start
    assert WRANGLER_ACTION in "\n".join(lines[action_start:action_end])


def test_relay_deploy_binds_the_exact_sha_and_reads_it_back_before_the_canary() -> None:
    value = _relay_workflow()
    deploy = _relay_deploy_job()
    assert value.startswith("name: Alert relay worker\n")
    assert "\npermissions:\n  contents: read\n" in value
    assert "if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'" in deploy
    assert "    needs: test\n" in deploy
    assert "    environment: production\n" in deploy
    assert "cancel-in-progress: false" in deploy
    assert "ref: ${{ github.sha }}" in deploy
    assert 'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"' in deploy
    assert "apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}" in deploy
    assert "accountId: ${{ steps.cloudflare-account.outputs.account_id }}" in deploy
    assert "SOURCE_REVISION: ${{ github.sha }}" in deploy
    assert "vars: |\n            SOURCE_REVISION\n" in deploy
    assert "id: cloudflare-account" in deploy
    assert "https://api.cloudflare.com/client/v4/accounts" in deploy
    assert "exactly one account" in deploy
    assert "re.fullmatch(r\"[0-9a-fA-F]{32}\", account_id)" in deploy
    assert 'echo "::add-mask::$account_id"' in deploy
    assert "printf 'account_id=%s\\n' \"$account_id\" >> \"$GITHUB_OUTPUT\"" in deploy
    assert "CLOUDFLARE_ACCOUNT_ID must be exactly 32 hexadecimal characters." in deploy
    assert "Cloudflare account discovery request failed." in deploy
    # Account binding is explicit now; nothing reads zones (no Zone:Read scope).
    assert "resolve_cloudflare_relay_account" not in value
    assert "/zones" not in value
    order = [
        "Resolve Cloudflare deployment account",
        WRANGLER_ACTION,
        "python scripts/verify_worker_revision.py",
        "--url https://ntfy.a11oy.net/.well-known/szl-worker-revision",
        '--expect-revision "${GITHUB_SHA}"',
        "python scripts/alert_channel_canary.py",
        "Upload secret-free delivery evidence",
    ]
    positions = [deploy.index(marker) for marker in order]
    assert positions == sorted(positions)


def test_relay_readback_and_bundle_changes_trigger_the_workflow() -> None:
    value = _relay_workflow()
    pull_request = value.split("  pull_request:\n", 1)[1].split("  push:\n", 1)[0]
    push = value.split("  push:\n", 1)[1].split("  workflow_dispatch:\n", 1)[0]
    for trigger in (pull_request, push):
        assert "'scripts/verify_worker_revision.py'" in trigger
        assert "'tests/test_verify_worker_revision.py'" in trigger
        assert "'ops/alert-relay-worker/**'" in trigger
    test_job = value.split("\n  test:\n", 1)[1].split("\n  deploy:\n", 1)[0]
    assert "tests/test_verify_worker_revision.py" in test_job
    assert "npm run build" in test_job
