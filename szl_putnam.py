"""
szl_putnam.py — Putnam 2025 canonical-set honest verdict layer (a11oy console tab)
==================================================================================

Serves the **honest, per-problem** kernel verdict for the canonical Putnam 2025
set (86th Putnam, Dec 6 2025: A1-A6, B1-B6) plus the three kernel-clean SZL
originals that ship alongside it, transcribed faithfully from the Lean sources
on ``szl-holdings/lutar-lean`` branch ``putnam-2025-canonical-set``.

Source of truth
---------------
Every status below mirrors the ``Honest status:`` label written into each Lean
source file at the pinned commit. Nothing here is inflated:

* REAL  = kernel-checked, zero ``sorry``, axiom footprint within policy.
* DEMO  = compiles and faithfully states the problem, but the proof is
          DEFERRED with ``sorry`` (and/or unproven helper lemmas).
* OPEN  = the corrected answer is faithfully formalized, but the main proof is
          DEFERRED with ``sorry``; some helper lemmas may already be REAL.

The canonical 12 Putnam problems are currently **0 REAL / 10 DEMO / 2 OPEN**
(A3 and A6 are OPEN). The three SZL-native originals (EXPERIMENTAL companions,
NOT part of the Putnam 12) are **3 REAL**. These two tallies are kept SEPARATE
on purpose — the SZL originals never inflate the Putnam REAL count.

This module reads NOTHING from disk at runtime: the lutar-lean ``.lean`` files
are not vendored into the a11oy image, so the verdict is embedded here as cited
data and refreshed by re-deploying when the branch advances. Honest framing:
this is a transcribed snapshot of the per-file labels at the pinned commit, not
a live ``lake build`` performed inside this process.

Pattern mirrors szl_readiness.py / szl_contracting.py / szl_bounties.py::

    import szl_putnam
    szl_putnam.register(app, ns="a11oy")

Endpoints (per namespace ns)::

    GET /api/{ns}/v1/putnam
        -> { layer, honest, doctrine, source, sha, short, base, computed,
             putnam:{count,real,demo,open,problems:[...]},
             szl_originals:{count,real,items:[...]}, checked_at }
    GET /api/{ns}/v1/putnam/{problem_id}
        -> a single problem or SZL original (404 if unknown).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------
# Pinned canonical source (lutar-lean branch putnam-2025-canonical-set)
# --------------------------------------------------------------------------
_SHA = "baf483be3c832b64da47161b558e283d68da6650"
_SHORT = "baf483b"
_BRANCH = "putnam-2025-canonical-set"
_COMPUTED = "2026-06-15"  # date this snapshot was transcribed from the branch
_REPO = "szl-holdings/lutar-lean"
_TREE = "https://github.com/%s/tree/%s/Lutar/Putnam" % (_REPO, _SHA)
_BASE = "https://github.com/%s/blob/%s/Lutar/Putnam/" % (_REPO, _SHA)
_DOCTRINE = "v11"

_HONEST = (
    "Honest, doctrine-v11 per-problem verdict for the canonical Putnam 2025 set "
    "(A1-A6, B1-B6), transcribed faithfully from the `Honest status:` label in "
    "each Lean source on lutar-lean branch %s @%s. REAL = kernel-checked, zero "
    "`sorry`, in-policy axioms; DEMO = faithful statement, proof deferred with "
    "`sorry`; OPEN = corrected answer formalized, main proof deferred. The 12 "
    "Putnam problems are 0 REAL / 10 DEMO / 2 OPEN. The 3 SZL-native originals "
    "are kernel-clean (3 REAL) but are EXPERIMENTAL companions, NOT part of the "
    "Putnam 12, and never inflate the Putnam REAL count. This is a transcribed "
    "snapshot of the pinned commit, not a live `lake build` in this process."
) % (_BRANCH, _SHORT)

_SOURCE = "%s — Lutar/Putnam/*.lean @ %s (branch %s)" % (_REPO, _SHORT, _BRANCH)

# --------------------------------------------------------------------------
# Canonical 12 Putnam problems. (id, file, title, status, note)
# Status transcribed verbatim from each file's `Honest status:` label.
# --------------------------------------------------------------------------
_PUTNAM: List[Dict[str, str]] = [
    {
        "id": "A1", "file": "P_A1.lean", "title": "Putnam 2025 A1",
        "status": "DEMO",
        "note": "Faithful statement (2*mₖ+1 and 2*nₖ+1 coprime for all but "
                "finitely many k); proof deferred (`sorry`).",
    },
    {
        "id": "A2", "file": "P_A2.lean", "title": "Putnam 2025 A2",
        "status": "DEMO",
        "note": "Faithful statement with the official extremal answer; proof "
                "deferred (`sorry`).",
    },
    {
        "id": "A3", "file": "P_A3.lean", "title": "Putnam 2025 A3",
        "status": "OPEN",
        "note": "Corrected answer: the SECOND player (Bob) wins for every "
                "n ≥ 1. Formalized via a second-player pairing strategy; the "
                "main theorem is deferred (`sorry`). The combinatorial helpers "
                "`card_positions` and `three_pow_odd'` are REAL (kernel-checked).",
    },
    {
        "id": "A4", "file": "P_A4.lean", "title": "Putnam 2025 A4",
        "status": "DEMO",
        "note": "Faithful statement; proof deferred (`sorry`).",
    },
    {
        "id": "A5", "file": "P_A5.lean", "title": "Putnam 2025 A5",
        "status": "DEMO",
        "note": "Faithful statement; proof deferred (`sorry`).",
    },
    {
        "id": "A6", "file": "P_A6.lean", "title": "Putnam 2025 A6",
        "status": "OPEN",
        "note": "General powers-of-two divisibility claim deferred (`sorry`). "
                "Base data b₁..b₄ and d_pow_one are REAL; the naive LINEAR-index "
                "reading is REAL-proven FALSE "
                "(`putnam_A6_original_statement_is_false`).",
    },
    {
        "id": "B1", "file": "P_B1.lean", "title": "Putnam 2025 B1",
        "status": "DEMO",
        "note": "Faithful statement; proof deferred (`sorry`).",
    },
    {
        "id": "B2", "file": "P_B2.lean", "title": "Putnam 2025 B2",
        "status": "DEMO",
        "note": "Faithful statement; proof deferred (`sorry`).",
    },
    {
        "id": "B3", "file": "P_B3.lean", "title": "Putnam 2025 B3",
        "status": "DEMO",
        "note": "Faithful statement; proof deferred (`sorry`).",
    },
    {
        "id": "B4", "file": "P_B4.lean", "title": "Putnam 2025 B4",
        "status": "DEMO",
        "note": "Faithful statement; proof deferred (`sorry`).",
    },
    {
        "id": "B5", "file": "P_B5.lean", "title": "Putnam 2025 B5",
        "status": "DEMO",
        "note": "Faithful statement; proof deferred (`sorry`).",
    },
    {
        "id": "B6", "file": "P_B6.lean", "title": "Putnam 2025 B6",
        "status": "DEMO",
        "note": "Faithful statement with the official extremal answer; proof "
                "deferred (`sorry`).",
    },
]

# --------------------------------------------------------------------------
# SZL-native originals (EXPERIMENTAL companions, all REAL). (id, file, title,
# status, theorems, note). file paths are under Lutar/Putnam/SZL/.
# --------------------------------------------------------------------------
_SZL: List[Dict[str, Any]] = [
    {
        "id": "SZL-LambdaEquiv", "file": "SZL/LambdaEquiv.lean",
        "title": "Positive-scaling equivalence (Λ ≈ scaling)",
        "status": "REAL",
        "theorems": ["scaleEquiv_refl", "scaleEquiv_symm", "scaleEquiv_trans",
                     "scaleEquiv_equivalence"],
        "note": "Positive scaling on a real vector space is an equivalence "
                "relation — the scale-invariance backbone of the Λ-invariant "
                "story (Λ identified up to positive scaling). Kernel-checked, "
                "zero `sorry`, no new axiom.",
    },
    {
        "id": "SZL-ReceiptVerify", "file": "SZL/ReceiptVerify.lean",
        "title": "Receipt sign / verify correctness",
        "status": "REAL",
        "theorems": ["verify_sign", "verify_iff", "verify_tamper"],
        "note": "Receipt verification is sound (a signed receipt verifies), "
                "complete (verifies iff the tag is canonical), and "
                "tamper-evident (a non-canonical tag fails). Models the a11oy "
                "receipt-signing backbone. Kernel-checked, zero `sorry`, no "
                "new axiom.",
    },
    {
        "id": "SZL-Robustness", "file": "SZL/Robustness.lean",
        "title": "Scaling robustness (Lipschitz bound)",
        "status": "REAL",
        "theorems": ["scaling_lipschitz_eq", "scaling_lipschitz",
                     "scaling_nonexpansive"],
        "note": "Scaling by c on ℝ is exactly |c|-Lipschitz, hence "
                "nonexpansive when |c| ≤ 1 — the robustness backbone behind "
                "certified-radius style guarantees. Kernel-checked, zero "
                "`sorry`, no new axiom.",
    },
]


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _file_url(rel: str) -> str:
    return _BASE + rel


def _putnam_block() -> Dict[str, Any]:
    real = sum(1 for p in _PUTNAM if p["status"] == "REAL")
    demo = sum(1 for p in _PUTNAM if p["status"] == "DEMO")
    open_ = sum(1 for p in _PUTNAM if p["status"] == "OPEN")
    problems = [{
        "id": p["id"], "title": p["title"], "file": p["file"],
        "url": _file_url(p["file"]), "status": p["status"], "note": p["note"],
    } for p in _PUTNAM]
    return {
        "set": "Putnam 2025 (86th Putnam, Dec 6 2025) — A1-A6, B1-B6",
        "count": len(_PUTNAM), "real": real, "demo": demo, "open": open_,
        "problems": problems,
    }


def _szl_block() -> Dict[str, Any]:
    real = sum(1 for s in _SZL if s["status"] == "REAL")
    items = [{
        "id": s["id"], "title": s["title"], "file": s["file"],
        "url": _file_url(s["file"]), "status": s["status"],
        "theorems": s.get("theorems", []), "note": s["note"],
    } for s in _SZL]
    return {
        "set": "SZL-native originals (EXPERIMENTAL companions, not part of the "
               "Putnam 12)",
        "count": len(_SZL), "real": real, "items": items,
    }


def _payload(ns: str) -> Dict[str, Any]:
    return {
        "layer": "%s putnam 2025 honest verdict" % ns,
        "honest": _HONEST,
        "doctrine": _DOCTRINE,
        "source": _SOURCE,
        "repo": _REPO,
        "branch": _BRANCH,
        "sha": _SHA,
        "short": _SHORT,
        "tree": _TREE,
        "base": _BASE,
        "computed": _COMPUTED,
        "putnam": _putnam_block(),
        "szl_originals": _szl_block(),
        "checked_at": _now_iso(),
    }


def _find(problem_id: str) -> Optional[Dict[str, Any]]:
    pid = (problem_id or "").strip()
    low = pid.lower()
    for p in _PUTNAM:
        if p["id"].lower() == low:
            return {"kind": "putnam", "id": p["id"], "title": p["title"],
                    "file": p["file"], "url": _file_url(p["file"]),
                    "status": p["status"], "note": p["note"]}
    for s in _SZL:
        if s["id"].lower() == low:
            return {"kind": "szl_original", "id": s["id"], "title": s["title"],
                    "file": s["file"], "url": _file_url(s["file"]),
                    "status": s["status"], "theorems": s.get("theorems", []),
                    "note": s["note"]}
    return None


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    """Attach the Putnam-2025 honest-verdict endpoints for ns to a FastAPI app."""
    try:
        from fastapi.responses import JSONResponse
    except Exception:  # pragma: no cover
        return {"layer": "putnam", "registered": False}

    base = "/api/%s/v1/putnam" % ns

    @app.get(base)
    async def _putnam_index():  # noqa: ANN202
        return JSONResponse(_payload(ns))

    @app.get(base + "/{problem_id}")
    async def _putnam_one(problem_id: str):  # noqa: ANN202
        hit = _find(problem_id)
        if hit is None:
            return JSONResponse(
                {"error": "unknown problem", "problem_id": problem_id,
                 "known": ([p["id"] for p in _PUTNAM]
                           + [s["id"] for s in _SZL])},
                status_code=404,
            )
        return JSONResponse({
            "layer": "%s putnam 2025 honest verdict" % ns,
            "honest": _HONEST, "doctrine": _DOCTRINE, "source": _SOURCE,
            "sha": _SHA, "short": _SHORT, "branch": _BRANCH,
            "problem": hit, "checked_at": _now_iso(),
        })

    pb = _putnam_block()
    sb = _szl_block()
    return {
        "layer": "putnam", "registered": True, "ns": ns, "base": base,
        "sha": _SHORT,
        "putnam": "%d REAL / %d DEMO / %d OPEN"
                  % (pb["real"], pb["demo"], pb["open"]),
        "szl_originals": "%d REAL" % sb["real"],
    }
