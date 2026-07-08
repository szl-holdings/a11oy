#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainmemory.py — BRAIN MEMORY FRESHNESS: governed episodic memory-freshness / decay
honesty for the estate knowledge graph.

WHAT IT DOES (honest by construction):
  It reuses the SAME honest brain graph (szl_brain_api.get_index -> a11oy_brain_graph) and
  computes a deterministic, explainable memory-freshness score per node. It invents no nodes,
  harvests nothing, and — critically — NEVER fabricates a timestamp or a decay curve it cannot
  measure.

  RECENCY SIGNAL, HONESTLY LABELLED. A "freshness" score wants a real recency signal (when was
  this node last harvested / seen?). This estate's harvested nodes carry node_label, degree,
  salience, community and title — but NO per-node harvest timestamp. So this module DETECTS at
  request time whether any real recency field is present:

    * recency field present on the nodes  -> MODELED freshness (recency ⊕ structural proxy),
                                             the recency component derived from the real
                                             timestamp delta read THIS request.
    * NO recency field (the estate today) -> STRUCTURAL-ONLY freshness: a connectivity/salience
                                             PROXY, LABELLED STRUCTURAL-ONLY. It does NOT claim
                                             to measure decay; it flags the WEAKLY-embedded
                                             nodes (low degree, low salience) as the ones most
                                             likely to be stale and in need of re-harvest. It
                                             NEVER invents a timestamp or a decay half-life.

  PER-COMPONENT, EXPLAINABLE. Every ranked node reports its components (recency where real,
  connectivity, salience) and the weights, so the score is auditable, never a black box.

  VERDICT + HONEST NOTE. Each node gets FRESH / AGING / STALE from fixed thresholds. STALE nodes
  carry the honest note that they should be RE-HARVESTED, never silently trusted. When no real
  recency signal exists the whole surface says so (STRUCTURAL-ONLY) rather than pretend to decay.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info/ranking reads mint NOTHING. Only the POST
receipt endpoint emits an UNSIGNED SHA-256 content digest over the freshness aggregate (mirrors
the honestywall content-digest pattern) — a plain content hash, never a fabricated signature.

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only READS + ranks.
  - Λ stays Conjecture 1 (advisory); introduces no theorem, no green/1.0. Trust ceiling 0.97.
  - A label is NEVER upgraded: STRUCTURAL-ONLY is never printed as MODELED/MEASURED; the score
    is never printed as MEASURED. A truthful STRUCTURAL-ONLY beats a fabricated freshness.
  - Pure stdlib + numpy. Additive routes, registered before the SPA catch-all. 0 runtime CDN.
