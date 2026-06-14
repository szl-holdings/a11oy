# -*- coding: utf-8 -*-
# ===========================================================================
# a11oy_nav_wireup.py — Estate wire-up gap closure (QA10)
# ---------------------------------------------------------------------------
# PROBLEM (QA10): seven integration surfaces are LIVE and serve HTTP 200 but were
# NOT reachable from the /console left-nav:
#     /nemo  /autoreview  /factory  /constitution  /quant  /agent-loop  /energy
# (/grc was already linked by a11oy_grc.py's own injector; /governance served a
# real page but had no nav entry either.) A demo viewer landing on /console could
# not click through to any of them.
#
# FIX (ADDITIVE, idempotent, 0 lines removed from the SPA source): mirror the
# proven a11oy_grc.py / serve.py _OperatorWidgetInjector pattern — a single
# BaseHTTPMiddleware that, on every text/html response, injects:
#   (1) a NEW left-nav group "Sovereign & Agentic Core (NEW)" into the /console
#       page, with one honest, labelled nav-item per missing surface (+ a
#       Governance entry), placed right before the sidebar footer. Keyed by the
#       data-attribute data-nav-wireup="qa10" so re-runs NEVER double-inject and
#       other lanes' nav items are NEVER touched.
#   (2) a lightweight "Related surfaces" cross-link strip into each flagship page
#       (nemo / autoreview / factory / constitution / energy / agent-loop / quant
#       / grc) so the surfaces are cross-linked. Keyed by data-related-surfaces
#       so it is idempotent and additive.
#
# The console SPA source (pages/console.html) is NOT edited. The injector only
# ADDS nav markup; it removes nothing.
#
# DOCTRINE (v11/v12): locked=8 @ c7c0ba17; Λ = Conjecture 1 (NOT a theorem); 0
# visible codenames (labels are the surfaces' own honest titles); 0 CDN (pure
# inline markup, no external assets); honest labels only; never weakens a gate;
# never commits a key; additive-only.
#
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# ===========================================================================
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# The seven surfaces missing from the /console nav, plus Governance (which had a
# live page but no nav entry). Each tuple: (path, icon-glyph, honest label).
# Labels are the surfaces' own public titles — NO codenames.
# ---------------------------------------------------------------------------
_SURFACES = [
    ("/nemo",         "\u25C6", "SZL-Nemo"),                       # ◆
    ("/autoreview",   "\u2713", "Auto-Review (Governed Autonomy)"),  # ✓
    ("/factory",      "\u2699", "Governed Factory"),               # ⚙
    ("/constitution", "\u00A7", "Constitution"),                   # §
    ("/quant",        "\u2211", "Quant Engine"),                   # ∑
    ("/agent-loop",   "\u21BB", "Agent Loop"),                     # ↻
    ("/energy",       "\u26A1", "Energy / Sovereign Compute"),     # ⚡
    ("/governance",   "\u2696", "Governance / Eval / Calibration"),  # ⚖
    # R5: a11oy Restraint (governed code-minimization / dependency-frugality
    # ladder) + its two-arm benchmark. Honest labels; no codenames.
    ("/restraint",       "\u27C2", "Restraint (Governed Frugality)"),  # ⟂ (perp)
    ("/restraint-bench", "\u2696", "Restraint Benchmark"),            # ⚖
]

# Idempotency marker for the nav-group injection.
_NAV_MARKER = b'data-nav-wireup="qa10"'

# Sidebar anchor: the console sidebar ends with <div class="side-foot">…; we place
# the new group immediately before it (so it is the last group in the aside).
_FOOT_ANCHOR = b'<div class="side-foot">'
# Fallbacks if the footer is ever renamed.
_GROUP_ANCHOR = b'<div class="nav-group">'


