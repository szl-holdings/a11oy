# SPDX-License-Identifier: Apache-2.0
"""Static contracts for the LYTE lattice BIND surface on a-11-oy.com."""
from pathlib import Path

import szl_lyte_lattice as lyte

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "web" / "lyte.html").read_text(encoding="utf-8")
SERVE = (ROOT / "serve.py").read_text(encoding="utf-8")
DOCKER = (ROOT / "Dockerfile").read_text(encoding="utf-8")
LANDING = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")


def test_first_paint_is_connecting_never_live_or_running() -> None:
    assert 'id="liveTag" aria-live="polite">LYTE · CONNECTING<' in PAGE
    assert 'id="organBadge">BIND · connecting<' in PAGE
    assert "first paint is <b>CONNECTING</b>" in PAGE
    assert "never fabricates <b>LIVE</b>, <b>RUNNING</b>, or <b>PASS</b>" in PAGE
    assert "LYTE · LIVE" not in PAGE
    assert "Hub RUNNING" in PAGE and "after Immune readback" in PAGE


def test_page_does_not_claim_certificate_or_flagship() -> None:
    assert "not a second flagship" in PAGE.lower()
    assert "not a production certificate" in PAGE.lower()
    assert "BIND_AS_A11OY_PACKAGE" in PAGE
    assert "a11oy.com" in PAGE
    assert "Do not rehost" in PAGE or "do not rehost" in PAGE.lower()


def test_status_is_bind_unsigned_and_unmeasured() -> None:
    s = lyte.status()
    assert s["state"] == "BIND"
    assert s["honesty"]["certified"] is False
    assert s["honesty"]["proven_trust"] is False
    assert s["honesty"]["lyte"] == "STRUCTURAL-ONLY"
    assert "UNAVAILABLE" in s["honesty"]["energy_joule"]
    assert s["honesty"]["occupancy"].startswith("UNAVAILABLE")
    assert s["hub"]["running"] is False
    assert s["hub"]["state"] == "UNAVAILABLE"
    assert s["source"]["sha"].startswith("9db7f25")
    assert s["khipu_receipt"]["proven_trust"] is False
    assert s["product"]["certified"] is False
    assert s["product"]["path"] == "/lyte"
    assert len(s["frontiers"]) == 28
    assert s["frontiers"][0]["n"] == "lyte"
    assert s["frontiers"][-1]["n"] == "N27"
    assert len(s["waves"]) == 3


def test_healthz_never_claims_hub_running() -> None:
    h = lyte.healthz()
    assert h["ok"] is True
    assert h["hub_running"] is False
    assert h["certified"] is False
    assert h["proven_trust"] is False


def test_routes_wired_in_serve_and_image() -> None:
    assert 'app.add_api_route("/lyte", _ptg_serve("lyte.html"), methods=["GET", "HEAD"]' in SERVE
    assert 'app.add_api_route("/a11oy/lyte", _ptg_serve("lyte.html"), methods=["GET", "HEAD"]' in SERVE
    assert "import szl_lyte_lattice" in SERVE
    assert "COPY szl_lyte_lattice.py" in DOCKER
    assert "web/lyte.html" in DOCKER


def test_landing_binds_the_package_without_lyte_title_case() -> None:
    assert 'href="/lyte"' in LANDING
    assert "LYTE lattice" in LANDING
    assert "not a second flagship" in LANDING.lower() or "BIND package" in LANDING
    assert "Lyte lattice" not in LANDING


def test_zero_cdn_and_mobile() -> None:
    assert "cdn.jsdelivr.net" not in PAGE
    assert "fonts.googleapis.com" not in PAGE
    assert "<script src=\"http" not in PAGE
    assert "@media(max-width:760px)" in PAGE
    assert 'class="table-scroll" role="region"' in PAGE
    assert "repeat(auto-fit,minmax(min(100%,200px),1fr))" in PAGE
