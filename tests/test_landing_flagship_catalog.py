# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Front-door product site: three flagships, Hub catalog, fail-closed honesty.

NVIDIA-style public site — one hero, three products, collections as catalog
not a zoo. Λ uniqueness stays Conjecture 1. No 40 fake SKUs. No invented
GPU joules. 44px hit targets. Vendored three.js only.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONT = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")

COLLECTIONS = (
    "https://huggingface.co/collections/SZLHOLDINGS/szl-flagship-models-6a9315c1c853da528726dd8d",
    "https://huggingface.co/collections/SZLHOLDINGS/szl-kernels-software-6a9315c19d509bb9214d3e64",
    "https://huggingface.co/collections/SZLHOLDINGS/szl-roadmap-no-admitted-data-6a9315c19fb3920077cefe50",
    "https://huggingface.co/collections/SZLHOLDINGS/szl-flagship-spaces-6a9315c15be8186d77796e62",
)

HONESTY = ("MEASURED", "REPORTED", "ROADMAP", "SOFTWARE", "UNAVAILABLE", "SIMULATED")


def test_nav_is_flagships_not_surface_sprawl() -> None:
    nav = FRONT.split('<nav class="nav-links" id="site-nav">', 1)[1].split("</nav>", 1)[0]
    assert 'href="#products"' in nav
    assert 'href="#catalog"' in nav
    assert "https://a11oy.net" in nav
    assert 'href="/console"' in nav
    for sprawl in ("/ecosystem", "/anatomy-v5", "/observability", "/console#arena", "#surfaces"):
        assert sprawl not in nav


def test_three_products_max() -> None:
    assert FRONT.count('class="card product-card"') == 3
    assert 'id="product-a11oy"' in FRONT
    assert 'id="product-killinchu"' in FRONT
    assert 'id="product-forge"' in FRONT
    assert "Nine surfaces" not in FRONT
    assert "All nine surfaces" not in FRONT
    assert "Five Superpowers" not in FRONT
    # Vertical leftovers are not products.
    assert 'id="product-insurance"' not in FRONT
    assert "<h3>Insurance</h3>" not in FRONT
    assert "<h3>Finance</h3>" not in FRONT
    assert "<h3>Real estate</h3>" not in FRONT


def test_lyte_is_bound_package_not_flagship() -> None:
    """LYTE binds onto the product door as a package. Not a fourth flagship."""
    nav = FRONT.split('<nav class="nav-links" id="site-nav">', 1)[1].split("</nav>", 1)[0]
    assert 'href="/lyte"' in nav
    assert 'id="bind-lyte"' in FRONT
    assert "LYTE lattice" in FRONT
    assert "BIND package" in FRONT
    assert "not a flagship" in FRONT.lower() or "Not a fourth product" in FRONT
    assert 'id="product-lyte"' not in FRONT
    assert FRONT.count('class="card product-card"') == 3
    # lexicon_gate on the front door bans title-case Lyte.
    import re

    assert re.search(r"\bLyte\b", FRONT) is None


def test_hub_collections_are_the_catalog() -> None:
    catalog = FRONT.split('id="catalog"', 1)[1].split("</section>", 1)[0]
    for url in COLLECTIONS:
        assert url in catalog
    assert "not forty product SKUs" in FRONT
    assert "ROADMAP cards are empty on purpose" in FRONT or "Not trained" in catalog
    assert "40 Hub" not in FRONT
    assert "all 40" not in FRONT.lower()


def test_honesty_chips_are_fail_closed() -> None:
    for label in HONESTY:
        assert f'<div class="lt">{label}</div>' in FRONT
    assert "Λ = Conjecture 1" in FRONT
    assert "never a theorem" in FRONT
    assert "this page does not invent live GPU joules" in FRONT
    # Λ chip path stays gray, never live/green.
    lam = FRONT.split("function lamChip(elId, v)", 1)[1].split("function ", 1)[0]
    assert "grayChip" in lam
    assert "liveChip" not in lam
    assert "CONJECTURE" in lam


def test_proof_link_is_a11oy_net() -> None:
    assert 'href="https://a11oy.net"' in FRONT
    hero_cta = FRONT.split('class="cta-row"', 1)[1].split("</div>", 1)[0]
    assert "a11oy.net" in hero_cta


def test_no_threejs_cdn_on_front_door() -> None:
    for host in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com", "threejs.org/build"):
        assert host not in FRONT
    assert "/hero/vendor3d/three.module.min.js" in FRONT


def test_hit_targets_remain_44px() -> None:
    assert "min-height:44px" in FRONT
    assert "min-width:44px" in FRONT
    rule = FRONT.split(".nav nav a{", 1)[1].split("}", 1)[0]
    assert "min-height:44px" in rule
    assert "min-width:44px" in rule
