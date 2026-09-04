#!/usr/bin/env python3
"""Network-free contract for the vertical intelligence card overhaul."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "a11oy_landing.html"


def source() -> str:
    return LANDING.read_text(encoding="utf-8")


def card_section(text: str) -> str:
    start = text.index('id="vertical-bodies"')
    end = text.index("<!-- ====================== FLAGSHIPS", start)
    return text[start:end]


def test_five_public_cards_have_unique_domain_instruments() -> None:
    text = source()
    section = card_section(text)
    assert 'data-szl-vertical-intelligence-cards-v2="true"' in section
    assert section.count('class="body-card"') == 5

    expected = {
        "terra": "parcel-grid",
        "killinchu": "voyage-radar",
        "counsel": "authority-chain",
        "finance": "probability-orbit",
        "lyte": "service-lattice",
    }
    for vertical, motif in expected.items():
        assert section.count(f'id="body-{vertical}"') == 1
        assert section.count(f'data-vertical="{vertical}"') == 1
        assert section.count(f'data-motif="{motif}"') == 1
        assert (
            f"https://szlholdings-vertical-services.hf.space/intelligence/{vertical}"
            in section
        )


def test_cards_expose_model_kernel_and_authority_boundaries() -> None:
    section = card_section(source())
    for fragment in (
        "Model route",
        "Kernel route",
        "Khipu 1.5B",
        "ReceiptAgent",
        "A11OY-MINI",
        "kernel-suite",
        "invariants",
        "lambda-gate",
        "receipt-attn",
        "block-kv",
        "SIMULATED EFFECTS",
        "NO TRADE EXECUTION",
        "NO CUSTODY",
        "ATTORNEY-LED",
        "NO FILING AUTHORITY",
        "NO PERSON PROSPECTING",
        "HUMAN BIND",
        "4 OPERATIONAL PLANES",
        "IMMUNE MIGRATION-GATED",
        "ONE PUBLIC RUNTIME",
        "https://szlholdings-killinchu.hf.space/defend",
    ):
        assert fragment in section


def test_card_section_is_dependency_free_and_accessible() -> None:
    text = source()
    section = card_section(text)
    lowered = section.lower()
    for forbidden in ("<script", "<iframe", "unpkg", "jsdelivr", "cdn."):
        assert forbidden not in lowered
    assert section.count('aria-hidden="true"') == 5
    assert section.count("Enter ") >= 5
    assert "@media(prefers-reduced-motion:reduce)" in text
    assert "@media(forced-colors:active)" in text
    assert "min-height:46px" in text


def test_responsive_card_geometry_is_source_native() -> None:
    text = source()
    for fragment in (
        ".body-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr))",
        "#body-terra{grid-column:span 5}",
        "#body-killinchu{grid-column:span 7}",
        ".body-card,#body-terra,#body-killinchu{grid-column:span 6}",
        ".body-card,#body-terra,#body-killinchu{grid-column:1;min-height:auto}",
        "@keyframes szl-radar-sweep",
    ):
        assert fragment in text
    assert text.count("  .fabric-note{") == 1
