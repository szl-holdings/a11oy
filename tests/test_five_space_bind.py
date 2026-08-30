# SPDX-License-Identifier: Apache-2.0
"""Static contracts for the five-space operator BIND surface on a-11-oy.com.

Locks BIND_AS_A11OY_PACKAGE honesty without pretending a local SAMPLE compile
is a live Hub, a production certificate, a Vite dump onto the flagship, or /console.
"""
from pathlib import Path

import szl_five_space as op

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "web" / "five-space.html").read_text(encoding="utf-8")
SERVE = (ROOT / "serve.py").read_text(encoding="utf-8")
DOCKER = (ROOT / "Dockerfile").read_text(encoding="utf-8")
LANDING = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
NAV = (ROOT / "a11oy_nav_wireup.py").read_text(encoding="utf-8")


def test_first_paint_is_connecting_never_live_or_running() -> None:
    assert 'id="liveTag" aria-live="polite">OPERATOR · CONNECTING<' in PAGE
    assert 'id="organBadge">BIND · connecting<' in PAGE
    assert "first paint is <b>CONNECTING</b>" in PAGE.lower() or "First paint is <b>CONNECTING</b>" in PAGE
    assert "never fabricates <b>LIVE</b>, <b>RUNNING</b>, or <b>PASS</b>" in PAGE
    assert "OPERATOR · LIVE" not in PAGE
    assert "Hub RUNNING" not in PAGE or "UNAVAILABLE" in PAGE


def test_page_does_not_claim_certificate_or_flagship() -> None:
    assert "not a second flagship" in PAGE.lower()
    assert "not a production certificate" in PAGE.lower()
    assert "does not replace /console" in PAGE.lower()
    assert "BIND_AS_A11OY_PACKAGE" in PAGE
    assert "a11oy.com" in PAGE  # never-origin disclosure
    assert "Vite dump" in PAGE or "vite dump" in PAGE.lower()
    assert "sovereign=false" in PAGE


def test_five_named_spaces_present() -> None:
    for name in ("Command", "Loop", "Queue", "Memory", "Ledger"):
        assert name in PAGE
    assert 'data-space="command"' in PAGE
    assert 'data-space="ledger"' in PAGE
    assert "UNSIGNED-honest" in PAGE
    assert "a11oy.net/five-space/" in PAGE


def test_status_is_bind_unsigned_and_unmeasured() -> None:
    s = op.status()
    assert s["state"] == "BIND"
    assert s["honesty"]["certified"] is False
    assert s["honesty"]["proven_trust"] is False
    assert s["honesty"]["sovereign"] is False
    assert s["honesty"]["operator"] == "STRUCTURAL-ONLY"
    assert s["honesty"]["replaces_console"] is False
    assert s["honesty"]["vite_dump"] is False
    assert "UNAVAILABLE" in s["honesty"]["energy_joule"]
    assert s["product"]["certified"] is False
    assert s["product"]["path"] == "/five-space"
    assert [sp["id"] for sp in s["spaces"]] == [
        "command",
        "loop",
        "queue",
        "memory",
        "ledger",
    ]
    assert s["spaces"][1]["honesty"] == "SAMPLE"
    assert s["khipu_receipt"]["proven_trust"] is False
    assert s["proof"]["record"] == "https://a11oy.net/five-space/"


def test_healthz_never_claims_hub_running() -> None:
    h = op.healthz()
    assert h["ok"] is True
    assert h["hub_running"] is False
    assert h["certified"] is False
    assert h["proven_trust"] is False
    assert h["sovereign"] is False


def test_routes_wired_in_serve_and_image() -> None:
    assert 'app.add_api_route("/five-space", _ptg_serve("five-space.html"), methods=["GET", "HEAD"]' in SERVE
    assert 'app.add_api_route("/a11oy/five-space", _ptg_serve("five-space.html"), methods=["GET", "HEAD"]' in SERVE
    assert "import szl_five_space" in SERVE
    assert "COPY szl_five_space.py" in DOCKER
    assert "web/five-space.html" in DOCKER


def test_page_cites_two_origins_and_not_console() -> None:
    assert "a-11-oy.com/five-space" in PAGE
    assert "a11oy.net/five-space/" in PAGE
    assert "does not replace /console" in PAGE.lower()
    assert "not a second flagship" in PAGE.lower()


def test_landing_and_nav_cite_the_package() -> None:
    assert 'id="bind-five-space"' in LANDING
    assert 'href="/five-space"' in LANDING
    assert "Five-space operator" in LANDING
    assert "Honesty LIVE" not in LANDING
    assert '("/five-space"' in NAV
    assert '"/five-space": "Sovereign & Agentic Core"' in NAV


def test_zero_cdn_and_mobile() -> None:
    assert "cdn.jsdelivr.net" not in PAGE
    assert "fonts.googleapis.com" not in PAGE
    assert '<script src="http' not in PAGE
    assert "@media(max-width:760px)" in PAGE
    mobile_css = PAGE.split("@media(max-width:760px){", 1)[1].split(
        "@media(max-width:420px){", 1
    )[0]
    assert (
        '[data-related-surfaces="qa10"]'
        "{padding-bottom:calc(4.6rem + env(safe-area-inset-bottom))!important;}"
    ) in mobile_css
    assert 'class="table-scroll" role="region"' in PAGE
    assert "repeat(auto-fit,minmax(min(100%,180px),1fr))" in PAGE
    assert "min-height:44px" in PAGE