"""

import datetime
import hashlib
import json
import math
from typing import Any

try:  # numpy is a core dep; stay honest if it is somehow absent.
    import numpy as _np
    _HAVE_NUMPY = True
except Exception:  # pragma: no cover
    _np = None
    _HAVE_NUMPY = False

# Honest-label vocabulary (doctrine v11), re-stated (not imported) so a broken import can never
# blank it. This surface only ever emits MODELED or STRUCTURAL-ONLY as its OWN top label — never
# MEASURED (there is no live decay meter), never upgraded.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

MODELED = "MODELED"
STRUCTURAL_ONLY = "STRUCTURAL-ONLY"
UNAVAILABLE = "UNAVAILABLE"

# Freshness verdicts.
FRESH = "FRESH"
AGING = "AGING"
STALE = "STALE"

# Verdict thresholds on the freshness score in [0,1] (fixed + documented, never tuned per node).
FRESH_MIN = 0.60   # freshness >= 0.60            -> FRESH
AGING_MIN = 0.30   # 0.30 <= freshness < 0.60     -> AGING
#                    freshness < 0.30             -> STALE

# Component weights. Two honest modes; the weights are reported so the score is auditable.
#   MODELED (a real recency field exists): recency dominates, structure supports.
#   STRUCTURAL-ONLY (no recency field):    connectivity + salience proxy ONLY (no recency term).
WEIGHTS_MODELED = {"recency": 0.50, "connectivity": 0.30, "salience": 0.20}
WEIGHTS_STRUCTURAL = {"connectivity": 0.60, "salience": 0.40}

# Candidate per-node recency fields. If a node carries one of these (a REAL captured timestamp),
# freshness becomes MODELED and the recency component is derived from its delta. The estate's
# harvested nodes carry NONE of these today -> the surface degrades honestly to STRUCTURAL-ONLY.
RECENCY_FIELDS = (
    "harvested_at", "captured_at", "last_seen", "last_seen_at", "updated_at",
    "created_at", "seen_at", "timestamp", "mtime", "epoch",
)

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html + the .js).
SURFACE_ID = "brainmemory"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _now_ts() -> float:
    return datetime.datetime.now(datetime.timezone.utc).timestamp()


# --------------------------------------------------------------------------- #
# Normalisation helpers — deterministic min-max to [0,1]. numpy where present,
# pure-python fallback otherwise (identical result). A constant column -> all 0.0
# (nothing distinguishes the nodes on that axis, so it contributes nothing).
# --------------------------------------------------------------------------- #

def _minmax(values: list) -> list:
    if not values:
        return []
    if _HAVE_NUMPY:
        arr = _np.asarray(values, dtype=float)
        lo = float(arr.min())
        hi = float(arr.max())
        if hi - lo <= 1e-12:
            return [0.0] * len(values)
        return [float(x) for x in (arr - lo) / (hi - lo)]
    lo = min(values)
    hi = max(values)
    if hi - lo <= 1e-12:
        return [0.0] * len(values)
    return [(float(x) - lo) / (hi - lo) for x in values]


def _parse_ts(val: Any) -> float | None:
    """Parse a recency field VERBATIM into an epoch float. Accepts a numeric epoch or an ISO-8601
    string. Never guesses: an unparseable value yields None (that node has no honest recency)."""
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str) and val.strip():
        s = val.strip()
        try:
            return float(s)
        except ValueError:
            pass
        try:
            iso = s.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.timestamp()
        except Exception:
            return None
    return None


def _detect_recency_field(raw_nodes: list) -> str | None:
    """Return the first RECENCY_FIELD that is present + parseable on ANY node, else None. Honest:
    we only claim a recency signal when a real, parseable timestamp actually exists in the data."""
    for field in RECENCY_FIELDS:
        for n in raw_nodes:
            if isinstance(n, dict) and field in n and _parse_ts(n.get(field)) is not None:
                return field
    return None


def _verdict(score: float) -> str:
    if score >= FRESH_MIN:
        return FRESH
    if score >= AGING_MIN:
        return AGING
    return STALE


# --------------------------------------------------------------------------- #
# Core scoring — PURE, deterministic, dependency-free (works on plain dicts so it
# is unit-testable without a live graph). Each input node is a dict carrying at
# least: id, degree, salience, and (optionally) community, title, kind, plus a
# recency field when one exists. Returns the full freshness aggregate.
# --------------------------------------------------------------------------- #

def compute_freshness(nodes: list, *, recency_field: str | None = None,
                      now_ts: float | None = None, top: int | None = None) -> dict:
    """Compute the deterministic freshness aggregate over `nodes`.

    If `recency_field` is given AND real timestamps parse -> MODELED (recency ⊕ structural).
    Otherwise -> STRUCTURAL-ONLY (connectivity + salience proxy, no invented decay)."""
    nodes = [n for n in nodes if isinstance(n, dict) and n.get("id") is not None]
    n = len(nodes)

    degrees = [float(x.get("degree", 0) or 0) for x in nodes]
    saliences = [float(x.get("salience", 0.0) or 0.0) for x in nodes]

    # Recency is honest ONLY if the field is present AND parseable on this data.
    ts_values: list = []
    have_recency = False
    if recency_field:
        parsed = [_parse_ts(x.get(recency_field)) for x in nodes]
        if any(p is not None for p in parsed):
            have_recency = True
            # Missing/unparseable timestamps on some nodes -> treated as OLDEST (min), never
            # fabricated as fresh. This is the honest-pessimistic choice.
            present = [p for p in parsed if p is not None]
            floor = min(present) if present else 0.0
            ts_values = [p if p is not None else floor for p in parsed]

    conn_norm = _minmax(degrees)
    sal_norm = _minmax(saliences)

    if have_recency:
        # Newer -> higher. min-max over the real epoch deltas read THIS request.
        rec_norm = _minmax(ts_values)
        weights = dict(WEIGHTS_MODELED)
        label = MODELED
        mode = "recency+structural"
    else:
        rec_norm = [None] * n
        weights = dict(WEIGHTS_STRUCTURAL)
        label = STRUCTURAL_ONLY
        mode = "structural-only"

    ranking: list = []
    verdict_counts = {FRESH: 0, AGING: 0, STALE: 0}
    for i, node in enumerate(nodes):
        components: dict = {
            "connectivity": round(conn_norm[i], 6),
            "salience": round(sal_norm[i], 6),
        }
        if have_recency:
            components["recency"] = round(rec_norm[i], 6)
            score = (weights["recency"] * rec_norm[i]
                     + weights["connectivity"] * conn_norm[i]
                     + weights["salience"] * sal_norm[i])
        else:
            components["recency"] = None  # honest: no recency signal available
            score = (weights["connectivity"] * conn_norm[i]
                     + weights["salience"] * sal_norm[i])
        score = max(0.0, min(1.0, score))
        verdict = _verdict(score)
        verdict_counts[verdict] += 1

        entry = {
            "id": node.get("id"),
            "title": node.get("title", node.get("id")),
            "kind": node.get("kind"),
            "community": node.get("community"),
            "degree": int(degrees[i]),
            "salience": round(saliences[i], 8),
            "freshness": round(score, 6),
            "verdict": verdict,
            "label": label,
            "components": components,
        }
        if verdict == STALE:
            entry["note"] = ("weakly-embedded / low-freshness — RE-HARVEST recommended; "
                             "do not silently trust this node")
        ranking.append(entry)

    # Deterministic order: freshest first, ties broken by id (stable, reproducible).
    ranking.sort(key=lambda e: (-e["freshness"], str(e["id"])))
    if isinstance(top, int) and top > 0:
        ranking = ranking[:top]

    return {
        "label": label,
        "mode": mode,
        "recency_signal": have_recency,
        "recency_field": recency_field if have_recency else None,
        "weights": weights,
        "thresholds": {"FRESH": f">= {FRESH_MIN}", "AGING": f">= {AGING_MIN}", "STALE": f"< {AGING_MIN}"},
        "node_count": n,
        "verdict_counts": verdict_counts,
        "ranking": ranking,
        "honest_note": _honest_note(have_recency),
        "computed_at_utc": _now_iso(),
    }


def _honest_note(have_recency: bool) -> str:
    if have_recency:
        return ("freshness is MODELED: a recency component (from the real per-node timestamp "
                "delta read this request) combined with a connectivity/salience structural "
                "proxy. STALE nodes should be re-harvested, never silently trusted.")
    return ("no real per-node recency signal exists on the estate graph, so freshness is "
            "STRUCTURAL-ONLY: a connectivity + salience PROXY, NOT a decay measurement. It flags "
            "weakly-embedded nodes (low degree, low salience) as the ones most likely to be "
            "stale and worth re-harvesting. No timestamp or decay half-life is fabricated.")


# --------------------------------------------------------------------------- #
# Live wiring — reuse the AUDITED brain index (szl_brain_api.get_index). Guarded:
# if the brain index is unavailable, degrade honestly (UNAVAILABLE) rather than raise.
# --------------------------------------------------------------------------- #

def _load_nodes(ns: str) -> tuple[list, str | None]:
    """Return (nodes, recency_field). Each node dict carries id/degree/salience/community/title/
    kind sourced from the reused honest brain index. recency_field is detected from the RAW graph
    nodes (which may carry more fields than the ranked view)."""
    import szl_brain_api as _api
    idx = _api.get_index(ns)
    # salience() ranks EVERY node when asked for all of them, with degree/salience/community.
    ranked = idx.salience(top=len(idx.ids)) if getattr(idx, "ids", None) else []
    nodes: list = []
    by_id = getattr(idx, "by_id", {}) or {}
    for r in ranked:
        raw = by_id.get(r.get("id"), {})
        entry = {
            "id": r.get("id"),
            "title": r.get("title"),
            "kind": r.get("kind"),
            "degree": r.get("degree", 0),
            "salience": r.get("salience", 0.0),
            "community": r.get("community"),
        }
        # carry through any recency field verbatim if the raw node has one
        for f in RECENCY_FIELDS:
            if isinstance(raw, dict) and f in raw:
                entry[f] = raw[f]
        nodes.append(entry)
    recency_field = _detect_recency_field(list(by_id.values()))
    return nodes, recency_field


def build_aggregate(ns: str = "a11oy", top: int | None = None) -> dict:
    """Build the live freshness aggregate over the reused honest brain graph. Never raises: an
    honest UNAVAILABLE aggregate on any failure (no fabricated freshness)."""
    try:
        nodes, recency_field = _load_nodes(ns)
        agg = compute_freshness(nodes, recency_field=recency_field, now_ts=_now_ts(), top=top)
        agg.update({
            "ok": True,
            "endpoint": "brain/memory",
            "service": "a11oy.brain.memory",
            "surface_id": SURFACE_ID,
            "title": "Brain Memory Freshness — honest episodic decay proxy",
            "doctrine": _doctrine(),
            "honest_labels_vocabulary": list(HONEST_LABELS),
            "timestamp_utc": _now_iso(),
        })
        return agg
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False,
            "endpoint": "brain/memory",
            "service": "a11oy.brain.memory",
            "surface_id": SURFACE_ID,
            "label": UNAVAILABLE,
            "recency_signal": False,
            "recency_field": None,
            "node_count": 0,
            "ranking": [],
            "verdict_counts": {FRESH: 0, AGING: 0, STALE: 0},
            "error": str(exc)[:200],
            "doctrine": _doctrine(),
            "honest_note": "brain memory freshness unavailable; no fabricated freshness emitted.",
            "timestamp_utc": _now_iso(),
        }


def _doctrine() -> dict:
    return {
        "version": "v11",
        "locked_proven": LOCKED_COUNT,
        "locked_set": list(LOCKED_SET),
        "kernel_commit": KERNEL_COMMIT,
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
        "note": ("READ-only freshness ranking; touches no locked formula and no kernel; GET "
                 "reads sign/mint nothing; POST receipt emits an UNSIGNED SHA-256 content digest "
                 "only; introduces no theorem, no green/1.0. Λ is Conjecture 1, never a theorem."),
    }


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), NEVER on GET.
# --------------------------------------------------------------------------- #

def _canonical_core(aggregate: dict) -> str:
    """Deterministic canonical serialization of the freshness-bearing content (excludes the
    volatile timestamp), so the digest attests the VERDICTS + evidence, not the clock."""
    core = {
        "label": aggregate.get("label"),
        "mode": aggregate.get("mode"),
        "recency_signal": aggregate.get("recency_signal"),
        "recency_field": aggregate.get("recency_field"),
        "weights": aggregate.get("weights"),
        "node_count": aggregate.get("node_count"),
        "verdict_counts": aggregate.get("verdict_counts"),
        "ranking": [
            {"id": e.get("id"), "freshness": e.get("freshness"),
             "verdict": e.get("verdict"), "label": e.get("label"),
             "components": e.get("components")}
            for e in aggregate.get("ranking", [])
        ],
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def content_receipt(aggregate: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the freshness aggregate (no signature)."""
    canonical = _canonical_core(aggregate)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainmemory.freshness",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST receipt)",
        "note": ("unsigned SHA-256 content digest of the freshness aggregate; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #

def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/memory/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/memory"
    return {
        "ok": True,
        "endpoint": "brain/memory/info",
        "service": "a11oy.brain.memory",
        "surface_id": SURFACE_ID,
        "title": "Brain Memory Freshness — honest episodic decay proxy",
        "label": MODELED,
        "what": ("a deterministic, explainable memory-freshness score per knowledge-graph node, "
                 "derived from honest signals ONLY. If a real per-node recency timestamp exists "
                 "the score is MODELED (recency ⊕ structural); otherwise it is STRUCTURAL-ONLY (a "
                 "connectivity + salience proxy, never an invented decay curve). Reuses the same "
                 "honest brain graph; invents no nodes, harvests nothing, fabricates no timestamp."),
        "endpoints": {
            "info": f"GET  {base}/info",
            "ranking": f"GET  {base}?top=",
            "receipt": f"POST {base}/receipt",
        },
        "formula": {
            "modeled": ("freshness = 0.50·recency + 0.30·connectivity + 0.20·salience  "
                        "(when a real per-node recency timestamp exists)"),
            "structural_only": ("freshness = 0.60·connectivity + 0.40·salience  "
                                "(no recency signal — LABELLED STRUCTURAL-ONLY, not a decay measurement)"),
            "components": {
                "recency": "min-max of the REAL per-node timestamp delta (newest→1); omitted when absent",
                "connectivity": "min-max of node degree (how embedded the node is in the graph)",
                "salience": "min-max of PageRank salience (how load-bearing the node is)",
            },
            "verdicts": {"FRESH": f"freshness >= {FRESH_MIN}", "AGING": f">= {AGING_MIN}",
                         "STALE": f"< {AGING_MIN} — RE-HARVEST recommended, never silently trusted"},
        },
        "honest_labels": {
            "MODELED": "used ONLY when a real recency timestamp is present",
            "STRUCTURAL-ONLY": "used when NO recency signal exists — a proxy, never MEASURED, never upgraded",
            "note": "the score is NEVER labelled MEASURED — there is no live decay meter.",
        },
        "recency_fields_probed": list(RECENCY_FIELDS),
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — GET info/ranking mint nothing; only "
                           "POST /receipt emits an unsigned SHA-256 content digest."),
        "doctrine": _doctrine(),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "timestamp_utc": _now_iso(),
    }


