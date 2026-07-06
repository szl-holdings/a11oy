#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""
a11oy_canonical_domain.py — make a-11-oy.com the single canonical host.

a11oy.net is SUNSET. This installs an app-level 301 redirect so any request whose
Host header is on the a11oy.net domain — the apex (a11oy.net), www, OR ANY
subdomain (*.a11oy.net) — is permanently redirected to the same path+query on
https://a-11-oy.com. The canonical HF Space host (szlholdings-a11oy.hf.space),
localhost, and a-11-oy.com itself are passed through untouched, so the app keeps
working on its origin while the public URL converges.

Doctrine ("No a11oy.net on user surfaces"): matching only the apex + www left a
real gap — any OTHER a11oy.net host (e.g. app.a11oy.net, a stray CNAME) fell
through and SERVED user surfaces on .net. The match is host-suffix based so no
a11oy.net host can serve user content; every one of them is redirect-only.

This is a READ-PATH-SAFE redirect: it is a pure 301 Location response, mints no
receipt, signs nothing, and touches no state (provenance rule: never sign on a read
path). Doctrine-safe: try/except-guarded register(app).
"""

CANONICAL_HOST = "a-11-oy.com"

# The sunset domain. Any host that IS this apex or ends with ".<apex>" (i.e. any
# subdomain) is redirect-only and must never serve a user surface.
SUNSET_DOMAIN = "a11oy.net"


def _is_sunset_host(host: str) -> bool:
    """True if `host` is the a11oy.net apex or any of its subdomains."""
    return host == SUNSET_DOMAIN or host.endswith("." + SUNSET_DOMAIN)


def register(app):
    """Install the a11oy.net -> a-11-oy.com 301 redirect middleware. Returns a status list."""
    from starlette.responses import RedirectResponse

    @app.middleware("http")
    async def _canonical_host_redirect(request, call_next):
        host = (request.headers.get("host") or "").split(":")[0].lower()
        if _is_sunset_host(host):
            target = f"https://{CANONICAL_HOST}{request.url.path}"
            if request.url.query:
                target = f"{target}?{request.url.query}"
            # 301: permanent. The sunset host must never be presented as canonical.
            return RedirectResponse(url=target, status_code=301)
        return await call_next(request)

    return [f"301 {SUNSET_DOMAIN} (+ *.{SUNSET_DOMAIN}) -> https://{CANONICAL_HOST}"]
