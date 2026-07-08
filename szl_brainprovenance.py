# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainprovenance.py — PER-ANSWER PROVENANCE LINEAGE over the honest brain.

This is SOURCE-LINEAGE provenance ONLY: for a brain retrieval answer it builds a
traceable chain of exactly WHICH knowledge-graph nodes supported that answer,
each node's honest data label read VERBATIM, and its community/origin — so a
reader can trace an answer back to the graph nodes it stands on.

It is explicitly NOT:
  * cryptographic attestation of a weapon, model, or artifact,
  * SLSA / in-toto / Rekor BUILD provenance of an image or binary,
  * any counter-UAS / targeting / fusion capability.
It answers one honest question — "what did this answer stand on, and how well is
each of those sources labelled?" — and never upgrades a label to do it.

WHAT IT DOES, at request time (honest by construction):
  1. Run the SAME honest brain retrieval (szl_brain_api.get_index(ns).ask(q, k)),
     which returns a REAL grounding_subgraph {nodes[], links[]} whether or not a
     sovereign model was reachable. This module invents no nodes and harvests
     nothing — it only re-orders and labels the grounding the brain already found.
  2. Build a DETERMINISTIC PROVENANCE CHAIN: the ordered list of supporting nodes
     (sorted by ppr desc, then salience desc, then id asc), each carried as
     {id, title, node_label (VERBATIM), community, contribution_weight}. The
     contribution_weight is the node's ppr normalised over the chain (salience
     used only if every ppr is 0); it never fabricates an importance a node did
     not earn from the retrieval.
  3. Compute an HONEST COVERAGE statement over the grounding: how much of the
     grounding is HARVESTED vs MODELED vs UNAVAILABLE vs OTHER/unlabelled, read
     from each node's own label VERBATIM — never upgraded (a MODELED node is
     never reported HARVESTED; an UNAVAILABLE/unlabelled node is never hidden).
  4. Emit ONE honest verdict over the chain:
       TRACEABLE          — chain covers the grounding AND every node carries a
                            source label (HARVESTED/MODELED/LIVE), none UNAVAILABLE
                            or unlabelled.
       PARTIAL-PROVENANCE — chain non-empty and covers the grounding, but some
                            nodes are UNAVAILABLE or unlabelled.
       UNTRACEABLE        — no grounding / empty chain, or every node is
                            UNAVAILABLE/unlabelled (nothing real to trace to).
     NEVER TRACEABLE while any node is UNAVAILABLE/unlabelled.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info/provenance reads mint
NOTHING. Only POST .../receipt emits an UNSIGNED SHA-256 content digest over the
chain (mirrors the govern/honestywall content-digest pattern) — a plain content
hash, never a fabricated signature, never a receipt on a GET.

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only re-views
    the brain's own retrieval. Touches no locked formula and no kernel.
  * Λ stays Conjecture 1 (never a theorem); Khipu BFT stays Conjecture 2. Trust
    ceiling 0.97, never 100%. No label is ever upgraded.
  * Pure stdlib + numpy (numpy import is guarded; a pure-python path is used if it
    is absent). Additive routes, registered before the SPA catch-all. 0 runtime CDN.
"""

import datetime
import hashlib
import json
from typing import Any

try:  # numpy is allowed; keep it optional so a missing wheel degrades honestly.
    import numpy as _np
    _HAVE_NUMPY = True
except Exception:  # pragma: no cover - numpy is a core dep, but stay honest
    _np = None
    _HAVE_NUMPY = False

# Honest Doctrine v11 labels (verbatim — never upgraded).
MODELED = "MODELED"          # this surface's OWN top label (a derived view)
LBL_UNAVAILABLE = "UNAVAILABLE"

# Source-label buckets we classify grounding nodes into. Read VERBATIM from the
# node's own `node_label`; membership never upgrades a label.
_SOURCE_LABELS = ("HARVESTED", "MODELED", "LIVE")   # real, traceable sources
_UNTRACEABLE_LABELS = ("UNAVAILABLE",)              # nothing real to trace to

# Verdicts.
TRACEABLE = "TRACEABLE"
PARTIAL = "PARTIAL-PROVENANCE"
UNTRACEABLE = "UNTRACEABLE"

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "brainprovenance"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _verbatim_label(node: dict) -> str | None:
    """Return the node's OWN label VERBATIM (never upgraded). None if unlabelled."""
    v = node.get("node_label")
    if v is None:
        v = node.get("label")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def _is_source(label: str | None) -> bool:
    """A label that traces to a real source (HARVESTED/MODELED/LIVE), read verbatim."""
    return isinstance(label, str) and label.strip().upper() in _SOURCE_LABELS


