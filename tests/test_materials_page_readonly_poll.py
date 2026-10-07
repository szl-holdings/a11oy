#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The materials page summary poll must be read-only (MAT-F07 UI half).

web/materials.html re-runs loadCards() every 12 s per open tab. Doctrine v11:
receipt-on-write, never on read — a poll must not POST /certify, which mints a
Khipu receipt per tick. The liveness probe is GET /certify/presets (emits nothing);
the user-initiated Certify button keeps its POST. Static parse only: no server,
no browser, no network.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "web" / "materials.html"

MUTATING_METHOD = re.compile(r"""method\s*:\s*["'](POST|PUT|PATCH|DELETE)["']""", re.IGNORECASE)


def _html() -> str:
    return PAGE.read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    m = re.search(r"async function %s\(\)\{(.*?)\n\}\n" % re.escape(name), _html(), re.S)
    assert m, f"{name}() not found in web/materials.html"
    return m.group(1)


def test_summary_poll_makes_no_mutating_request():
    body = _function_body("loadCards")
    hit = MUTATING_METHOD.search(body)
    assert hit is None, f"loadCards() issues a mutating request: {hit.group(0)}"
    assert 'MAT + "/certify",' not in body, "loadCards() still targets POST /certify"


def test_summary_poll_probes_the_readonly_presets_route():
    body = _function_body("loadCards")
    assert 'fetchJSON(MAT + "/certify/presets")' in body
    assert 'setProbe("cCertify", cert.status)' in body


def test_summary_poll_is_still_scheduled_every_12_seconds():
    html = _html()
    assert "setInterval(loadCards, 12000)" in html
    assert "/certify has no GET-info route" not in html, "stale comment: the GET route exists"


def test_explicit_certify_action_still_posts():
    body = _function_body("runCertify")
    assert re.search(r'fetchJSON\(MAT \+ "/certify",\s*\{method:"POST"', body)
    html = _html()
    assert 'getElementById("runCert").addEventListener("click",runCertify)' in html
