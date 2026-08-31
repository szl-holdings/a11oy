# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""test_energy_ops_dashboard.py — guards the press-play "Today" operator console.

Dev4 frontend deliverable: pages/energy-ops.html + its /energy-ops route in serve.py.
This suite asserts, OFFLINE and deterministically (no network, no GPU):

  (1) the /energy-ops route is registered in serve.py and serves the page file;
  (2) the page wires the PLAY/STOP buttons to the REAL operator endpoints
      (POST /energy/operator/start + /stop, GET /energy/operator/status);
  (3) every live panel reads its real endpoint (ledger, projection, harvest/posture);
  (4) all four honesty-chip states render (MEASURED/MODELED/SAMPLE/ESTIMATE)
      plus the ZERO + DEGRADED states doctrine v11 requires;
  (5) revenue is NEVER shown MEASURED until a real charge clears (ZERO default);
  (6) degraded / NO-LIVE-DATA handling exists for 404/error;
  (7) grep-assert: 0 runtime CDN (no external <script src>/<link href>/url());
  (8) grep-assert: system fonts only (no @font-face / webfont import).

Run: python test_energy_ops_dashboard.py   (also collectable by pytest)
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "pages" / "energy-ops.html"
SERVE = ROOT / "serve.py"

API = "/api/a11oy/v1"


def _page() -> str:
    assert PAGE.is_file(), f"missing dashboard page: {PAGE}"
    return PAGE.read_text(encoding="utf-8")


def _serve() -> str:
    assert SERVE.is_file(), f"missing serve.py: {SERVE}"
    return SERVE.read_text(encoding="utf-8")


# ---------------------------------------------------------------- (1) route
def test_route_registered():
    s = _serve()
    assert '@app.get("/energy-ops")' in s, "/energy-ops route not registered in serve.py"
    # serves the page file, with the honest INDEX_HTML fallback (no fabricated stub)
    assert 'PAGES_DIR / "energy-ops.html"' in s
    assert "FileResponse(INDEX_HTML" in s
    # registered before the SPA catch-all (explicit route wins): the energy-ops
    # block must appear before the viz/frontier block which sits just above the SPA.
    assert s.index('@app.get("/energy-ops")') < s.index('@app.get("/viz")'), \
        "energy-ops route must be registered before later catch-all routes"


# ------------------------------------------------- (2) PLAY/STOP -> operator
def test_play_stop_hit_real_operator_endpoints():
    p = _page()
    # POST start + stop (the press-play toggle), GET status
    assert f'{API}/energy/operator/' in p
    assert '"/energy/operator/" + action' in p or "/energy/operator/start" in p
    assert "start" in p and "stop" in p
    assert f'{API}/energy/operator/status' in p
    # the toggle issues a POST (not a GET) for start/stop
    assert 'method: "POST"' in p
    # there is a real button bound to a click handler
    assert 'id="play"' in p
    assert 'addEventListener("click"' in p


# ------------------------------------------------ (3) panels read live data
def test_panels_read_live_endpoints():
    p = _page()
    for ep in (
        f"{API}/energy/operator/status",   # node status + today totals
        f"{API}/energy/ledger",            # receipt feed + dry-run earnings
        f"{API}/energy/projection?window=running",  # 1-day MODELED headline
        f"{API}/harvest/posture",          # grid price + negative window
    ):
        assert ep in p, f"panel does not read live endpoint: {ep}"
    # the wow-moment negative-window indicator + big measured-joules counter
    assert "neg-banner" in p
    assert "THE GRID IS PAYING US" in p.upper()
    assert "big-joules" in p


# -------------------------------------------------- (4) honesty chips render
def test_all_honesty_chip_states_present():
    p = _page()
    for label in ("MEASURED", "MODELED", "SAMPLE", "ESTIMATE", "ZERO", "DEGRADED"):
        assert label in p, f"honesty label missing: {label}"
    for cls in ("chip-measured", "chip-modeled", "chip-sample",
                "chip-estimate", "chip-zero", "chip-degraded"):
        assert cls in p, f"chip css class missing: {cls}"
    # a 4-state chip helper exists (replicated szl3d_label)
    assert "function setChip" in p


# --------------------------------------- (5) revenue never MEASURED-by-default
def test_revenue_not_measured_until_charge_clears():
    p = _page()
    # the "real cleared revenue" metric defaults to ZERO and only flips to
    # MEASURED when realCents > 0 (a cleared charge) — never fabricated.
    assert 'id="m-real-chip"' in p
    assert 'realCents > 0 ? "MEASURED" : "ZERO"' in p
    # earnings-so-far is explicitly MODELED dry-run, not MEASURED
    assert "dryRunTotal" in p
    assert 'id="m-earn-chip"' in p
    # doctrine intent stated on the page
    assert "until a real" in p.lower() and "charge clears" in p.lower()


# ----------------------------------------------- (6) degraded / NO-LIVE-DATA
def test_degraded_handling():
    p = _page()
    assert "NO-LIVE-DATA" in p
    assert "DEGRADED" in p
    # an error sentinel path exists (404/error -> __error) and never fabricates
    assert "__error" in p
    assert "function isErr" in p


# -------------------------------------------------------- (7) 0 runtime CDN
def test_zero_runtime_cdn():
    p = _page()
    cdn_markers = [
        "http://", "https://", "//cdn", "cdnjs", "unpkg", "jsdelivr",
        "googleapis", "gstatic", "cloudflare", "skypack", "esm.sh",
    ]
    low = p.lower()
    for m in cdn_markers:
        # allow nothing — the page must be fully self-contained
        assert m not in low, f"runtime CDN / external URL reference found: {m!r}"
    # no external script/link to an off-origin asset
    for tag in re.findall(r'<script[^>]*\bsrc=("[^"]*"|\'[^\']*\')', p, re.I):
        assert tag.strip("'\"").startswith("/"), f"external script src: {tag}"
    for tag in re.findall(r'<link[^>]*\bhref=("[^"]*"|\'[^\']*\')', p, re.I):
        href = tag.strip("'\"")
        assert href.startswith("/") or href.startswith("#"), f"external link href: {tag}"


# ----------------------------------------------------- (8) system fonts only
def test_system_fonts_only():
    p = _page().lower()
    assert "@font-face" not in p, "no custom webfonts allowed (system fonts only)"
    assert "fonts.googleapis" not in p
    assert "system-ui" in p, "page should declare a system-ui font stack"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
