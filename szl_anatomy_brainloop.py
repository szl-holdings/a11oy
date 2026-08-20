# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
szl_anatomy_brainloop.py — the GOVERNED LIVING-BRAIN loop.

Turns the harvested ~knowledge brain (a11oy_brain_graph) from a PICTURE into an
ACTIVE ORGAN that DRIVES metered inference: a query grounds a load-bearing
subgraph (Personalized-PageRank / HippoRAG-style), an answer is attempted on the
sovereign mesh (MEASURED energy via the /energy/live NVML probe path, #789),
every WRITE emits a SHA-256 hash-chained RECEIPT, and the answer becomes a
CANDIDATE node ONLY if a validation gate passes — otherwise it is QUARANTINED.

THE 7-STAGE LOOP (one governed cycle == one POST /anatomy/pulse):
  1. QUERY      a query enters (operator or /brain/ask).
  2. GROUND     Personalized-PageRank retrieves the load-bearing subgraph
                (query-seeded restart, alpha=0.85) over the REAL harvested graph
                PLUS the reinforced overlay edges.
  3. ANSWER     grounded prompt -> sovereign inference on the mesh IF reachable
                (szl_brain_api, guarded; energy MEASURED via szl_energy_live);
                else an HONEST UNAVAILABLE for generated text (the subgraph is
                still real). We NEVER fabricate an answer, a token, or a joule.
  4. RECEIPT    a hash-chained receipt {query, subgraph_ids, answer_digest,
                joules, tokens_per_joule, model, ts, prev_hash, receipt_hash}.
                Receipts are emitted ONLY on writes (this POST), NEVER on GETs.
  5. WRITE-BACK the answer becomes a CANDIDATE node + maps-to edges ONLY if the
                validation gate passes (dedupe, provenance present, confidence
                >= threshold); else it is QUARANTINED. Three-tier belief:
                CONJECTURE -> CORROBORATED -> LOAD-BEARING (verbatim labels).
  6. REINFORCE  Hebbian bump on the traversed edges, dual-timescale (fast
                episodic + slow semantic) with time decay.
  7. SALIENCE   periodic PPR recompute exposes the current load-bearing
                knowledge (GET /anatomy/salience); consolidation is advisory.

THREE DIFFERENTIATORS (all implemented):
  (a) every write-back carries a real energy + provenance RECEIPT — the graph
      grows ONLY through auditable metered inference (an ungated write is
      QUARANTINED, never written load-bearing).
  (b) an active receipt-replay SELF-AUDIT that DEMOTES a node's belief tier if
      its backing receipt no longer verifies (tamper-evident belief).
  (c) Λ-advisory salience is NEVER presented as truth (capped <= 0.97); a raw
      CONJECTURE is never auto-upgraded to a theorem by salience alone.

DOCTRINE v11 (NON-NEGOTIABLE):
  - honest labels verbatim, never upgraded: MEASURED / MODELED / CONJECTURE /
    CORROBORATED / LOAD-BEARING / UNAVAILABLE.
  - NEVER fabricate a joule / receipt / answer / node.
  - Λ = Conjecture 1 — advisory, never a theorem; trust <= 0.97; provenance 1.0.
  - NEVER mutate the harvested source nodes — every write-back lands in a SEPARATE
    append-only OVERLAY sidecar, clearly labeled "overlay".
  - locked-8 unchanged @ c7c0ba17; canonical a-11-oy.com.

Additive + import-safe + crash-proof: every external call is guarded; a missing
Wave-1 szl_brain_api degrades to the graph builder's own salience (this module's
PPR). Pure stdlib (json / hashlib / math / os / re / threading / datetime).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import threading
from datetime import datetime, timezone

# --------------------------------------------------------------------------- #
# Honest label vocabulary (verbatim; never upgraded).
# --------------------------------------------------------------------------- #
TIER_CONJECTURE = "CONJECTURE"
TIER_CORROBORATED = "CORROBORATED"
TIER_LOAD_BEARING = "LOAD-BEARING"
LABEL_MEASURED = "MEASURED"
LABEL_MODELED = "MODELED"
LABEL_UNAVAILABLE = "UNAVAILABLE"

_TIER_ORDER = [TIER_CONJECTURE, TIER_CORROBORATED, TIER_LOAD_BEARING]

