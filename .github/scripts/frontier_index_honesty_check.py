#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""frontier_index_honesty_check.py — INDEPENDENT honesty guard for the Frontier INDEX.

The Frontier Index surface (szl_frontier_index.py, GET
/api/a11oy/v1/frontier-index/catalog) claims, for every registered frontier surface,
the honest data label that surface's OWN backend emits. The whole promise of that
surface is "honest by construction — it cannot claim a label a backend does not emit."
This script is the CI that keeps that promise true: it re-derives every a11oy-native
surface's label INDEPENDENTLY and FAILS the build (non-zero exit) if the catalog ever
claims a label a surface's backend does not actually emit.

INDEPENDENCE (the point of a cross-check): this script deliberately shares NO code with
szl_frontier_index. It does NOT import that module's _extract_label / _invoke_route /
_probe_label / _surface_routes. It re-implements label extraction and endpoint probing
from scratch, and — crucially — it probes each endpoint through a DIFFERENT mechanism:
a real Starlette TestClient HTTP GET (the catalog itself uses direct route-callable
invocation because it runs INSIDE a request where a nested client would corrupt the
middleware; this guard runs standalone, so it can drive the real HTTP path). If the
two independent derivations disagree, the catalog is drifting and the build fails.

WHAT IT ASSERTS, per catalog entry:
  * every reported label is a member of the doctrine honesty vocabulary (no invented
    token, no "VERIFIED"/"1.0"/green state);
  * for every surface the catalog calls "a11oy-native" WITH a concrete label read from a
    concrete endpoint, that endpoint — probed independently — emits exactly that label
    (never a different vocabulary token, never nothing);
  * every citation the catalog attributes to a native surface actually appears in that
    surface's own backend response.

NEGATIVE CONTROL (--selftest): before it is ever trusted against the live catalog, the
checker is fed a planted lie — a catalog entry that claims a label its toy backend does
NOT emit, and one that claims an out-of-vocabulary token — and MUST reject both, plus
accept a truthful entry. This is the org guard pattern (cf.
constellation-honesty-guard.yml / eval-arena-negative-control.yml): a guard that cannot
catch planted drift is not trusted on real data.

