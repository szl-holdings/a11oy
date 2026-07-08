#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_frontier_index.py — Frontier INDEX: an honest, self-auditing catalog of the
whole ecosystem of frontier surfaces.

GET /api/a11oy/v1/frontier-index/catalog ENUMERATES every registered frontier surface
and, for each one, reports:

  * id            — the surface id (from the app's OWN surface registry)
  * title         — the human title (from the same registry)
  * category      — the surface category (map / attention / proof / brain / ...)
  * backend       — "a11oy-native" when a local /api/{ns}/v1 route for this surface is
                    registered AND actually answers in-process with an honest label;
                    "cross-origin-fallback" when a route exists but does not answer with
                    an a11oy honest label (e.g. a proxy to another origin that 502s);
                    "frontend-only" when no local backend route is registered at all.
  * label         — the honest data label the surface's OWN backend ACTUALLY emits right
                    now (LIVE / MEASURED / MODELED / SAMPLE / SIMULATED / CACHED / PROVEN
                    / CONJECTURE / ROADMAP / DEGRADED / REPLAY / UNAVAILABLE / ...). Read
                    VERBATIM from the live response — never upgraded, never fabricated.
  * citations     — the cited paper(s) (arXiv ids / DOIs) the backend itself declares in
                    its response, if any.
  * endpoint      — the exact registered route the label was read from (or null).

HONEST BY CONSTRUCTION — the whole point of this surface. The catalog is NOT a hand-
maintained list that can drift. It is derived at request time from two live sources in the
running app:

  1. the app's own surface registry (``szl3d_holographic.SURFACES``) — imported in-process,
     so it can never diverge from the 3D shell / holographic UI; and
  2. the FastAPI app's registered routes (``app.routes``) + each surface's OWN response —
     probed in-process — so "a11oy-native vs cross-origin-fallback" and the honest label are
     the GROUND TRUTH of what is wired, not an assertion typed into this file.

A companion CI honesty guard (.github/scripts/frontier_index_honesty_check.py) re-derives
each label independently and FAILS the build if the catalog ever claims a label a surface's
backend does not actually emit. This module therefore stays honest automatically.

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17; touches
    no locked formula and no kernel.
  - Λ stays Conjecture 1 (advisory); introduces no theorem, no green/1.0, no proof of Λ.
    Trust ceiling 0.97, never 100%.
  - PURE READ. Signs nothing, mints nothing on a GET (receipts belong on writes).
  - No label is ever upgraded: a surface's MODELED stays MODELED; a down/proxy surface is
    honestly UNAVAILABLE, never relabeled OK.
  - Additive route, registered before the SPA catch-all; canonical domain a-11-oy.com;
    0 runtime CDN.
"""

import datetime
import re
from typing import Any

# Honesty-label vocabulary (doctrine v11). Tests grep these exact strings. This is the
# ALLOWED set a surface's backend may emit; the catalog reports whichever one the backend
# actually returns, never a token outside this set.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)
# The self label of this ecosystem surface itself.
MODELED = "MODELED"
UNAVAILABLE = "UNAVAILABLE"

# Backend-kind vocabulary.
NATIVE = "a11oy-native"
FALLBACK = "cross-origin-fallback"
FRONTEND = "frontend-only"

TRUST_CEILING = 0.97

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "frontierindex"

# arXiv id / DOI patterns, so citations are harvested from whatever a backend declares
# in-band rather than re-typed here (drift-proof).
_ARXIV = re.compile(r"arXiv:\d{4}\.\d{4,5}(?:v\d+)?", re.IGNORECASE)
_DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")

# Ordered candidate endpoint suffixes tried per surface when probing for its honest label.
# All are READ-only shapes (health / status / info / manifest / summary / limits / bare id
# / frontier tile). We stop at the first that answers 200 with a recognized honest label.
_CANDIDATE_SUFFIXES = (
    "/health", "/healthz", "/status", "/info", "/manifest", "/summary",
    "/limits", "/state", "",
)

_API_PREFIX_TMPL = "/api/{ns}/v1"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _norm(token: str) -> str:
    """Normalize an id / path segment for matching: lowercase, drop non-alphanumerics."""
    return re.sub(r"[^a-z0-9]", "", (token or "").lower())


def _primary_label(*values: Any) -> str | None:
    """Return the FIRST honest-vocabulary token that appears in any of the given label-ish
    values (a label may be compound, e.g. 'MODELED/SIMULATED — not hardware'; we take the
    earliest-occurring vocabulary token). Read verbatim; never invented."""
    for val in values:
        if not isinstance(val, str):
            continue
        up = val.upper()
        best_pos, best_tok = None, None
        for tok in HONEST_LABELS:
            i = up.find(tok)
            if i >= 0 and (best_pos is None or i < best_pos):
                best_pos, best_tok = i, tok
        if best_tok:
            return best_tok
    return None


def _extract_label(payload: dict) -> str | None:
    """Pull the honest label a backend response declares, checking the conventional keys
    (label / claim / data_label / doctrine.label_top) in priority order."""
    if not isinstance(payload, dict):
        return None
    doctrine = payload.get("doctrine") if isinstance(payload.get("doctrine"), dict) else {}
    return _primary_label(
        payload.get("label"),
        payload.get("data_label"),
        payload.get("claim"),
        doctrine.get("label_top") if isinstance(doctrine, dict) else None,
    )


def _extract_citations(payload: Any, limit: int = 12) -> list[str]:
    """Harvest cited arXiv ids / DOIs the backend itself declares anywhere in its response.
    Deduped, order-preserving, bounded. If a backend cites nothing, returns []."""
    try:
        import json as _json
        blob = _json.dumps(payload, default=str)
    except Exception:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for m in list(_ARXIV.finditer(blob)) + list(_DOI.finditer(blob)):
        tok = m.group(0).rstrip(".,;")
        key = tok.lower()
        if key not in seen:
            seen.add(key)
            found.append(tok)
        if len(found) >= limit:
            break
    return found


# ---------------------------------------------------------------------------
# Route introspection — GROUND TRUTH of what is actually wired.
# ---------------------------------------------------------------------------

def _registered_get_paths(app, ns: str) -> list[str]:
    """Every registered GET route path under /api/{ns}/v1 (the running app's truth)."""
    prefix = _API_PREFIX_TMPL.format(ns=ns)
    paths: set[str] = set()
    for r in getattr(app, "routes", []) or []:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None) or set()
        if not path or not path.startswith(prefix):
            continue
        if methods and "GET" not in methods:
            continue
        paths.add(path)
    return sorted(paths)


def _surface_routes(surface_id: str, get_paths: list[str], ns: str) -> list[str]:
    """Registered GET routes that belong to `surface_id` — a route whose path has a SEGMENT
    equal (normalized) to the surface id. Segment-equality (not substring) so 'frontier'
    does not swallow '/frontier-index/...' and 'ssm' does not match 'hybridssm'."""
    prefix = _API_PREFIX_TMPL.format(ns=ns)
    want = _norm(surface_id)
    hits: list[str] = []
    for p in get_paths:
        rest = p[len(prefix):].strip("/")
        segs = [s for s in rest.split("/") if s and not s.startswith("{")]
        if any(_norm(s) == want for s in segs):
            hits.append(p)
    # Shortest / fewest-segment routes first — the representative read endpoints.
    return sorted(hits, key=lambda p: (p.count("/"), len(p)))


def _pick_probe_endpoints(surface_id: str, routes: list[str], ns: str) -> list[str]:
    """From a surface's registered GET routes, choose an ordered, de-duplicated list of
    PARAM-FREE endpoints to probe for the honest label, most-likely-labeled first."""
    prefix = _API_PREFIX_TMPL.format(ns=ns)
    param_free = [p for p in routes if "{" not in p]
    scored: list[tuple[int, str]] = []
    for p in param_free:
        tail = p[len(prefix):]
        score = len(_CANDIDATE_SUFFIXES)  # default (unranked) — after the known suffixes
        for i, suf in enumerate(_CANDIDATE_SUFFIXES):
            if suf and tail.endswith(suf):
                score = i
                break
            if suf == "" and _norm(tail.rstrip("/").split("/")[-1]) == _norm(surface_id):
                score = len(_CANDIDATE_SUFFIXES) - 1
        scored.append((score, p))
    scored.sort(key=lambda t: (t[0], t[1].count("/"), len(t[1])))
    out: list[str] = []
    for _, p in scored:
        if p not in out:
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# In-process label probe — read each surface's OWN response, honestly.
#
# We invoke each surface's registered endpoint CALLABLE directly (never a nested
# HTTP client): starlette's BaseHTTPMiddleware is re-entrancy-hostile, so driving a
# TestClient from inside a live request corrupts the outer request. Calling the route
# function directly reads the surface's OWN honest label without touching the ASGI /
# middleware stack — which is exactly the ground truth we want. Every call is bounded by
# a worker-thread timeout so a proxy endpoint that reaches for the network cannot hang the
# catalog; on timeout / error the surface degrades to the honest "no label" outcome.
# ---------------------------------------------------------------------------

def _get_route(app, path: str):
    """Return the registered GET route object whose path == `path` (or None)."""
    for r in getattr(app, "routes", []) or []:
        if getattr(r, "path", None) == path:
            methods = getattr(r, "methods", None) or set()
            if not methods or "GET" in methods:
                return r
    return None


def _synthetic_request(app, path: str):
    """A minimal read-only Starlette Request, so endpoints that take a `Request` (for
    headers / query) can be invoked directly. Body is empty; this is a pure GET."""
    from starlette.requests import Request

    scope = {
        "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": [], "server": ("frontier-index", 80), "client": ("frontier-index", 0),
        "app": app,
    }

    async def _receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive=_receive)