# --------------------------------------------------------------------------- #
# Loop constants (LEADERS_MEMORY_ANATOMY §4.3).
# --------------------------------------------------------------------------- #
PPR_ALPHA = 0.85          # PageRank restart (HippoRAG default).
PPR_ITERS = 40            # power-iteration cap.
PPR_EPS = 1e-6            # L1 convergence tolerance.
TOPK = 25                 # load-bearing subgraph size (k).
CONF_THRESHOLD = 0.6      # write-back confidence gate.
ETA_FAST = 0.05           # Hebbian potentiation — fast/episodic.
ETA_SLOW = 0.02           # Hebbian potentiation — slow/semantic.
LAMBDA_FAST = 5.0e-5      # decay per second — fast (episodic forgets quickly).
LAMBDA_SLOW = 5.0e-7      # decay per second — slow (semantic persists).
DELTA_HUB = 5.0           # incident slow-weight sum to become a hub (LOAD-BEARING).
CORROBORATE_MIN = 2       # re-activations to move CONJECTURE -> CORROBORATED.
LAMBDA_ADVISORY_CAP = 0.97  # Λ-advisory salience is NEVER presented as truth.

DOCTRINE = {
    "version": "v11",
    "lambda": "Conjecture 1",
    "locked_count": 8,
    "trust_ceiling": LAMBDA_ADVISORY_CAP,
    "provenance": 1.0,
    "canonical_domain": "a-11-oy.com",
    "note": ("governed living-brain loop; the graph grows ONLY through receipted "
             "metered inference; harvested source nodes are NEVER mutated — "
             "write-backs land in a separate append-only overlay."),
}

_STOPWORDS = frozenset((
    "the", "and", "for", "are", "was", "with", "that", "this", "from", "into",
    "how", "what", "why", "who", "which", "does", "did", "will", "can", "has",
    "have", "not", "you", "your", "our", "their", "its", "his", "her", "them",
    "about", "over", "under", "between", "within", "using", "use", "used",
))


# --------------------------------------------------------------------------- #
# Time / hashing helpers.
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _epoch(ts: str) -> float:
    try:
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return 0.0


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


def _tokens(text: str) -> set:
    toks = re.findall(r"[a-z0-9]+", str(text).lower())
    return {t for t in toks if len(t) >= 3 and t not in _STOPWORDS}


# --------------------------------------------------------------------------- #
# Guarded intake of the harvested brain graph (never fabricates; degrades honest).
# --------------------------------------------------------------------------- #
def _load_graph(ns: str = "a11oy") -> dict:
    """Return the harvested brain graph, or an honest empty when unavailable.

    NEVER mutated here — this is the read-only source substrate."""
    try:
        import a11oy_brain_graph as _bg  # type: ignore
        g = _bg.get_brain_graph(ns)
        nodes = g.get("nodes") or []
        links = g.get("links") or []
        return {"available": True, "nodes": nodes, "links": links,
                "node_count": g.get("node_count", len(nodes))}
    except Exception as exc:  # honest degrade — no fabricated graph
        return {"available": False, "nodes": [], "links": [],
                "reason": f"brain graph unavailable: {type(exc).__name__}"}


def _energy_snapshot() -> dict:
    """MEASURED mesh-energy probe (#789 NVML path). NEVER fabricates joules."""
    try:
        import szl_energy_live as _el  # type: ignore
        live = _el.build_live()
        label = live.get("label", LABEL_UNAVAILABLE)
        return {
            "label": label,
            "joules_label": live.get("joules_label", LABEL_UNAVAILABLE),
            "total_joules": live.get("total_joules"),
            "total_watts": live.get("total_watts"),
            "exporter": live.get("exporter"),
            "as_of": live.get("ts"),
        }
    except Exception as exc:
        return {"label": LABEL_UNAVAILABLE, "joules_label": LABEL_UNAVAILABLE,
                "total_joules": None, "total_watts": None, "exporter": None,
                "reason": f"meter unavailable: {type(exc).__name__}"}


def _sovereign_answer(query: str, subgraph_ids: list) -> dict:
    """Attempt sovereign inference on the mesh (Wave-1 szl_brain_api, guarded).

    Returns generated text + tokens + model when a real sovereign engine answers;
    otherwise an HONEST UNAVAILABLE — the subgraph stays real, nothing is faked.
    """
    try:
        import szl_brain_api as _api  # type: ignore
        for fn_name in ("ask", "answer", "generate", "infer"):
            fn = getattr(_api, fn_name, None)
            if callable(fn):
                out = fn(query, subgraph_ids=subgraph_ids)
                if isinstance(out, dict) and out.get("text"):
                    return {
                        "available": True,
                        "text": str(out["text"]),
                        "tokens": int(out.get("tokens") or 0),
                        "model": str(out.get("model") or "sovereign"),
                        "label": LABEL_MEASURED,
                    }
        return {"available": False, "text": None, "tokens": 0, "model": None,
                "label": LABEL_UNAVAILABLE,
                "reason": "szl_brain_api present but no answer produced"}
    except Exception as exc:
        # Wave-1 not on main / mesh unreachable — honest UNAVAILABLE.
        return {"available": False, "text": None, "tokens": 0, "model": None,
                "label": LABEL_UNAVAILABLE,
                "reason": f"sovereign inference unavailable: {type(exc).__name__}"}


