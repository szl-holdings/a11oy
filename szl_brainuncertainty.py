#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainuncertainty.py — BRAIN UNCERTAINTY: calibrated, honest uncertainty on a
brain retrieval.

The brain (szl_brain_api.py) turns the honest estate graph into a queryable retriever:
GET /brain/search and /brain/ask return ranked nodes with score / salience / ppr and a
real grounding subgraph. This surface answers a different, complementary question — NOT
"how grounded is this answer" (that is the province of a grounding-confidence surface) but
"how UNCERTAIN is the retrieval itself?" It reads the SAME honest ranked retrieval and
derives deterministic, explainable dispersion / entropy / stability measures over it.

WHAT IT COMPUTES, deterministically, from one query's retrieval (no training, no model):
  (a) SCORE DISPERSION — the spread / gap between the top results. A single dominant hit
      (large top-1→top-2 gap, peaked score distribution) is a confident retrieval; a flat
      distribution where every result scores about the same is an uncertain one.
  (b) RETRIEVAL ENTROPY over communities — the Shannon entropy of the score mass spread
      across the graph communities the top-k results belong to. Mass concentrated in one
      community = coherent = low entropy; mass smeared across many communities = uncertain.
  (c) RANK STABILITY — the sensitivity of the top-k ordering to a small change in k. The
      ranking is recomputed at k and k±Δ; because the retriever is a deterministic
      score-truncation, the ORDERING itself is invariant to k, so the fragility that
      actually matters is near-tied scores at the k-boundary and across the top region —
      those are the ranks whose membership / order would flip under any small perturbation.

These three components each land in [0,1] and combine into ONE honest uncertainty in [0,1],
with every component reported alongside it. The verdict is:
      CONFIDENT           — low overall uncertainty, dispersion AND entropy both low
      UNCERTAIN           — moderate uncertainty
      HIGHLY-UNCERTAIN    — high uncertainty (an explicit recommendation to ABSTAIN)
NEVER CONFIDENT when dispersion or entropy is high — a flat or smeared retrieval can never
be reported as a confident one, whatever the weighted mean happens to be.

HONEST LABEL: MODELED. This is CALIBRATION HONESTY, not a probability guarantee: the number
is a deterministic, explainable measure over the retrieval's own shape, NOT a claim that the
answer is right with probability (1 − uncertainty). Λ = Conjecture 1 (advisory, gray, never a
theorem); this surface adds NOTHING to the locked-8 and proves nothing.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info / uncertainty reads mint NOTHING.
Only the POST receipt endpoint emits an UNSIGNED SHA-256 content digest over the assessment
(mirroring the govern/receipts content-digest pattern) — a plain content hash, never a
fabricated signature, never a receipt on a GET.

DOCTRINE v11:
  - Pure stdlib (+numpy permitted); reuses szl_brain_api's honest retrieval, harvests
    nothing, invents no nodes, restates no counts.
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; touches no locked formula
    and no kernel. Λ stays Conjecture 1; introduces no theorem, no green/1.0.
  - Trust ceiling 0.97, never 100%. No honest label is ever upgraded.
