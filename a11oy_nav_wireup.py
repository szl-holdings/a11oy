# -*- coding: utf-8 -*-
# ===========================================================================
# a11oy_nav_wireup.py — Command-centre nav consolidation (full, real, no stubs)
# ---------------------------------------------------------------------------
# GOAL: every /console left-nav tab opens a REAL, working view backed by real
# data — no dead tabs, no stubs, no static markup that gets wiped. Two proven
# facts drive the design:
#
#   (a) The console rebuilds its ENTIRE left-nav from one JS SPEC array on load
#       (buildNav()): it removes every .nav-group/.nav-item and re-adds only the
#       SPEC entries, then re-applies on a timer + a MutationObserver. So SPEC is
#       the single source of truth; any DOM injected before <div class="side-foot">
#       is wiped within ~1s. (An earlier build injected a static nav group here;
#       that never survived — it was removed. Do NOT reintroduce static-DOM nav.)
#
#   (b) buildNav() renders each SPEC row: a 3-tuple [id,glyph,label] wires
#       onclick=go(id) (an in-app VIEW); a 4-tuple [id,glyph,label,href] wires
#       onclick=location.href=href (a full-page surface). go(id) is a strict
#       no-op for an id absent from the client VIEWS registry — so a 3-tuple for
#       an unregistered id would be a DEAD tab.
#
# THIS MODULE (additive, idempotent, 0 lines removed from the SPA source):
#   1. Splices the command-centre VIEW groups (Verticals / Research / Formulas)
#      into SPEC as 3-tuples. Every id is POSITIVELY confirmed in the VIEWS
#      registry (each renders live data via vertPack / mountNeuro / etc.).
#   2. Splices two 4-tuple PAGE-LINK groups ("Sovereign & Agentic Core" and
#      "Platform & Infrastructure") to the ops surfaces. Every path was probed
#      live and serves a real, dedicated HTTP-200 page (NOT the SPA catch-all
#      shell). Paths that only fell through to the generic orchestration shell
#      (/restraint, /sapa) are deliberately EXCLUDED; the real Restraint page is
#      reached at /restraint-bench instead.
#   3. Repoints the previously-DEAD built-in 'frontier' tab (go('frontier') had
#      no VIEWS entry) to the real /frontier page.
#   4. Injects a small "Related surfaces" cross-link strip into the flagship ops
#      pages so they cross-link each other.
#
# The console SPA source (pages/console.html) is NOT edited; the served HTML
# response is transformed in a BaseHTTPMiddleware. All transforms are idempotent.
#
# DOCTRINE (v11/v12): honest labels only (the surfaces' own public titles; no
# codenames); 0 CDN (pure inline markup, no external assets); never weakens a
# gate; never commits a key; additive-only.
# ===========================================================================
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Ops / agentic surfaces exposed in the command centre as SPEC PAGE-LINKS.
# Each was probed live and returns a real, dedicated HTTP-200 document (verified
# it is NOT the SPA catch-all shell). Each tuple: (path, icon-glyph, honest
# label). Labels are the surfaces' own public titles — NO codenames.
#
# Deliberately NOT listed (would be bandaids — they only fall through to the
# generic orchestration SPA shell, not a dedicated page):
#   /restraint  -> generic shell; the REAL Restraint page is /restraint-bench.
#   /sapa       -> generic shell; no dedicated SAPA page exists.
# ---------------------------------------------------------------------------
_SURFACES = [
    ("/cockpit",        "\u2318",     "Command Cockpit"),                   # ⌘
    ("/nemo",           "\u25C6",     "SZL-Nemo"),                          # ◆
    ("/autoreview",     "\u2713",     "Auto-Review (Governed Autonomy)"),   # ✓
    ("/factory",        "\u2699",     "Governed Factory"),                  # ⚙
    ("/constitution",   "\u00A7",     "Constitution"),                      # §
    ("/quant",          "\u2211",     "Quant Engine"),                      # ∑
    ("/agent-loop",     "\u21BB",     "Agent Loop"),                        # ↻
    ("/energy",         "\u26A1",     "Energy / Sovereign Compute"),        # ⚡
    ("/code",           "\u276F",     "Code \u2014 Orchestration Platform"),# ❯
    ("/fleet-c2",       "\u2316",     "Fleet C2"),                          # ⌖
    ("/living-anatomy", "\u2695",     "Living Anatomy"),                    # ⚕
    ("/governance",     "\u2696",     "Governance / Eval / Calibration"),   # ⚖
    ("/restraint-bench","\u27C2",     "Restraint (Governed Frugality)"),    # ⟂
    ("/materials",      "\u269B",     "Materials \u2014 Verifiable Discovery"),  # ⚛
    ("/dns",            "\U0001F310", "DNS &amp; Subdomains"),              # 🌐
    ("/ayllu",          "\u2641",     "Ayllu Council"),                     # ♁ agent community
]