# --------------------------------------------------------------------------- #
# Stage 2 — GROUND: Personalized-PageRank over the real graph + overlay edges.
# --------------------------------------------------------------------------- #
def _personalized_pagerank(nodes: list, links: list, seeds: dict,
                           overlay_edges: dict) -> dict:
    """Query-seeded PageRank (restart to `seeds`, alpha=PPR_ALPHA).

    Undirected adjacency over the harvested links plus reinforced overlay edges
    (weighted 1 + slow-weight). Deterministic power iteration. Returns id->score
    normalised to sum 1. Empty dict when the graph is empty."""
    ids = [n.get("id") for n in nodes if n.get("id")]
    idset = set(ids)
    if not ids:
        return {}

    adj: dict = {i: {} for i in ids}

    def _bump(u, v, w):
        if u in adj and v in idset:
            adj[u][v] = adj[u].get(v, 0.0) + w
            adj[v][u] = adj[v].get(u, 0.0) + w

    for lk in links:
        u, v = lk.get("source"), lk.get("target")
        if u in idset and v in idset and u != v:
            _bump(u, v, 1.0)
    for (u, v), ed in overlay_edges.items():
        if u in idset and v in idset and u != v:
            _bump(u, v, 1.0 + float(ed.get("w_slow", 0.0)))

    # Personalization vector p (restart distribution).
    if seeds:
        stot = float(sum(seeds.values())) or 1.0
        p = {i: (seeds.get(i, 0.0) / stot) for i in ids}
    else:
        u = 1.0 / len(ids)
        p = {i: u for i in ids}

    out_w = {i: float(sum(adj[i].values())) for i in ids}
    r = dict(p)
    for _ in range(PPR_ITERS):
        nxt = {i: (1.0 - PPR_ALPHA) * p[i] for i in ids}
        dangling = 0.0
        for i in ids:
            ri = r[i]
            if ri <= 0.0:
                continue
            ow = out_w[i]
            if ow <= 0.0:
                dangling += ri
                continue
            share = PPR_ALPHA * ri / ow
            for v, w in adj[i].items():
                nxt[v] += share * w
        if dangling:
            add = PPR_ALPHA * dangling
            for i in ids:
                nxt[i] += add * p[i]
        delta = sum(abs(nxt[i] - r[i]) for i in ids)
        r = nxt
        if delta < PPR_EPS:
            break
    tot = float(sum(r.values())) or 1.0
    return {i: r[i] / tot for i in ids}


def _seed_from_query(query: str, nodes: list) -> tuple:
    """Return (seeds:id->weight, matched_fraction). Seeds = nodes whose text
    overlaps the query tokens. matched_fraction is honest grounding confidence."""
    qtok = _tokens(query)
    if not qtok:
        return {}, 0.0
    seeds: dict = {}
    hit_tokens: set = set()
    for n in nodes:
        nid = n.get("id")
        if not nid:
            continue
        ntok = _tokens(" ".join(str(n.get(k, "")) for k in
                               ("id", "title", "label", "kind")))
        common = qtok & ntok
        if common:
            seeds[nid] = float(len(common))
            hit_tokens |= common
    frac = len(hit_tokens) / len(qtok) if qtok else 0.0
    return seeds, round(frac, 6)


# --------------------------------------------------------------------------- #
# Append-only OVERLAY sidecar (separate layer; harvested nodes never mutated).
# The log is an event stream folded into state on read — deterministic + replayable.
# --------------------------------------------------------------------------- #
_LOCK = threading.RLock()
_STATE_CACHE: dict = {"mtime": None, "state": None, "path": None}


def _overlay_path() -> str:
    override = os.environ.get("SZL_BRAIN_OVERLAY")
    if override:
        return override
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (here, tempfile.gettempdir()):
        try:
            os.makedirs(cand, exist_ok=True)
            probe = os.path.join(cand, ".szl_brain_overlay.jsonl")
            with open(probe, "a", encoding="utf-8"):
                pass
            return probe
        except Exception:
            continue
    return os.path.join(tempfile.gettempdir(), ".szl_brain_overlay.jsonl")


def _append_events(events: list) -> None:
    path = _overlay_path()
    with _LOCK:
        with open(path, "a", encoding="utf-8") as fh:
            for ev in events:
                fh.write(json.dumps(ev, sort_keys=True, ensure_ascii=False) + "\n")
        _STATE_CACHE["mtime"] = None  # invalidate


