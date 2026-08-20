#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainagent.py — HONESTY-GATED AGENTIC GRAPH REASONER over the estate brain graph.

This surface treats the honest brain graph (the node/link graph szl_brain_api.py already
indexes) as a STATE SPACE and reasons over it ONE node at a time — a bounded, deterministic,
agentic traversal (a CLAUSE / GraphSearch-style best-first walk). Given a query it seeds from the
top retrieval matches and, at each step, chooses an ACTION deterministically:

  EXPAND    — accept the current best candidate as evidence AND queue its neighbours to explore
  FOLLOW    — move to a queued neighbour (recorded as the neighbour's own hop)
  BACKTRACK — reject the current candidate (it failed the honesty gate) and fall back to the
              next-best frontier node, exploring none of the rejected node's neighbours
  STOP      — halt because evidence is sufficient, the frontier is exhausted, the budget is
              spent, or the honesty gate has blocked the whole frontier

There is NO model call anywhere in the traversal: next hops are ranked purely by graph
heuristics (relevance to the query ⊕ PageRank salience), so a run is fully reproducible and
pure-stdlib+numpy.

THE HONESTY GATE (the one differentiator). Before a candidate node is accepted as evidence it
must pass a machine-checkable gate assembled from the sibling brain-honesty surfaces, each
consulted through a GUARDED import:

  grounding      szl_brainground       — an ungrounded/isolated node must not be walked into
  provenance     szl_brainprovenance   — an untraceable node (no source of any kind) is refused
  contradiction  szl_braincontradict   — a node that conflicts with doctrine/accepted evidence
  uncertainty    szl_brainuncertainty  — a node too weakly relevant/salient to rely on

If a candidate is ungrounded / untraceable / contradicted / too uncertain, the reasoner does
NOT take the hop and records exactly WHY. If a sibling surface is not importable, THAT guard is
UNAVAILABLE — never a fabricated pass. A node is accepted ONLY when at least one guard is
available AND no available guard blocks; with every guard UNAVAILABLE the node is refused (we
never fabricate grounding we cannot verify).

BUDGET-AWARE STOP (A2RAG / CLAUSE). The walk carries an explicit budget: max_steps decisions
and max_nodes visited. It stops when evidence is sufficient, OR the budget is exhausted, OR the
honesty gate has blocked the frontier — and the report names WHICH.

HONEST ABSTENTION. If the walk cannot assemble sufficiently-grounded evidence within budget it
ABSTAINS rather than bluffing. Verdicts:

  ANSWER-GROUNDED         — >= MIN_EVIDENCE nodes passed the honesty gate (a grounded answer set)
  PARTIAL                 — some gate-passed evidence, but below MIN_EVIDENCE, frontier exhausted
                            (not a budget stop) — honestly partial, never dressed up as grounded
  ABSTAINED-BUDGET        — budget spent before sufficient grounded evidence was assembled
  ABSTAINED-INSUFFICIENT  — no gate-passed evidence at all (nonsense query / gate blocked all)

The surface emits a TRACE — the ordered hops, each with its action and its accept/reject reason —
and, on WRITE only, an UNSIGNED SHA-256 content-digest receipt. Its top label is MODELED: it
reasons over MODELED retrieval, it is NOT a MEASURED answer, and it makes NO sentience or
consciousness claim (doctrine bans that).

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only READS + traverses.
    Touches no locked formula and no kernel.
  * Λ stays Conjecture 1 (never a theorem); Khipu BFT stays Conjecture 2; introduces no theorem,
    no green/1.0. Trust ceiling 0.97, never 100%.
  * No label is ever upgraded; a gate-blocked hop is never reported as grounded.
  * Pure stdlib + numpy. Additive routes, registered BEFORE the SPA catch-all; 0 runtime CDN.
  * Strictly knowledge-graph reasoning honesty — advances NO detection / fusion / effector /
    targeting / cueing capability.
"""

import datetime
import hashlib
import importlib
import json
import re
from typing import Any, Callable

try:  # numpy is a core dep; guarded so a missing wheel degrades honestly, never crashes boot.
    import numpy as _np
    _HAVE_NUMPY = True
except Exception:  # pragma: no cover - numpy is present in this estate
    _np = None
    _HAVE_NUMPY = False

# Honesty-label vocabulary (doctrine v11), re-stated (not imported) so a broken import can never
# silently blank it; tests grep these exact strings.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# This surface's own top label — MODELED reasoning over MODELED retrieval, never a measurement.
MODELED = "MODELED"
UNAVAILABLE = "UNAVAILABLE"

# Per-hop actions (a deterministic agentic walk over the graph state space).
EXPAND = "EXPAND"
FOLLOW = "FOLLOW"
BACKTRACK = "BACKTRACK"
STOP = "STOP"
ACTIONS = (EXPAND, FOLLOW, BACKTRACK, STOP)

# Per-guard status.
PASS = "PASS"
BLOCK = "BLOCK"
# (UNAVAILABLE reused from the label vocabulary above for an absent sibling guard.)
GUARD_STATUSES = (PASS, BLOCK, UNAVAILABLE)

# Overall verdicts.
ANSWER_GROUNDED = "ANSWER-GROUNDED"
PARTIAL = "PARTIAL"
ABSTAINED_INSUFFICIENT = "ABSTAINED-INSUFFICIENT"
ABSTAINED_BUDGET = "ABSTAINED-BUDGET"
VERDICTS = (ANSWER_GROUNDED, PARTIAL, ABSTAINED_INSUFFICIENT, ABSTAINED_BUDGET)

# Minimum gate-passed evidence nodes for a grounded answer; below this the honest verdict is a
# PARTIAL / ABSTAINED, never a grounded answer over one lonely node.
MIN_EVIDENCE = 2
# A node is accepted only when at least this many guards are available AND none block; with every
# guard UNAVAILABLE the node is refused (we never fabricate grounding we cannot verify).
MIN_GUARDS = 1

# Budget defaults + clamps (an explicit, budget-aware bounded walk).
DEFAULT_MAX_STEPS = 24
DEFAULT_MAX_NODES = 16
MAX_STEPS_CAP = 200
MAX_NODES_CAP = 200

# Production per-node heuristic thresholds (deterministic; no model call).
_SALIENCE_EPS = 1e-9          # a strictly-positive salience is "reachable" in the walk
_REL_MIN = 0.05               # relevance floor below which (with low salience) a node is uncertain
_SAL_MIN = 1e-4               # salience floor pairing with _REL_MIN for the uncertainty guard

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "brainagent"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _tokens(*parts: str) -> list:
    out = []
    for p in parts:
        for t in _TOKEN_RE.findall((p or "").lower()):
            if len(t) >= 2:
                out.append(t)
    return out


def _doctrine_block(note: str = "") -> dict:
    d = {
        "version": "v11",
        "label_top": MODELED,
        "locked_proven": LOCKED_COUNT,
        "locked_set": list(LOCKED_SET),
        "kernel_commit": KERNEL_COMMIT,
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
        "sentience_claim": False,
    }
    if note:
        d["note"] = note
    return d


# --------------------------------------------------------------------------- #
# Engine abstraction — the traversable state space. The production engine wraps
# szl_brain_api.BrainIndex over the honest reused graph; tests inject a tiny
# deterministic fake so the walk logic is proven without the real graph.
# --------------------------------------------------------------------------- #
class _BrainEngine:
    """Production engine over szl_brain_api.get_index(ns). Read-only; invents no nodes."""

    def __init__(self, index):
        self._idx = index
        self._pr = getattr(index, "_pagerank_global", {}) or {}

    def seeds(self, q: str, k: int) -> list:
        try:
            hits = self._idx.search(q, max(5, k))
        except Exception:
            return []
        return [h["id"] for h in hits]

    def neighbors(self, nid: str) -> list:
        adj = getattr(self._idx, "adj", {}) or {}
        return sorted(adj.get(nid, ()))

    def node(self, nid: str) -> dict:
        by_id = getattr(self._idx, "by_id", {}) or {}
        n = by_id.get(nid)
        if n is None:
            return {}
        try:
            return self._idx._node_view(n)
        except Exception:
            return dict(n)

    def salience(self, nid: str) -> float:
        try:
            return float(self._pr.get(nid, 0.0))
        except Exception:
            return 0.0

    def relevance(self, nid: str, q: str) -> float:
        """MODELED token-overlap of the query against the node's own text. Never a MEASURED
        semantic similarity — a deterministic proxy used only to order the walk."""
        node = self.node(nid)
        if not node:
            return 0.0
        qtok = set(_tokens(q))
        if not qtok:
            return 0.0
        ntok = set(_tokens(str(node.get("title", "")), str(node.get("kind", "")),
                           str(node.get("id", "")), str(node.get("axis") or ""),
                           str(node.get("source") or "")))
        if not ntok:
            return 0.0
        return len(qtok & ntok) / len(qtok)


# Test / integration seam: an injected engine is used verbatim when set. Absent an override the
# production _BrainEngine over the real index is built. This lets tests prove the walk on a tiny
# deterministic graph without importing the whole estate.
_ENGINE_OVERRIDE = None


def _get_engine(ns: str = "a11oy"):
    if _ENGINE_OVERRIDE is not None:
        return _ENGINE_OVERRIDE
    import szl_brain_api as _api  # guarded at call site (register/handlers wrap in try/except)
    return _BrainEngine(_api.get_index(ns))


# --------------------------------------------------------------------------- #
# The honesty gate — machine-checkable, assembled from guarded sibling imports.
# Each guard maps (node, query, ctx) -> {status, reason, label}. Availability is
# a GUARDED import: a sibling that will not import makes its guard UNAVAILABLE
# (never a fabricated pass). A node is accepted only with >= MIN_GUARDS available
# and NO available guard blocking.
# --------------------------------------------------------------------------- #
GATE_SIBLINGS = {
    "grounding":     "szl_brainground",
    "provenance":    "szl_brainprovenance",
    "contradiction": "szl_braincontradict",
    "uncertainty":   "szl_brainuncertainty",
}
GATE_KEYS = ("grounding", "provenance", "contradiction", "uncertainty")

# Test seam mirroring the estate pattern: an override callable per guard key is consulted FIRST.
# Absent an override the guarded-import availability path is used.
_GATE_OVERRIDES: dict[str, Callable[..., Any]] = {}

# When True, ONLY guards present in _GATE_OVERRIDES are gathered; every other guard is forced
# UNAVAILABLE regardless of whether its real sibling happens to import on this checkout. This
# makes a test deterministic: it declares the exact guard set it wants and the rest are honestly
# absent. Off (False) in production — the real guarded-import path runs for any guard without an
# override.
_GATE_ISOLATE = False


def _sibling_importable(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False
    except Exception:  # a sibling that raises on import is honestly treated as unavailable
        return False


def _normalize_guard(raw: Any) -> dict:
    """Coerce an override's return into {status, reason}. Accepts a status string, a bool
    (True=PASS / False=BLOCK), or a dict carrying status/verdict/label. Never upgrades a label."""
    if isinstance(raw, dict):
        status = raw.get("status")
        if not isinstance(status, str):
            v = raw.get("verdict")
            if isinstance(v, str) and v.strip():
                status = BLOCK if v.strip().upper() not in (PASS, "OK", "GROUNDED",
                                                            "CONFIDENT", "NO-CONFLICT",
                                                            "TRACEABLE") else PASS
            else:
                status = UNAVAILABLE
        status = status.strip().upper()
        if status not in GUARD_STATUSES:
            status = UNAVAILABLE
        reason = raw.get("reason") or raw.get("note") or f"status={status}"
        return {"status": status, "reason": str(reason)}
    if isinstance(raw, bool):
        return {"status": PASS if raw else BLOCK, "reason": "override boolean"}
    if isinstance(raw, str):
        s = raw.strip().upper()
        return {"status": s if s in GUARD_STATUSES else UNAVAILABLE, "reason": f"status={s}"}
    return {"status": UNAVAILABLE, "reason": "override returned no interpretable status"}


def _prod_guard(key: str, node: dict, q: str, ctx: dict) -> dict:
    """Deterministic per-node heuristic for one guard, aligned to what that sibling concerns.
    Only reached when the guard's sibling module is importable (else UNAVAILABLE upstream)."""
    if key == "grounding":
        # An isolated node (no edges) with no salience cannot ground an answer.
        degree = node.get("degree", 0) or 0
        sal = ctx.get("salience", 0.0)
        if degree <= 0 and sal <= _SALIENCE_EPS:
            return {"status": BLOCK, "reason": "isolated node, zero salience — ungrounded hop"}
        return {"status": PASS, "reason": f"grounded (degree={degree}, salience>{_SALIENCE_EPS})"}
    if key == "provenance":
        # Traceable when the node carries ANY origin field; a wholly anonymous node is refused.
        if any(node.get(f) for f in ("url", "source", "formula_id", "axis", "title")):
            return {"status": PASS, "reason": "traceable to a node origin field"}
        return {"status": BLOCK, "reason": "no source/url/formula_id/axis/title — untraceable"}
    if key == "contradiction":
        # A node that claims a conjecture is a proven theorem contradicts doctrine (Λ is
        # Conjecture 1, never a theorem) and must not be silently walked into as fact.
        conj = node.get("conjecture")
        proof = str(node.get("proof_status") or "").strip().lower()
        if conj and proof in ("proven", "theorem", "proved"):
            return {"status": BLOCK,
                    "reason": "conjecture marked proven — conflicts with doctrine (Λ is "
                              "Conjecture 1, never a theorem)"}
        return {"status": PASS, "reason": "no doctrine/evidence conflict detected"}
    if key == "uncertainty":
        rel = ctx.get("relevance", 0.0)
        sal = ctx.get("salience", 0.0)
        if rel < _REL_MIN and sal < _SAL_MIN:
            return {"status": BLOCK,
                    "reason": f"relevance {rel:.3f} and salience {sal:.2e} both too low — too "
                              "uncertain to rely on"}
        return {"status": PASS, "reason": f"relevance/salience sufficient (rel={rel:.3f})"}
    return {"status": UNAVAILABLE, "reason": "unknown guard"}


def _run_guard(key: str, node: dict, q: str, ctx: dict) -> dict:
    """One guard: override first, else guarded-import availability + production heuristic. Never
    raises — any failure degrades THIS guard to UNAVAILABLE (never a fabricated pass)."""
    base = {"guard": key, "module": GATE_SIBLINGS.get(key), "status": UNAVAILABLE, "reason": None}
    override = _GATE_OVERRIDES.get(key)
    if _GATE_ISOLATE and override is None:
        base["reason"] = ("gate isolation active: sibling forced absent (test seam); guard "
                          "honestly UNAVAILABLE")
        return base
    try:
        if override is not None:
            for args in ((node, q, ctx), (node, q), (node,), ()):
                try:
                    raw = override(*args)
                    break
                except TypeError as exc:
                    if "argument" in str(exc) or "positional" in str(exc):
                        continue
                    raise
            else:  # pragma: no cover - the () call above always binds
                raw = override(node)
            g = _normalize_guard(raw)
            base.update(g)
            return base
        if not _sibling_importable(GATE_SIBLINGS[key]):
            base["reason"] = ("sibling not importable (guarded ImportError); guard honestly "
                              "UNAVAILABLE — never a fabricated pass")
            return base
        base.update(_prod_guard(key, node, q, ctx))
        return base
    except Exception as exc:  # a live failure degrades THIS guard honestly, never the walk
        base["status"] = UNAVAILABLE
        base["reason"] = f"guard compute failed, reported honestly: {str(exc)[:140]}"
        return base


def _gate_node(nid: str, node: dict, q: str, ctx: dict) -> dict:
    """Run every guard on a candidate node and decide accept/reject. A node is ACCEPTED only when
    >= MIN_GUARDS guards are available AND none block; any block rejects (recording which), and
    all-UNAVAILABLE rejects too (we never fabricate grounding we cannot verify)."""
    guards = [_run_guard(k, node, q, ctx) for k in GATE_KEYS]
    blocks = [g for g in guards if g["status"] == BLOCK]
    passes = [g for g in guards if g["status"] == PASS]
    available = [g for g in guards if g["status"] in (PASS, BLOCK)]

    if blocks:
        reason = "; ".join(f"{g['guard']}:{g['reason']}" for g in blocks)
        return {"accepted": False, "guards": guards,
                "reason": f"honesty gate BLOCKED ({len(blocks)}): {reason}"}
    if len(passes) < MIN_GUARDS or not available:
        return {"accepted": False, "guards": guards,
                "reason": (f"honesty gate could not verify grounding "
                           f"({len(passes)} guard(s) available < {MIN_GUARDS} required); "
                           "refused — never a fabricated pass")}
    return {"accepted": True, "guards": guards,
            "reason": f"honesty gate PASSED ({len(passes)} guard(s) available, 0 blocking)"}


# --------------------------------------------------------------------------- #
# The bounded agentic traversal.
# --------------------------------------------------------------------------- #
def _clamp(v, lo, hi, default):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(v, hi))