# ---------------------------------------------------------------------------
# Ops-surface nav groups (T001): consolidate the command centre to 10 total nav
# groups = the 5 built-in console SPEC groups (Operate / Govern / Prove /
# Knowledge / Models & Tools) + the 3 command-centre VIEW groups below + these 2
# ops-surface page-link groups. Membership is by path so _SURFACES stays the flat
# source of truth; every row remains a 4-tuple page-link -> every href reachable.
# ---------------------------------------------------------------------------
_SURFACE_GROUP_ORDER = ["Sovereign & Agentic Core", "Platform & Infrastructure"]
_SURFACE_GROUP_OF = {
    "/cockpit": "Sovereign & Agentic Core",
    "/nemo": "Sovereign & Agentic Core",
    "/autoreview": "Sovereign & Agentic Core",
    "/factory": "Sovereign & Agentic Core",
    "/constitution": "Sovereign & Agentic Core",
    "/agent-loop": "Sovereign & Agentic Core",
    "/code": "Sovereign & Agentic Core",
    "/ayllu": "Sovereign & Agentic Core",
    "/governance": "Sovereign & Agentic Core",
    "/restraint-bench": "Sovereign & Agentic Core",
    "/quant": "Platform & Infrastructure",
    "/energy": "Platform & Infrastructure",
    "/fleet-c2": "Platform & Infrastructure",
    "/living-anatomy": "Platform & Infrastructure",
    "/materials": "Platform & Infrastructure",
    "/dns": "Platform & Infrastructure",
}
_SURFACE_GROUPS = [
    (label, [row for row in _SURFACES if _SURFACE_GROUP_OF.get(row[0]) == label])
    for label in _SURFACE_GROUP_ORDER
]

# ===========================================================================
# Command-centre VIEW groups (in-app views switched by go('id')). ONLY ids
# POSITIVELY confirmed in the client VIEWS registry are wired here (go('X') is a
# strict no-op for an unregistered key -> a dead tab). Each renders live data.
# ---------------------------------------------------------------------------
_SPEC_MARKER = b"qa12-nav"

# The SPEC array closes with "]]\n  ];\n\n  function buildNav(){" (the final
# "]]" closes the last built-in group; "function buildNav(){" is unique). We
# splice our groups in after that final "]]" and before the "];".
_SPEC_ANCHOR = b"]]\n  ];\n\n  function buildNav(){"

