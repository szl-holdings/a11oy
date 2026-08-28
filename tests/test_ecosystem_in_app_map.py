# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Contracts for /ecosystem as an in-app command-surface map.

Atlas inventory and ROADMAP cuts belong on https://a11oy.net. This page must not
present itself as the Hub atlas, must keep interactive /verify on a-11-oy.com,
and must not stamp the unhyphenated a11oy.com host.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ECOSYSTEM = (ROOT / "pages" / "ecosystem.html").read_text(encoding="utf-8")


def test_ecosystem_is_an_in_app_map_not_the_hub_atlas() -> None:
    assert "in-app map" in ECOSYSTEM.lower() or "In-app map" in ECOSYSTEM
    assert "Not the Hub atlas" in ECOSYSTEM or "not the Hub atlas" in ECOSYSTEM
    assert "Ecosystem Atlas" not in ECOSYSTEM
    assert 'href="https://a11oy.net"' in ECOSYSTEM
    assert "ROADMAP" in ECOSYSTEM
    assert "Hub atlas" in ECOSYSTEM
    assert 'href="/api/a11oy/v1/ecosystem/atlas"' not in ECOSYSTEM


def test_ecosystem_keeps_interactive_verify_on_this_origin() -> None:
    assert 'href="/verify"' in ECOSYSTEM
    assert "Interactive receipt verify stays here" in ECOSYSTEM or "interactive verifier on this origin" in ECOSYSTEM.lower()
    assert "https://a11oy.net/verify" not in ECOSYSTEM


def test_ecosystem_has_product_proof_origin_header() -> None:
    assert ">Product<" in ECOSYSTEM
    assert ">Proof<" in ECOSYSTEM
    assert 'href="https://a-11-oy.com"' in ECOSYSTEM
    assert 'href="https://a11oy.net">Proof</a>' in ECOSYSTEM
    assert 'aria-label="Product and proof origins"' in ECOSYSTEM


def test_ecosystem_public_default_omits_hidden_operator_surfaces() -> None:
    lowered = ECOSYSTEM.lower()
    assert "killinchu" not in lowered
    assert "contract gap" not in lowered
    assert "labsintro" not in lowered
    assert 'data-view="labs"' not in ECOSYSTEM
    assert "flag switcher" not in lowered
    assert 'class="switcher"' not in ECOSYSTEM


def test_ecosystem_introduces_no_a11oy_com_canonical() -> None:
    assert "https://a11oy.com" not in ECOSYSTEM
    assert "http://a11oy.com" not in ECOSYSTEM
    assert 'href="https://a-11-oy.com/ecosystem"' in ECOSYSTEM


def test_ecosystem_does_not_ship_investor_view() -> None:
    assert "/investor" not in ECOSYSTEM
    assert "Investor View" not in ECOSYSTEM


def test_ecosystem_maps_command_and_proof_surfaces() -> None:
    for href in ("/console", "/console#ask", "/console#decision", "/governance", "/trust", "/frontier"):
        assert f'href:\'{href}\'' in ECOSYSTEM or f'href="{href}"' in ECOSYSTEM
    assert "Λ = Conjecture 1" in ECOSYSTEM
    assert "Alloy by SZL Holdings" in ECOSYSTEM