def _invoke_route(app, route, path: str, timeout: float):
    """Invoke a route's endpoint callable directly, bounded by `timeout` seconds, and return
    its decoded JSON payload (dict) or None. Supplies a synthetic Request for a `Request`
    parameter; if any other argument is required (path/query params we cannot safely
    fabricate) we decline and return None so the surface is classified honestly."""
    import inspect
    import json as _json

    fn = getattr(route, "endpoint", None)
    if fn is None or not callable(fn):
        return None
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None

    from starlette.requests import Request as _Req
    kwargs: dict[str, Any] = {}
    for p in sig.parameters.values():
        if p.default is not inspect.Parameter.empty:
            continue
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if p.annotation is _Req or p.name in ("req", "request"):
            kwargs[p.name] = _synthetic_request(app, path)
        else:
            return None  # needs an arg we won't fabricate -> decline (honest)

    def _work():
        import asyncio as _aio
        if inspect.iscoroutinefunction(fn):
            return _aio.run(fn(**kwargs))
        res = fn(**kwargs)
        if inspect.isawaitable(res):
            return _aio.run(res)
        return res

    import concurrent.futures as _cf
    try:
        with _cf.ThreadPoolExecutor(max_workers=1) as ex:
            res = ex.submit(_work).result(timeout=timeout)
    except Exception:
        return None

    if isinstance(res, dict):
        return res
    body = getattr(res, "body", None)
    if body is None:
        return None
    try:
        payload = _json.loads(body)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _probe_label(app, endpoints: list[str], timeout: float = 3.0
                 ) -> tuple[str | None, str | None, list[str], bool]:
    """Probe candidate endpoints by invoking their route callables directly and return
    (label, endpoint_used, citations, any_ok). Fully guarded: a slow/error endpoint never
    raises — it degrades to the honest "no label" outcome."""
    any_ok = False
    for ep in endpoints:
        route = _get_route(app, ep)
        if route is None:
            continue
        payload = _invoke_route(app, route, ep, timeout)
        if payload is None:
            continue
        any_ok = True
        label = _extract_label(payload)
        if label:
            return label, ep, _extract_citations(payload), True
    return None, None, [], any_ok


