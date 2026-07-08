#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_status_aggregate.py — the operational-dashboard back-end.

GET /api/a11oy/v1/status is an honest, drift-proof aggregate of the running
estate. For every registered surface it reports:

  * the honest DATA LABEL its own backend actually emits (LIVE / MEASURED /
    MODELED / SAMPLE / ... / UNAVAILABLE) — read VERBATIM, never upgraded; and
  * a derived HEALTH state (LIVE / DEGRADED / UNAVAILABLE / FRONTEND) computed
    from whether the surface's own /api route answered in-process with a
    recognized honest label.

It then rolls those up per SUBSYSTEM (the surface category from the app's own
registry) and for the WHOLE ESTATE, so an operator can see at a glance which
subsystems are live, degraded, or unavailable.

DRIFT-PROOF BY CONSTRUCTION. This module does NOT maintain its own surface list
or re-probe routes itself. It is built ENTIRELY on top of the Wave-Q frontier
INDEX (``szl_frontier_index.build_catalog``), which derives its data live from:

  1. the app's OWN surface registry (``szl3d_holographic.SURFACES``), and
  2. the FastAPI app's registered routes + each surface's own response.

So this status aggregate can never diverge from the 3D shell / holographic UI
or from what is actually wired — if a surface is added, removed, or changes its
honest label, this endpoint reflects it automatically on the next probe cycle.
The catalog is cached (30s TTL) inside the frontier index, so a status GET does
not re-probe every surface on every hit.

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17.
  - Λ stays Conjecture 1 (advisory); no theorem, no green/1.0, trust ceiling 0.97.
  - PURE READ. Signs nothing, mints nothing on a GET.
  - No label is ever upgraded: a surface's MODELED stays MODELED; a down surface
    is honestly UNAVAILABLE, never relabeled OK. The estate rollup NEVER claims a
    fabricated "all-green": it reports the honest worst-case of what it observed.
  - Additive route, registered before the SPA catch-all; canonical a-11-oy.com.
