# SPDX-License-Identifier: Apache-2.0
"""Regression contract for Putnam branch labels and immutable source refs."""

from __future__ import annotations

from pathlib import Path

import szl_putnam


ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "pages" / "console.html"
EXPECTED_BRANCH = "putnam-2025-canonical-set"
EXPECTED_REF = "baf483be3c832b64da47161b558e283d68da6650"


def test_payload_keeps_branch_and_immutable_ref_distinct() -> None:
    payload = szl_putnam._payload("a11oy")

    assert payload["branch"] == EXPECTED_BRANCH
    assert payload["canonical_ref"] == EXPECTED_REF
    assert payload["sha"] == EXPECTED_REF
    assert payload["branch"] != payload["canonical_ref"]
    assert len(str(payload["sha"])) == 40
    assert "/tree/" + EXPECTED_REF + "/" in str(payload["tree"])
    assert "/blob/" + EXPECTED_REF + "/" in str(payload["base"])


def test_console_labels_branch_and_pinned_ref_separately() -> None:
    html = CONSOLE.read_text(encoding="utf-8")

    assert "var BRANCH='putnam-2025-canonical-set';" in html
    assert "var REF=SHA;" in html
    assert "var BRANCH=SHA;" not in html
    assert "ref:j.canonical_ref||j.sha||REF" in html
    assert "branch:BRANCH, ref:REF" in html
    assert "lutar-lean/tree/'+REF+'/Lutar/Putnam" in html
    assert "lutar-lean/blob/'+REF+'/Lutar/Putnam/" in html
    assert "lutar-lean branch '+esc(m.branch)" in html
    assert "\\u00b7 pinned @'+esc(m.short)" in html
