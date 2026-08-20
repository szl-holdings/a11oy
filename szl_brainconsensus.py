#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainconsensus.py — BRAIN CONSENSUS: honest corroboration of a brain grounding.

The brain (szl_brain_api.py) turns the honest estate graph into a queryable retriever:
GET /brain/ask returns a REAL grounding subgraph — the supporting nodes (each with its
community / degree / salience / node_label + links) that back a query. This surface answers
a distinct, complementary question. NOT "how grounded is this answer" (that is the province
of a grounding-confidence surface) and NOT "how uncertain is the retrieval" (that is the
province of an uncertainty surface) — but "how MANY INDEPENDENT nodes support this claim, and
how broadly do they AGREE?" A claim backed by many nodes spanning several distinct graph
communities is well-CORROBORATED; a claim that collapses onto a single node, or a single
clique, is SINGLE-SOURCE and must be flagged as such.

WHAT IT COMPUTES, deterministically, from one query's grounding (no training, no model):
  (a) DISTINCT SUPPORTING NODES — the number of distinct nodes in the REAL grounding subgraph
      that back the query. One node is not corroboration; it is a single source.
  (b) DISTINCT COMMUNITIES SPANNED — how many distinct graph communities those nodes belong
      to. Cross-community agreement is STRONGER evidence than agreement inside one clique:
      several nodes that all sit in one community may simply be restating one another.
  (c) SUPPORT CONCENTRATION — the Herfindahl concentration of the support mass across the
      communities present (∈ (0,1]; 1.0 = all mass in one community). Its inverse-Simpson
      reciprocal is the EFFECTIVE number of communities actually carrying weight, so a lone
      dominant community with a scatter of tiny others is not mistaken for broad agreement.

From these come honest corroboration measures and a SINGLE-SOURCE-RISK flag that fires when
support collapses to one node OR one community (or one community carries almost all the mass).
The verdict is:
      CORROBORATED         — several distinct nodes spanning several distinct communities
      WEAK-CORROBORATION   — multiple nodes but effectively one source / one community
      SINGLE-SOURCE        — support is a single node (nothing to corroborate)
NEVER CORROBORATED when the single-source-risk flag is set — a claim resting on one node or
one clique can never be reported as well-corroborated, whatever the node count happens to be.

HONEST LABEL: MODELED. This is CORROBORATION HONESTY, not a truth guarantee: the number is a
deterministic, explainable measure of how BROADLY the grounding is distributed across the
honest graph — it is NOT a claim that a well-corroborated claim is therefore TRUE (many nodes
can still share one upstream error). Λ = Conjecture 1 (advisory, gray, never a theorem); this
surface adds NOTHING to the locked-8 and proves nothing.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info / consensus reads mint NOTHING. Only
the POST receipt endpoint emits an UNSIGNED SHA-256 content digest over the measurement
(mirroring the govern/receipts content-digest pattern) — a plain content hash, never a
fabricated signature, never a receipt on a GET.

DOCTRINE v11:
  - Pure stdlib (+numpy permitted); reuses szl_brain_api's honest grounding, harvests nothing,
    invents no nodes, restates no counts.
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; touches no locked formula and
    no kernel. Λ stays Conjecture 1; introduces no theorem, no green/1.0.
  - Trust ceiling 0.97, never 100%. No honest label is ever upgraded.
