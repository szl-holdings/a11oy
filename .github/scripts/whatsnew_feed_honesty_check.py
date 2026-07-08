#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""whatsnew_feed_honesty_check.py — INDEPENDENT honesty guard for the What's New feed.

The What's New surface (szl_whatsnew.py, GET /api/a11oy/v1/whatsnew/feed) advertises the
estate's recently-added frontier surfaces. Its core promise is drift-proof: it can only ever
list surfaces that are ACTUALLY REGISTERED — it must never invent a surface, resurrect a
removed one, or otherwise claim something the running app does not register. This script is
the CI that keeps that promise: it re-derives the set of registered surface ids INDEPENDENTLY
and FAILS the build (non-zero exit) if the feed ever lists a surface that is not registered.

This ADDS a guard; it weakens none.

INDEPENDENCE (the point of a cross-check): this script deliberately shares NO code with
szl_whatsnew. It does NOT import that module. It derives the authoritative registered-id set
straight from the app's own surface registry (szl3d_holographic.SURFACES) and, as a second
independent witness, from the app's registered API routes. If the feed lists an id that is in
NEITHER, the feed is drifting and the build fails.

WHAT IT ASSERTS, per feed:
  * ok:true and a top label inside the doctrine honesty vocabulary (no invented token, no
    "VERIFIED"/"1.0"/green state);
  * Λ stays "Conjecture 1" (advisory) and trust ceiling ≤ 0.97 (never trust_100_percent);
  * EVERY item id is a REGISTERED surface (present in szl3d_holographic.SURFACES) — the
    drift-proof invariant;
  * every item's label is inside the honesty vocabulary and never a banned green token;
  * item ids are unique (no padded/duplicated entries) and the shown count matches items[];
  * any "added" timestamp is either honestly null or a plausible ISO-8601 date — never a
    fabricated placeholder.

NEGATIVE CONTROL (--selftest): before it is trusted against the live feed, the checker is fed
a planted lie — a feed that lists a surface id absent from the registry (and one with an
out-of-vocabulary label) — and MUST reject both, plus accept a truthful feed. This is the org
guard pattern (cf. frontier_index_honesty_check.py --selftest /
constellation-honesty-guard.yml): a guard that cannot catch planted drift is not trusted on
real data.

