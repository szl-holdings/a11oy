#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_braingaps.py — BRAIN GAPS: an honest map of what the brain does NOT know.

Most brain surfaces describe what the graph HAS. This one is the mirror image: it
reports, deterministically and without flattery, where the live knowledge graph is
THIN or EMPTY — coverage gaps, sparsely-populated communities, weakly-connected
island nodes, and the share of nodes carrying no real honesty label. For a supplied
query it answers the one honest question a knowledge graph should never dodge: *do
we actually have grounding for THIS topic, or is it a GAP?*

It is PURE honesty / observability over the knowledge graph. It advances NO
detection / fusion / effector / targeting / cueing capability. It harvests nothing,
invents no node, and never fabricates coverage — a topic the graph cannot ground is
reported as a GAP, never dressed up as COVERED.

WHAT IT MEASURES, at request time (read VERBATIM from the live graph via
szl_brain_api / a11oy_brain_graph — structural counts of THIS read, MEASURED):
  * thin communities  — communities whose node count is at/below THIN_COMMUNITY_MAX
                        (little internal evidence; a sparse pocket of the graph).
  * island nodes       — nodes with degree <= ISLAND_DEGREE_MAX (0 = isolated, 1 =
                        dangling): knowledge that connects to little or nothing else.
  * label posture      — the count/share of each honesty label the graph's OWN nodes
                        carry, and the UNLABELLED / UNAVAILABLE share (weak grounding),
                        read VERBATIM, never upgraded.

PER-TOPIC VERDICT (a MODELED judgement over MEASURED matches; only real matches count):
  COVERED — enough matched nodes AND at least one is well-connected (real grounding).
  THIN    — some matches, but too few or all weakly-connected (fragile grounding).
  GAP     — no matched node at all (the brain has no grounding for this topic — said
            plainly, never fabricated into coverage).

ESTATE-WIDE VERDICT over the coverage posture:
  WELL-COVERED   — the graph is broadly connected: island share and thin-community
                   share are both below their material thresholds.
  PATCHY         — some sparsity (islands or thin communities present) but below the
                   material gap thresholds.
  SPARSE         — island share OR thin-community share is at/above its material
                   threshold (a materially gappy graph — never softened to WELL-COVERED).
A SPARSE posture is never reported as WELL-COVERED; a truthful SPARSE/GAP beats a fake
green.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info/gaps reads mint NOTHING. Only
the POST receipt endpoint emits an UNSIGNED SHA-256 content digest over the gap map
(mirrors the govern/honestywall content-digest pattern) — a plain content hash, never
a fabricated signature, never a receipt on a GET.

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only OBSERVES.
    Touches no locked formula and no kernel.
  * Λ stays Conjecture 1 (advisory); introduces no theorem, no green/1.0, no proof of
    Λ. Khipu BFT remains Conjecture 2. Trust ceiling 0.97, never 100%.
  * No label is ever upgraded; a GAP can never be reported as COVERED. A truthful
    GAP/SPARSE beats a fake green.
  * Pure stdlib (+numpy tolerated, not required). Additive routes, registered before
    the SPA catch-all; canonical domain a-11-oy.com; 0 runtime CDN.
