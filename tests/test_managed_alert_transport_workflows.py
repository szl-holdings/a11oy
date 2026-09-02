from __future__ import annotations

from pathlib import Path

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
            job_prefix = before.rsplit("\n  ", 1)[-1]
            # Either the same job already checked out the repository or the
            # repair inserted a dedicated immutable checkout before this step.
            assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in before
    assert actual == EXPECTED


def test_relay_workflow_deploys_and_requires_a_real_post_deploy_canary() -> None:
    value = (WORKFLOW_DIR / "alert-relay-worker.yml").read_text(encoding="utf-8")
    assert "wrangler@4.128.0" in value
    assert "CLOUDFLARE_API_TOKEN" in value
    assert "ntfy.a11oy.net" in value
    assert "alert_channel_canary.py" in value
    assert "--send" in value
    assert "Enforce real delivery health" in value