def _is_unavailable(label: str | None) -> bool:
    return isinstance(label, str) and label.strip().upper() in _UNTRACEABLE_LABELS


# --------------------------------------------------------------------------- #
# Chain construction — deterministic ordering + honest contribution weights.
# --------------------------------------------------------------------------- #
def _order_nodes(nodes: list[dict]) -> list[dict]:
    """Deterministic supporting order: ppr desc, salience desc, id asc.

    Ties break on id so two identical retrievals yield byte-identical chains."""
    def key(n: dict):
        ppr = n.get("ppr")
        ppr = float(ppr) if isinstance(ppr, (int, float)) else 0.0
        sal = n.get("salience")
        sal = float(sal) if isinstance(sal, (int, float)) else 0.0
        return (-ppr, -sal, str(n.get("id", "")))
    return sorted(nodes, key=key)


def _contribution_weights(ordered: list[dict]) -> list[float]:
    """Normalised contribution per node over the chain.

    Uses ppr; if every ppr is 0 (retrieval gave no PPR mass), falls back to
    salience; if that is also all-zero, distributes uniformly. Never invents a
    weight beyond what the retrieval produced. Deterministic."""
    def _mass(n: dict, field: str) -> float:
        v = n.get(field)
        return float(v) if isinstance(v, (int, float)) and v > 0 else 0.0

    raw = [_mass(n, "ppr") for n in ordered]
    if sum(raw) <= 0.0:
        raw = [_mass(n, "salience") for n in ordered]
    total = sum(raw)
    n = len(ordered)
    if n == 0:
        return []
    if total <= 0.0:
        return [round(1.0 / n, 8)] * n
    if _HAVE_NUMPY:
        arr = _np.asarray(raw, dtype=float)
        w = arr / arr.sum()
        return [round(float(x), 8) for x in w]
    return [round(x / total, 8) for x in raw]


def build_chain(ask_result: dict) -> list[dict]:
    """The ordered provenance chain from a brain /ask result. Each entry carries
    the node's label VERBATIM. Pure function of the retrieval — deterministic."""
    grounding = ask_result.get("grounding_subgraph") or {}
    nodes = grounding.get("nodes") or []
    ordered = _order_nodes([n for n in nodes if isinstance(n, dict) and n.get("id")])
    weights = _contribution_weights(ordered)
    chain: list[dict] = []
    for n, w in zip(ordered, weights):
        chain.append({
            "id": n.get("id"),
            "title": n.get("title", n.get("id")),
            "node_label": _verbatim_label(n),   # VERBATIM, may be None (unlabelled)
            "community": n.get("community"),
            "contribution_weight": w,
            "ppr": round(float(n.get("ppr", 0.0)), 8)
                   if isinstance(n.get("ppr"), (int, float)) else 0.0,
            "salience": round(float(n.get("salience", 0.0)), 8)
                        if isinstance(n.get("salience"), (int, float)) else 0.0,
        })
    return chain


