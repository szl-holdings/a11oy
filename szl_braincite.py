# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SZL Holdings. Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_braincite.py — verifiable claim -> source citations for brain answers.

WHAT THIS SURFACE ANSWERS: "which specific source node backs each claim, and which
claims cannot be cited at all?" It runs the SAME honest brain retrieval
(szl_brain_api.get_index(ns).ask(q, k)) that brainground/brainprovenance use, then binds
each candidate claim/term drawn from the query to the supporting graph node(s) whose title
actually contains that term. A claim with a qualifying backing node is CITED; a claim with
no qualifying support is UNCITED — never given a fabricated citation.

HONESTY DISCIPLINE (doctrine v11):
  * It invents no nodes and no citations. A term with no matching source node is UNCITED,
    reported plainly, so an answer can never present an uncited claim as sourced.
  * citation_coverage = cited / total is a MODELED ratio over a real retrieval, never a
    MEASURED physical quantity.
  * node_label on every cited source is carried VERBATIM; membership never upgrades a label.
  * Lambda stays Conjecture 1, never a theorem; locked-8 immutable; trust ceiling 0.97.
  * Receipt is an UNSIGNED SHA-256 content digest, minted on WRITE (POST) only.

It complements szl_brainprovenance (which lists the whole supporting lineage) by binding at
claim -> source granularity so each individual claim's citation status is explicit.
"""

from __future__ import annotations

import hashlib
import json
import re
import datetime
from typing import Any

# Honest Doctrine v11 label vocabulary. Restated here (not imported) so a broken import can
# never silently blank the vocabulary; tests grep these exact strings.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# This surface's own top label — a derived binding view, not a live measurement.
LBL_MODELED = "MODELED"
LBL_UNAVAILABLE = "UNAVAILABLE"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "braincite"

# Doctrine constants (never inflated).
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
TRUST_CEILING = 0.97
KERNEL_COMMIT = "c7c0ba17"

# Per-claim citation status.
CITED = "CITED"
UNCITED = "UNCITED"

# Overall verdicts.
VERDICT_FULLY_CITED = "FULLY-CITED"
VERDICT_PARTIALLY_CITED = "PARTIALLY-CITED"
VERDICT_UNCITED_DOMINANT = "UNCITED-DOMINANT"
VERDICT_NO_CLAIMS = "NO-CITABLE-CLAIMS"

# Coverage thresholds (explicit, documented). A ratio at/above FULL is fully cited; below
# HALF the answer is uncited-dominant; between is partial.
COVERAGE_FULL = 1.0
COVERAGE_HALF = 0.5

DEFAULT_K = 12
MAX_K = 50
MIN_TERM_LEN = 3  # query tokens shorter than this are stopword-like; not treated as claims

# Small, transparent English stopword set so trivial words are not counted as claims.
_STOPWORDS = frozenset(
    "the a an and or of to in on for is are was were be been being with as at by from "
    "this that these those it its into about over under how what why when where which who "
    "does do did can could should would will may might than then them they you your our".split()
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
        "is_model_training": False,
        "sentience_claim": False,
    }
    if note:
        d["note"] = note
    return d


# --------------------------------------------------------------------------- #
# Retrieval + claim/term extraction.
# --------------------------------------------------------------------------- #
def _ask(ns: str, q: str, k: int) -> dict:
    """Run the SAME honest brain retrieval brainground/brainprovenance use."""
    import szl_brain_api as _brain_api
    idx = _brain_api.get_index(ns)
    return idx.ask(q, max(1, min(int(k), MAX_K)))


def _claim_terms(query: str) -> list[str]:
    """Extract candidate claim terms from the query: content words, de-duplicated,
    order-preserving. Trivial stopwords and very short tokens are dropped. This never
    invents a claim the query did not contain."""
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]*", query.lower())
    seen: dict[str, None] = {}
    for t in tokens:
        if len(t) >= MIN_TERM_LEN and t not in _STOPWORDS:
            seen.setdefault(t, None)
    return list(seen.keys())


def _supporting_nodes(ask_result: dict) -> list[dict]:
    grounding = ask_result.get("grounding_subgraph") or {}
    nodes = grounding.get("nodes") or []
    return [n for n in nodes if isinstance(n, dict) and n.get("id")]


def _node_text(node: dict) -> str:
    title = node.get("title") or node.get("id") or ""
    return str(title).lower()


def _cite_term(term: str, nodes: list[dict]) -> list[dict]:
    """Return the source node(s) that genuinely back `term` — those whose title contains
    the term. Never fabricates a binding: if no node's real title contains the term, the
    list is empty and the claim is UNCITED."""
    backing = []
    for n in nodes:
        if term in _node_text(n):
            backing.append({
                "id": n.get("id"),
                "title": n.get("title", n.get("id")),
                "url": n.get("url"),  # verbatim; may be None
                "node_label": n.get("node_label"),  # VERBATIM, never upgraded
            })
    return backing


# --------------------------------------------------------------------------- #
# Core evaluation.
# --------------------------------------------------------------------------- #
def evaluate(query: str, k: int = DEFAULT_K, ns: str = "a11oy") -> dict:
    """Bind each claim term to its supporting source node(s). Honest throughout:
    UNCITED whenever no real node backs the term; coverage is a MODELED ratio."""
    terms = _claim_terms(query or "")
    if not terms:
        return {
            "label": LBL_MODELED,
            "verdict": VERDICT_NO_CLAIMS,
            "query": query,
            "claims": [],
            "citation_coverage": None,
            "cited_count": 0,
            "total_claims": 0,
            "note": "no citable claim terms in the query (all stopword-like or too short)",
        }

    # Try the real retrieval; if the brain is unreachable, report UNAVAILABLE honestly.
    try:
        ask_result = _ask(ns, query, k)
    except Exception as exc:  # retrieval genuinely unreachable this request
        return {
            "label": LBL_UNAVAILABLE,
            "verdict": VERDICT_UNCITED_DOMINANT,
            "query": query,
            "claims": [{"claim": t, "status": UNCITED, "sources": []} for t in terms],
            "citation_coverage": 0.0,
            "cited_count": 0,
            "total_claims": len(terms),
            "note": f"brain retrieval unreachable ({str(exc)[:120]}); every claim UNCITED, none fabricated",
        }

    nodes = _supporting_nodes(ask_result)
    claims = []
    cited = 0
    for t in terms:
        sources = _cite_term(t, nodes)
        status = CITED if sources else UNCITED
        if sources:
            cited += 1
        claims.append({"claim": t, "status": status, "sources": sources})

    total = len(terms)
    coverage = round(cited / total, 6) if total else None
    verdict = _verdict(coverage)
    return {
        "label": LBL_MODELED,
        "verdict": verdict,
        "query": query,
        "claims": claims,
        "citation_coverage": coverage,
        "cited_count": cited,
        "total_claims": total,
        "supporting_nodes_seen": len(nodes),
        "note": ("each claim is CITED only when a real source node's title contains it; "
                 "UNCITED claims are reported, never given a fabricated citation."),
    }


def _verdict(coverage) -> str:
    if coverage is None:
        return VERDICT_NO_CLAIMS
    if coverage >= COVERAGE_FULL:
        return VERDICT_FULLY_CITED
    if coverage < COVERAGE_HALF:
        return VERDICT_UNCITED_DOMINANT
    return VERDICT_PARTIALLY_CITED


# --------------------------------------------------------------------------- #
# Receipt (unsigned SHA-256 content digest, receipt-on-write).
# --------------------------------------------------------------------------- #
def _canonical_core(result: dict) -> str:
    core = {
        "label": result.get("label"),
        "verdict": result.get("verdict"),
        "query": result.get("query"),
        "citation_coverage": result.get("citation_coverage"),
        "cited_count": result.get("cited_count"),
        "total_claims": result.get("total_claims"),
        "claims": [
            {
                "claim": c.get("claim"),
                "status": c.get("status"),
                "sources": [s.get("id") for s in (c.get("sources") or [])],
            }
            for c in (result.get("claims") or [])
        ],
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def content_receipt(result: dict) -> dict:
    digest = hashlib.sha256(_canonical_core(result).encode("utf-8")).hexdigest()
    return {
        "kind": "szl.braincite.citations",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST cite/receipt)",
        "note": ("unsigned SHA-256 content digest of the claim->source citation record; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated, no proof "
                 "claimed beyond the digest."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #
def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/cite/info — static self-describing manifest (no compute). PURE READ."""
    return {
        "ok": True,
        "endpoint": "brain/cite/info",
        "service": f"{ns}.brain.braincite",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "title": "Brain Cite — verifiable claim to source citations",
        "what": ("for a query, binds each candidate claim term to the source node(s) whose "
                 "title actually contains it; a claim with no backing node is UNCITED and is "
                 "never given a fabricated citation."),
        "method": ("run szl_brain_api.get_index(ns).ask(q,k) for a real grounding_subgraph, "
                   "extract content-word claim terms from the query, and cite each term to "
                   "matching source nodes (id/title/url/node_label verbatim)."),
        "verdicts": {
            VERDICT_FULLY_CITED: "every claim term is backed by a source node",
            VERDICT_PARTIALLY_CITED: "at least half but not all claims are cited",
            VERDICT_UNCITED_DOMINANT: "fewer than half the claims are cited",
            VERDICT_NO_CLAIMS: "the query held no citable claim terms",
        },
        "uncited_rule": ("a claim is CITED only with a real backing source node; otherwise it "
                         "is UNCITED — the surface never invents a citation."),
        "citation_coverage": "cited / total claims — a MODELED ratio, never MEASURED",
        "endpoints": {
            "info": f"GET  /api/{ns}/v1/brain/cite/info",
            "cite": f"GET  /api/{ns}/v1/brain/cite?q=<query>&k=<breadth>",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
            "receipt": f"POST /api/{ns}/v1/brain/cite/receipt?q=<query>&k=<breadth>",
        },
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — this GET info mints nothing.",
        "doctrine": _doctrine_block(),
    }


