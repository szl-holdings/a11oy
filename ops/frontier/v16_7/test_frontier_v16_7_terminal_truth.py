"""Frontier v16.7 source-truth regressions.

These tests are intentionally source-level: they ensure a cold server-render and a
failed browser fetch never advertise an in-progress state forever, and that the
FastAPI route modules obey the repository's annotation rule.
"""
from pathlib import Path
import importlib.util
import json
import re

HERE = Path(__file__).resolve()
ROOT = next(parent for parent in HERE.parents if (parent / "AGENTS.md").is_file())
REPAIR_SCRIPT = ROOT / "ops" / "frontier" / "v16_7" / "apply_current_main_repairs.py"
SPEC = importlib.util.spec_from_file_location("frontier_v16_7_repairs", REPAIR_SCRIPT)
assert SPEC and SPEC.loader
REPAIRS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPAIRS)


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_series_a_server_render_is_terminal_before_javascript() -> None:
    page = text("routers/series_a_web/index.html")
    for forbidden in (
        ">CHECKING<",
        ">CONNECTING<",
        ">Not observed yet<",
    ):
        assert forbidden not in page
    assert "UNKNOWN · no observation yet" in page
    assert "UNKNOWN · no governed events observed" in page
    assert "UNKNOWN · no signed receipts observed" in page


def test_series_a_fetch_failure_terminalizes_every_card_and_receipts() -> None:
    script = text("routers/series_a_web/app.js")
    assert '["estate", "repos", "prs", "spaces", "models", "datasets", "trust", "signer"]' in script
    assert "receipts endpoint did not produce a current observation" in script
    assert "currentEvidence = null" in script
    assert "invalidateAuthorization()" in script
    assert "setEventTerminal(\"CONNECTED · waiting for governed events\")" in script
    assert "setEventTerminal(\"UNAVAILABLE · event stream disconnected\")" in script
    assert 'dataset.placeholder === "true"' in script
    assert 'textContent === "CONNECTING"' not in script
    assert "RECONNECTING" not in script


def test_route_modules_do_not_postpone_annotations() -> None:
    for relative in (
        "routers/frontier_reads.py",
        "routers/series_a_control_plane.py",
    ):
        assert "from __future__ import annotations" not in text(relative)


def test_readme_does_not_unconditionally_claim_live_signing() -> None:
    readme = text("README.md")
    assert not re.search(
        r"(?m)^Signed receipts on every governed action\s*\|\s*LIVE\s*$",
        readme,
    )
    assert "CONFIGURATION-BOUND" in readme
    assert "otherwise explicitly UNSIGNED" in readme


def test_repair_oracle_matches_the_actual_markdown_status_row() -> None:
    source = "| Signed receipts on every governed action | **LIVE** |\n"
    changes: list[str] = []
    repaired = REPAIRS.repair_readme(source, changes)
    assert changes == ["README receipt claim is configuration-bound"]
    assert "**CONFIGURATION-BOUND**" in repaired
    assert "**LIVE**" not in repaired
    assert REPAIRS.repair_readme(repaired, []) == repaired


def test_repair_oracle_rejects_mixed_old_and_repaired_rows() -> None:
    repaired = REPAIRS.repair_readme(
        "| Signed receipts on every governed action | **LIVE** |\n",
        [],
    )
    mixed = "| Signed receipts on every governed action | **LIVE** |\n" + repaired
    try:
        REPAIRS.repair_readme(mixed, [])
    except REPAIRS.RepairError:
        pass
    else:
        raise AssertionError("mixed unconditional and repaired receipt rows must fail closed")


def test_repair_oracle_rejects_mixed_old_and_reformatted_repaired_rows() -> None:
    old = "| Signed receipts on every governed action | **LIVE** |\n"
    variant = (
        "  |  Signed receipts on every governed action  |  CONFIGURATION-BOUND  ·  SIGNED  only  "
        "when  the  persistent  production  key  is  present;  otherwise  explicitly  UNSIGNED  |\n"
    )
    try:
        REPAIRS.repair_readme(old + variant, [])
    except REPAIRS.RepairError:
        pass
    else:
        raise AssertionError("mixed unconditional and reformatted repaired receipt rows must fail closed")


def test_qualification_requires_ruleset_bound_workflow_identity() -> None:
    guide = text("ops/frontier/v16_7/README.md")
    assert "ruleset-bound identity" in guide
    assert "mutable status-context" in guide
    assert "status context or this workflow" not in guide
    contract = json.loads(text("ops/frontier/v16_7/SOLO_EXECUTION_CONTRACT.json"))
    promotion = contract["promotion"]
    assert promotion["required_workflow_path"] == ".github/workflows/frontier-solo-qualification.yml"
    assert "required_check" not in promotion


def test_global_console_server_render_is_terminal_before_javascript() -> None:
    page = text("pages/console.html")
    assert ">initializing&hellip;</div>" not in page
    assert '<span id="runtime-status-text">CHECKING</span>' not in page
    assert '<div class="view-sub">loading…</div>' not in page
    assert "live meter reconnecting&hellip;" not in page
    assert "UNKNOWN · awaiting first measured observation" in page
    assert '<span id="runtime-status-text">UNKNOWN</span>' in page
    assert "UNKNOWN · no measured console view has rendered" in page
    assert "STATUS UNAVAILABLE · shell ready" in page


def test_root_console_server_render_is_terminal_before_javascript() -> None:
    page = text("console/index.html")
    assert '<div class="view-sub">loading…</div>' not in page
    assert "UNKNOWN · no measured root view has rendered" in page
