# SPDX-License-Identifier: Apache-2.0
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
szl_brain_corpus — the Brain vault as a FIRST-CLASS RAG corpus source (Wave O, Dev 4).

Closes the flywheel loop the founder asked for: the Brain's harvested knowledge
(a11oy_brain_graph, itself built from brain/harvest/*.jsonl + the live estate)
becomes a retrievable, per-claim-citable corpus that szl_governed_rag can draw on
(corpus="brain"), and a compact "pulse" context the governed agent-loop can consult.

DOCTRINE (honest by construction):
  * The corpus is derived STRICTLY from real harvested Brain nodes — every passage
    is a real graph node with a real id, and its `source` citation is the node's own
    provenance (url / harvest source / kind). We NEVER fabricate a node or a citation.
  * If the Brain graph is empty / unimportable at runtime, available() is False and
    corpus() returns [] — the caller must surface UNAVAILABLE, never a fabricated hit.
  * Λ = Conjecture 1 — advisory, never "green". Adds NOTHING to the locked-8.

DEV-1 COORDINATION (the Brain read path / brain-hub pulse):
  brain_pulse() prefers Dev-1's szl_brain_hub.pulse() (the signed ecosystem pulse) as
  the canonical read path. If #brain-hub is not merged yet, it degrades to a GUARDED
  local summary built from a11oy_brain_graph (labeled brain_hub_available=False) so the
  agent-loop still gets honest context and never fabricates. See DEPENDENCY note below.

This module is a PURE READ: no network, deterministic given repo state.
"""
from __future__ import annotations

from typing import Any

# ── Brain read path (knowledge). a11oy_brain_graph reads brain/harvest/*.jsonl +
#    szl_puriq_formulas + a11oy_frontier_page — all already in the image. ──────────
try:
    import a11oy_brain_graph as _bg  # noqa: F401
    _BG_OK = True
    _BG_ERR = ""
except Exception as _e:  # pragma: no cover - import guard
    _bg = None  # type: ignore
    _BG_OK = False
    _BG_ERR = repr(_e)

# ── Dev-1 brain-hub (the signed pulse bus). Optional — guarded until #brain-hub
#    lands. When present we consult its pulse as the canonical read path. ──────────
try:
    import szl_brain_hub as _hub  # noqa: F401
    _HUB_OK = True
except Exception:  # pragma: no cover - Dev-1 dependency not merged yet
    _hub = None  # type: ignore
    _HUB_OK = False

CORPUS_ID = "brain"
_CONJECTURE_NOTE = "Λ = Conjecture 1 — NOT a theorem. Advisory, never 'green'."

# Node kinds that are the arXiv co-author MULTIPLIER — real people on real papers,
# but they overstate the corpus if each becomes its own passage. We drop them from
# the DEFAULT corpus (honest headline = distinct artifacts) but keep every artifact
# kind. a11oy_brain_graph already tracks this distinction (distinct_artifacts).
_PERSON_KINDS = frozenset({"person", "author"})

# Deterministic priority so the corpus is stable + the most useful artifacts lead.
_KIND_PRIORITY = {
    "formula": 0, "surface": 1, "endpoint": 2, "estate": 3, "topic": 4,
    "axis": 5, "paper": 6, "benchmark": 7, "dataset": 8, "standard": 9,
    "lab": 10, "org": 11, "repo": 12,
}


def available(ns: str = "a11oy") -> bool:
    """True iff the Brain graph is importable AND has harvested at least one node.

    This is the honest gate the caller checks before claiming a brain-sourced
    answer — False means the vault is empty/down and the caller must say UNAVAILABLE."""
    if not _BG_OK:
        return False
    try:
        g = _bg.get_brain_graph(ns)
        return bool(g.get("nodes"))
    except Exception:
        return False


def _node_text(n: dict[str, Any]) -> str:
    """Compose a real, self-describing passage from a Brain node's OWN fields.

    Strictly a projection of harvested attributes — no invented facts. The text is
    what the graph already asserts about the node (title, kind, organ, provenance)."""
    kind = str(n.get("kind", "node"))
    title = str(n.get("title") or n.get("id", ""))
    bits: list[str] = [f"{title} is a {kind} in the SZL Brain knowledge graph."]
    if kind == "formula":
        fid = n.get("formula_id", "")
        organ = n.get("organ", "")
        prim = n.get("primitive", "")
        proof = n.get("proof_status", "")
        if fid or organ:
            bits.append(f"Formula {fid} sits in the {organ} organ.".strip())
        if prim:
            bits.append(f"Its primitive is: {prim}.")
        if proof:
            bits.append(f"Proof status: {proof}.")
        if n.get("conjecture") and str(n.get("conjecture")) != "None":
            bits.append(f"Conjecture: {n['conjecture']}.")
        if str(n.get("locked")).lower() == "true":
            bits.append("Flagged locked-8 (adds nothing; not modified here).")
    elif kind in ("paper", "benchmark", "dataset", "standard", "lab", "org", "person", "author"):
        axis = n.get("axis", "")
        src = n.get("source", "")
        if axis:
            bits.append(f"It is harvested on the '{axis}' research axis.")
        if src:
            bits.append(f"Harvest source: {src}.")
        if n.get("url"):
            bits.append(f"Reference: {n['url']}.")
    elif kind == "surface":
        if n.get("asset"):
            bits.append(f"Frontier surface asset: {n['asset']}.")
    elif kind == "endpoint":
        if n.get("path"):
            bits.append(f"Endpoint path: {n['path']}.")
    elif kind == "axis":
        if n.get("url"):
            bits.append(f"Axis reference: {n['url']}.")
    elif kind == "topic":
        if n.get("derived_from"):
            bits.append(f"Derived from {n['derived_from']}.")
    if n.get("note"):
        bits.append(str(n["note"]))
    return " ".join(b for b in bits if b).strip()


def _node_source(n: dict[str, Any]) -> str:
    """The node's OWN provenance string — this becomes the per-claim citation.

    Never fabricated: it is the harvest source / url / kind the graph already carries."""
    kind = str(n.get("kind", "node"))
    label = str(n.get("label", ""))
    prov = n.get("url") or n.get("source") or n.get("path") or ""
    tag = f"Brain[{CORPUS_ID}] {kind}"
    if label:
        tag += f" · {label}"
    if prov:
        tag += f" · {prov}"
    else:
        tag += f" · node {n.get('id', '')}"
    return tag


def corpus(ns: str = "a11oy", *, limit: int = 400,
           include_people: bool = False) -> list[dict[str, str]]:
    """Build the Brain RAG corpus: a list of {id, text, source} passages, one per
    real harvested node. Deterministic ordering (kind priority, then id). Returns []
    when the Brain is empty/down — the caller MUST then surface UNAVAILABLE.

    Every id is a real graph node id; every `source` is that node's own provenance
    so per-claim citations are auditable back to the Brain vault. Bounded by `limit`
    so a 9k-node graph doesn't blow the retriever — the highest-priority artifacts
    (formulas, surfaces, endpoints, then harvested field artifacts) lead."""
    if not available(ns):
        return []
    try:
        g = _bg.get_brain_graph(ns)
    except Exception:
        return []
    nodes = g.get("nodes") or []

    def _key(n: dict[str, Any]):
        return (_KIND_PRIORITY.get(str(n.get("kind")), 99), str(n.get("id", "")))

    out: list[dict[str, str]] = []
    for n in sorted(nodes, key=_key):
        kind = str(n.get("kind", ""))
        if kind in _PERSON_KINDS and not include_people:
            continue
        text = _node_text(n)
        if not text:
            continue
        out.append({
            "id": str(n.get("id", "")),
            "text": text,
            "source": _node_source(n),
        })
        if len(out) >= max(1, int(limit)):
            break
    return out


def stats(ns: str = "a11oy") -> dict[str, Any]:
    """Honest headline about the Brain corpus — counts are real len()s, never faked."""
    if not _BG_OK:
        return {"available": False, "reason": "a11oy_brain_graph unimportable",
                "error": _BG_ERR, "conjecture_note": _CONJECTURE_NOTE}
    try:
        g = _bg.get_brain_graph(ns)
    except Exception as e:
        return {"available": False, "reason": "brain graph build failed",
                "error": repr(e), "conjecture_note": _CONJECTURE_NOTE}
    summ = g.get("summary", {})
    return {
        "available": bool(g.get("nodes")),
        "node_count": g.get("node_count", 0),
        "link_count": g.get("link_count", 0),
        "distinct_artifacts": g.get("distinct_artifacts", 0),
        "by_kind": summ.get("by_kind", {}),
        "harvest_available": (_bg.harvest_available() if hasattr(_bg, "harvest_available") else None),
        "corpus_label": "HARVESTED (Brain knowledge graph) — real nodes, real provenance",
        "conjecture_note": _CONJECTURE_NOTE,
    }


def brain_pulse(ns: str = "a11oy", query: str = "", *, top_k: int = 5) -> dict[str, Any]:
    """A compact, honest Brain 'pulse' context for the agent-loop to CONSULT.

    Read path (Dev-1 coordination):
      * PREFERRED: Dev-1's szl_brain_hub.pulse() — the signed ecosystem pulse. When
        present we surface its knowledge summary (brain_hub_available=True).
      * GUARDED FALLBACK (until #brain-hub merges): a local summary built directly
        from a11oy_brain_graph (brain_hub_available=False + a dependency note). Still
        real, still honest — no fabricated pulse.

    Optionally includes the top-`top_k` brain passages lexically relevant to `query`
    (real nodes only) so the loop can ground on them. Returns available=False +
    UNAVAILABLE when the Brain is empty/down."""
    base: dict[str, Any] = {
        "corpus_id": CORPUS_ID,
        "brain_hub_available": _HUB_OK,
        "conjecture_note": _CONJECTURE_NOTE,
    }

    # PREFERRED read path: Dev-1's signed pulse.
    if _HUB_OK and _hub is not None:
        try:
            p = _hub.pulse(ns) if hasattr(_hub, "pulse") else None
            if isinstance(p, dict):
                base["source"] = "szl_brain_hub.pulse (Dev-1 signed pulse bus)"
                base["available"] = True
                base["label"] = "LIVE (brain-hub pulse)"
                base["knowledge"] = p.get("knowledge") or p.get("knowledge_summary") or {}
                base["energy"] = p.get("energy") or p.get("energy_summary")
                base["lambda_advisory"] = p.get("lambda") or _CONJECTURE_NOTE
                base["hub_receipt"] = p.get("receipt")
        except Exception as e:  # pragma: no cover - hub present but errored
            base["hub_note"] = f"brain-hub present but pulse() failed: {e!r}; using guarded fallback."

    # GUARDED FALLBACK / enrichment: local graph summary.
    if not base.get("available"):
        st = stats(ns)
        base["source"] = "a11oy_brain_graph (guarded local fallback)"
        base["available"] = bool(st.get("available"))
        base["label"] = ("MODELED (local brain-graph summary; brain-hub not merged — "
                         "see DEPENDENCY)" if st.get("available") else
                         "UNAVAILABLE — Brain vault empty/down; no context fabricated")
        base["knowledge"] = {
            "node_count": st.get("node_count", 0),
            "link_count": st.get("link_count", 0),
            "distinct_artifacts": st.get("distinct_artifacts", 0),
            "by_kind": st.get("by_kind", {}),
        }
        base["dependency"] = ("Dev-1 szl_brain_hub (#brain-hub) not merged in this runtime; "
                              "consulting a11oy_brain_graph directly as a guarded fallback. "
                              "Code targets szl_brain_hub.pulse() when it lands.")

    if not base.get("available"):
        base.setdefault("label", "UNAVAILABLE — Brain vault empty/down; no context fabricated")
        base["relevant"] = []
        return base

    # Optional: top-k brain passages relevant to the task (real nodes only).
    relevant: list[dict[str, str]] = []
    q = str(query or "").strip().lower()
    if q:
        toks = {t for t in q.replace("/", " ").replace("-", " ").split() if len(t) > 2}
        scored: list[tuple[int, dict[str, str]]] = []
        for doc in corpus(ns, limit=1000):
            dt = doc["text"].lower()
            score = sum(1 for t in toks if t in dt)
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda kv: (-kv[0], kv[1]["id"]))
        relevant = [{"id": d["id"], "text": d["text"][:240], "source": d["source"]}
                    for _, d in scored[: max(1, int(top_k))]]
    base["relevant"] = relevant
    base["relevant_note"] = ("Top brain passages lexically relevant to the task (real "
                             "harvested nodes; cite by id/source). Empty when nothing "
                             "in the vault matches — never padded.")
    return base


def _selftest() -> None:  # pragma: no cover
    print(f"[szl_brain_corpus] brain_graph_ok={_BG_OK} brain_hub_ok={_HUB_OK}")
    print(f"[szl_brain_corpus] available={available()}")
    st = stats()
    print(f"[szl_brain_corpus] stats: nodes={st.get('node_count')} "
          f"distinct={st.get('distinct_artifacts')} available={st.get('available')}")
    c = corpus(limit=25)
    assert isinstance(c, list)
    if available():
        assert c, "brain available but corpus empty"
        for d in c:
            assert d["id"] and d["text"] and d["source"], f"bad brain passage {d}"
        # every id must be a REAL node id (no fabrication)
        g = _bg.get_brain_graph()
        real_ids = {n["id"] for n in g["nodes"]}
        for d in c:
            assert d["id"] in real_ids, f"fabricated brain id {d['id']}"
        print(f"[szl_brain_corpus] corpus OK: {len(c)} real passages, ids verified real.")
    else:
        assert c == [], "brain unavailable must yield empty corpus (honest UNAVAILABLE)"
        print("[szl_brain_corpus] Brain UNAVAILABLE — empty corpus (honest).")
    pulse = brain_pulse(query="euler khipu formula proof")
    assert "available" in pulse and "label" in pulse
    print(f"[szl_brain_corpus] pulse: available={pulse['available']} label={pulse['label']!r} "
          f"relevant={len(pulse.get('relevant', []))}")
    print("[szl_brain_corpus] ALL OK — Λ = Conjecture 1 (advisory, never green).")


if __name__ == "__main__":
    _selftest()