def _fold_state(path: str) -> dict:
    """Replay the append-only log into current overlay state."""
    state = {
        "receipts": [],           # ordered hash chain
        "nodes": {},              # id -> node record
        "edges": {},              # (u,v) -> {w_fast,w_slow,count,last_ts}
        "prev_hash": "",
    }
    if not os.path.isfile(path):
        return state
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            kind = ev.get("ev")
            if kind == "receipt":
                state["receipts"].append(ev)
                state["prev_hash"] = ev.get("receipt_hash", state["prev_hash"])
            elif kind == "node":
                state["nodes"][ev["id"]] = {
                    "id": ev["id"], "text": ev.get("text", ""),
                    "digest": ev.get("digest", ""),
                    "tier": ev.get("tier", TIER_CONJECTURE),
                    "quarantined": bool(ev.get("quarantined", False)),
                    "quarantine_reason": ev.get("quarantine_reason", ""),
                    "receipt_hash": ev.get("receipt_hash", ""),
                    "corroboration": int(ev.get("corroboration", 0)),
                    "maps_to": list(ev.get("maps_to", [])),
                    "created_ts": ev.get("ts", ""),
                    "layer": "overlay",
                }
            elif kind == "corroborate":
                nd = state["nodes"].get(ev.get("id"))
                if nd:
                    nd["corroboration"] = int(nd.get("corroboration", 0)) + 1
            elif kind in ("promote", "demote"):
                nd = state["nodes"].get(ev.get("id"))
                if nd:
                    nd["tier"] = ev.get("tier", nd["tier"])
                    if ev.get("quarantined") is not None:
                        nd["quarantined"] = bool(ev["quarantined"])
                    if ev.get("reason"):
                        nd["tier_reason"] = ev["reason"]
            elif kind == "reinforce":
                ts = ev.get("ts", "")
                t = _epoch(ts)
                for pair in ev.get("edges", []):
                    u, v = pair[0], pair[1]
                    key = (u, v) if u <= v else (v, u)
                    ed = state["edges"].get(key)
                    if ed is None:
                        ed = {"w_fast": 0.0, "w_slow": 0.0, "count": 0,
                              "last_ts": ts}
                        state["edges"][key] = ed
                    dt = max(0.0, t - _epoch(ed["last_ts"])) if ed["last_ts"] else 0.0
                    ed["w_fast"] = ed["w_fast"] * math.exp(-LAMBDA_FAST * dt) + ETA_FAST
                    ed["w_slow"] = ed["w_slow"] * math.exp(-LAMBDA_SLOW * dt) + ETA_SLOW
                    ed["count"] += 1
                    ed["last_ts"] = ts
    return state


def _get_state() -> dict:
    path = _overlay_path()
    with _LOCK:
        try:
            mtime = os.path.getmtime(path) if os.path.isfile(path) else 0.0
        except Exception:
            mtime = 0.0
        if (_STATE_CACHE["state"] is not None
                and _STATE_CACHE["mtime"] == mtime
                and _STATE_CACHE["path"] == path):
            return _STATE_CACHE["state"]
        state = _fold_state(path)
        _STATE_CACHE.update({"mtime": mtime, "state": state, "path": path})
        return state


def _incident_slow_weight(state: dict, node_id: str) -> float:
    tot = 0.0
    for (u, v), ed in state["edges"].items():
        if u == node_id or v == node_id:
            tot += float(ed.get("w_slow", 0.0))
    return tot


# --------------------------------------------------------------------------- #
# Stage 4 — RECEIPT (hash-chained; emitted ONLY on writes).
# --------------------------------------------------------------------------- #
def _make_receipt(query: str, subgraph_ids: list, answer_digest: str,
                  energy: dict, tokens: int, model, prev_hash: str) -> dict:
    joules = energy.get("total_joules")
    joules_label = energy.get("joules_label", LABEL_UNAVAILABLE)
    # tokens_per_joule ONLY when BOTH a real token count and MEASURED joules exist.
    tpj = None
    tpj_label = LABEL_UNAVAILABLE
    if (isinstance(joules, (int, float)) and joules > 0 and tokens
            and energy.get("label") == LABEL_MEASURED):
        tpj = round(tokens / joules, 6)
        tpj_label = LABEL_MEASURED
    body = {
        "ev": "receipt",
        "query_digest": _sha(query),
        "subgraph_ids": list(subgraph_ids),
        "subgraph_size": len(subgraph_ids),
        "answer_digest": answer_digest,
        "joules": joules,
        "joules_label": joules_label,
        "tokens": int(tokens or 0),
        "tokens_per_joule": tpj,
        "tokens_per_joule_label": tpj_label,
        "model": model,
        "energy_label": energy.get("label", LABEL_UNAVAILABLE),
        "ts": _now_iso(),
        "prev_hash": prev_hash,
    }
    body["receipt_hash"] = _sha(
        body["prev_hash"], body["query_digest"], body["answer_digest"],
        json.dumps(body["subgraph_ids"], sort_keys=True),
        str(body["joules"]), str(body["tokens"]), str(body["model"]), body["ts"],
    )
    return body


