# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""The restraint page must show the operator refusal and must not POST on load."""

from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "web" / "restraint.html"


def test_restraint_page_does_not_evaluate_on_load_and_surfaces_401():
    text = PAGE.read_text(encoding="utf-8")
    assert "credential_configured" in text
    assert "BLOCKED" in text
    assert "does not collect or send the operator secret" in text
    assert "endpoint unavailable (is the Space running?)" not in text
    # The ladder POST is bound to the Run button. Loading the page must not call it.
    assert "\nrun();\n" not in text
    assert "$('#run').onclick=run;" in text