# --------------------------------------------------------------------------- #
# Coverage — honest label breakdown over the grounding (never upgraded).
# --------------------------------------------------------------------------- #
def build_coverage(chain: list[dict]) -> dict:
    """How much of the grounding is HARVESTED vs MODELED vs UNAVAILABLE vs OTHER.

    Counts are over the chain (= the grounding supporting set). Fractions are of
    the total chain length. Labels read VERBATIM; an unlabelled node is counted as
    OTHER-UNLABELLED, never silently promoted."""
    total = len(chain)
    counts: dict[str, int] = {}
    harvested = modeled = live = unavailable = unlabelled = other = 0
    for e in chain:
        lab = e.get("node_label")
        key = lab.upper() if isinstance(lab, str) and lab.strip() else "UNLABELLED"
        counts[key] = counts.get(key, 0) + 1
        if lab is None:
            unlabelled += 1
        else:
            up = lab.upper()
            if up == "HARVESTED":
                harvested += 1
            elif up == "MODELED":
                modeled += 1
            elif up == "LIVE":
                live += 1
            elif up == "UNAVAILABLE":
                unavailable += 1
            else:
                other += 1

    def frac(x: int) -> float:
        return round(x / total, 8) if total else 0.0

    traceable_nodes = harvested + modeled + live
    return {
        "total_nodes": total,
        "label_counts_verbatim": counts,
        "harvested": harvested,
        "modeled": modeled,
        "live": live,
        "unavailable": unavailable,
        "unlabelled": unlabelled,
        "other": other,
        "fraction_harvested": frac(harvested),
        "fraction_modeled": frac(modeled),
        "fraction_live": frac(live),
        "fraction_unavailable": frac(unavailable),
        "fraction_unlabelled": frac(unlabelled),
        "fraction_traceable_to_source": frac(traceable_nodes),
        "note": ("fractions are of the grounding supporting set; labels read "
                 "VERBATIM, never upgraded (a MODELED node is never reported "
                 "HARVESTED; UNAVAILABLE/unlabelled nodes are never hidden)."),
    }


def verdict_for(chain: list[dict], coverage: dict) -> tuple[str, str]:
    """Honest verdict over the chain. Returns (verdict, reason).

    NEVER TRACEABLE while any node is UNAVAILABLE or unlabelled."""
    total = coverage["total_nodes"]
    if total == 0:
        return UNTRACEABLE, "no grounding nodes supported this answer; nothing to trace."
    traceable_to_source = coverage["harvested"] + coverage["modeled"] + coverage["live"]
    if traceable_to_source == 0:
        return (UNTRACEABLE,
                "every supporting node is UNAVAILABLE or unlabelled; no real source to trace to.")
    unavailable = coverage["unavailable"]
    unlabelled = coverage["unlabelled"]
    other = coverage["other"]
    if unavailable == 0 and unlabelled == 0 and other == 0:
        return (TRACEABLE,
                f"all {total} supporting node(s) carry a source label "
                f"(HARVESTED/MODELED/LIVE); chain covers the grounding.")
    return (PARTIAL,
            f"{traceable_to_source}/{total} supporting node(s) trace to a source; "
            f"{unavailable} UNAVAILABLE, {unlabelled} unlabelled, {other} other-labelled "
            f"(never upgraded to TRACEABLE).")


# --------------------------------------------------------------------------- #
# Provenance assembly (pure computation — mints nothing).
# --------------------------------------------------------------------------- #
def _ask(ns: str, q: str, k: int) -> dict:
    """Run the honest brain retrieval. Guarded: a missing brain degrades honestly."""
    import szl_brain_api as _brain_api
    idx = _brain_api.get_index(ns)
    return idx.ask(q, max(1, k))