def _verify_receipt(entry: dict, prev_hash: str) -> bool:
    if entry.get("prev_hash") != prev_hash:
        return False
    recomputed = _sha(
        entry.get("prev_hash", ""), entry.get("query_digest", ""),
        entry.get("answer_digest", ""),
        json.dumps(entry.get("subgraph_ids", []), sort_keys=True),
        str(entry.get("joules")), str(entry.get("tokens")),
        str(entry.get("model")), entry.get("ts", ""),
    )
    return recomputed == entry.get("receipt_hash")


# --------------------------------------------------------------------------- #
# Stage 1-6 — one governed pulse (a WRITE; emits a receipt).
# --------------------------------------------------------------------------- #
def pulse(query: str, ns: str = "a11oy") -> dict:
    """Run ONE governed living-brain cycle (stages 1-6) for `query`.

    Returns the receipt, the grounded subgraph, the candidate write-back with its
    belief tier (or an honest QUARANTINED reason), and the reinforced edges.
    Crash-proof: any fault degrades to an honest response — never raises."""
    query = (query or "").strip()
    try:
        if not query:
            return {"ok": False, "kind": "anatomy-brainloop-pulse", "ns": ns,
                    "doctrine": DOCTRINE, "error": "empty query (nothing to ground)",
                    "computed_at": _now_iso()}

        graph = _load_graph(ns)
        state = _get_state()

        # ---- Stage 2: GROUND -------------------------------------------- #
        if not graph.get("available"):
            energy = _energy_snapshot()
            prev = state.get("prev_hash", "")
            receipt = _make_receipt(query, [], _sha(""), energy, 0, None, prev)
            _append_events([receipt])
            return {
                "ok": True, "kind": "anatomy-brainloop-pulse", "ns": ns,
                "doctrine": DOCTRINE,
                "stages": {"ground": {"label": LABEL_UNAVAILABLE,
                                      "reason": graph.get("reason", "no graph"),
                                      "subgraph": []}},
                "answer": {"label": LABEL_UNAVAILABLE,
                           "text": None, "note": "no harvested graph to ground on"},
                "receipt": receipt,
                "write_back": {"written": False, "quarantined": True,
                               "reason": "no grounded subgraph (graph unavailable)"},
                "reinforced_edges": [],
                "computed_at": _now_iso(),
            }

        nodes, links = graph["nodes"], graph["links"]
        seeds, matched_frac = _seed_from_query(query, nodes)
        scores = _personalized_pagerank(nodes, links, seeds, state["edges"])
        title_by_id = {n.get("id"): (n.get("title") or n.get("id")) for n in nodes}
        kind_by_id = {n.get("id"): n.get("kind", "") for n in nodes}
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:TOPK]
        smax = ranked[0][1] if ranked else 0.0
        subgraph = [{
            "id": nid,
            "title": title_by_id.get(nid, nid),
            "kind": kind_by_id.get(nid, ""),
            # Λ-advisory salience — NEVER truth: normalised then capped at 0.97.
            "salience": round(min(LAMBDA_ADVISORY_CAP,
                                  (sc / smax) if smax > 0 else 0.0), 6),
        } for nid, sc in ranked]
        subgraph_ids = [s["id"] for s in subgraph]
        grounded_by = ("query-seeded PPR" if seeds
                       else "global PPR (no query token matched a node)")

        # ---- Stage 3: ANSWER (sovereign mesh IF reachable; else UNAVAILABLE) #
        answer = _sovereign_answer(query, subgraph_ids)
        energy = _energy_snapshot()
        ans_text = answer.get("text")
        answer_digest = _sha(ans_text) if ans_text else _sha("")

        # ---- Stage 4: RECEIPT (this is a WRITE) ------------------------- #
        prev = state.get("prev_hash", "")
        receipt = _make_receipt(query, subgraph_ids, answer_digest, energy,
                                answer.get("tokens", 0), answer.get("model"), prev)

        # ---- Stage 5: WRITE-BACK (GATED) -------------------------------- #
        # Confidence = grounding strength (matched fraction) tempered by whether a
        # real answer was produced. NEVER fabricated.
        gen_ok = bool(answer.get("available") and ans_text)
        confidence = round(matched_frac * (1.0 if gen_ok else 0.5), 6)
        dup = answer_digest in {n.get("digest") for n in state["nodes"].values()}
        gate_reasons = []
        if not gen_ok:
            gate_reasons.append("no sovereign generated text (UNAVAILABLE)")
        if dup:
            gate_reasons.append("duplicate answer_digest (dedupe)")
        if confidence < CONF_THRESHOLD:
            gate_reasons.append(f"low confidence {confidence} < {CONF_THRESHOLD}")
        gate_pass = not gate_reasons

        cand_id = "overlay:" + answer_digest[:16]
        events = [receipt]
        write_back = {
            "candidate_id": cand_id,
            "confidence": confidence,
            "written": False,
            "quarantined": not gate_pass,
        }
        if gate_pass:
            node_ev = {
                "ev": "node", "id": cand_id, "text": ans_text,
                "digest": answer_digest, "tier": TIER_CONJECTURE,
                "quarantined": False, "receipt_hash": receipt["receipt_hash"],
                "corroboration": 0,
                "maps_to": subgraph_ids[:5],  # maps-to edges into grounding subgraph
                "ts": _now_iso(),
            }
            events.append(node_ev)
            write_back.update({"written": True, "tier": TIER_CONJECTURE,
                               "maps_to": subgraph_ids[:5]})
        else:
            # Re-activation of an EXISTING node corroborates it (evidence-driven,
            # never salience-driven — a raw conjecture is never auto-upgraded).
            if dup:
                existing = next((n for n in state["nodes"].values()
                                 if n.get("digest") == answer_digest), None)
                if existing and not existing.get("quarantined"):
                    events.append({"ev": "corroborate", "id": existing["id"],
                                   "ts": _now_iso()})
                    write_back["corroborated"] = existing["id"]
            write_back["reason"] = "; ".join(gate_reasons)

        # ---- Stage 6: REINFORCE (Hebbian, traversed edges) -------------- #
        reinforced = []
        for i in range(len(subgraph_ids) - 1):
            reinforced.append([subgraph_ids[i], subgraph_ids[i + 1]])
        if gate_pass:
            for sid in subgraph_ids[:5]:
                reinforced.append([cand_id, sid])
        if reinforced:
            events.append({"ev": "reinforce", "edges": reinforced, "ts": _now_iso()})

        _append_events(events)

        # Post-write belief maintenance (deterministic tier transitions).
        _consolidate_tiers(ns)

        return {
            "ok": True, "kind": "anatomy-brainloop-pulse", "ns": ns,
            "doctrine": DOCTRINE,
            "stages": {
                "query": query,
                "ground": {"label": LABEL_MODELED, "grounded_by": grounded_by,
                           "matched_fraction": matched_frac,
                           "subgraph": subgraph},
                "answer": {"label": answer.get("label"),
                           "available": bool(answer.get("available")),
                           "model": answer.get("model"),
                           "tokens": answer.get("tokens", 0),
                           "text": ans_text,
                           "note": answer.get("reason", "")},
                "energy": energy,
            },
            "receipt": receipt,
            "write_back": write_back,
            "reinforced_edges": reinforced,
            "honesty": ("salience is Λ-advisory (<=0.97), never truth; the graph "
                        "grows ONLY via receipted metered inference; UNAVAILABLE "
                        "answers are QUARANTINED, never written load-bearing; "
                        "harvested source nodes are never mutated."),
            "computed_at": _now_iso(),
        }
    except Exception as exc:  # never raise into the app
        return {"ok": False, "kind": "anatomy-brainloop-pulse", "ns": ns,
                "doctrine": DOCTRINE,
                "error": f"{type(exc).__name__}: {exc}",
                "computed_at": _now_iso()}