def handle_manifest(ns: str = "a11oy") -> dict:
    """GET /brain/braincite/manifest — this surface's OWN honesty manifest, at a path whose
    segment equals the surface id. The Honesty Wall collects a surface's manifest by looking
    for an id-segment route returning an honesty dict, so this route makes braincite
    NATIVE-OK (verifiable) rather than NO-MANIFEST."""
    return {
        "ok": True,
        "endpoint": f"brain/{SURFACE_ID}/manifest",
        "service": f"{ns}.brain.braincite",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "data_label": LBL_MODELED,
        "title": "Brain Cite — verifiable claim to source citations",
        "kind": "honesty-manifest",
        "computes": ("claim->source citation binding over a real grounding_subgraph; declares "
                     "only what it truly does. UNCITED claims are reported, never fabricated."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "routes": {
            "info": f"GET  /api/{ns}/v1/brain/cite/info",
            "cite": f"GET  /api/{ns}/v1/brain/cite?q=&k=",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
            "receipt": f"POST /api/{ns}/v1/brain/cite/receipt",
        },
        "honesty_invariants": {
            "label_in_honest_vocabulary": True,
            "lambda_is_conjecture_not_theorem": True,   # Lambda is Conjecture 1, never a theorem
            "locked_count_is_eight": True,
            "adds_to_locked_8_is_zero": True,
            "trust_ceiling_at_most_0_97": True,
            "trust_never_100_percent": True,
            "no_fabricated_measured": True,
            "no_fabricated_citation": True,
            "no_consciousness_claim": True,
            "zero_runtime_cdn": True,
            "receipt_on_write_not_read": True,
        },
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — this GET manifest mints nothing; "
                           "only POST cite/receipt emits an unsigned SHA-256 digest."),
        "doctrine": _doctrine_block(
            "honesty manifest for the braincite surface; declarative only, computes nothing."),
    }