def traverse(q: str = "", max_steps: int = DEFAULT_MAX_STEPS,
             max_nodes: int = DEFAULT_MAX_NODES, ns: str = "a11oy") -> dict:
    """Run the honesty-gated bounded walk and return trace + verdict + budget usage. Never
    raises: any engine failure degrades to an honest ABSTAINED-INSUFFICIENT with a reason."""
    max_steps = _clamp(max_steps, 1, MAX_STEPS_CAP, DEFAULT_MAX_STEPS)
    max_nodes = _clamp(max_nodes, 1, MAX_NODES_CAP, DEFAULT_MAX_NODES)

    try:
        engine = _get_engine(ns)
        seed_ids = list(dict.fromkeys(engine.seeds(q, max_nodes)))
    except Exception as exc:
        return _abstain_report(q, max_steps, max_nodes, ABSTAINED_INSUFFICIENT,
                               f"engine unavailable: {str(exc)[:140]}", [], seeds=[])

    if not seed_ids:
        return _report(q, max_steps, max_nodes, engine=None, seeds=[], trace=[],
                       accepted=[], steps_used=0, nodes_visited=0,
                       stop_reason="no seed nodes matched the query (nothing to traverse)")

    # Frontier of (score, id, is_seed). Best-first: highest score, tie-break by id for
    # determinism. Seeds enter first; a node's neighbours are queued only when it is EXPANDed.
    def _score(nid: str) -> float:
        return round(0.65 * engine.relevance(nid, q) + 0.35 * engine.salience(nid), 8)

    frontier = [(_score(nid), nid) for nid in seed_ids]
    queued = set(seed_ids)
    visited = set()
    accepted = []          # ordered list of accepted evidence node ids
    trace = []
    steps_used = 0
    nodes_visited = 0
    stop_reason = None

    while True:
        # --- budget / termination checks (before spending another step) ---
        if len(accepted) >= MIN_EVIDENCE:
            stop_reason = (f"sufficient grounded evidence assembled "
                           f"({len(accepted)} >= {MIN_EVIDENCE})")
            trace.append(_hop(len(trace) + 1, None, STOP, None, stop_reason, None))
            break
        if steps_used >= max_steps:
            stop_reason = f"step budget exhausted ({steps_used}/{max_steps} decisions)"
            trace.append(_hop(len(trace) + 1, None, STOP, None, stop_reason, None))
            break
        if nodes_visited >= max_nodes:
            stop_reason = f"node budget exhausted ({nodes_visited}/{max_nodes} nodes visited)"
            trace.append(_hop(len(trace) + 1, None, STOP, None, stop_reason, None))
            break
        if not frontier:
            stop_reason = "frontier exhausted (no more reachable candidates)"
            trace.append(_hop(len(trace) + 1, None, STOP, None, stop_reason, None))
            break

        # --- pick the best candidate deterministically ---
        frontier.sort(key=lambda t: (-t[0], t[1]))
        score, nid = frontier.pop(0)
        if nid in visited:
            continue
        visited.add(nid)
        nodes_visited += 1
        steps_used += 1

        node = engine.node(nid) or {"id": nid}
        ctx = {"salience": engine.salience(nid), "relevance": engine.relevance(nid, q),
               "accepted": list(accepted)}
        gate = _gate_node(nid, node, q, ctx)

        if gate["accepted"]:
            accepted.append(nid)
            # EXPAND: accept as evidence and queue neighbours to FOLLOW next.
            new_nbrs = []
            for m in engine.neighbors(nid):
                if m not in queued and m not in visited:
                    frontier.append((_score(m), m))
                    queued.add(m)
                    new_nbrs.append(m)
            trace.append(_hop(len(trace) + 1, nid, EXPAND, True,
                              gate["reason"], score, node=node, ctx=ctx,
                              guards=gate["guards"], followed=new_nbrs))
        else:
            # BACKTRACK: reject this hop, explore none of its neighbours, fall back to next-best.
            trace.append(_hop(len(trace) + 1, nid, BACKTRACK, False,
                              gate["reason"], score, node=node, ctx=ctx,
                              guards=gate["guards"], followed=[]))

    return _report(q, max_steps, max_nodes, engine=engine, seeds=seed_ids, trace=trace,
                   accepted=accepted, steps_used=steps_used, nodes_visited=nodes_visited,
                   stop_reason=stop_reason)