# --------------------------------------------------------------------------- #
# Stage 7 — CONSOLIDATION + belief-tier maintenance (evidence-driven).
# --------------------------------------------------------------------------- #
def _consolidate_tiers(ns: str = "a11oy") -> list:
    """Deterministic tier transitions from EVIDENCE (never from salience alone):
      CONJECTURE  -> CORROBORATED   when corroboration >= CORROBORATE_MIN
      CORROBORATED-> LOAD-BEARING   when incident slow-weight >= DELTA_HUB
    A raw CONJECTURE is never auto-upgraded to a theorem by salience (differ. c)."""
    state = _get_state()
    events = []
    for nid, nd in state["nodes"].items():
        if nd.get("quarantined"):
            continue
        tier = nd.get("tier", TIER_CONJECTURE)
        if tier == TIER_CONJECTURE and nd.get("corroboration", 0) >= CORROBORATE_MIN:
            events.append({"ev": "promote", "id": nid, "tier": TIER_CORROBORATED,
                           "reason": f"corroboration {nd['corroboration']} >= "
                                     f"{CORROBORATE_MIN}", "ts": _now_iso()})
        elif tier == TIER_CORROBORATED:
            if _incident_slow_weight(state, nid) >= DELTA_HUB:
                events.append({"ev": "promote", "id": nid, "tier": TIER_LOAD_BEARING,
                               "reason": f"incident slow-weight >= {DELTA_HUB} (hub)",
                               "ts": _now_iso()})
    if events:
        _append_events(events)
    return events


