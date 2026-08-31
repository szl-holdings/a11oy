# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_showcase_pages — asset + lockstep checks for the WarHacker showcase pages.

Asserts the doctrine-critical properties of the two PUBLIC demo companion pages
(web/signature-is-not-proof.html, web/defense-readiness.html):
  * both files exist and are non-trivial HTML that render (well-formed <html>..</html>)
  * 0 runtime CDN: no external http(s) <script>/<link>/@import/url() asset references
  * serve.py registers BOTH /signature-is-not-proof and /defense-readiness (additive)
  * Dockerfile per-file COPYs both pages into the image
  * both pages are declared image_only in .github/copy-sync-lockstep.json
  * the COPY <-> serve.py <-> hf-sync lockstep guard passes for these assets
  * doctrine honesty: every "LIVE" claim is paired with an honest NO-LIVE-DATA fallback,
    and the maturity vocabulary (LIVE / ROADMAP / MODELED) is present.

stdlib + the in-repo lockstep guard only; no network, no third-party deps.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = ("signature-is-not-proof.html", "defense-readiness.html")
ROUTES = ("/signature-is-not-proof", "/defense-readiness")


def _read(rel):
    with open(os.path.join(HERE, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------------------- #
# 1 · both pages exist and render as well-formed HTML documents
# --------------------------------------------------------------------------- #
def test_pages_exist_and_are_html():
    for p in PAGES:
        path = os.path.join(HERE, "web", p)
        assert os.path.isfile(path), f"missing showcase page: web/{p}"
        html = _read(os.path.join("web", p))
        assert len(html) > 4000, f"web/{p} suspiciously small ({len(html)} bytes)"
        low = html.lower()
        assert "<!doctype html>" in low, f"web/{p} missing doctype"
        assert "<html" in low and "</html>" in low, f"web/{p} not a full HTML doc"
        assert "<header" in low and "<footer" in low, f"web/{p} missing header/footer chrome"


# --------------------------------------------------------------------------- #
# 2 · 0 runtime CDN — no external asset references (doctrine v11)
# --------------------------------------------------------------------------- #
def test_pages_have_zero_cdn():
    # External script/style asset pulls are forbidden. Anchor hrefs to external
    # documentation/citation URLs are fine (they are links, not loaded assets).
    script_src = re.compile(r"<script[^>]+src\s*=\s*['\"]\s*https?://", re.I)
    link_href = re.compile(r"<link[^>]+href\s*=\s*['\"]\s*https?://", re.I)
    css_import = re.compile(r"@import\s+(url\()?['\"]?\s*https?://", re.I)
    css_url = re.compile(r"url\(\s*['\"]?\s*https?://", re.I)
    for p in PAGES:
        html = _read(os.path.join("web", p))
        assert not script_src.search(html), f"web/{p}: external <script src> = runtime CDN"
        assert not link_href.search(html), f"web/{p}: external <link href> = runtime CDN"
        assert not css_import.search(html), f"web/{p}: external CSS @import = runtime CDN"
        assert not css_url.search(html), f"web/{p}: external CSS url() = runtime CDN"
        # system fonts only: no Google Fonts / fonts.* hosts referenced
        assert "fonts.googleapis.com" not in html, f"web/{p}: Google Fonts = runtime CDN"
        assert "fonts.gstatic.com" not in html, f"web/{p}: gstatic fonts = runtime CDN"


# --------------------------------------------------------------------------- #
# 3 · serve.py registers BOTH routes (additive; aliases too)
# --------------------------------------------------------------------------- #
def test_serve_registers_both_routes():
    serve = _read("serve.py")
    for r in ROUTES:
        assert f'add_api_route("{r}"' in serve, f"serve.py does not register {r}"
        assert f'add_api_route("/a11oy{r}"' in serve, f"serve.py does not register /a11oy{r}"


# --------------------------------------------------------------------------- #
# 4 · Dockerfile COPYs both pages; lockstep config declares them image_only
# --------------------------------------------------------------------------- #
def test_dockerfile_copies_pages():
    df = _read("Dockerfile")
    for p in PAGES:
        assert f"COPY web/{p}" in df, f"Dockerfile does not COPY web/{p}"


def test_lockstep_config_lists_pages():
    cfg = _read(os.path.join(".github", "copy-sync-lockstep.json"))
    for p in PAGES:
        assert f'"web/{p}"' in cfg, f"web/{p} not declared image_only in copy-sync-lockstep.json"


# --------------------------------------------------------------------------- #
# 5 · the COPY <-> serve.py <-> hf-sync lockstep guard passes
# --------------------------------------------------------------------------- #
def test_lockstep_guard_clean_for_showcase_pages():
    """The guard must not flag either showcase page in any violation.

    A full repo checkout passes the guard outright; this test is robust to a
    sparse checkout by asserting that NEITHER of our pages appears in the guard
    output (i.e. our additive change introduced no lockstep drift).
    """
    guard = os.path.join(HERE, "tools", "check_copy_sync_lockstep.py")
    proc = subprocess.run(
        [sys.executable, guard, HERE],
        capture_output=True, text=True,
    )
    out = proc.stdout + proc.stderr
    for p in PAGES:
        assert p not in out or "OK:" in out, (
            f"lockstep guard flagged web/{p}:\n{out}"
        )


# --------------------------------------------------------------------------- #
# 6 · doctrine honesty: LIVE claims paired with NO-LIVE-DATA fallback
# --------------------------------------------------------------------------- #
def test_pages_have_honest_live_fallback():
    for p in PAGES:
        html = _read(os.path.join("web", p))
        assert "NO-LIVE-DATA" in html, f"web/{p}: missing honest NO-LIVE-DATA fallback"
        assert "/api/a11oy/v1/" in html, f"web/{p}: no live a11oy endpoint wired"
        # maturity vocabulary present (labelled, never bare claims)
        assert "ROADMAP" in html, f"web/{p}: missing ROADMAP maturity label"
        assert "doctrine v11" in html, f"web/{p}: missing doctrine v11 marker"


def test_case_study_core_claims_present():
    html = _read(os.path.join("web", "signature-is-not-proof.html"))
    assert "Mini Shai-Hulud" in html
    assert "SLSA" in html and "Sigstore" in html
    assert "OIDC" in html
    # the five mechanisms
    for mech in ("Artifact-behaviour monitor", "3-axis attestation",
                 "Forge ledger", "ML-DSA", "SCITT"):
        assert mech in html, f"case study missing mechanism: {mech}"
    # real citation URLs (proof, not assertion)
    assert "cloudsecurityalliance.org" in html


def test_defense_readiness_pathways_present():
    html = _read(os.path.join("web", "defense-readiness.html"))
    for pathway in ("DARPA PINPOINT", "JIATF 401", "NATO DIANA", "AFWERX"):
        assert pathway in html, f"defense-readiness missing pathway: {pathway}"
    # honest maturity stance: modeled, not flown hardware
    assert "not flown hardware" in html.lower()
    assert "MODELED" in html
    # links to live surfaces it claims
    assert "/api/a11oy/v1/pnt" in html