"""

import datetime
import hashlib
import json
import re

# Honesty-label vocabulary (doctrine v11). Re-stated here (not imported) so a broken
# import can never silently blank the vocabulary; tests grep these exact strings.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# Structural counts read from a live graph are MEASURED; a derived verdict is MODELED.
LBL_MEASURED = "MEASURED"
LBL_MODELED = "MODELED"
LBL_UNAVAILABLE = "UNAVAILABLE"

# Per-topic verdicts.
COVERED = "COVERED"
THIN = "THIN"
GAP = "GAP"
TOPIC_VERDICTS = (COVERED, THIN, GAP)

# Estate-wide coverage verdicts.
WELL_COVERED = "WELL-COVERED"
PATCHY = "PATCHY"
SPARSE = "SPARSE"
ESTATE_VERDICTS = (WELL_COVERED, PATCHY, SPARSE)

# Structural thresholds (all deterministic, documented, and honest).
THIN_COMMUNITY_MAX = 3     # a community with <= 3 nodes is a THIN (sparse) pocket
ISLAND_DEGREE_MAX = 1      # degree <= 1 is an island (0 = isolated, 1 = dangling)
COVERED_MIN_MATCHES = 3    # a topic needs >= 3 matched nodes to be COVERED
COVERED_MIN_DEGREE = 2     # ... and >= 1 of them must have degree >= 2 (real grounding)

# Estate-wide material gap thresholds (fractions). At/above these => SPARSE.
SPARSE_ISLAND_SHARE = 0.50       # >= half the nodes are islands => materially sparse
SPARSE_THIN_COMMUNITY_SHARE = 0.50  # >= half the communities are thin => sparse

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "braingaps"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


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
# Pure helpers (deterministic; stdlib only).
# --------------------------------------------------------------------------- #

def _tokens(text: str) -> set:
    """Lowercase alphanumeric tokens of a string (deterministic, stdlib only)."""
    return set(_TOKEN_RE.findall((text or "").lower()))


def _node_text(n: dict) -> str:
    """The searchable text of a node: its title and id (VERBATIM, no harvest)."""
    return f"{n.get('title', '')} {n.get('id', '')}"


def _node_matches(nodes: list, query: str) -> list:
    """Nodes whose title/id tokens overlap the query tokens, or whose title/id contains
    the query substring. Deterministic; sorted by (-overlap, id). No fabrication — a
    query that matches nothing yields an empty list (an honest GAP upstream)."""
    qtokens = _tokens(query)
    qlower = (query or "").lower().strip()
    if not qtokens and not qlower:
        return []
    scored = []
    for n in nodes:
        ntokens = _tokens(_node_text(n))
        overlap = len(qtokens & ntokens)
        substr = bool(qlower and (qlower in str(n.get("title", "")).lower()
                                  or qlower in str(n.get("id", "")).lower()))
        if overlap <= 0 and not substr:
            continue
        scored.append((overlap, substr, n))
    scored.sort(key=lambda r: (-r[0], str(r[2].get("id", ""))))
    return [
        {"id": n.get("id"), "title": n.get("title", n.get("id")),
         "degree": int(n.get("degree", 0) or 0),
         "node_label": n.get("label"),
         "overlap": overlap, "substring": substr}
        for overlap, substr, n in scored
    ]


def topic_verdict(matches: list) -> tuple:
    """MODELED COVERED / THIN / GAP verdict over the MEASURED matched nodes.

    Never fabricates coverage: zero matches is a GAP, plainly. Coverage requires both
    enough matches AND real connectivity (a well-connected match) — otherwise THIN."""
    if not matches:
        return (GAP, "no node in the graph matches this topic; the brain has no "
                     "grounding for it (an honest GAP, never fabricated into coverage)")
    max_degree = max(int(m.get("degree", 0) or 0) for m in matches)
    if len(matches) >= COVERED_MIN_MATCHES and max_degree >= COVERED_MIN_DEGREE:
        return (COVERED, f"{len(matches)} matched node(s), best-connected degree "
                         f"{max_degree} (>= {COVERED_MIN_DEGREE}); real grounding present")
    return (THIN, f"only {len(matches)} matched node(s), best-connected degree "
                  f"{max_degree}; grounding is fragile (needs >= {COVERED_MIN_MATCHES} "
                  f"matches and a degree >= {COVERED_MIN_DEGREE} node to be COVERED)")


# --------------------------------------------------------------------------- #
# Coverage-gap analysis — deterministic, over plain graph primitives.
# --------------------------------------------------------------------------- #

def analyze(*, nodes: list, link_count: int, community_of: dict,
            community_algo: str, content_hash: str, ns: str,
            query: str = "") -> dict:
    """Build a MEASURED coverage-gap map from raw graph primitives.

    Pure and deterministic: the same graph state yields the same map. Structural
    counts are MEASURED from THIS read; the COVERED/THIN/GAP + estate verdicts are
    MODELED judgements over those MEASURED counts — never fabricated.

    Args:
      nodes:        list of node dicts, each with 'id', 'title', 'label', 'degree'.
      link_count:   the real len() of the graph's links.
      community_of: id -> community-id mapping (as computed by the brain index).
      community_algo: the algorithm name the index actually used (verbatim).
      content_hash: the graph's content hash (for correlating maps).
      ns:           namespace.
      query:        optional topic to grade COVERED / THIN / GAP.
    """
    node_count = len(nodes)

    # ---- island nodes (degree <= ISLAND_DEGREE_MAX) ----------------------- #
    islands = [n for n in nodes if int(n.get("degree", 0) or 0) <= ISLAND_DEGREE_MAX]
    isolated = [n for n in islands if int(n.get("degree", 0) or 0) == 0]
    island_count = len(islands)
    isolated_count = len(isolated)
    island_share = (island_count / node_count) if node_count else 0.0
    island_sample = sorted(
        (str(n.get("id")) for n in islands))[:25]  # bounded, deterministic sample

    # ---- thin communities (size <= THIN_COMMUNITY_MAX) -------------------- #
    comm_sizes: dict = {}
    for cid in community_of.values():
        comm_sizes[cid] = comm_sizes.get(cid, 0) + 1
    community_count = len(comm_sizes)
    thin_communities = [
        {"community": str(cid), "size": size, "verdict": THIN}
        for cid, size in sorted(comm_sizes.items(),
                                key=lambda kv: (kv[1], str(kv[0])))
        if size <= THIN_COMMUNITY_MAX
    ]
    thin_community_count = len(thin_communities)
    thin_community_share = (thin_community_count / community_count
                            if community_count else 0.0)

    # ---- label posture (VERBATIM; UNLABELLED/UNAVAILABLE = weak grounding) - #
    label_counts: dict = {}
    for n in nodes:
        lbl = n.get("label")
        key = str(lbl) if lbl is not None and str(lbl) != "" else "UNLABELLED"
        label_counts[key] = label_counts.get(key, 0) + 1
    label_shares = ({k: round(v / node_count, 6) for k, v in label_counts.items()}
                    if node_count else {})
    unlabelled_count = label_counts.get("UNLABELLED", 0)
    unavailable_count = label_counts.get("UNAVAILABLE", 0)
    # weak-grounding share = nodes with no real honesty label (UNLABELLED or UNAVAILABLE)
    weak_label_count = unlabelled_count + unavailable_count
    weak_label_share = (weak_label_count / node_count) if node_count else 0.0

    # ---- estate-wide coverage verdict (MODELED over MEASURED shares) ------ #
    if island_share >= SPARSE_ISLAND_SHARE or thin_community_share >= SPARSE_THIN_COMMUNITY_SHARE:
        estate_verdict = SPARSE
        estate_reason = (
            f"island share {round(island_share, 4)} or thin-community share "
            f"{round(thin_community_share, 4)} is at/above its material threshold; "
            "the graph is materially sparse (never softened to WELL-COVERED)")
    elif island_count or thin_community_count:
        estate_verdict = PATCHY
        estate_reason = (
            f"{island_count} island node(s) and {thin_community_count} thin "
            "community(ies) present, but below the material gap thresholds")
    else:
        estate_verdict = WELL_COVERED
        estate_reason = "no island nodes and no thin communities; broadly connected"

    metrics = {
        "node_count": node_count,
        "link_count": link_count,
        "island_count": island_count,
        "isolated_count": isolated_count,
        "island_share": round(island_share, 6),
        "island_degree_max": ISLAND_DEGREE_MAX,
        "island_sample": island_sample,
        "community_count": community_count,
        "community_algo": community_algo,
        "thin_community_count": thin_community_count,
        "thin_community_share": round(thin_community_share, 6),
        "thin_community_max_size": THIN_COMMUNITY_MAX,
        "thin_communities": thin_communities,
        "label_distribution": dict(sorted(label_counts.items(),
                                           key=lambda kv: (-kv[1], kv[0]))),
        "label_shares": dict(sorted(label_shares.items(),
                                    key=lambda kv: (-kv[1], kv[0]))),
        "unlabelled_count": unlabelled_count,
        "unavailable_count": unavailable_count,
        "weak_label_count": weak_label_count,
        "weak_label_share": round(weak_label_share, 6),
    }

    out = {
        "label": LBL_MEASURED,
        "surface_id": SURFACE_ID,
        "ns": ns,
        "content_hash": content_hash,
        "estate_verdict": estate_verdict,
        "estate_verdict_reason": estate_reason,
        "metrics": metrics,
        "measurement": ("structural counts (islands, thin communities, label posture) "
                        "are MEASURED from THIS live graph read, deterministic given the "
                        "graph state; honesty labels are read VERBATIM and never upgraded. "
                        "The COVERED/THIN/GAP and estate verdicts are MODELED judgements "
                        "over those MEASURED counts — no coverage is ever fabricated."),
        "thresholds": {
            "thin_community_max_size": THIN_COMMUNITY_MAX,
            "island_degree_max": ISLAND_DEGREE_MAX,
            "covered_min_matches": COVERED_MIN_MATCHES,
            "covered_min_degree": COVERED_MIN_DEGREE,
            "sparse_island_share": SPARSE_ISLAND_SHARE,
            "sparse_thin_community_share": SPARSE_THIN_COMMUNITY_SHARE,
        },
        "timestamp_utc": _now_iso(),
    }

    # ---- optional per-topic grounding verdict ----------------------------- #
    q = (query or "").strip()
    if q:
        matches = _node_matches(nodes, q)
        verdict, reason = topic_verdict(matches)
        out["topic"] = {
            "label": LBL_MODELED,
            "query": q,
            "verdict": verdict,
            "verdict_reason": reason,
            "match_count": len(matches),
            "best_connected_degree": (max((int(m.get("degree", 0) or 0)
                                           for m in matches)) if matches else 0),
            "matches": matches[:25],  # bounded, deterministic
            "note": ("verdict is MODELED over MEASURED token/substring matches; a topic "
                     "the graph cannot ground is a GAP, never fabricated into coverage."),
        }
    return out


# --------------------------------------------------------------------------- #
# Live gap map — reuse the AUDITED brain index (never re-harvest).
# --------------------------------------------------------------------------- #

def live_gaps(ns: str = "a11oy", query: str = "") -> dict:
    """Read the live brain graph + index and compute the current coverage-gap map.

    Fully guarded: if the brain index/graph is unavailable, returns an honest
    UNAVAILABLE map rather than raising or fabricating coverage."""
    try:
        import szl_brain_api as _brain_api
        idx = _brain_api.get_index(ns)
        return analyze(
            nodes=idx.nodes,
            link_count=len(idx.links),
            community_of=idx.community_of,
            community_algo=idx.community_algo,
            content_hash=idx.content_hash,
            ns=ns,
            query=query,
        )
    except Exception as exc:  # honest degrade — never a fabricated map
        return {
            "label": LBL_UNAVAILABLE,
            "surface_id": SURFACE_ID,
            "ns": ns,
            "estate_verdict": None,
            "error": str(exc)[:200],
            "measurement": ("brain graph/index unavailable this request; no coverage "
                            "map fabricated (honest UNAVAILABLE)."),
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), never GET.
# --------------------------------------------------------------------------- #

def _canonical_core(result: dict) -> str:
    """Deterministic canonical serialization of the gap-bearing content (excludes the
    volatile timestamp), so the digest attests the VERDICTS + evidence, not the clock."""
    metrics = result.get("metrics", {}) if isinstance(result.get("metrics"), dict) else {}
    topic = result.get("topic") if isinstance(result.get("topic"), dict) else None
    core = {
        "estate_verdict": result.get("estate_verdict"),
        "content_hash": result.get("content_hash"),
        "metrics": metrics,
        "topic": {
            "query": topic.get("query"),
            "verdict": topic.get("verdict"),
            "match_count": topic.get("match_count"),
        } if topic else None,
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def _content_receipt(result: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the gap map (no signature
    fabricated). RECEIPT-ON-WRITE — only the POST receipt path calls this."""
    canonical = _canonical_core(result)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.braingaps.map",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST receipt)",
        "note": ("unsigned SHA-256 content digest of the coverage-gap map; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #

def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/gaps/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/gaps"
    return {
        "ok": True,
        "service": "a11oy.brain.gaps",
        "endpoint": "brain/gaps/info",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "title": "Brain Gaps — an honest map of what the brain does NOT know",
        "what": ("computes a deterministic coverage-gap map of the live brain graph: "
                 "thin (sparse) communities, weakly-connected island nodes, and the "
                 "share of nodes with no real honesty label. For a supplied query it "
                 "grades the topic COVERED / THIN / GAP. Pure honesty/observability "
                 "over the knowledge graph; advances no detection/fusion/effector/"
                 "targeting/cueing capability. Never fabricates coverage — a topic the "
                 "graph cannot ground is reported as a GAP, never dressed up as COVERED."),
        "endpoints": {
            "info": f"GET  {base}/info",
            "gaps": f"GET  {base}",
            "gaps_for_topic": f"GET  {base}?q=",
            "receipt": f"POST {base}/receipt",
        },
        "metrics": [
            "island_count / island_share (degree<=1; MEASURED)",
            "isolated_count (degree==0; MEASURED)",
            "thin_community_count / thin_community_share (size<=3; MEASURED)",
            "label_distribution / label_shares (VERBATIM node labels; MEASURED)",
            "weak_label_share (UNLABELLED + UNAVAILABLE nodes; MEASURED)",
            "per-topic COVERED/THIN/GAP verdict (MODELED over MEASURED matches)",
        ],
        "topic_verdicts": list(TOPIC_VERDICTS),
        "topic_verdict_legend": {
            COVERED: (f">= {COVERED_MIN_MATCHES} matched nodes AND a node of degree "
                      f">= {COVERED_MIN_DEGREE} (real grounding)"),
            THIN: "some matches but too few or all weakly-connected (fragile grounding)",
            GAP: "no matched node at all — the brain has no grounding (never fabricated)",
        },
        "estate_verdicts": list(ESTATE_VERDICTS),
        "estate_verdict_legend": {
            WELL_COVERED: "no islands and no thin communities; broadly connected",
            PATCHY: "some sparsity present but below the material gap thresholds",
            SPARSE: ("island share OR thin-community share at/above its material "
                     "threshold (never softened to WELL-COVERED)"),
        },
        "thresholds": {
            "thin_community_max_size": THIN_COMMUNITY_MAX,
            "island_degree_max": ISLAND_DEGREE_MAX,
            "covered_min_matches": COVERED_MIN_MATCHES,
            "covered_min_degree": COVERED_MIN_DEGREE,
            "sparse_island_share": SPARSE_ISLAND_SHARE,
            "sparse_thin_community_share": SPARSE_THIN_COMMUNITY_SHARE,
        },
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — only POST /receipt emits an "
                           "unsigned SHA-256 content digest."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "additive OBSERVE-only surface over the knowledge graph; touches no locked "
            "formula and no kernel; Λ = Conjecture 1, never a theorem."),
        "timestamp_utc": _now_iso(),
    }


