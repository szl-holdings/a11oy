# SPDX-License-Identifier: Apache-2.0
"""Regression contract for Putnam branch labels and immutable source refs."""

from __future__ import annotations

from pathlib import Path

import szl_putnam


ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "pages" / "console.html"
EXPECTED_BRANCH = "putnam-2025-canonical-set"
EXPECTED_REF = "baf483be3c832b64da47161b558e283d68da6650"


def _assert_source_identity(payload: dict[str, object]) -> None:
    assert payload["branch"] == EXPECTED_BRANCH
    assert payload["ref"] == EXPECTED_REF
    assert payload["sha"] == EXPECTED_REF
    assert payload["branch"] != payload["ref"]
    assert len(str(payload["sha"])) == 40
    assert "/tree/" + EXPECTED_REF + "/" in str(payload["tree"])
    assert "/blob/" + EXPECTED_REF + "/" in str(payload["base"])


def test_source_identity_keeps_branch_and_immutable_ref_distinct() -> None:
    _assert_source_identity(szl_putnam._source_identity())


def test_index_and_problem_payloads_share_the_source_contract() -> None:
    index = szl_putnam._payload("a11oy")
    hit = szl_putnam._find("A1")
    assert hit is not None
    detail = szl_putnam._problem_payload("a11oy", hit)

    _assert_source_identity(index)
    _assert_source_identity(detail)


def test_console_labels_branch_and_pinned_ref_separately() -> None:
    html = CONSOLE.read_text(encoding="utf-8")

    assert "var BRANCH='putnam-2025-canonical-set';" in html
    assert "var REF=SHA;" in html
    assert "var BRANCH=SHA;" not in html
    assert "branch:j.branch||BRANCH, ref:j.ref||j.sha||REF" in html
    assert "branch:BRANCH, ref:REF" in html
    assert "'/tree/'+REF+'/Lutar/Putnam'" in html
    assert "'/blob/'+REF+'/Lutar/Putnam/'" in html
    assert "lutar-lean branch '+esc(m.branch)+' · pinned @'+esc(m.short)" in html