def _classify_surface(app, surface: dict, get_paths: list[str], ns: str) -> dict:
    """Build one honest catalog entry for a single surface, introspected live."""
    sid = surface.get("id", "")
    title = surface.get("title", sid)
    category = surface.get("cat", surface.get("category"))
    entry = {
        "id": sid,
        "title": title,
        "category": category,
        "backend": FRONTEND,
        "label": UNAVAILABLE,
        "citations": [],
        "endpoint": None,
        "routes_registered": 0,
    }

    # This surface itself: probe its own /health only (never /catalog -> no recursion).
    if _norm(sid) == _norm(SURFACE_ID):
        probe = [f"/api/{ns}/v1/frontier-index/health"]
        routes = probe
    else:
        routes = _surface_routes(sid, get_paths, ns)
        probe = _pick_probe_endpoints(sid, routes, ns)

    entry["routes_registered"] = len(routes)

    if not routes:
        # No local /api route at all -> the 3D surface renders MODELED/cross-origin in the
        # client; there is no a11oy-native backend to report a label. Honest FRONTEND.
        entry["backend"] = FRONTEND
        entry["label"] = UNAVAILABLE
        entry["note"] = "no a11oy-native /api route registered; client-side surface"
        return entry

    label, used_ep, citations, any_200 = _probe_label(app, probe)
    if label:
        entry["backend"] = NATIVE
        entry["label"] = label            # VERBATIM from the backend — never upgraded.
        entry["endpoint"] = used_ep
        entry["citations"] = citations
    elif any_200:
        # A route answered 200 but emitted no recognized honest label (e.g. an aggregate
        # endpoint). Native backend present, label honestly UNLABELED.
        entry["backend"] = NATIVE
        entry["label"] = UNAVAILABLE
        entry["endpoint"] = probe[0] if probe else None
        entry["note"] = "native route answered 200 but declared no top-level honest label"
    else:
        # Route(s) exist but none answered with an a11oy honest label -> a proxy / cross-
        # origin fallback that is not answering natively right now. Honest, not faked.
        entry["backend"] = FALLBACK
        entry["label"] = UNAVAILABLE
        entry["endpoint"] = probe[0] if probe else (routes[0] if routes else None)
        entry["note"] = ("route registered but no a11oy-native honest label emitted "
                         "in-process (cross-origin/proxy fallback)")
    return entry


