#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Canonical-origin handoffs for the audited Hugging Face Spaces estate.

This shared module keeps the historical ``/spaces/<slug>`` links working without
executing another Space inside the a11oy or Killinchu origin:

* ``GET/HEAD /spaces`` renders a minimal fallback index when the richer tiles
  surface is not registered.
* ``GET/HEAD /spaces/{name}`` returns a no-store 307 to the audited Space's
  canonical Hugging Face application origin.
* ``GET/HEAD /spaces/{name}/{path}`` preserves the suffix and raw query string
  in the same no-store 307 handoff.

There is no upstream fetch path in this module. It never copies upstream HTML,
JavaScript, response bytes, authentication state, or ``Set-Cookie`` into the
host application. Interactive apps, streaming, cookies, and authentication stay
isolated on Hugging Face. Unknown identifiers fail closed with 404, so these
routes cannot become an open redirect.

Routes are front-inserted so exact compatibility links beat the application's
SPA catch-all. The audited 26-Space identity list is static; runtime reachability
continues to be measured honestly by ``szl_spaces_surface``.

Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
from __future__ import annotations

import html
import sys
from typing import Any
from urllib.parse import quote

_ORG_PREFIX = "szlholdings-"
_ORG = "SZLHOLDINGS"
SPACE_HANDOFF_MODE = "canonical-redirect-only/v1"

# Audited 26-Space public estate. Runtime state is deliberately absent here.
# ``slug`` is the lowercase legacy route key; SDK selects the canonical app host.
SPACE_INVENTORY: list[dict[str, str]] = [
    {"name": "a11oy", "slug": "a11oy", "title": "a11oy — Command Center", "sdk": "docker"},
    {"name": "anatomy", "slug": "anatomy", "title": "SZL Living Anatomy", "sdk": "docker"},
    {"name": "cosmos", "slug": "cosmos", "title": "SZL Cosmos", "sdk": "docker"},
    {"name": "david-leads", "slug": "david-leads", "title": "David Leads — Sovereign Insurance Intelligence", "sdk": "docker"},
    {"name": "energy-attest-holo", "slug": "energy-attest-holo", "title": "Energy Attestation Holo", "sdk": "static"},
    {"name": "energy-attested-runs", "slug": "energy-attested-runs", "title": "Energy-Attested Inference Runs", "sdk": "gradio"},
    {"name": "governed-norm-holo", "slug": "governed-norm-holo", "title": "Governed Norms — WILLAY classifiers", "sdk": "static"},
    {"name": "governed-receipt-verifier", "slug": "governed-receipt-verifier", "title": "Governed Receipt Verifier", "sdk": "static"},
    {"name": "guardrail-receipt", "slug": "guardrail-receipt", "title": "Guardrail Decision-Receipt", "sdk": "gradio"},
    {"name": "hatun-mcp", "slug": "hatun-mcp", "title": "hatun — MCP Server", "sdk": "docker"},
    {"name": "holographic", "slug": "holographic", "title": "Holographic Estate", "sdk": "docker"},
    {"name": "immune", "slug": "immune", "title": "IMMUNE — Verifiable AI Defense Matrix", "sdk": "docker"},
    {"name": "killinchu", "slug": "killinchu", "title": "killinchu — Andean Drone Intelligence", "sdk": "docker"},
    {"name": "lambda-gate-holo", "slug": "lambda-gate-holo", "title": "Λ Gate — Conjecture 1, never green", "sdk": "static"},
    {"name": "llm-router-live", "slug": "llm-router-live", "title": "SZL LLM Router", "sdk": "docker"},
    {"name": "README", "slug": "readme", "title": "SZL Holdings — Governed-AI Command Platform", "sdk": "static"},
    {"name": "receipt-chain-live", "slug": "receipt-chain-live", "title": "Receipt Chain Live", "sdk": "static"},
    {"name": "sda", "slug": "sda", "title": "SZL SDA", "sdk": "docker"},
    {"name": "szl-blocked-live", "slug": "szl-blocked-live", "title": "szl-blocked-live", "sdk": "static"},
    {"name": "szl-estate-live", "slug": "szl-estate-live", "title": "Khipu Loom — Governed AI Estate", "sdk": "static"},
    {"name": "szl-forge-lab", "slug": "szl-forge-lab", "title": "SZL Forge Lab", "sdk": "gradio"},
    {"name": "szl-govsign-live", "slug": "szl-govsign-live", "title": "szl-govsign-live", "sdk": "static"},
    {"name": "szl-kernels-live", "slug": "szl-kernels-live", "title": "SZL Kernel Operations Hub", "sdk": "static"},
    {"name": "szl-model-inference-lab", "slug": "szl-model-inference-lab", "title": "SZL Model Inference Lab", "sdk": "docker"},
    {"name": "szl-provctl-live", "slug": "szl-provctl-live", "title": "szl-provctl-live", "sdk": "static"},
    {"name": "yarqa", "slug": "yarqa", "title": "yarqa — Plug-Flow Compartments (live or sample, always honest)", "sdk": "docker"},
]
_SPACE_BY_NAME = {sp["name"]: sp for sp in SPACE_INVENTORY}
_SPACE_BY_SLUG = {sp["slug"]: sp for sp in SPACE_INVENTORY}