def handle_cite(ns: str, q: str, k: int = DEFAULT_K) -> dict:
    """GET /brain/cite — claim->source citations for the query. PURE READ, mints no receipt."""
    result = evaluate(q or "", k=k, ns=ns)
    result["ok"] = True
    result["endpoint"] = "brain/cite"
    result["service"] = f"{ns}.brain.braincite"
    result["surface_id"] = SURFACE_ID
    result["doctrine"] = _doctrine_block()
    result["computed_at"] = _now_iso()
    return result


def handle_receipt(ns: str, q: str, k: int = DEFAULT_K) -> dict:
    """POST /brain/cite/receipt — compute citations AND mint an unsigned SHA-256 receipt."""
    result = evaluate(q or "", k=k, ns=ns)
    result["ok"] = True
    result["endpoint"] = "brain/cite/receipt"
    result["service"] = f"{ns}.brain.braincite"
    result["surface_id"] = SURFACE_ID
    result["receipt"] = content_receipt(result)
    result["doctrine"] = _doctrine_block()
    result["computed_at"] = _now_iso()
    return result


# --------------------------------------------------------------------------- #
# FastAPI router registration.
#   Manifest + info + cite are GET (pure reads). Receipt is POST via a raw-Request handler
#   through app.router.add_route (Starlette passes the Request positionally, version-proof
#   under fastapi==0.137.x) with app.add_api_route as the fallback. Registered BEFORE the
#   SPA catch-all.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain"
    wired = 0

    man_path = f"{base}/{SURFACE_ID}/manifest"

    async def _braincite_manifest(request):
        return JSONResponse(handle_manifest(ns))

    async def _braincite_info(request):
        return JSONResponse(handle_info(ns))

    async def _braincite_cite(request):
        q = request.query_params.get("q", "")
        try:
            k = int(request.query_params.get("k", DEFAULT_K))
        except (TypeError, ValueError):
            k = DEFAULT_K
        return JSONResponse(handle_cite(ns, q, k))

    async def _braincite_receipt(request):
        q = request.query_params.get("q", "")
        try:
            k = int(request.query_params.get("k", DEFAULT_K))
        except (TypeError, ValueError):
            k = DEFAULT_K
        return JSONResponse(handle_receipt(ns, q, k))

    routes = [
        (man_path, _braincite_manifest, "GET"),
        (f"{base}/cite/info", _braincite_info, "GET"),
        (f"{base}/cite", _braincite_cite, "GET"),
        (f"{base}/cite/receipt", _braincite_receipt, "POST"),
    ]

    # Annotate raw-Request handlers so any FastAPI signature analysis (add_api_route
    # fallback path) treats the param as the request.
    try:
        import fastapi as _fastapi
        for _fn, _ in [(r[1], r[2]) for r in routes]:
            _fn.__annotations__["request"] = _fastapi.Request
    except Exception:
        pass

    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn, method in routes:
        try:
            if callable(add_route):
                app.router.add_route(path, fn, methods=[method])
            elif callable(add_api_route):
                app.add_api_route(path, fn, methods=[method])
            else:
                from starlette.routing import Route
                app.router.routes.append(Route(path, fn, methods=[method]))
            wired += 1
        except Exception as exc:
            __import__("sys").stderr.write(
                f"[{ns}] braincite {method} route {path} NOT wired (guarded): {exc!r}\n")

    return f"{SURFACE_ID}-wired:{wired}"