def handle_ranking(ns: str = "a11oy", top: int = 25) -> dict:
    """GET /brain/memory?top= — freshness ranking + per-component breakdown + verdict. PURE READ
    (mints nothing). Label is MODELED or STRUCTURAL-ONLY, honestly, never upgraded."""
    top = max(1, min(int(top), 5000))
    return build_aggregate(ns, top=top)


def handle_receipt(ns: str = "a11oy") -> dict:
    """POST /brain/memory/receipt — the freshness aggregate + an UNSIGNED SHA-256 content-digest
    receipt (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    agg = build_aggregate(ns, top=None)
    out = dict(agg)
    out["endpoint"] = "brain/memory/receipt"
    out["receipt"] = content_receipt(agg)
    return out


# --------------------------------------------------------------------------- #
# FastAPI registration.
#   GET  info/ranking — normal FastAPI GET handlers (pure reads).
#   POST receipt      — raw-Request handler via app.router.add_route (Starlette passes the
#                       Request positionally, version-proof under fastapi==0.137.x), with
#                       app.add_api_route as the fallback. Annotated request: fastapi.Request.
#                       Registered BEFORE the SPA catch-all by serve.py.
# --------------------------------------------------------------------------- #

def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/memory"

    @app.get(f"{base}/info")
    def _brainmemory_info():
        """Self-describing brain-memory-freshness manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainmemory_ranking(top: int = 25):
        """Freshness ranking + per-component breakdown + verdict (pure read; mints nothing)."""
        return JSONResponse(handle_ranking(ns, top))

    async def _brainmemory_receipt(request):
        """POST: freshness aggregate + UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE).
        The body is ignored (a pure aggregate compute)."""
        return JSONResponse(handle_receipt(ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature analysis (in
    # the add_api_route fallback path) treats the param as the request object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _brainmemory_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rcpt_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rcpt_path, _brainmemory_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rcpt_path, _brainmemory_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rcpt_path, _brainmemory_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainmemory receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainmemory-wired:2(get-only)"

    return "brainmemory-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — honest verdicts, STRUCTURAL-ONLY when no recency, receipt only on write.
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainmemory — self-test (deterministic memory-freshness)")
    print("=" * 72)

    # Synthetic nodes with NO recency field -> STRUCTURAL-ONLY, verdict transitions present.
    synth = [
        {"id": "hub", "degree": 40, "salience": 0.9, "title": "hub"},
        {"id": "mid", "degree": 12, "salience": 0.3, "title": "mid"},
        {"id": "orphan", "degree": 0, "salience": 0.0, "title": "orphan"},
    ]
    agg = compute_freshness(synth, recency_field=None)
    assert agg["label"] == STRUCTURAL_ONLY
    assert agg["recency_signal"] is False
    assert agg["ranking"][0]["id"] == "hub"          # most embedded -> freshest
    assert agg["ranking"][-1]["id"] == "orphan"      # orphan -> stalest
    assert agg["ranking"][-1]["verdict"] == STALE
    assert agg["ranking"][-1]["components"]["recency"] is None
    for e in agg["ranking"]:
        assert 0.0 <= e["freshness"] <= 1.0
        assert e["label"] == STRUCTURAL_ONLY  # never upgraded
    print(f"[1] STRUCTURAL-ONLY (no recency): hub FRESH..orphan STALE  OK "
          f"(verdicts={agg['verdict_counts']})")

    # Synthetic nodes WITH a real recency field -> MODELED, recency component populated.
    synth_ts = [
        {"id": "new", "degree": 5, "salience": 0.2, "harvested_at": 2_000_000_000},
        {"id": "old", "degree": 5, "salience": 0.2, "harvested_at": 1_000_000_000},
    ]
    agg2 = compute_freshness(synth_ts, recency_field="harvested_at")
    assert agg2["label"] == MODELED and agg2["recency_signal"] is True
    assert agg2["ranking"][0]["id"] == "new"         # newer timestamp -> fresher
    assert agg2["ranking"][0]["components"]["recency"] == 1.0
    assert agg2["ranking"][-1]["components"]["recency"] == 0.0
    print("[2] MODELED (real recency): newer > older; recency component populated  OK")

    # Receipt: deterministic on the SAME aggregate; RECEIPT-ON-WRITE only.
    r1 = content_receipt(agg)
    r2 = content_receipt(agg)
    assert r1["content_sha256"] == r2["content_sha256"] and len(r1["content_sha256"]) == 64
    assert r1["signed"] is False and r1["mode"] == "UNSIGNED-CONTENT-DIGEST"
    # a DIFFERENT aggregate -> a different digest.
    assert content_receipt(agg2)["content_sha256"] != r1["content_sha256"]
    info = handle_info("a11oy")
    assert "receipt" not in info, "GET info must NOT mint a receipt (receipt-on-write-not-on-read)"
    print(f"[3] receipt deterministic sha256={r1['content_sha256'][:16]}… ; GET mints nothing  OK")

    # Doctrine: locked-8 exact, adds nothing, Λ Conjecture 1, trust 0.97 not 100%.
    d = _doctrine()
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[4] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    print("\nok:true checks:4")
    _sys.exit(0)
