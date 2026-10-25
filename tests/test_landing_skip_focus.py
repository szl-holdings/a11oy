# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Product skip link must move focus to #main, not only change the hash."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
HOMEPAGE_CSS_PATH = ROOT / "console/assets/a11oy-homepage.css"
HOMEPAGE_CSS = HOMEPAGE_CSS_PATH.read_text(encoding="utf-8")
HOMEPAGE_CSS_SHA256 = hashlib.sha256(HOMEPAGE_CSS_PATH.read_bytes()).hexdigest()


def test_main_is_a_programmatic_focus_target() -> None:
    assert '<a class="skip-link" href="#main">Skip to main content</a>' in LANDING
    assert '<main id="main" tabindex="-1">' in LANDING
    assert "<style" not in LANDING.lower()
    assert 'html[data-szl-shell-owner="homepage"] #main:focus{' in HOMEPAGE_CSS
    assert "outline:3px solid var(--focus);" in HOMEPAGE_CSS
    assert "var(--focus," not in HOMEPAGE_CSS
    assert "#0f726e" not in HOMEPAGE_CSS
    query = HOMEPAGE_CSS_SHA256[:12]
    assert f'href="/assets/a11oy-homepage.css?v={query}" id="szl-homepage-shell"' in LANDING
    assert "dab2353006c8" not in LANDING


def test_skip_activation_focuses_main_outside_the_archive_drawer() -> None:
    script = LANDING.split("<script>", 1)[1].split("</script>", 1)[0]
    assert "if(!drawer) return;" not in script
    assert 'document.querySelector(\'a.skip-link[href="#main"]\')' in script
    assert "requestAnimationFrame(focusMain)" in script
    assert 'target.id==="main"' in script
    assert "if(moveFocus) focusMain();" in script
    assert "drawer.contains(target)" in script