Doctrine v11: read-only; imports serve.py in-process (no network, no CDN); asserts
Λ = Conjecture 1 stays advisory and trust ceiling ≤ 0.97; adds nothing to the locked-8.
"""
from __future__ import annotations

import json
import os
import re
import sys

# serve.py lives at the repo root. When this script is run directly, sys.path[0] is the
# script's own directory (.github/scripts), so put the repo root (and cwd) on the path so
# `import serve` resolves the same way the CI job's working directory expects.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for _p in (os.getcwd(), _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- Independent copy of the doctrine honesty vocabulary. Re-typed on purpose: this
# guard must NOT import szl_frontier_index, or a bug there would hide behind itself.
HONEST_VOCAB = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)
NATIVE = "a11oy-native"
CATALOG_PATH = "/api/a11oy/v1/frontier-index/catalog"

# Banned "dishonest green" tokens that must never appear as a catalog label.
_BANNED_LABELS = ("VERIFIED", "1.0", "100%", "GUARANTEED", "PROVEN-TRUE")


# ---------------------------------------------------------------------------
# Independent label extraction. Deliberately a different implementation from
# szl_frontier_index._extract_label: recursively collect every string that lives
# under a label-ish key, then return the earliest-occurring vocabulary token.
# ---------------------------------------------------------------------------
_LABEL_KEYS = ("label", "data_label", "claim", "label_top")


def _collect_label_strings(payload) -> list[str]:
    """Walk the payload and gather, in document order, every string value that sits
    under a label-ish key (label / data_label / claim / label_top), at any depth."""
    out: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(k, str) and k.lower() in _LABEL_KEYS and isinstance(v, str):
                    out.append(v)
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return out


def independent_label(payload) -> str | None:
    """The honest label THIS guard derives from a backend payload, from scratch. Returns
    the first vocabulary token found across the label-ish values, or None if none."""
    for text in _collect_label_strings(payload):
        up = text.upper()
        best_pos, best_tok = None, None
        for tok in HONEST_VOCAB:
            i = up.find(tok)
            if i >= 0 and (best_pos is None or i < best_pos):
                best_pos, best_tok = i, tok
        if best_tok:
            return best_tok
    return None


def independent_citations(payload) -> set[str]:
    """Every arXiv id / DOI that appears ANYWHERE in the payload, lowercased for compare.
    Independent of szl_frontier_index's harvester."""
    try:
        blob = json.dumps(payload, default=str)
    except Exception:
        return set()
    arxiv = re.findall(r"arXiv:\d{4}\.\d{4,5}(?:v\d+)?", blob, re.IGNORECASE)
    doi = re.findall(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", blob)
    return {t.rstrip(".,;").lower() for t in (arxiv + doi)}


# ---------------------------------------------------------------------------
# Independent endpoint probing. Primary path: a real HTTP GET via Starlette's
# TestClient (a different mechanism from the catalog's in-request direct-callable
# invocation). Fallback: our OWN minimal direct-callable invocation, so a route that
# is unreachable through the SPA catch-all is still read from its backend — we never
# excuse a mismatch by "couldn't reach it".
# ---------------------------------------------------------------------------

def _http_get_json(client, path: str):
    """Return decoded JSON for a GET via TestClient, or None on any non-200/non-JSON."""
    try:
        r = client.get(path)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    try:
        j = r.json()
    except Exception:
        return None
    return j if isinstance(j, dict) else None


def _direct_call_json(app, path: str):
    """Our own from-scratch direct-callable invocation of a registered GET route, for
    endpoints the full HTTP stack cannot reach (catch-all ordering). Independent of
    szl_frontier_index._invoke_route."""
    import inspect

    route = None
    for r in getattr(app, "routes", []) or []:
        if getattr(r, "path", None) == path:
            methods = getattr(r, "methods", None) or set()
            if not methods or "GET" in methods:
                route = r
                break
    if route is None:
        return None
    fn = getattr(route, "endpoint", None)
    if not callable(fn):
        return None
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None

    from starlette.requests import Request

    scope = {
        "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": [], "server": ("honesty-check", 80), "client": ("honesty-check", 0),
        "app": app,
    }

    async def _receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    kwargs = {}
    for p in sig.parameters.values():
        if p.default is not inspect.Parameter.empty:
            continue
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if p.annotation is Request or p.name in ("req", "request"):
            kwargs[p.name] = Request(scope, receive=_receive)
        else:
            return None  # needs an arg we won't fabricate

    import asyncio
    import concurrent.futures as cf

    def _work():
        res = fn(**kwargs)
        if inspect.isawaitable(res):
            return asyncio.run(res)
        return res

    try:
        with cf.ThreadPoolExecutor(max_workers=1) as ex:
            res = ex.submit(_work).result(timeout=5.0)
    except Exception:
        return None

    if isinstance(res, dict):
        return res
    body = getattr(res, "body", None)
    if body is None:
        return None
    try:
        payload = json.loads(body)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def probe_backend(app, client, path: str):
    """Independently read a surface endpoint's OWN payload — real HTTP first, direct-call
    fallback. Returns the payload dict or None."""
    return _http_get_json(client, path) or _direct_call_json(app, path)


# ---------------------------------------------------------------------------
# Core check: given the catalog dict + a probe function, return list of violations.
# The probe function takes an endpoint path and returns that endpoint's own payload
# (or None). Factored out so the negative-control self-test can inject a toy probe.
# ---------------------------------------------------------------------------

def find_violations(catalog: dict, probe) -> list[str]:
    v: list[str] = []

    if not isinstance(catalog, dict) or catalog.get("ok") is not True:
        v.append(f"catalog not ok / not a dict: {type(catalog).__name__}")
        return v

    top = str(catalog.get("label", ""))
    if independent_label(catalog) is None and top.upper() not in HONEST_VOCAB:
        v.append(f"catalog top label {top!r} is not in the honesty vocabulary")
    for bad in _BANNED_LABELS:
        if bad in top.upper():
            v.append(f"catalog top label {top!r} contains banned dishonest token {bad!r}")

    doctrine = catalog.get("doctrine") or {}
    lam = str(doctrine.get("lambda", ""))
    if lam and "Conjecture 1" not in lam:
        v.append(f"Λ must stay 'Conjecture 1' (advisory), catalog says {lam!r}")
    tc = doctrine.get("trust_ceiling")
    if isinstance(tc, (int, float)) and tc > 0.97:
        v.append(f"trust ceiling {tc} exceeds 0.97")
    if doctrine.get("trust_100_percent") is True:
        v.append("catalog asserts trust_100_percent=true (banned)")

    surfaces = catalog.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        v.append("catalog has no surfaces[] to audit")
        return v

    for e in surfaces:
        if not isinstance(e, dict):
            v.append(f"surface entry is not a dict: {e!r}")
            continue
        sid = e.get("id", "?")
        label = str(e.get("label", ""))
        up = label.upper()

        # (a) every reported label must be in-vocabulary and never a dishonest green token.
        if up not in HONEST_VOCAB:
            v.append(f"[{sid}] reports label {label!r} outside the honesty vocabulary")
        for bad in _BANNED_LABELS:
            if bad in up:
                v.append(f"[{sid}] label {label!r} contains banned token {bad!r}")

        # (b) native surfaces with a concrete label + endpoint must be independently
        #     confirmed to emit EXACTLY that label from their own backend.
        if e.get("backend") != NATIVE:
            continue
        ep = e.get("endpoint")
        if not ep or up == "UNAVAILABLE":
            continue  # native-but-unlabeled is honest; nothing to re-derive
        payload = probe(ep)
        if payload is None:
            v.append(f"[{sid}] catalog claims a11oy-native label {label!r} from {ep} "
                     f"but that endpoint yields no backend payload independently")
            continue
        derived = independent_label(payload)
        if derived is None:
            v.append(f"[{sid}] catalog claims label {label!r} from {ep} but the backend "
                     f"independently emits NO honest label — catalog is over-claiming")
        elif derived != up:
            v.append(f"[{sid}] LABEL DRIFT: catalog claims {label!r} from {ep} but the "
                     f"backend independently emits {derived!r}")

        # (c) citations the catalog attributes must actually be in the backend response.
        claimed = e.get("citations") or []
        if claimed:
            have = independent_citations(payload)
            for c in claimed:
                if str(c).rstrip(".,;").lower() not in have:
                    v.append(f"[{sid}] catalog attributes citation {c!r} not present in "
                             f"the backend's own response at {ep}")

    return v


def _count_native_labelled(catalog: dict) -> int:
    """How many surfaces the catalog claims as a11oy-native WITH a concrete label + endpoint
    — i.e. how many claims the cross-check can actually re-derive."""
    n = 0
    for e in catalog.get("surfaces", []) or []:
        if (isinstance(e, dict) and e.get("backend") == NATIVE and e.get("endpoint")
                and str(e.get("label", "")).upper() != "UNAVAILABLE"):
            n += 1
    return n


# ---------------------------------------------------------------------------
# Negative control — prove the checker rejects planted drift before we trust it.
# Fully self-contained: a toy catalog + toy backends, no serve.py needed.
# ---------------------------------------------------------------------------

def _selftest() -> int:
    print("frontier_index_honesty_check --selftest (negative control)")

    # Toy backends keyed by endpoint. The truthful surface emits MODELED; the guard must
    # accept a catalog that claims MODELED and reject one that claims anything else.
    backends = {
        "/toy/good": {"label": "MODELED", "citations": ["arXiv:2401.00001"]},
        "/toy/measured": {"label": "MEASURED"},
    }

    def toy_probe(ep):
        return backends.get(ep)

    def catalog_with(entry_label, entry_ep, backend=NATIVE, citations=None):
        return {
            "ok": True, "label": "MODELED",
            "doctrine": {"lambda": "Conjecture 1", "trust_ceiling": 0.97,
                         "trust_100_percent": False},
            "surfaces": [{
                "id": "toy", "backend": backend, "label": entry_label,
                "endpoint": entry_ep, "citations": citations or [],
            }],
        }

    failures = 0

    # 1) truthful catalog (claims MODELED, backend emits MODELED) -> MUST pass (0 violations)
    ok_cat = catalog_with("MODELED", "/toy/good", citations=["arXiv:2401.00001"])
    vio = find_violations(ok_cat, toy_probe)
    if vio:
        print(f"  [1] FAIL: truthful catalog wrongly flagged: {vio}")
        failures += 1
    else:
        print("  [1] truthful catalog accepted (0 violations)  OK")

    # 2) planted lie: claims MEASURED but backend at /toy/good emits MODELED -> MUST flag
    lie_cat = catalog_with("MEASURED", "/toy/good")
    vio = find_violations(lie_cat, toy_probe)
    if any("DRIFT" in x for x in vio):
        print("  [2] planted label-drift (claims MEASURED, backend MODELED) REJECTED  OK")
    else:
        print(f"  [2] FAIL: label-drift lie was NOT rejected: {vio}")
        failures += 1

    # 3) out-of-vocabulary token -> MUST flag
    oov_cat = catalog_with("VERIFIED", "/toy/good")
    vio = find_violations(oov_cat, toy_probe)
    if any("vocabulary" in x or "banned" in x for x in vio):
        print("  [3] out-of-vocabulary / banned label REJECTED  OK")
    else:
        print(f"  [3] FAIL: out-of-vocabulary label was NOT rejected: {vio}")
        failures += 1

    # 4) over-claim: native label claimed from an endpoint that yields nothing -> MUST flag
    ghost_cat = catalog_with("MODELED", "/toy/missing")
    vio = find_violations(ghost_cat, toy_probe)
    if any("no backend payload" in x for x in vio):
        print("  [4] over-claim (label from an endpoint that emits nothing) REJECTED  OK")
    else:
        print(f"  [4] FAIL: over-claim was NOT rejected: {vio}")
        failures += 1

    # 5) fabricated citation not in the backend response -> MUST flag
    fab_cat = catalog_with("MODELED", "/toy/good", citations=["arXiv:9999.99999"])
    vio = find_violations(fab_cat, toy_probe)
    if any("citation" in x for x in vio):
        print("  [5] fabricated citation REJECTED  OK")
    else:
        print(f"  [5] FAIL: fabricated citation was NOT rejected: {vio}")
        failures += 1

    if failures:
        print(f"\nSELFTEST FAILED: {failures} negative-control case(s) not caught")
        return 1
    print("\nselftest ok: the honesty checker rejects planted drift on all 5 controls")
    return 0


# ---------------------------------------------------------------------------
# Live check — boot serve.py in-process, fetch the real catalog, audit it.
# ---------------------------------------------------------------------------

def _live_check() -> int:
    print("frontier_index_honesty_check (live) — booting serve.py in-process")
    try:
        import serve  # noqa: F401 — importing wires the FastAPI app + all routes
    except Exception as exc:
        print(f"FAIL: could not import serve.py: {exc!r}")
        return 1
    app = getattr(serve, "app", None)
    if app is None:
        print("FAIL: serve.app not found")
        return 1

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        catalog = _http_get_json(client, CATALOG_PATH)
        if catalog is None:
            # fall back to direct-callable so a catch-all ordering bug is reported honestly
            catalog = _direct_call_json(app, CATALOG_PATH)
        if catalog is None:
            print(f"FAIL: {CATALOG_PATH} returned no JSON catalog (200) — endpoint down")
            return 1

        summary = catalog.get("summary", {})
        print(f"  catalog: {summary.get('surfaces')} surfaces, "
              f"backends={summary.get('backend_counts')}, "
              f"cited={summary.get('surfaces_with_citations')}, label={catalog.get('label')}")

        n_native = _count_native_labelled(catalog)
        print(f"  independently re-derivable a11oy-native labels: {n_native}")
        violations = find_violations(catalog, lambda ep: probe_backend(app, client, ep))

    if n_native == 0:
        print("\nFAIL: the catalog exposes NO a11oy-native labelled surface to re-derive; "
              "the honesty cross-check would be vacuous. Expected at least one native "
              "backend (e.g. the frontier-index surface's own /health).")
        return 1

    if violations:
        print(f"\nHONESTY VIOLATIONS ({len(violations)}) — the catalog claims labels a "
              f"backend does not emit:")
        for x in violations:
            print(f"  - {x}")
        print("\nFAIL: Frontier Index catalog is not honest-by-construction.")
        return 1

    print("\nok: every a11oy-native label in the catalog was independently confirmed "
          "against its own backend; no drift, no fabricated citation, Λ advisory.")
    return 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return _selftest()
    return _live_check()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
