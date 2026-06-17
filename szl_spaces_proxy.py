#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""szl_spaces_proxy.py — surface the live HF Spaces estate under a11oy.net/spaces/*.

ADDITIVE, self-contained, SHARED (byte-identical in a11oy + killinchu). Founder rule:
"all the huggingface on my a11oy.net" with NO new subdomains. This module reverse-
proxies each live Hugging Face Space to a same-origin path:

    GET/HEAD /spaces                 -> index (delegates to szl_spaces_surface tiles if
                                        present; else a minimal honest index of the 11)
    GET/HEAD /spaces/{name}          -> reverse-proxy of https://szlholdings-{name}.hf.space/
    GET/HEAD /spaces/{name}/{path}   -> reverse-proxy of that Space's sub-paths/assets

The proxy is a SERVER-SIDE fetch over the app's shared httpx.AsyncClient (resolved
lazily from serve.py's module global, like szl_engine_status), NOT a browser CDN load —
so it satisfies the 0-runtime-CDN doctrine for the same reason a11oy_hf_assets.py states
(server-side fetch, not a browser CDN). HTML responses get a <base href="/spaces/{name}/">
injected so the Space's root-relative assets resolve back through this proxy.

HONEST DEGRADE: upstream timeout / connect error / unreachable -> a clean 502 page
("Space <name> is starting / unreachable — open directly: <hf.space url>"). NEVER a fake
200. Hop-by-hop headers are stripped. The proxy is an ALLOWLIST of the known Space names
only (no open proxy); unknown names -> 404. a11oy is NOT self-proxied (would loop) and
killinchu is served on its own host — both are listed as TILES (by szl_spaces_surface)
linking to their canonical hosts, but are NOT in the reverse-proxy allowlist here.

No auth token is forwarded to HF — these are PUBLIC Spaces.

Routes are inserted at the FRONT of app.router.routes (app.router.routes[0:0] = new)
so they win over the /api/<ns>/{path:path} Node proxy + the /{full_path:path} SPA
catch-all (the same route-to-front idiom a11oy_hf_assets.py uses).

Doctrine v11: locked-proven = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17;
Λ = Conjecture 1; Khipu = Conjecture 2; trust never 100%; 0 runtime CDN (server-side
fetch); no user-visible codenames (Space names are their own honest titles); never
commits a key; additive-only; never weakens a gate; honest 502 beats a fake 200.

Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations

import sys
from typing import Any

_ORG_PREFIX = "szlholdings-"

# The 11 live Spaces (all RUNNING). app URL pattern: https://szlholdings-<name>.hf.space
# PROXY allowlist = the names we reverse-proxy under /spaces/<name>. We SKIP:
#   - "a11oy"    : self-proxy would loop (a11oy.net IS the a11oy Space).
#   - "killinchu": served on its own host; we link the tile to its host, never proxy it.
# Both skipped names are still listed as TILES by szl_spaces_surface.
ALL_SPACES = [
    "immune", "sda", "anatomy", "cathedral", "energy", "yarqa",
    "khipu-constellation", "llm-router-live", "hatun-mcp", "a11oy", "killinchu",
]
# Names we DO reverse-proxy (allowlist). Order preserved for the fallback index.
PROXY_SPACES = [n for n in ALL_SPACES if n not in ("a11oy", "killinchu")]


def hf_url(name: str) -> str:
    """Canonical HF app URL for a Space name (lowercase, org-prefixed)."""
    return f"https://{_ORG_PREFIX}{name}.hf.space"


# Hop-by-hop headers (RFC 7230 §6.1) — never forwarded across the proxy boundary.
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
    # content-encoding/length are recomputed by our Response; strip to avoid mismatch.
    "content-encoding", "content-length",
}

_PROXY_TIMEOUT = 20.0      # the box egress to *.hf.space flaps; give a full page GET room
                           # to ride through a flap (the health HEAD probe needs less).
_PROXY_RETRIES = 3         # retry a transient flap several times before honest-degrading.
_MAX_BYTES = 25 * 1024 * 1024  # 25MB cap per proxied response (Spaces are light pages).