def _build_nav_block() -> bytes:
    """The new left-nav group. Mirrors the existing nav-item markup verbatim
    (class="nav-item" + <span class="ico"> + label) so it inherits the console's
    own styling — 0 CDN, 0 inline <style>, 0 codenames."""
    items = []
    for path, ico, label in _SURFACES:
        # esc the label defensively even though all labels are static + safe.
        items.append(
            '<div class="nav-item" data-nav-wireup="qa10" data-wireup-path="%s" '
            'onclick="location.href=\'%s\'" style="cursor:pointer">'
            '<span class="ico">%s</span>%s</div>' % (path, path, ico, label)
        )
    block = (
        '<div class="nav-group" data-nav-wireup="qa10">'
        'Sovereign &amp; Agentic Core (NEW)</div>'
        + "".join(items)
    )
    return block.encode("utf-8")


# Idempotency marker for the related-surfaces cross-link strip.
_REL_MARKER = b'data-related-surfaces="qa10"'

# Flagship surfaces that get the cross-link strip + the page each strip is hosted
# on (so we can drop the current page from its own strip).
_FLAGSHIP_PATHS = {
    "/nemo", "/autoreview", "/factory", "/constitution",
    "/energy", "/agent-loop", "/quant", "/grc", "/restraint",  # R5
}


def _build_related_strip(current_path: str) -> bytes:
    """A small 'Related surfaces' strip linking the flagship surfaces to each
    other. Inline-styled (0 CDN). Honest labels; the current page is omitted."""
    links = []
    rel = [
        ("/nemo", "SZL-Nemo"),
        ("/autoreview", "Auto-Review"),
        ("/factory", "Factory"),
        ("/constitution", "Constitution"),
        ("/energy", "Energy"),
        ("/agent-loop", "Agent Loop"),
        ("/quant", "Quant"),
        ("/grc", "GRC"),
        ("/restraint", "Restraint"),  # R5: flagship cluster cross-link
    ]
    for path, label in rel:
        if path == current_path:
            continue
        links.append(
            '<a href="%s" style="color:#d4a444;text-decoration:none;'
            'margin:0 .55em;white-space:nowrap">%s</a>' % (path, label)
        )
    strip = (
        '<nav data-related-surfaces="qa10" aria-label="Related surfaces" '
        'style="margin:1.25rem auto;max-width:1100px;padding:.6rem .9rem;'
        'border-top:1px solid #1d2632;font:13px/1.6 system-ui,sans-serif;'
        'color:#7c8794;text-align:center">'
        '<span style="color:#7c8794;margin-right:.4em">Related surfaces:</span>'
        + "".join(links)
        + "</nav>"
    )
    return strip.encode("utf-8")


def _make_injector():
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response

    nav_block = _build_nav_block()

    class _NavWireupInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            resp = await call_next(request)
            try:
                ct = (resp.headers.get("content-type") or "").lower()
                if "text/html" not in ct:
                    return resp
                p = request.url.path
                # Never touch API / SSE / asset routes.
                if (p.startswith("/api/") or p.startswith("/v1/")
                        or p.startswith("/vendor/") or p.startswith("/assets/")
                        or p.startswith("/static/")):
                    return resp

                body = b""
                async for chunk in resp.body_iterator:
                    body += chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode()

                changed = False

                # (1) Nav-group injection — only on pages that carry the console
                #     sidebar markup. Idempotent via _NAV_MARKER.
                if _NAV_MARKER not in body:
                    if _FOOT_ANCHOR in body:
                        body = body.replace(_FOOT_ANCHOR, nav_block + _FOOT_ANCHOR, 1)
                        changed = True
                    elif _GROUP_ANCHOR in body:
                        # No footer found but a nav exists -> append after the
                        # first nav-group so the new group still lands in the nav.
                        body = body.replace(_GROUP_ANCHOR, _GROUP_ANCHOR + nav_block, 1)
                        changed = True

                # (2) Related-surfaces strip — only on the flagship pages, and
                #     only if not already present. Idempotent via _REL_MARKER.
                if p in _FLAGSHIP_PATHS and _REL_MARKER not in body and b"</body>" in body:
                    body = body.replace(b"</body>", _build_related_strip(p) + b"</body>", 1)
                    changed = True

                # NOTE: body_iterator was fully consumed above, so we MUST
                # rebuild the Response from the buffered bytes even when unchanged.
                # Returning the original (exhausted) resp here emitted an EMPTY body
                # downstream -> white-screen on / and other doc pages.
                headers = dict(resp.headers)
                headers.pop("content-length", None)
                return Response(content=body, status_code=resp.status_code,
                                headers=headers, media_type="text/html")
            except Exception:
                return resp

    return _NavWireupInjector


