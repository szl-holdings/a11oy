# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainlineage.py — NODE-ORIGIN LINEAGE over the honest brain graph.

This surface answers ONE honest question about a knowledge-graph node: HOW did
this node ENTER the graph — what is its harvest/origin metadata chain? It reads
ONLY the real fields the brain builder (a11oy_brain_graph) actually attached to
each node and reconstructs an ordered ORIGIN CHAIN from them. When a node carries
NO origin/source field, it reports origin = UNKNOWN — it NEVER fabricates a source.

This is KNOWLEDGE-GRAPH PROVENANCE-OF-NODE-ORIGIN (where did this fact come from),
and is DISTINCT from szl_brainprovenance (which nodes supported an ANSWER). It is
STRICTLY knowledge-graph honesty. It is explicitly NOT:
  * cryptographic attestation of a model, weapon, or artifact,
  * SLSA / in-toto / Rekor BUILD provenance of an image or binary,
  * any counter-UAS / targeting / fusion / effector capability.

WHAT IT READS (the REAL origin fields, per node, VERBATIM — never invented):
  STRONG (explicit cited source)  : source, url
  STRUCTURAL (derivation/harvest) : derived_from, axis, src_layer, ring, org,
                                     domain, path, organ, formula_id, asset
  WEAK (classification only)      : node_label / label, community, kind, layer
A node's origin is TRACED only from a STRONG field; a STRUCTURAL field yields a
partial, structural-only chain; WEAK signals alone are not an origin.