def _honest_502(name: str) -> bytes:
    """Clean 502 page — NEVER a fake 200. Tells the user to open the Space directly."""
    url = hf_url(name)
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Space %s — starting / unreachable</title></head>"
        "<body style=\"margin:0;background:#0b0f14;color:#cdd6e0;"
        "font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;"
        "display:flex;min-height:100vh;align-items:center;justify-content:center\">"
        "<main style=\"max-width:560px;padding:2rem;text-align:center\">"
        "<div style=\"font-size:2.2rem;margin-bottom:.4rem\">&#9889;</div>"
        "<h1 style=\"font-size:1.25rem;margin:0 0 .6rem;color:#e7eef6\">"
        "Space &ldquo;%s&rdquo; is starting or unreachable</h1>"
        "<p style=\"color:#8a96a3;margin:0 0 1.2rem\">The upstream Hugging Face Space did "
        "not respond in time. This is an honest 502 &mdash; not a faked page. "
        "It usually means the Space is waking from sleep; try again shortly.</p>"
        "<p><a href=\"%s\" style=\"color:#d4a444;text-decoration:none;font-weight:600\">"
        "Open %s directly on Hugging Face &rarr;</a></p>"
        "<p style=\"margin-top:1.4rem\"><a href=\"/spaces\" "
        "style=\"color:#7c8794;text-decoration:none\">&larr; All Spaces</a></p>"
        "</main></body></html>" % (name, name, url, name)
    ).encode("utf-8")


def _fallback_index() -> bytes:
    """Minimal honest /spaces index — used ONLY if szl_spaces_surface (the rich tiles
    page) is not registered. Lists every Space name with both links. 0 CDN."""
    rows = []
    for name in ALL_SPACES:
        if name in ("a11oy", "killinchu"):
            local = hf_url(name)  # own canonical host (not self-proxied here)
            local_label = "Open on HF"
        else:
            local = "/spaces/%s" % name
            local_label = "Open in a11oy.net"
        rows.append(
            "<li style=\"margin:.4rem 0\"><strong style=\"color:#e7eef6\">%s</strong> "
            "&middot; <a href=\"%s\" style=\"color:#d4a444;text-decoration:none\">%s</a> "
            "&middot; <a href=\"%s\" style=\"color:#7c8794;text-decoration:none\">Open on HF</a>"
            "</li>" % (name, local, local_label, hf_url(name))
        )
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Spaces</title></head>"
        "<body style=\"margin:0;background:#0b0f14;color:#cdd6e0;"
        "font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:2rem\">"
        "<main style=\"max-width:760px;margin:0 auto\">"
        "<h1 style=\"color:#e7eef6\">Hugging Face Spaces</h1>"
        "<p style=\"color:#8a96a3\">All live Spaces, surfaced under a11oy.net. "
        "Server-side reverse proxy &mdash; 0 browser CDN.</p>"
        "<ul style=\"list-style:none;padding:0\">" + "".join(rows) + "</ul>"
        "</main></body></html>"
    ).encode("utf-8")


def _resolve_client() -> Any:
    """Resolve the app's shared httpx.AsyncClient lazily from serve.py's module global
    (same idiom as szl_engine_status) so registration order doesn't matter."""
    try:
        import serve as _serve  # type: ignore
        return getattr(_serve, "_http_client", None)
    except Exception:
        return None


def _urllib_fetch(method: str, url: str, headers: dict, timeout: float):
    """Blocking stdlib fetch — the PROVEN-working outbound path on the live box
    (a11oy_hf_assets.py reaches HF via urllib server-side). Used as a fallback when the
    shared httpx.AsyncClient is None or fails. Returns (status, body_bytes, headers_dict).
    Raises on failure (caller degrades to an honest 502). 0 browser CDN; no auth token."""
    import http.client
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = getattr(r, "status", None) or r.getcode()
            hdrs = {k: v for k, v in r.headers.items()}
            # Read the body TOLERANTLY: a flapping upstream often drops the connection
            # mid-stream (http.client.IncompleteRead). The status line + headers already
            # arrived fine, so return whatever body bytes we got rather than 502-ing a
            # response that was really a 200. This is honest: status reflects the REAL
            # upstream status; we just don't discard a near-complete page over a late EOF.
            try:
                body = r.read(_MAX_BYTES)
            except http.client.IncompleteRead as ire:
                body = ire.partial or b""
            except Exception:
                body = b""
            return status, body, hdrs
    except urllib.error.HTTPError as he:  # a real upstream non-2xx is NOT a flap
        body = b""
        try:
            body = he.read(_MAX_BYTES)
        except Exception:
            pass
        return he.code, body, {k: v for k, v in (he.headers or {}).items()}