# R5: where the console web assets live (matches serve.py _PTG_WEB).
_WEB_DIR = "/app/web"
_RESTRAINT_HTML = "restraint.html"


def _register_restraint_bench(app) -> List[str]:
    """R5: register a REAL /restraint-bench route. Previously /restraint-bench only
    fell through to the SPA catch-all; this serves the Restraint page (which hosts
    the two-arm benchmark section, id="bench") directly via FileResponse so the nav
    item resolves to a real 200 document. ADDITIVE + idempotent: if the route is
    already present (re-run / another lane) we do NOT add a duplicate."""
    out: List[str] = []
    try:
        existing = {getattr(r, "path", None) for r in getattr(app, "routes", [])}
        if "/restraint-bench" in existing:
            return ["/restraint-bench already registered (skipped)"]
    except Exception:
        pass
    import os
    from starlette.responses import FileResponse, RedirectResponse

    async def _restraint_bench(request):
        # Serve the Restraint page (it carries the live two-arm benchmark UI). If
        # the asset is missing for any reason, redirect to /restraint rather than
        # 404 — never breaks the nav link.
        fp = os.path.join(_WEB_DIR, _RESTRAINT_HTML)
        if os.path.isfile(fp):
            return FileResponse(fp, media_type="text/html")
        return RedirectResponse(url="/restraint")

    # Insert at position 0 so it resolves BEFORE the SPA/proxy catch-all.
    try:
        from starlette.routing import Route
        app.router.routes.insert(0, Route("/restraint-bench", _restraint_bench, methods=["GET"]))
        out.append("GET /restraint-bench (FileResponse restraint.html)")
    except Exception:
        # Fallback to the standard registration path.
        app.add_api_route("/restraint-bench", _restraint_bench, methods=["GET"])
        out.append("GET /restraint-bench (api_route)")
    return out


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    """Attach the idempotent nav-wireup injector + register the real /restraint-bench
    route (R5). ADDITIVE; the injector only injects honest nav markup into HTML
    responses and removes nothing. try/except-guarded by the caller."""
    registered: List[str] = []
    # R5: ensure /restraint-bench resolves to a real document (was SPA fallback).
    try:
        registered.extend(_register_restraint_bench(app))
    except Exception:
        pass
    app.add_middleware(_make_injector())
    registered.append("MIDDLEWARE nav-wireup injector (QA10)")
    return {
        "registered": registered,
        "count": len(registered),
        "capability": "Nav Wire-Up (QA10)",
        "surfaces": [p for p, _, _ in _SURFACES],
        "data_label": "NAV",
    }


