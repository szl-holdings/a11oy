#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainwatch.py — BRAIN WATCH: a governed honesty-posture DRIFT monitor.

The brain watch computes a deterministic honesty-posture SNAPSHOT of the live
knowledge graph and compares CURRENT vs a PRIOR snapshot (supplied by the caller)
to report DRIFT. It is PURE honesty / observability over the knowledge graph: it
advances NO detection / fusion / effector / targeting / cueing capability. It only
OBSERVES the structural honesty posture the estate's own brain graph already
declares — never fabricating a trend, never upgrading a label.

WHAT IT MEASURES, at request time (all real, read VERBATIM from the live graph via
a11oy_brain_graph / szl_brain_api — this module invents no node and harvests
nothing):
  * label_distribution  — the count/share of each honesty label the graph's OWN
                          nodes carry (HARVESTED / MODELED / LIVE / UNAVAILABLE …),
                          read VERBATIM, never upgraded.
  * community posture    — community_count, the largest-community share, the
                          singleton share, and a fragmentation ratio.
  * orphan_share         — the share of nodes with degree <= 1 (isolated / dangling
                          knowledge that connects to little else).
  * salience posture     — a Gini concentration of the PageRank salience and the
                          top-1 / top-5 salience mass share.
Every number is MEASURED from THIS live read (deterministic given the graph state).
The drift DELTA between CURRENT and a PRIOR snapshot is MODELED — a derived
comparison, never a measurement, and it is only computed when a real PRIOR snapshot
is supplied. With no prior, the watch reports BASELINE-ONLY honestly and fabricates
no trend.

DRIFT VERDICT over the reachable evidence:
  STABLE        — a prior was supplied and no tracked metric moved beyond epsilon.
  DRIFTING      — a prior was supplied and some tracked metric moved beyond epsilon,
                  but no honesty-degrading rise crossed its material threshold.
  DEGRADED      — the UNAVAILABLE share rose materially, or the orphan share rose
                  materially (honesty posture got worse this comparison).
  BASELINE-ONLY — no prior snapshot supplied; current posture only, no trend.
A DEGRADED verdict is never softened to STABLE/DRIFTING; a truthful DEGRADED beats a
fabricated STABLE.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info/watch reads mint NOTHING.
Only the POST compare endpoint emits an UNSIGNED SHA-256 content digest over the
drift aggregate (mirrors the govern/honestywall content-digest pattern) — a plain
content hash, never a fabricated signature, never a receipt on a GET.

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only OBSERVES.
    Touches no locked formula and no kernel.
  * Λ stays Conjecture 1 (advisory); introduces no theorem, no green/1.0, no proof
    of Λ. Khipu BFT remains Conjecture 2. Trust ceiling 0.97, never 100%.
  * No label is ever upgraded; a DEGRADED posture can never be reported as STABLE. A
    truthful BLOCKED/DEGRADED beats a fake green.
  * Pure stdlib (+numpy tolerated, not required). Additive routes, registered before
    the SPA catch-all; canonical domain a-11-oy.com; 0 runtime CDN.