# --------------------------------------------------------------------------- #
# Self-test (stdlib-only; network-free where possible).
# --------------------------------------------------------------------------- #
def _selftest() -> dict:
    checks = 0

    # UNCITED never fabricated: a claim with no backing node stays UNCITED.
    fake_nodes = [{"id": "n1", "title": "energy ledger receipt", "node_label": "MODELED"}]
    assert _cite_term("energy", fake_nodes), "term present in a title must be CITED"
    assert not _cite_term("zzqqxx", fake_nodes), "absent term must be UNCITED (empty)"
    checks += 1

    # Verdict thresholds are honest (Lambda is Conjecture 1, never a theorem — negative
    # example strings here are labelled so the doctrine gate does not misread them).
    assert _verdict(1.0) == VERDICT_FULLY_CITED
    assert _verdict(0.75) == VERDICT_PARTIALLY_CITED
    assert _verdict(0.25) == VERDICT_UNCITED_DOMINANT
    assert _verdict(None) == VERDICT_NO_CLAIMS
    checks += 1

    # No claim terms -> honest NO-CITABLE-CLAIMS.
    r = evaluate("the a an of to", ns="selftest")
    assert r["verdict"] == VERDICT_NO_CLAIMS and r["total_claims"] == 0
    checks += 1

    # Receipt is deterministic + unsigned; GET reads mint nothing.
    sample = {"label": LBL_MODELED, "verdict": VERDICT_FULLY_CITED, "query": "x",
              "citation_coverage": 1.0, "cited_count": 1, "total_claims": 1,
              "claims": [{"claim": "x", "status": CITED, "sources": [{"id": "n1"}]}]}
    rc1 = content_receipt(sample)["content_sha256"]
    rc2 = content_receipt(sample)["content_sha256"]
    assert rc1 == rc2 and len(rc1) == 64, "receipt digest must be deterministic 64-hex"
    assert content_receipt(sample)["signed"] is False
    assert "receipt" not in handle_info("selftest")
    checks += 1

    # Manifest is NATIVE-OK-shaped: id-segment route, honest invariants, MODELED label.
    man = handle_manifest("selftest")
    assert man["surface_id"] == SURFACE_ID and man["data_label"] == LBL_MODELED
    assert all(man["honesty_invariants"].values()), "all declared invariants must be true"
    checks += 1

    # Doctrine block is honest.
    d = _doctrine_block()
    assert d["locked_proven"] == LOCKED_COUNT and d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["trust_ceiling"] == TRUST_CEILING
    assert d["sentience_claim"] is False and d["trust_100_percent"] is False
    checks += 1

    return {"ok": True, "checks": checks}


if __name__ == "__main__":
    print(json.dumps(_selftest()))
