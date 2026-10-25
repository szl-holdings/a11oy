# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Landing identity and evidence contracts.

The historical filename stays stable for callers. The retired WebGL assertions
already failed on accepted main; the current hero is native illustrative vector
art with an opaque text surface. Browser reflow checks cover the opened archive,
computed contrast, text enlargement, keyboard controls and unavailable providers.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "a11oy_landing.html"


@pytest.fixture(scope="module")
def html() -> str:
    return LANDING.read_text(encoding="utf-8")


def stylesheet() -> str:
    return (ROOT / "console/assets/a11oy-homepage.css").read_text(encoding="utf-8")


def test_hero_is_an_explicitly_illustrative_native_field(html: str) -> None:
    assert html.count('class="holo-aperture"') == 1
    assert '<div class="holo-field" aria-hidden="true">' in html
    assert 'class="specimen-wrap" data-surface="dark"' in html
    assert "MODELED SPECIMEN / illustrative" in html
    assert 'class="specimen-status">not live</span>' in html
    assert 'id="hero-canvas"' not in html
    assert "gl.POINTS" not in html


def test_hero_uses_local_canonical_assets_without_font_downloads(html: str) -> None:
    for host in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com", "threejs.org/build"):
        assert host not in html
    assert html.count('src="/assets/szl/orbit-v2/szl-icon-32.svg"') == 2
    assert '@font-face' not in html + stylesheet()
    assert 'href="/assets/szl/szl-design-system.css"' in html


def test_decoration_is_bounded_and_does_not_animate_under_reduced_motion() -> None:
    css = stylesheet()
    assert "prefers-reduced-motion:reduce" in css
    assert "animation:none !important; transition:none !important" in css
    assert ".holo-field" in css and "pointer-events:none" in css
    assert "#szl-holo-ambient" in css and ".szl-spectral-field" in css
    assert "will-change:auto" in css


# --------------------------------------------------- 2. honest default values

NV_ROWS = (
    "nv-service", "nv-doctrine", "nv-kernel", "nv-surfaces",
    "nv-policy", "nv-signer", "nv-digest", "nv-verdict",
)


@pytest.mark.parametrize("row_id", NV_ROWS)
def test_every_instrument_row_ships_unavailable(html: str, row_id: str) -> None:
    m = re.search(r'id="%s"[^>]*>([^<]*)<' % re.escape(row_id), html)
    assert m, f"instrument row {row_id} not found in the static bytes"
    assert m.group(1).strip() == "UNAVAILABLE", (
        f"{row_id} ships a pre-baked value {m.group(1)!r}; it must ship UNAVAILABLE "
        "so a JS-off / API-down reader is never shown an invented number"
    )


# ---------------------------------------------------------- 3. real endpoints

def test_panel_reads_only_the_three_real_endpoints(html: str) -> None:
    for ep in ("/api/a11oy/healthz", "/v1/frontier/surfaces", "/v1/attest/manifest"):
        assert ep in html, f"instrument panel is not wired to {ep}"


def test_panel_cites_its_endpoints_in_visible_copy(html: str) -> None:
    src = html[html.index('class="nv-src"'):]
    src = src[:src.index("</div>") + 6]
    assert "/api/a11oy/healthz" in src
    assert "attest/manifest" in src


# --------------------------------------------------------- 4. SIGNED is earned

def test_signed_requires_signature_present_and_verified(html: str) -> None:
    # the only place the literal SIGNED verdict is produced must be gated on both flags
    assert "sig.signed === true" in html
    assert "sig.verified === true" in html
    gate = html[html.index("sig.signed === true"):]
    gate = gate[:400]
    assert "SIGNED" in gate, "SIGNED verdict is not adjacent to its verification gate"
    assert "HASH-LINKED" in html, "missing the honest weaker-than-SIGNED verdict"


def test_signer_state_is_disclosed_separately(html: str) -> None:
    assert "Receipt records \u00b7 signer state separate" in html
    assert ("Signer state is disclosed separately only where an actual signer-status "
            "read is present.") in html


# ------------------------------------------------------------- 5. lambda row

def test_lambda_row_is_labelled_conjecture(html: str) -> None:
    assert 'class="nv-chip">Conjecture 1 \u00b7 not a theorem</span>' in html, (
        "the hero instrument panel must label \u039b as Conjecture 1, not a theorem"
    )
    assert "\u039b = Conjecture 1" in html


# ------------------------------------------------------- 6. fluid type, mono

def test_fluid_type_and_canonical_font_roles_are_present(html: str) -> None:
    css = stylesheet()
    for token in ("clamp(2.7rem,5.15vw,4.75rem)", "var(--font-display)", "var(--font-mono)", "var(--text-base)"):
        assert token in css
    canonical = (ROOT / "console/assets/szl/szl-design-system.css").read_text(encoding="utf-8")
    assert "--measure:68ch" in canonical
    assert 'href="/assets/a11oy-homepage.css?v=61c132098e06" id="szl-homepage-shell"' in html


def test_text_wrap_and_tabular_numbers() -> None:
    css = stylesheet()
    for token in ("text-wrap:balance", "text-wrap:pretty", "overflow-wrap:anywhere", "tabular-nums"):
        assert token in css


def test_owned_sheet_does_not_fork_the_canonical_palette() -> None:
    css = stylesheet()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert not re.search(r"(?:rgb|rgba|hsl|hsla|hwb|oklch)\(", css)
    for role in ("--action-bg", "--action-hover-bg", "--action-press-bg", "--holo-edge", "--text-sub", "--focus"):
        assert "var(" + role + ")" in css


def test_specimen_text_has_an_opaque_ground_separate_from_art() -> None:
    css = stylesheet()
    assert "background-color:var(--surface)" in css
    assert "linear-gradient(var(--surface),var(--surface)) padding-box" in css
    assert "position:absolute; inset:-14% -13% 0; pointer-events:none; z-index:-1" in css


def test_mobile_reflows_every_archive_grid_without_body_clipping() -> None:
    css = stylesheet()
    assert "@media(max-width:760px)" in css
    assert "repeat(auto-fit,minmax(min(100%,16rem),1fr))" in css
    assert "overflow:visible !important" in css
    assert 'class="archive-disclosure" id="full-record"' in LANDING.read_text(encoding="utf-8")