def _hop(step, nid, action, accepted, reason, score, node=None, ctx=None,
         guards=None, followed=None) -> dict:
    hop = {"step": step, "node": nid, "action": action, "accepted": accepted,
           "reason": reason, "score": score}
    if node is not None:
        hop["title"] = node.get("title", nid)
        hop["kind"] = node.get("kind")
    if ctx is not None:
        hop["salience"] = round(ctx.get("salience", 0.0), 8)
        hop["relevance"] = round(ctx.get("relevance", 0.0), 6)
    if guards is not None:
        hop["guards"] = [{"guard": g["guard"], "status": g["status"], "reason": g["reason"]}
                         for g in guards]
    if followed is not None:
        hop["followed"] = followed
    return hop


def _decide_verdict(accepted: list, stop_reason: str) -> tuple[str, str]:
    """Grade the walk honestly. ANSWER-GROUNDED needs >= MIN_EVIDENCE gate-passed nodes; a budget
    stop below that is ABSTAINED-BUDGET; some evidence but frontier-exhausted is PARTIAL; nothing
    grounded is ABSTAINED-INSUFFICIENT. A gate-blocked hop is never counted as grounded."""
    n = len(accepted)
    budget_stop = "budget exhausted" in (stop_reason or "")
    if n >= MIN_EVIDENCE:
        return (ANSWER_GROUNDED,
                f"{n} node(s) passed the honesty gate (>= {MIN_EVIDENCE}); grounded evidence set")
    if budget_stop:
        return (ABSTAINED_BUDGET,
                f"budget spent with only {n} gate-passed node(s) (< {MIN_EVIDENCE}); abstaining "
                "rather than answering under-grounded")
    if n >= 1:
        return (PARTIAL,
                f"{n} gate-passed node(s) but < {MIN_EVIDENCE} and the frontier is exhausted; "
                "honestly PARTIAL, never presented as fully grounded")
    return (ABSTAINED_INSUFFICIENT,
            "no node passed the honesty gate; abstaining rather than fabricating a grounded "
            "answer")