# ---------------------------------------------------------------------------
# Catalog assembly (cached, honest, pure read).
# ---------------------------------------------------------------------------

_CATALOG_TTL = 30.0  # seconds


def _surface_registry() -> list[dict]:
    """The app's OWN surface registry, imported in-process (never re-typed here)."""
    import szl3d_holographic as holo
    surfaces = getattr(holo, "SURFACES", None)
    if not isinstance(surfaces, list):
        return []
    return [s for s in surfaces if isinstance(s, dict) and s.get("id")]


def _build_catalog(app, ns: str = "a11oy") -> dict:
    surfaces = _surface_registry()
    get_paths = _registered_get_paths(app, ns) if app is not None else []

    entries: list[dict] = []
    for s in surfaces:
        try:
            entries.append(_classify_surface(app, s, get_paths, ns))
        except Exception as exc:  # noqa: BLE001 — degrade this ONE entry, never the catalog
            entries.append({
                "id": s.get("id"), "title": s.get("title", s.get("id")),
                "category": s.get("cat"), "backend": FRONTEND, "label": UNAVAILABLE,
                "citations": [], "endpoint": None, "routes_registered": 0,
                "note": f"introspection failed for this surface, reported honestly: {exc}",
            })

    backend_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    cited = 0
    for e in entries:
        backend_counts[e["backend"]] = backend_counts.get(e["backend"], 0) + 1
        label_counts[e["label"]] = label_counts.get(e["label"], 0) + 1
        if e.get("citations"):
            cited += 1

    return {
        "ok": True,
        "endpoint": "frontier-index/catalog",
        "service": "a11oy.frontier.index",
        "title": "Frontier Index — honest ecosystem catalog + self-audit",
        "label": MODELED,
        "what": ("an honest, self-auditing enumeration of every registered frontier surface "
                 "with the data label its OWN backend actually emits, its cited paper(s), and "
                 "whether it is a11oy-native or a cross-origin fallback. Derived live from the "
                 "app's surface registry + registered routes + each surface's own response — "
                 "never a hand-maintained list that can drift."),
        "introspection": {
            "surface_registry": "szl3d_holographic.SURFACES (imported in-process)",
            "route_source": f"app.routes under /api/{ns}/v1 (GET)",
            "label_source": "each surface's own in-process response (VERBATIM, never upgraded)",
            "api_routes_seen": len(get_paths),
        },
        "doctrine": {
            "label_top": MODELED,
            "locked_proven": 8,
            "locked_set": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
            "kernel_commit": "c7c0ba17",
            "adds_to_locked_8": 0,
            "lambda": "Conjecture 1",
            "khipu_bft": "Conjecture 2",
            "trust_ceiling": TRUST_CEILING,
            "trust_100_percent": False,
            "runtime_cdn": 0,
            "note": ("additive read-only surface; touches no locked formula and no kernel; "
                     "signs/mints nothing on a GET; introduces no theorem, no green/1.0."),
        },
        "labels_legend": {
            "a11oy-native": "a local /api route for this surface answered in-process with an honest label",
            "cross-origin-fallback": "route registered but no a11oy-native honest label emitted (proxy/other origin)",
            "frontend-only": "no local /api route; the surface renders client-side (MODELED/cross-origin)",
        },
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "summary": {
            "surfaces": len(entries),
            "backend_counts": backend_counts,
            "label_counts": label_counts,
            "surfaces_with_citations": cited,
        },
        "surfaces": entries,
        "timestamp_utc": _now_iso(),
    }


