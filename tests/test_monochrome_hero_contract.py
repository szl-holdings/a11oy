# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Contract for the monochrome "genius" front-door hero.

The hero renders the SZL monochrome design system v1 and an honest live-read
card. These guards lock the two things that can rot:

  1. Design: the holographic proof-kernel canvas exists, is monochrome, and the
     hero carries no colour accent (no teal/blue/gold token inside the hero).
  2. Honesty: every hero live value defaults to UNAVAILABLE in static HTML, is
     read from a REAL a11oy endpoint, and SIGNED is only ever written when the
     attestation API reports a signature that exists AND verified this request.
     Lambda stays "Conjecture 1 - not a theorem".
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT_DOOR = ROOT / "a11oy_landing.html"


def _html() -> str:
    return FRONT_DOOR.read_text(encoding="utf-8")


def _hero_markup(html: str) -> str:
    start = html.index('<section class="hero">')
    end = html.index("</section>", start)
    return html[start:end]


def test_hero_mounts_the_monochrome_holographic_proof_kernel() -> None:
    html = _html()
    hero = _hero_markup(html)
    assert '<canvas id="holo"' in hero
    # The kernel is the fibonacci-sphere point cloud from the SZL design system.
    assert "monochrome holographic proof kernel" in html
    assert "prefers-reduced-motion: reduce" in html
    # Monochrome: the point cloud and its core glow are white / warm off-white only.
    assert "rgba(255,255,255," in html
    assert "rgba(240,238,230,0.06)" in html
    # The retired Three.js hero boot must not come back on the front door.
    assert "mountHero" not in html
    assert 'id="hero-canvas"' not in html


def test_hero_carries_no_colour_accent() -> None:
    html = _html()
    hero_css_start = html.index('SZL monochrome "genius" hero')
    hero_css = html[hero_css_start : html.index(
        "/* Mobile overrides intentionally follow all equal-specificity base rules. */",
        hero_css_start,
    )]
    for banned in ("var(--proof)", "var(--lattice)", "var(--gold)", "58,244,200", "91,141,238", "8a6bff"):
        assert banned not in hero_css, f"colour accent leaked into the monochrome hero: {banned}"
    # Warm off-white display type + the neutral ramp are present.
    assert "--mg-cream:#f0eee6" in hero_css
    assert "--mg-t2:#9a9a9e" in hero_css
    assert "clamp(34px,7vw,72px)" in hero_css


def test_hero_live_card_defaults_to_unavailable() -> None:
    hero = _hero_markup(_html())
    for element_id in (
        "mg-service",
        "mg-doctrine",
        "mg-kernel",
        "mg-surfaces",
        "mg-policy",
        "mg-signer",
        "mg-digest",
        "mg-verdict",
    ):
        assert f'id="{element_id}">UNAVAILABLE<' in hero, element_id


def test_hero_live_card_reads_real_a11oy_endpoints() -> None:
    html = _html()
    for endpoint in (
        "/api/a11oy/healthz",
        "/api/a11oy/v1/frontier/surfaces",
        "/api/a11oy/v1/attest/manifest",
    ):
        # cited in the card body AND actually fetched by the reader
        assert f'href="{endpoint}"' in html, endpoint
        assert f'getJSON("{endpoint}")' in html, endpoint
    # The values come from the payloads, never from a literal in the page.
    assert "statement_digest_sha256" in html
    assert "health.rollup.signer.status" in html
    assert "surf.count" in html
    assert "att.verdict" in html


def test_hero_says_signed_only_on_a_verified_signature() -> None:
    html = _html()
    assert 'sig.signed===true&&sig.verified===true' in html
    signed_index = html.index('verdict="SIGNED"')
    guard_index = html.index('sig.signed===true&&sig.verified===true')
    assert guard_index < signed_index
    # Honest fallbacks, never a fabricated verdict.
    assert 'verdict="HASH-LINKED"' in html
    assert 'verdict="UNAVAILABLE"' in html


def test_hero_lambda_is_conjecture_not_a_theorem() -> None:
    hero = _hero_markup(_html())
    assert "Conjecture 1 · not a theorem" in hero
    # The advisory bound is never upgraded and never rendered green.
    assert 'class="k gray" id="hs-lambda">Conjecture 1<' in hero
    assert "Λ trust gate · advisory bound" in hero
    assert "Λ = Theorem" not in hero
    assert "proven bound" not in hero


def test_hero_keeps_the_existing_honest_copy() -> None:
    hero = _hero_markup(_html())
    assert "Governed agent change management · verifiable by anyone, offline" in hero
    assert "policy-gated and signed into a receipt" in hero
    assert "offline, in your own browser" in hero
    assert "BLOCKED" in hero
    assert 'id="hs-proven">8</div>' in hero
    assert 'class="k gray" id="hs-overclaims">—<' in hero
    assert "Locked Lean-proven theorems" in hero
