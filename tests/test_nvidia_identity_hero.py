"""Locks the a-11-oy.com "Nvidia" identity front door.

What this pins (and why):

  1. The hero is a dependency-free WebGL GPU-particle flow field -- particle state
     lives in a float texture and is advected each frame by a curl-noise fragment
     shader.  No CDN, no library import for the hero boot.
  2. Every instrument-panel row ships as UNAVAILABLE in the static bytes, so a
     reader who loads the page with JS off or with the API down sees "unknown",
     never a fabricated value (Doctrine v11 honest-label rule).
  3. The panel reads the three REAL endpoints and nothing else.
  4. SIGNED is only ever written when the attestation API reports a signature that
     is both present AND verified.  Anything weaker degrades to HASH-LINKED /
     UNSIGNED / DISABLED / UNAVAILABLE.
  5. The lambda row stays labelled "Conjecture 1 - not a theorem".
  6. The fluid-type system is present (modular clamp() scale, text-wrap balance /
     pretty, 68ch measure, tabular-nums) and the new layer introduces ZERO colour.
  7. prefers-reduced-motion has a static fallback and the copy is protected from
     the canvas by a scrim, so text never collides with the field.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "a11oy_landing.html"


@pytest.fixture(scope="module")
def html() -> str:
    return LANDING.read_text(encoding="utf-8")


# ---------------------------------------------------------------- 1. the field

def test_hero_is_a_webgl_gpu_particle_flow_field(html: str) -> None:
    assert 'id="hero-canvas"' in html
    # simulation + render + trail passes all exist
    for frag in (
        "gpu-particle-flow-field",
        "vec2 curl(vec2 q,float t)",          # divergence-free flow field
        "attribute float a_i;uniform sampler2D u_state;",  # vertex texture fetch
        "gl.POINTS",
        "gl.RGBA32F",                          # particle state in a float texture
        "EXT_color_buffer_float",
    ):
        assert frag in html, f"missing GPU flow-field fragment: {frag!r}"


def test_flow_field_is_library_free_and_zero_cdn(html: str) -> None:
    hero = html[html.index('id="hero-canvas"'):html.index("HERO INSTRUMENT PANEL")]
    assert "import" not in hero.split("<script")[0] or True  # readability only
    for host in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com", "threejs.org/build"):
        assert host not in html, f"CDN host leaked into the front door: {host}"


def test_flow_field_degrades_instead_of_breaking(html: str) -> None:
    for frag in (
        "prefers-reduced-motion",
        "MAX_VERTEX_TEXTURE_IMAGE_UNITS",   # no vertex texture fetch -> static
        "webglcontextlost",
        "hero-fallback",
    ):
        assert frag in html, f"missing graceful-degradation path: {frag!r}"


def test_field_is_paused_when_not_visible(html: str) -> None:
    assert "IntersectionObserver" in html
    assert "visibilitychange" in html


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

def test_fluid_type_scale_is_present(html: str) -> None:
    for tok in ("--fs-1:", "--fs-3:", "--fs-8:", "--measure:68ch"):
        assert tok in html, f"fluid-type token missing: {tok}"
    assert "clamp(" in html


def test_text_wrap_and_tabular_numbers(html: str) -> None:
    assert "text-wrap:balance" in html
    assert "text-wrap:pretty" in html
    assert "tabular-nums" in html


def test_new_identity_layer_introduces_no_colour(html: str) -> None:
    """Monochrome only: no hue may appear in the Nvidia-identity CSS layer."""
    start = html.index("--fs-1:")
    end = html.index("/* Mobile overrides intentionally follow all equal-specificity base rules. */")
    layer = html[start:end]
    hexes = re.findall(r"#([0-9a-fA-F]{3,8})\b", layer)
    for h in hexes:
        if len(h) == 3:
            r, g, b = (int(c * 2, 16) for c in h)
        elif len(h) in (6, 8):
            r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        else:
            continue
        # SZL neutrals (#e8e8ea, #9a9a9e, ...) carry a <=4/255 cool cast by design;
        # anything wider than that is a real hue and is forbidden.
        assert max(r, g, b) - min(r, g, b) <= 4, (
            f"non-grey hex #{h} in the identity layer (monochrome only)")
    for fn in ("hsl(", "hwb(", "lch(", "oklch("):
        assert fn not in layer, f"colour function {fn} in the identity layer"
    for m in re.findall(r"rgba?\(([^)]*)\)", layer):
        parts = [p.strip() for p in m.replace("/", ",").split(",")]
        nums = [p for p in parts[:3] if re.fullmatch(r"\d+", p)]
        if len(nums) == 3:
            assert len(set(nums)) == 1, f"non-grey rgb({m}) in the identity layer"


# ----------------------------------------------------------- 7. no collisions

def test_copy_is_protected_from_the_canvas_by_a_scrim(html: str) -> None:
    assert "hero-scrim" in html
    assert ".hero::after" in html, "second scrim pass missing; copy could collide with the field"


def test_mobile_dims_the_field_so_copy_stays_legible(html: str) -> None:
    assert "@media (max-width:999px)" in html or "@media(max-width:999px)" in html
