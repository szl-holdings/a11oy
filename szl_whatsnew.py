#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_whatsnew.py — What's New: an honest, auto-derived "what's new" feed for the estate.

GET /api/a11oy/v1/whatsnew/feed shows the RECENTLY-ADDED frontier surfaces, each with the
honest data label its OWN backend actually emits right now and the paper(s) that backend
cites — ordered by when the surface was actually added to the repository.

HONEST BY CONSTRUCTION — the same drift-proof principle as the Frontier Index. This is NOT
a hand-maintained CHANGELOG file that drifts out of date. Both halves are derived at request
time from live sources in the running app + the real repository:

  1. WHAT the surfaces ARE + their honest label + citations — read from the Frontier Index
     catalog (szl_frontier_index.build_catalog), which is itself derived live from the app's
     surface registry (szl3d_holographic.SURFACES) + app.routes + each surface's own response
     and is independently CI-audited (frontier_index_honesty_check.py). The whatsnew feed adds
     NO new label logic: every per-surface label + citation is read VERBATIM from that audited
     catalog, so it can never claim a label a backend does not emit.

  2. WHEN each surface was added — read from the REAL git history: the commit that first added
     the surface's 3D module (static/3d/surfaces/<id>.js). ONE `git log --diff-filter=A` pass,
     bounded + guarded. When git history is unavailable at runtime (the container ships the
     app files per-file with NO .git tree), the recency signal degrades HONESTLY to the
     registry authoring order and says so — it never fabricates commit dates.

A companion CI honesty guard (.github/scripts/whatsnew_feed_honesty_check.py) re-derives the
set of REGISTERED surface ids independently (from szl3d_holographic.SURFACES, sharing no code
with this module) and FAILS the build if the feed ever lists a surface that is not actually
registered — so the feed stays honest automatically. It never weakens an existing gate.

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17; touches no
    locked formula and no kernel.
  - Λ stays Conjecture 1 (advisory); introduces no theorem, no green/1.0, no proof of Λ.
    Khipu BFT remains Conjecture 2. Trust ceiling 0.97, never 100%.
  - PURE READ. Signs nothing, mints nothing on a GET (receipts belong on writes).
  - No label is ever upgraded: a surface's MODELED stays MODELED; an unavailable surface is
    honestly UNAVAILABLE, never relabeled OK. Commit dates are never fabricated.
  - Additive route, registered before the SPA catch-all; canonical domain a-11-oy.com; 0
    runtime CDN.
