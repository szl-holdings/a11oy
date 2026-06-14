# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# ===========================================================================
# a11oy_willay_nav.py — idempotent nav-injection for the WILLAY tab.
# ---------------------------------------------------------------------------
# Adds ONE honest left-nav item → /willay into the /console SPA, plus a small
# "WILLAY — signed & shown" cross-link strip on the WILLAY page itself. Mirrors
# the proven a11oy_nav_wireup.py BaseHTTPMiddleware pattern EXACTLY:
#   • never rewrites the console SPA source (pages/console.html is NOT edited);
#   • only ADDS markup into text/html responses, removes nothing;
#   • idempotent via the data-willay-nav="w1" marker (re-runs never double-inject);
#   • 0 CDN (pure inline markup, no external assets, no <script>);
#   • 0 user-visible codenames; honest label only.
#
# This is a SEPARATE injector from the QA10 nav-wireup so the two never collide:
# the QA10 injector keys on data-nav-wireup="qa10"; this one keys on
# data-willay-nav="w1". Both can run on the same response harmlessly.
#
# Doctrine: locked=8 @ c7c0ba17 · Λ = Conjecture 1 · additive-only · never weakens a gate.
# Signed-off-by: Stephen P. Lutar Jr. · Co-Authored-By: Perplexity Computer Agent.
# ===========================================================================
from typing import Any, Dict, List

# The single honest nav item. Label is the surface's own title — NO codename.
_WILLAY_PATH = "/willay"
_WILLAY_ICO = "\u25C9"   # ◉  (the disclosing eye / governor shown)
_WILLAY_LABEL = "WILLAY \u2014 Safety Gateway (signed &amp; shown)"

_NAV_MARKER = b'data-willay-nav="w1"'
_REL_MARKER = b'data-willay-rel="w1"'

# Sidebar anchor (same as the QA10 injector): place before the sidebar footer.
_FOOT_ANCHOR = b'<div class="side-foot">'
_GROUP_ANCHOR = b'<div class="nav-group">'


def _build_nav_block() -> bytes:
    """A one-item nav group for WILLAY. Inherits console nav styling (class="nav-item"
    + <span class="ico">). 0 CDN, 0 <style>, 0 <script>, 0 codenames."""
    item = (
        '<div class="nav-item" data-willay-nav="w1" data-willay-path="%s" '
        'onclick="location.href=\'%s\'" style="cursor:pointer">'
        '<span class="ico">%s</span>%s</div>' % (_WILLAY_PATH, _WILLAY_PATH, _WILLAY_ICO, _WILLAY_LABEL)
    )
    block = ('<div class="nav-group" data-willay-nav="w1">Governed Inverse (WILLAY)</div>' + item)
    return block.encode("utf-8")


def _build_rel_strip() -> bytes:
    """A small honest strip on the /willay page linking back to the related
    governance surfaces. Inline-styled (0 CDN)."""
    rel = [("/governance-gateway", "Governance Gateway"), ("/constitution", "Constitution"),
           ("/restraint", "Restraint"), ("/governance", "Governance / Eval")]
    links = "".join(
        '<a href="%s" style="color:#39d8c8;text-decoration:none;margin:0 .55em;'
        'white-space:nowrap">%s</a>' % (p, l) for p, l in rel)
    strip = (
        '<nav data-willay-rel="w1" aria-label="WILLAY related surfaces" '
        'style="margin:1.25rem auto;max-width:1120px;padding:.6rem .9rem;'
        'border-top:1px solid #1c2733;font:13px/1.6 system-ui,sans-serif;'
        'color:#8aa0b4;text-align:center">'
        '<span style="margin-right:.4em">Related governance surfaces:</span>' + links + '</nav>')
    return strip.encode("utf-8")


def _make_injector():
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response

    nav_block = _build_nav_block()
    rel_strip = _build_rel_strip()

    class _WillayNavInjector(BaseHTTPMiddleware):
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

                # (2) Related strip on the /willay page only — idempotent.
                if p == _WILLAY_PATH and _REL_MARKER not in body and b"</body>" in body:
                    body = body.replace(b"</body>", rel_strip + b"</body>", 1)

                headers = dict(resp.headers)
                headers.pop("content-length", None)
                return Response(content=body, status_code=resp.status_code,
                                headers=headers, media_type="text/html")
            except Exception:
                return resp

    return _WillayNavInjector


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    """Attach the idempotent WILLAY nav injector. ADDITIVE; the console SPA source
    is never edited. try/except-guarded by the caller."""
    app.add_middleware(_make_injector())
    return {
        "registered": ["MIDDLEWARE willay-nav injector (w1)"],
        "capability": "WILLAY nav wire-up",
        "tab_route": _WILLAY_PATH,
        "data_label": "WILLAY-NAV",
    }


# ---------------------------------------------------------------------------
# Self-test (run: python a11oy_willay_nav.py) — proves idempotency + additivity.
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
    SAMPLE_WILLAY = '<html><body><h1>WILLAY</h1></body></html>'

    async def _console(req):
        return HTMLResponse(SAMPLE_CONSOLE)

    async def _willay(req):
        return HTMLResponse(SAMPLE_WILLAY)

    app = Starlette(routes=[Route("/console", _console), Route("/willay", _willay)])
    st = register(app, ns="a11oy")
    assert st["tab_route"] == "/willay", st
    c = TestClient(app)

    h1 = c.get("/console").text
    h2 = c.get("/console").text
    assert h1 == h2, "console injection must be byte-identical (idempotent)"
    assert h1.count('data-willay-nav="w1"') == 2, "one group + one item marker"
    assert "location.href='/willay'" in h1, "nav must link /willay"
    assert "Existing" in h1 and "Operate</div>" in h1 and "footer</div>" in h1, \
        "must NOT remove existing nav markup"

    w1 = c.get("/willay").text
    w2 = c.get("/willay").text
    assert w1 == w2, "willay page injection must be idempotent"
    assert w1.count('data-willay-rel="w1"') == 1, "related strip injects exactly once"
    assert "/governance-gateway" in w1, "related strip must cross-link governance surfaces"

    inj = (_build_nav_block().decode() + _build_rel_strip().decode()).lower()
    assert "http://" not in inj and "https://" not in inj, "nav markup must be 0-CDN"
    assert "<script" not in inj, "nav markup must inject no script"
    for bad in ("amaru", "rosie", "sentra", "jarvis"):
        assert bad not in inj, "no user-visible codenames in WILLAY nav markup"
    print("a11oy_willay_nav: ALL OK — /willay nav item injected once; idempotent; "
          "additive; 0 codenames; 0 CDN")
