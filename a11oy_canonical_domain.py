#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""
a11oy_canonical_domain.py — two-origin identity lock (Doctrine v11).

LOCKED DOMAIN ARCHITECTURE (do not merge the two hosts):

- a-11-oy.com  = product command center (this app, HF Space behind Cloudflare)
- a11oy.net    = canonical public proof/registry (GitHub Pages, separate failure
  domain). Must stay up if the product is down.

This module used to 301 every a11oy.net Host onto a-11-oy.com. That is a
landmine: if DNS ever pointed .net at this Space, the registry origin would
vanish into the product app. register() therefore installs NO cross-origin
redirect. It also never issues a Location to the unhyphenated third-party
host a11oy.com (a furniture shop we do not control).

HTML canonicals stay on https://a-11-oy.com even when Hugging Face
runtime.domains reports that host PENDING. PENDING is an open DNS/provider
defect (KALLPA / Stephen). Do not paper it over by pointing canonicals at
*.hf.space, and do not retarget Cloudflare DNS just to satisfy Hugging Face
if that would take the public origin down. See docs/runbook.md INC-05 and
docs/SPACES_HEALTH_OPERATIONS.md (custom domain state).

DX — routes, contracts, env, promote path (staging Space ≠ prod DNS):
- Routes: product HTML and /verify live on a-11-oy.com. The lasting public
  receipt RECORD belongs on a11oy.net. Do not merge the two origins.
- Contracts: crawlers send HEAD. HTML documents and robots.txt must HEAD 200
  with the same headers as GET and an empty body.
- Env: Space runtime vars configure the app. Prod DNS is Cloudflare in front
  of the Space. x-szl-wire-d: LIVE is DSSE Wire D provenance, not "domain LIVE".
- Promote: hf-sync publishes GitHub main → Space SZLHOLDINGS/a11oy
  (szlholdings-a11oy.hf.space READY). Apex a-11-oy.com is a Cloudflare A-record
  front, not Hugging Face custom-domain READY. Do not treat Space READY as
  prod-DNS verified.

Read-path-safe: no receipt, no signing, no state. Doctrine-safe try/except
register(app).
"""

CANONICAL_HOST = "a-11-oy.com"
REGISTRY_HOST = "a11oy.net"
# Third-party furniture shop. Never a canonical, og:url, sameAs, or redirect target.
FORBIDDEN_PUBLIC_HOST = "a11oy.com"

# HTML document paths crawlers and monitors probe with HEAD. GET-only FastAPI
# routes 405 on HEAD; /verify and /ecosystem already declare GET+HEAD and 200.
HTML_DOCUMENT_HEAD_PATHS = ("/", "/console", "/trust", "/assurance", "/robots.txt")


def _host_without_port(host: str) -> str:
    return (host or "").split(":")[0].lower()


def _is_registry_host(host: str) -> bool:
    """True if `host` is the a11oy.net apex or any of its subdomains."""
    h = _host_without_port(host)
    return h == REGISTRY_HOST or h.endswith("." + REGISTRY_HOST)


def _is_product_host(host: str) -> bool:
    h = _host_without_port(host)
    return h == CANONICAL_HOST or h.endswith("." + CANONICAL_HOST)


def _is_forbidden_public_host(host: str) -> bool:
    h = _host_without_port(host)
    return h == FORBIDDEN_PUBLIC_HOST or h.endswith("." + FORBIDDEN_PUBLIC_HOST)


def ensure_html_documents_accept_head(app):
    """Add HEAD to pinned HTML document routes that already accept GET.

    FastAPI ``@app.get`` registrations in this tree do not accept HEAD (live
    MEASURED 405 JSON on /console, /trust, /assurance). Starlette FileResponse
    already omits the body when the method is HEAD, matching GET headers.
    """
    router = getattr(app, "router", app)
    patched = []
    for route in getattr(router, "routes", []):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path not in HTML_DOCUMENT_HEAD_PATHS or not methods:
            continue
        if "GET" not in methods:
            continue
        if "HEAD" in methods:
            patched.append(path)
            continue
        if not isinstance(methods, set):
            methods = set(methods)
            route.methods = methods
        methods.add("HEAD")
        patched.append(path)
    return patched


def register(app):
    """Install the two-origin identity lock. Never 301 .net onto the product host."""

    @app.middleware("http")
    async def _two_origin_identity(request, call_next):
        # Pass through. Explicitly do not 301 a11oy.net → a-11-oy.com and do not
        # 301 a-11-oy.com → a11oy.net. Never set Location to a11oy.com.
        return await call_next(request)

    ensure_html_documents_accept_head(app)
    return [
        (
            f"two-origin identity: product=https://{CANONICAL_HOST} "
            f"registry=https://{REGISTRY_HOST}; no cross-origin 301"
        )
    ]
