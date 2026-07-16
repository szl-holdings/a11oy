#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""szl_spaces_surface.py — console "Spaces" surface (health API + tiles + nav).

ADDITIVE, self-contained, SHARED across a11oy + killinchu. The console companion to
the canonical handoff module: a LIVE health view of the whole HF Spaces estate plus a
clean tiles page and ONE idempotent nav item, following the additive-injector pattern
(a11oy_nav_wireup.py / killinchu_nav_wireup.py).

ROUTES (additive, inserted at the FRONT of the router so they beat the SPA + Node-proxy
catch-alls — same route-to-front idiom as a11oy_hf_assets.py):

  GET  /api/<ns>/v1/spaces/health  -> for each Space, an HONEST status:
        {name, slug, title, sdk, stage, app_reachable, url, canonical_url, proxy_url}
        - stage          : runtime.stage from the HF API
                           (https://huggingface.co/api/spaces/SZLHOLDINGS/<name>),
                           or "unknown" if that API call degrades. LABELLED as HF-API.
        - app_reachable  : a REAL server-side probe of
                           https://szlholdings-<name>.hf.space/ (HEAD, short timeout).
                           true ONLY when the probe really succeeded. Never fabricated.
        Degrade -> stage:"unknown", app_reachable:false. NEVER a faked stage/200.

  GET/HEAD /spaces                 -> a clean tiles page (one card per Space: honest
        title, live status dot fed by /health, canonical isolated hf.space app link,
        and a separate huggingface.co repository link).
        No upstream app executes inside the a11oy or Killinchu origin. Pure inline
        markup, 0 browser CDN. Status dots are filled by a tiny inline fetch of the
        SAME-ORIGIN /health JSON (our own server-side-probed endpoint).

NAV: a BaseHTTPMiddleware injector adds ONE nav item "Spaces" -> /spaces into the
console left-nav (before <div class="side-foot">, with nav-group / nav-item fallbacks).
Idempotent — keyed by data-attribute data-nav-spaces="hf1"; removes NOTHING from the SPA
source; never touches /api, /v1, /assets, /static, /vendor responses. Works identically
on the a11oy /console and killinchu /elite consoles (same sidebar markup) — which is why
this module can be byte-identical in both apps.

The /spaces probe + HF-API call are SERVER-SIDE fetches (resolve the shared httpx client
lazily from serve.py, like szl_engine_status) — 0 runtime CDN, same justification as
a11oy_hf_assets.py. No auth token forwarded to HF (public Spaces / public API).

Doctrine v11: locked-proven = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17;
Λ = Conjecture 1; Khipu = Conjecture 2; trust never 100%; 0 runtime CDN; no user-visible
codenames (Space names are their own honest titles); never commits a key; additive-only;
honest "unknown"/false beats a fabricated stage.

Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations

import sys
import time
from typing import Any

_ORG = "SZLHOLDINGS"
_ORG_PREFIX = "szlholdings-"
SPACE_TILE_ORIGIN_MODE = "canonical-isolated-hf/v1"

# Audited 26-Space public estate. Names are exact Hub repository names and titles are
# the current public card titles observed during the 2026-07-16 alignment audit. Runtime
# state is deliberately NOT frozen here: /health measures it on every cache refresh and
# degrades to unknown/false when evidence is unavailable. ``slug`` is the lowercase,
# same-origin route key; it differs from ``name`` only for the Hub repository ``README``.
# a11oy + killinchu retain the historical own-host classification in the health payload,
# but every tile now opens its canonical isolated Hugging Face application origin.
SPACES: list[dict[str, str]] = [
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
_SPACE_BY_NAME = {sp["name"]: sp for sp in SPACES}
_SPACE_BY_SLUG = {sp["slug"]: sp for sp in SPACES}
# Product Spaces retained as metadata for consumers that distinguish flagship hosts.
_OWN_HOST = {"a11oy", "killinchu"}

_DOCTRINE = {
    "version": "v11",
    "lambda": "Conjecture 1",
    "khipu": "Conjecture 2",
    "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "trust_ceiling": "never 100%",
}

_PROBE_TIMEOUT = 6.0
_HF_API_TIMEOUT = 6.0
_HEALTH_CACHE_TTL = 20.0  # seconds — keep the tiles page snappy without re-probing 26x.
_HEALTH_CACHE: dict[str, Any] = {"ts": 0.0, "payload": None}
_RUNNING_STAGES = {"RUNNING"}


def _space_record(identifier: str) -> dict[str, str]:
    """Resolve only audited inventory identifiers; fail closed for unknown names."""
    record = _SPACE_BY_NAME.get(identifier) or _SPACE_BY_SLUG.get(identifier)
    if record is None:
        raise ValueError("unknown Space identifier: %s" % identifier)
    return record


def hf_url(name: str) -> str:
    record = _space_record(name)
    host_suffix = ".static.hf.space" if record["sdk"] == "static" else ".hf.space"
    return f"https://{_ORG_PREFIX}{record['slug']}{host_suffix}"


def hf_api_url(name: str) -> str:
    record = _space_record(name)
    return f"https://huggingface.co/api/spaces/{_ORG}/{record['name']}"


def hf_repo_url(name: str) -> str:
    record = _space_record(name)
    return f"https://huggingface.co/spaces/{_ORG}/{record['name']}"


def canonical_url(name: str) -> str:
    """Canonical isolated application origin for an audited Space."""
    return hf_url(name)


def proxy_url(name: str) -> str:
    """Deprecated compatibility alias for ``canonical_url``.

    No upstream Space executes under the host application's origin; interactive
    apps, streaming, cookies, and authentication stay isolated on Hugging Face.
    """
    return canonical_url(name)


def _resolve_client() -> Any:
    """Lazily resolve the app's shared httpx.AsyncClient from serve.py (same idiom as
    szl_engine_status), so registration order doesn't matter."""
    try:
        import serve as _serve  # type: ignore
        return getattr(_serve, "_http_client", None)
    except Exception:
        return None


# stdlib fallback fetch — this is the PROVEN-working outbound path on the live box
# (a11oy_hf_assets.py reaches huggingface.co via urllib server-side). When the shared
# httpx.AsyncClient is None or its outbound attempt fails, we fall back to urllib run in
# a thread so the probe still reflects REAL reachability instead of a false negative.
# Still 0 browser CDN (server-side fetch). No auth token forwarded (public).
def _urllib_probe(url: str, timeout: float, want_json: bool = False) -> Any:
    """Blocking stdlib fetch. Returns (status_code, json_or_None). Raises on failure."""
    import json as _json
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "szl-spaces-surface/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        status = getattr(r, "status", None) or r.getcode()
        if want_json:
            data = r.read(262144)
            try:
                return status, _json.loads(data.decode("utf-8", "replace"))
            except Exception:
                return status, None
        return status, None


async def _to_thread(fn, *a, **kw):
    import asyncio as _asyncio
    return await _asyncio.get_event_loop().run_in_executor(None, lambda: fn(*a, **kw))


async def _probe_one(client: Any, sp: dict[str, str]) -> dict[str, Any]:
    """HONEST per-Space status. app_reachable is a REAL HEAD probe; stage is from the
    HF API. Any failure degrades to honest false/'unknown' — never fabricated."""
    name = sp["name"]
    slug = sp["slug"]
    result: dict[str, Any] = {
        "name": name,
        "slug": slug,
        "title": sp["title"],
        "sdk": sp["sdk"],
        "url": hf_url(name),
        "canonical_url": canonical_url(name),
        "proxy_url": proxy_url(name),
        "own_host": slug in _OWN_HOST,
        "stage": "unknown",         # from HF API; HF-API-labelled below
        "stage_source": "hf-api",
        "app_reachable": False,     # REAL probe; only true when the probe truly succeeds
    }
    # (1) REAL liveness probe of the canonical Space app. Try the shared async httpx
    #     client first; on None/failure fall back to the PROVEN stdlib urllib path.
    probed = False
    if client is not None:
        try:
            r = await client.request("HEAD", hf_url(name) + "/",
                                     timeout=_PROBE_TIMEOUT, follow_redirects=True)
            result["app_reachable"] = bool(r.status_code < 500)
            result["app_status"] = r.status_code
            result["probe_via"] = "httpx"
            probed = True
        except Exception:
            try:
                r = await client.get(hf_url(name) + "/", timeout=_PROBE_TIMEOUT,
                                     follow_redirects=True)
                result["app_reachable"] = bool(r.status_code < 500)
                result["app_status"] = r.status_code
                result["probe_via"] = "httpx"
                probed = True
            except Exception:
                probed = False
    if not probed:
        # stdlib fallback (the path a11oy_hf_assets proves works on this box).
        try:
            status, _ = await _to_thread(_urllib_probe, hf_url(name) + "/", _PROBE_TIMEOUT, False)
            result["app_reachable"] = bool(status < 500)
            result["app_status"] = status
            result["probe_via"] = "urllib"
        except Exception as e:
            result["app_reachable"] = False
            result["probe_error"] = type(e).__name__

    # (2) HF API runtime.stage (public API, no token). Honest "unknown" on any failure.
    got_stage = False
    if client is not None:
        try:
            ra = await client.get(hf_api_url(name), timeout=_HF_API_TIMEOUT,
                                  headers={"User-Agent": "szl-spaces-surface/1.0"})
            if ra.status_code == 200:
                data = ra.json()
                stage = (((data or {}).get("runtime") or {}).get("stage"))
                if isinstance(stage, str) and stage:
                    result["stage"] = stage
                got_stage = True
            else:
                result["stage_http"] = ra.status_code
                got_stage = True
        except Exception:
            got_stage = False
    if not got_stage:
        try:
            status, data = await _to_thread(_urllib_probe, hf_api_url(name), _HF_API_TIMEOUT, True)
            if status == 200 and isinstance(data, dict):
                stage = ((data.get("runtime") or {}).get("stage"))
                if isinstance(stage, str) and stage:
                    result["stage"] = stage
            else:
                result["stage_http"] = status
        except Exception as e:
            result["stage_error"] = type(e).__name__

    result["state"] = _space_health_state(result)
    return result


def _space_health_state(space: dict[str, Any]) -> str:
    """Derive one conservative, user-facing state from observed row evidence."""
    reachable = bool(space.get("app_reachable"))
    stage = str(space.get("stage") or "unknown").upper()
    if reachable and stage in _RUNNING_STAGES:
        return "LIVE"
    if not reachable and stage == "UNKNOWN":
        return "UNAVAILABLE"
    return "DEGRADED"


def _aggregate_health_state(spaces: list[dict[str, Any]]) -> str:
    """Derive a conservative top-level state from the observed Space rows."""
    if not spaces:
        return "UNAVAILABLE"
    states = [_space_health_state(row) for row in spaces]
    if all(state == "LIVE" for state in states):
        return "LIVE"
    if all(state == "UNAVAILABLE" for state in states):
        return "UNAVAILABLE"
    return "DEGRADED"


async def spaces_health() -> dict[str, Any]:
    """Aggregate honest health for the audited 26-Space estate (short TTL cache)."""
    now = time.monotonic()
    if _HEALTH_CACHE["payload"] is not None and (now - _HEALTH_CACHE["ts"]) < _HEALTH_CACHE_TTL:
        cached = _HEALTH_CACHE["payload"]
        # Return a new top-level mapping: label the transport as CACHED while
        # preserving the original aggregate verdict for auditability.
        return {
            **cached,
            "state": "CACHED",
            "cached_state": cached.get("state", "UNAVAILABLE"),
        }

    client = _resolve_client()
    # Probe every Space concurrently. _probe_one handles client=None internally by
    # falling back to the stdlib urllib path (the proven outbound path on this box),
    # so we always return REAL reachability, degrading honestly only on true failure.
    import asyncio as _asyncio
    spaces = list(await _asyncio.gather(*[_probe_one(client, sp) for sp in SPACES]))

    payload = {
        "state": _aggregate_health_state(spaces),
        "count": len(spaces),
        "spaces": spaces,
        "labels": {
            "state": "Fresh: LIVE only when every app is reachable and HF reports RUNNING; otherwise DEGRADED or UNAVAILABLE. TTL reuse is CACHED with cached_state.",
            "space_state": "LIVE requires app_reachable:true plus HF stage RUNNING; partial evidence is DEGRADED",
            "stage": "HF API runtime.stage (https://huggingface.co/api/spaces/SZLHOLDINGS/<name>)",
            "app_reachable": "REAL server-side HEAD/GET probe of the canonical Space app",
            "degrade": "stage:'unknown' + app_reachable:false; never fabricated",
        },
        "note": "Server-side probed; 0 browser CDN. Honest LIVE/DEGRADED/UNAVAILABLE; cache reuse is explicitly CACHED.",
        "doctrine": _DOCTRINE,
        "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _HEALTH_CACHE["payload"] = payload
    _HEALTH_CACHE["ts"] = now
    return payload


# ---------------------------------------------------------------------------
# Tiles page — pure inline markup, 0 CDN. Status dots are filled by a tiny inline
# fetch of the SAME-ORIGIN /api/<ns>/v1/spaces/health (our own server-side-probed
# endpoint, not a CDN). Cards are pre-rendered so the page is useful even with JS off.
# ---------------------------------------------------------------------------
def _tiles_page(ns: str) -> bytes:
    cards = []
    for sp in SPACES:
        name = sp["name"]
        slug = sp["slug"]
        title = sp["title"]
        primary = canonical_url(name)
        primary_label = "Open isolated app"
        cards.append(
            '<article class="sp-card" data-space="%s">'
            '<header class="sp-head">'
            '<span class="sp-dot" data-dot="%s" title="status">&#9679;</span>'
            '<h2 class="sp-title">%s</h2></header>'
            '<div class="sp-kind">%s &middot; %s</div>'
            '<div class="sp-stage" data-stage="%s">stage: <span>checking&hellip;</span></div>'
            '<div class="sp-links">'
            '<a class="sp-open" href="%s" rel="noopener" target="_blank">%s &#8599;</a>'
            '<a class="sp-hf" href="%s" rel="noopener" target="_blank">View repository &#8599;</a>'
            '</div></article>'
            % (slug, slug, title, name, sp["sdk"], slug,
               primary, primary_label, hf_repo_url(name))
        )
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Spaces &middot; ' + ns + '</title>'
        '<style>'
        ':root{color-scheme:dark}'
        '*{box-sizing:border-box}'
        'body{margin:0;background:#0b0f14;color:#cdd6e0;'
        'font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}'
        '.sp-wrap{max-width:1100px;margin:0 auto;padding:2rem 1.25rem;min-width:0}'
        '.sp-h1{color:#e7eef6;font-size:1.6rem;margin:0 0 .25rem}'
        '.sp-sub{color:#8a96a3;margin:0 0 .75rem;overflow-wrap:anywhere}'
        '.sp-health{display:flex;align-items:center;gap:.45rem;min-height:44px;'
        'color:#8a96a3;margin:0 0 1rem}'
        '.sp-health strong{border:1px solid #3b4654;border-radius:999px;padding:.22rem .55rem;'
        'color:#9fb0c0;font-size:.76rem;letter-spacing:.04em}'
        '.sp-health strong.live{border-color:#3ad07a;color:#3ad07a}'
        '.sp-health strong.degraded{border-color:#c9a23a;color:#c9a23a}'
        '.sp-health strong.unavailable{border-color:#e0593a;color:#e0593a}'
        '.sp-health strong.cached,.sp-health strong.checking{border-color:#697787;color:#9fb0c0}'
        '.sp-grid{display:grid;gap:1rem;min-width:0;'
        'grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}'
        '.sp-card{background:#121821;border:1px solid #1d2632;border-radius:12px;'
        'padding:1rem 1.1rem;display:flex;flex-direction:column;gap:.5rem;min-width:0}'
        '.sp-head{display:flex;align-items:center;gap:.55rem;min-width:0}'
        '.sp-dot{color:#5b6675;font-size:.7rem;line-height:1}'
        '.sp-dot.up{color:#3ad07a}.sp-dot.down{color:#e0593a}.sp-dot.unknown{color:#c9a23a}'
        '.sp-title{font-size:1rem;margin:0;color:#e7eef6;font-weight:600;min-width:0;overflow-wrap:anywhere}'
        '.sp-kind{color:#697787;font-size:.76rem;overflow-wrap:anywhere}'
        '.sp-stage{color:#7c8794;font-size:.82rem;overflow-wrap:anywhere}'
        '.sp-stage span{color:#9fb0c0}'
        '.sp-links{margin-top:auto;display:flex;gap:.9rem;flex-wrap:wrap;padding-top:.4rem}'
        '.sp-links a{display:inline-flex;align-items:center;min-height:44px;padding:.4rem .15rem}'
        '.sp-open{color:#d4a444;text-decoration:none;font-weight:600}'
        '.sp-hf{color:#7c8794;text-decoration:none}'
        '.sp-foot{color:#5b6675;font-size:.8rem;margin-top:1.6rem;overflow-wrap:anywhere}'
        '@media(max-width:375px){'
        '.sp-wrap{padding:1.25rem .75rem}.sp-grid{grid-template-columns:minmax(0,1fr)}'
        '.sp-links{gap:.15rem}.sp-links a{flex:1 1 100%}}'
        '</style></head>'
        '<body><main class="sp-wrap">'
        '<h1 class="sp-h1">Hugging Face Spaces</h1>'
        '<p class="sp-sub">All 26 audited Spaces in one evidence-labelled registry. '
        'Apps open on their canonical isolated Hugging Face origin; health is probed '
        'server-side. Legacy <code>/spaces/&lt;slug&gt;</code> links are no-store 307 handoffs.</p>'
        '<p class="sp-health">Estate health: '
        '<strong id="sp-estate-health" class="checking" aria-live="polite">CHECKING</strong></p>'
        '<div class="sp-grid">' + "".join(cards) + '</div>'
        '<p class="sp-foot">Status dot &amp; stage are filled from the same-origin '
        '<code>/api/' + ns + '/v1/spaces/health</code> endpoint (real server-side probe '
        '+ HF API). Honest: a grey/amber dot means starting or unknown, never a faked up.</p>'
        '</main>'
        '<script>'
        '(function(){'
        'var estate=document.getElementById("sp-estate-health");'
        'function estateState(raw,cached){'
        'var allowed={LIVE:1,DEGRADED:1,UNAVAILABLE:1,CACHED:1};'
        'raw=String(raw||"UNAVAILABLE").toUpperCase();if(!allowed[raw])raw="UNAVAILABLE";'
        'var label=raw;if(raw==="CACHED")label="CACHED \\u00b7 "+String(cached||"UNAVAILABLE").toUpperCase()+" snapshot";'
        'if(estate){estate.className=raw.toLowerCase();estate.textContent=label;}}'
        'function healthUnavailable(){estateState("UNAVAILABLE");'
        'var cards=document.querySelectorAll(".sp-card");for(var i=0;i<cards.length;i++){'
        'var dot=cards[i].querySelector(".sp-dot");if(dot){dot.classList.remove("up","unknown");'
        'dot.classList.add("down");dot.title="UNAVAILABLE / health fetch failed";}'
        'var st=cards[i].querySelector(".sp-stage span");if(st)st.textContent="UNAVAILABLE \\u00b7 health fetch failed";}}'
        'fetch("/api/' + ns + '/v1/spaces/health").then(function(r){'
        'if(!r.ok)throw new Error("health "+r.status);return r.json();})'
        '.then(function(d){estateState(d.state,d.cached_state);(d.spaces||[]).forEach(function(s){'
        'var card=document.querySelector(\'[data-space="\'+(s.slug||s.name)+\'"]\');if(!card)return;'
        'var dot=card.querySelector(".sp-dot");'
        'var stage=String(s.stage||"unknown").toUpperCase();'
        'var state=String(s.state||((s.app_reachable&&stage==="RUNNING")?"LIVE":'
        '((s.app_reachable||stage!=="UNKNOWN")?"DEGRADED":"UNAVAILABLE"))).toUpperCase();'
        'if(state!=="LIVE"&&state!=="DEGRADED"&&state!=="UNAVAILABLE")state="UNAVAILABLE";'
        'if(dot){dot.classList.remove("up","down","unknown");'
        'dot.classList.add(state==="LIVE"?"up":(state==="DEGRADED"?"unknown":"down"));'
        'dot.title=state+" / "+(s.app_reachable?"reachable":"unreachable")+" / stage:"+(s.stage||"unknown");}'
        'var st=card.querySelector(".sp-stage span");'
        'if(st){st.textContent=state+" \\u00b7 "+(s.stage||"unknown")+'
        '(s.app_reachable?" \\u00b7 reachable":" \\u00b7 unreachable");}'
        '});}).catch(healthUnavailable);'
        '})();'
        '</script>'
        '</body></html>'
    )
    return html.encode("utf-8")


# ---------------------------------------------------------------------------
# Nav injector — ONE "Spaces" nav item into the console left-nav. Same additive,
# idempotent BaseHTTPMiddleware idiom as a11oy_nav_wireup / killinchu_nav_wireup.
# ---------------------------------------------------------------------------
_NAV_MARKER = b'data-nav-spaces="hf1"'
_FOOT_ANCHOR = b'<div class="side-foot">'
_GROUP_ANCHOR = b'<div class="nav-group">'
_NAVITEM_ANCHOR = b'<div class="nav-item"'


def _nav_item() -> bytes:
    """ONE 'Spaces' nav item, mirroring the console's own nav-item markup so it inherits
    the console styling (0 CDN, 0 codename). Globe glyph; honest label."""
    return (
        '<a class="nav-item" data-nav-spaces="hf1" data-wireup-path="/spaces" '
        'href="/spaces" style="cursor:pointer;text-decoration:none">'
        '<span class="ico">\U0001F310</span>Spaces</a>'
    ).encode("utf-8")


def _make_injector():
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response

    nav_item = _nav_item()

    class _SpacesNavInjector(BaseHTTPMiddleware):
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
                # The /spaces tiles page IS our own page; don't inject the sidebar nav
                # into it (it has no console sidebar). Cheap guard — also keeps it idempotent.
                if p == "/spaces" or p.startswith("/spaces/"):
                    return resp

                body = b""
                async for chunk in resp.body_iterator:
                    body += chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode()

                if _NAV_MARKER not in body:
                    if _FOOT_ANCHOR in body:
                        body = body.replace(_FOOT_ANCHOR, nav_item + _FOOT_ANCHOR, 1)
                    elif _NAVITEM_ANCHOR in body:
                        # No footer found, but a nav exists -> place after the first
                        # nav-item div so 'Spaces' still lands in the nav.
                        start = body.find(_NAVITEM_ANCHOR)
                        end = body.find(b"</div>", start)
                        if end != -1:
                            end += len(b"</div>")
                            body = body[:end] + nav_item + body[end:]
                    elif _GROUP_ANCHOR in body:
                        body = body.replace(_GROUP_ANCHOR, _GROUP_ANCHOR + nav_item, 1)

                # body_iterator is consumed — MUST rebuild the Response even if unchanged,
                # else downstream sees an empty body (white screen).
                headers = dict(resp.headers)
                headers.pop("content-length", None)
                return Response(content=body, status_code=resp.status_code,
                                headers=headers, media_type="text/html")
            except Exception:
                return resp

    return _SpacesNavInjector


def register(app, ns: str = "a11oy") -> str:
    """ADDITIVE: mount GET /api/<ns>/v1/spaces/health + GET/HEAD /spaces (rich tiles)
    at the FRONT of the router (beat the SPA + Node-proxy catch-alls), and attach the
    idempotent 'Spaces' nav injector. try/except-guarded by the caller."""
    try:
        from starlette.responses import Response, JSONResponse as _JSON
    except Exception as e:  # pragma: no cover
        return "unavailable: %r" % (e,)

    n_before = len(app.router.routes)
    tiles = _tiles_page(ns)

    async def _health(request):
        payload = await spaces_health()
        return _JSON(payload, headers={"Cache-Control": "no-store"})

    async def _tiles(request):
        headers = {"Cache-Control": "no-store"}
        if request.method.upper() == "HEAD":
            return Response(content=b"", status_code=200, media_type="text/html", headers=headers)
        return Response(content=tiles, status_code=200, media_type="text/html", headers=headers)

    from starlette.routing import Route
    routes = [
        Route("/api/%s/v1/spaces/health" % ns, _health, methods=["GET"]),
        # The rich tiles page OWNS /spaces (wins over szl_spaces_proxy's fallback index
        # because this module is registered SECOND and front-inserts after it).
        Route("/spaces", _tiles, methods=["GET", "HEAD"]),
    ]
    for r in routes:
        app.router.routes.append(r)

    new = app.router.routes[n_before:]
    del app.router.routes[n_before:]
    app.router.routes[0:0] = new

    app.add_middleware(_make_injector())

    print("[%s] Spaces surface registered: /api/%s/v1/spaces/health + /spaces (tiles, "
          "%d spaces) + nav injector [moved %d routes to front]"
          % (ns, ns, len(SPACES), len(new)), file=sys.stderr)
    return "ok: %d spaces, health + tiles + nav, %d routes" % (len(SPACES), len(new))


# ---------------------------------------------------------------------------
# Self-test — pure stdlib + starlette TestClient; no real network. Stubs the shared
# client to assert: health degrades honestly (no client -> stage unknown + reachable
# false), tiles page lists ALL 26 names + has the health-fetch JS, nav injects exactly
# once + is idempotent + removes nothing, /spaces is NOT nav-injected.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import ast as _ast
    with open(__file__, "r", encoding="utf-8") as _fh:
        _ast.parse(_fh.read())

    assert len(SPACES) == 26, len(SPACES)
    tp = _tiles_page("a11oy")
    for sp in SPACES:
        assert sp["name"].encode() in tp, "tiles missing %s" % sp["name"]
        assert sp["title"].encode() in tp, "tiles missing title %s" % sp["title"]
        assert canonical_url(sp["name"]).encode() in tp, "tiles missing canonical app origin"
        assert hf_repo_url(sp["name"]).encode() in tp, "tiles missing repository link"
        assert proxy_url(sp["name"]) == canonical_url(sp["name"]), "primary link must stay isolated"
    assert b"/api/a11oy/v1/spaces/health" in tp, "tiles must fetch the health endpoint"
    assert b"http://" not in tp, "tiles must be 0 CDN (no http://)"
    assert b'href="/spaces/' not in tp, "tiles must not execute an app under this origin"
    assert b"canonical isolated Hugging Face origin" in tp
    # Repository anchors are navigation only; no browser asset is loaded from HF.
    assert tp.count(b"https://huggingface.co/spaces/") == len(SPACES)
    assert b'<script src="https://' not in tp and b'<link href="https://' not in tp

    running = {"app_reachable": True, "app_status": 200, "stage": "RUNNING"}
    unknown = {"app_reachable": False, "stage": "unknown"}
    http_200_unknown = {"app_reachable": True, "app_status": 200, "stage": "unknown"}
    assert _aggregate_health_state([running, dict(running)]) == "LIVE"
    assert _aggregate_health_state([unknown, dict(unknown)]) == "UNAVAILABLE"
    assert _aggregate_health_state([running, unknown]) == "DEGRADED"
    assert _aggregate_health_state([http_200_unknown]) == "DEGRADED", \
        "HTTP 200 alone must never upgrade aggregate state to LIVE"
    assert _space_health_state(running) == "LIVE"
    assert _space_health_state(unknown) == "UNAVAILABLE"
    assert _space_health_state(http_200_unknown) == "DEGRADED"

    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, PlainTextResponse
    from starlette.routing import Route as _R
    from starlette.testclient import TestClient

    SAMPLE_CONSOLE = (
        '<html><body><aside>'
        '<div class="nav-group">Operate</div>'
        '<div class="nav-item" data-view="x" onclick="go(\'x\')">'
        '<span class="ico">+</span>Existing</div>'
        '<div class="side-foot">footer</div>'
        '</aside></body></html>'
    )

    async def _console(req):
        return HTMLResponse(SAMPLE_CONSOLE)

    app = Starlette(routes=[
        _R("/console", _console),
        _R("/{full_path:path}", lambda req: PlainTextResponse("SPA")),
    ])
    st = register(app, ns="a11oy")
    assert st.startswith("ok:"), st
    c = TestClient(app)

    # health: no httpx client wired -> falls back to the stdlib urllib probe. Stub that
    # final outbound path so this self-test is hermetic and verifies the exact honest
    # degrade contract for every audited Space (no network, no fabricated green state).
    _self_mod = sys.modules[__name__]
    _orig_probe = _self_mod._urllib_probe
    def _offline(*_a, **_k):
        raise OSError("simulated offline audit")
    _self_mod._urllib_probe = _offline
    _HEALTH_CACHE["ts"] = 0.0
    _HEALTH_CACHE["payload"] = None
    try:
        health_response = c.get("/api/a11oy/v1/spaces/health")
        h = health_response.json()
    finally:
        _self_mod._urllib_probe = _orig_probe
        _HEALTH_CACHE["ts"] = 0.0
        _HEALTH_CACHE["payload"] = None
    assert h["count"] == 26, h["count"]
    assert h["state"] == "UNAVAILABLE", h["state"]
    assert health_response.headers["cache-control"] == "no-store"
    for s in h["spaces"]:
        assert s["app_reachable"] is False, "offline probe must honestly degrade false"
        assert s["stage"] == "unknown", "offline HF API must honestly degrade unknown"
        assert s["state"] == "UNAVAILABLE", "offline row must fail closed"
    assert h["doctrine"]["locked_proven"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]

    # tiles page resolves + lists all names
    t = c.get("/spaces")
    assert t.status_code == 200 and "text/html" in t.headers["content-type"], t.status_code
    assert t.headers["cache-control"] == "no-store"
    for sp in SPACES:
        assert sp["name"] in t.text, "tiles page missing %s" % sp["name"]

    # nav injects exactly once + idempotent + removes nothing
    p1 = c.get("/console").text
    p2 = c.get("/console").text
    assert p1.count('data-nav-spaces="hf1"') == 1, "nav must inject exactly once"
    assert p2.count('data-nav-spaces="hf1"') == 1, "nav must be idempotent"
    assert 'href="/spaces"' in p1, "nav must link /spaces with a real anchor"
    assert "Operate</div>" in p1 and "Existing</div>" in p1 and "footer</div>" in p1, \
        "must remove nothing from the SPA source"
    assert p1 == p2, "second console render must be byte-identical (idempotent)"
    # the tiles page itself must NOT be nav-injected (it has no console sidebar)
    assert 'data-nav-spaces="hf1"' not in c.get("/spaces").text, "/spaces must not be nav-injected"

    print("szl_spaces_surface: ALL OK (26 canonical isolated links; honest degrade; "
          "tiles 0-CDN + no-store; nav idempotent + additive; /spaces not self-injected)")