"""

import datetime
import os
import re
import subprocess
from typing import Any

# Honesty-label vocabulary (doctrine v11). Re-stated here (not imported) so a broken import
# can never silently blank the vocabulary; tests grep these exact strings.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)
MODELED = "MODELED"
LIVE = "LIVE"
DEGRADED = "DEGRADED"
UNAVAILABLE = "UNAVAILABLE"

TRUST_CEILING = 0.97

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "whatsnew"

# How many recently-added surfaces the feed shows by default.
DEFAULT_LIMIT = 12

_FEED_TTL = 30.0  # seconds — warm reads serve the last real build.

# Where the 3D surface modules live, relative to the repo root; the git add-date of
# "<_SURFACES_DIR>/<id>.js" is the surface's real "added" timestamp.
_SURFACES_DIR = "static/3d/surfaces"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _repo_root() -> str:
    """Directory this module lives in — the app/repo root at both dev and runtime."""
    return os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# 1. WHEN — real git add-dates per surface module (drift-proof recency signal).
# ---------------------------------------------------------------------------

def _git_add_dates(root: str, timeout: float = 6.0) -> dict[str, dict[str, str]]:
    """Return {surface_id: {"added": ISO8601, "commit": short_sha}} derived from the REAL
    git history: the commit that first ADDED static/3d/surfaces/<id>.js. ONE `git log` pass,
    bounded + fully guarded. Returns {} when git / the .git tree is unavailable (e.g. the
    runtime container) — the caller then degrades honestly to registry order, never a
    fabricated date."""
    cmd = [
        "git", "-C", root, "log", "--diff-filter=A",
        "--name-only", "--date=iso-strict", "--format=%x1f%cI%x1f%h", "--",
        _SURFACES_DIR,
    ]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except Exception:
        return {}
    if out.returncode != 0 or not out.stdout:
        return {}

    dates: dict[str, dict[str, str]] = {}
    cur_date: str | None = None
    cur_commit: str | None = None
    for line in out.stdout.splitlines():
        if line.startswith("\x1f"):
            parts = line.split("\x1f")
            # parts == ['', '<cIso>', '<short_sha>']
            cur_date = parts[1] if len(parts) > 1 else None
            cur_commit = parts[2] if len(parts) > 2 else None
            continue
        line = line.strip()
        if not line or not line.endswith(".js"):
            continue
        base = os.path.basename(line)
        sid = base[:-3] if base.endswith(".js") else base
        # git log is newest-first; a file's FIRST add is the last we see. Keep the earliest
        # (overwrite so the final value is the oldest = true add commit).
        if cur_date:
            dates[sid] = {"added": cur_date, "commit": cur_commit or ""}
    return dates


# ---------------------------------------------------------------------------
# 2. WHAT — read every surface's honest label + citations from the audited
#    Frontier Index catalog (single source of truth; no new label logic here).
# ---------------------------------------------------------------------------

def _catalog(app, ns: str) -> dict:
    """The Frontier Index catalog (honest, self-audited). Imported in-process; never re-typed.
    Fully guarded — on any failure the feed degrades honestly rather than raising."""
    try:
        import szl_frontier_index as _fi
        cat = _fi.build_catalog(app, ns) if app is not None else {}
        return cat if isinstance(cat, dict) else {}
    except Exception:
        return {}


def _registry_ids() -> list[str]:
    """Ordered surface ids from the app's OWN registry (szl3d_holographic.SURFACES). This is
    the AUTHORING order — a coarse recency proxy used only when git history is unavailable."""
    try:
        import szl3d_holographic as holo
        surfaces = getattr(holo, "SURFACES", None)
        if not isinstance(surfaces, list):
            return []
        return [s["id"] for s in surfaces if isinstance(s, dict) and s.get("id")]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Feed assembly (cached, honest, pure read).
# ---------------------------------------------------------------------------

def _build_feed(app, ns: str = "a11oy", limit: int = DEFAULT_LIMIT) -> dict:
    root = _repo_root()
    cat = _catalog(app, ns)
    entries = cat.get("surfaces") if isinstance(cat.get("surfaces"), list) else []
    # id -> catalog entry (WHAT + honest label + citations). Ground truth of "registered".
    by_id: dict[str, dict] = {
        e.get("id"): e for e in entries
        if isinstance(e, dict) and e.get("id")
    }

    reg_ids = _registry_ids()
    add_dates = _git_add_dates(root)
    # A surface is a candidate for the feed ONLY if it is actually registered (present in the
    # catalog derived from szl3d_holographic.SURFACES). This is the drift-proof invariant the
    # CI guard enforces: the feed can never list a surface that is not registered.
    candidate_ids = [sid for sid in reg_ids if sid in by_id] or list(by_id.keys())

    git_ok = bool(add_dates)
    if git_ok:
        history_source = "git-log"
        history_label = LIVE
        # Order by real git add-date (newest first); undated surfaces sink to the bottom in
        # registry order (honest — we do not know their add date, so we never guess it).
        dated = [s for s in candidate_ids if s in add_dates]
        undated = [s for s in candidate_ids if s not in add_dates]
        dated.sort(key=lambda s: add_dates[s]["added"], reverse=True)
        ordered = dated + undated
    else:
        history_source = "registry-order"
        history_label = DEGRADED
        # No git tree at runtime: fall back to registry AUTHORING order (newest appended last),
        # so newest-appended surfaces come first. Labeled honestly, dates omitted (never faked).
        ordered = list(reversed(candidate_ids))

    feed_items: list[dict] = []
    for sid in ordered[: max(0, int(limit))]:
        e = by_id.get(sid, {})
        d = add_dates.get(sid)
        item = {
            "id": sid,
            "title": e.get("title", sid),
            "category": e.get("category"),
            "label": e.get("label", UNAVAILABLE),   # VERBATIM from the audited catalog.
            "backend": e.get("backend"),
            "endpoint": e.get("endpoint"),
            "citations": e.get("citations", []),
            "added": d["added"] if d else None,      # real commit date, or null (never faked).
            "added_commit": d["commit"] if d else None,
            "added_source": "git" if d else history_source,
        }
        feed_items.append(item)

    labels_seen: dict[str, int] = {}
    cited = 0
    for it in feed_items:
        labels_seen[it["label"]] = labels_seen.get(it["label"], 0) + 1
        if it.get("citations"):
            cited += 1

    return {
        "ok": True,
        "endpoint": "whatsnew/feed",
        "service": "a11oy.whatsnew",
        "title": "What's New — honest auto-derived estate changelog",
        "label": MODELED,
        "what": ("recently-added frontier surfaces, each with the honest data label its OWN "
                 "backend emits and the paper(s) it cites, ordered by when the surface was "
                 "actually added to the repository. Derived live from the Frontier Index "
                 "catalog (registry + routes + each surface's own response) + real git "
                 "history — never a hand-maintained changelog that can drift."),
        "history": {
            "source": history_source,
            "label": history_label,
            "note": ("commit dates read from the REAL git history (git log --diff-filter=A "
                     "over static/3d/surfaces)" if git_ok else
                     "git history unavailable at runtime (no .git tree); ordering falls back "
                     "to the registry authoring order — NO commit dates fabricated"),
            "surfaces_dir": _SURFACES_DIR,
            "dated_surfaces": len(add_dates),
        },
        "introspection": {
            "what_source": "szl_frontier_index.build_catalog (audited catalog; labels VERBATIM)",
            "registry_source": "szl3d_holographic.SURFACES (imported in-process)",
            "when_source": "git log --diff-filter=A over static/3d/surfaces (real add commit)",
            "registered_surfaces": len(by_id),
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
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "count": len(feed_items),
        "limit": int(limit),
        "summary": {
            "shown": len(feed_items),
            "registered_surfaces": len(by_id),
            "label_counts": labels_seen,
            "items_with_citations": cited,
            "history_source": history_source,
        },
        "items": feed_items,
        "timestamp_utc": _now_iso(),
    }


def build_feed(app, ns: str = "a11oy", limit: int = DEFAULT_LIMIT) -> dict:
    """Cached entrypoint. Serves the last real feed for _FEED_TTL seconds so a GET does not
    re-probe every surface / re-shell git on every hit. The cache only holds real output."""
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    key = (id(app), ns, int(limit))
    cache = getattr(build_feed, "_cache", None)
    if cache is not None:
        ck, ts, val = cache
        if ck == key and (now - ts) < _FEED_TTL:
            return val
    val = _build_feed(app, ns, limit)
    build_feed._cache = (key, now, val)  # type: ignore[attr-defined]
    return val


def handle_feed(app, ns: str = "a11oy", limit: int = DEFAULT_LIMIT) -> dict:
    """GET /whatsnew/feed — handler used by FastAPI and __main__."""
    try:
        return build_feed(app, ns, limit)
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False,
            "endpoint": "whatsnew/feed",
            "label": UNAVAILABLE,
            "error": str(exc),
            "doctrine": "v11: feed unavailable; no fabricated surface/date/label emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_health() -> dict:
    """GET /whatsnew/health — a tiny, side-effect-free self-describing health tile. This is
    the endpoint the Frontier Index catalog probes for THIS surface, so the feed (which reads
    that catalog) never recurses into itself."""
    return {
        "ok": True,
        "endpoint": "whatsnew/health",
        "service": "a11oy.whatsnew",
        "label": MODELED,
        "surface_id": SURFACE_ID,
        "doctrine": {"lambda": "Conjecture 1", "locked_proven": 8, "trust_ceiling": TRUST_CEILING},
        "timestamp_utc": _now_iso(),
    }


# ---------------------------------------------------------------------------
# FastAPI router registration — mirrors szl_frontier_index.register().
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the whatsnew endpoints on the FastAPI ``app``. Returns a status string.

    The feed handler is a SYNC def so FastAPI runs it in a worker thread — that lets the
    in-process catalog probe (which drives its own event loop) run safely."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/whatsnew"

    @app.get(f"{base}/feed")
    def _whatsnew_feed(request: Request):
        """Honest 'what's new' feed: recently-added surfaces with VERBATIM labels + cited
        papers, ordered by real git add-date — derived live from the running app + git."""
        try:
            limit = int(request.query_params.get("limit", DEFAULT_LIMIT))
        except Exception:
            limit = DEFAULT_LIMIT
        limit = max(1, min(limit, 100))
        return JSONResponse(handle_feed(app, ns, limit))

    @app.get(f"{base}/health")
    def _whatsnew_health():
        """Self-describing health tile (also the catalog self-probe endpoint; never recurses)."""
        return JSONResponse(handle_health())

    return "whatsnew-wired:2"


# ---------------------------------------------------------------------------
# Self-test — honest labels, real introspection, no fabricated date, no upgrade.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json
    import sys as _sys

    print("=" * 72)
    print("szl_whatsnew — self-test (honest auto-derived what's-new feed)")
    print("=" * 72)

    from fastapi import FastAPI
    app = FastAPI()
    # Wire the frontier index (the feed's WHAT source) + a couple of real surfaces so the
    # feed has honest labelled entries to introspect, then this surface itself.
    import szl_frontier_index as _fi
    _fi.register(app, ns="a11oy")
    try:
        import szl_frontier_zkinfer as _zk
        _zk.register(app, ns="a11oy")
    except Exception as _e:  # pragma: no cover
        print(f"(zkinfer not wired for self-test: {_e!r})")
    register(app, ns="a11oy")

    feed = handle_feed(app, ns="a11oy")
    blob = _json.dumps(feed)

    # 1) feed built, ok:true, MODELED self label, items present.
    assert feed["ok"] is True
    assert feed["endpoint"] == "whatsnew/feed"
    assert feed["label"] == MODELED
    items = feed["items"]
    assert isinstance(items, list) and len(items) >= 1, "feed has no items"
    print(f"[1] feed ok, MODELED, {len(items)} items, history={feed['history']['source']}  OK")

    # 2) every item is a REGISTERED surface (drift-proof invariant) with an honest-vocabulary
    #    label read verbatim — never an invented token, never a fabricated date.
    reg = set(_registry_ids())
    vocab = set(HONEST_LABELS)
    for it in items:
        assert it["id"] in reg, f"feed lists unregistered surface {it['id']!r}"
        assert it["label"] in vocab, f"{it['id']}: non-vocabulary label {it['label']!r}"
        # date is either a real ISO string or honestly null — never a fabricated placeholder.
        assert it["added"] is None or isinstance(it["added"], str)
    print(f"[2] all {len(items)} items are registered surfaces w/ vocabulary labels  OK")

    # 3) the WHAT is read from the audited catalog: an item's label MUST equal the catalog's
    #    label for that surface (single source of truth; no second copy).
    cat = _fi.build_catalog(app, ns="a11oy")
    cat_label = {e["id"]: e["label"] for e in cat["surfaces"]}
    for it in items:
        assert it["label"] == cat_label.get(it["id"]), (
            f"{it['id']}: feed label {it['label']!r} != catalog {cat_label.get(it['id'])!r}")
    print("[3] per-surface labels read VERBATIM from the audited Frontier Index catalog  OK")

    # 4) doctrine: locked-8 exact, adds nothing, Λ Conjecture 1, trust 0.97 not 100%.
    d = feed["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[4] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    # 5) no green/1.0 verified state anywhere; git recency signal honestly labeled.
    assert "VERIFIED" not in blob and '"1.0"' not in feed["label"]
    assert feed["history"]["label"] in (LIVE, DEGRADED, UNAVAILABLE)
    print(f"[5] no VERIFIED/green-1.0 state; history label={feed['history']['label']}  OK")

    print("\n--- feed keys ---")
    for k in feed:
        print(f"  - {k}")
    print("\nok:true checks:5")
    _sys.exit(0)