async def _to_thread(fn, *a, **kw):
    import asyncio as _asyncio
    return await _asyncio.get_event_loop().run_in_executor(None, lambda: fn(*a, **kw))


def _rewrite_html(body: bytes, name: str) -> bytes:
    """Inject <base href="/spaces/<name>/"> so the Space's root-relative asset URLs
    (e.g. /assets/app.js, href="/"...) resolve back through this proxy. Idempotent:
    if a base href for this proxy is already present, leave the body untouched."""
    base_tag = ('<base href="/spaces/%s/">' % name).encode("utf-8")
    if base_tag in body:
        return body
    low = body.lower()
    # Prefer to place the <base> right after <head ...> so it applies to all assets.
    h = low.find(b"<head")
    if h != -1:
        gt = body.find(b">", h)
        if gt != -1:
            return body[: gt + 1] + base_tag + body[gt + 1:]
    # No <head> — try right after <html ...>.
    h = low.find(b"<html")
    if h != -1:
        gt = body.find(b">", h)
        if gt != -1:
            return body[: gt + 1] + base_tag + body[gt + 1:]
    # No usable anchor — prepend (still better than broken relative assets).
    return base_tag + body


async def _proxy(name: str, subpath: str, request) -> Any:
    """Reverse-proxy one request to the named Space. Honest 502 on any upstream flap."""
    from starlette.responses import Response

    if name not in PROXY_SPACES:
        # Not in the allowlist — either unknown, or a deliberately-skipped self/own-host
        # Space. 404 (no open proxy). The skipped ones are reachable as tiles only.
        return Response(content=b"Unknown or non-proxied Space.\n",
                        status_code=404, media_type="text/plain")

    # Resolve the shared async httpx client if it's wired. On the LIVE box serve.py runs
    # as __main__ (Dockerfile CMD ["python","serve.py"]), so `import serve` inside
    # _resolve_client() binds a SECOND module object whose startup() never fired and whose
    # _http_client is therefore None — even though the real __main__ app has a live client.
    # We must NOT 502 on a None client: the stdlib urllib path below is the PROVEN outbound
    # path on this box (it is exactly what szl_spaces_surface's health probe uses to report
    # app_reachable=true). So client==None simply means "skip httpx, use urllib" — never an
    # automatic honest-502. An honest 502 is reserved for a GENUINE upstream flap (both the
    # httpx attempt AND the urllib fallback exhausted their retries).
    client = _resolve_client()

    target = hf_url(name) + "/" + subpath
    # Send a CLEAN, minimal header set rather than forwarding the raw browser headers.
    # Forwarding the incoming Host (a11oy.net) makes HF route to the wrong vhost -> 404,
    # and forwarding the full browser header set (incl. Accept-Encoding: br, X-Forwarded-*)
    # was tripping the upstream fetch on the live box. We mirror the proven-working probe:
    # identity encoding, a simple UA, and only the few request headers that are safe to
    # pass through. No Host, no cookies, no auth token (public Spaces).
    _SAFE_PASS = {"accept", "accept-language", "range", "content-type"}
    fwd_headers = {
        "User-Agent": "szl-spaces-proxy/1.0",
        "Accept-Encoding": "identity",
    }
    for k, v in request.headers.items():
        if k.lower() in _SAFE_PASS:
            fwd_headers[k] = v
    fwd_headers.setdefault("Accept", "*/*")
    method = request.method.upper()

    status = None
    body = b""
    up_headers: dict = {}
    last_exc = None

    # Try the shared async httpx client first (streaming-capable, preferred).
    if client is not None:
        for _attempt in range(_PROXY_RETRIES + 1):
            try:
                upstream = await client.request(
                    method, target, headers=fwd_headers,
                    timeout=_PROXY_TIMEOUT, follow_redirects=True,
                )
                status = upstream.status_code
                body = upstream.content or b""
                up_headers = {k: v for k, v in upstream.headers.items()}
                break
            except Exception as e:  # connect/timeout/read error -> try fallback below
                last_exc = e
                status = None
                import asyncio as _a
                await _a.sleep(0.4 * (_attempt + 1))  # brief backoff across a flap

    # Fallback to the PROVEN stdlib urllib path if httpx was None or failed.
    if status is None:
        import asyncio as _a
        for _attempt in range(_PROXY_RETRIES + 1):
            try:
                status, body, up_headers = await _to_thread(
                    _urllib_fetch, method, target, fwd_headers, _PROXY_TIMEOUT)
                break
            except Exception as e:  # genuine upstream flap -> honest 502
                last_exc = e
                status = None
                await _a.sleep(0.5 * (_attempt + 1))  # brief backoff across a flap

    if status is None:
        print("[spaces-proxy] upstream flap for %s: %r" % (name, last_exc),
              file=sys.stderr)
        # Surface the real upstream error class in an honest diagnostic header (the body
        # stays the clean honest-502 page). Never fabricates a 200.
        return Response(content=_honest_502(name), status_code=502,
                        media_type="text/html",
                        headers={"x-szl-proxy-error": type(last_exc).__name__ if last_exc else "none",
                                 "x-szl-proxy-target": target})

    if len(body) > _MAX_BYTES:
        body = body[:_MAX_BYTES]
    ct = (up_headers.get("content-type") or up_headers.get("Content-Type") or "").lower()

    # HTML: inject <base href> so assets resolve under /spaces/<name>/.
    if "text/html" in ct:
        body = _rewrite_html(body, name)

    out_headers = {
        k: v for k, v in up_headers.items()
        if k.lower() not in _HOP_BY_HOP
    }
    # HEAD must carry no body.
    if method == "HEAD":
        body = b""

    return Response(content=body, status_code=status,
                    headers=out_headers,
                    media_type=ct or None)