"""

import datetime
import hashlib
import json
from typing import Any

# Honest Doctrine v11 labels (verbatim — never upgraded).
MODELED = "MODELED"
UNAVAILABLE = "UNAVAILABLE"

# Verdicts.
CORROBORATED = "CORROBORATED"
WEAK_CORROBORATION = "WEAK-CORROBORATION"
SINGLE_SOURCE = "SINGLE-SOURCE"

# Corroboration thresholds (advisory; a claim below these is not well-corroborated).
MIN_CORROBORATED_NODES = 3          # fewer distinct supporting nodes => not corroboration
MIN_CORROBORATED_COMMUNITIES = 2    # cross-community agreement requires >= 2 communities
MIN_EFFECTIVE_COMMUNITIES = 1.5     # a lone dominant community + scatter is not broad agreement
# Support mass concentrated at/above this in ONE community => single-source risk.
SINGLE_SOURCE_CONCENTRATION = 0.85

# Corroboration score combine weights: cross-community breadth is weighted HIGHER than raw
# node count — several nodes in one clique may be restating one another, so community spread is
# the stronger corroboration signal. Sum == 1.0.
W_NODE_BREADTH = 0.40
W_COMMUNITY_BREADTH = 0.60

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

SURFACE_ID = "brainconsensus"

_DEFAULT_K = 12
_UNCLUSTERED = "__unclustered__"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _clamp01(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))


def _round(x: float, n: int = 6) -> float:
    return round(float(x), n)


# --------------------------------------------------------------------------- #
# Retrieval — read the SAME honest grounding subgraph szl_brain_api already serves.
# Fully guarded: if the brain API is unavailable the surface degrades honestly.
# --------------------------------------------------------------------------- #
def _support_weight(n: dict) -> float:
    """Non-negative support weight for a grounding node: PPR mass if present, else salience,
    else a uniform 1.0. Never negative; never fabricated."""
    for key in ("ppr", "salience"):
        w = n.get(key)
        if isinstance(w, (int, float)) and w == w and w > 0:
            return float(w)
    return 1.0


def _retrieve(idx: Any, q: str, k: int) -> list[dict]:
    """Return the REAL grounding-subgraph support nodes as
    [{id, community, weight, node_label, title}] for one query at k.
    Reuses szl_brain_api.BrainIndex.ask — invents nothing, restates no counts."""
    k = max(1, int(k))
    res = idx.ask(q, k)
    sub = (res or {}).get("grounding_subgraph", {}) or {}
    nodes = sub.get("nodes", []) or []
    out = []
    seen = set()
    for n in nodes:
        nid = n.get("id")
        if nid is None or nid in seen:
            continue  # distinct nodes only — never double-count one source
        seen.add(nid)
        cid = n.get("community")
        out.append({
            "id": nid,
            "community": str(cid) if cid is not None else _UNCLUSTERED,
            "weight": _support_weight(n),
            "node_label": n.get("node_label"),
            "title": n.get("title", nid),
        })
    return out


# --------------------------------------------------------------------------- #
# Corroboration measures — distinct nodes, distinct communities, concentration.
# --------------------------------------------------------------------------- #
def _measure(support: list[dict]) -> dict:
    """Deterministic corroboration measures over the distinct support nodes."""
    n_nodes = len(support)
    if n_nodes == 0:
        return {
            "distinct_support_nodes": 0,
            "distinct_communities": 0,
            "effective_support_nodes": 0.0,
            "effective_communities": 0.0,
            "community_concentration": None,
            "node_breadth": 0.0,
            "community_breadth": 0.0,
            "corroboration": 0.0,
            "community_mass": {},
            "reason": "no supporting nodes in the grounding subgraph",
        }

    # Distinct communities the support spans.
    community_mass: dict[str, float] = {}
    total_w = 0.0
    for s in support:
        w = max(0.0, float(s.get("weight", 0.0)))
        community_mass[s["community"]] = community_mass.get(s["community"], 0.0) + w
        total_w += w
    n_comms = len(community_mass)

    # If every weight was zero, fall back to a uniform count distribution (never fabricated).
    if total_w <= 0:
        community_mass = {c: 1.0 for c in community_mass}
        total_w = float(n_comms)
        node_weights = [1.0 / n_nodes] * n_nodes
    else:
        node_weights = [max(0.0, float(s.get("weight", 0.0))) / total_w for s in support]

    # Effective number of distinct supporting nodes (inverse Simpson over node weights).
    node_hhi = sum(w * w for w in node_weights) or 1.0
    eff_nodes = 1.0 / node_hhi

    # Community concentration (Herfindahl) and its inverse-Simpson effective community count.
    comm_shares = [m / total_w for m in community_mass.values()]
    comm_hhi = sum(p * p for p in comm_shares) or 1.0
    eff_comms = 1.0 / comm_hhi

    # Breadth components in [0,1]: 1 node / 1 community => 0 (no breadth).
    node_breadth = _clamp01(1.0 - 1.0 / eff_nodes)
    community_breadth = _clamp01(1.0 - comm_hhi)
    corroboration = _clamp01(W_NODE_BREADTH * node_breadth
                             + W_COMMUNITY_BREADTH * community_breadth)

    return {
        "distinct_support_nodes": n_nodes,
        "distinct_communities": n_comms,
        "effective_support_nodes": _round(eff_nodes, 4),
        "effective_communities": _round(eff_comms, 4),
        "community_concentration": _round(comm_hhi, 4),
        "node_breadth": _round(node_breadth, 4),
        "community_breadth": _round(community_breadth, 4),
        "corroboration": _round(corroboration, 6),
        "community_mass": {c: _round(m / total_w, 4)
                           for c, m in sorted(community_mass.items())},
        "note": ("distinct nodes across distinct communities; cross-community agreement is "
                 "weighted higher than raw node count (nodes in one clique may restate one "
                 "another)."),
    }


# --------------------------------------------------------------------------- #
# Verdict — NEVER CORROBORATED when the single-source-risk flag is set.
# --------------------------------------------------------------------------- #
def _verdict(m: dict) -> tuple[str, bool, str]:
    """Return (verdict, single_source_risk, reason)."""
    n_nodes = m["distinct_support_nodes"]
    n_comms = m["distinct_communities"]
    conc = m.get("community_concentration")
    eff_comms = m.get("effective_communities") or 0.0

    if n_nodes == 0:
        return (SINGLE_SOURCE, True,
                "no supporting nodes retrieved — nothing to corroborate")

    # Single-source risk: one node, or one community, or one community carrying ~all the mass.
    single_source_risk = (
        n_nodes <= 1
        or n_comms <= 1
        or (conc is not None and conc >= SINGLE_SOURCE_CONCENTRATION)
    )

    if n_nodes <= 1:
        return (SINGLE_SOURCE, True,
                "support collapses to a single node — this is a single source, not corroboration")

    corroborated = (
        n_nodes >= MIN_CORROBORATED_NODES
        and n_comms >= MIN_CORROBORATED_COMMUNITIES
        and eff_comms >= MIN_EFFECTIVE_COMMUNITIES
        and not single_source_risk
    )
    if corroborated:
        return (CORROBORATED, False,
                f"{n_nodes} distinct nodes spanning {n_comms} distinct communities "
                f"(effective {m['effective_communities']}) — broadly corroborated")

    # Honesty override: whatever the counts, a single-source-risk grounding is never
    # CORROBORATED. It reports as WEAK-CORROBORATION with an explicit reason.
    if single_source_risk:
        why = ("all support in one community" if n_comms <= 1
               else "one community carries almost all the support mass")
        return (WEAK_CORROBORATION, True,
                f"multiple nodes but {why} — treat as a single source, corroborate more widely")
    return (WEAK_CORROBORATION, False,
            f"{n_nodes} nodes across {n_comms} communities but below the corroboration "
            f"threshold — tentative, corroborate more widely")


# --------------------------------------------------------------------------- #
# Assessment — the honest MODELED payload over one query's grounding.
# --------------------------------------------------------------------------- #
def assess(idx: Any, q: str, k: int = _DEFAULT_K) -> dict:
    k = max(1, min(int(k), 100))
    support = _retrieve(idx, q, k)
    m = _measure(support)
    verdict, single_source_risk, reason = _verdict(m)

    return {
        "ok": True,
        "endpoint": "brain/consensus",
        "service": "a11oy.brain.consensus",
        "label": MODELED,
        "surface_id": SURFACE_ID,
        "query": q,
        "k": k,
        "support_nodes_retrieved": m["distinct_support_nodes"],
        "verdict": verdict,
        "single_source_risk": single_source_risk,
        "verdict_reason": reason,
        "corroboration": m["corroboration"],
        "measures": {
            "distinct_support_nodes": m["distinct_support_nodes"],
            "distinct_communities": m["distinct_communities"],
            "effective_support_nodes": m["effective_support_nodes"],
            "effective_communities": m["effective_communities"],
            "community_concentration": m["community_concentration"],
            "node_breadth": m["node_breadth"],
            "community_breadth": m["community_breadth"],
            "community_mass": m["community_mass"],
        },
        "formula": ("corroboration = 0.40·node_breadth + 0.60·community_breadth; "
                    "node_breadth = 1 − 1/effective_nodes, community_breadth = 1 − "
                    "community_HHI; CORROBORATED requires >= 3 distinct nodes across >= 2 "
                    "distinct communities (effective >= 1.5); NEVER CORROBORATED when the "
                    "single-source-risk flag is set"),
        "thresholds": {
            "min_corroborated_nodes": MIN_CORROBORATED_NODES,
            "min_corroborated_communities": MIN_CORROBORATED_COMMUNITIES,
            "min_effective_communities": MIN_EFFECTIVE_COMMUNITIES,
            "single_source_concentration": SINGLE_SOURCE_CONCENTRATION,
        },
        "support": [{"id": s["id"], "title": s["title"], "community": s["community"],
                     "node_label": s["node_label"], "weight": _round(s["weight"], 6)}
                    for s in support[:12]],
        "corroboration_honesty": (
            "CORROBORATION HONESTY, NOT A TRUTH GUARANTEE: this measures how BROADLY the "
            "grounding is distributed across distinct nodes and communities of the honest "
            "graph. It is NOT a claim that a well-corroborated claim is TRUE — many nodes can "
            "share one upstream error. Λ = Conjecture 1 (advisory)."),
        "doctrine": _doctrine_block(),
        "honesty_invariants": _honesty_invariants(),
        "timestamp_utc": _now_iso(),
    }


def _doctrine_block() -> dict:
    return {
        "label_top": MODELED,
        "locked_proven": LOCKED_COUNT,
        "locked_set": LOCKED_SET,
        "kernel_commit": KERNEL_COMMIT,
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1 (advisory, gray; never a theorem, never green)",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
        "note": ("corroboration surface over the honest brain grounding; reuses szl_brain_api, "
                 "harvests nothing, adds nothing to the locked-8; GET reads sign/mint nothing; "
                 "POST receipt emits an UNSIGNED SHA-256 content digest only."),
    }


def _honesty_invariants() -> dict:
    return {
        "corroboration_in_unit_interval": True,
        "distinct_nodes_and_communities_reported": True,
        "never_corroborated_when_single_source_risk": True,
        "single_source_flag_when_support_is_one_node_or_community": True,
        "corroboration_not_a_truth_guarantee": True,
        "receipt_on_write_not_on_read": True,
        "lambda_is_conjecture_1_not_a_theorem": True,
        "adds_nothing_to_locked_8": True,
        "no_consciousness_claim": True,
        "label_never_upgraded": True,
    }


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), never on a GET.
# --------------------------------------------------------------------------- #
def _canonical_core(assessment: dict) -> str:
    """Deterministic canonical serialization of the integrity-bearing content (excludes the
    volatile timestamp), so the digest attests the verdict + measures, not the clock."""
    meas = assessment.get("measures", {})
    core = {
        "query": assessment.get("query"),
        "k": assessment.get("k"),
        "support_nodes_retrieved": assessment.get("support_nodes_retrieved"),
        "verdict": assessment.get("verdict"),
        "single_source_risk": assessment.get("single_source_risk"),
        "corroboration": assessment.get("corroboration"),
        "measures": {name: meas.get(name) for name in
                     ("distinct_support_nodes", "distinct_communities",
                      "effective_support_nodes", "effective_communities",
                      "community_concentration")},
        "label": assessment.get("label"),
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def _content_receipt(assessment: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the assessment (no signature fabricated)."""
    canonical = _canonical_core(assessment)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainconsensus.measurement",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST receipt)",
        "note": ("unsigned SHA-256 content digest of the corroboration measurement; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #
def _get_index(ns: str):
    import szl_brain_api
    return szl_brain_api.get_index(ns)


def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/consensus/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/consensus"
    return {
        "ok": True,
        "endpoint": "brain/consensus/info",
        "service": "a11oy.brain.consensus",
        "surface_id": SURFACE_ID,
        "label": MODELED,
        "title": "Brain Consensus — honest corroboration of a brain grounding",
        "what": ("measures how MANY distinct nodes support a query's grounding and how BROADLY "
                 "they agree, over the SAME honest grounding subgraph szl_brain_api serves — "
                 "distinct supporting nodes, distinct communities spanned, and support "
                 "concentration — into a CORROBORATED / WEAK-CORROBORATION / SINGLE-SOURCE "
                 "verdict. Distinguishes a well-corroborated claim from a single-source one."),
        "measures": {
            "distinct_support_nodes": ("count of distinct nodes in the REAL grounding subgraph "
                                       "that back the query; one node is a single source"),
            "distinct_communities": ("count of distinct graph communities those nodes span; "
                                      "cross-community agreement is stronger than one clique"),
            "support_concentration": ("Herfindahl concentration of the support mass across the "
                                      "communities present; near 1.0 => one community => "
                                      "single-source risk"),
        },
        "formula": ("corroboration = 0.40·node_breadth + 0.60·community_breadth; "
                    "CORROBORATED requires >= 3 distinct nodes across >= 2 distinct communities "
                    "(effective >= 1.5); NEVER CORROBORATED when the single-source-risk flag "
                    "is set"),
        "verdicts": {
            CORROBORATED: "several distinct nodes spanning several distinct communities",
            WEAK_CORROBORATION: "multiple nodes but effectively one source / one community",
            SINGLE_SOURCE: "support is a single node — nothing to corroborate",
        },
        "thresholds": {
            "min_corroborated_nodes": MIN_CORROBORATED_NODES,
            "min_corroborated_communities": MIN_CORROBORATED_COMMUNITIES,
            "min_effective_communities": MIN_EFFECTIVE_COMMUNITIES,
            "single_source_concentration": SINGLE_SOURCE_CONCENTRATION,
        },
        "endpoints": {
            "info": f"GET  {base}/info",
            "consensus": f"GET  {base}?q=&k=",
            "receipt": f"POST {base}/receipt",
        },
        "honest_labels": [MODELED, UNAVAILABLE],
        "corroboration_honesty": (
            "CORROBORATION HONESTY, NOT A TRUTH GUARANTEE — it measures breadth of support "
            "across the honest graph, not P(claim true). Λ = Conjecture 1 (advisory)."),
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — only POST /receipt emits an unsigned "
                           "SHA-256 content digest; GET reads mint nothing."),
        "doctrine": _doctrine_block(),
        "honesty_invariants": _honesty_invariants(),
        "timestamp_utc": _now_iso(),
    }


