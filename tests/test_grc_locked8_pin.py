#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""/grc must not bind the locked-8 to the corpus pin c7c0ba17. Network-free.

c7c0ba17 (lutar-lean, 2026-05-31) is the doctrine v11 corpus pin. It predates
every f1_..f22_ theorem for the eight formulas, which were added from 2026-06-01
(1fe5ab1) and 2026-06-04 (e6de491, #185), and the locked-8 set itself, which is
first declared (locked_count_eight) in lutar-lean 5cfaf9a (#219, 2026-06-10).
The GRC disclaimer is served as ``honest`` on /grc/matrix, /grc/mapping and the
/grc index, as the OSCAL metadata remarks, and in the /grc page disclaimer box,
so every one of those must carry the same wording as row A.6.6 and the footer.
"""
import json
import re
from pathlib import Path

import pytest

import a11oy_grc as G
import a11oy_grc_data as D

ROOT = Path(__file__).resolve().parents[1]
OSCAL_ARTIFACT = ROOT / "compliance" / "oscal" / "a11oy-component-definition.json"
PIN_BINDING = re.compile(r"(locked(-proven)?\s*=\s*)?8\s*@\s*c7c0ba17")


def _assert_unbound(text: str) -> None:
    assert not PIN_BINDING.search(text), PIN_BINDING.search(text).group(0)


def test_disclaimer_does_not_bind_locked8_to_corpus_pin():
    _assert_unbound(D.HONEST_DISCLAIMER)
    assert "locked-proven = 8 per lutar-lean #219" in D.HONEST_DISCLAIMER
    assert "UNREVIEWED" in D.HONEST_DISCLAIMER
    # the kernel_commit field that ships beside it is named for what it is
    assert "c7c0ba17 is the doctrine v11 corpus pin" in D.HONEST_DISCLAIMER


@pytest.mark.parametrize("build", [D.build_matrix, D.build_mapping, D.build_oscal,
                                   G._merged_matrix, G._merged_oscal, G.info])
def test_grc_json_payloads_do_not_bind_locked8_to_corpus_pin(build):
    _assert_unbound(json.dumps(build(), ensure_ascii=False))


def test_matrix_honest_matches_row_a66_wording():
    mx = D.build_matrix()
    a66 = next(r for r in mx["matrix"] if r["control"] == "A.6.6")
    assert "per lutar-lean #219 (5cfaf9a" in a66["mechanism"]
    assert "per lutar-lean #219 (5cfaf9a" in mx["honest"]


def test_committed_oscal_artifact_carries_the_live_disclaimer():
    art = json.loads(OSCAL_ARTIFACT.read_text(encoding="utf-8"))
    remarks = art["component-definition"]["metadata"]["remarks"]
    assert remarks == D.HONEST_DISCLAIMER
    _assert_unbound(remarks)


def test_grc_page_does_not_bind_locked8_to_corpus_pin():
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    G.register(app, ns="a11oy")
    c = TestClient(app)
    for path in ("/grc", "/compliance"):
        r = c.get(path)
        assert r.status_code == 200, path
        _assert_unbound(r.text)
        assert "locked-proven = 8 per lutar-lean #219" in r.text
    for ep in ("/api/a11oy/v1/grc", "/api/a11oy/v1/grc/matrix",
               "/api/a11oy/v1/grc/mapping", "/api/a11oy/v1/grc/oscal"):
        r = c.get(ep)
        assert r.status_code == 200, ep
        _assert_unbound(r.text)