"""

import datetime
import hashlib
import json

# Honesty-label vocabulary (doctrine v11). Re-stated here (not imported) so a broken
# import can never silently blank the vocabulary; tests grep these exact strings.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# Structural counts read from a live graph are MEASURED; a drift delta is MODELED.
LBL_MEASURED = "MEASURED"
LBL_MODELED = "MODELED"
LBL_UNAVAILABLE = "UNAVAILABLE"

# Drift verdicts.
STABLE = "STABLE"
DRIFTING = "DRIFTING"
DEGRADED = "DEGRADED"
BASELINE_ONLY = "BASELINE-ONLY"

# Verdict thresholds (fractions of nodes). A rise ABOVE these is honesty-degrading.
DEGRADE_UNAVAIL_RISE = 0.02   # +2 percentage-points of UNAVAILABLE share
DEGRADE_ORPHAN_RISE = 0.05    # +5 percentage-points of orphan (degree<=1) share
DRIFT_EPS = 0.01              # any tracked metric moving >1pp is DRIFTING

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "brainwatch"

# Metric keys tracked for drift (each is a fraction in [0,1] except where noted).
_TRACKED = (
    "unavailable_share", "orphan_share", "community_fragmentation",
    "largest_community_share", "singleton_community_share",
    "salience_gini", "salience_top1_share", "salience_top5_share",
)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _doctrine_block(note: str = "") -> dict:
    d = {
        "version": "v11",
        "label_top": LBL_MODELED,
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
    if note:
        d["note"] = note
    return d


# --------------------------------------------------------------------------- #
# Pure metric helpers (deterministic; stdlib only).
# --------------------------------------------------------------------------- #

def _gini(values: list) -> float:
    """Gini concentration of a list of non-negative weights. 0 = perfectly even,
    ->1 = one node holds all the mass. Deterministic; returns 0.0 for an empty or
    all-zero list (honest: no concentration to report)."""
    vals = sorted(float(v) for v in values if v is not None and v >= 0.0)
    n = len(vals)
    total = sum(vals)
    if n == 0 or total <= 0.0:
        return 0.0
    cum = 0.0
    for i, v in enumerate(vals, 1):
        cum += i * v
    g = (2.0 * cum) / (n * total) - (n + 1.0) / n
    # clamp tiny float excursions into [0,1]
    return max(0.0, min(1.0, g))


def _topk_share(values: list, k: int) -> float:
    """Share of total mass held by the top-k largest weights."""
    vals = sorted((float(v) for v in values if v is not None and v >= 0.0),
                  reverse=True)
    total = sum(vals)
    if total <= 0.0:
        return 0.0
    return sum(vals[:max(1, k)]) / total


# --------------------------------------------------------------------------- #
# Snapshot — a deterministic honesty-posture reading of ONE graph.
# --------------------------------------------------------------------------- #

def compute_posture(*, nodes: list, link_count: int, community_of: dict,
                    salience: dict, community_algo: str,
                    content_hash: str, ns: str) -> dict:
    """Build a MEASURED honesty-posture snapshot from raw graph primitives.

    Pure and deterministic: given the same graph state it returns the same
    snapshot. Structural counts are MEASURED from THIS read — never fabricated.

    Args:
      nodes:        list of node dicts, each with 'id', 'label', 'degree'.
      link_count:   the real len() of the graph's links.
      community_of: id -> community-id mapping (as computed by the brain index).
      salience:     id -> PageRank salience mapping (as computed by the index).
      community_algo: the algorithm name the index actually used (verbatim).
      content_hash: the graph's content hash (for correlating snapshots).
      ns:           namespace.
    """
    node_count = len(nodes)

    # ---- label distribution (VERBATIM, never upgraded) -------------------- #
    label_counts: dict = {}
    for n in nodes:
        lbl = n.get("label")
        key = str(lbl) if lbl is not None else "UNLABELLED"
        label_counts[key] = label_counts.get(key, 0) + 1
    label_shares = ({k: v / node_count for k, v in label_counts.items()}
                    if node_count else {})
    unavailable_share = label_shares.get("UNAVAILABLE", 0.0)

    # ---- orphan share (degree <= 1) --------------------------------------- #
    orphan_count = sum(1 for n in nodes if int(n.get("degree", 0) or 0) <= 1)
    orphan_share = (orphan_count / node_count) if node_count else 0.0

    # ---- community posture ------------------------------------------------ #
    comm_sizes: dict = {}
    for cid in community_of.values():
        comm_sizes[cid] = comm_sizes.get(cid, 0) + 1
    community_count = len(comm_sizes)
    sizes = sorted(comm_sizes.values(), reverse=True)
    largest_community_share = (sizes[0] / node_count) if (sizes and node_count) else 0.0
    singleton_communities = sum(1 for s in sizes if s == 1)
    singleton_community_share = (singleton_communities / community_count
                                 if community_count else 0.0)
    # fragmentation: communities per node — higher = more fragmented posture.
    community_fragmentation = (community_count / node_count) if node_count else 0.0

    # ---- salience concentration ------------------------------------------- #
    sal_values = [salience.get(n["id"], 0.0) for n in nodes]
    salience_gini = _gini(sal_values)
    salience_top1_share = _topk_share(sal_values, 1)
    salience_top5_share = _topk_share(sal_values, 5)

    metrics = {
        "label_distribution": dict(sorted(label_counts.items(),
                                           key=lambda kv: (-kv[1], kv[0]))),
        "label_shares": {k: round(v, 6) for k, v in sorted(
            label_shares.items(), key=lambda kv: (-kv[1], kv[0]))},
        "unavailable_share": round(unavailable_share, 6),
        "orphan_count": orphan_count,
        "orphan_share": round(orphan_share, 6),
        "community_count": community_count,
        "community_algo": community_algo,
        "largest_community_share": round(largest_community_share, 6),
        "singleton_community_share": round(singleton_community_share, 6),
        "community_fragmentation": round(community_fragmentation, 6),
        "salience_gini": round(salience_gini, 6),
        "salience_top1_share": round(salience_top1_share, 6),
        "salience_top5_share": round(salience_top5_share, 6),
    }

    return {
        "label": LBL_MEASURED,
        "surface_id": SURFACE_ID,
        "ns": ns,
        "content_hash": content_hash,
        "node_count": node_count,
        "link_count": link_count,
        "metrics": metrics,
        "measurement": ("all metrics MEASURED from THIS live graph read; "
                        "deterministic given the graph state. Honesty labels are "
                        "read VERBATIM from each node and never upgraded."),
        "timestamp_utc": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Live snapshot — reuse the AUDITED brain index (never re-harvest).
# --------------------------------------------------------------------------- #

def live_snapshot(ns: str = "a11oy") -> dict:
    """Read the live brain graph + index and compute the current posture snapshot.

    Fully guarded: if the brain index/graph is unavailable, returns an honest
    UNAVAILABLE snapshot rather than raising or fabricating numbers."""
    try:
        import szl_brain_api as _brain_api
        idx = _brain_api.get_index(ns)
        salience = getattr(idx, "_pagerank_global", {}) or {}
        return compute_posture(
            nodes=idx.nodes,
            link_count=len(idx.links),
            community_of=idx.community_of,
            salience=salience,
            community_algo=idx.community_algo,
            content_hash=idx.content_hash,
            ns=ns,
        )
    except Exception as exc:  # honest degrade — never a fabricated snapshot
        return {
            "label": LBL_UNAVAILABLE,
            "surface_id": SURFACE_ID,
            "ns": ns,
            "error": str(exc)[:200],
            "measurement": ("brain graph/index unavailable this request; no posture "
                            "fabricated (honest UNAVAILABLE)."),
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# Prior-snapshot extraction + drift comparison (the delta is MODELED).
# --------------------------------------------------------------------------- #

def _extract_metrics(obj) -> dict | None:
    """Pull the tracked numeric metrics out of a caller-supplied prior snapshot.

    Accepts either a full watch response ({"metrics": {...}} or nested under
    "current"/"snapshot"/"prior") or a bare metrics dict. Returns a flat dict of
    the tracked metrics that were actually present (never invents a missing one),
    or None if nothing usable was supplied — so a bogus/empty prior yields an
    honest BASELINE-ONLY, never a fabricated trend."""
    if not isinstance(obj, dict):
        return None
    # unwrap common envelopes
    for key in ("prior", "prior_snapshot", "current", "snapshot"):
        inner = obj.get(key)
        if isinstance(inner, dict):
            got = _extract_metrics(inner)
            if got:
                return got
    src = obj.get("metrics") if isinstance(obj.get("metrics"), dict) else obj
    out: dict = {}
    for k in _TRACKED:
        v = src.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = float(v)
    return out or None


def compare(current: dict, prior_obj) -> dict:
    """Compare CURRENT posture vs a PRIOR snapshot; return a drift verdict.

    The current snapshot's structural counts are MEASURED; the DRIFT (delta) is
    MODELED — a derived comparison, only computed when a real prior is supplied.
    With no usable prior, returns BASELINE-ONLY (no fabricated trend)."""
    cur_metrics = current.get("metrics", {}) if isinstance(current, dict) else {}
    prior_metrics = _extract_metrics(prior_obj)

    base = {
        "label": LBL_MODELED,
        "surface_id": SURFACE_ID,
        "endpoint": "brain/watch/compare",
        "current": current,
        "prior_provided": prior_metrics is not None,
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "MODELED drift over MEASURED snapshots; observe-only, touches no locked "
            "formula/kernel. GET reads mint nothing; POST compare emits an UNSIGNED "
            "SHA-256 content digest only. Λ = Conjecture 1, never a theorem."),
        "timestamp_utc": _now_iso(),
    }

    if prior_metrics is None:
        base.update({
            "verdict": BASELINE_ONLY,
            "verdict_reason": ("no prior snapshot supplied; reporting current posture "
                               "only. No trend is fabricated without a real prior."),
            "drift": None,
        })
        return base

    # ---- MODELED delta over the tracked metrics --------------------------- #
    delta: dict = {}
    for k in _TRACKED:
        c = cur_metrics.get(k)
        p = prior_metrics.get(k)
        if isinstance(c, (int, float)) and isinstance(p, (int, float)):
            delta[k] = round(float(c) - float(p), 6)

    d_unavail = delta.get("unavailable_share", 0.0)
    d_orphan = delta.get("orphan_share", 0.0)

    material: list = []
    if d_unavail > DEGRADE_UNAVAIL_RISE:
        material.append({
            "metric": "unavailable_share", "delta": d_unavail,
            "threshold": DEGRADE_UNAVAIL_RISE,
            "why": "UNAVAILABLE share rose materially — honesty posture degraded"})
    if d_orphan > DEGRADE_ORPHAN_RISE:
        material.append({
            "metric": "orphan_share", "delta": d_orphan,
            "threshold": DEGRADE_ORPHAN_RISE,
            "why": "orphan (degree<=1) share rose materially — posture degraded"})

    moved = [k for k, v in delta.items() if abs(v) > DRIFT_EPS]

    if material:
        verdict = DEGRADED
        reason = (f"{len(material)} honesty-degrading rise(s) crossed a material "
                  f"threshold; reported DEGRADED (never softened to STABLE).")
    elif moved:
        verdict = DRIFTING
        reason = (f"{len(moved)} tracked metric(s) moved beyond {DRIFT_EPS} but no "
                  f"honesty-degrading threshold was crossed.")
    else:
        verdict = STABLE
        reason = f"no tracked metric moved beyond {DRIFT_EPS}."

    # label-distribution L1 drift (share space) — MODELED, informational.
    cur_shares = cur_metrics.get("label_shares", {}) if isinstance(
        cur_metrics.get("label_shares"), dict) else {}
    all_labels = set(cur_shares)
    label_l1 = None
    if cur_shares:
        # prior label shares may be absent; only compute when the prior carried them.
        prior_full = prior_obj if isinstance(prior_obj, dict) else {}
        p_metrics = prior_full.get("metrics") if isinstance(
            prior_full.get("metrics"), dict) else prior_full
        p_shares = p_metrics.get("label_shares") if isinstance(
            p_metrics, dict) else None
        if isinstance(p_shares, dict):
            all_labels |= set(p_shares)
            label_l1 = round(sum(abs(cur_shares.get(l, 0.0) - p_shares.get(l, 0.0))
                                 for l in all_labels), 6)

    base.update({
        "verdict": verdict,
        "verdict_reason": reason,
        "drift": {
            "label": LBL_MODELED,
            "delta": delta,
            "moved_beyond_eps": moved,
            "drift_eps": DRIFT_EPS,
            "material_changes": material,
            "label_distribution_l1": label_l1,
            "thresholds": {
                "degrade_unavailable_rise": DEGRADE_UNAVAIL_RISE,
                "degrade_orphan_rise": DEGRADE_ORPHAN_RISE,
            },
            "note": ("delta is MODELED (a derived comparison over two MEASURED "
                     "snapshots), never a measurement."),
        },
    })
    return base


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), never GET.
# --------------------------------------------------------------------------- #

def _canonical_core(result: dict) -> str:
    """Deterministic canonical serialization of the drift-bearing content (excludes
    volatile timestamps), so the digest attests the VERDICT + evidence, not the clock."""
    cur = result.get("current", {}) if isinstance(result.get("current"), dict) else {}
    drift = result.get("drift") if isinstance(result.get("drift"), dict) else None
    core = {
        "verdict": result.get("verdict"),
        "prior_provided": result.get("prior_provided"),
        "current_metrics": cur.get("metrics"),
        "content_hash": cur.get("content_hash"),
        "delta": drift.get("delta") if drift else None,
        "material_changes": drift.get("material_changes") if drift else None,
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def _content_receipt(result: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the drift result (no signature
    fabricated). RECEIPT-ON-WRITE — only the POST compare path calls this."""
    canonical = _canonical_core(result)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainwatch.drift",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST compare)",
        "note": ("unsigned SHA-256 content digest of the drift result; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #

def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/watch/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/watch"
    return {
        "ok": True,
        "service": "a11oy.brain.watch",
        "endpoint": "brain/watch/info",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "title": "Brain Watch — knowledge-graph honesty-posture drift monitor",
        "what": ("computes a deterministic honesty-posture snapshot of the live brain "
                 "graph (label distribution, community/orphan/salience posture) and "
                 "compares CURRENT vs a caller-supplied PRIOR snapshot to report "
                 "DRIFT. Pure honesty/observability over the knowledge graph; advances "
                 "no detection/fusion/effector/targeting/cueing capability. Never "
                 "fabricates a trend without a real prior; never upgrades a label."),
        "endpoints": {
            "info": f"GET  {base}/info",
            "watch": f"GET  {base}",
            "compare": f"POST {base}/compare",
        },
        "metrics": [
            "label_distribution / label_shares (VERBATIM node labels; MEASURED)",
            "unavailable_share (MEASURED)",
            "orphan_share (degree<=1; MEASURED)",
            "community_count / largest_community_share / singleton_community_share / "
            "community_fragmentation (MEASURED)",
            "salience_gini / salience_top1_share / salience_top5_share (MEASURED)",
            "drift delta between CURRENT and PRIOR (MODELED, only with a real prior)",
        ],
        "verdicts": [STABLE, DRIFTING, DEGRADED, BASELINE_ONLY],
        "verdict_legend": {
            STABLE: "prior supplied; no tracked metric moved beyond epsilon",
            DRIFTING: "prior supplied; some metric moved, no material degradation",
            DEGRADED: ("UNAVAILABLE share or orphan share rose materially "
                       "(never softened to STABLE)"),
            BASELINE_ONLY: "no prior supplied; current posture only, no fabricated trend",
        },
        "thresholds": {
            "degrade_unavailable_rise": DEGRADE_UNAVAIL_RISE,
            "degrade_orphan_rise": DEGRADE_ORPHAN_RISE,
            "drift_eps": DRIFT_EPS,
        },
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — only POST /compare emits an "
                           "unsigned SHA-256 content digest."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "additive OBSERVE-only surface over the knowledge graph; touches no locked "
            "formula and no kernel; Λ = Conjecture 1, never a theorem."),
        "timestamp_utc": _now_iso(),
    }