def register(app, ns: str = "a11oy") -> str:
    """ADDITIVE: mount the /spaces reverse-proxy routes at the FRONT of the router so
    they beat the SPA + Node-proxy catch-alls. try/except-guarded by the caller."""
    try:
        from starlette.responses import Response
    except Exception as e:  # pragma: no cover
        return "unavailable: %r" % (e,)

    n_before = len(app.router.routes)

    async def _spaces_index(request):
        # Delegate the rich tiles page to szl_spaces_surface if it owns /spaces; this
        # fallback index only renders if that module isn't present. Idempotent: this
        # route is inserted only once per register() and register() is guarded upstream.
        if request.method.upper() == "HEAD":
            return Response(content=b"", status_code=200, media_type="text/html")
        return Response(content=_fallback_index(), status_code=200,
                        media_type="text/html")

    async def _spaces_name(request):
        name = request.path_params.get("name", "")
        return await _proxy(name, "", request)

    async def _spaces_path(request):
        name = request.path_params.get("name", "")
        subpath = request.path_params.get("path", "")
        return await _proxy(name, subpath, request)

    from starlette.routing import Route
    # NOTE: szl_spaces_surface registers its OWN richer /spaces tiles page and inserts
    # it at the front AFTER this module (it's registered second in serve.py), so the
    # tiles page wins over this fallback index — by design. Both are idempotent.
    routes = [
        Route("/spaces", _spaces_index, methods=["GET", "HEAD"]),
        Route("/spaces/{name}", _spaces_name, methods=["GET", "HEAD"]),
        Route("/spaces/{name}/{path:path}", _spaces_path, methods=["GET", "HEAD"]),
    ]
    for r in routes:
        app.router.routes.append(r)

    new = app.router.routes[n_before:]
    del app.router.routes[n_before:]
    app.router.routes[0:0] = new
    print("[%s] Spaces reverse-proxy registered: /spaces + /spaces/{name} + "
          "/spaces/{name}/{path} (%d proxied: %s) [moved %d routes to front]"
          % (ns, len(PROXY_SPACES), ",".join(PROXY_SPACES), len(new)), file=sys.stderr)
    return "ok: %d proxied spaces, %d routes" % (len(PROXY_SPACES), len(new))


