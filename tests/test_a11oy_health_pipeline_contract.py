from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ".github/workflows/a11oy-api-health.yml",
    ".github/workflows/brain-honesty-check.yml",
    ".github/workflows/sovereign-node-drop.yml",
    ".github/workflows/phantom-required-check-guard.yml",
)


def _run_capture(tmp_path: Path, capture: str) -> subprocess.CompletedProcess[str]:
    script = f"""set +e
python3 -c 'raise SystemExit(7)' | tee \"$1\"
code={capture}
exit \"$code\"
"""
    return subprocess.run(
        ["bash", "-c", script, "pipeline-contract", str(tmp_path / "probe.log")],
        check=False,
        capture_output=True,
        text=True,
    )


def test_plain_dollar_question_masks_the_checker_failure(tmp_path: Path) -> None:
    result = _run_capture(tmp_path, "$?")
    assert result.returncode == 0


def test_pipestatus_preserves_the_checker_failure_through_tee(tmp_path: Path) -> None:
    result = _run_capture(tmp_path, "${PIPESTATUS[0]}")
    assert result.returncode == 7


def test_all_piped_health_guards_capture_the_producer_status() -> None:
    for relative in WORKFLOWS:
        value = (ROOT / relative).read_text(encoding="utf-8")
        assert "| tee " in value, relative
        assert "code=${PIPESTATUS[0]}" in value, relative
        assert "\n          code=$?\n" not in value, relative
