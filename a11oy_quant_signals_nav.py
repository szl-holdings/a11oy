# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# ===========================================================================
# a11oy_quant_signals_nav.py — idempotent nav-injection for the QUANT SIGNALS page.
# ---------------------------------------------------------------------------
# Adds ONE honest left-nav item → /signals into the /console (a11oy) and
# /elite (killinchu) SPAs, plus a small cross-link strip on the /signals
# page itself. Mirrors the proven a11oy_khipu_demo_nav.py / a11oy_uds_portability_nav.py
# BaseHTTPMiddleware pattern:
#   • never rewrites the SPA source (pages/console.html is NOT edited);
#   • only ADDS markup into text/html responses, removes nothing;
#   • idempotent via the data-quantsignals-nav="s1" marker (re-runs never double-inject);
#   • 0 CDN (pure inline markup, no external assets, no <script>);
#   • 0 user-visible codenames; honest label only.
#
# A SEPARATE injector from QA10 / WILLAY / WAQAY / YUPAY / UDS / KHIPU so none collide:
#   QA10 keys data-nav-wireup="qa10"; WILLAY data-willay-nav="w1"; WAQAY
#   data-waqay-nav="q1"; YUPAY data-yupay-nav="y1"; UDS data-udsport-nav="u1";
#   KHIPU data-khipudemo-nav="k1"; this keys data-quantsignals-nav="s1".
#
# Doctrine: locked=8 @ c7c0ba17 · Λ = Conjecture 1 · additive-only · never weakens a gate.
# Honesty: the target page shows DSSE-signed ADVISORY / PAPER-ONLY receipts,
# re-verified server-side; verification proves INTEGRITY + ORIGIN only. The nav
# label makes no accuracy claim — "signed receipts" only, never "profitable".
# Signed-off-by: Stephen P. Lutar Jr. · Co-Authored-By: Perplexity Computer Agent.
# ===========================================================================
from typing import Any, Dict

_SIGNALS_PATH = "/signals"
_SIGNALS_ICO = "\U0001F4C8"   # 📈  (signals — advisory research, not advice)
_SIGNALS_LABEL = "Quant Signals \u2014 signed receipts"

_NAV_MARKER = b'data-quantsignals-nav="s1"'
_REL_MARKER = b'data-quantsignals-rel="s1"'

# Sidebar anchors (same as the QA10 / WILLAY / WAQAY / YUPAY / UDS / KHIPU injectors).
_FOOT_ANCHOR = b'<div class="side-foot">'
_GROUP_ANCHOR = b'<div class="nav-group">'


def _build_nav_block() -> bytes:
    item = (
        '<div class="nav-item" data-quantsignals-nav="s1" data-quantsignals-path="%s" '
        'onclick="location.href=\'%s\'" style="cursor:pointer">'
        '<span class="ico">%s</span>%s</div>' % (_SIGNALS_PATH, _SIGNALS_PATH, _SIGNALS_ICO, _SIGNALS_LABEL)
    )
    block = ('<div class="nav-group" data-quantsignals-nav="s1">Quant (signed)</div>' + item)
    return block.encode("utf-8")


def _build_rel_strip() -> bytes:
    rel = [("/yupay", "YUPAY — Governed Audit"), ("/waqay", "WAQAY — Sovereign Memory"),
           ("/willay", "WILLAY — Safety Gateway"), ("/khipu-demo", "Khipu Demo")]
    links = "".join(
        '<a href="%s" style="color:#39d8c8;text-decoration:none;margin:0 .55em;'
        'white-space:nowrap">%s</a>' % (p, l) for p, l in rel)
    strip = (
        '<nav data-quantsignals-rel="s1" aria-label="Quant signals related surfaces" '
        'style="margin:1.25rem auto;max-width:1180px;padding:.6rem .9rem;'
        'border-top:1px solid #1c2733;font:13px/1.6 system-ui,sans-serif;'
        'color:#9fb4c6;text-align:center">'
        '<span style="margin-right:.4em">Related sovereign surfaces:</span>' + links + '</nav>')
    return strip.encode("utf-8")


def _make_injector():
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response

    nav_block = _build_nav_block()
    rel_strip = _build_rel_strip()

    class _QuantSignalsNavInjector(BaseHTTPMiddleware):
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

                # (1) Nav-item injection — idempotent, only where the sidebar exists.
                if _NAV_MARKER not in body:
                    if _FOOT_ANCHOR in body:
                        body = body.replace(_FOOT_ANCHOR, nav_block + _FOOT_ANCHOR, 1)
                    elif _GROUP_ANCHOR in body:
                        body = body.replace(_GROUP_ANCHOR, _GROUP_ANCHOR + nav_block, 1)

                # (2) Related strip on the /signals page only — idempotent.
                if p == _SIGNALS_PATH and _REL_MARKER not in body and b"</body>" in body:
                    body = body.replace(b"</body>", rel_strip + b"</body>", 1)

                headers = dict(resp.headers)
                headers.pop("content-length", None)
                return Response(content=body, status_code=resp.status_code,
                                headers=headers, media_type="text/html")
            except Exception:
                return resp

    return _QuantSignalsNavInjector


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    """Attach the idempotent Quant-signals nav injector. ADDITIVE; the SPA
    source is never edited. try/except-guarded by the caller."""
    app.add_middleware(_make_injector())
    return {
        "registered": ["MIDDLEWARE quant-signals-nav injector (s1)"],
        "capability": "Quant Signals nav wire-up",
        "tab_route": _SIGNALS_PATH,
        "data_label": "QUANT-SIGNALS-NAV",
    }


# ---------------------------------------------------------------------------
# Self-test (run: python a11oy_quant_signals_nav.py).
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
    SAMPLE_PAGE = '<html><body><h1>Quant Signals</h1></body></html>'

    async def _console(req):
        return HTMLResponse(SAMPLE_CONSOLE)

    async def _page(req):
        return HTMLResponse(SAMPLE_PAGE)

    app = Starlette(routes=[Route("/console", _console), Route("/signals", _page)])
    st = register(app, ns="a11oy")
    assert st["tab_route"] == "/signals", st
    c = TestClient(app)

    h1 = c.get("/console").text
    h2 = c.get("/console").text
    assert h1 == h2, "console injection must be byte-identical (idempotent)"
    assert h1.count('data-quantsignals-nav="s1"') == 2, "one group + one item marker"
    assert "location.href='/signals'" in h1, "nav must link /signals"
    assert "Existing" in h1 and "Operate</div>" in h1 and "footer</div>" in h1, \
        "must NOT remove existing nav markup"

    w1 = c.get("/signals").text
    w2 = c.get("/signals").text
    assert w1 == w2, "page injection must be idempotent"
    assert w1.count('data-quantsignals-rel="s1"') == 1, "related strip injects exactly once"
    assert "/yupay" in w1 and "/waqay" in w1, "related strip must cross-link governance surfaces"

    inj = (_build_nav_block().decode() + _build_rel_strip().decode()).lower()
    assert "http://" not in inj and "https://" not in inj, "nav markup must be 0-CDN"
    assert "<script" not in inj, "nav markup must inject no script"
    for bad in ("am" + "aru", "ro" + "sie", "sen" + "tra", "jar" + "vis"):
        assert bad not in inj, "no user-visible internal codenames in nav markup"
    print("a11oy_quant_signals_nav: ALL OK — /signals nav item injected once; "
          "idempotent; additive; 0 codenames; 0 CDN")