def handle_gaps(ns: str = "a11oy", query: str = "") -> dict:
    """GET /brain/gaps — the estate-wide gap map (and, with q=, the per-topic verdict).
    PURE READ (mints nothing). Never 500s: honest degraded response on error."""
    try:
        gmap = live_gaps(ns, query)
        available = gmap.get("label") != LBL_UNAVAILABLE
        return {
            "ok": available,
            "endpoint": "brain/gaps",
            "surface_id": SURFACE_ID,
            # this surface's OWN top label is MODELED (a derived gap map + verdict); the
            # structural counts INSIDE gaps.metrics are MEASURED. Honest either way, never
            # upgraded — UNAVAILABLE when the graph can't be read.
            "label": LBL_MODELED if available else LBL_UNAVAILABLE,
            "query": query or "",
            "estate_verdict": gmap.get("estate_verdict"),
            "gaps": gmap,
            "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — GET mints nothing; "
                               "POST /receipt digests."),
            "doctrine": _doctrine_block(
                "pure read; Λ = Conjecture 1; adds nothing to the locked-8. Coverage is "
                "never fabricated — a GAP is reported plainly."),
            "timestamp_utc": _now_iso(),
        }
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False, "endpoint": "brain/gaps", "label": LBL_UNAVAILABLE,
            "surface_id": SURFACE_ID, "estate_verdict": None, "error": str(exc)[:200],
            "doctrine": "v11: brain-gaps unavailable; no fabricated coverage emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_receipt(ns: str = "a11oy", query: str = "") -> dict:
    """POST /brain/gaps/receipt — the gap map + an UNSIGNED SHA-256 content-digest
    receipt (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    try:
        gmap = live_gaps(ns, query)
        available = gmap.get("label") != LBL_UNAVAILABLE
        out = {
            "ok": available,
            "endpoint": "brain/gaps/receipt",
            "surface_id": SURFACE_ID,
            "label": LBL_MODELED if available else LBL_UNAVAILABLE,
            "query": query or "",
            "estate_verdict": gmap.get("estate_verdict"),
            "gaps": gmap,
            "doctrine": _doctrine_block(
                "POST receipt emits an UNSIGNED SHA-256 content digest only; no signature "
                "fabricated; coverage never fabricated. Λ = Conjecture 1."),
            "timestamp_utc": _now_iso(),
        }
        out["receipt"] = _content_receipt(gmap)
        return out
    except Exception as exc:
        return {
            "ok": False, "endpoint": "brain/gaps/receipt", "label": LBL_UNAVAILABLE,
            "estate_verdict": None, "error": str(exc)[:200],
            "doctrine": "v11: receipt unavailable; no fabricated coverage/receipt emitted.",
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# FastAPI router registration.
#   GET  info/gaps — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST receipt   — raw-Request handler via app.router.add_route (Starlette passes the
#                    Request positionally, version-proof under fastapi==0.137.x), with
#                    app.add_api_route as the fallback. The handler is annotated
#                    request: fastapi.Request. Registered BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #

def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/gaps"

    @app.get(f"{base}/info")
    def _braingaps_info():
        """Self-describing brain-gaps manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _braingaps_gaps(q: str = ""):
        """Estate-wide coverage-gap map; with q=, the per-topic COVERED/THIN/GAP verdict
        (pure read; mints nothing)."""
        return JSONResponse(handle_gaps(ns, q))

    async def _braingaps_receipt(request):
        """POST: gap map + an UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE). Reads
        q from the query string when present; the body is otherwise ignored (a pure
        map compute)."""
        q = request.query_params.get("q", "")
        return JSONResponse(handle_receipt(ns, q))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature
    # analysis (in the add_api_route fallback path) treats the param as the request
    # object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _braingaps_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rec_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rec_path, _braingaps_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rec_path, _braingaps_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rec_path, _braingaps_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] braingaps receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "braingaps-wired:2(get-only)"

    return "braingaps-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — honest gaps, no fabricated coverage, receipt only on write.
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_braingaps — self-test (knowledge-graph coverage-gap honesty)")
    print("=" * 72)

    # A small, fully synthetic fixture graph (no network, no heavy index build). It has
    # a well-connected "lambda" cluster (COVERED), a dangling "khipu" node (THIN), and
    # zero mention of "quantum" (a GAP). "islet" is an isolated (degree 0) node.
    fixture_nodes = [
        {"id": "lambda-core", "title": "Lambda kernel core", "label": "MEASURED", "degree": 5},
        {"id": "lambda-proof", "title": "Lambda Conjecture 1 note", "label": "CONJECTURE", "degree": 4},
        {"id": "lambda-lemma", "title": "Lambda supporting lemma", "label": "MODELED", "degree": 3},
        {"id": "khipu-node", "title": "Khipu BFT sketch", "label": "MODELED", "degree": 1},  # island
        {"id": "islet", "title": "orphan islet", "label": "UNAVAILABLE", "degree": 0},  # isolated
    ]
    # communities: the lambda trio (c0, size 3 = thin at max) + two singletons (thin).
    community_of = {"lambda-core": "c0", "lambda-proof": "c0", "lambda-lemma": "c0",
                    "khipu-node": "c1", "islet": "c2"}

    gmap = analyze(
        nodes=fixture_nodes, link_count=6, community_of=community_of,
        community_algo="fixture-cc", content_hash="deadbeef", ns="a11oy")

    # 1) structural counts MEASURED + honest.
    assert gmap["label"] == LBL_MEASURED
    m = gmap["metrics"]
    assert m["node_count"] == 5
    assert m["island_count"] == 2 and m["isolated_count"] == 1  # khipu(1) + islet(0)
    assert abs(m["island_share"] - 0.4) < 1e-9
    # every community here is <= 3 nodes => all thin.
    assert m["community_count"] == 3 and m["thin_community_count"] == 3
    # weak-label share: only "islet" is UNAVAILABLE, nothing UNLABELLED => 1/5.
    assert m["weak_label_count"] == 1 and abs(m["weak_label_share"] - 0.2) < 1e-9
    print(f"[1] map MEASURED — node_count=5, islands={m['island_count']} "
          f"(isolated={m['isolated_count']}), thin_communities={m['thin_community_count']}, "
          f"weak_label_share={m['weak_label_share']}  OK")

    # 2) estate verdict SPARSE (never softened): thin-community share 3/3 = 1.0 >= 0.50.
    assert gmap["estate_verdict"] == SPARSE, gmap["estate_verdict"]
    print(f"[2] estate_verdict={gmap['estate_verdict']} (thin-community share crossed "
          f"the material threshold; never softened to WELL-COVERED)  OK")

    # 3) per-topic COVERED vs GAP vs THIN — coverage never fabricated.
    covered = analyze(nodes=fixture_nodes, link_count=6, community_of=community_of,
                      community_algo="fixture-cc", content_hash="deadbeef",
                      ns="a11oy", query="lambda")
    assert covered["topic"]["verdict"] == COVERED, covered["topic"]
    assert covered["topic"]["label"] == LBL_MODELED
    gap = analyze(nodes=fixture_nodes, link_count=6, community_of=community_of,
                  community_algo="fixture-cc", content_hash="deadbeef",
                  ns="a11oy", query="quantum")
    # "quantum" appears in NO node — an honest GAP, never fabricated into coverage.
    assert gap["topic"]["verdict"] == GAP and gap["topic"]["match_count"] == 0
    thin = analyze(nodes=fixture_nodes, link_count=6, community_of=community_of,
                   community_algo="fixture-cc", content_hash="deadbeef",
                   ns="a11oy", query="khipu")
    # "khipu" matches ONE dangling (degree 1) node => THIN (fragile grounding), not COVERED.
    assert thin["topic"]["verdict"] == THIN, thin["topic"]
    print(f"[3] topic verdicts: lambda={covered['topic']['verdict']}, "
          f"quantum={gap['topic']['verdict']}, khipu={thin['topic']['verdict']} "
          f"(GAP never fabricated into coverage)  OK")

    # 4) RECEIPT-ON-WRITE: receipt handler mints an unsigned sha256; gaps GET mints none.
    r = _content_receipt(covered)
    assert r["algorithm"] == "sha256" and len(r["content_sha256"]) == 64
    assert r["signed"] is False and r["mode"] == "UNSIGNED-CONTENT-DIGEST"
    g = handle_gaps("a11oy", "lambda")  # live read (may be UNAVAILABLE off-box) — mints nothing
    assert "receipt" not in g, "GET gaps must NOT mint a receipt (receipt-on-write)"
    # deterministic digest: same content => same hash.
    assert _content_receipt(covered)["content_sha256"] == r["content_sha256"]
    print(f"[4] POST digest={r['content_sha256'][:16]}… unsigned + deterministic; "
          f"GET gaps mints nothing  OK")

    # 5) doctrine: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 not 100%.
    d = _doctrine_block()
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