# (viewid, icon-glyph, honest label) — all rendered as 3-tuples -> go(viewid).
_VIEW_GROUPS = [
    ("Verticals", [
        ("vfinance",    "\u25B3", "Finance"),
        ("vrealestate", "\u25E9", "Real Estate"),
        ("vcyber",      "\u2726", "Cyber Resilience"),
        ("vdefense",    "\u26EF", "Defense / Gov"),
        ("vlegal",      "\u2696", "Legal Matter"),
    ]),
    ("Research (Experimental)", [
        ("neuro",       "\u25D0", "Neuroplasticity"),
        ("sovereignty", "\u2691", "Sovereignty (Allodial)"),
        ("allodialai",  "\u27D0", "Allodial AI"),
        ("l6chain",     "\u2263", "Chain of Title"),
        ("entangle",    "\u221E", "Entanglement"),
        ("scaling",     "\u2922", "Metabolic Scaling"),
    ]),
    ("Formulas & Capability", [
        ("atlas",       "\u2733", "Formula Atlas"),
        ("capfsm",      "\u25F0", "Capability FSM"),
        ("receiptfp",   "\u25C9", "Receipt Fingerprint"),
    ]),
]

# Frontier fix: the built-in 'frontier' tab was a 3-tuple -> go('frontier'),
# but no VIEWS['frontier'] exists, so it was a dead no-op. /frontier serves a
# real page, so repoint it to a 4-tuple page-link. Byte-exact anchor (the source
# ships the glyph as the literal escape \u25c8).
_FRONTIER_OLD = b'["frontier","\\u25c8","Frontier Pipeline"]'
_FRONTIER_NEW = b'["frontier","\\u25c8","SZL Frontier","/frontier"]'


def _js_str(s: str) -> str:
    """Emit a JS double-quoted string literal, escaping non-ASCII as \\uXXXX
    (astral chars > U+FFFF as a UTF-16 surrogate pair) so the fragment matches
    the console's own SPEC style and the injected bytes stay pure-ASCII."""
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif 32 <= o < 127:
            out.append(ch)
        elif o <= 0xFFFF:
            out.append("\\u%04x" % o)
        else:  # astral plane -> UTF-16 surrogate pair
            o -= 0x10000
            out.append("\\u%04x\\u%04x" % (0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF)))
    out.append('"')
    return "".join(out)


def _build_spec_groups_js() -> bytes:
    """Build the JS SPEC-array fragment for the restored command-centre groups.
    View groups emit 3-tuples ([id,glyph,label] -> go(id)); the ops-surface
    group emits 4-tuples ([id,glyph,label,href] -> location.href=href), exactly
    like the console's own willay/verify/assurance page-links. The prefix comma
    + marker comment splice the groups in after the last built-in SPEC group.
    0 CDN, 0 <script>, 0 codenames (labels are the surfaces' honest titles)."""
    groups_js: List[str] = []
    # (1) in-app VIEW groups -> 3-tuples
    for group_label, items in _VIEW_GROUPS:
        rows = ["      [%s,%s,%s]" % (_js_str(v), _js_str(i), _js_str(l))
                for v, i, l in items]
        groups_js.append("    [%s, [\n%s\n    ]]"
                         % (_js_str(group_label), ",\n".join(rows)))
    # (2) ops-surface PAGE-LINK groups -> 4-tuples (id derived from the path)
    for group_label, items in _SURFACE_GROUPS:
        prows = ["      [%s,%s,%s,%s]"
                 % (_js_str(path.lstrip("/")), _js_str(ico), _js_str(label), _js_str(path))
                 for path, ico, label in items]
        groups_js.append("    [%s, [\n%s\n    ]]"
                         % (_js_str(group_label), ",\n".join(prows)))
    frag = (",\n    /* qa12-nav: command-centre view-tabs + ops surfaces restored into SPEC */\n"
            + ",\n".join(groups_js))
    return frag.encode("utf-8")


# Idempotency marker for the related-surfaces cross-link strip.
_REL_MARKER = b'data-related-surfaces="qa10"'

# Flagship surfaces that get the cross-link strip. /restraint-bench (the REAL
# Restraint page) is used, not /restraint (generic shell fallthrough).
_FLAGSHIP_PATHS = {
    "/nemo", "/autoreview", "/factory", "/constitution",
    "/energy", "/agent-loop", "/quant", "/grc", "/restraint-bench",
    "/code", "/fleet-c2", "/living-anatomy",
}


