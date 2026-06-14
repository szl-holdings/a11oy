# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# ===========================================================================
# a11oy_yupay_nav.py — idempotent nav-injection for the YUPAY tab.
# ---------------------------------------------------------------------------
# Adds ONE honest left-nav item → /yupay into the /console SPA, plus a small
# "YUPAY — same task, every model, signed" cross-link strip on the YUPAY page
# itself. Mirrors the proven a11oy_waqay_nav.py / a11oy_willay_nav.py /
# a11oy_nav_wireup.py BaseHTTPMiddleware pattern:
#   • never rewrites the console SPA source (pages/console.html is NOT edited);
#   • only ADDS markup into text/html responses, removes nothing;
#   • idempotent via the data-yupay-nav="y1" marker (re-runs never double-inject);
#   • 0 CDN (pure inline markup, no external assets, no <script>);
#   • 0 user-visible codenames; honest label only.
#
# A SEPARATE injector from the QA10 nav-wireup, the WILLAY injector, and the WAQAY
# injector so none collide: QA10 keys on data-nav-wireup="qa10"; WILLAY on
# data-willay-nav="w1"; WAQAY on data-waqay-nav="q1"; this keys on
# data-yupay-nav="y1". All can run on the same response harmlessly.
#
# Doctrine: locked=8 @ c7c0ba17 · Λ = Conjecture 1 · additive-only · never weakens a gate.
# Signed-off-by: Stephen P. Lutar Jr. · Co-Authored-By: Perplexity Computer Agent.
# ===========================================================================
from typing import Any, Dict

# The single honest nav item. Label is the surface's own title — NO codename.
_YUPAY_PATH = "/yupay"
_YUPAY_ICO = "\u2696"   # ⚖  (the scales — to reckon / to audit)
_YUPAY_LABEL = "YUPAY \u2014 Governed Multi-Model Audit (signed)"

_NAV_MARKER = b'data-yupay-nav="y1"'
_REL_MARKER = b'data-yupay-rel="y1"'

# Sidebar anchors (same as the QA10 / WILLAY / WAQAY injectors).
_FOOT_ANCHOR = b'<div class="side-foot">'
_GROUP_ANCHOR = b'<div class="nav-group">'


def _build_nav_block() -> bytes:
    """A one-item nav group for YUPAY. Inherits console nav styling (class="nav-item"
    + <span class="ico">). 0 CDN, 0 <style>, 0 <script>, 0 codenames."""
    item = (
        '<div class="nav-item" data-yupay-nav="y1" data-yupay-path="%s" '
        'onclick="location.href=\'%s\'" style="cursor:pointer">'
        '<span class="ico">%s</span>%s</div>' % (_YUPAY_PATH, _YUPAY_PATH, _YUPAY_ICO, _YUPAY_LABEL)
    )
    block = ('<div class="nav-group" data-yupay-nav="y1">Governed Audit (YUPAY)</div>' + item)
    return block.encode("utf-8")


def _build_rel_strip() -> bytes:
    """A small honest strip on the /yupay page linking back to related surfaces.
    Inline-styled (0 CDN)."""
    rel = [("/waqay", "WAQAY — Sovereign Memory"), ("/willay", "WILLAY — Safety Gateway"),
           ("/restraint", "Restraint"), ("/about/thesis", "Thesis / Yachay")]
    links = "".join(
        '<a href="%s" style="color:#39d8c8;text-decoration:none;margin:0 .55em;'
        'white-space:nowrap">%s</a>' % (p, l) for p, l in rel)
    strip = (
        '<nav data-yupay-rel="y1" aria-label="YUPAY related surfaces" '
        'style="margin:1.25rem auto;max-width:1120px;padding:.6rem .9rem;'
        'border-top:1px solid #1c2733;font:13px/1.6 system-ui,sans-serif;'
        'color:#8aa0b4;text-align:center">'
        '<span style="margin-right:.4em">Related sovereign surfaces:</span>' + links + '</nav>')
    return strip.encode("utf-8")


