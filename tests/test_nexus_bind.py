# SPDX-License-Identifier: Apache-2.0
"""Static contracts for the NEXUS analog vanity path on a-11-oy.com.

Locks BIND_AS_A11OY_PACKAGE honesty without a landing-door expansion, atlas
rewrite, fourth flagship, Hub 307, or fabricated LIVE energy.
"""
from pathlib import Path

import szl_nexus as nexus

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "web" / "nexus.html").read_text(encoding="utf-8")
SERVE = (ROOT / "serve.py").read_text(encoding="utf-8")
DOCKER = (ROOT / "Dockerfile").read_text(encoding="utf-8")
LANDING = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")


def test_first_paint_is_connecting_never_live_or_running() -> None:
    assert 'id="liveTag" aria-live="polite">NEXUS · CONNECTING<' in PAGE
    assert 'id="organBadge">BIND · connecting<' in PAGE
    assert "first paint is <b>CONNECTING</b>" in PAGE
    assert "never fabricates <b>LIVE</b>, <b>RUNNING</b>, or <b>PASS</b>" in PAGE
    assert "NEXUS · LIVE" not in PAGE
    assert "Hub Space is <b>private</b>" in PAGE


def test_page_does_not_claim_certificate_or_flagship() -> None:
    assert "not a fourth flagship" in PAGE.lower()
    assert "not a production certificate" in PAGE.lower()
    assert "BIND_AS_A11OY_PACKAGE" in PAGE
    assert "a11oy.com" in PAGE  # never-origin disclosure
    assert "Do not clone" in PAGE or "do not clone" in PAGE.lower()


def test_status_is_bind_unsigned_and_unmeasured() -> None:
    s = nexus.status()
    assert s["state"] == "BIND"
    assert s["honesty"]["certified"] is False
    assert s["honesty"]["proven_trust"] is False
    assert s["honesty"]["fourth_flagship"] is False
    assert s["honesty"]["nexus"] == "SOFTWARE"
    assert "UNAVAILABLE" in s["honesty"]["energy_joule"]
    assert s["hub"]["running"] is False
    assert s["hub"]["public"] is False
    assert s["hub"]["state"] == "UNAVAILABLE"
    assert s["source"]["sha"].startswith("bf7765ce")
    assert s["khipu_receipt"]["proven_trust"] is False
    assert s["product"]["certified"] is False
    assert s["product"]["path"] == "/nexus"
    assert len(s["frontiers"]) == 20
    assert s["modules"] == ["grid", "scope", "tape", "patch", "seq", "voice"]
    assert len(s["organs"]) == 5
    assert s["willay"]["organ"] is False


def test_healthz_never_claims_hub_running() -> None:
    h = nexus.healthz()
    assert h["ok"] is True
    assert h["hub_running"] is False
    assert h["hub_public"] is False
    assert h["certified"] is False
    assert h["proven_trust"] is False
    assert h["energy_joule"] == "UNAVAILABLE"


def test_routes_wired_in_serve_and_image() -> None:
    assert 'app.add_api_route("/nexus", _ptg_serve("nexus.html"), methods=["GET", "HEAD"]' in SERVE
    assert 'app.add_api_route("/a11oy/nexus", _ptg_serve("nexus.html"), methods=["GET", "HEAD"]' in SERVE
    assert "import szl_nexus" in SERVE
    assert "COPY szl_nexus.py" in DOCKER
    assert "web/nexus.html" in DOCKER


def test_landing_door_not_expanded() -> None:
    """Product door stays Products / Catalog / Proof. NEXUS is a vanity path."""
    assert 'id="bind-nexus"' not in LANDING
    assert 'href="/nexus"' not in LANDING
    assert ">NEXUS<" not in LANDING


def test_zero_cdn_and_mobile() -> None:
    assert "cdn.jsdelivr.net" not in PAGE
    assert "fonts.googleapis.com" not in PAGE
    assert "<script src=\"http" not in PAGE
    assert "@media(max-width:760px)" in PAGE
    assert 'class="table-scroll" role="region"' in PAGE
    assert "repeat(auto-fit,minmax(min(100%,200px),1fr))" in PAGE