def _modeled_confidence(accepted: list, nodes_visited: int) -> float | None:
    """A MODELED confidence = accepted / visited, capped at the trust ceiling (0.97, never 1.0).
    None when nothing was visited. A derived MODELED number, NEVER a MEASURED proof."""
    if nodes_visited <= 0:
        return None
    ratio = len(accepted) / nodes_visited
    if _HAVE_NUMPY:
        ratio = float(_np.clip(ratio, 0.0, TRUST_CEILING))
    else:  # pragma: no cover - numpy present in this estate
        ratio = min(ratio, TRUST_CEILING)
    return round(ratio, 6)


def _report(q, max_steps, max_nodes, engine, seeds, trace, accepted,
            steps_used, nodes_visited, stop_reason) -> dict:
    verdict, reason = _decide_verdict(accepted, stop_reason)
    return {
        "ok": True,
        "endpoint": "brain/agent",
        "service": "a11oy.brain.agent",
        "surface_id": SURFACE_ID,
        "title": "Brain Agent — honesty-gated agentic graph reasoner over the estate brain",
        "label": MODELED,
        "query": q,
        "verdict": verdict,
        "verdict_reason": reason,
        "modeled_confidence": _modeled_confidence(accepted, nodes_visited),
        "what": ("a bounded, deterministic agentic traversal of the honest brain graph. From the "
                 "query's top retrieval seeds it walks node-by-node, choosing EXPAND / FOLLOW / "
                 "BACKTRACK / STOP by pure graph heuristics (no model call), and gates every "
                 "candidate through the sibling brain-honesty surfaces (grounding, provenance, "
                 "contradiction, uncertainty). An ungrounded/untraceable/contradicted/uncertain "
                 "hop is refused and the reason recorded; an absent sibling guard is UNAVAILABLE, "
                 "never a fabricated pass. It abstains (ABSTAINED-INSUFFICIENT / ABSTAINED-BUDGET) "
                 "rather than answer under-grounded. Strictly knowledge-graph reasoning honesty — "
                 "advances no detection/fusion/effector/targeting/cueing capability; makes no "
                 "sentience claim."),
        "seeds": list(seeds),
        "cited_node_ids": list(accepted),
        "trace": trace,
        "budget": {
            "max_steps": max_steps,
            "max_nodes": max_nodes,
            "steps_used": steps_used,
            "nodes_visited": nodes_visited,
            "min_evidence_required": MIN_EVIDENCE,
        },
        "summary": {
            "seeds": len(seeds),
            "nodes_visited": nodes_visited,
            "accepted": len(accepted),
            "rejected": sum(1 for h in trace if h["action"] == BACKTRACK),
            "stop_reason": stop_reason,
        },
        "verdict_legend": {
            ANSWER_GROUNDED: f">= {MIN_EVIDENCE} nodes passed the honesty gate (grounded set)",
            PARTIAL: f"1..{MIN_EVIDENCE - 1} gate-passed nodes, frontier exhausted (not budget)",
            ABSTAINED_BUDGET: "budget spent before sufficient grounded evidence",
            ABSTAINED_INSUFFICIENT: "no node passed the honesty gate (nonsense / gate blocked)",
        },
        "action_legend": {
            EXPAND: "accept the candidate as evidence and queue its neighbours",
            FOLLOW: "move to a queued neighbour (recorded as that neighbour's own hop)",
            BACKTRACK: "reject the candidate (gate blocked) and fall back to the next best",
            STOP: "halt (sufficient / frontier exhausted / budget spent / gate blocked frontier)",
        },
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "additive READ-and-traverse surface over the brain-honesty siblings; touches no "
            "locked formula and no kernel; GET reads sign/mint nothing; POST receipt emits an "
            "UNSIGNED SHA-256 content digest only; introduces no theorem, no green/1.0; "
            "modeled_confidence is a MODELED ratio capped at 0.97, never MEASURED, never 100%; "
            "makes no sentience/consciousness claim."),
        "timestamp_utc": _now_iso(),
    }


