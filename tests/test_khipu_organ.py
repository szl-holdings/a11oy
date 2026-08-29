# SPDX-License-Identifier: Apache-2.0
"""Static contracts for the KHIPU product organ on a-11-oy.com.

Locks original-cut honesty: never a rehost, never a fabricated joule, never
proven_trust, never a FIFO Hub card, never a11oy.com as origin.
"""
from pathlib import Path

import szl_khipu_organ as khipu

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "web" / "khipu.html").read_text(encoding="utf-8")
SERVE = (ROOT / "serve.py").read_text(encoding="utf-8")
DOCKER = (ROOT / "Dockerfile").read_text(encoding="utf-8")
LANDING = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")


def test_first_paint_is_connecting() -> None:
    assert 'id="liveTag" aria-live="polite">KHIPU · CONNECTING<' in PAGE
    assert "First paint is CONNECTING" in PAGE
    assert "KHIPU · LIVE" not in PAGE
    assert "proven_trust false" in PAGE
    assert "energy UNAVAILABLE" in PAGE
    assert "CUDA UNAVAILABLE" in PAGE
    assert "Conjecture 1 OPEN" in PAGE


def test_page_is_original_cut_not_rehost() -> None:
    assert "never a rehost" in PAGE.lower() or "never a rehost of" in PAGE
    assert "not SGLang" in PAGE
    assert "not Mixtral" in PAGE
    assert "not SageAttention" in PAGE
    assert "not FlashAttention" in PAGE or "FlashAttention" in PAGE
    assert "a11oy.com" in PAGE  # never-origin disclosure
    assert "FIFO kernel Hub cards" in PAGE
    assert "stay 401" in PAGE
    assert "cdn.jsdelivr.net" not in PAGE
    assert "fonts.googleapis.com" not in PAGE


def test_status_is_unsigned_and_unmeasured() -> None:
    s = khipu.status()
    assert s["organ"] == "KHIPU"
    assert s["honesty"]["proven_trust"] is False
    assert s["honesty"]["energy"] == "UNAVAILABLE"
    assert s["honesty"]["cuda"] == "UNAVAILABLE"
    assert s["honesty"]["conjecture_1"] == "OPEN"
    assert s["duals"]["Ari"] == "GreenLight"
    assert s["duals"]["Kay Pacha"] == "Anatomy"
    assert s["product"]["path"] == "/khipu"
    assert s["khipu_receipt"]["proven_trust"] is False
    assert s["locked_proven"]["count"] == 8
    assert len(s["cuts"]) == 6


def test_kernels_fail_closed() -> None:
    g = khipu.lambda_gate()
    z = khipu.lambda_gate([0.0] + khipu._FLOORS[1:])
    assert g["advisory"] is True and g["proven_trust"] is False
    assert z["blocked"] is True and z["value"] == 0.0
    assert khipu.greenlight()["greenlit"] == 1
    assert khipu.greenlight(paint_sorry=1)["blocked"] == 1
    assert khipu.greenlight(claim_proven=1)["blocked"] == 1
    assert khipu.greenlight(stamp_joule=1)["blocked"] == 1
    assert khipu.anatomy()["blocked"] is False
    assert khipu.anatomy(zero_heart=True)["blocked"] is True
    assert khipu.anatomy(fabricate_joule=True)["blocked"] is True
    assert khipu.prefix_witness()["hold"] == 1
    assert khipu.prefix_witness(hijack=1)["broken"] == 1
    assert khipu.route_witness()["hold"] == 1
    assert khipu.route_witness(tamper=1)["broken"] == 1


def test_healthz_never_claims_cuda_or_joule() -> None:
    h = khipu.healthz()
    assert h["ok"] is True
    assert h["certified"] is False
    assert h["proven_trust"] is False
    assert h["cuda"] == "UNAVAILABLE"
    assert h["energy"] == "UNAVAILABLE"


def test_routes_wired_in_serve_and_image() -> None:
    assert 'app.add_api_route("/khipu", _ptg_serve("khipu.html"), methods=["GET", "HEAD"]' in SERVE
    assert 'app.add_api_route("/a11oy/khipu", _ptg_serve("khipu.html"), methods=["GET", "HEAD"]' in SERVE
    assert "import szl_khipu_organ" in SERVE
    assert "COPY szl_khipu_organ.py" in DOCKER
    assert "web/khipu.html" in DOCKER
    src = (ROOT / "szl_khipu_organ.py").read_text(encoding="utf-8")
    assert "/api/{ns}/v1/khipu-organ" in src
    assert "app.router.routes.insert" not in src
    assert 'prefixes = [f"/api/{ns}/v1/khipu-organ"]' in src
    assert "/api/a11oy/v1/khipu-organ" in PAGE
    assert 'const API="/api/a11oy/v1/khipu-organ"' in PAGE
    assert "Two public origins only" in PAGE
    st = khipu.status()
    assert st["origins"]["product"] == "https://a-11-oy.com"
    assert st["origins"]["proof"] == "https://a11oy.net"
    assert "holdings" not in st
    assert "holdings.a-11-oy.com" not in PAGE


def test_landing_does_not_expand_the_door() -> None:
    # NVIDIA-style door stays Products / Catalog / Proof. LYTE is the one BIND
    # package on the door. KHIPU is a bound path (GET /khipu), not a fifth flagship
    # and not a surface card.
    assert 'id="bind-khipu"' not in LANDING
    assert 'href="/khipu"' not in LANDING
    assert "three flagships" in LANDING
    assert "Not nine surfaces" in LANDING or "not nine surfaces" in LANDING


def test_selftest() -> None:
    assert khipu._selftest()["ok"] is True
