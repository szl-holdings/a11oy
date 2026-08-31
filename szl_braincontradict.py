#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_braincontradict.py — CONTRADICTION DETECTOR across the honest knowledge graph.

A governed frontier surface that surfaces potential CONTRADICTIONS between grounded
nodes HONESTLY — it PRESENTS the conflict and refuses to RESOLVE it. For a query it
retrieves the relevant subgraph from the same honest brain graph the rest of the
estate reads (via szl_brain_api.get_index — invents no nodes, harvests nothing) and
looks for pairs of topically-related grounded claims that DISAGREE, using only
simple, transparent, deterministic lexical/structural heuristics:

  * NEGATION polarity   — two claims that share a subject but where one carries a
                          negation marker (no / not / never / cannot / fails / lacks
                          / without / absence) the other does not.
  * ANTONYM opposition  — two claims that share a subject but carry opposing terms
                          from a small, transparent antonym table (secure/insecure,
                          safe/unsafe, enabled/disabled, pass/fail, valid/invalid …).
  * NUMERIC conflict    — two claims about the same subject that assert materially
                          different numbers for the same quantity.

There is NO black-box model in the detection path: every flag is explainable by the
exact tokens that triggered it. Confidence is an HONEST heuristic strength, never a
proof, and never 1.0.

CRITICAL HONESTY — PRESENT, NEVER RESOLVE. Every reported conflict carries BOTH
sides verbatim, the reason it was flagged, and an explicit ``adjudication:
human-required`` with ``resolution: null``. This surface NEVER picks a winner, NEVER
fabricates a resolution, and NEVER hides one side. A truthful "these two grounded
claims disagree; a human must adjudicate" beats a fake reconciliation.

VERDICT (honest, over the retrieved subgraph):
  NO-CONFLICT       — no candidate disagreeing pairs found.
  POSSIBLE-CONFLICT — candidate pair(s) found, all below the flag threshold (weak).
  CONFLICT-FLAGGED  — at least one candidate pair at/above the flag threshold.

ENDPOINTS (additive, before the SPA catch-all; pure reads sign/mint nothing):
  GET  /api/<ns>/v1/brain/contradict/info      static describe + method + honest labels
  GET  /api/<ns>/v1/brain/contradict?q=&k=     run detection, return pairs + reasons +
                                               verdict (label MODELED)
  POST /api/<ns>/v1/brain/contradict/receipt   UNSIGNED SHA-256 content-digest
                                               receipt-on-write (GET mints nothing)

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; touches no locked
    formula and no kernel. Λ stays Conjecture 1; Khipu BFT stays Conjecture 2.
  * Detection is MODELED (a deterministic lexical/structural heuristic), NEVER
    MEASURED. Confidence is capped below 1.0; trust ceiling 0.97, never 100%.
  * RECEIPT-ON-WRITE, NOT ON-READ: only POST /receipt emits an unsigned SHA-256
    content digest; the GET reads mint nothing. No signature is fabricated.
  * Pure stdlib + numpy. 0 runtime CDN.