def _build_related_strip(current_path: str) -> bytes:
    """A small 'Related surfaces' strip linking the flagship surfaces to each
    other. Inline-styled (0 CDN). Honest labels; the current page is omitted."""
    rel = [
        ("/nemo", "SZL-Nemo"),
        ("/autoreview", "Auto-Review"),
        ("/factory", "Factory"),
        ("/constitution", "Constitution"),
        ("/energy", "Energy"),
        ("/agent-loop", "Agent Loop"),
        ("/quant", "Quant"),
        ("/grc", "GRC"),
        ("/restraint-bench", "Restraint"),
        ("/code", "Code"),
        ("/fleet-c2", "Fleet C2"),
        ("/living-anatomy", "Living Anatomy"),
    ]
    links = []
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

    spec_groups_js = _build_spec_groups_js()

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

                # (1) Splice the command-centre view-tabs + ops-surface page-links
                #     into the SPA's SPEC array so buildNav() renders them natively
                #     and they survive its nav rebuild + MutationObserver (static
                #     DOM does not). Idempotent via _SPEC_MARKER.
                if _SPEC_MARKER not in body and _SPEC_ANCHOR in body:
                    body = body.replace(
                        _SPEC_ANCHOR,
                        b"]]" + spec_groups_js + b"\n  ];\n\n  function buildNav(){",
                        1,
                    )

                # (2) Repoint the previously-dead 'frontier' built-in tab to the
                #     real /frontier page. Naturally idempotent (the old 3-tuple is
                #     gone after the replace; the source re-supplies it each request).
                if _FRONTIER_OLD in body:
                    body = body.replace(_FRONTIER_OLD, _FRONTIER_NEW, 1)

                # (3) Related-surfaces cross-link strip on flagship pages. Idempotent.
                if p in _FLAGSHIP_PATHS and _REL_MARKER not in body and b"</body>" in body:
                    body = body.replace(b"</body>", _build_related_strip(p) + b"</body>", 1)

                # body_iterator was fully consumed above, so we MUST rebuild the
                # Response from the buffered bytes even when unchanged. Returning
                # the original (exhausted) resp would emit an EMPTY body -> white
                # screen on doc pages.
                headers = dict(resp.headers)
                headers.pop("content-length", None)
                return Response(content=body, status_code=resp.status_code,
                                headers=headers, media_type="text/html")
            except Exception:
                return resp

    return _NavWireupInjector


# Where the console web assets live (matches serve.py _PTG_WEB).
_WEB_DIR = "/app/web"
_RESTRAINT_HTML = "restraint.html"


def _register_restraint_bench(app) -> List[str]:
    """Register a REAL /restraint-bench route serving the Restraint page (which
    hosts the frugality content + the two-arm benchmark, id="bench") directly via
    FileResponse, so the nav item resolves to a real 200 document instead of the
    SPA catch-all. ADDITIVE + idempotent: skip if the route already exists."""
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
        fp = os.path.join(_WEB_DIR, _RESTRAINT_HTML)
        if os.path.isfile(fp):
            return FileResponse(fp, media_type="text/html")
        return RedirectResponse(url="/restraint")

    try:
        from starlette.routing import Route
        app.router.routes.insert(0, Route("/restraint-bench", _restraint_bench, methods=["GET"]))
        out.append("GET /restraint-bench (FileResponse restraint.html)")
    except Exception:
        app.add_api_route("/restraint-bench", _restraint_bench, methods=["GET"])
        out.append("GET /restraint-bench (api_route)")
    return out


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    """Attach the idempotent nav-wireup injector + register the real
    /restraint-bench route. ADDITIVE; the injector only transforms HTML responses
    (SPEC splice + frontier repoint + cross-link strip) and removes nothing."""
    registered: List[str] = []
    try:
        registered.extend(_register_restraint_bench(app))
    except Exception:
        pass
    app.add_middleware(_make_injector())
    registered.append("MIDDLEWARE nav-wireup injector (SPEC view-tabs + ops page-links + frontier fix)")
    return {
        "registered": registered,
        "count": len(registered),
        "capability": "Command-centre nav consolidation (real views + ops surfaces)",
        "surfaces": [p for p, _, _ in _SURFACES],
        "views": [v for _, items in _VIEW_GROUPS for v, _, _ in items],
        "data_label": "NAV",
    }


