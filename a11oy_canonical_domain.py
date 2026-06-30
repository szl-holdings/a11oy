#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""
a11oy_canonical_domain.py — make a-11-oy.com the single canonical host.

a11oy.net is SUNSET. This installs an app-level 301 redirect so any request whose
Host header is a11oy.net (or www.a11oy.net) is permanently redirected to the same
path+query on https://a-11-oy.com. The canonical HF Space host
(szlholdings-a11oy.hf.space), localhost, and a-11-oy.com itself are passed through
untouched, so the app keeps working on its origin while the public URL converges.

This is a READ-PATH-SAFE redirect: it is a pure 308/301 Location response, mints no
receipt, signs nothing, and touches no state (provenance rule: never sign on a read
path). Doctrine-safe: try/except-guarded register(app).
"""

CANONICAL_HOST = "a-11-oy.com"

# Hosts that should be permanently redirected to the canonical host.
SUNSET_HOSTS = {"a11oy.net", "www.a11oy.net"}


def register(app):
    """Install the a11oy.net -> a-11-oy.com 301 redirect middleware. Returns a status list."""
    from starlette.responses import RedirectResponse

    @app.middleware("http")
    async def _canonical_host_redirect(request, call_next):
        host = (request.headers.get("host") or "").split(":")[0].lower()
        if host in SUNSET_HOSTS:
            target = f"https://{CANONICAL_HOST}{request.url.path}"
            if request.url.query:
                target = f"{target}?{request.url.query}"
            # 301: permanent. The sunset host must never be presented as canonical.
            return RedirectResponse(url=target, status_code=301)
        return await call_next(request)

    return [f"301 {h} -> https://{CANONICAL_HOST}" for h in sorted(SUNSET_HOSTS)]