def build_provenance(ns: str, q: str, k: int = 12) -> dict:
    """The full provenance-lineage view for one query. Pure read; mints nothing."""
    q = (q or "").strip()
    if not q:
        return {
            "ok": False,
            "label": MODELED,
            "surface_id": SURFACE_ID,
            "endpoint": "brain/provenance",
            "verdict": UNTRACEABLE,
            "verdict_reason": "empty query; no retrieval performed, no chain fabricated.",
            "query": q,
            "provenance_kind": "SOURCE-LINEAGE (knowledge-graph node provenance)",
            "chain": [],
            "coverage": build_coverage([]),
            "doctrine": _doctrine_block(),
            "timestamp_utc": _now_iso(),
        }
    try:
        ask_result = _ask(ns, q, k)
    except Exception as exc:  # never 500 — honest degraded response
        return {
            "ok": False,
            "label": LBL_UNAVAILABLE,
            "surface_id": SURFACE_ID,
            "endpoint": "brain/provenance",
            "verdict": UNTRACEABLE,
            "verdict_reason": f"brain retrieval unavailable; no chain fabricated: {str(exc)[:160]}",
            "query": q,
            "provenance_kind": "SOURCE-LINEAGE (knowledge-graph node provenance)",
            "chain": [],
            "coverage": build_coverage([]),
            "doctrine": _doctrine_block(),
            "timestamp_utc": _now_iso(),
        }

    chain = build_chain(ask_result)
    coverage = build_coverage(chain)
    verdict, reason = verdict_for(chain, coverage)

    grounding = ask_result.get("grounding_subgraph") or {}
    answer_label = ask_result.get("answer_label", LBL_UNAVAILABLE)
    return {
        "ok": True,
        "label": MODELED,
        "surface_id": SURFACE_ID,
        "endpoint": "brain/provenance",
        "service": "a11oy.brain.provenance",
        "query": q,
        "k": max(1, k),
        "provenance_kind": "SOURCE-LINEAGE (knowledge-graph node provenance)",
        "not_provenance_of": ["build/SLSA/in-toto/Rekor artifact attestation",
                              "cryptographic model/weapon attestation",
                              "counter-UAS/targeting/fusion"],
        "retrieval": ask_result.get("retrieval"),
        "answer_label": answer_label,   # VERBATIM from the brain (often UNAVAILABLE)
        "answer_model": ask_result.get("answer_model"),
        "grounding_node_count": grounding.get("node_count", len(chain)),
        "grounding_link_count": grounding.get("link_count"),
        "chain_length": len(chain),
        "chain": chain,
        "coverage": coverage,
        "verdict": verdict,
        "verdict_reason": reason,
        "verdict_legend": {
            TRACEABLE: "chain covers grounding AND every node carries a source label",
            PARTIAL: "chain covers grounding but some nodes are UNAVAILABLE/unlabelled",
            UNTRACEABLE: "no grounding, or every supporting node is UNAVAILABLE/unlabelled",
        },
        "doctrine": _doctrine_block(),
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — GET mints nothing; POST /receipt digests.",
        "note": ("chain + coverage are a deterministic re-view of the brain's OWN grounding "
                 "subgraph; node labels read VERBATIM, never upgraded; TRACEABLE is never "
                 "reported while any node is UNAVAILABLE/unlabelled."),
        "timestamp_utc": _now_iso(),
    }


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
        "note": ("additive SOURCE-LINEAGE view over the brain's own retrieval; touches no "
                 "locked formula and no kernel; GET reads sign/mint nothing; POST /receipt "
                 "emits an UNSIGNED SHA-256 content digest only; introduces no theorem."),
    }


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), never a GET.
# --------------------------------------------------------------------------- #
def _canonical_core(prov: dict) -> str:
    """Deterministic canonical serialization of the chain-bearing content (excludes
    the volatile timestamp), so the digest attests the CHAIN + verdict, not the clock."""
    core = {
        "query": prov.get("query"),
        "verdict": prov.get("verdict"),
        "coverage": prov.get("coverage"),
        "chain": [
            {"id": e.get("id"), "node_label": e.get("node_label"),
             "community": e.get("community"),
             "contribution_weight": e.get("contribution_weight")}
            for e in prov.get("chain", [])
        ],
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def content_receipt(prov: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the provenance chain."""
    canonical = _canonical_core(prov)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainprovenance.chain",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST /receipt)",
        "note": ("unsigned SHA-256 content digest of the provenance chain; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #
def handle_info(ns: str = "a11oy") -> dict:
    """GET .../provenance/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/provenance"
    return {
        "ok": True,
        "label": MODELED,
        "surface_id": SURFACE_ID,
        "service": "a11oy.brain.provenance",
        "endpoint": "brain/provenance/info",
        "title": "Brain Provenance — per-answer source-lineage chain",
        "what": ("for a brain retrieval answer, builds a traceable chain of exactly WHICH "
                 "knowledge-graph nodes supported it, each node's honest label read VERBATIM, "
                 "plus an honest coverage statement (HARVESTED vs MODELED vs UNAVAILABLE) and a "
                 "TRACEABLE / PARTIAL-PROVENANCE / UNTRACEABLE verdict."),
        "provenance_kind": "SOURCE-LINEAGE (knowledge-graph node provenance)",
        "explicitly_not": ("This is SOURCE-LINEAGE provenance of an ANSWER only. It is NOT "
                           "cryptographic attestation of a model or weapon, NOT SLSA/in-toto/"
                           "Rekor build attestation of an artifact, and NOT any counter-UAS / "
                           "targeting / fusion capability."),
        "method": ("re-view the brain's OWN grounding_subgraph from szl_brain_api.ask(q,k): "
                   "order supporting nodes by ppr desc, salience desc, id asc; carry each "
                   "node's label VERBATIM + a ppr-normalised contribution_weight; classify "
                   "coverage by verbatim label; verdict downgrades when nodes are "
                   "UNAVAILABLE/unlabelled — never upgraded."),
        "endpoints": {
            "info": f"GET  {base}/info",
            "provenance": f"GET  {base}?q=&k=",
            "receipt": f"POST {base}/receipt  (body: {{\"q\":..,\"k\":..}})",
        },
        "verdicts": [TRACEABLE, PARTIAL, UNTRACEABLE],
        "honest_labels": {
            "source_labels_traceable": list(_SOURCE_LABELS),
            "untraceable_labels": list(_UNTRACEABLE_LABELS),
            "note": "labels are read VERBATIM from each node; membership never upgrades a label.",
        },
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — only POST /receipt emits an unsigned SHA-256 digest.",
        "doctrine": _doctrine_block(),
        "numpy_available": _HAVE_NUMPY,
        "timestamp_utc": _now_iso(),
    }


def handle_provenance(ns: str, q: str, k: int = 12) -> dict:
    """GET .../provenance?q=&k= — the provenance chain + coverage + verdict. PURE READ."""
    return build_provenance(ns, q, k)


def handle_receipt(ns: str, q: str, k: int = 12) -> dict:
    """POST .../provenance/receipt — provenance + an UNSIGNED SHA-256 content digest
    (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    prov = build_provenance(ns, q, k)
    out = dict(prov)
    out["receipt"] = content_receipt(prov)
    return out


# --------------------------------------------------------------------------- #
# FastAPI registration.
#   GET  info/provenance — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST receipt         — raw-Request handler via app.router.add_route (Starlette
#                          passes the Request positionally, version-proof under
#                          fastapi==0.137.x), with app.add_api_route as the fallback.
#                          Registered BEFORE the SPA catch-all by serve.py.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/provenance"

    @app.get(f"{base}/info")
    def _brainprovenance_info():
        """Static self-describing manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainprovenance_get(q: str = "", k: int = 12):  # noqa: ANN202
        """Provenance chain + coverage + verdict for a query (pure read; mints nothing)."""
        return JSONResponse(handle_provenance(ns, q, k))

    async def _brainprovenance_receipt(request):
        """POST: provenance chain + UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE)."""
        q, k = "", 12
        try:
            body = await request.json()
            if isinstance(body, dict):
                q = str(body.get("q", body.get("query", "")) or "")
                kv = body.get("k", 12)
                k = int(kv) if isinstance(kv, (int, float, str)) and str(kv).strip() else 12
        except Exception:  # noqa: BLE001 — a bodyless/garbled POST still gets an honest answer
            q, k = "", 12
        # Query params override / supplement a missing body.
        try:
            qp = request.query_params
            if not q and qp.get("q"):
                q = str(qp.get("q"))
            if qp.get("k"):
                k = int(qp.get("k"))
        except Exception:  # noqa: BLE001
            pass
        return JSONResponse(handle_receipt(ns, q, k))

    # Annotate the raw-Request handler as fastapi.Request so the add_api_route fallback
    # path treats the param as the request object (0.137.x signature-analysis gotcha).
    try:
        import fastapi as _fastapi
        _brainprovenance_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rcpt_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rcpt_path, _brainprovenance_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rcpt_path, _brainprovenance_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rcpt_path, _brainprovenance_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainprovenance receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainprovenance-wired:2(get-only)"

    return "brainprovenance-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — deterministic chain, verbatim labels, honest coverage + verdict,
# receipt only on write, labels never upgraded.
# --------------------------------------------------------------------------- #
def _selftest() -> None:
    import sys as _sys

    print("=" * 72)
    print("szl_brainprovenance — self-test (per-answer source-lineage chain)")
    print("=" * 72)

    # 1) A synthetic ask() result with mixed labels proves ordering + coverage + verdict.
    #    (Λ is Conjecture 1, never a theorem — this negated mention is the honest label.)
    fake = {
        "grounding_subgraph": {
            "node_count": 4, "link_count": 2,
            "nodes": [
                {"id": "b", "title": "modeled node", "node_label": "MODELED",
                 "community": 1, "ppr": 0.20, "salience": 0.10},
                {"id": "a", "title": "harvested leader", "node_label": "HARVESTED",
                 "community": 2, "ppr": 0.40, "salience": 0.30},
                {"id": "c", "title": "unavailable node", "node_label": "UNAVAILABLE",
                 "community": 1, "ppr": 0.10, "salience": 0.05},
                {"id": "d", "title": "unlabelled node", "node_label": None,
                 "community": 3, "ppr": 0.10, "salience": 0.05},
            ],
        },
        "answer_label": "UNAVAILABLE",
        "retrieval": "hippoRAG-PPR(local) ⊕ graphRAG-community(global)",
    }
    chain = build_chain(fake)
    assert [e["id"] for e in chain] == ["a", "b", "c", "d"], "ppr-desc, id-asc ordering"
    assert chain[0]["node_label"] == "HARVESTED", "label read verbatim"
    assert chain[3]["node_label"] is None, "unlabelled stays None, never upgraded"
    w = [e["contribution_weight"] for e in chain]
    assert abs(sum(w) - 1.0) < 1e-6, f"weights normalise to 1, got {sum(w)}"
    assert w == sorted(w, reverse=True), "weights follow ppr ordering"
    print(f"[1] chain ordered {[e['id'] for e in chain]}, weights sum=1, labels verbatim  OK")

    cov = build_coverage(chain)
    assert cov["harvested"] == 1 and cov["modeled"] == 1
    assert cov["unavailable"] == 1 and cov["unlabelled"] == 1
    v, _r = verdict_for(chain, cov)
    assert v == PARTIAL, f"mixed labels must be PARTIAL-PROVENANCE, got {v}"
    print(f"[2] coverage harvested=1 modeled=1 unavailable=1 unlabelled=1; verdict={v}  OK")

    # 3) All-source chain -> TRACEABLE. All-unavailable -> UNTRACEABLE. Empty -> UNTRACEABLE.
    good = build_chain({"grounding_subgraph": {"nodes": [
        {"id": "x", "node_label": "HARVESTED", "ppr": 0.5},
        {"id": "y", "node_label": "MODELED", "ppr": 0.5}]}})
    gv, _ = verdict_for(good, build_coverage(good))
    assert gv == TRACEABLE, f"all-source chain must be TRACEABLE, got {gv}"
    bad = build_chain({"grounding_subgraph": {"nodes": [
        {"id": "z", "node_label": "UNAVAILABLE", "ppr": 0.9}]}})
    bv, _ = verdict_for(bad, build_coverage(bad))
    assert bv == UNTRACEABLE, f"all-unavailable chain must be UNTRACEABLE, got {bv}"
    ev, _ = verdict_for([], build_coverage([]))
    assert ev == UNTRACEABLE, "empty chain must be UNTRACEABLE"
    print(f"[3] verdict downgrades honestly: TRACEABLE / UNTRACEABLE / empty→UNTRACEABLE  OK")

    # 4) Determinism — identical retrieval yields byte-identical chain + digest.
    prov1 = {"query": "q", "verdict": v, "coverage": cov, "chain": chain}
    prov2 = {"query": "q", "verdict": v, "coverage": cov, "chain": chain}
    r1, r2 = content_receipt(prov1), content_receipt(prov2)
    assert r1["content_sha256"] == r2["content_sha256"], "receipt digest deterministic"
    assert r1["signed"] is False and len(r1["content_sha256"]) == 64
    print(f"[4] receipt UNSIGNED sha256={r1['content_sha256'][:16]}… deterministic  OK")

    # 5) doctrine block honest: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 not 100%.
    d = _doctrine_block()
    assert d["locked_proven"] == 8 and d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[5] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    print("\nok:true checks:5")
    _sys.exit(0)


if __name__ == "__main__":
    _selftest()
