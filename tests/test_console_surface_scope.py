# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Dark panels inside the light console keep their own ink, and the gate label follows its read.

On 2026-10-06 the command view's dark hero rendered its heading at about 1.01:1 in the light
shell: the restrained layer re-points --szl-holo-ink at the page's --text on <html>, and the
holo heading rule outranks .hero-h1. KANCHAY 1.2.0 lets a panel declare its own surface; these
tests keep the console wired to it.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = (ROOT / "pages" / "console.html").read_text(encoding="utf-8")
FOCUS_CSS = (ROOT / "console" / "assets" / "szl-console-focus.css").read_text(encoding="utf-8")
KANCHAY_COPIES = (
    "console/assets/szl",
    "docs/site/docs/public/szl",
    "landing/szl",
    "organs/amaru/web/public/szl",
    "routers/command_centre_web/szl",
)


def _hero_markup() -> str:
    return CONSOLE.split("var HERO_HTML=", 1)[1].split("c.innerHTML=HERO_HTML", 1)[0]


def _investor_overlay() -> str:
    return CONSOLE.split('<div id="inv-overlay"', 1)[1].split("</section>", 1)[0]


def _rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{(?P<body>[^}]*)\}", css)
    assert match, selector
    return match.group("body")


def test_dark_panels_declare_their_own_surface_and_leave_the_page_one_h1():
    hero = _hero_markup()
    assert hero.startswith("'<section class=\"hero\" data-surface=\"dark\"")
    assert "<h1" not in hero
    assert '<h2 class="hero-h1">' in hero

    overlay = _investor_overlay()
    assert overlay.startswith(' data-surface="dark" role="dialog" aria-modal="true"')
    assert "<h1" not in overlay
    assert ".inv-hero h1" not in CONSOLE


def test_restrained_aliases_re_resolve_on_nested_surfaces():
    nested = (
        'html[data-console-style="restrained"],\n'
        'html[data-console-style="restrained"] :is([data-surface="dark"],[data-surface="light"])'
    )
    body = _rule(FOCUS_CSS, nested)
    for alias in ("--szl-holo-ink:var(--text)", "--teal:var(--link)", "--gold:var(--text)"):
        assert alias in body
    # The page background and --bg stay on <html>; a nested panel paints its own ground.
    assert "background" not in body
    assert "--bg:" not in body

    light = _rule(
        FOCUS_CSS,
        'html[data-console-style="restrained"][data-surface="light"],\n'
        'html[data-console-style="restrained"] [data-surface="light"]',
    )
    assert "--health-ok:var(--color-success-strong)" in light


def test_every_vendored_kanchay_copy_is_bundle_1_2_0():
    design = {
        (ROOT / copy / "szl-design-system.css").read_bytes() for copy in KANCHAY_COPIES
    }
    assert len(design) == 1
    css = design.pop().decode("utf-8")
    assert "KANCHAY Design System v1.2.0" in css
    assert ':root, [data-surface="dark"] {' in css

    for copy in KANCHAY_COPIES:
        source = json.loads((ROOT / copy / "SOURCE.json").read_text(encoding="utf-8"))
        assert source["version"] == "1.2.0", copy
        for name, digest in source["sha256"].items():
            path = ROOT / copy / name
            if path.exists():
                assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, (copy, name)


def test_gate_label_follows_its_read_and_never_mints_live():
    hero = _hero_markup()
    assert '<em class="mlabel" id="hero-gate-tag">PENDING</em>' in hero
    assert ">LIVE<" not in hero

    fill = CONSOLE.split("var _gateTag=document.getElementById('hero-gate-tag');", 1)[1]
    fill = fill.split("})();", 1)[0]
    answered, failed = fill.split("}catch(_e){", 1)
    # An HTTP answer is an observation; it is never promoted to LIVE.
    assert "_gateTag.textContent='OBSERVED'" in answered
    assert "'LIVE'" not in fill
    assert "_gateTag.textContent='UNAVAILABLE'" in failed
    # The attested-datum seal marks a returned verdict, never an unavailable read.
    assert "rmark" not in failed