# ---------------------------------------------------------------------------
# Self-test: builds a synthetic console + a flagship page, runs the injector
# twice, and asserts: SPEC view-tabs + ops page-links spliced once (idempotent),
# the dead 'frontier' tab repointed to /frontier, the cross-link strip is
# idempotent + omits the current page, native SPEC/buildNav + original markup
# untouched, and no CDN / no <script> injected.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    SAMPLE_CONSOLE = (
        '<html><body><aside class="side">'
        '<div class="brand">brand</div>'
        '<div class="nav-group">Operate</div>'
        '<div class="nav-item" data-view="govern" onclick="go(\'govern\')">'
        '<span class="ico">\u2713</span>Readiness &amp; Compliance</div>'
        '<div class="side-foot">footer</div>'
        '</aside>'
        # Minimal SPEC + buildNav mirroring the real console so the SPEC splice
        # and the frontier repoint are exercised. The closing
        # "]]\\n  ];\\n\\n  function buildNav(){" is byte-identical to _SPEC_ANCHOR.
        '<script>\n'
        '  var SPEC = [\n'
        '    ["Prove", [\n'
        '      ["arena","\\u229c","Eval Arena"],\n'
        '      ["frontier","\\u25c8","Frontier Pipeline"]\n'
        '    ]],\n'
        '    ["Models & Tools", [\n'
        '      ["mcp","\\u2699","Agent Tools"]\n'
        '    ]]\n'
        '  ];\n'
        '\n'
        '  function buildNav(){ return SPEC; }\n'
        '</script>'
        '<main>x</main></body></html>'
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
    # /restraint-bench route registration must be idempotent.
    rb_first = _register_restraint_bench(app)
    assert any("/restraint-bench" in r for r in rb_first), rb_first
    rb_second = _register_restraint_bench(app)
    assert any("already registered" in r for r in rb_second), rb_second
    bench_routes = [r for r in app.router.routes if getattr(r, "path", None) == "/restraint-bench"]
    assert len(bench_routes) == 1, "/restraint-bench must be registered exactly once"
    st = register(app, ns="a11oy")
    assert any("already registered" in r for r in st["registered"]), st["registered"]
    c = TestClient(app)
    # /restraint-bench resolves (FileResponse missing in test -> redirect to /restraint)
    rb = c.get("/restraint-bench")
    assert rb.status_code == 200 and "Restraint" in rb.text, (rb.status_code, rb.text[:120])

    h1 = c.get("/console").text
    h2 = c.get("/console").text  # second hit must be byte-identical (idempotent)

    # --- SPEC splice: exactly once, idempotent ---
    assert h1.count("qa12-nav") == 1, "SPEC groups must be spliced in exactly once"
    assert h1.count("qa12-nav") == h2.count("qa12-nav"), "SPEC splice must be idempotent"

    # --- every VIEW group + 3-tuple tab present ---
    for group_label, items in _VIEW_GROUPS:
        assert ("[%s, [" % _js_str(group_label)) in h1, "missing SPEC group %s" % group_label
        for viewid, _ico, _label in items:
            assert ("[%s," % _js_str(viewid)) in h1, "missing SPEC tab %s" % viewid
    assert "Neuroplasticity" in h1 and "Allodial AI" in h1 and "Chain of Title" in h1, \
        "expected honest view labels present"

    # --- ops-surface PAGE-LINK groups: every surface present as a real href 4-tuple ---
    for _grp_label, _grp_items in _SURFACE_GROUPS:
        assert ("[%s, [" % _js_str(_grp_label)) in h1, \
            "missing ops-surface group %s" % _grp_label
        for path, _ico, _label in _grp_items:
            assert (_js_str(path)) in h1, "missing ops page-link href %s" % path
    # every surface still lands in exactly one group (reachability preserved)
    assert sum(len(i) for _, i in _SURFACE_GROUPS) == len(_SURFACES), \
        "every ops surface must belong to exactly one nav group"
    # --- 10-group consolidation: 5 built-in console SPEC groups + spliced groups ---
    _BUILTIN_SPEC_GROUPS = 5  # Operate, Govern, Prove, Knowledge, Models & Tools
    _spliced_groups = len(_VIEW_GROUPS) + len(_SURFACE_GROUPS)
    assert _BUILTIN_SPEC_GROUPS + _spliced_groups == 10, \
        "nav must consolidate to 10 groups (5 built-in + %d spliced)" % _spliced_groups
    # excluded bandaid paths must NOT be wired
    assert '"/sapa"' not in h1, "/sapa (no real page) must not be wired"
    assert '"/restraint"]' not in h1 and '"/restraint",' not in h1, \
        "/restraint (generic shell fallthrough) must not be wired"

    # --- dead 'frontier' tab repointed to the real /frontier page ---
    assert '["frontier","\\u25c8","SZL Frontier","/frontier"]' in h1, \
        "frontier must repoint to the real /frontier page"
    assert '["frontier","\\u25c8","Frontier Pipeline"]' not in h1, \
        "the dead frontier 3-tuple must be gone"

    # --- native SPEC + buildNav + original markup intact ---
    assert "function buildNav(){" in h1, "buildNav must remain intact"
    assert '["mcp","\\u2699","Agent Tools"]' in h1, "native SPEC group must be preserved"
    assert "Readiness &amp; Compliance" in h1, "must NOT remove existing nav items"
    assert "Operate</div>" in h1, "must NOT remove existing nav group"
    assert "footer</div>" in h1, "must NOT remove footer"
    assert h1 == h2, "second render must be byte-identical (idempotent)"

    # --- related-surfaces cross-link strip (flagship page) ---
    n1 = c.get("/nemo").text
    n2 = c.get("/nemo").text
    assert n1.count('data-related-surfaces="qa10"') == 1, "related strip must inject once"
    assert n2.count('data-related-surfaces="qa10"') == 1, "related strip must be idempotent"
    assert "Auto-Review" in n1 and "/autoreview" in n1, "strip must cross-link surfaces"
    assert "/restraint-bench" in n1, "strip must cross-link the real Restraint page"
    assert "/nemo" not in n1.split('data-related-surfaces="qa10"')[1].split("</nav>")[0], \
        "related strip must omit the current page (/nemo)"
    assert n1 == n2, "second nemo render must be byte-identical"

    # --- doctrine guard: injected markup is 0-CDN + injects no <script> ---
    injected = (_build_spec_groups_js().decode()
                + _build_related_strip("/grc").decode()).lower()
    assert "http://" not in injected and "https://" not in injected, "nav markup must be 0-CDN"
    assert "<script" not in injected, "nav markup must inject no script"

    _view_items = sum(len(items) for _, items in _VIEW_GROUPS)
    _surface_items = sum(len(items) for _, items in _SURFACE_GROUPS)
    print("a11oy_nav_wireup: ALL OK (%d SPEC view-tabs in %d groups; %d ops page-links "
          "in %d groups; 10 nav groups total with the 5 built-in console groups; "
          "frontier repointed; idempotent; additive; cross-links; 0 codenames; 0 CDN)"
          % (_view_items, len(_VIEW_GROUPS), _surface_items, len(_SURFACE_GROUPS)))