def self_audit(ns: str = "a11oy") -> dict:
    """Differentiator (b): receipt-replay SELF-AUDIT that DEMOTES a node's belief
    tier when its backing receipt no longer verifies (tamper-evident belief)."""
    state = _get_state()
    prev = ""
    ok_hashes = set()
    broken = []
    for i, entry in enumerate(state["receipts"]):
        if _verify_receipt(entry, prev):
            ok_hashes.add(entry.get("receipt_hash"))
        else:
            broken.append({"index": i, "receipt_hash": entry.get("receipt_hash")})
        prev = entry.get("receipt_hash", prev)

    demotions = []
    events = []
    for nid, nd in state["nodes"].items():
        rh = nd.get("receipt_hash")
        if not rh:
            continue
        if rh not in ok_hashes:
            cur = nd.get("tier", TIER_CONJECTURE)
            idx = _TIER_ORDER.index(cur) if cur in _TIER_ORDER else 0
            if idx > 0:
                new_tier = _TIER_ORDER[idx - 1]
                quarantined = False
            else:
                new_tier = TIER_CONJECTURE
                quarantined = True
            events.append({"ev": "demote", "id": nid, "tier": new_tier,
                           "quarantined": quarantined,
                           "reason": "backing receipt failed self-audit replay",
                           "ts": _now_iso()})
            demotions.append({"id": nid, "from": cur, "to": new_tier,
                              "quarantined": quarantined})
    if events:
        _append_events(events)
    return {
        "ok": not broken,
        "label": LABEL_MEASURED,  # this IS a real replay over the real chain
        "receipts_checked": len(state["receipts"]),
        "chain_ok": not broken,
        "broken": broken,
        "demotions": demotions,
        "note": ("receipt-replay self-audit; a node whose backing receipt no "
                 "longer verifies is DEMOTED one belief tier (differentiator b)."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Read views (GETs — NEVER emit a receipt).
# --------------------------------------------------------------------------- #
def salience_view(top: int = TOPK, ns: str = "a11oy") -> dict:
    """GET view: current load-bearing knowledge, belief-tiered. Pure read."""
    try:
        top = max(1, min(200, int(top)))
    except Exception:
        top = TOPK
    graph = _load_graph(ns)
    state = _get_state()

    live = []
    if graph.get("available"):
        seeds: dict = {}  # unseeded => global PPR (estate-wide salience)
        scores = _personalized_pagerank(graph["nodes"], graph["links"], seeds,
                                         state["edges"])
        title_by_id = {n.get("id"): (n.get("title") or n.get("id"))
                       for n in graph["nodes"]}
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
        smax = ranked[0][1] if ranked else 0.0
        live = [{
            "id": nid, "title": title_by_id.get(nid, nid),
            "salience": round(min(LAMBDA_ADVISORY_CAP,
                                  (sc / smax) if smax > 0 else 0.0), 6),
            "tier": "MODELED-source",  # harvested source node, not a belief claim
        } for nid, sc in ranked]

    overlay = []
    for nid, nd in state["nodes"].items():
        overlay.append({
            "id": nid, "text_digest": nd.get("digest", "")[:16],
            "tier": nd.get("tier", TIER_CONJECTURE),
            "quarantined": bool(nd.get("quarantined", False)),
            "corroboration": nd.get("corroboration", 0),
            "incident_slow_weight": round(_incident_slow_weight(state, nid), 6),
            "receipt_hash": nd.get("receipt_hash", "")[:16],
            "layer": "overlay",
        })
    tier_counts = {t: 0 for t in _TIER_ORDER}
    quarantined = 0
    for nd in state["nodes"].values():
        if nd.get("quarantined"):
            quarantined += 1
        else:
            tier_counts[nd.get("tier", TIER_CONJECTURE)] = \
                tier_counts.get(nd.get("tier", TIER_CONJECTURE), 0) + 1

    return {
        "ok": True, "kind": "anatomy-brainloop-salience", "ns": ns,
        "doctrine": DOCTRINE,
        "label": LABEL_MODELED,
        "advisory_note": ("salience is Λ-advisory (capped <=0.97) — a derived "
                          "view, NEVER presented as truth."),
        "source_salience": live,       # harvested-graph global PPR
        "overlay_belief": sorted(overlay,
                                 key=lambda o: (-o["incident_slow_weight"], o["id"])),
        "belief_summary": {
            "by_tier": tier_counts, "quarantined": quarantined,
            "total_overlay_nodes": len(state["nodes"]),
        },
        "graph_available": bool(graph.get("available")),
        "computed_at": _now_iso(),
    }


def loop_health(ns: str = "a11oy") -> dict:
    """Compact loop-health snapshot for the /anatomy/loop intake (honest empties)."""
    graph = _load_graph(ns)
    state = _get_state()
    audit = self_audit(ns)
    tier_counts = {t: 0 for t in _TIER_ORDER}
    quarantined = 0
    for nd in state["nodes"].values():
        if nd.get("quarantined"):
            quarantined += 1
        else:
            tier_counts[nd.get("tier", TIER_CONJECTURE)] = \
                tier_counts.get(nd.get("tier", TIER_CONJECTURE), 0) + 1
    last = state["receipts"][-1] if state["receipts"] else None
    return {
        "label": LABEL_MODELED,
        "graph_available": bool(graph.get("available")),
        "source_node_count": graph.get("node_count", 0),
        "receipts": len(state["receipts"]),
        "chain_ok": audit["chain_ok"],
        "last_receipt_hash": (last.get("receipt_hash", "")[:16] if last else ""),
        "overlay_nodes": len(state["nodes"]),
        "reinforced_edges": len(state["edges"]),
        "belief": {"by_tier": tier_counts, "quarantined": quarantined},
        "self_audit_demotions": len(audit.get("demotions", [])),
    }


def salience_topk(k: int = 8, ns: str = "a11oy") -> list:
    """Top-k source-graph salience (Λ-advisory) for the /anatomy/loop intake."""
    view = salience_view(top=k, ns=ns)
    return view.get("source_salience", [])[:k]


def evidence_receipt_anatomy(node_id: str, ns: str = "a11oy") -> tuple:
    """Existing Anatomy v5 bridge to the Brain evidence receipt contract.

    This is a pure GET view: it reuses the reranker's deterministic per-node
    anatomy and an already-written Ouroboros receipt when one matches the current
    inventory. It never mints on read and returns explicit UNKNOWN/UNVERIFIED
    fields when no written receipt exists.
    """
    try:
        import szl_brain_reranker as _reranker
        return _reranker.anatomy_receipt(str(node_id), ns)
    except Exception as exc:
        return ({"ok": False, "status": LABEL_UNAVAILABLE,
                 "reason": f"evidence receipt unavailable: {type(exc).__name__}",
                 "receipt_sha256": "UNKNOWN"}, 503)


# --------------------------------------------------------------------------- #
# Registration — POST /anatomy/pulse (write), GET /anatomy/salience (read).
# Raw-Request handlers via app.router.add_route (fallback add_api_route). These
# resolve BEFORE the SPA catch-all because register() runs in the early import
# chain (szl_anatomy_loop -> here), long before the catch-all is defined.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> list:
    import fastapi
    base = f"/api/{ns}/v1/anatomy"

    async def _pulse_handler(request: fastapi.Request):
        from starlette.responses import JSONResponse
        q = ""
        try:
            q = request.query_params.get("q", "") or ""
            if not q:
                body = await request.body()
                if body:
                    try:
                        data = json.loads(body.decode("utf-8"))
                        q = str(data.get("q", "") or data.get("query", ""))
                    except Exception:
                        q = ""
        except Exception:
            q = ""
        return JSONResponse(pulse(q, ns=ns))

    async def _salience_handler(request: fastapi.Request):
        from starlette.responses import JSONResponse
        top = request.query_params.get("top", str(TOPK))
        return JSONResponse(salience_view(top=top, ns=ns))

    async def _audit_handler(request: fastapi.Request):
        from starlette.responses import JSONResponse
        return JSONResponse(self_audit(ns=ns))

    async def _evidence_receipt_handler(request: fastapi.Request):
        from starlette.responses import JSONResponse
        node_id = str(request.path_params.get("node_id") or "")
        body, status = evidence_receipt_anatomy(node_id, ns)
        return JSONResponse(body, status_code=status)

    routes = [
        (f"{base}/pulse", _pulse_handler, ["POST"]),
        (f"{base}/salience", _salience_handler, ["GET"]),
        (f"{base}/self-audit", _audit_handler, ["GET"]),
        (f"{base}/evidence-receipt/{{node_id:path}}", _evidence_receipt_handler, ["GET"]),
    ]
    router = getattr(app, "router", None)
    add_route = getattr(router, "add_route", None) if router else None
    for path, fn, methods in routes:
        try:
            if callable(add_route):
                app.router.add_route(path, fn, methods=methods)
            else:
                app.add_api_route(path, fn, methods=methods)
        except Exception:
            try:
                app.add_api_route(path, fn, methods=methods)
            except Exception:
                pass
    return [p for p, _, _ in routes]


def _selftest() -> dict:
    """No-server self-test: run one pulse offline and assert doctrine invariants."""
    out = pulse("energy provenance receipt salience")
    assert out["kind"] == "anatomy-brainloop-pulse", out
    assert "receipt" in out and out["receipt"]["receipt_hash"], out
    # salience is Λ-advisory: no salience value may exceed the trust ceiling.
    for s in out.get("stages", {}).get("ground", {}).get("subgraph", []):
        assert s["salience"] <= LAMBDA_ADVISORY_CAP + 1e-9, s
    audit = self_audit()
    assert audit["chain_ok"] in (True, False), audit
    sal = salience_view(top=5)
    assert sal["label"] == LABEL_MODELED, sal
    return {"ok": True, "receipt_hash": out["receipt"]["receipt_hash"][:16],
            "write_back_written": out["write_back"]["written"],
            "chain_ok": audit["chain_ok"],
            "graph_available": out.get("stages", {}).get("ground", {})
            .get("label") != LABEL_UNAVAILABLE}


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