def handle_consensus(ns: str, q: str, k: int = _DEFAULT_K) -> dict:
    """GET /brain/consensus?q=&k= — the corroboration measurement. PURE READ (mints nothing)."""
    try:
        idx = _get_index(ns)
    except Exception as exc:  # never 500 — honest degraded response
        return {
            "ok": False, "endpoint": "brain/consensus", "label": UNAVAILABLE,
            "surface_id": SURFACE_ID, "query": q, "error": str(exc)[:200],
            "doctrine": "v11: brain index unavailable; no fabricated corroboration emitted.",
            "timestamp_utc": _now_iso(),
        }
    try:
        return assess(idx, q, k)
    except Exception as exc:
        return {
            "ok": False, "endpoint": "brain/consensus", "label": UNAVAILABLE,
            "surface_id": SURFACE_ID, "query": q, "error": str(exc)[:200],
            "doctrine": "v11: measurement unavailable; no fabricated corroboration emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_receipt(ns: str, q: str, k: int = _DEFAULT_K) -> dict:
    """POST /brain/consensus/receipt — the measurement + an UNSIGNED SHA-256 content-digest
    receipt (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    assessment = handle_consensus(ns, q, k)
    if not assessment.get("ok"):
        assessment.setdefault("label", UNAVAILABLE)
        assessment["receipt"] = None
        assessment["note"] = "measurement unavailable; no receipt minted over a non-result."
        return assessment
    out = dict(assessment)
    out["receipt"] = _content_receipt(assessment)
    return out


def _parse_k(raw: Any, default: int = _DEFAULT_K) -> int:
    try:
        return max(1, min(int(raw), 100))
    except Exception:
        return default


# --------------------------------------------------------------------------- #
# FastAPI registration.
#   GET  info / consensus — normal FastAPI GET handlers.
#   POST receipt          — raw-Request handler via app.router.add_route (Starlette passes the
#                           Request positionally, version-proof under fastapi==0.137.x), with
#                           app.add_api_route as the fallback. Annotated request: fastapi.Request.
#                           Registered BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/consensus"

    @app.get(f"{base}/info")
    def _brainconsensus_info():
        """Self-describing corroboration manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainconsensus_get(q: str = "", k: int = _DEFAULT_K):
        """Corroboration measurement over one query's grounding (pure read; mints nothing)."""
        return JSONResponse(handle_consensus(ns, q, k))

    async def _brainconsensus_receipt(request):
        """POST: measurement + UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE). q/k are read
        from the query string, falling back to the JSON body."""
        q = ""
        k = _DEFAULT_K
        try:
            q = request.query_params.get("q", "") or ""
            if request.query_params.get("k") is not None:
                k = _parse_k(request.query_params.get("k"))
        except Exception:
            pass
        if not q:
            try:
                body = await request.json()
                if isinstance(body, dict):
                    q = str(body.get("q", "") or "")
                    if body.get("k") is not None:
                        k = _parse_k(body.get("k"))
            except Exception:
                pass
        return JSONResponse(handle_receipt(ns, q, k))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature analysis (in
    # the add_api_route fallback path) treats the param as the request object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _brainconsensus_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rcpt_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rcpt_path, _brainconsensus_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rcpt_path, _brainconsensus_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rcpt_path, _brainconsensus_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainconsensus receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainconsensus-wired:2(get-only)"

    return "brainconsensus-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — honest measures, [0,1], corroborated vs single-source verdicts, receipt on write.
# Adversarial / negative strings are labeled: Λ is Conjecture 1, never a theorem, never green —
# they exist only to prove the checks still catch a real drift.
# --------------------------------------------------------------------------- #
class _FakeIndex:
    """A tiny deterministic stand-in so the self-test does not depend on the live graph. Its
    ask(q, k) returns a grounding subgraph keyed by a substring of the query."""

    def __init__(self, grounding_by_key):
        self._g = grounding_by_key

    def ask(self, q, k):
        if "single" in q:
            key = "single"
        elif "weak" in q:
            key = "weak"
        else:
            key = "corroborated"
        nodes = [dict(n) for n in self._g.get(key, [])[:max(1, int(k))]]
        return {"grounding_subgraph": {"nodes": nodes, "node_count": len(nodes)}}


def _demo_index() -> "_FakeIndex":
    corroborated = [
        {"id": "n0", "title": "n0", "community": "c0", "ppr": 0.30, "node_label": MODELED},
        {"id": "n1", "title": "n1", "community": "c1", "ppr": 0.25, "node_label": MODELED},
        {"id": "n2", "title": "n2", "community": "c2", "ppr": 0.20, "node_label": MODELED},
        {"id": "n3", "title": "n3", "community": "c0", "ppr": 0.15, "node_label": MODELED},
        {"id": "n4", "title": "n4", "community": "c1", "ppr": 0.10, "node_label": MODELED},
    ]
    weak = [
        {"id": "w0", "title": "w0", "community": "c0", "ppr": 0.40, "node_label": MODELED},
        {"id": "w1", "title": "w1", "community": "c0", "ppr": 0.35, "node_label": MODELED},
        {"id": "w2", "title": "w2", "community": "c0", "ppr": 0.25, "node_label": MODELED},
    ]
    single = [
        {"id": "u0", "title": "u0", "community": "c0", "ppr": 0.80, "node_label": MODELED},
    ]
    return _FakeIndex({"corroborated": corroborated, "weak": weak, "single": single})


if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainconsensus — self-test (honest corroboration of a brain grounding)")
    print("=" * 72)

    idx = _demo_index()
    a_corr = assess(idx, "corroborated query", k=12)
    a_weak = assess(idx, "weak query", k=12)
    a_single = assess(idx, "single query", k=12)

    # 1) corroboration in [0,1]; distinct nodes + communities reported.
    for a in (a_corr, a_weak, a_single):
        assert 0.0 <= a["corroboration"] <= 1.0, a["corroboration"]
        m = a["measures"]
        assert m["distinct_support_nodes"] >= 1
        assert m["distinct_communities"] >= 1
    print(f"[1] corroboration in [0,1], distinct nodes/communities reported  OK "
          f"(corr={a_corr['corroboration']}, weak={a_weak['corroboration']}, "
          f"single={a_single['corroboration']})")

    # 2) multi-community support => CORROBORATED; one node => SINGLE-SOURCE + risk flag.
    assert a_corr["verdict"] == CORROBORATED, a_corr["verdict"]
    assert a_corr["measures"]["distinct_communities"] >= 2
    assert a_single["verdict"] == SINGLE_SOURCE, a_single["verdict"]
    assert a_single["single_source_risk"] is True
    print("[2] multi-community=CORROBORATED, one-node=SINGLE-SOURCE(risk)  OK")

    # 3) never CORROBORATED from one source: the one-community 'weak' case is flagged and is
    #    NEVER reported CORROBORATED, whatever the node count. (Λ = Conjecture 1, never green.)
    assert a_weak["single_source_risk"] is True
    assert a_weak["verdict"] != CORROBORATED
    print("[3] never CORROBORATED while single-source-risk set  OK")

    # 4) RECEIPT-ON-WRITE: the digest is an unsigned sha256; GET measurement mints none.
    rec = _content_receipt(a_corr)
    assert rec["algorithm"] == "sha256" and len(rec["content_sha256"]) == 64
    assert rec["signed"] is False and rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert "receipt" not in a_corr, "GET measurement must NOT carry a receipt"
    assert _content_receipt(a_corr)["content_sha256"] == rec["content_sha256"]
    print(f"[4] POST digest={rec['content_sha256'][:16]}… unsigned; GET mints nothing  OK")

    # 5) doctrine: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 not 100%, MODELED.
    d = a_corr["doctrine"]
    assert a_corr["label"] == MODELED
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"].startswith("Conjecture 1") and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[5] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    print("\nok:true checks:5")
    _sys.exit(0)