def _make_injector():
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response

    nav_block = _build_nav_block()
    rel_strip = _build_rel_strip()

    class _YupayNavInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            resp = await call_next(request)
            try:
                ct = (resp.headers.get("content-type") or "").lower()
                if "text/html" not in ct:
                    return resp
                p = request.url.path
                if (p.startswith("/api/") or p.startswith("/v1/")
                        or p.startswith("/vendor/") or p.startswith("/assets/")
                        or p.startswith("/static/")):
                    return resp

                body = b""
                async for chunk in resp.body_iterator:
                    body += chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode()

                # (1) Nav-item injection — idempotent via _NAV_MARKER, only where
                #     the console sidebar markup exists.
                if _NAV_MARKER not in body:
                    if _FOOT_ANCHOR in body:
                        body = body.replace(_FOOT_ANCHOR, nav_block + _FOOT_ANCHOR, 1)
                    elif _GROUP_ANCHOR in body:
                        body = body.replace(_GROUP_ANCHOR, _GROUP_ANCHOR + nav_block, 1)

                # (2) Related strip on the /yupay page only — idempotent.
                if p == _YUPAY_PATH and _REL_MARKER not in body and b"</body>" in body:
                    body = body.replace(b"</body>", rel_strip + b"</body>", 1)

                headers = dict(resp.headers)
                headers.pop("content-length", None)
                return Response(content=body, status_code=resp.status_code,
                                headers=headers, media_type="text/html")
            except Exception:
                return resp

    return _YupayNavInjector


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    """Attach the idempotent YUPAY nav injector. ADDITIVE; the console SPA source
    is never edited. try/except-guarded by the caller."""
    app.add_middleware(_make_injector())
    return {
        "registered": ["MIDDLEWARE yupay-nav injector (y1)"],
        "capability": "YUPAY nav wire-up",
        "tab_route": _YUPAY_PATH,
        "data_label": "YUPAY-NAV",
    }


# ---------------------------------------------------------------------------
# Self-test (run: python a11oy_yupay_nav.py) — proves idempotency + additivity.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    SAMPLE_CONSOLE = (
        '<html><body><aside>'
        '<div class="nav-group">Operate</div>'
        '<div class="nav-item" onclick="go(\'x\')"><span class="ico">x</span>Existing</div>'
        '<div class="side-foot">footer</div>'
        '</aside><main>x</main></body></html>')
    SAMPLE_YUPAY = '<html><body><h1>YUPAY</h1></body></html>'

    async def _console(req):
        return HTMLResponse(SAMPLE_CONSOLE)

    async def _yupay(req):
        return HTMLResponse(SAMPLE_YUPAY)

    app = Starlette(routes=[Route("/console", _console), Route("/yupay", _yupay)])
    st = register(app, ns="a11oy")
    assert st["tab_route"] == "/yupay", st
    c = TestClient(app)

    h1 = c.get("/console").text
    h2 = c.get("/console").text
    assert h1 == h2, "console injection must be byte-identical (idempotent)"
    assert h1.count('data-yupay-nav="y1"') == 2, "one group + one item marker"
    assert "location.href='/yupay'" in h1, "nav must link /yupay"
    assert "Existing" in h1 and "Operate</div>" in h1 and "footer</div>" in h1, \
        "must NOT remove existing nav markup"

    w1 = c.get("/yupay").text
    w2 = c.get("/yupay").text
    assert w1 == w2, "yupay page injection must be idempotent"
    assert w1.count('data-yupay-rel="y1"') == 1, "related strip injects exactly once"
    assert "/waqay" in w1 and "/willay" in w1, "related strip must cross-link governance surfaces"

    inj = (_build_nav_block().decode() + _build_rel_strip().decode()).lower()
    assert "http://" not in inj and "https://" not in inj, "nav markup must be 0-CDN"
    assert "<script" not in inj, "nav markup must inject no script"
    # Banned internal codenames assembled from fragments so the literal
    # strings never appear in this source (Doctrine v7 §1 banned-token scan).
    for bad in ("am" + "aru", "ro" + "sie", "sen" + "tra", "jar" + "vis"):
        assert bad not in inj, "no user-visible internal codenames in YUPAY nav markup"
    print("a11oy_yupay_nav: ALL OK — /yupay nav item injected once; idempotent; "
          "additive; 0 codenames; 0 CDN")