ALL_SPACES = [sp["slug"] for sp in SPACE_INVENTORY]
HANDOFF_SPACES = list(ALL_SPACES)
# Backwards-compatible public name retained for downstream inventory checks.
PROXY_SPACES = HANDOFF_SPACES

_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-SZL-Space-Handoff": "canonical-origin",
}


def _space_record(identifier: str) -> dict[str, str]:
    """Resolve only audited inventory identifiers; fail closed otherwise."""

    record = _SPACE_BY_NAME.get(identifier) or _SPACE_BY_SLUG.get(identifier)
    if record is None:
        raise ValueError("unknown Space identifier: %s" % identifier)
    return record


def hf_url(name: str) -> str:
    """Return the canonical isolated application origin for an audited Space."""

    record = _space_record(name)
    suffix = ".static.hf.space" if record["sdk"] == "static" else ".hf.space"
    return f"https://{_ORG_PREFIX}{record['slug']}{suffix}"


def hf_repo_url(name: str) -> str:
    """Return the canonical Hugging Face repository page for an audited Space."""

    record = _space_record(name)
    return f"https://huggingface.co/spaces/{_ORG}/{record['name']}"


def _fallback_index() -> bytes:
    """Render the dependency-free fallback registry with canonical links only."""

    rows = []
    for record in SPACE_INVENTORY:
        title = html.escape(record["title"])
        name = html.escape(record["name"])
        sdk = html.escape(record["sdk"])
        canonical = html.escape(hf_url(record["slug"]), quote=True)
        repository = html.escape(hf_repo_url(record["slug"]), quote=True)
        rows.append(
            '<li style="margin:.4rem 0"><strong style="color:#e7eef6">%s</strong> '
            '<small style="color:#697787">%s &middot; %s</small> '
            '&middot; <a href="%s" rel="noopener" target="_blank" '
            'style="color:#d4a444;text-decoration:none">Open canonical app &#8599;</a> '
            '&middot; <a href="%s" rel="noopener" target="_blank" '
            'style="color:#7c8794;text-decoration:none">View repository &#8599;</a></li>'
            % (title, name, sdk, canonical, repository)
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Hugging Face Spaces</title>'
        '<style>*{box-sizing:border-box}li{overflow-wrap:anywhere}'
        'li a{display:inline-flex;align-items:center;min-height:44px;padding:.3rem .15rem}'
        '@media(max-width:375px){body{padding:1rem!important}}</style></head>'
        '<body style="margin:0;background:#0b0f14;color:#cdd6e0;'
        'font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:2rem">'
        '<main style="max-width:760px;margin:0 auto">'
        '<h1 style="color:#e7eef6">Hugging Face Spaces</h1>'
        '<p style="color:#8a96a3">All 26 audited Spaces open on their canonical isolated '
        'Hugging Face origins. Legacy <code>/spaces/&lt;slug&gt;</code> links are no-store '
        '307 handoffs; no upstream response bytes or cookies cross this application.</p>'
        '<ul style="list-style:none;padding:0">' + "".join(rows) + "</ul>"
        "</main></body></html>"
    ).encode("utf-8")


def _canonical_target(name: str, subpath: str = "", query: str = "") -> str:
    """Build a fixed-origin redirect target without accepting an arbitrary host."""

    record = _SPACE_BY_SLUG.get(name)
    if record is None or name not in HANDOFF_SPACES:
        raise ValueError("unknown Space identifier: %s" % name)
    target = hf_url(name)
    if subpath:
        encoded_path = quote(subpath.lstrip("/"), safe="/:@!$&'()*+,;=-._~")
        target += "/" + encoded_path
    if query:
        target += "?" + quote(query, safe="=&;%:+,/?@-._~")
    return target


def _raw_query(request: Any) -> str | None:
    raw = request.scope.get("query_string", b"")
    try:
        query = bytes(raw).decode("ascii")
    except (UnicodeDecodeError, TypeError, ValueError):
        return None
    if "\r" in query or "\n" in query:
        return None
    return query


async def _proxy(name: str, subpath: str, request: Any) -> Any:
    """Legacy function name; perform a redirect-only canonical-origin handoff."""

    from starlette.responses import RedirectResponse, Response

    if name not in HANDOFF_SPACES:
        return Response(
            content=b"Unknown or non-handoff Space.\n",
            status_code=404,
            media_type="text/plain",
            headers={"Cache-Control": "no-store"},
        )

    query = _raw_query(request)
    if query is None:
        return Response(
            content=b"Invalid query string.\n",
            status_code=400,
            media_type="text/plain",
            headers={"Cache-Control": "no-store"},
        )

    target = _canonical_target(name, subpath, query)

    return RedirectResponse(target, status_code=307, headers=_NO_STORE_HEADERS)