def handle_watch(ns: str = "a11oy") -> dict:
    """GET /brain/watch — the CURRENT posture snapshot. PURE READ (mints nothing).

    With no prior (a GET carries none), the verdict is honestly BASELINE-ONLY and no
    trend is fabricated."""
    snap = live_snapshot(ns)
    out = {
        "ok": snap.get("label") != LBL_UNAVAILABLE,
        "endpoint": "brain/watch",
        "surface_id": SURFACE_ID,
        "label": snap.get("label", LBL_UNAVAILABLE),
        "verdict": BASELINE_ONLY,
        "verdict_reason": ("GET carries no prior snapshot; reporting current posture "
                           "only. POST a prior to /compare for a drift verdict. No "
                           "trend is fabricated."),
        "snapshot": snap,
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — GET mints nothing; "
                           "POST /compare digests."),
        "doctrine": _doctrine_block(
            "pure read; Λ = Conjecture 1; adds nothing to the locked-8."),
        "timestamp_utc": _now_iso(),
    }
    return out


def handle_compare(ns: str = "a11oy", prior_obj=None) -> dict:
    """POST /brain/watch/compare — drift of CURRENT vs a caller-supplied PRIOR +
    an UNSIGNED SHA-256 content-digest receipt (RECEIPT-ON-WRITE). Never 500s:
    honest degraded response on error."""
    try:
        current = live_snapshot(ns)
        result = compare(current, prior_obj)
        result["ok"] = True
        result["endpoint"] = "brain/watch/compare"
        result["receipt"] = _content_receipt(result)
        return result
    except Exception as exc:
        return {
            "ok": False, "endpoint": "brain/watch/compare", "label": LBL_UNAVAILABLE,
            "verdict": BASELINE_ONLY, "error": str(exc)[:200],
            "doctrine": "v11: compare unavailable; no fabricated verdict/receipt emitted.",
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# FastAPI router registration.
#   GET  info/watch — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST compare    — raw-Request handler via app.router.add_route (Starlette passes
#                     the Request positionally, version-proof under fastapi==0.137.x),
#                     with app.add_api_route as the fallback. The handler is annotated
#                     request: fastapi.Request. Registered BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #

def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/watch"

    @app.get(f"{base}/info")
    def _brainwatch_info():
        """Self-describing brain-watch manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainwatch_watch():
        """Current honesty-posture snapshot; BASELINE-ONLY (pure read; mints nothing)."""
        return JSONResponse(handle_watch(ns))

    async def _brainwatch_compare(request):
        """POST: drift of CURRENT vs the PRIOR snapshot in the body + an UNSIGNED
        SHA-256 content digest (RECEIPT-ON-WRITE). A missing/empty/bogus body yields
        an honest BASELINE-ONLY — never a fabricated trend."""
        prior_obj = None
        try:
            raw = await request.body()
            if raw:
                prior_obj = json.loads(raw)
        except Exception:  # a malformed body degrades to BASELINE-ONLY, never a 500
            prior_obj = None
        return JSONResponse(handle_compare(ns, prior_obj))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature
    # analysis (in the add_api_route fallback path) treats the param as the request
    # object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _brainwatch_compare.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    cmp_path = f"{base}/compare"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(cmp_path, _brainwatch_compare, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(cmp_path, _brainwatch_compare, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(cmp_path, _brainwatch_compare, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainwatch compare POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainwatch-wired:2(get-only)"

    return "brainwatch-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — honest posture, no fabricated trend, receipt only on write.
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainwatch — self-test (knowledge-graph honesty-posture drift)")
    print("=" * 72)

    # A small, fully synthetic fixture graph (no network, no heavy index build).
    fixture_nodes = [
        {"id": "a", "label": "HARVESTED", "degree": 4},
        {"id": "b", "label": "MODELED", "degree": 3},
        {"id": "c", "label": "LIVE", "degree": 2},
        {"id": "d", "label": "MODELED", "degree": 1},   # orphan (degree<=1)
        {"id": "e", "label": "UNAVAILABLE", "degree": 0},  # orphan
    ]
    community_of = {"a": "c0", "b": "c0", "c": "c1", "d": "c1", "e": "c2"}
    salience = {"a": 0.40, "b": 0.25, "c": 0.20, "d": 0.10, "e": 0.05}

    snap = compute_posture(
        nodes=fixture_nodes, link_count=5, community_of=community_of,
        salience=salience, community_algo="fixture-cc", content_hash="deadbeef",
        ns="a11oy")

    # 1) snapshot metrics MEASURED + honest.
    assert snap["label"] == LBL_MEASURED
    m = snap["metrics"]
    assert snap["node_count"] == 5
    assert m["label_distribution"]["MODELED"] == 2
    assert abs(m["unavailable_share"] - 0.2) < 1e-9  # 1/5
    assert m["orphan_count"] == 2 and abs(m["orphan_share"] - 0.4) < 1e-9
    assert m["community_count"] == 3
    assert 0.0 <= m["salience_gini"] <= 1.0
    print(f"[1] snapshot MEASURED — node_count=5, unavailable_share="
          f"{m['unavailable_share']}, orphan_share={m['orphan_share']}, "
          f"communities={m['community_count']}, gini={m['salience_gini']}  OK")

    # 2) BASELINE-ONLY when no prior — NO fabricated trend.
    b = compare(snap, None)
    assert b["verdict"] == BASELINE_ONLY and b["drift"] is None
    assert b["prior_provided"] is False
    print("[2] no prior => BASELINE-ONLY, drift=None (no fabricated trend)  OK")

    # 3) STABLE vs DEGRADED on planted deltas.
    stable_prior = dict(snap)  # identical snapshot => STABLE
    st = compare(snap, stable_prior)
    assert st["verdict"] == STABLE, st["verdict"]

    # plant a prior with LOWER unavailable/orphan so CURRENT shows a material rise.
    degraded_prior = {"metrics": {
        "unavailable_share": 0.0, "orphan_share": 0.0,
        "community_fragmentation": m["community_fragmentation"],
        "largest_community_share": m["largest_community_share"],
        "singleton_community_share": m["singleton_community_share"],
        "salience_gini": m["salience_gini"],
        "salience_top1_share": m["salience_top1_share"],
        "salience_top5_share": m["salience_top5_share"],
    }}
    dg = compare(snap, degraded_prior)
    assert dg["verdict"] == DEGRADED, dg["verdict"]
    assert any(c["metric"] == "unavailable_share" for c in dg["drift"]["material_changes"])
    print(f"[3] identical prior => STABLE; unavailable/orphan rise => DEGRADED "
          f"(never softened)  OK")

    # 4) RECEIPT-ON-WRITE: compare handler mints an unsigned sha256; watch mints none.
    r = _content_receipt(dg)
    assert r["algorithm"] == "sha256" and len(r["content_sha256"]) == 64
    assert r["signed"] is False and r["mode"] == "UNSIGNED-CONTENT-DIGEST"
    w = handle_watch("a11oy")  # live read (may be UNAVAILABLE off-box) — must mint nothing
    assert "receipt" not in w, "GET watch must NOT mint a receipt (receipt-on-write)"
    # deterministic digest: same content => same hash.
    assert _content_receipt(dg)["content_sha256"] == r["content_sha256"]
    print(f"[4] POST digest={r['content_sha256'][:16]}… unsigned + deterministic; "
          f"GET watch mints nothing  OK")

    # 5) doctrine: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 not 100%.
    d = b["doctrine"]
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    # labels stay in the honest vocabulary and are never upgraded.
    assert LBL_MEASURED in HONEST_LABELS and LBL_MODELED in HONEST_LABELS
    print("[5] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    print("\nok:true checks:5")
    _sys.exit(0)