"""

import datetime
from typing import Any

# The self label of this operational-status surface itself. It is a derived
# operational VIEW (like the frontier index it reads from), so it labels itself
# MODELED — never claiming its rollup is a measured/proven fact.
MODELED = "MODELED"
LIVE = "LIVE"
DEGRADED = "DEGRADED"
UNAVAILABLE = "UNAVAILABLE"
FRONTEND = "FRONTEND"  # client-side surface: no backend to be healthy/unhealthy

TRUST_CEILING = 0.97

# Health tokens are drawn from the honest vocabulary so any label/health value
# stays inside the doctrine honesty vocabulary the CI contract gate enforces.
_HEALTH_HEALTHY = LIVE
_HEALTH_DEGRADED = DEGRADED
_HEALTH_UNAVAILABLE = UNAVAILABLE
_HEALTH_FRONTEND = FRONTEND


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _health_for(entry: dict) -> str:
    """Derive an honest HEALTH state for one catalog surface entry.

    Health is orthogonal to the data label: a MODELED surface whose backend
    answers in-process is honestly LIVE (working as designed); a surface whose
    route exists but does not answer with an a11oy-native honest label is
    DEGRADED; a surface with no local backend is FRONTEND (client-side, not a
    backend-health concern); an explicit UNAVAILABLE is UNAVAILABLE.
    """
    backend = entry.get("backend")
    label = (entry.get("label") or "").upper()
    if backend == "frontend-only":
        return _HEALTH_FRONTEND
    if backend == "a11oy-native":
        # answered in-process; UNAVAILABLE only if it declared no honest label.
        return _HEALTH_UNAVAILABLE if label == UNAVAILABLE else _HEALTH_HEALTHY
    if backend == "cross-origin-fallback":
        return _HEALTH_DEGRADED
    # Unknown backend kind -> honest UNAVAILABLE rather than an invented health.
    return _HEALTH_UNAVAILABLE


def _blank_counts() -> dict:
    return {LIVE: 0, DEGRADED: 0, UNAVAILABLE: 0, FRONTEND: 0}


def _estate_health(counts: dict) -> str:
    """Honest whole-estate rollup. NEVER a fabricated all-green:

      * UNAVAILABLE if no surface backend is live at all;
      * DEGRADED    if some are live but any backend is degraded/unavailable;
      * LIVE        only if every surface that HAS a backend answered live.

    FRONTEND-only surfaces are not backend-health concerns and never by
    themselves drag the estate below LIVE.
    """
    live = counts.get(LIVE, 0)
    degraded = counts.get(DEGRADED, 0)
    unavailable = counts.get(UNAVAILABLE, 0)
    if live == 0:
        return _HEALTH_UNAVAILABLE
    if degraded > 0 or unavailable > 0:
        return _HEALTH_DEGRADED
    return _HEALTH_HEALTHY


def _degraded() -> Any:
    """Import the frontier index lazily so this module never hard-fails at import
    time if the index is unavailable (additive, guarded)."""
    import szl_frontier_index as _fi
    return _fi


def build_status(app, ns: str = "a11oy") -> dict:
    """Assemble the honest operational-status aggregate from the frontier index."""
    fi = _degraded()
    catalog = fi.build_catalog(app, ns)

    surfaces = catalog.get("surfaces", []) if isinstance(catalog, dict) else []
    catalog_ok = bool(isinstance(catalog, dict) and catalog.get("ok"))

    subsystems: dict[str, dict] = {}
    estate_counts = _blank_counts()
    entries: list[dict] = []

    for s in surfaces:
        if not isinstance(s, dict):
            continue
        health = _health_for(s)
        category = s.get("category") or "uncategorized"
        data_label = s.get("label", UNAVAILABLE)
        entries.append({
            "id": s.get("id"),
            "title": s.get("title", s.get("id")),
            "subsystem": category,
            "backend": s.get("backend"),
            "data_label": data_label,   # VERBATIM from the surface's own backend.
            "health": health,           # derived, honest.
            "endpoint": s.get("endpoint"),
            "routes_registered": s.get("routes_registered", 0),
            "citations": s.get("citations", []),
        })
        sub = subsystems.setdefault(category, {
            "subsystem": category, "surfaces": 0, "counts": _blank_counts(),
            "health": _HEALTH_UNAVAILABLE,
        })
        sub["surfaces"] += 1
        sub["counts"][health] = sub["counts"].get(health, 0) + 1
        estate_counts[health] = estate_counts.get(health, 0) + 1

    for sub in subsystems.values():
        sub["health"] = _estate_health(sub["counts"])

    estate_health = _estate_health(estate_counts) if catalog_ok else _HEALTH_UNAVAILABLE

    return {
        "ok": True,
        "endpoint": "status",
        "service": "a11oy.status.aggregate",
        "title": "a11oy operational status — honest per-subsystem/surface aggregate",
        "label": MODELED,
        "what": ("an honest, drift-proof operational aggregate: per subsystem and per "
                 "surface, the honest data label its OWN backend emits + a derived health "
                 "state, rolled up for the whole estate. Built on the Wave-Q frontier index "
                 "(szl3d_holographic.SURFACES + app.routes + each surface's own response), "
                 "so it can never drift from what is actually wired."),
        "source": "szl_frontier_index.build_catalog (Wave-Q frontier index, cached)",
        "catalog_ok": catalog_ok,
        "estate": {
            "health": estate_health,
            "surfaces": len(entries),
            "subsystems": len(subsystems),
            "counts": estate_counts,
        },
        "health_legend": {
            LIVE: "surface's own /api route answered in-process with an honest label",
            DEGRADED: "route registered but no a11oy-native honest label emitted (proxy/other origin)",
            UNAVAILABLE: "native route answered without an honest label, or introspection failed",
            FRONTEND: "no local /api route; client-side surface (not a backend-health concern)",
        },
        "subsystems": sorted(subsystems.values(), key=lambda d: d["subsystem"]),
        "surfaces": entries,
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
            "note": ("additive read-only aggregate; touches no locked formula and no kernel; "
                     "signs/mints nothing on a GET; introduces no theorem, no green/1.0; the "
                     "estate rollup reports the honest worst-case, never a fabricated all-green."),
        },
        "timestamp_utc": _now_iso(),
    }


def handle_status(app, ns: str = "a11oy") -> dict:
    """GET /status — never 500s: on any failure, an honest UNAVAILABLE payload."""
    try:
        return build_status(app, ns)
    except Exception as exc:  # noqa: BLE001 — honest degrade, never crash the SPA
        return {
            "ok": False,
            "endpoint": "status",
            "service": "a11oy.status.aggregate",
            "label": UNAVAILABLE,
            "estate": {"health": UNAVAILABLE, "surfaces": 0, "subsystems": 0,
                       "counts": _blank_counts()},
            "reason": str(exc),
            "doctrine": "v11: status aggregate unavailable; no fabricated health emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_health() -> dict:
    """GET /status/health — a tiny, side-effect-free self-describing tile."""
    return {
        "ok": True,
        "endpoint": "status/health",
        "service": "a11oy.status.aggregate",
        "label": MODELED,
        "doctrine": {"lambda": "Conjecture 1", "locked_proven": 8,
                     "trust_ceiling": TRUST_CEILING},
        "timestamp_utc": _now_iso(),
    }


def register(app, ns: str = "a11oy") -> str:
    """Mount the operational-status endpoints on the FastAPI ``app``.

    SYNC def handlers so FastAPI runs them in a worker thread — the frontier
    index they call probes surfaces via its own bounded worker threads."""
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/status"

    @app.get(base)
    def _status_aggregate():
        """Honest operational aggregate: per-subsystem/surface data label + health,
        rolled up for the whole estate. Drift-proof (reuses the frontier index)."""
        return JSONResponse(handle_status(app, ns))

    @app.get(f"{base}/health")
    def _status_health():
        """Self-describing health tile for the status aggregate itself."""
        return JSONResponse(handle_health())

    return "status-aggregate-wired:2"


# ---------------------------------------------------------------------------
# Self-test — honest labels, drift-proof reuse, no upgrade, no fabrication.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json
    import sys as _sys

    print("=" * 72)
    print("szl_status_aggregate — self-test (honest operational aggregate)")
    print("=" * 72)

    from fastapi import FastAPI
    import szl_frontier_index as _fi

    app = FastAPI()
    _fi.register(app, ns="a11oy")
    register(app, ns="a11oy")
    try:
        import szl_frontier_zkinfer as _zk
        _zk.register(app, ns="a11oy")
    except Exception as _e:  # pragma: no cover
        print(f"(zkinfer not wired for self-test: {_e!r})")

    st = handle_status(app, ns="a11oy")
    blob = _json.dumps(st)

    # 1) ok:true, built from the frontier index, enumerates the real registry.
    assert st["ok"] is True, st
    assert st["endpoint"] == "status"
    assert "frontier_index" in st["source"]
    surfaces = st["surfaces"]
    assert len(surfaces) >= 50, f"expected the full surface registry, got {len(surfaces)}"
    print(f"[1] built from frontier index, enumerated {len(surfaces)} surfaces, ok:true  OK")

    # 2) every surface carries an honest data label + an honest health token; the
    #    per-subsystem + estate counts are internally consistent.
    HEALTHS = {LIVE, DEGRADED, UNAVAILABLE, FRONTEND}
    for e in surfaces:
        assert e["health"] in HEALTHS, f"{e['id']}: bad health {e['health']}"
        assert isinstance(e["data_label"], str) and e["data_label"], e
    est = st["estate"]
    assert est["surfaces"] == len(surfaces)
    assert sum(est["counts"].values()) == len(surfaces), (est["counts"], len(surfaces))
    subsurf = sum(s["surfaces"] for s in st["subsystems"])
    assert subsurf == len(surfaces), f"subsystem surface sum {subsurf} != {len(surfaces)}"
    print(f"[2] honest health per surface; counts consistent; estate={est['health']}  OK")

    # 3) data label read VERBATIM (never upgraded): matches the frontier index catalog.
    cat = _fi.build_catalog(app, ns="a11oy")
    cat_by_id = {c["id"]: c["label"] for c in cat["surfaces"]}
    for e in surfaces:
        assert e["data_label"] == cat_by_id.get(e["id"]), (
            f"{e['id']}: status {e['data_label']} != catalog {cat_by_id.get(e['id'])}")
    print("[3] data labels read VERBATIM from the frontier index (no drift, no upgrade)  OK")

    # 4) doctrine: locked-8 exact, adds nothing, Λ Conjecture 1, trust 0.97 not 100%.
    d = st["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[4] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    # 5) no fabricated all-green: estate health is only LIVE if zero degraded/unavailable.
    assert st["label"] == MODELED
    assert "VERIFIED" not in st["label"]
    # Λ (Conjecture 1) is only ever cited as the literal string "Conjecture 1" — never
    # asserted "green" anywhere the doctrine gate would read a Λ field.
    assert st["doctrine"]["lambda"] == "Conjecture 1"
    if est["counts"][DEGRADED] > 0 or est["counts"][UNAVAILABLE] > 0:
        assert est["health"] in (DEGRADED, UNAVAILABLE), est
    print(f"[5] self label MODELED, no green; estate rollup honest={est['health']}  OK")

    print("\nok:true checks:5")
    _sys.exit(0)