Doctrine v11: read-only; imports serve.py in-process (no network, no CDN); asserts
Λ = Conjecture 1 stays advisory and trust ceiling ≤ 0.97; adds nothing to the locked-8.
"""
from __future__ import annotations

import os
import re
import sys

# serve.py + szl3d_holographic.py live at the repo root. When run directly, sys.path[0] is the
# script's own dir (.github/scripts); put the repo root (and cwd) on the path so `import serve`
# / `import szl3d_holographic` resolve the way the CI job's working directory expects.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for _p in (os.getcwd(), _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- Independent copy of the doctrine honesty vocabulary. Re-typed on purpose: this guard
# must NOT import szl_whatsnew, or a bug there would hide behind itself.
HONEST_VOCAB = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)
FEED_PATH = "/api/a11oy/v1/whatsnew/feed"

# Banned "dishonest green" tokens that must never appear as a feed label.
_BANNED_LABELS = ("VERIFIED", "1.0", "100%", "GUARANTEED", "PROVEN-TRUE")

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


# ---------------------------------------------------------------------------
# Independent derivation of the AUTHORITATIVE registered-surface id set. Two
# witnesses, neither borrowed from szl_whatsnew:
#   1. szl3d_holographic.SURFACES (the app's own surface registry), and
#   2. the app's registered GET routes under /api/{ns}/v1 (path segments).
# The union is what "registered" means; a feed id in NEITHER is drift.
# ---------------------------------------------------------------------------

def _norm(token: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (token or "").lower())


def registry_ids() -> set[str]:
    """Registered surface ids from szl3d_holographic.SURFACES (imported independently)."""
    import szl3d_holographic as holo

    surfaces = getattr(holo, "SURFACES", None)
    if not isinstance(surfaces, list):
        return set()
    return {s["id"] for s in surfaces if isinstance(s, dict) and s.get("id")}


def route_segment_ids(app, ns: str = "a11oy") -> set[str]:
    """Normalized path segments of every registered GET route under /api/{ns}/v1 — a second,
    independent witness that a surface id is actually wired into the running app."""
    prefix = f"/api/{ns}/v1"
    segs: set[str] = set()
    for r in getattr(app, "routes", []) or []:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None) or set()
        if not path or not path.startswith(prefix):
            continue
        if methods and "GET" not in methods:
            continue
        rest = path[len(prefix):].strip("/")
        for s in rest.split("/"):
            if s and not s.startswith("{"):
                segs.add(_norm(s))
    return segs


# ---------------------------------------------------------------------------
# Core check: given the feed dict + the authoritative registered set (+ optional
# route-segment witnesses), return a list of violations. Factored out so the
# negative-control self-test can inject a toy registry.
# ---------------------------------------------------------------------------

def find_violations(feed: dict, registered: set[str], route_segs: set[str] | None = None) -> list[str]:
    v: list[str] = []
    route_segs = route_segs or set()

    if not isinstance(feed, dict) or feed.get("ok") is not True:
        v.append(f"feed not ok / not a dict: {type(feed).__name__}")
        return v

    top = str(feed.get("label", ""))
    if top.upper() not in HONEST_VOCAB:
        v.append(f"feed top label {top!r} is not in the honesty vocabulary")
    for bad in _BANNED_LABELS:
        if bad in top.upper():
            v.append(f"feed top label {top!r} contains banned dishonest token {bad!r}")

    doctrine = feed.get("doctrine") or {}
    lam = str(doctrine.get("lambda", ""))
    if lam and "Conjecture 1" not in lam:
        v.append(f"Λ must stay 'Conjecture 1' (advisory), feed says {lam!r}")
    tc = doctrine.get("trust_ceiling")
    if isinstance(tc, (int, float)) and tc > 0.97:
        v.append(f"trust ceiling {tc} exceeds 0.97")
    if doctrine.get("trust_100_percent") is True:
        v.append("feed asserts trust_100_percent=true (banned)")

    items = feed.get("items")
    if not isinstance(items, list):
        v.append("feed has no items[] array to audit")
        return v

    # shown count must match the real item list (never a padded/inflated number).
    summary = feed.get("summary") or {}
    shown = summary.get("shown", feed.get("count"))
    if isinstance(shown, int) and shown != len(items):
        v.append(f"feed summary.shown={shown} != len(items)={len(items)} (count drift)")

    seen: set[str] = set()
    for e in items:
        if not isinstance(e, dict):
            v.append(f"feed item is not a dict: {e!r}")
            continue
        sid = e.get("id")
        if not sid:
            v.append("feed item has no id")
            continue

        # (a) THE drift-proof invariant: every listed surface MUST be registered.
        if sid not in registered and _norm(sid) not in route_segs:
            v.append(f"[{sid}] feed lists a surface that is NOT registered "
                     f"(absent from szl3d_holographic.SURFACES and from app routes)")

        # (b) no duplicate/padded entries.
        if sid in seen:
            v.append(f"[{sid}] duplicate feed entry (padding)")
        seen.add(sid)

        # (c) label must be in-vocabulary and never a dishonest green token.
        label = str(e.get("label", ""))
        up = label.upper()
        if up not in HONEST_VOCAB:
            v.append(f"[{sid}] reports label {label!r} outside the honesty vocabulary")
        for bad in _BANNED_LABELS:
            if bad in up:
                v.append(f"[{sid}] label {label!r} contains banned token {bad!r}")

        # (d) an "added" date is either honestly null or a plausible ISO-8601 date.
        added = e.get("added")
        if added is not None and not (isinstance(added, str) and _ISO_RE.match(added)):
            v.append(f"[{sid}] 'added' timestamp {added!r} is neither null nor a valid "
                     f"ISO-8601 date (possible fabricated placeholder)")

    return v


# ---------------------------------------------------------------------------
# Negative control — prove the checker rejects planted drift before we trust it.
# Fully self-contained: a toy feed + toy registry, no serve.py needed.
# ---------------------------------------------------------------------------

def _selftest() -> int:
    print("whatsnew_feed_honesty_check --selftest (negative control)")

    registered = {"alpha", "beta", "whatsnew"}

    def feed_with(items, top="MODELED", doctrine=None):
        return {
            "ok": True, "label": top,
            "doctrine": doctrine or {"lambda": "Conjecture 1", "trust_ceiling": 0.97,
                                     "trust_100_percent": False},
            "count": len(items),
            "summary": {"shown": len(items)},
            "items": items,
        }

    failures = 0

    # 1) truthful feed (only registered ids, valid labels) -> MUST pass (0 violations).
    ok_feed = feed_with([
        {"id": "alpha", "label": "MODELED", "added": "2026-07-01T00:00:00Z"},
        {"id": "beta", "label": "SAMPLE", "added": None},
    ])
    vio = find_violations(ok_feed, registered)
    if vio:
        print(f"  [1] FAIL: truthful feed wrongly flagged: {vio}")
        failures += 1
    else:
        print("  [1] truthful feed accepted (0 violations)  OK")

    # 2) planted lie: lists a surface id absent from the registry -> MUST flag.
    ghost = feed_with([{"id": "ghostsurface", "label": "MODELED", "added": None}])
    vio = find_violations(ghost, registered)
    if any("NOT registered" in x for x in vio):
        print("  [2] planted unregistered surface REJECTED  OK")
    else:
        print(f"  [2] FAIL: unregistered surface was NOT rejected: {vio}")
        failures += 1

    # 3) out-of-vocabulary / banned label -> MUST flag.
    oov = feed_with([{"id": "alpha", "label": "VERIFIED", "added": None}])
    vio = find_violations(oov, registered)
    if any("vocabulary" in x or "banned" in x for x in vio):
        print("  [3] out-of-vocabulary / banned label REJECTED  OK")
    else:
        print(f"  [3] FAIL: out-of-vocabulary label was NOT rejected: {vio}")
        failures += 1

    # 4) count drift: summary.shown lies about the real item count -> MUST flag.
    drift = feed_with([{"id": "alpha", "label": "MODELED", "added": None}])
    drift["summary"]["shown"] = 99
    vio = find_violations(drift, registered)
    if any("count drift" in x for x in vio):
        print("  [4] count drift (shown != len(items)) REJECTED  OK")
    else:
        print(f"  [4] FAIL: count drift was NOT rejected: {vio}")
        failures += 1

    # 5) fabricated date placeholder -> MUST flag.
    fab = feed_with([{"id": "alpha", "label": "MODELED", "added": "soon™"}])
    vio = find_violations(fab, registered)
    if any("ISO-8601" in x for x in vio):
        print("  [5] fabricated 'added' date placeholder REJECTED  OK")
    else:
        print(f"  [5] FAIL: fabricated date was NOT rejected: {vio}")
        failures += 1

    # 6) Λ downgrade attempt -> MUST flag.
    lam = feed_with([{"id": "alpha", "label": "MODELED", "added": None}],
                    doctrine={"lambda": "theorem", "trust_ceiling": 0.97})
    vio = find_violations(lam, registered)
    if any("Conjecture 1" in x for x in vio):
        print("  [6] Λ downgrade (theorem) REJECTED  OK")
    else:
        print(f"  [6] FAIL: Λ downgrade was NOT rejected: {vio}")
        failures += 1

    if failures:
        print(f"\nSELFTEST FAILED: {failures} negative-control case(s) not caught")
        return 1
    print("\nselftest ok: the honesty checker rejects planted drift on all 6 controls")
    return 0


# ---------------------------------------------------------------------------
# Live check — boot serve.py in-process, fetch the real feed, audit it.
# ---------------------------------------------------------------------------

def _http_get_json(client, path: str):
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


def _live_check() -> int:
    print("whatsnew_feed_honesty_check (live) — booting serve.py in-process")
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

    registered = registry_ids()
    if not registered:
        print("FAIL: szl3d_holographic.SURFACES yielded no registered surface ids")
        return 1

    with TestClient(app) as client:
        feed = _http_get_json(client, FEED_PATH)
        if feed is None:
            print(f"FAIL: {FEED_PATH} returned no JSON feed (200) — endpoint down or "
                  f"falling through to the SPA catch-all")
            return 1

        route_segs = route_segment_ids(app, "a11oy")
        summary = feed.get("summary", {})
        print(f"  feed: shown={summary.get('shown')}, "
              f"registered_surfaces={summary.get('registered_surfaces')}, "
              f"history={feed.get('history', {}).get('source')}, label={feed.get('label')}")
        print(f"  authoritative registered ids: {len(registered)} (registry) / "
              f"{len(route_segs)} route segments")

        violations = find_violations(feed, registered, route_segs)

        items = feed.get("items") or []
        if not items:
            print("\nFAIL: the feed lists NO items; the drift-proof cross-check would be "
                  "vacuous. Expected at least one recently-added registered surface.")
            return 1

    if violations:
        print(f"\nHONESTY VIOLATIONS ({len(violations)}) — the feed claims something the "
              f"running app does not register / an out-of-vocabulary or fabricated value:")
        for x in violations:
            print(f"  - {x}")
        print("\nFAIL: What's New feed is not honest-by-construction.")
        return 1

    print(f"\nok: all {len(items)} feed items are registered surfaces with honest-vocabulary "
          f"labels; no drift, no fabricated date, Λ advisory, trust ≤ 0.97.")
    return 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return _selftest()
    return _live_check()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