def build_catalog(app, ns: str = "a11oy") -> dict:
    """Cached entrypoint. Serves the last real catalog for _CATALOG_TTL seconds so a GET does
    not re-probe every surface on every hit. The cache only ever holds real output."""
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    cache = getattr(build_catalog, "_cache", None)
    if cache is not None:
        ts, val = cache
        if (now - ts) < _CATALOG_TTL:
            return val
    val = _build_catalog(app, ns)
    build_catalog._cache = (now, val)  # type: ignore[attr-defined]
    return val


def handle_catalog(app, ns: str = "a11oy") -> dict:
    """GET /frontier-index/catalog — handler used by FastAPI and __main__."""
    try:
        return build_catalog(app, ns)
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False,
            "endpoint": "frontier-index/catalog",
            "label": UNAVAILABLE,
            "error": str(exc),
            "doctrine": "v11: catalog unavailable; no fabricated surface/label emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_health() -> dict:
    """GET /frontier-index/health — a tiny, side-effect-free, self-describing health tile
    (also the endpoint the catalog probes for THIS surface, so it never recurses)."""
    return {
        "ok": True,
        "endpoint": "frontier-index/health",
        "service": "a11oy.frontier.index",
        "label": MODELED,
        "surface_id": SURFACE_ID,
        "doctrine": {"lambda": "Conjecture 1", "locked_proven": 8, "trust_ceiling": TRUST_CEILING},
        "timestamp_utc": _now_iso(),
    }