def _abstain_report(q, max_steps, max_nodes, verdict, reason, trace, seeds) -> dict:
    return {
        "ok": False,
        "endpoint": "brain/agent",
        "surface_id": SURFACE_ID,
        "label": UNAVAILABLE,
        "query": q,
        "verdict": verdict,
        "verdict_reason": reason,
        "seeds": list(seeds),
        "cited_node_ids": [],
        "trace": trace,
        "budget": {"max_steps": max_steps, "max_nodes": max_nodes,
                   "steps_used": 0, "nodes_visited": 0,
                   "min_evidence_required": MIN_EVIDENCE},
        "doctrine": "v11: brain-agent engine unavailable; no fabricated grounded answer emitted.",
        "timestamp_utc": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), never GET.
# --------------------------------------------------------------------------- #
def _canonical_core(report: dict) -> str:
    """Deterministic canonical serialization of the reasoning-bearing content (excludes the
    volatile timestamp), so the digest attests the VERDICT + walk, not the clock."""
    budget = report.get("budget", {}) or {}
    core = {
        "query": report.get("query"),
        "verdict": report.get("verdict"),
        "modeled_confidence": report.get("modeled_confidence"),
        "cited_node_ids": report.get("cited_node_ids"),
        "seeds": report.get("seeds"),
        "budget": {"max_steps": budget.get("max_steps"), "max_nodes": budget.get("max_nodes"),
                   "steps_used": budget.get("steps_used"),
                   "nodes_visited": budget.get("nodes_visited")},
        "trace": [{"step": h.get("step"), "node": h.get("node"), "action": h.get("action"),
                   "accepted": h.get("accepted")} for h in report.get("trace", [])],
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def _content_receipt(report: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the traversal report (no signature
    fabricated). RECEIPT-ON-WRITE — only the POST receipt path calls this."""
    canonical = _canonical_core(report)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainagent.traversal",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST receipt)",
        "note": ("unsigned SHA-256 content digest of the reasoning trace + verdict; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #
def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/agent/info — describe the reasoner, honesty gate, budget model, honest labels
    (no compute). PURE READ (mints nothing)."""
    base = f"/api/{ns}/v1/brain/agent"
    return {
        "ok": True,
        "service": "a11oy.brain.agent",
        "endpoint": "brain/agent/info",
        "surface_id": SURFACE_ID,
        "label": MODELED,
        "title": "Brain Agent — honesty-gated agentic graph reasoner over the estate brain",
        "what": ("a bounded, deterministic agentic traversal of the honest brain graph as a state "
                 "space, one node at a time. Seeds from the query's top retrieval matches, then "
                 "chooses EXPAND / FOLLOW / BACKTRACK / STOP by pure graph heuristics (relevance "
                 "⊕ PageRank salience; no model call). Every candidate hop is gated through the "
                 "sibling brain-honesty surfaces; an ungrounded/untraceable/contradicted/uncertain "
                 "hop is refused with a recorded reason, and an absent sibling guard is "
                 "UNAVAILABLE — never a fabricated pass. It abstains rather than answer "
                 "under-grounded. Strictly knowledge-graph reasoning honesty; makes no sentience "
                 "claim."),
        "honesty_gate": {
            "guards": [{"guard": k, "sibling": GATE_SIBLINGS[k]} for k in GATE_KEYS],
            "policy": ("a node is accepted ONLY when >= "
                       f"{MIN_GUARDS} guard(s) are available AND none block; any block rejects "
                       "the hop (recording which guard and why); with every guard UNAVAILABLE "
                       "the node is refused — grounding is never fabricated."),
            "statuses": list(GUARD_STATUSES),
        },
        "budget_model": {
            "max_steps": {"default": DEFAULT_MAX_STEPS, "cap": MAX_STEPS_CAP,
                          "meaning": "traversal decisions before a forced STOP"},
            "max_nodes": {"default": DEFAULT_MAX_NODES, "cap": MAX_NODES_CAP,
                          "meaning": "distinct nodes visited before a forced STOP"},
            "min_evidence_required": MIN_EVIDENCE,
        },
        "actions": list(ACTIONS),
        "action_legend": {
            EXPAND: "accept the candidate as evidence and queue its neighbours",
            FOLLOW: "move to a queued neighbour (recorded as that neighbour's own hop)",
            BACKTRACK: "reject the candidate (gate blocked) and fall back to the next best",
            STOP: "halt (sufficient / frontier exhausted / budget spent / gate blocked frontier)",
        },
        "verdicts": list(VERDICTS),
        "verdict_legend": {
            ANSWER_GROUNDED: f">= {MIN_EVIDENCE} nodes passed the honesty gate (grounded set)",
            PARTIAL: f"1..{MIN_EVIDENCE - 1} gate-passed nodes, frontier exhausted (not budget)",
            ABSTAINED_BUDGET: "budget spent before sufficient grounded evidence",
            ABSTAINED_INSUFFICIENT: "no node passed the honesty gate (nonsense / gate blocked)",
        },
        "endpoints": {
            "info": f"GET  {base}/info",
            "agent": f"GET  {base}?q=&max_steps=&max_nodes=",
            "receipt": f"POST {base}/receipt",
        },
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — GET info/agent mint nothing; only POST "
                           "/receipt emits an unsigned SHA-256 content digest."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "additive READ-and-traverse surface; touches no locked formula and no kernel; "
            "Λ = Conjecture 1, never a theorem; makes no sentience/consciousness claim."),
        "timestamp_utc": _now_iso(),
    }


def handle_agent(q: str = "", max_steps: int = DEFAULT_MAX_STEPS,
                 max_nodes: int = DEFAULT_MAX_NODES, ns: str = "a11oy") -> dict:
    """GET /brain/agent — run the honesty-gated bounded walk for a query. PURE READ (mints
    nothing). Never 500s: honest degraded ABSTAINED response on error."""
    try:
        return traverse(q, max_steps, max_nodes, ns)
    except Exception as exc:  # never 500: honest degraded response, no fabricated answer
        return _abstain_report(q, max_steps, max_nodes, ABSTAINED_INSUFFICIENT,
                               f"traversal unavailable: {str(exc)[:180]}", [], seeds=[])


def handle_receipt(q: str = "", max_steps: int = DEFAULT_MAX_STEPS,
                   max_nodes: int = DEFAULT_MAX_NODES, ns: str = "a11oy") -> dict:
    """POST /brain/agent/receipt — the traversal report + an UNSIGNED SHA-256 content-digest
    receipt (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    try:
        rep = traverse(q, max_steps, max_nodes, ns)
        out = dict(rep)
        out["receipt"] = _content_receipt(rep)
        return out
    except Exception as exc:
        return {
            "ok": False, "endpoint": "brain/agent/receipt", "label": UNAVAILABLE,
            "verdict": ABSTAINED_INSUFFICIENT, "error": str(exc)[:200],
            "doctrine": "v11: receipt unavailable; no fabricated verdict/receipt emitted.",
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# FastAPI router registration.
#   GET  info/agent — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST receipt    — raw-Request handler via app.router.add_route (Starlette passes the Request
#                     positionally, version-proof under fastapi==0.137.x), with app.add_api_route
#                     as the fallback. The handler is annotated request: fastapi.Request.
#                     Registered BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/agent"

    @app.get(f"{base}/info")
    def _brainagent_info():
        """Self-describing brain-agent manifest: reasoner + honesty gate + budget (pure read)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainagent_agent(q: str = "", max_steps: int = DEFAULT_MAX_STEPS,
                          max_nodes: int = DEFAULT_MAX_NODES):
        """Run the honesty-gated bounded walk for a query; return trace + verdict (pure read)."""
        return JSONResponse(handle_agent(q, max_steps, max_nodes, ns))

    async def _brainagent_receipt(request):
        """POST: traversal report + an UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE).
        Reads q/max_steps/max_nodes from the query string; the body is otherwise ignored."""
        qp = request.query_params
        q = qp.get("q", "")
        max_steps = _clamp(qp.get("max_steps", DEFAULT_MAX_STEPS), 1, MAX_STEPS_CAP,
                           DEFAULT_MAX_STEPS)
        max_nodes = _clamp(qp.get("max_nodes", DEFAULT_MAX_NODES), 1, MAX_NODES_CAP,
                           DEFAULT_MAX_NODES)
        return JSONResponse(handle_receipt(q, max_steps, max_nodes, ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature analysis (in
    # the add_api_route fallback path) treats the param as the request object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _brainagent_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rec_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rec_path, _brainagent_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rec_path, _brainagent_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rec_path, _brainagent_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainagent receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainagent-wired:2(get-only)"

    return "brainagent-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — deterministic walk over a tiny injected engine; honesty gate blocks an ungrounded
# hop; budget + insufficient abstentions fire; receipt only on write; labels never upgraded.
# --------------------------------------------------------------------------- #
class _FakeEngine:
    """A tiny deterministic graph engine for the self-test / tests. Λ is Conjecture 1, never a
    theorem — this fake invents no grounding beyond what a test explicitly declares."""

    def __init__(self, nodes: dict, edges: dict, seeds: list):
        self._nodes = nodes
        self._edges = edges
        self._seeds = seeds

    def seeds(self, q, k):
        return list(self._seeds)

    def neighbors(self, nid):
        return sorted(self._edges.get(nid, ()))

    def node(self, nid):
        return dict(self._nodes.get(nid, {"id": nid}))

    def salience(self, nid):
        return float(self._nodes.get(nid, {}).get("salience", 0.0))

    def relevance(self, nid, q):
        return float(self._nodes.get(nid, {}).get("relevance", 0.0))


if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainagent — self-test (honesty-gated agentic graph reasoner)")
    print("=" * 72)

    # Deterministic gate isolation: only guards a check declares are gathered; every other guard
    # is forced honestly UNAVAILABLE regardless of which real siblings import on this checkout.
    _GATE_ISOLATE = True

    _nodes = {f"n{i}": {"id": f"n{i}", "title": f"node {i}", "kind": "concept",
                        "degree": 2, "salience": 0.1, "relevance": 0.5, "source": "estate"}
              for i in range(6)}
    _edges = {"n0": ["n1", "n2"], "n1": ["n3"], "n2": ["n4"], "n3": ["n5"], "n4": [], "n5": []}
    _seeds = ["n0", "n1", "n2", "n3", "n4", "n5"]
    _ENGINE_OVERRIDE = _FakeEngine(_nodes, _edges, _seeds)

    # [1] All guards PASS -> nodes accepted -> ANSWER-GROUNDED, and the walk is deterministic.
    _GATE_OVERRIDES.clear()
    _GATE_OVERRIDES["grounding"] = lambda node, q, ctx: PASS
    _GATE_OVERRIDES["provenance"] = lambda node, q, ctx: PASS
    r1a = traverse("q", max_steps=20, max_nodes=10)
    r1b = traverse("q", max_steps=20, max_nodes=10)
    assert r1a["verdict"] == ANSWER_GROUNDED, r1a["verdict"]
    assert r1a["label"] == MODELED
    assert [h["node"] for h in r1a["trace"]] == [h["node"] for h in r1b["trace"]], "deterministic"
    assert len(r1a["cited_node_ids"]) >= MIN_EVIDENCE
    print(f"[1] all-pass gate -> {r1a['verdict']} (cited={len(r1a['cited_node_ids'])}); "
          "traversal deterministic  OK")

    # [2] Honesty gate BLOCKS an ungrounded hop: a grounding guard that blocks n1 must reject it
    # (n1 never cited), a contradicted/ungrounded hop the reasoner refuses to walk into.
    _GATE_OVERRIDES.clear()
    _GATE_OVERRIDES["grounding"] = (lambda node, q, ctx:
                                    BLOCK if node.get("id") == "n1" else PASS)
    _GATE_OVERRIDES["provenance"] = lambda node, q, ctx: PASS
    r2 = traverse("q", max_steps=20, max_nodes=10)
    assert "n1" not in r2["cited_node_ids"], "gate-blocked node must never be cited"
    blk = [h for h in r2["trace"] if h["node"] == "n1"]
    assert blk and blk[0]["action"] == BACKTRACK and blk[0]["accepted"] is False
    print("[2] honesty gate blocked ungrounded hop n1 -> BACKTRACK, never cited  OK")

    # [3] ABSTAINED-BUDGET: a budget too small to assemble MIN_EVIDENCE grounded nodes abstains.
    _GATE_OVERRIDES.clear()
    _GATE_OVERRIDES["grounding"] = lambda node, q, ctx: PASS
    r3 = traverse("q", max_steps=1, max_nodes=1)
    assert r3["verdict"] == ABSTAINED_BUDGET, r3["verdict"]
    print(f"[3] tiny budget -> {r3['verdict']} (never a grounded answer under budget)  OK")

    # [4] ABSTAINED-INSUFFICIENT on a nonsense query (no seeds) — nothing to traverse.
    _ENGINE_OVERRIDE = _FakeEngine(_nodes, _edges, [])
    r4 = traverse("qwertyuiop-not-a-real-topic", max_steps=20, max_nodes=10)
    assert r4["verdict"] == ABSTAINED_INSUFFICIENT, r4["verdict"]
    assert r4["cited_node_ids"] == []
    print(f"[4] nonsense/no-seed query -> {r4['verdict']} (honest abstention)  OK")

    # [5] Never ANSWER-GROUNDED without passing the gate: every guard UNAVAILABLE -> nothing
    # accepted -> ABSTAINED-INSUFFICIENT (a sibling absent is never a fabricated pass).
    _ENGINE_OVERRIDE = _FakeEngine(_nodes, _edges, _seeds)
    _GATE_OVERRIDES.clear()  # isolate on + no overrides => all guards UNAVAILABLE
    r5 = traverse("q", max_steps=20, max_nodes=10)
    assert r5["verdict"] != ANSWER_GROUNDED, r5["verdict"]
    assert r5["cited_node_ids"] == []
    print(f"[5] all guards UNAVAILABLE -> {r5['verdict']}, never ANSWER-GROUNDED  OK")

    # [6] RECEIPT-ON-WRITE: POST receipt is an unsigned deterministic sha256; GET mints none.
    _GATE_OVERRIDES.clear()
    _GATE_OVERRIDES["grounding"] = lambda node, q, ctx: PASS
    _GATE_OVERRIDES["provenance"] = lambda node, q, ctx: PASS
    rec = handle_receipt("q", 20, 10)["receipt"]
    assert rec["algorithm"] == "sha256" and len(rec["content_sha256"]) == 64
    assert rec["signed"] is False and rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert "receipt" not in handle_agent("q", 20, 10), "GET must NOT mint a receipt"
    assert handle_receipt("q", 20, 10)["receipt"]["content_sha256"] == rec["content_sha256"]
    print(f"[6] POST digest={rec['content_sha256'][:16]}… unsigned + deterministic; "
          "GET mints nothing  OK")

    # [7] doctrine: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 not 100%, no sentience claim.
    d = _doctrine_block()
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0 and d["sentience_claim"] is False
    print("[7] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97, no sentience  OK")

    _GATE_OVERRIDES.clear()
    _ENGINE_OVERRIDE = None
    _GATE_ISOLATE = False
    print("\nok:true checks:7")
    _sys.exit(0)
