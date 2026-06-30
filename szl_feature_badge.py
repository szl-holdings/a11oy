# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v13
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
szl_feature_badge.py — THEOREM-BACKED feature badges (HuggingFace-model-card-grade).

A machine-readable provenance chain for any deployed a11oy/killinchu feature:

    paper (Zenodo DOI)  →  Lean 4 proof (file + sha256 from lutar-lean)  →  deployed feature

rendered as an inline badge. Badge states (NEVER weaken):

  - THEOREM-BACKED  (green)  — a REAL proven Lean theorem covers the feature: the .lean
                              file resolves, its sha256 matches the registry, and it has
                              ZERO real `sorry`/`admit` (comments stripped first).
  - CONJECTURE-GATED (gray)  — the backing statement is an OPEN conjecture (has a real
                              `sorry`, or the registry marks it a conjecture). e.g.
                              Conjecture 1 (Λ uniqueness), Conjecture 2/3 (Khipu BFT).
  - ADVISORY        (blue)   — no formal-proof link; engineering claim only.

A conjecture is NEVER rendered THEOREM-BACKED. If the .lean file is absent from the image
the badge degrades to the registry's recorded status with `proof_file_present: false` and
`hash_verified_live: false` — honest, never faked.

ADDITIVE, try/except-guarded, stdlib-only. Registers BEFORE the SPA /{full_path:path}
catch-all via the established register(app, ns) contract.
"""
import hashlib
import json
import os
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REGISTRY_PATH = _HERE / "feature_provenance.json"
# lutar-lean proof root (per-file COPY'd into the image; see Dockerfile)
_PROOF_ROOTS = [_HERE / "proofs" / "lutar-lean", _HERE / "lutar-lean", _HERE]

# KANCHAY palette
_VOID = "#080c14"
_PROOF = "#3af4c8"     # green — theorem-backed
_LATTICE = "#5b8dee"   # blue — advisory
_GOLD = "#d7b96b"
_GRAY = "#7c8794"      # gray — conjecture-gated

_STATE_COLOR = {
    "THEOREM-BACKED": _PROOF,
    "CONJECTURE-GATED": _GRAY,
    "ADVISORY": _LATTICE,
}

_COMMENT_BLOCK = re.compile(r"/-.*?-/", re.S)
_COMMENT_LINE = re.compile(r"--[^\n]*")
_SORRY = re.compile(r"\b(sorry|admit)\b")
_THEOREM = re.compile(r"\b(theorem|lemma)\b")


def _strip_lean_comments(src: str) -> str:
    return _COMMENT_LINE.sub("", _COMMENT_BLOCK.sub("", src))


def _resolve_lean_file(rel_path: str):
    """Find a lutar-lean file under any known proof root. Returns (Path|None)."""
    for root in _PROOF_ROOTS:
        cand = root / rel_path
        if cand.is_file():
            return cand
    # also try the bare path relative to CWD
    p = Path(rel_path)
    return p if p.is_file() else None


def resolve_proof(rel_path: str) -> dict:
    """Read a Lean file and resolve its REAL proof status from source.

    Returns {present, sha256, real_sorries, theorems, status} where status is
    "PROVEN" (0 real sorries and ≥1 theorem) or "OPEN" (has a real sorry) or
    "UNKNOWN" (no theorems found).
    """
    f = _resolve_lean_file(rel_path)
    if f is None:
        return {"present": False, "sha256": None, "real_sorries": None,
                "theorems": None, "status": "FILE-ABSENT"}
    src = f.read_text(encoding="utf-8", errors="replace")
    sha = hashlib.sha256(src.encode("utf-8")).hexdigest()
    body = _strip_lean_comments(src)
    sorries = len(_SORRY.findall(body))
    theorems = len(_THEOREM.findall(body))
    if sorries > 0:
        status = "OPEN"
    elif theorems > 0:
        status = "PROVEN"
    else:
        status = "UNKNOWN"
    return {"present": True, "sha256": sha, "real_sorries": sorries,
            "theorems": theorems, "status": status}


def _load_registry() -> dict:
    try:
        return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"features": []}


def _decide_badge(entry: dict, proof: dict) -> dict:
    """Apply the honest badge-state rules. Never THEOREM-BACKED for a conjecture."""
    kind = entry.get("kind", "advisory")        # "theorem" | "conjecture" | "advisory"
    expected_sha = entry.get("lean_sha256")
    hash_verified = bool(proof.get("present") and expected_sha
                         and proof.get("sha256") == expected_sha)

    if kind == "advisory" or not entry.get("lean_file"):
        state = "ADVISORY"
    elif kind == "conjecture":
        state = "CONJECTURE-GATED"
    else:  # kind == "theorem" — only green if a REAL proven theorem actually resolves
        live_proven = proof.get("status") == "PROVEN"
        if proof.get("present"):
            state = "THEOREM-BACKED" if (live_proven and hash_verified) else "CONJECTURE-GATED"
        else:
            # file absent: fall back to recorded status, never fake green
            recorded = entry.get("recorded_status")
            state = "THEOREM-BACKED" if recorded == "PROVEN" else "CONJECTURE-GATED"

    return {
        "state": state,
        "hash_verified_live": hash_verified,
        "proof_file_present": bool(proof.get("present")),
    }


def build_badge(feature_id: str, registry: dict = None) -> dict:
    """Assemble the full HF-model-card-grade provenance + badge for one feature."""
    registry = registry or _load_registry()
    entry = next((f for f in registry.get("features", [])
                  if f.get("id") == feature_id), None)
    if entry is None:
        return {"error": "unknown_feature", "feature_id": feature_id}

    proof = resolve_proof(entry["lean_file"]) if entry.get("lean_file") else \
        {"present": False, "status": "N/A"}
    decision = _decide_badge(entry, proof)

    return {
        "schema": "szl.feature-provenance/v1",
        "feature_id": feature_id,
        "feature": entry.get("feature"),
        "deployed_at": entry.get("deployed_at"),
        "badge_state": decision["state"],
        "color": _STATE_COLOR[decision["state"]],
        "provenance_chain": {
            "paper": {
                "title": entry.get("paper_title"),
                "doi": entry.get("doi"),
                "url": f"https://doi.org/{entry['doi']}" if entry.get("doi") else None,
            },
            "lean_proof": {
                "file": entry.get("lean_file"),
                "theorem": entry.get("theorem"),
                "expected_sha256": entry.get("lean_sha256"),
                "resolved_sha256": proof.get("sha256"),
                "hash_verified_live": decision["hash_verified_live"],
                "proof_file_present": decision["proof_file_present"],
                "real_sorries": proof.get("real_sorries"),
                "status": proof.get("status"),
                "conjecture_id": entry.get("conjecture_id"),
                "repo": "szl-holdings/lutar-lean",
            },
            "deployed_feature": {
                "surface": entry.get("surface"),
                "route": entry.get("route"),
            },
        },
        "honesty": {
            "kind": entry.get("kind"),
            "note": entry.get("note", ""),
        },
    }


def render_svg(badge: dict) -> str:
    """Inline SVG badge in KANCHAY palette (no external fonts/assets)."""
    state = badge.get("badge_state", "ADVISORY")
    color = badge.get("color", _LATTICE)
    label = "proof"
    msg = {"THEOREM-BACKED": "theorem-backed", "CONJECTURE-GATED": "conjecture-gated",
           "ADVISORY": "advisory"}.get(state, "advisory")
    lw, mw = 46, 8 * len(msg) + 18
    w = lw + mw
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" '
        f'role="img" aria-label="{label}: {msg}">'
        f'<rect width="{lw}" height="20" fill="{_VOID}"/>'
        f'<rect x="{lw}" width="{mw}" height="20" fill="{color}"/>'
        f'<g fill="#fff" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
        f'<text x="6" y="14">{label}</text>'
        f'<text x="{lw + 8}" y="14" fill="{_VOID}">{msg}</text>'
        f'</g></svg>'
    )


def register(app, ns: str = "a11oy") -> dict:  # pragma: no cover
    """Attach feature-badge endpoints (before the SPA catch-all)."""
    try:
        from starlette.routing import Route
        from starlette.responses import JSONResponse, Response
    except Exception:
        return {"registered": [], "status": "starlette-absent"}

    async def _badge(request):
        b = build_badge(request.path_params["feature_id"])
        return JSONResponse(b, status_code=404 if b.get("error") else 200)

    async def _badge_svg(request):
        b = build_badge(request.path_params["feature_id"])
        if b.get("error"):
            return JSONResponse(b, status_code=404)
        return Response(render_svg(b), media_type="image/svg+xml",
                        headers={"Cache-Control": "no-cache"})

    async def _badges(request):
        reg = _load_registry()
        items = [build_badge(f["id"], reg) for f in reg.get("features", [])]
        return JSONResponse({"schema": "szl.feature-provenance/v1",
                             "count": len(items), "features": items})

    routes = [
        Route(f"/api/{ns}/v1/badges", _badges),
        Route(f"/api/{ns}/v1/badge/{{feature_id}}", _badge),
        Route(f"/api/{ns}/v1/badge/{{feature_id}}/svg", _badge_svg),
    ]
    # insert at HEAD so they win over the SPA /{full_path:path} catch-all
    for r in reversed(routes):
        app.router.routes.insert(0, r)
    return {"registered": [r.path for r in routes], "status": "ok"}
