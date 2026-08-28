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
- Contracts: crawlers and health monitors send HEAD. HTML documents, robots.txt,
  sitemap.xml, and the health JSON probes below must HEAD with the same
  status+headers as GET and an empty body. Starlette Route(..., methods=["GET"])
  / FastAPI @app.get is the usual 405 — including on the Space (Server: szl),
  not Cloudflare. GET-only /api/a11oy/* is worse: the Node proxy catch-all
  already accepts HEAD, so monitors see 404 instead of 405 (QHAPAQ 2026-08-28).
  Public product GET/HEAD/OPTIONS are Host-aware (this app, not a Cloudflare
  transform): on Host a-11-oy.com and www.a-11-oy.com, Link rel=canonical is
  https://a-11-oy.com{path} (path only; no query). huggingface.co/spaces is never the product canonical.
  a11oy.com is never that canonical. On *.hf.space the app omits a Space Hub
  canonical; it does not make the Space the public product canonical.
- Env: Space runtime vars configure the app. Prod DNS is Cloudflare orange-cloud
  (proxied) in front of the Space. This app does not change DNS. x-szl-wire-d:
  LIVE is DSSE Wire D provenance, not "domain LIVE". HF custom domain stays
  PENDING/UNAVAILABLE in product. www.a-11-oy.com GET / is Cloudflare HTTP 404
  (UNAVAILABLE until Cloudflare 301 www → apex). MEASURED 2026-08-28 ~18:06 UTC:
  DNS resolves via Cloudflare IPv6 2606:4700:…; the 404 is Cloudflare, not the
  Space. Do not add a second HF custom domain. This app does not change DNS.
  Host-aware Link on Host www still emits https://a-11-oy.com{path}.
  Do not merge PR 1363.
- Promote: hf-sync publishes GitHub main → Space SZLHOLDINGS/a11oy
  (szlholdings-a11oy.hf.space READY). Staging Space ≠ prod DNS. Apex
  a-11-oy.com stays Cloudflare orange-cloud. Stephen may later add the HF
  verify TXT (_huggingface.a-11-oy.com) WITHOUT dropping that proxy. Keep
  orange-cloud. Do not grey-cloud. Do not stamp LIVE. Do not treat Space
  READY as prod-DNS verified.

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
# QHAPAQ S1–S12 MEASURED 2026-08-28 13:05–13:12 ET: GET 200 / HEAD 405 on
# /healthz /readyz /api/health; GET 200 / HEAD 404 on /api/a11oy/healthz and
# /api/a11oy/v1/health (HEAD fell through to the /api/a11oy/{path} proxy).
HEALTH_JSON_HEAD_PATHS = (
    "/healthz",
    "/readyz",
    "/api/health",
    "/api/a11oy/healthz",
    "/api/a11oy/v1/health",
)
GET_HEAD_PATHS = HTML_DOCUMENT_HEAD_PATHS + HEALTH_JSON_HEAD_PATHS + (
    "/sitemap.xml",
)

_OPTIONS_ALLOW = "GET, HEAD, OPTIONS"
_OPTIONS_ACAM = "GET, HEAD, POST, OPTIONS"


def _host_without_port(host: str) -> str:
    return (host or "").split(":")[0].lower()


def _is_registry_host(host: str) -> bool:
    """True if `host` is the a11oy.net apex or any of its subdomains."""
    h = _host_without_port(host)
    return h == REGISTRY_HOST or h.endswith("." + REGISTRY_HOST)


def _is_product_host(host: str) -> bool:
    h = _host_without_port(host)
    return h == CANONICAL_HOST or h.endswith("." + CANONICAL_HOST)


def _is_public_product_host(host: str) -> bool:
    """Apex and www only. Host-aware Link rewrite — not a Cloudflare transform."""
    h = _host_without_port(host)
    return h == CANONICAL_HOST or h == "www." + CANONICAL_HOST


def _is_hf_space_host(host: str) -> bool:
    h = _host_without_port(host)
    return h == "hf.space" or h.endswith(".hf.space")


def _effective_request_host(request) -> str:
    """Host, or X-Forwarded-Host when Cloudflare presents the product apex."""
    forwarded = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if _is_public_product_host(forwarded):
        return forwarded
    return request.headers.get("host") or ""


def _is_forbidden_public_host(host: str) -> bool:
    h = _host_without_port(host)
    return h == FORBIDDEN_PUBLIC_HOST or h.endswith("." + FORBIDDEN_PUBLIC_HOST)


def _normalize_path(path: str) -> str:
    raw = (path or "/").split("?")[0] or "/"
    if raw != "/" and raw.endswith("/"):
        return raw.rstrip("/") or "/"
    return raw


def product_canonical_url(path: str) -> str:
    """Public product canonical. Never huggingface.co/spaces, never a11oy.com."""
    return f"https://{CANONICAL_HOST}{_normalize_path(path)}"


def _iter_link_values(headers) -> list:
    if hasattr(headers, "getlist"):
        return [v for v in (headers.getlist("link") or []) if v]
    if hasattr(headers, "get_list"):
        return [v for v in (headers.get_list("link") or []) if v]
    raw = headers.get("link")
    return [raw] if raw else []


def _is_rel_canonical(value: str) -> bool:
    lower = value.lower().replace("'", '"')
    return 'rel="canonical"' in lower or "rel=canonical" in lower


def _link_is_space_hub_or_furniture(value: str) -> bool:
    lower = value.lower()
    if "huggingface.co/spaces/" in lower:
        return True
    furniture = FORBIDDEN_PUBLIC_HOST
    return furniture in lower.replace(CANONICAL_HOST, "")


def apply_product_canonical_link(response, path: str) -> None:
    """Stamp Link rel=canonical to https://a-11-oy.com{path}; drop Space/furniture."""
    headers = response.headers
    kept = []
    for value in _iter_link_values(headers):
        if _is_rel_canonical(value):
            continue
        kept.append(value)
    if "link" in headers:
        del headers["link"]
    for value in kept:
        if hasattr(headers, "append"):
            headers.append("link", value)
        else:
            headers["link"] = value
    canonical = f'<{product_canonical_url(path)}>; rel="canonical"'
    if hasattr(headers, "append") and kept:
        headers.append("link", canonical)
    else:
        headers["link"] = canonical


def omit_space_or_furniture_canonical_link(response) -> None:
    """On *.hf.space: omit Space Hub / furniture rel=canonical. Do not stamp product."""
    headers = response.headers
    kept = []
    for value in _iter_link_values(headers):
        if _is_rel_canonical(value) and _link_is_space_hub_or_furniture(value):
            continue
        kept.append(value)
    if "link" in headers:
        del headers["link"]
    for value in kept:
        if hasattr(headers, "append"):
            headers.append("link", value)
        else:
            headers["link"] = value


def rewrite_host_aware_canonical_link(response, path: str, host: str) -> None:
    """Host-aware Link rewrite in this app. Not a Cloudflare transform.

    a-11-oy.com / www → https://a-11-oy.com{path}. *.hf.space omits Space Hub
    canonical. Never huggingface.co/spaces, never a11oy.com.
    """
    if _is_registry_host(host):
        return
    if _is_public_product_host(host):
        apply_product_canonical_link(response, path)
        return
    omit_space_or_furniture_canonical_link(response)


def _options_response(existing=None, path: str = "/", host: str = ""):
    from starlette.responses import Response

    response = Response(status_code=200)
    if existing is not None:
        for key, value in existing.headers.items():
            if key.lower().startswith("access-control-"):
                response.headers[key] = value
    response.headers["Allow"] = _OPTIONS_ALLOW
    if "access-control-allow-methods" not in response.headers:
        response.headers["Access-Control-Allow-Methods"] = _OPTIONS_ACAM
    rewrite_host_aware_canonical_link(response, path, host)
    return response


def ensure_html_documents_accept_head(app):
    """Add HEAD to pinned HTML document and health JSON routes that accept GET.

    FastAPI ``@app.get`` and Starlette ``Route(..., methods=["GET"])`` do not
    accept HEAD. Live MEASURED 2026-08-28: 405 on documents and /healthz;
    404 on /api/a11oy/healthz because the proxy catch-all already lists HEAD.
    Same 405 on szlholdings-a11oy.hf.space (Server: szl) — the app, not Cloudflare.
    Starlette Response / FileResponse already omit the body on HEAD.
    """
    router = getattr(app, "router", app)
    patched = []
    for route in getattr(router, "routes", []):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path not in GET_HEAD_PATHS or not methods:
            continue
        if "GET" not in methods:
            continue
        if not isinstance(methods, set):
            methods = set(methods)
            route.methods = methods
        methods.add("HEAD")
        patched.append(path)
    return patched


def register(app):
    """Install the two-origin identity lock. Never 301 .net onto the product host.

    Also: Host-aware Link rel=canonical (this app, not a Cloudflare transform).
    On a-11-oy.com / www, canonical is https://a-11-oy.com{path}. The Hugging
    Face Space URL is never the public product canonical. OPTIONS on public
    documents carries Allow + Access-Control-Allow-Methods. HF custom domain
    stays PENDING/UNAVAILABLE. Keep orange-cloud. Do not grey-cloud. www GET /
    is Cloudflare HTTP 404 (UNAVAILABLE until Cloudflare 301 www → apex). Do
    not add a second HF custom domain. This app does not change DNS (verify
    TXT is Stephen, without dropping the proxy). Host-aware Link on www still
    emits https://a-11-oy.com{path}.
    """

    @app.middleware("http")
    async def _two_origin_identity(request, call_next):
        # Do not 301 a11oy.net → a-11-oy.com and do not 301 a-11-oy.com → a11oy.net.
        # Never set Location to a11oy.com.
        path = _normalize_path(getattr(request.url, "path", "/") or "/")
        host = _effective_request_host(request)

        if request.method == "OPTIONS":
            response = await call_next(request)
            if _is_registry_host(host):
                return response
            if "access-control-allow-methods" in response.headers:
                if "allow" not in response.headers:
                    response.headers["Allow"] = _OPTIONS_ALLOW
                rewrite_host_aware_canonical_link(response, path, host)
                return response
            if response.status_code == 405 or path in GET_HEAD_PATHS:
                return _options_response(response, path, host)
            if "allow" not in response.headers:
                response.headers["Allow"] = _OPTIONS_ALLOW
            rewrite_host_aware_canonical_link(response, path, host)
            return response

        response = await call_next(request)
        if _is_registry_host(host):
            return response
        if request.method in ("GET", "HEAD") and 200 <= response.status_code < 300:
            rewrite_host_aware_canonical_link(response, path, host)
        return response

    ensure_html_documents_accept_head(app)
    return [
        (
            f"two-origin identity: product=https://{CANONICAL_HOST} "
            f"registry=https://{REGISTRY_HOST}; no cross-origin 301; "
            f"Link rel=canonical Host-aware https://{CANONICAL_HOST}{{path}}"
        )
    ]