"""

import datetime
import hashlib
import json
import re
from typing import Any

# Honest Doctrine v11 labels (verbatim — never upgraded).
MODELED = "MODELED"
UNAVAILABLE = "UNAVAILABLE"

# Verdicts.
NO_CONFLICT = "NO-CONFLICT"
POSSIBLE_CONFLICT = "POSSIBLE-CONFLICT"
CONFLICT_FLAGGED = "CONFLICT-FLAGGED"

# Doctrine constants (never inflate).
TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "braincontradict"

# Honest heuristic confidence is capped well below 1.0 — a lexical flag is never a proof.
CONF_CAP = 0.9
# At/above this an honest candidate is strong enough to FLAG; below it is only POSSIBLE.
FLAG_THRESHOLD = 0.66
# Two numbers for the same subject disagree when they differ by more than this fraction.
NUMERIC_REL_TOL = 0.05

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

# Negation markers — presence of one on exactly one side of a shared-subject pair flags
# a polarity disagreement. Transparent and enumerable (no learned weights).
_NEGATIONS = {
    "no", "not", "never", "cannot", "cant", "wont", "without", "absence",
    "absent", "fails", "fail", "failed", "lacks", "lack", "lacking", "none",
    "neither", "nor", "excludes", "unavailable", "disproven", "unproven",
}

# Small, transparent antonym table. Each frozenset is a pair of mutually-opposing
# terms; a shared-subject pair carrying the two members disagrees. Enumerable by design.
_ANTONYM_PAIRS = [
    frozenset({"secure", "insecure"}),
    frozenset({"safe", "unsafe"}),
    frozenset({"enabled", "disabled"}),
    frozenset({"enable", "disable"}),
    frozenset({"pass", "fail"}),
    frozenset({"passed", "failed"}),
    frozenset({"valid", "invalid"}),
    frozenset({"stable", "unstable"}),
    frozenset({"present", "absent"}),
    frozenset({"proven", "unproven"}),
    frozenset({"verified", "unverified"}),
    frozenset({"signed", "unsigned"}),
    frozenset({"allow", "deny"}),
    frozenset({"allowed", "denied"}),
    frozenset({"increase", "decrease"}),
    frozenset({"increases", "decreases"}),
    frozenset({"rising", "falling"}),
    frozenset({"up", "down"}),
    frozenset({"high", "low"}),
    frozenset({"open", "closed"}),
    frozenset({"on", "off"}),
    frozenset({"true", "false"}),
    frozenset({"success", "failure"}),
    frozenset({"gain", "loss"}),
    frozenset({"positive", "negative"}),
    frozenset({"complete", "incomplete"}),
    frozenset({"reachable", "unreachable"}),
]

# Tokens that carry polarity/opposition themselves — excluded from the "subject" a pair
# must share, so opposition terms never masquerade as the shared subject.
_POLARITY_TOKENS = set(_NEGATIONS)
for _p in _ANTONYM_PAIRS:
    _POLARITY_TOKENS |= set(_p)

# Very common words that are not the subject of a claim.
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "is", "are", "was", "were", "be", "been",
    "and", "or", "for", "with", "on", "at", "by", "as", "it", "its", "this", "that",
    "these", "those", "from", "into", "then", "than", "but", "if", "so", "we", "our",
    "their", "they", "he", "she", "his", "her", "which", "who", "whom", "will",
    "can", "may", "has", "have", "had", "do", "does", "did", "via", "per",
}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _tokens(text: str) -> list:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t]


def _subject_tokens(tokens: list) -> set:
    """Meaningful subject tokens: drop stopwords, polarity/antonym tokens, bare numbers."""
    out = set()
    for t in tokens:
        if len(t) < 3:
            continue
        if t in _STOPWORDS or t in _POLARITY_TOKENS:
            continue
        if _NUM_RE.fullmatch(t):
            continue
        out.add(t)
    return out


def _node_text(n: dict) -> str:
    """The claim text for a node — title + optional summary/label, read verbatim."""
    parts = [n.get("title"), n.get("summary"), n.get("claim"), n.get("node_label")]
    return " ".join(str(p) for p in parts if p)


def _numbers(tokens_text: str) -> list:
    return [float(x) for x in _NUM_RE.findall(tokens_text or "")]


def _numeric_conflict(a_text: str, b_text: str) -> tuple:
    """Return (conflict: bool, detail: str|None). Materially-different numbers for a
    shared-subject pair disagree; identical (or near-identical) numbers do not."""
    na = _numbers(a_text)
    nb = _numbers(b_text)
    if not na or not nb:
        return False, None
    for x in na:
        for y in nb:
            hi = max(abs(x), abs(y), 1e-9)
            if abs(x - y) / hi > NUMERIC_REL_TOL:
                return True, f"{x:g} vs {y:g}"
    return False, None


def _clip(v: float) -> float:
    return max(0.0, min(CONF_CAP, v))


def _pair_signal(a: dict, b: dict, linked: bool) -> dict | None:
    """Detect a potential contradiction between two nodes. Pure, deterministic,
    explainable. Returns a conflict record or None. NEVER resolves — it only reports."""
    ta = _tokens(_node_text(a))
    tb = _tokens(_node_text(b))
    sa = _subject_tokens(ta)
    sb = _subject_tokens(tb)
    shared = sa & sb
    same_comm = (a.get("community") is not None
                 and a.get("community") == b.get("community"))
    # A pair must be topically related to be comparable at all: shared subject token,
    # OR (same community AND directly linked). Otherwise it is not the "same claim".
    if not shared and not (same_comm and linked):
        return None
    if not shared:
        return None  # need a concrete shared subject to name what disagrees

    set_a, set_b = set(ta), set(tb)
    neg_a = bool(set_a & _NEGATIONS)
    neg_b = bool(set_b & _NEGATIONS)

    signal = None
    reason = None
    base = 0.0

    # ANTONYM opposition (checked first: a concrete opposing term is the clearest signal).
    for pair in _ANTONYM_PAIRS:
        pa = set_a & pair
        pb = set_b & pair
        if pa and pb and pa != pb:
            signal = "antonym"
            x, y = sorted(pair)
            reason = (f"shared subject {sorted(shared)[:3]} but opposing terms "
                      f"'{x}' vs '{y}'")
            base = 0.65
            break

    # NUMERIC conflict.
    if signal is None:
        numconf, detail = _numeric_conflict(_node_text(a), _node_text(b))
        if numconf:
            signal = "numeric"
            reason = (f"shared subject {sorted(shared)[:3]} but conflicting numeric "
                      f"claims ({detail})")
            base = 0.7

    # NEGATION polarity (one side negated, the other not).
    if signal is None and (neg_a != neg_b):
        signal = "negation"
        which = "second" if neg_b else "first"
        reason = (f"shared subject {sorted(shared)[:3]} but the {which} claim carries a "
                  f"negation the other does not")
        base = 0.6

    if signal is None:
        return None

    overlap_ratio = len(shared) / max(1, min(len(sa) or 1, len(sb) or 1))
    conf = base + 0.25 * overlap_ratio
    if same_comm:
        conf += 0.05
    if linked:
        conf += 0.05
    conf = _clip(conf)

    return {
        "a": {"id": a.get("id"), "title": a.get("title", a.get("id")),
              "community": a.get("community")},
        "b": {"id": b.get("id"), "title": b.get("title", b.get("id")),
              "community": b.get("community")},
        "signal": signal,
        "reason": reason,
        "shared_subject": sorted(shared),
        "same_community": same_comm,
        "linked": linked,
        "confidence": round(conf, 4),
        # HONEST BY CONSTRUCTION: this surface presents, it does not resolve.
        "adjudication": "human-required",
        "resolution": None,
        "note": ("these two grounded claims disagree; a human must adjudicate. "
                 "This surface does not resolve the conflict or pick a winner."),
    }


def detect_conflicts(nodes: list, links: list | None = None) -> dict:
    """Pure detector over a subgraph: return honest conflict pairs + verdict. Deterministic
    (candidate pairs are sorted); NEVER emits a resolution or a winner."""
    nodes = [n for n in (nodes or []) if isinstance(n, dict) and n.get("id")]
    links = links or []
    linkset = set()
    for l in links:
        s, t = l.get("source"), l.get("target")
        if s is not None and t is not None:
            linkset.add(frozenset((s, t)))

    conflicts = []
    n = len(nodes)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = nodes[i], nodes[j]
            linked = frozenset((a.get("id"), b.get("id"))) in linkset
            rec = _pair_signal(a, b, linked)
            if rec is not None:
                conflicts.append(rec)

    conflicts.sort(key=lambda r: (-r["confidence"],
                                  str(r["a"]["id"]), str(r["b"]["id"])))

    flagged = [c for c in conflicts if c["confidence"] >= FLAG_THRESHOLD]
    if flagged:
        verdict = CONFLICT_FLAGGED
    elif conflicts:
        verdict = POSSIBLE_CONFLICT
    else:
        verdict = NO_CONFLICT

    return {
        "verdict": verdict,
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
        "flagged_count": len(flagged),
        "nodes_examined": n,
        "pairs_examined": n * (n - 1) // 2,
    }


# --------------------------------------------------------------------------- #
# Retrieval — reuse the SAME honest brain graph the estate already exposes.
# Indirected through a module-level function so it is guarded (honest UNAVAILABLE
# on failure) and cleanly substitutable in tests.
# --------------------------------------------------------------------------- #
def _retrieve_subgraph(q: str, k: int, ns: str) -> tuple:
    """Return (nodes, links, meta). Reuses szl_brain_api.get_index — invents no nodes."""
    import szl_brain_api as _brain_api
    idx = _brain_api.get_index(ns)
    seeds = idx.search(q, k=max(1, k))
    seed_ids = [s["id"] for s in seeds]
    sub = idx.subgraph(seed_ids) if seed_ids else {"nodes": [], "links": []}
    meta = {
        "source": "szl_brain_api.get_index (reused honest brain graph)",
        "seed_count": len(seed_ids),
        "content_hash": getattr(idx, "content_hash", None),
    }
    return sub.get("nodes", []), sub.get("links", []), meta


def _doctrine_block() -> dict:
    return {
        "label_top": MODELED,
        "locked_proven": LOCKED_COUNT,
        "locked_set": LOCKED_SET,
        "kernel_commit": KERNEL_COMMIT,
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "confidence_cap": CONF_CAP,
        "runtime_cdn": 0,
    }


def run_detection(q: str, k: int = 12, ns: str = "a11oy") -> dict:
    """GET /brain/contradict — retrieve the subgraph for q and detect conflicts. MODELED.
    Pure read: signs/mints nothing. Never 500s — degrades to an honest UNAVAILABLE."""
    try:
        nodes, links, meta = _retrieve_subgraph(q, k, ns)
    except Exception as exc:
        return {
            "ok": False,
            "endpoint": "brain/contradict",
            "label": UNAVAILABLE,
            "query": q,
            "error": str(exc)[:200],
            "doctrine": "v11: retrieval unavailable; no fabricated conflicts/verdict emitted.",
            "timestamp_utc": _now_iso(),
        }
    det = detect_conflicts(nodes, links)
    return {
        "ok": True,
        "endpoint": "brain/contradict",
        "service": "a11oy.brain.contradict",
        "title": "Brain Contradiction Detector — surfaces conflicts, never resolves them",
        "label": MODELED,
        "query": q,
        "k": k,
        "method": ("deterministic lexical/structural heuristics over the retrieved "
                   "subgraph: negation polarity, antonym opposition, numeric conflict. "
                   "No black-box model. Confidence is an honest heuristic strength, "
                   "never a proof, never 1.0."),
        "verdict": det["verdict"],
        "verdict_legend": {
            NO_CONFLICT: "no candidate disagreeing pairs found",
            POSSIBLE_CONFLICT: "candidate pair(s) found, all below the flag threshold",
            CONFLICT_FLAGGED: "at least one candidate pair at/above the flag threshold",
        },
        "flag_threshold": FLAG_THRESHOLD,
        "summary": {
            "nodes_examined": det["nodes_examined"],
            "pairs_examined": det["pairs_examined"],
            "conflict_count": det["conflict_count"],
            "flagged_count": det["flagged_count"],
        },
        "conflicts": det["conflicts"],
        "retrieval": meta,
        "honesty": ("PRESENTS conflicts, NEVER resolves them: every pair carries both "
                    "sides verbatim + adjudication=human-required, resolution=null. No "
                    "winner is picked, no side is hidden, no resolution is fabricated."),
        "doctrine": _doctrine_block(),
        "timestamp_utc": _now_iso(),
    }


def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/contradict/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/contradict"
    return {
        "ok": True,
        "endpoint": "brain/contradict/info",
        "service": "a11oy.brain.contradict",
        "surface_id": SURFACE_ID,
        "title": "Brain Contradiction Detector — surfaces conflicts, never resolves them",
        "label": MODELED,
        "what": ("a governed contradiction detector across the knowledge graph. For a "
                 "query it retrieves the relevant subgraph from the same honest brain "
                 "graph the estate reads and flags pairs of topically-related grounded "
                 "claims that disagree, using transparent deterministic heuristics. It "
                 "PRESENTS each conflict and refuses to RESOLVE it — a human must "
                 "adjudicate. No black-box model; detection is MODELED, never MEASURED."),
        "method": {
            "signals": ["negation-polarity", "antonym-opposition", "numeric-conflict"],
            "black_box_model": False,
            "confidence": "honest heuristic strength, capped below 1.0, never a proof",
            "resolution_policy": ("PRESENT-NEVER-RESOLVE: adjudication=human-required, "
                                  "resolution=null; no winner picked, no side hidden"),
        },
        "endpoints": {
            "info": f"GET  {base}/info",
            "detect": f"GET  {base}?q=&k=",
            "receipt": f"POST {base}/receipt",
        },
        "verdicts": [NO_CONFLICT, POSSIBLE_CONFLICT, CONFLICT_FLAGGED],
        "honest_labels": [MODELED, UNAVAILABLE],
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — only POST /receipt emits an "
                           "unsigned SHA-256 content digest; GET reads mint nothing."),
        "doctrine": _doctrine_block(),
        "timestamp_utc": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), NEVER on a GET.
# --------------------------------------------------------------------------- #
def _canonical_core(detection: dict) -> str:
    """Deterministic canonical serialization of the integrity-bearing content (excludes
    the volatile timestamp), so the digest attests the VERDICT + evidence, not the clock."""
    core = {
        "query": detection.get("query"),
        "verdict": detection.get("verdict"),
        "summary": detection.get("summary"),
        "conflicts": [
            {"a": c.get("a", {}).get("id"), "b": c.get("b", {}).get("id"),
             "signal": c.get("signal"), "confidence": c.get("confidence"),
             "resolution": c.get("resolution")}
            for c in detection.get("conflicts", [])
        ],
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def content_receipt(detection: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over a detection (no signature fabricated)."""
    canonical = _canonical_core(detection)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.braincontradict.detection",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST receipt)",
        "note": ("unsigned SHA-256 content digest of the contradiction detection; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


def handle_receipt(q: str, k: int = 12, ns: str = "a11oy") -> dict:
    """POST /brain/contradict/receipt — run detection + an UNSIGNED SHA-256 content-digest
    receipt (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    det = run_detection(q, k, ns)
    out = dict(det)
    out["endpoint"] = "brain/contradict/receipt"
    out["receipt"] = content_receipt(det)
    return out


# --------------------------------------------------------------------------- #
# FastAPI registration.
#   GET  info/detect — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST receipt     — raw-Request handler via app.router.add_route (Starlette passes the
#                      Request positionally, version-proof under fastapi==0.137.x), with
#                      app.add_api_route as the fallback. Handler annotated
#                      request: fastapi.Request. Registered BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/contradict"

    @app.get(f"{base}/info")
    def _braincontradict_info():
        """Static self-describing manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _braincontradict_detect(q: str = "", k: int = 12):
        """Run contradiction detection over the retrieved subgraph (pure read; MODELED)."""
        return JSONResponse(run_detection(q, k, ns))

    async def _braincontradict_receipt(request):
        """POST: run detection + an UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE)."""
        q, k = "", 12
        try:
            q = request.query_params.get("q", "") or ""
            k = int(request.query_params.get("k", 12) or 12)
        except Exception:
            q, k = "", 12
        try:
            body = await request.json()
            if isinstance(body, dict):
                q = str(body.get("q", q) or q)
                k = int(body.get("k", k) or k)
        except Exception:
            pass
        return JSONResponse(handle_receipt(q, k, ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature analysis
    # (in the add_api_route fallback path) treats the param as the request object (0.137.x).
    try:
        import fastapi as _fastapi
        _braincontradict_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rec_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rec_path, _braincontradict_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rec_path, _braincontradict_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rec_path, _braincontradict_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] braincontradict receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "braincontradict-wired:2(get-only)"

    return "braincontradict-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — plants a conflict, proves a clean query is NO-CONFLICT, proves the
# surface never resolves, and that the receipt is unsigned SHA-256 on write only.
# --------------------------------------------------------------------------- #
def _selftest() -> None:
    # A planted conflict pair (same community, opposing polarity via antonym + negation).
    # The doctrine references below stay honest: Λ is Conjecture 1, never a theorem.
    planted = [
        {"id": "n1", "title": "the sensor link is secure", "community": "c0"},
        {"id": "n2", "title": "the sensor link is insecure", "community": "c0"},
        {"id": "n3", "title": "latency budget is 10 ms", "community": "c1"},
        {"id": "n4", "title": "latency budget is 40 ms", "community": "c1"},
    ]
    det = detect_conflicts(planted, links=[])
    assert det["verdict"] == CONFLICT_FLAGGED, det["verdict"]
    assert det["conflict_count"] >= 2, det
    # NEVER a resolution / winner.
    for c in det["conflicts"]:
        assert c["resolution"] is None
        assert c["adjudication"] == "human-required"
        assert "a" in c and "b" in c  # both sides present, neither hidden
    print(f"[1] planted conflict -> {det['verdict']} "
          f"({det['conflict_count']} pairs, {det['flagged_count']} flagged)  OK")

    # A clean, unrelated set -> NO-CONFLICT.
    clean = [
        {"id": "m1", "title": "energy ledger records joules", "community": "c0"},
        {"id": "m2", "title": "khipu receipts seal state changes", "community": "c1"},
        {"id": "m3", "title": "pagerank ranks node salience", "community": "c2"},
    ]
    cd = detect_conflicts(clean, links=[])
    assert cd["verdict"] == NO_CONFLICT, cd
    assert cd["conflict_count"] == 0
    print("[2] clean query -> NO-CONFLICT (0 pairs)  OK")

    # Receipt: unsigned SHA-256, deterministic on content.
    fake = {"query": "x", "verdict": CONFLICT_FLAGGED,
            "summary": det, "conflicts": det["conflicts"]}
    r1 = content_receipt(fake)
    r2 = content_receipt(fake)
    assert r1["algorithm"] == "sha256" and len(r1["content_sha256"]) == 64
    assert r1["signed"] is False and r1["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert r1["content_sha256"] == r2["content_sha256"], "receipt deterministic"
    print(f"[3] receipt unsigned sha256={r1['content_sha256'][:16]}… deterministic  OK")

    # info(): MODELED, present-never-resolve policy, doctrine locked-8 exact.
    info = handle_info("a11oy")
    assert info["label"] == MODELED
    assert info["method"]["black_box_model"] is False
    d = info["doctrine"]
    assert d["locked_proven"] == 8 and d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["trust_100_percent"] is False
    assert d["trust_ceiling"] == 0.97
    print("[4] info MODELED, present-never-resolve, locked-8 exact, Λ=Conjecture 1  OK")

    print("\nok:true checks:4")


if __name__ == "__main__":
    _selftest()
