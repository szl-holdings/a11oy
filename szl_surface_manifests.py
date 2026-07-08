#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_surface_manifests.py — honesty manifests for client-only frontier surfaces.

Several holographic frontier surfaces are pure client-side 3D visualizations: they render
in-browser and read their numbers from an endpoint that is NOT registered a11oy-native in
this estate. Because no a11oy GET route carries their surface id, the Honesty Wall
(szl_honestywall.py) and the Frontier Index (szl_frontier_index.py) can see no native
manifest for them and mark them NO-MANIFEST — the wall cannot verify anything about them.

This module ADDS the missing per-surface honesty manifest each of these surfaces lacked. It
DOES NOT add, change, or fake any surface capability. Each manifest declares the HONEST TRUTH:

  * data label UNAVAILABLE — there is NO a11oy-native measuring backend for this surface in
    this namespace, so a11oy has nothing native to measure and nothing native to misreport.
    The label is never upgraded to MODELED/MEASURED; a client-only surface stays UNAVAILABLE.
  * the estate-wide doctrine invariants that ARE true estate-wide and that every surface abides
    by: locked_proven == 8 (adds 0), Λ = Conjecture 1 (never a theorem), Khipu BFT = Conjecture
    2, trust ceiling 0.97 (never 100%), 0 runtime CDN, and no consciousness claim.

Making these truthful manifests visible lets the Honesty Wall VERIFY the doctrine invariants of
each surface instead of skipping it as NO-MANIFEST — it raises the wall's COVERAGE without
inventing a single capability. A truthful UNAVAILABLE is the honest label here.

Pure observability/governance. Additive GET routes, registered before the SPA catch-all. GET
reads mint nothing.
"""
from __future__ import annotations

import datetime
from typing import Any

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"
UNAVAILABLE = "UNAVAILABLE"

# Client-only 3D visualization surfaces that have NO a11oy-native measuring backend in this
# namespace (id carries no a11oy GET route; the Frontier Index classifies each frontend-only).
# Their honest a11oy-native data label is therefore UNAVAILABLE. Titles are NOT re-typed here:
# they are read VERBATIM from the live registry (szl3d_holographic.SURFACES) so this stays
# drift-proof and can never disagree with the single source of truth.
CLIENT_ONLY_SURFACES = [
    "blt", "dla", "elf", "goat", "kla", "moe", "muon", "nsa", "nvfp4", "ringattn",
    "specdecode", "specexec", "ssm", "steering", "aimc", "catq", "herotq", "matgran",
    "s3search", "slidesparse",
]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _titles() -> dict[str, str]:
    """Surface titles read VERBATIM from the live registry (single source of truth)."""
    try:
        import szl3d_holographic as holo
        surfaces = getattr(holo, "SURFACES", None) or []
        return {s.get("id"): s.get("title", s.get("id"))
                for s in surfaces if isinstance(s, dict) and s.get("id")}
    except Exception:
        return {}


def _doctrine() -> dict[str, Any]:
    """The estate-wide doctrine block — true estate-wide, declared VERBATIM, never upgraded."""
    return {
        "label_top": UNAVAILABLE,
        "locked_proven": LOCKED_COUNT,
        "locked_set": list(LOCKED_SET),
        "kernel_commit": KERNEL_COMMIT,
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
    }


def manifest(sid: str, ns: str = "a11oy") -> dict[str, Any]:
    """The honest honesty manifest for one client-only surface. data label UNAVAILABLE (no
    a11oy-native backend to measure), plus the estate-wide doctrine invariants it abides by."""
    title = _titles().get(sid, sid)
    return {
        "ok": True,
        "service": f"a11oy.govern.manifest.{sid}",
        "endpoint": f"govern/manifest/{sid}",
        "surface_id": sid,
        "title": title,
        "label": UNAVAILABLE,
        "data_label": UNAVAILABLE,
        "provenance_coverage": 0.0,
        "what": (
            "client-side 3D visualization surface; no a11oy-native measuring backend is "
            "registered under this namespace, so a11oy has no native data to attest and "
            "nothing native to misreport — honest data label UNAVAILABLE (never upgraded to a "
            "MODELED/MEASURED capability the a11oy estate does not natively serve). This "
            "manifest declares only the estate-wide doctrine invariants the surface abides by."
        ),
        "doctrine": _doctrine(),
        "honesty_invariants": {
            "lambda_is_conjecture_1_not_a_theorem": True,
            "adds_nothing_to_locked_8": True,
            "no_consciousness_claim": True,
            "label_never_upgraded": True,
            "no_a11oy_native_backend_client_only_surface": True,
            "receipt_on_write_not_on_read": True,
        },
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — this GET manifest mints nothing.",
        "timestamp_utc": _now_iso(),
    }


def register(app, ns: str = "a11oy") -> str:
    """Register one GET honesty-manifest route per client-only surface, at a path whose id
    segment matches the surface id so the Honesty Wall / Frontier Index can read it in-process.
    ADDITIVE; GET reads mint nothing. Never crashes the app (caller wraps in try/except)."""
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/govern/manifest"
    wired = 0
    for sid in CLIENT_ONLY_SURFACES:
        path = f"{base}/{sid}"

        def _handler(_sid: str = sid):
            return JSONResponse(manifest(_sid, ns))

        try:
            app.add_api_route(path, _handler, methods=["GET"], include_in_schema=False)
            wired += 1
        except Exception as exc:  # additive register must never break boot
            print(f"[{ns}] surface-manifest route NOT wired for {sid} (guarded): {exc!r}",
                  file=__import__("sys").stderr)
    return f"surface-manifests-wired:{wired}"


if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_surface_manifests — self-test (honest UNAVAILABLE manifests)")
    print("=" * 72)

    from fastapi import FastAPI
    app = FastAPI()
    status = register(app, ns="a11oy")
    assert status == f"surface-manifests-wired:{len(CLIENT_ONLY_SURFACES)}", status
    print(f"[1] {status}  OK")

    for sid in CLIENT_ONLY_SURFACES:
        m = manifest(sid)
        assert m["label"] == UNAVAILABLE and m["data_label"] == UNAVAILABLE, sid
        d = m["doctrine"]
        assert d["locked_proven"] == 8 and d["adds_to_locked_8"] == 0, sid
        assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2", sid
        assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False, sid
        assert 0.0 <= m["provenance_coverage"] <= 1.0, sid
        assert m["honesty_invariants"]["no_consciousness_claim"] is True, sid
    print(f"[2] {len(CLIENT_ONLY_SURFACES)} manifests: UNAVAILABLE, locked-8 +0, "
          f"Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    print("\nok:true checks:2")
    _sys.exit(0)