# ---------------------------------------------------------------------------
# Self-test: builds a synthetic console + a flagship page, runs the injector
# twice, asserts the nav group + every surface link appear EXACTLY ONCE, that
# the related strip is idempotent, and that NO original markup was removed.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    SAMPLE_CONSOLE = (
        '<html><body><aside>'
        '<div class="nav-group">Operate</div>'
        '<div class="nav-item" data-view="govern" onclick="go(\'govern\')">'
        '<span class="ico">\u2713</span>Readiness &amp; Compliance</div>'
        '<div class="side-foot">footer</div>'
        '</aside><main>x</main></body></html>'
    )
    SAMPLE_NEMO = '<html><body><h1>SZL-Nemo</h1></body></html>'
    SAMPLE_RESTRAINT = '<html><body><h1>Restraint</h1><div id="bench"></div></body></html>'

    async def _console(req):
        return HTMLResponse(SAMPLE_CONSOLE)

    async def _nemo(req):
        return HTMLResponse(SAMPLE_NEMO)

    async def _restraint(req):
        return HTMLResponse(SAMPLE_RESTRAINT)

    app = Starlette(routes=[Route("/console", _console), Route("/nemo", _nemo),
                            Route("/restraint", _restraint)])
    # R5: /restraint-bench route registration must be idempotent. Exercise the
    # route-registration helper directly twice BEFORE the app starts (add_middleware
    # cannot run after start), so we can assert no duplicate route is added.
    rb_first = _register_restraint_bench(app)
    assert any("/restraint-bench" in r for r in rb_first), rb_first
    rb_second = _register_restraint_bench(app)
    assert any("already registered" in r for r in rb_second), rb_second
    bench_routes = [r for r in app.router.routes if getattr(r, "path", None) == "/restraint-bench"]
    assert len(bench_routes) == 1, "/restraint-bench must be registered exactly once"
    # now attach the injector (register() also calls _register_restraint_bench, which
    # will no-op since the route now exists).
    st = register(app, ns="a11oy")
    assert any("already registered" in r for r in st["registered"]), st["registered"]
    c = TestClient(app)
    # R5: /restraint-bench resolves (FileResponse missing in test -> redirect to /restraint)
    rb = c.get("/restraint-bench")
    assert rb.status_code == 200 and "Restraint" in rb.text, (rb.status_code, rb.text[:120])

    h1 = c.get("/console").text
    h2 = c.get("/console").text  # second hit must be byte-identical (idempotent)
    assert h1.count('data-nav-wireup="qa10"') == h2.count('data-nav-wireup="qa10"'), "nav must be idempotent"
    # one group marker + one marker per surface item == 1 + 8 == 9
    assert h1.count('data-nav-wireup="qa10"') == 1 + len(_SURFACES), "expected group + one item per surface"
    for path, _, _ in _SURFACES:
        assert ("location.href='%s'" % path) in h1, "missing nav link for %s" % path
    assert "Sovereign &amp; Agentic Core (NEW)" in h1, "missing nav group label"
    # additive: original items untouched
    assert "Readiness &amp; Compliance" in h1, "must NOT remove existing nav items"
    assert "Operate</div>" in h1, "must NOT remove existing nav group"
    assert "footer</div>" in h1, "must NOT remove footer"
    assert h1 == h2, "second render must be byte-identical (idempotent)"

    n1 = c.get("/nemo").text
    n2 = c.get("/nemo").text
    assert n1.count('data-related-surfaces="qa10"') == 1, "related strip must inject once"
    assert n2.count('data-related-surfaces="qa10"') == 1, "related strip must be idempotent"
    assert "SZL-Nemo" in n1 and "/autoreview" in n1, "related strip must cross-link surfaces"
    assert "/restraint" in n1, "related strip must cross-link Restraint (R5 flagship cluster)"
    # R5: Restraint appears in the console nav group + the /restraint page gets the strip
    assert "location.href='/restraint'" in h1, "nav must link /restraint"
    assert "location.href='/restraint-bench'" in h1, "nav must link /restraint-bench"
    r1 = c.get("/restraint").text
    assert r1.count('data-related-surfaces="qa10"') == 1, "/restraint is a flagship -> gets cross-link strip"
    assert "/restraint" not in r1.split('data-related-surfaces="qa10"')[1].split("</nav>")[0], \
        "strip must omit current page (/restraint)"
    assert "/nemo" not in n1.split('data-related-surfaces="qa10"')[1].split("</nav>")[0], \
        "related strip must omit the current page (/nemo)"
    assert n1 == n2, "second nemo render must be byte-identical"

    # Doctrine guard: the injected markup must be made of plain ASCII labels +
    # a few named glyphs only (no marketing-prose tokens, no codenames, no CDN).
    # The banned-token list itself is NOT enumerated here so this module never
    # trips the doctrine-grep banned-token gate; the external integration test
    # (qa10/integration_test.py) performs the explicit banned-token assertion.
    injected = (_build_nav_block().decode() + _build_related_strip("/grc").decode()).lower()
    assert "http://" not in injected and "https://" not in injected, "nav markup must be 0-CDN"
    assert "<script" not in injected, "nav markup must inject no script"

    print("a11oy_nav_wireup: ALL OK (nav group + %d surfaces; idempotent; "
          "additive; cross-links; 0 codenames; 0 CDN)" % len(_SURFACES))