VERDICT (per node, and aggregated over a query's top nodes):
  TRACED           — an explicit cited source (source and/or url) is present;
                     the origin chain traces to a real, named source.
  PARTIAL-LINEAGE  — no explicit source, but a structural/derivation origin is
                     inferable (derived_from / harvest axis / organ / org / …).
  UNKNOWN-ORIGIN   — no origin/source field at all; origin = UNKNOWN. NEVER a
                     fabricated source.

LABEL (this surface's honest read of the origin, per node):
  MODELED          — an explicit source exists; the chain is modeled from real
                     source/url fields.
  STRUCTURAL-ONLY  — only a structural (no explicit source) origin is inferable,
                     or the origin is UNKNOWN.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info/lineage reads mint NOTHING.
Only POST .../receipt emits an UNSIGNED SHA-256 content digest over the origin
chain(s) (mirrors the brainprovenance content-digest pattern) — a plain content
hash, never a fabricated signature, never a receipt on a GET.

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only re-reads
    the brain's OWN node fields. Touches no locked formula and no kernel.
  * Λ stays Conjecture 1 (never a theorem); Khipu BFT stays Conjecture 2. Trust
    ceiling 0.97, never 100%. No label is ever upgraded; UNKNOWN is never hidden.
  * Pure stdlib + numpy (numpy import is guarded; a pure-python path is used when
    it is absent). Additive routes, registered before the SPA catch-all. 0 runtime
    CDN.
"""

import datetime
import hashlib
import json

try:  # numpy is allowed; keep it optional so a missing wheel degrades honestly.
    import numpy as _np
    _HAVE_NUMPY = True
except Exception:  # pragma: no cover - numpy is a core dep, but stay honest
    _np = None
    _HAVE_NUMPY = False

# Honest Doctrine v11 labels (verbatim — never upgraded).
MODELED = "MODELED"                # explicit source => origin chain modeled from real fields
STRUCTURAL_ONLY = "STRUCTURAL-ONLY"  # only structural/no-explicit-source origin inferable
LBL_UNAVAILABLE = "UNAVAILABLE"

# Verdicts.
TRACED = "TRACED"
PARTIAL = "PARTIAL-LINEAGE"
UNKNOWN = "UNKNOWN-ORIGIN"

# Origin-field taxonomy — the REAL fields a11oy_brain_graph attaches to nodes.
# Read VERBATIM; membership here classifies a field, it never fabricates one.
STRONG_FIELDS = ("source", "url")                       # explicit cited origin
STRUCTURAL_FIELDS = ("derived_from", "axis", "src_layer", "ring",
                     "org", "domain", "path", "organ", "formula_id", "asset")
WEAK_FIELDS = ("node_label", "label", "community", "kind", "layer")

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "brainlineage"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _verbatim_label(node: dict) -> str | None:
    """The node's OWN origin-class label VERBATIM (never upgraded). None if absent."""
    v = node.get("node_label")
    if v is None:
        v = node.get("label")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def _clean(value) -> str | None:
    """A present, non-empty scalar rendered as a string; else None (never faked)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        s = value.strip()
        return s or None
    # non-scalar (list/dict) — stringify deterministically, never drop silently
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:  # pragma: no cover
        return str(value)


# --------------------------------------------------------------------------- #
# Origin chain — ordered steps read from the node's REAL fields (verbatim).
# --------------------------------------------------------------------------- #
def build_origin_chain(node: dict) -> list[dict]:
    """Ordered origin steps for a node, each read VERBATIM from a real field.

    Order: strong (cited source) first, then structural/derivation, then the
    weak classification signals. A field absent from the node produces NO step —
    a missing origin is never back-filled with a fabricated one."""
    chain: list[dict] = []

    def _step(field: str, tier: str) -> None:
        val = _clean(node.get(field))
        if val is not None:
            chain.append({"field": field, "value": val, "tier": tier})

    for f in STRONG_FIELDS:
        _step(f, "STRONG")
    for f in STRUCTURAL_FIELDS:
        _step(f, "STRUCTURAL")
    # weak signals: label first (it is the origin CLASS), then community/kind/layer.
    lab = _verbatim_label(node)
    if lab is not None:
        chain.append({"field": "node_label", "value": lab, "tier": "WEAK"})
    for f in ("community", "kind", "layer"):
        val = _clean(node.get(f))
        if val is not None:
            chain.append({"field": f, "value": val, "tier": "WEAK"})
    return chain


def _tier_present(chain: list[dict], tier: str) -> bool:
    return any(s.get("tier") == tier for s in chain)


def classify(chain: list[dict]) -> tuple[str, str, str]:
    """Honest (verdict, label, origin) for ONE node's origin chain.

    NEVER TRACED without a STRONG (explicit source/url) step; a node with only
    WEAK signals is UNKNOWN-ORIGIN with origin=UNKNOWN — never a fabricated source."""
    has_strong = _tier_present(chain, "STRONG")
    has_structural = _tier_present(chain, "STRUCTURAL")
    if has_strong:
        # the origin is the first STRONG value read verbatim (source, then url).
        origin = next(s["value"] for s in chain if s["tier"] == "STRONG")
        return TRACED, MODELED, origin
    if has_structural:
        origin = next(s["value"] for s in chain if s["tier"] == "STRUCTURAL")
        return PARTIAL, STRUCTURAL_ONLY, origin
    # only weak signals (or nothing): the origin is genuinely untracked.
    return UNKNOWN, STRUCTURAL_ONLY, "UNKNOWN"


def lineage_for_node(node: dict) -> dict:
    """The full origin-lineage record for ONE real node. Pure; fabricates nothing."""
    chain = build_origin_chain(node)
    verdict, label, origin = classify(chain)
    strong = [s for s in chain if s["tier"] == "STRONG"]
    structural = [s for s in chain if s["tier"] == "STRUCTURAL"]
    return {
        "id": node.get("id"),
        "title": node.get("title", node.get("id")),
        "kind": node.get("kind"),
        "layer": node.get("layer"),
        "node_label": _verbatim_label(node),   # VERBATIM origin class, may be None
        "community": node.get("community"),
        "origin": origin,                       # UNKNOWN when untracked, never faked
        "verdict": verdict,
        "label": label,
        "origin_chain": chain,
        "origin_field_count": len(chain),
        "explicit_source_fields": [s["field"] for s in strong],
        "structural_fields": [s["field"] for s in structural],
        "has_explicit_source": bool(strong),
    }


# --------------------------------------------------------------------------- #
# Aggregate verdict over a query's top nodes (never TRACED while any UNKNOWN).
# --------------------------------------------------------------------------- #
def _fraction(part: int, total: int) -> float:
    if not total:
        return 0.0
    if _HAVE_NUMPY:
        return round(float(_np.divide(part, total)), 8)
    return round(part / total, 8)


def aggregate(records: list[dict]) -> dict:
    """Honest roll-up over per-node lineage records.

    TRACED only if every node is TRACED; UNKNOWN-ORIGIN only if every node is
    UNKNOWN-ORIGIN (or there are no nodes); PARTIAL-LINEAGE otherwise. The verdict
    is NEVER TRACED while any node's origin is UNKNOWN."""
    total = len(records)
    traced = sum(1 for r in records if r["verdict"] == TRACED)
    partial = sum(1 for r in records if r["verdict"] == PARTIAL)
    unknown = sum(1 for r in records if r["verdict"] == UNKNOWN)
    if total == 0:
        verdict, reason = UNKNOWN, "no nodes matched; nothing to trace, no origin fabricated."
    elif traced == total:
        verdict = TRACED
        reason = f"all {total} node(s) carry an explicit cited source; origin fully traced."
    elif unknown == total:
        verdict = UNKNOWN
        reason = f"all {total} node(s) have no origin/source field; origin UNKNOWN (never fabricated)."
    else:
        verdict = PARTIAL
        reason = (f"{traced}/{total} traced to an explicit source, {partial} structural-only, "
                  f"{unknown} UNKNOWN-ORIGIN; never TRACED while any origin is UNKNOWN.")
    return {
        "total_nodes": total,
        "traced": traced,
        "partial_lineage": partial,
        "unknown_origin": unknown,
        "fraction_traced": _fraction(traced, total),
        "fraction_unknown_origin": _fraction(unknown, total),
        "verdict": verdict,
        "verdict_reason": reason,
    }


# --------------------------------------------------------------------------- #
# Brain access — reuse the SAME honest index; invent no node, harvest nothing.
# --------------------------------------------------------------------------- #
def _index(ns: str):
    import szl_brain_api as _brain_api
    return _brain_api.get_index(ns)


def _doctrine_block() -> dict:
    return {
        "label_top": MODELED,
        "locked_proven": LOCKED_COUNT,
        "locked_set": LOCKED_SET,
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
        "note": ("additive NODE-ORIGIN lineage over the brain's own node fields; touches no "
                 "locked formula and no kernel; GET reads sign/mint nothing; POST /receipt "
                 "emits an UNSIGNED SHA-256 content digest only; introduces no theorem; a node "
                 "with no source field reports origin UNKNOWN, never a fabricated source."),
    }


def _lineage_kind() -> str:
    return "NODE-ORIGIN-LINEAGE (knowledge-graph provenance of where a node came from)"


def _not_lineage() -> list:
    return ["per-answer node provenance (that is szl_brainprovenance)",
            "build/SLSA/in-toto/Rekor artifact attestation",
            "cryptographic model/weapon attestation",
            "counter-UAS/targeting/fusion/effector"]


# --------------------------------------------------------------------------- #
# Lineage assembly (pure computation — mints nothing).
# --------------------------------------------------------------------------- #
def build_lineage_by_id(ns: str, node_id: str) -> dict:
    """Origin chain + verdict for ONE node id. Pure read; mints nothing."""
    node_id = (node_id or "").strip()
    base = {
        "label": MODELED,
        "surface_id": SURFACE_ID,
        "endpoint": "brain/lineage",
        "service": "a11oy.brain.lineage",
        "mode": "id",
        "lineage_kind": _lineage_kind(),
        "not_lineage_of": _not_lineage(),
        "doctrine": _doctrine_block(),
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — GET mints nothing; POST /receipt digests.",
        "timestamp_utc": _now_iso(),
    }
    if not node_id:
        return dict(base, ok=False, found=False, id=node_id, verdict=UNKNOWN,
                    verdict_reason="empty id; no lookup performed, no origin fabricated.",
                    lineage=None)
    try:
        idx = _index(ns)
    except Exception as exc:  # never 500 — honest degraded response
        return dict(base, ok=False, found=False, id=node_id, label=LBL_UNAVAILABLE,
                    verdict=UNKNOWN,
                    verdict_reason=f"brain index unavailable; no origin fabricated: {str(exc)[:160]}",
                    lineage=None)
    node = idx.by_id.get(node_id)
    if node is None:
        return dict(base, ok=False, found=False, id=node_id, verdict=UNKNOWN,
                    verdict_reason=f"unknown node id {node_id!r}; origin UNKNOWN, never fabricated.",
                    lineage=None)
    rec = lineage_for_node(dict(node, community=idx.community_of.get(node_id)))
    return dict(base, ok=True, found=True, id=node_id,
                verdict=rec["verdict"], verdict_reason=(
                    f"origin {rec['verdict']}: "
                    + ("explicit cited source present"
                       if rec["has_explicit_source"]
                       else ("structural origin only"
                             if rec["verdict"] == PARTIAL
                             else "no origin/source field — origin UNKNOWN, never fabricated"))),
                lineage=rec, verdict_legend=_legend())


def build_lineage_by_query(ns: str, q: str, k: int = 10) -> dict:
    """Origin chains + aggregate verdict for a query's top nodes. Pure read."""
    q = (q or "").strip()
    k = max(1, min(int(k) if isinstance(k, (int, float)) else 10, 50))
    base = {
        "label": MODELED,
        "surface_id": SURFACE_ID,
        "endpoint": "brain/lineage",
        "service": "a11oy.brain.lineage",
        "mode": "query",
        "query": q,
        "k": k,
        "lineage_kind": _lineage_kind(),
        "not_lineage_of": _not_lineage(),
        "doctrine": _doctrine_block(),
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — GET mints nothing; POST /receipt digests.",
        "verdict_legend": _legend(),
        "timestamp_utc": _now_iso(),
    }
    if not q:
        agg = aggregate([])
        return dict(base, ok=False, lineages=[], aggregate=agg,
                    verdict=agg["verdict"],
                    verdict_reason="empty query; no retrieval performed, no origin fabricated.")
    try:
        idx = _index(ns)
        seeds = idx.search(q, k=k)
    except Exception as exc:  # never 500 — honest degraded response
        agg = aggregate([])
        return dict(base, ok=False, label=LBL_UNAVAILABLE, lineages=[], aggregate=agg,
                    verdict=agg["verdict"],
                    verdict_reason=f"brain retrieval unavailable; no origin fabricated: {str(exc)[:160]}")
    records = []
    for s in seeds:
        node = idx.by_id.get(s["id"])
        if node is None:
            continue
        rec = lineage_for_node(dict(node, community=idx.community_of.get(s["id"])))
        rec["retrieval_score"] = s.get("score")
        records.append(rec)
    agg = aggregate(records)
    return dict(base, ok=True, matched_nodes=len(records), lineages=records,
                aggregate=agg, verdict=agg["verdict"], verdict_reason=agg["verdict_reason"])


def _legend() -> dict:
    return {
        TRACED: "explicit cited source (source/url) present; origin traced to a real source",
        PARTIAL: "no explicit source, but a structural/derivation origin is inferable",
        UNKNOWN: "no origin/source field; origin UNKNOWN — never a fabricated source",
    }


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), never a GET.
# --------------------------------------------------------------------------- #
def _canonical_core(payload: dict) -> str:
    """Deterministic canonical serialization of the origin content (excludes the
    volatile timestamp), so the digest attests the ORIGIN CHAIN(S) + verdict."""
    def _rec_core(rec: dict) -> dict:
        return {
            "id": rec.get("id"),
            "verdict": rec.get("verdict"),
            "label": rec.get("label"),
            "origin": rec.get("origin"),
            "origin_chain": [{"field": s.get("field"), "value": s.get("value"),
                              "tier": s.get("tier")}
                             for s in (rec.get("origin_chain") or [])],
        }
    if payload.get("mode") == "id":
        lin = payload.get("lineage")
        core = {"mode": "id", "id": payload.get("id"),
                "verdict": payload.get("verdict"),
                "lineage": _rec_core(lin) if lin else None}
    else:
        core = {"mode": "query", "query": payload.get("query"),
                "verdict": payload.get("verdict"),
                "aggregate": payload.get("aggregate"),
                "lineages": [_rec_core(r) for r in (payload.get("lineages") or [])]}
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def content_receipt(payload: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the origin lineage."""
    canonical = _canonical_core(payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainlineage.origin",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST /receipt)",
        "note": ("unsigned SHA-256 content digest of the node-origin lineage; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #
def handle_info(ns: str = "a11oy") -> dict:
    """GET .../lineage/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/lineage"
    return {
        "ok": True,
        "label": MODELED,
        "surface_id": SURFACE_ID,
        "service": "a11oy.brain.lineage",
        "endpoint": "brain/lineage/info",
        "title": "Brain Lineage — how a node entered the knowledge graph",
        "what": ("for a knowledge-graph node (by id, or a query's top nodes) reconstructs the "
                 "ORIGIN CHAIN of how it entered the graph — read ONLY from the REAL fields the "
                 "brain builder attached — and honestly reports origin UNKNOWN when no source "
                 "field exists (never fabricated)."),
        "lineage_kind": _lineage_kind(),
        "distinct_from": ("szl_brainprovenance answers WHICH nodes supported an ANSWER; this "
                          "answers WHERE a node itself came from (its harvest/origin metadata)."),
        "explicitly_not": ("This is NODE-ORIGIN lineage of a knowledge-graph node only. It is NOT "
                           "per-answer provenance, NOT cryptographic model/weapon attestation, NOT "
                           "SLSA/in-toto/Rekor build attestation, and NOT any counter-UAS / "
                           "targeting / fusion / effector capability."),
        "origin_fields_read": {
            "strong_explicit_source": list(STRONG_FIELDS),
            "structural_derivation": list(STRUCTURAL_FIELDS),
            "weak_classification": list(WEAK_FIELDS),
            "note": ("read VERBATIM from each node; TRACED requires a STRONG field; a STRUCTURAL "
                     "field yields PARTIAL-LINEAGE; WEAK signals alone are UNKNOWN-ORIGIN."),
        },
        "endpoints": {
            "info": f"GET  {base}/info",
            "by_id": f"GET  {base}?id=",
            "by_query": f"GET  {base}?q=&k=",
            "receipt": f"POST {base}/receipt  (body: {{\"id\":..}} or {{\"q\":..,\"k\":..}})",
        },
        "verdicts": [TRACED, PARTIAL, UNKNOWN],
        "verdict_legend": _legend(),
        "honest_labels": {
            "labels": [MODELED, STRUCTURAL_ONLY],
            "note": ("MODELED when an explicit source exists; STRUCTURAL-ONLY when only a "
                     "structural (no explicit source) origin is inferable or origin is UNKNOWN. "
                     "Labels are never upgraded; UNKNOWN is never hidden."),
        },
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — only POST /receipt emits an unsigned SHA-256 digest.",
        "doctrine": _doctrine_block(),
        "numpy_available": _HAVE_NUMPY,
        "timestamp_utc": _now_iso(),
    }


def handle_lineage(ns: str, id: str = "", q: str = "", k: int = 10) -> dict:  # noqa: A002
    """GET .../lineage?id= | ?q= — origin chain(s) + verdict. PURE READ (mints nothing).

    id takes precedence when both are supplied; an empty request is honestly UNKNOWN."""
    if (id or "").strip():
        return build_lineage_by_id(ns, id)
    return build_lineage_by_query(ns, q, k)


def handle_receipt(ns: str, id: str = "", q: str = "", k: int = 10) -> dict:  # noqa: A002
    """POST .../lineage/receipt — lineage + an UNSIGNED SHA-256 content digest
    (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    payload = handle_lineage(ns, id=id, q=q, k=k)
    out = dict(payload)
    out["receipt"] = content_receipt(payload)
    return out


# --------------------------------------------------------------------------- #
# FastAPI registration.
#   GET  info/lineage — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST receipt      — raw-Request handler via app.router.add_route (Starlette
#                       passes the Request positionally, version-proof under
#                       fastapi==0.137.x), with app.add_api_route as the fallback.
#                       Registered BEFORE the SPA catch-all by serve.py.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/lineage"

    @app.get(f"{base}/info")
    def _brainlineage_info():
        """Static self-describing manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainlineage_get(id: str = "", q: str = "", k: int = 10):  # noqa: ANN202,A002
        """Origin chain(s) + verdict for a node id or a query (pure read; mints nothing)."""
        payload = handle_lineage(ns, id=id, q=q, k=k)
        if payload.get("mode") == "id" and payload.get("found") is False and (id or "").strip():
            return JSONResponse(payload, status_code=404)
        return JSONResponse(payload)

    async def _brainlineage_receipt(request):
        """POST: origin lineage + UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE)."""
        node_id, q, k = "", "", 10
        try:
            body = await request.json()
            if isinstance(body, dict):
                node_id = str(body.get("id", "") or "")
                q = str(body.get("q", body.get("query", "")) or "")
                kv = body.get("k", 10)
                k = int(kv) if isinstance(kv, (int, float, str)) and str(kv).strip() else 10
        except Exception:  # noqa: BLE001 — a bodyless/garbled POST still gets an honest answer
            node_id, q, k = "", "", 10
        # Query params override / supplement a missing body.
        try:
            qp = request.query_params
            if not node_id and qp.get("id"):
                node_id = str(qp.get("id"))
            if not q and qp.get("q"):
                q = str(qp.get("q"))
            if qp.get("k"):
                k = int(qp.get("k"))
        except Exception:  # noqa: BLE001
            pass
        return JSONResponse(handle_receipt(ns, id=node_id, q=q, k=k))

    # Annotate the raw-Request handler as fastapi.Request so the add_api_route fallback
    # path treats the param as the request object (0.137.x signature-analysis gotcha).
    try:
        import fastapi as _fastapi
        _brainlineage_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rcpt_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rcpt_path, _brainlineage_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rcpt_path, _brainlineage_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rcpt_path, _brainlineage_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainlineage receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainlineage-wired:2(get-only)"

    return "brainlineage-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — origin chain from real fields, UNKNOWN when no source (no
# fabrication), verdict transitions, deterministic receipt on write, labels
# never upgraded.
# --------------------------------------------------------------------------- #
def _selftest() -> None:
    import sys as _sys

    print("=" * 72)
    print("szl_brainlineage — self-test (node-origin lineage)")
    print("=" * 72)

    # 1) A harvested node with an explicit cited source -> TRACED / MODELED.
    #    (Λ is Conjecture 1, never a theorem — no proof claim is made here.)
    harvested = {"id": "field:x", "title": "harvested field node", "kind": "field",
                 "layer": -1, "label": "HARVESTED", "ring": "field",
                 "url": "https://example.org/paper", "source": "brain/harvest/pass2.jsonl",
                 "axis": "A"}
    rec = lineage_for_node(harvested)
    assert rec["verdict"] == TRACED, rec["verdict"]
    assert rec["label"] == MODELED, rec["label"]
    assert rec["origin"] == "brain/harvest/pass2.jsonl", rec["origin"]
    assert rec["has_explicit_source"] is True
    assert rec["origin_chain"][0]["tier"] == "STRONG"
    print(f"[1] harvested node TRACED/MODELED, origin={rec['origin']!r}  OK")

    # 2) A structural node (derived_from only, no explicit source) -> PARTIAL / STRUCTURAL-ONLY.
    topic = {"id": "topic:t", "title": "topic", "kind": "topic", "layer": 1,
             "label": "MODELED", "derived_from": "FORMULA_META.organ"}
    tr = lineage_for_node(topic)
    assert tr["verdict"] == PARTIAL, tr["verdict"]
    assert tr["label"] == STRUCTURAL_ONLY, tr["label"]
    assert tr["origin"] == "FORMULA_META.organ"
    assert tr["has_explicit_source"] is False
    print(f"[2] structural node PARTIAL-LINEAGE/STRUCTURAL-ONLY, origin={tr['origin']!r}  OK")

    # 3) A bare node with only weak signals (label + community) -> UNKNOWN-ORIGIN.
    #    origin MUST be UNKNOWN — a missing source is NEVER fabricated.
    bare = {"id": "bare:1", "title": "bare", "kind": "misc", "layer": 0,
            "label": "MODELED", "community": "c3"}
    br = lineage_for_node(bare)
    assert br["verdict"] == UNKNOWN, br["verdict"]
    assert br["origin"] == "UNKNOWN", br["origin"]
    assert br["label"] == STRUCTURAL_ONLY
    assert br["has_explicit_source"] is False
    print(f"[3] bare node UNKNOWN-ORIGIN, origin={br['origin']!r} (never fabricated)  OK")

    # 4) Aggregate: never TRACED while any node is UNKNOWN-ORIGIN.
    agg = aggregate([rec, tr, br])
    assert agg["verdict"] == PARTIAL, agg["verdict"]
    assert agg["traced"] == 1 and agg["unknown_origin"] == 1
    all_traced = aggregate([rec, dict(rec, id="field:y")])
    assert all_traced["verdict"] == TRACED
    all_unknown = aggregate([br, dict(br, id="bare:2")])
    assert all_unknown["verdict"] == UNKNOWN
    assert aggregate([])["verdict"] == UNKNOWN
    print(f"[4] aggregate downgrades honestly: mixed=PARTIAL, all-traced=TRACED, "
          f"all-unknown/empty=UNKNOWN-ORIGIN  OK")

    # 5) Receipt: UNSIGNED sha256, deterministic, ignores the volatile timestamp.
    p_id = {"mode": "id", "id": "field:x", "verdict": TRACED, "lineage": rec}
    r1 = content_receipt(p_id)
    r2 = content_receipt(dict(p_id, timestamp_utc="2026-01-01T00:00:00Z"))
    assert r1["signed"] is False and len(r1["content_sha256"]) == 64
    assert r1["content_sha256"] == r2["content_sha256"], "digest ignores timestamp"
    print(f"[5] receipt UNSIGNED sha256={r1['content_sha256'][:16]}… deterministic  OK")

    # 6) doctrine block honest: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 not 100%.
    d = _doctrine_block()
    assert d["locked_proven"] == 8 and d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[6] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    print("\nok:true checks:6")
    _sys.exit(0)


if __name__ == "__main__":
    _selftest()