def register(app: Any, ns: str = "a11oy") -> str:
    """Front-insert the fallback index and redirect-only compatibility routes."""

    try:
        from starlette.responses import Response
        from starlette.routing import Route
    except Exception as exc:  # pragma: no cover
        return "unavailable: %r" % (exc,)

    n_before = len(app.router.routes)

    async def _spaces_index(request: Any) -> Any:
        headers = {"Cache-Control": "no-store"}
        if request.method.upper() == "HEAD":
            return Response(content=b"", status_code=200, media_type="text/html", headers=headers)
        return Response(
            content=_fallback_index(),
            status_code=200,
            media_type="text/html",
            headers=headers,
        )

    async def _spaces_name(request: Any) -> Any:
        return await _proxy(request.path_params.get("name", ""), "", request)

    async def _spaces_path(request: Any) -> Any:
        return await _proxy(
            request.path_params.get("name", ""),
            request.path_params.get("path", ""),
            request,
        )

    routes = [
        Route("/spaces", _spaces_index, methods=["GET", "HEAD"], name="spaces-fallback-index"),
        Route("/spaces/{name}", _spaces_name, methods=["GET", "HEAD"], name="spaces-handoff-root"),
        Route(
            "/spaces/{name}/{path:path}",
            _spaces_path,
            methods=["GET", "HEAD"],
            name="spaces-handoff-path",
        ),
    ]
    app.router.routes.extend(routes)
    new = app.router.routes[n_before:]
    del app.router.routes[n_before:]
    app.router.routes[0:0] = new

    print(
        "[%s] Spaces canonical-origin handoffs registered: /spaces + "
        "/spaces/{name} + /spaces/{name}/{path} (%d audited handoffs; %d routes)"
        % (ns, len(HANDOFF_SPACES), len(new)),
        file=sys.stderr,
    )
    return "ok: %d canonical handoff spaces, %d routes" % (len(HANDOFF_SPACES), len(new))


if __name__ == "__main__":
    import ast
    from pathlib import Path

    source = Path(__file__).read_text(encoding="utf-8")
    ast.parse(source)
    assert "urllib" + ".request" not in source
    assert "client." + "request(" not in source
    assert "upstream." + "content" not in source

    assert len(ALL_SPACES) == len(HANDOFF_SPACES) == 26
    assert hf_url("README") == "https://szlholdings-readme.static.hf.space"
    assert hf_url("immune") == "https://szlholdings-immune.hf.space"
    try:
        hf_url("notreal")
        raise AssertionError("unknown Space identifier must fail closed")
    except ValueError:
        pass

    fallback = _fallback_index()
    for space in SPACE_INVENTORY:
        assert space["name"].encode() in fallback
        assert space["title"].encode() in fallback
        assert hf_url(space["slug"]).encode() in fallback
        assert hf_repo_url(space["slug"]).encode() in fallback
    assert b'href="/spaces/' not in fallback
    assert b"reverse proxy" not in fallback.lower()

    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    app = Starlette(routes=[Route("/{full_path:path}", lambda req: PlainTextResponse("SPA"))])
    status = register(app, ns="killinchu")
    assert status.startswith("ok:")
    client = TestClient(app)

    root = client.get(
        "/spaces/immune",
        headers={"Cookie": "private=session", "Authorization": "Bearer private"},
        follow_redirects=False,
    )
    assert root.status_code == 307
    assert root.headers["location"] == "https://szlholdings-immune.hf.space"
    assert root.headers["cache-control"] == "no-store"
    assert root.headers["x-szl-space-handoff"] == "canonical-origin"
    assert "set-cookie" not in root.headers and root.content == b""

    nested = client.get(
        "/spaces/immune/api/events?cursor=a%2Fb&cursor=two+words",
        follow_redirects=False,
    )
    assert nested.status_code == 307
    assert nested.headers["location"] == (
        "https://szlholdings-immune.hf.space/api/events?cursor=a%2Fb&cursor=two+words"
    )
    head = client.head("/spaces/immune/assets/app.js?build=7", follow_redirects=False)
    assert head.status_code == 307 and head.content == b""
    assert head.headers["location"].endswith("/assets/app.js?build=7")
    assert client.get("/spaces/notreal", follow_redirects=False).status_code == 404
    own = client.get("/spaces/a11oy", follow_redirects=False)
    assert own.status_code == 307
    assert own.headers["location"] == "https://szlholdings-a11oy.hf.space"

    print(
        "szl_spaces_proxy: ALL OK (26 audited redirect-only handoffs; "
        "path/query preserved; no-store; no upstream bytes/Set-Cookie)"
    )