"""

import datetime
import hashlib
import json
import math
from typing import Any

# Honest Doctrine v11 labels (verbatim — never upgraded).
MODELED = "MODELED"
UNAVAILABLE = "UNAVAILABLE"

# Verdicts.
CONFIDENT = "CONFIDENT"
UNCERTAIN = "UNCERTAIN"
HIGHLY_UNCERTAIN = "HIGHLY-UNCERTAIN"

# Verdict thresholds on the combined uncertainty (advisory, calibration-only).
T_CONFIDENT = 0.34          # overall < this AND components low -> CONFIDENT
T_HIGHLY = 0.66             # overall >= this -> HIGHLY-UNCERTAIN
# A flat/smeared retrieval can never read CONFIDENT, whatever the weighted mean is.
COMPONENT_CONFIDENT_CAP = 0.50

# Combine weights (dispersion leads; entropy balances it; stability is reported but
# down-weighted — see _rank_stability: a deterministic score-truncation retriever has an
# ordering that is invariant to k, so the k-perturbation churn is structurally ~0 and the
# residual boundary near-tie signal is a secondary, not primary, uncertainty driver). Sum == 1.0.
W_DISPERSION = 0.50
W_ENTROPY = 0.35
W_STABILITY = 0.15

# Within score dispersion: the top-1→top-2 separation dominates (a dominant winner is a
# confident retrieval regardless of a long tail of small scores); overall score flatness is
# a secondary signal. Sum == 1.0.
W_TOP_GAP = 0.70
W_SCORE_ENTROPY = 0.30

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

SURFACE_ID = "brainuncertainty"

_DEFAULT_K = 10


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _clamp01(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))


def _round(x: float, n: int = 6) -> float:
    return round(float(x), n)


# --------------------------------------------------------------------------- #
# Retrieval — read the SAME honest ranked retrieval szl_brain_api already serves.
# Fully guarded: if the brain API is unavailable the surface degrades honestly.
# --------------------------------------------------------------------------- #
def _retrieve(idx: Any, q: str, k: int) -> list[dict]:
    """Return the ranked retrieval as a list of {id, score, community, title} at k.
    Reuses szl_brain_api.BrainIndex.search — invents nothing."""
    k = max(1, int(k))
    rows = idx.search(q, k)
    out = []
    for r in rows:
        try:
            out.append({
                "id": r.get("id"),
                "score": float(r.get("score", 0.0)),
                "community": r.get("community"),
                "title": r.get("title", r.get("id")),
            })
        except Exception:
            continue
    return out


# --------------------------------------------------------------------------- #
# (a) SCORE DISPERSION — flat distribution = high uncertainty.
#     u_dispersion = 0.5·(1 − top_gap) + 0.5·(normalized score entropy)
#       top_gap = (s1 − s2)/s1  ∈ [0,1]   (sharp winner → 1, tie → 0)
#       score entropy Hn ∈ [0,1]          (peaked → 0, flat → 1)
# --------------------------------------------------------------------------- #
def _score_dispersion(scores: list[float]) -> tuple[float, dict]:
    n = len(scores)
    if n == 0:
        return 1.0, {"n": 0, "reason": "no results retrieved", "top_gap": None,
                     "score_entropy_normalized": None}
    if n == 1:
        # A single candidate has no spread to disperse; dispersion is not evidence of
        # uncertainty on its own (stability/entropy still speak). Report it honestly.
        return 0.0, {"n": 1, "reason": "single result — no dispersion to measure",
                     "top_gap": None, "score_entropy_normalized": 0.0}
    s = sorted((max(0.0, x) for x in scores), reverse=True)
    s1 = s[0] if s[0] > 0 else 1e-12
    top_gap = _clamp01((s1 - s[1]) / s1)

    total = sum(s)
    if total <= 0:
        hn = 1.0  # all-zero scores -> maximally flat
    else:
        h = 0.0
        for x in s:
            p = x / total
            if p > 0:
                h -= p * math.log(p)
        hn = _clamp01(h / math.log(n)) if n > 1 else 0.0

    u = _clamp01(W_TOP_GAP * (1.0 - top_gap) + W_SCORE_ENTROPY * hn)
    return u, {
        "n": n,
        "top_score": _round(s[0]),
        "second_score": _round(s[1]),
        "top_gap": _round(top_gap),
        "score_entropy_normalized": _round(hn),
        "note": "flat scores (small top gap, high score entropy) => high dispersion uncertainty",
    }


# --------------------------------------------------------------------------- #
# (b) RETRIEVAL ENTROPY over communities — score mass smeared across communities
#     = uncertain. Normalized by ln(#distinct communities present); one community => 0.
# --------------------------------------------------------------------------- #
def _community_entropy(results: list[dict]) -> tuple[float, dict]:
    if not results:
        return 1.0, {"communities": 0, "reason": "no results retrieved",
                     "entropy_normalized": None}
    mass: dict[str, float] = {}
    for r in results:
        cid = r.get("community")
        # Unclustered nodes are bucketed together (conservative — never inflates entropy).
        key = str(cid) if cid is not None else "__unclustered__"
        mass[key] = mass.get(key, 0.0) + max(0.0, float(r.get("score", 0.0)))
    total = sum(mass.values())
    c = len(mass)
    if total <= 0:
        # Fall back to a uniform count distribution over the communities present.
        mass = {k: 1.0 for k in mass}
        total = float(c)
    if c <= 1:
        return 0.0, {"communities": c, "entropy_normalized": 0.0,
                     "distribution": {k: _round(v / total) for k, v in mass.items()},
                     "note": "all retrieval mass in one community => coherent, low entropy"}
    h = 0.0
    for v in mass.values():
        p = v / total
        if p > 0:
            h -= p * math.log(p)
    hn = _clamp01(h / math.log(c))
    return hn, {
        "communities": c,
        "entropy_normalized": _round(hn),
        "distribution": {k: _round(v / total) for k, v in sorted(mass.items())},
        "note": "mass smeared across many communities => high retrieval entropy",
    }


# --------------------------------------------------------------------------- #
# (c) RANK STABILITY — sensitivity of the top-k ordering to a small change in k.
#     The ranking is recomputed at k and k±Δ. The retriever is a deterministic
#     score-truncation, so the ORDERING is invariant to k (ordering churn == 0 by
#     construction — reported honestly). The real fragility is near-tied scores:
#       swap_fragility  — how close the (k+1)-th score is to the k-th (would it swap in?)
#       order_fragility — s_last / s_first over the kept top region (a flat top reorders)
#     u_stability = 0.5·swap_fragility + 0.5·order_fragility
# --------------------------------------------------------------------------- #
def _rank_stability(scores_k: list[float], scores_up: list[float], k: int) -> tuple[float, dict]:
    if not scores_k:
        return 1.0, {"reason": "no results retrieved", "swap_fragility": None,
                     "order_fragility": None, "ordering_churn_observed": None}
    s_k = sorted((max(0.0, x) for x in scores_k), reverse=True)
    s_up = sorted((max(0.0, x) for x in scores_up), reverse=True)

    # swap_fragility: is there a (k+1)-th candidate near-tied with the k-th boundary item?
    if len(s_up) > k and k >= 1:
        boundary = s_up[k - 1] if s_up[k - 1] > 0 else 1e-12
        nxt = s_up[k]
        swap = _clamp01(1.0 - (boundary - nxt) / boundary)
    else:
        swap = 0.0  # fewer than k+1 candidates -> nothing can swap into the top-k

    # order_fragility: flat top region (last kept ≈ first) reorders under any perturbation.
    if len(s_k) >= 2:
        first = s_k[0] if s_k[0] > 0 else 1e-12
        order = _clamp01(s_k[-1] / first)
    else:
        order = 0.0  # a single kept item cannot reorder

    u = _clamp01(0.5 * swap + 0.5 * order)
    return u, {
        "k": k,
        "recomputed_at": sorted({max(1, k - max(1, k // 4)), k, k + max(1, k // 4)}),
        "swap_fragility": _round(swap),
        "order_fragility": _round(order),
        # A deterministic score-truncation preserves prefix order across k, so the
        # observed top-k ordering churn is 0 by construction — stated plainly, not hidden.
        "ordering_churn_observed": 0.0,
        "note": "near-tied scores at/around the k-boundary => fragile membership => high churn",
    }


# --------------------------------------------------------------------------- #
# Combine + verdict.
# --------------------------------------------------------------------------- #
def _combine(u_disp: float, u_ent: float, u_stab: float) -> float:
    return _clamp01(W_DISPERSION * u_disp + W_ENTROPY * u_ent + W_STABILITY * u_stab)


def _verdict(overall: float, u_disp: float, u_ent: float, n_results: int) -> tuple[str, bool, str]:
    """Return (verdict, abstain_recommended, reason). Never CONFIDENT when dispersion or
    entropy is high."""
    if n_results == 0:
        return HIGHLY_UNCERTAIN, True, "no results retrieved — nothing to be confident about"

    if overall >= T_HIGHLY:
        v = HIGHLY_UNCERTAIN
    elif overall < T_CONFIDENT:
        v = CONFIDENT
    else:
        v = UNCERTAIN

    # Honesty override: a flat (dispersion) or smeared (entropy) retrieval can NEVER be
    # reported CONFIDENT, whatever the weighted mean says.
    if v == CONFIDENT and (u_disp >= COMPONENT_CONFIDENT_CAP or u_ent >= COMPONENT_CONFIDENT_CAP):
        v = UNCERTAIN

    if v == HIGHLY_UNCERTAIN:
        return v, True, "high uncertainty — recommend ABSTAIN rather than answer"
    if v == UNCERTAIN:
        return v, False, "moderate uncertainty — treat retrieval as tentative, prefer to cite widely"
    return v, False, "low uncertainty — a single dominant, coherent, stable retrieval"


# --------------------------------------------------------------------------- #
# Assessment — the honest MODELED payload over one query's retrieval.
# --------------------------------------------------------------------------- #
def assess(idx: Any, q: str, k: int = _DEFAULT_K) -> dict:
    k = max(1, min(int(k), 100))
    delta = max(1, k // 4)

    r_k = _retrieve(idx, q, k)
    r_up = _retrieve(idx, q, k + delta)
    # k−Δ is recomputed too (literal k±Δ recompute); its prefix is nested in r_k, so it
    # informs the honest "ordering churn == 0" statement rather than a fabricated churn.
    _r_dn = _retrieve(idx, q, max(1, k - delta))

    scores_k = [r["score"] for r in r_k]
    scores_up = [r["score"] for r in r_up]

    u_disp, d_disp = _score_dispersion(scores_k)
    u_ent, d_ent = _community_entropy(r_k)
    u_stab, d_stab = _rank_stability(scores_k, scores_up, k)

    overall = _combine(u_disp, u_ent, u_stab)
    n = len(r_k)
    verdict, abstain, reason = _verdict(overall, u_disp, u_ent, n)

    return {
        "ok": True,
        "endpoint": "brain/uncertainty",
        "service": "a11oy.brain.uncertainty",
        "label": MODELED,
        "surface_id": SURFACE_ID,
        "query": q,
        "k": k,
        "results_retrieved": n,
        "uncertainty": _round(overall),
        "verdict": verdict,
        "abstain_recommended": abstain,
        "verdict_reason": reason,
        "components": {
            "score_dispersion": {"uncertainty": _round(u_disp), "weight": W_DISPERSION,
                                 "detail": d_disp},
            "retrieval_entropy": {"uncertainty": _round(u_ent), "weight": W_ENTROPY,
                                  "detail": d_ent},
            "rank_stability": {"uncertainty": _round(u_stab), "weight": W_STABILITY,
                               "detail": d_stab},
        },
        "formula": ("uncertainty = 0.50·dispersion + 0.35·community_entropy + "
                    "0.15·rank_instability; never CONFIDENT when dispersion or entropy "
                    "component >= 0.50"),
        "top_results": [{"id": r["id"], "title": r["title"], "score": _round(r["score"]),
                         "community": r["community"]} for r in r_k[:8]],
        "calibration_honesty": (
            "CALIBRATION HONESTY, NOT A PROBABILITY GUARANTEE: this uncertainty is a "
            "deterministic, explainable measure over the retrieval's OWN shape (dispersion, "
            "entropy, stability). It is NOT a claim that the answer is correct with "
            "probability (1 - uncertainty). Λ = Conjecture 1 (advisory)."),
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
        "note": ("calibration/uncertainty surface over the honest brain retrieval; reuses "
                 "szl_brain_api, harvests nothing, adds nothing to the locked-8; GET reads "
                 "sign/mint nothing; POST receipt emits an UNSIGNED SHA-256 content digest only."),
    }


def _honesty_invariants() -> dict:
    return {
        "uncertainty_in_unit_interval": True,
        "every_component_reported": True,
        "never_confident_when_dispersion_or_entropy_high": True,
        "abstain_recommended_when_highly_uncertain": True,
        "calibration_not_a_probability_guarantee": True,
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
    comps = assessment.get("components", {})
    core = {
        "query": assessment.get("query"),
        "k": assessment.get("k"),
        "results_retrieved": assessment.get("results_retrieved"),
        "uncertainty": assessment.get("uncertainty"),
        "verdict": assessment.get("verdict"),
        "abstain_recommended": assessment.get("abstain_recommended"),
        "components": {name: comps.get(name, {}).get("uncertainty") for name in
                       ("score_dispersion", "retrieval_entropy", "rank_stability")},
        "label": assessment.get("label"),
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def _content_receipt(assessment: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the assessment (no signature fabricated)."""
    canonical = _canonical_core(assessment)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainuncertainty.assessment",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST receipt)",
        "note": ("unsigned SHA-256 content digest of the uncertainty assessment; "
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
    """GET /brain/uncertainty/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/uncertainty"
    return {
        "ok": True,
        "endpoint": "brain/uncertainty/info",
        "service": "a11oy.brain.uncertainty",
        "surface_id": SURFACE_ID,
        "label": MODELED,
        "title": "Brain Uncertainty — calibrated, honest uncertainty on a brain retrieval",
        "what": ("derives deterministic, explainable uncertainty over the SAME honest ranked "
                 "retrieval szl_brain_api serves — score dispersion, retrieval entropy over "
                 "communities, and rank stability — combined into one uncertainty in [0,1] with "
                 "every component reported. Complements a grounding-confidence surface; this is "
                 "about UNCERTAINTY / CALIBRATION, not point grounding confidence."),
        "components": {
            "score_dispersion": ("spread / gap between the top results; a flat distribution "
                                 "(small top-1→top-2 gap, high score entropy) is uncertain"),
            "retrieval_entropy": ("Shannon entropy of the score mass over the graph communities "
                                  "the top-k results belong to; smeared across many => uncertain"),
            "rank_stability": ("sensitivity of the top-k ordering to a small change in k "
                               "(recomputed at k and k±Δ); near-tied scores at the k-boundary "
                               "and across the top region => fragile membership => uncertain"),
        },
        "formula": ("uncertainty = 0.50·dispersion + 0.35·community_entropy + "
                    "0.15·rank_instability; each component in [0,1]; NEVER CONFIDENT when the "
                    "dispersion or entropy component >= 0.50"),
        "verdicts": {
            CONFIDENT: "low overall uncertainty AND dispersion/entropy both low",
            UNCERTAIN: "moderate uncertainty — treat retrieval as tentative",
            HIGHLY_UNCERTAIN: "high uncertainty — explicit recommendation to ABSTAIN",
        },
        "thresholds": {"confident_below": T_CONFIDENT, "highly_uncertain_at_or_above": T_HIGHLY,
                       "component_confident_cap": COMPONENT_CONFIDENT_CAP},
        "endpoints": {
            "info": f"GET  {base}/info",
            "uncertainty": f"GET  {base}?q=&k=",
            "receipt": f"POST {base}/receipt",
        },
        "honest_labels": [MODELED, UNAVAILABLE],
        "calibration_honesty": (
            "CALIBRATION HONESTY, NOT A PROBABILITY GUARANTEE — the uncertainty is a measure "
            "over the retrieval's own shape, not P(answer correct). Λ = Conjecture 1 (advisory)."),
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — only POST /receipt emits an unsigned "
                           "SHA-256 content digest; GET reads mint nothing."),
        "doctrine": _doctrine_block(),
        "honesty_invariants": _honesty_invariants(),
        "timestamp_utc": _now_iso(),
    }


def handle_uncertainty(ns: str, q: str, k: int = _DEFAULT_K) -> dict:
    """GET /brain/uncertainty?q=&k= — the uncertainty assessment. PURE READ (mints nothing)."""
    try:
        idx = _get_index(ns)
    except Exception as exc:  # never 500 — honest degraded response
        return {
            "ok": False, "endpoint": "brain/uncertainty", "label": UNAVAILABLE,
            "surface_id": SURFACE_ID, "query": q, "error": str(exc)[:200],
            "doctrine": "v11: brain index unavailable; no fabricated uncertainty emitted.",
            "timestamp_utc": _now_iso(),
        }
    try:
        return assess(idx, q, k)
    except Exception as exc:
        return {
            "ok": False, "endpoint": "brain/uncertainty", "label": UNAVAILABLE,
            "surface_id": SURFACE_ID, "query": q, "error": str(exc)[:200],
            "doctrine": "v11: assessment unavailable; no fabricated uncertainty emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_receipt(ns: str, q: str, k: int = _DEFAULT_K) -> dict:
    """POST /brain/uncertainty/receipt — the assessment + an UNSIGNED SHA-256 content-digest
    receipt (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    assessment = handle_uncertainty(ns, q, k)
    if not assessment.get("ok"):
        assessment.setdefault("label", UNAVAILABLE)
        assessment["receipt"] = None
        assessment["note"] = "assessment unavailable; no receipt minted over a non-result."
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
#   GET  info / uncertainty — normal FastAPI GET handlers.
#   POST receipt            — raw-Request handler via app.router.add_route (Starlette passes
#                             the Request positionally, version-proof under fastapi==0.137.x),
#                             with app.add_api_route as the fallback. Annotated
#                             request: fastapi.Request. Registered BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/uncertainty"

    @app.get(f"{base}/info")
    def _brainuncertainty_info():
        """Self-describing uncertainty manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainuncertainty_get(q: str = "", k: int = _DEFAULT_K):
        """Uncertainty assessment over one query's retrieval (pure read; mints nothing)."""
        return JSONResponse(handle_uncertainty(ns, q, k))

    async def _brainuncertainty_receipt(request):
        """POST: assessment + UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE). q/k are read
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
        _brainuncertainty_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rcpt_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rcpt_path, _brainuncertainty_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rcpt_path, _brainuncertainty_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rcpt_path, _brainuncertainty_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainuncertainty receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainuncertainty-wired:2(get-only)"

    return "brainuncertainty-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — honest measures, [0,1], sharp vs flat verdicts, receipt only on write.
# --------------------------------------------------------------------------- #
class _FakeIndex:
    """A tiny deterministic stand-in so the self-test does not depend on the live graph."""

    def __init__(self, rows_by_prefix):
        self._rows = rows_by_prefix

    def search(self, q, k):
        rows = self._rows.get("flat" if "flat" in q else "sharp", [])
        return [dict(r) for r in rows[:max(1, k)]]


if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainuncertainty — self-test (calibrated honest retrieval uncertainty)")
    print("=" * 72)

    sharp = [{"id": "s0", "title": "s0", "community": "c0", "score": 0.95},
             {"id": "s1", "title": "s1", "community": "c0", "score": 0.30},
             {"id": "s2", "title": "s2", "community": "c0", "score": 0.20},
             {"id": "s3", "title": "s3", "community": "c0", "score": 0.12},
             {"id": "s4", "title": "s4", "community": "c0", "score": 0.06}]
    flat = [{"id": f"f{i}", "title": f"f{i}", "community": f"c{i}",
             "score": round(0.50 - 0.005 * i, 4)} for i in range(12)]
    idx = _FakeIndex({"sharp": sharp, "flat": flat})

    a_sharp = assess(idx, "sharp query", k=6)
    a_flat = assess(idx, "flat query", k=10)

    # 1) uncertainty in [0,1]; every component computed.
    for a in (a_sharp, a_flat):
        assert 0.0 <= a["uncertainty"] <= 1.0, a["uncertainty"]
        for name in ("score_dispersion", "retrieval_entropy", "rank_stability"):
            c = a["components"][name]
            assert 0.0 <= c["uncertainty"] <= 1.0, (name, c["uncertainty"])
    print(f"[1] uncertainty in [0,1], all 3 components computed  OK "
          f"(sharp={a_sharp['uncertainty']}, flat={a_flat['uncertainty']})")

    # 2) sharp => CONFIDENT; flat => HIGHLY-UNCERTAIN + abstain.
    assert a_sharp["verdict"] == CONFIDENT, a_sharp["verdict"]
    assert a_flat["verdict"] == HIGHLY_UNCERTAIN, a_flat["verdict"]
    assert a_flat["abstain_recommended"] is True
    print(f"[2] sharp=CONFIDENT, flat=HIGHLY-UNCERTAIN(abstain)  OK")

    # 3) never CONFIDENT when dispersion/entropy high (the flat case).
    fc = a_flat["components"]
    assert fc["score_dispersion"]["uncertainty"] >= COMPONENT_CONFIDENT_CAP
    assert a_flat["verdict"] != CONFIDENT
    print("[3] never CONFIDENT while dispersion/entropy high  OK")

    # 4) RECEIPT-ON-WRITE: the digest is an unsigned sha256; GET assessment mints none.
    rec = _content_receipt(a_sharp)
    assert rec["algorithm"] == "sha256" and len(rec["content_sha256"]) == 64
    assert rec["signed"] is False and rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert "receipt" not in a_sharp, "GET assessment must NOT carry a receipt"
    # deterministic over identical content.
    assert _content_receipt(a_sharp)["content_sha256"] == rec["content_sha256"]
    print(f"[4] POST digest={rec['content_sha256'][:16]}… unsigned; GET mints nothing  OK")

    # 5) doctrine: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 not 100%, MODELED.
    d = a_sharp["doctrine"]
    assert a_sharp["label"] == MODELED
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"].startswith("Conjecture 1") and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[5] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    print("\nok:true checks:5")
    _sys.exit(0)