# ---------------------------------------------------------------------------
# FastAPI router registration — mirrors szl_frontier_manifest.register().
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the frontier-index endpoints on the FastAPI ``app``. Returns a status string.

    The catalog handler is a SYNC def so FastAPI runs it in a worker thread — that lets the
    in-process TestClient probe (which drives its own event loop) run safely."""
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/frontier-index"

    @app.get(f"{base}/catalog")
    def _frontier_index_catalog():
        """Honest ecosystem catalog: every surface's id, title, backend kind, the label its
        own backend emits, and cited papers — introspected live from the running app."""
        return JSONResponse(handle_catalog(app, ns))

    @app.get(f"{base}/health")
    def _frontier_index_health():
        """Self-describing health tile (also the self-probe endpoint; never recurses)."""
        return JSONResponse(handle_health())

    return "frontier-index-wired:2"


# ---------------------------------------------------------------------------
# Self-test — honest labels, real introspection, no upgrade, no fabrication.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json
    import sys as _sys

    print("=" * 72)
    print("szl_frontier_index — self-test (honest ecosystem catalog + introspection)")
    print("=" * 72)

    # Build a real app with a couple of representative surfaces wired, then introspect it.
    from fastapi import FastAPI
    app = FastAPI()
    register(app, ns="a11oy")
    try:
        import szl_frontier_zkinfer as _zk
        _zk.register(app, ns="a11oy")
    except Exception as _e:  # pragma: no cover
        print(f"(zkinfer not wired for self-test: {_e!r})")

    cat = handle_catalog(app, ns="a11oy")
    blob = _json.dumps(cat)

    # 1) it enumerated the app's OWN surface registry (non-trivial), ok:true.
    assert cat["ok"] is True
    assert cat["endpoint"] == "frontier-index/catalog"
    surfaces = cat["surfaces"]
    assert len(surfaces) >= 50, f"expected the full surface registry, got {len(surfaces)}"
    print(f"[1] enumerated {len(surfaces)} surfaces from the app's own registry, ok:true  OK")

    # 2) every surface carries an honest backend kind + a label from the allowed vocabulary.
    kinds = {NATIVE, FALLBACK, FRONTEND}
    vocab = set(HONEST_LABELS)
    for e in surfaces:
        assert e["backend"] in kinds, f"{e['id']}: bad backend kind {e['backend']}"
        assert e["label"] in vocab, f"{e['id']}: non-vocabulary label {e['label']}"
    print("[2] every surface has an honest backend kind + vocabulary label  OK")

    # 3) the label is READ from the backend, never upgraded: the zkinfer surface (if wired)
    #    must report EXACTLY what its backend emits (MODELED), a11oy-native.
    zk = next((e for e in surfaces if e["id"] == "zkinfer"), None)
    if zk is not None:
        import szl_frontier_zkinfer as _zk2
        emitted = _extract_label(_zk2.build_payload())
        assert zk["label"] == emitted, f"catalog {zk['label']} != backend {emitted}"
        assert zk["backend"] == NATIVE, f"zkinfer should be a11oy-native, got {zk['backend']}"
        assert zk["citations"], "zkinfer declares arXiv citations; catalog must surface them"
        print(f"[3] zkinfer label read VERBATIM from backend = {emitted}, native, "
              f"{len(zk['citations'])} citations  OK")
    else:
        print("[3] zkinfer not present (skipped)  OK")

    # 4) doctrine: locked-8 exact, adds nothing, Λ Conjecture 1, trust 0.97 not 100%.
    d = cat["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[4] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    # 5) no VERIFIED/green-1.0 top state; self label MODELED; summary present.
    assert cat["label"] == MODELED
    assert "summary" in cat and cat["summary"]["surfaces"] == len(surfaces)
    assert "VERIFIED" not in cat["label"]
    print(f"[5] self label MODELED, summary={_json.dumps(cat['summary'])}  OK")

    print("\nok:true checks:5")
    _sys.exit(0)