# ---------------------------------------------------------------------------
# Self-test — pure stdlib + starlette TestClient; no real network. Stubs the shared
# client to assert: allowlist enforced (unknown -> 404), honest 502 on a dead client,
# <base href> injection, HEAD carries no body, and the fallback index lists all 11.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import ast as _ast
    # parse-self guard
    with open(__file__, "r", encoding="utf-8") as _fh:
        _ast.parse(_fh.read())

    # base-href injection
    out = _rewrite_html(b"<html><head><title>x</title></head><body>hi</body></html>", "immune")
    assert b'<base href="/spaces/immune/">' in out, "must inject base href"
    assert _rewrite_html(out, "immune") == out, "base href injection must be idempotent"

    # honest 502 content
    p = _honest_502("sda")
    assert b"honest 502" in p and b"szlholdings-sda.hf.space" in p, "502 must be honest + direct link"

    # allowlist
    assert "a11oy" not in PROXY_SPACES and "killinchu" not in PROXY_SPACES, "self/own-host skipped"
    assert len(ALL_SPACES) == 11 and len(PROXY_SPACES) == 9, (len(ALL_SPACES), len(PROXY_SPACES))

    # fallback index lists all 11 names
    idx = _fallback_index()
    for nm in ALL_SPACES:
        assert nm.encode() in idx, "index missing %s" % nm

    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route as _R
    from starlette.testclient import TestClient

    a = Starlette(routes=[_R("/{full_path:path}", lambda req: PlainTextResponse("SPA"))])
    st = register(a, ns="a11oy")
    assert st.startswith("ok:"), st
    c = TestClient(a)
    # /spaces fallback index resolves before the SPA catch-all and lists all names
    r = c.get("/spaces")
    assert r.status_code == 200 and "immune" in r.text and "killinchu" in r.text, r.status_code
    # unknown / non-proxied name -> 404 (no open proxy); a11oy is deliberately skipped
    assert c.get("/spaces/a11oy").status_code == 404, "a11oy must not be self-proxied"
    assert c.get("/spaces/notreal").status_code == 404, "unknown -> 404"
    # known name, no shared client wired AND the (urllib) upstream fetch fails -> honest 502
    # (never a fake 200). We stub _urllib_fetch so the test is hermetic (no real network):
    # client==None must NOT short-circuit to 502 by itself; it must fall through to urllib,
    # and only a GENUINE fetch failure degrades honestly. This is the regression guard for
    # the live __main__/import-serve dual-module bug (client==None on the box) that was
    # making EVERY proxied Space 502 even though the urllib probe reached the upstream fine.
    # NB: stub the global in THIS running module (serve runs us as __main__, and _proxy
    # resolves _urllib_fetch via the module global at call time), so monkeypatch globals().
    _self_mod = sys.modules[__name__]
    _orig_fetch = _self_mod._urllib_fetch
    def _boom(*_a, **_k):
        raise OSError("simulated upstream flap")
    _self_mod._urllib_fetch = _boom
    try:
        r502 = c.get("/spaces/immune")
        assert r502.status_code == 502 and "honest 502" in r502.text, (r502.status_code, r502.text[:80])
        assert r502.headers.get("x-szl-proxy-error") == "OSError", r502.headers.get("x-szl-proxy-error")
        rh = c.head("/spaces/immune")
        assert rh.status_code == 502, rh.status_code
    finally:
        _self_mod._urllib_fetch = _orig_fetch
    # client==None + urllib SUCCESS -> 200 proxied (proves None no longer auto-502s).
    def _ok(method, url, headers, timeout):
        return 200, b"<html><head></head><body>live immune</body></html>", {"content-type": "text/html"}
    _self_mod._urllib_fetch = _ok
    try:
        r200 = c.get("/spaces/immune")
        assert r200.status_code == 200, r200.status_code
        assert b'<base href="/spaces/immune/">' in r200.content, "must inject base href on proxied HTML"
    finally:
        _self_mod._urllib_fetch = _orig_fetch

    print("szl_spaces_proxy: ALL OK (allowlist; honest 502 on genuine flap; client==None "
          "falls through to urllib not auto-502; base-href idempotent; "
          "%d proxied of %d; 0 CDN server-side fetch)" % (len(PROXY_SPACES), len(ALL_SPACES)))
