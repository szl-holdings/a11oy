#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainretro.py — BRAIN RETRO: an honest RETROSPECTIVE CALIBRATION record over the
brain's OWN past answers.

WHY THIS EXISTS. Every sibling brain-honesty surface answers ONE query in the present:
*is this grounded?* (brainground), *how uncertain am I?* (brainuncertainty), *what did I
ask and what did I answer?* (brainqueryaudit's append-only hash-linked ledger). None of
them ever looks BACK. So the brain has never been able to answer the one question that
actually holds it accountable: **were the answers I already gave actually grounded?**

brainretro is that backward look. It READS the query-audit ledger (what the brain
recorded it answered), RE-RUNS the CURRENT grounding for those same queries, and
compares. The output is a calibration record, not a boast: of the past answers recorded
as confident, how many are STILL grounded now? Of the past ABSTENTIONS, how many were
justified (still ungrounded)? This is the self-honesty loop — the brain measuring its
own past honesty.

WHAT THIS IS — AND IS NOT (honest by construction, Doctrine v11):
  * It is OBSERVABILITY / CALIBRATION ACCOUNTING over the knowledge-graph brain. It is
    accounting, arithmetic over two readings of the same query. It advances NO
    detection / fusion / effector / targeting / cueing capability and computes nothing
    about the world.
  * It is NOT model training, NOT fine-tuning, NOT a reward signal, and it writes
    nothing back into any model or graph. No training data is produced or consumed.
  * It is NOT a claim of self-awareness, sentience, or consciousness — the doctrine bans
    those claims and this surface makes none. "Self-honesty" here means exactly one
    mechanical thing: recompute-and-compare arithmetic over a recorded ledger.
  * Its own top label is MODELED (a derived comparison view, never a live measurement of
    semantic truth). No label is ever upgraded.

THE HONEST CAVEAT THAT MATTERS MOST. The query-audit ledger it reads is EPHEMERAL —
in-memory, reset on every process restart. On a freshly started Space there is simply no
history to calibrate against, so brainretro reports INSUFFICIENT-HISTORY. That is the
honest default, and it is stated plainly in /info rather than dressed up as if the
surface owned a persistent audit history. A truthful INSUFFICIENT-HISTORY beats a
fabricated calibration rate.

CLASSIFICATION (per past ledger entry, three buckets, never more generous than evidence):
  * CONFIRMED     — the recorded posture STILL holds on recompute (a past GROUNDED answer
                    is still grounded; a past abstention is still ungrounded, i.e. the
                    abstention was justified).
  * DRIFTED       — the recorded posture NO LONGER holds. Direction is reported honestly:
                    OVER-CLAIM (past grounded, now ungrounded — a real honesty risk) or
                    OVER-CAUTION (past abstained, now grounded — cautious, not a claim).
  * STALE-UNKNOWN — the comparison CANNOT be made: grounding is not recomputable right
                    now, or the recorded verdict is outside the known posture vocabulary.
                    A past answer is NEVER counted as correct without recomputed evidence;
                    an uncomparable entry stays STALE-UNKNOWN forever rather than pass.

OVERALL VERDICT:
  * INSUFFICIENT-HISTORY — the ledger is absent, empty, smaller than MIN_HISTORY, or
    nothing in the sample was recomputable. The honest default (see the caveat above).
  * DRIFT-DETECTED       — at least one sampled entry DRIFTED. Never softened.
  * WELL-CALIBRATED      — enough comparable history and zero DRIFTED entries.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. GET info/retro mint NOTHING. Only POST
retro/receipt emits an UNSIGNED SHA-256 content digest over the computed calibration
record (mirrors the honestywall / brainground content-digest pattern) — a plain content
hash, never a fabricated signature.

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; touches no locked
    formula and no kernel. Λ stays Conjecture 1 (advisory, gray, never a theorem, never
    green/1.0). Khipu BFT stays Conjecture 2. Trust ceiling 0.97, never 100%.
  * Sibling surfaces are reached through GUARDED imports. An absent sibling yields
    UNAVAILABLE — never a fabricated ledger, never a fabricated grounding.
  * Pure stdlib + numpy. Additive routes registered before the SPA catch-all; canonical
    domain a-11-oy.com; 0 runtime CDN.
"""

import datetime
import hashlib
import json

import numpy as np

# Honest Doctrine v11 label vocabulary. Restated here (not imported) so a broken import
# can never silently blank the vocabulary; tests grep these exact strings.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# This surface's own top label — a derived comparison view, not a live measurement.
LBL_MODELED = "MODELED"
LBL_UNAVAILABLE = "UNAVAILABLE"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "brainretro"

# Doctrine constants (never inflated).
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
TRUST_CEILING = 0.97
KERNEL_COMMIT = "c7c0ba17"

# Per-entry classifications.
CLS_CONFIRMED = "CONFIRMED"
CLS_DRIFTED = "DRIFTED"
CLS_STALE_UNKNOWN = "STALE-UNKNOWN"

# Drift direction (only meaningful on a DRIFTED entry).
DRIFT_OVER_CLAIM = "OVER-CLAIM"      # past grounded -> now ungrounded (honesty risk)
DRIFT_OVER_CAUTION = "OVER-CAUTION"  # past abstained -> now grounded (cautious, not a claim)

# Overall verdicts.
VERDICT_WELL_CALIBRATED = "WELL-CALIBRATED"
VERDICT_DRIFT_DETECTED = "DRIFT-DETECTED"
VERDICT_INSUFFICIENT_HISTORY = "INSUFFICIENT-HISTORY"

# Recorded/recomputed grounding verdicts mapped to an ordered POSTURE rank. A verdict
# outside this map is NOT guessed — the entry becomes STALE-UNKNOWN.
POSTURE_RANK = {
    "GROUNDED": 2,                  # confident: the brain answered
    "WEAK-GROUNDING": 1,            # cautious: answered with caution
    "INSUFFICIENT-GROUNDING": 0,    # abstention: the brain declined to answer
}
POSTURE_NAME = {2: "CONFIDENT", 1: "CAUTIOUS", 0: "ABSTAINED"}

# Which recorded postures count as a past CONFIDENT answer vs a past ABSTENTION, for the
# two headline calibration rates.
CONFIDENT_RANK = 2
ABSTENTION_RANK = 0

# Sampling / sufficiency.
DEFAULT_SAMPLE = 12          # most-recent N ledger entries recomputed per request
MAX_SAMPLE = 50              # hard cap (this is a read, not a crawl)
MIN_HISTORY = 3              # fewer recorded entries than this => INSUFFICIENT-HISTORY
DEFAULT_K = 12               # retrieval breadth handed to the grounding recompute


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


EPHEMERAL_CAVEAT = (
    "THE QUERY-AUDIT LEDGER THIS SURFACE READS IS EPHEMERAL: szl_brainqueryaudit keeps "
    "it in memory only and it resets on every process restart. There is no persistent "
    "answer history behind this surface. On a freshly started Space the ledger is empty, "
    "so brainretro honestly reports INSUFFICIENT-HISTORY — it does not imply a durable "
    "record it does not have. A calibration rate only appears once this same process has "
    f"recorded at least {MIN_HISTORY} query entries."
)


def _persistence_block() -> dict:
    return {
        "durable": False,
        "storage": "in-memory (ephemeral) — owned by szl_brainqueryaudit",
        "resets_on_restart": True,
        "min_history_required": MIN_HISTORY,
        "honest_default_on_fresh_process": VERDICT_INSUFFICIENT_HISTORY,
        "caveat": EPHEMERAL_CAVEAT,
    }


# --------------------------------------------------------------------------- #
# Sibling bridges — GUARDED imports. An absent sibling is UNAVAILABLE, never
# fabricated into an empty-but-valid ledger or a fabricated grounding verdict.
# --------------------------------------------------------------------------- #

def read_ledger(ns: str = "a11oy") -> tuple:
    """Read the query-audit ledger entries for a namespace. Returns (entries, error).

    entries is None (NOT an empty list) when the ledger cannot be read at all — the two
    cases are honestly different: None means UNAVAILABLE (we do not know what the brain
    answered), [] means the ledger is readable and genuinely empty. Never raises."""
    try:
        import szl_brainqueryaudit as _qa
    except Exception as exc:  # sibling absent -> UNAVAILABLE, never fabricated
        return None, f"szl_brainqueryaudit not importable: {str(exc)[:160]}"
    accessor = getattr(_qa, "_ledger", None)
    if not callable(accessor):
        return None, "szl_brainqueryaudit exposes no ledger accessor (_ledger)"
    try:
        raw = accessor(ns)
        if raw is None:
            return None, "szl_brainqueryaudit returned no ledger for this namespace"
        return [dict(e) for e in raw], None
    except Exception as exc:
        return None, f"szl_brainqueryaudit ledger read failed: {str(exc)[:160]}"


def recompute_grounding(query: str, k: int = DEFAULT_K, ns: str = "a11oy") -> tuple:
    """Re-run the CURRENT grounding for one past query. Returns (result, error).

    result is None whenever grounding cannot be recomputed — including the case where
    brainground itself answers with ok=False (brain retrieval unreachable). That is the
    critical honesty rule: an unreachable brain must NOT be read as evidence that a past
    answer drifted. No recompute, no comparison; the entry becomes STALE-UNKNOWN."""
    try:
        import szl_brainground as _bg
    except Exception as exc:  # sibling absent -> UNAVAILABLE, never fabricated
        return None, f"szl_brainground not importable: {str(exc)[:160]}"
    evaluate = getattr(_bg, "evaluate", None)
    if not callable(evaluate):
        return None, "szl_brainground exposes no evaluate()"
    try:
        res = evaluate(query, k=max(1, int(k)), ns=ns)
    except Exception as exc:
        return None, f"szl_brainground evaluate failed: {str(exc)[:160]}"
    if not isinstance(res, dict):
        return None, "szl_brainground returned a non-dict result"
    if res.get("ok") is not True:
        # brainground degraded honestly (e.g. brain graph unavailable). We refuse to
        # treat its fallback verdict as recomputed evidence of anything.
        return None, ("szl_brainground could not score grounding this request "
                      f"({str(res.get('verdict'))[:60]}); no comparison made")
    return res, None


# --------------------------------------------------------------------------- #
# Classification — the pure comparison. Recorded posture vs recomputed posture.
# --------------------------------------------------------------------------- #

def classify(recorded_verdict, recomputed_verdict) -> dict:
    """Compare ONE recorded verdict against ONE recomputed verdict. PURE.

    Returns {classification, drift_direction, past_posture, now_posture, reason}. Either
    verdict being absent or outside POSTURE_RANK yields STALE-UNKNOWN: we never guess a
    posture, and we never count an uncomparable past answer as correct."""
    past_key = str(recorded_verdict or "").strip().upper()
    now_key = str(recomputed_verdict or "").strip().upper()
    past_rank = POSTURE_RANK.get(past_key)
    now_rank = POSTURE_RANK.get(now_key)

    if past_rank is None or now_rank is None:
        missing = []
        if past_rank is None:
            missing.append(f"recorded verdict {past_key or '(absent)'!s} not in the "
                           f"known posture vocabulary")
        if now_rank is None:
            missing.append("grounding not recomputable this request")
        return {
            "classification": CLS_STALE_UNKNOWN,
            "drift_direction": None,
            "past_posture": POSTURE_NAME.get(past_rank),
            "now_posture": POSTURE_NAME.get(now_rank),
            "reason": ("; ".join(missing) + " — reported STALE-UNKNOWN; the past answer "
                       "is NOT counted correct without recomputed evidence"),
        }

    if past_rank == now_rank:
        if past_rank == ABSTENTION_RANK:
            reason = ("the recorded abstention is still ungrounded on recompute — the "
                      "abstention was justified")
        elif past_rank == CONFIDENT_RANK:
            reason = ("the recorded confident answer is STILL grounded on recompute — "
                      "posture confirmed")
        else:
            reason = ("the recorded cautious posture is unchanged on recompute — "
                      "posture confirmed")
        return {
            "classification": CLS_CONFIRMED,
            "drift_direction": None,
            "past_posture": POSTURE_NAME[past_rank],
            "now_posture": POSTURE_NAME[now_rank],
            "reason": reason,
        }

    if past_rank > now_rank:
        direction = DRIFT_OVER_CLAIM
        reason = ("the recorded posture was MORE confident than the current grounding "
                  "supports (past " + POSTURE_NAME[past_rank] + ", now "
                  + POSTURE_NAME[now_rank] + ") — a real honesty risk, reported as "
                  "drift and never softened")
    else:
        direction = DRIFT_OVER_CAUTION
        reason = ("the recorded posture was LESS confident than the current grounding "
                  "supports (past " + POSTURE_NAME[past_rank] + ", now "
                  + POSTURE_NAME[now_rank] + ") — cautious rather than over-claiming, "
                  "still recorded as drift because the recorded posture no longer holds")
    return {
        "classification": CLS_DRIFTED,
        "drift_direction": direction,
        "past_posture": POSTURE_NAME[past_rank],
        "now_posture": POSTURE_NAME[now_rank],
        "reason": reason,
    }


def _rate(numerator: int, denominator: int):
    """Honest count ratio via numpy, or None when there is nothing to divide."""
    if not denominator:
        return None
    return float(round(float(np.divide(float(numerator), float(denominator))), 6))


# --------------------------------------------------------------------------- #
# The calibration record.
# --------------------------------------------------------------------------- #

def evaluate(sample: int = DEFAULT_SAMPLE, k: int = DEFAULT_K,
             ns: str = "a11oy") -> dict:
    """Build the retrospective calibration record. PURE READ (mints nothing).

    Reads the query-audit ledger, recomputes CURRENT grounding for the most recent
    `sample` entries, classifies each CONFIRMED / DRIFTED / STALE-UNKNOWN, and reports
    honest rates plus the overall verdict."""
    sample = max(1, min(int(sample or DEFAULT_SAMPLE), MAX_SAMPLE))
    k = max(1, min(int(k or DEFAULT_K), 64))

    entries, ledger_err = read_ledger(ns)
    if entries is None:
        return {
            "ok": False,
            "endpoint": "brain/retro",
            "surface_id": SURFACE_ID,
            "label": LBL_UNAVAILABLE,
            "ns": ns,
            "verdict": VERDICT_INSUFFICIENT_HISTORY,
            "verdict_reason": ("the query-audit ledger could not be read, so there is no "
                              "recorded answer history to calibrate against; no "
                              "calibration rate fabricated"),
            "ledger_status": LBL_UNAVAILABLE,
            "ledger_error": ledger_err,
            "history_entries": None,
            "sample_requested": sample,
            "entries": [],
            "summary": _empty_summary(),
            "calibration": _empty_calibration(),
            "persistence": _persistence_block(),
            "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — this read mints nothing."),
            "doctrine": _doctrine_block(
                "ledger sibling unavailable; honest UNAVAILABLE, no history invented. "
                "Λ = Conjecture 1, never a theorem."),
            "timestamp_utc": _now_iso(),
        }

    history = len(entries)
    window = entries[-sample:] if history else []

    rows = []
    for e in window:
        query = e.get("query")
        recorded = e.get("returned_verdict")
        now_res, ground_err = recompute_grounding(str(query or ""), k=k, ns=ns)
        recomputed = now_res.get("verdict") if isinstance(now_res, dict) else None
        cls = classify(recorded, recomputed)
        rows.append({
            "seq": e.get("seq"),
            "query": query,
            "recorded_at_utc": e.get("timestamp_utc"),
            "recorded_verdict": recorded,
            "recorded_grounding_label": e.get("grounding_label"),
            "recomputed_verdict": recomputed,
            "recomputed_confidence": (
                now_res.get("grounding_confidence") if isinstance(now_res, dict) else None),
            "recompute_error": ground_err,
            "classification": cls["classification"],
            "drift_direction": cls["drift_direction"],
            "past_posture": cls["past_posture"],
            "now_posture": cls["now_posture"],
            "reason": cls["reason"],
        })

    summary = _summarize(rows, history=history, sample_requested=sample)
    calibration = _calibrate(rows)
    verdict, reason = _verdict(history, summary)

    return {
        "ok": True,
        "endpoint": "brain/retro",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "ns": ns,
        "verdict": verdict,
        "verdict_reason": reason,
        "verdicts": [VERDICT_WELL_CALIBRATED, VERDICT_DRIFT_DETECTED,
                     VERDICT_INSUFFICIENT_HISTORY],
        "ledger_status": "READ",
        "ledger_error": None,
        "history_entries": history,
        "sample_requested": sample,
        "k": k,
        "entries": rows,
        "summary": summary,
        "calibration": calibration,
        "persistence": _persistence_block(),
        "method": ("read the recorded {query, returned_verdict} entries from the "
                   "query-audit ledger, re-run the CURRENT grounding for each sampled "
                   "query via szl_brainground.evaluate, and compare the recorded posture "
                   "with the recomputed posture. Arithmetic over two readings — no model "
                   "call, no training, no writeback."),
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — this GET recomputes and "
                           "compares but mints nothing and appends nothing."),
        "doctrine": _doctrine_block(
            "retrospective calibration accounting over the knowledge-graph brain; adds "
            "nothing to the locked-8; Λ = Conjecture 1, never a theorem; no sentience "
            "claim; not model training."),
        "timestamp_utc": _now_iso(),
    }


def _empty_summary() -> dict:
    return {
        "history_entries": None, "sample_requested": None, "sampled": 0,
        "confirmed": 0, "drifted": 0, "stale_unknown": 0, "comparable": 0,
        "drift_over_claim": 0, "drift_over_caution": 0,
        "drifted_seqs": [], "min_history_required": MIN_HISTORY,
    }


def _empty_calibration() -> dict:
    return {
        "confident_recorded": 0, "confident_still_grounded": 0,
        "confident_confirmed_rate": None,
        "abstentions_recorded": 0, "abstentions_still_justified": 0,
        "abstention_justified_rate": None,
        "calibration_rate": None, "modeled_calibration": None,
        "note": ("rates are honest COUNT RATIOS over comparable sampled entries only; "
                 "STALE-UNKNOWN entries are excluded from every numerator AND every "
                 "denominator rather than assumed correct. None means 'nothing "
                 "comparable' — never 0.0 and never 1.0 by default."),
    }


def _summarize(rows: list, history: int, sample_requested: int) -> dict:
    confirmed = [r for r in rows if r["classification"] == CLS_CONFIRMED]
    drifted = [r for r in rows if r["classification"] == CLS_DRIFTED]
    stale = [r for r in rows if r["classification"] == CLS_STALE_UNKNOWN]
    return {
        "history_entries": history,
        "sample_requested": sample_requested,
        "sampled": len(rows),
        "confirmed": len(confirmed),
        "drifted": len(drifted),
        "stale_unknown": len(stale),
        "comparable": len(confirmed) + len(drifted),
        "drift_over_claim": sum(1 for r in drifted
                                if r["drift_direction"] == DRIFT_OVER_CLAIM),
        "drift_over_caution": sum(1 for r in drifted
                                  if r["drift_direction"] == DRIFT_OVER_CAUTION),
        "drifted_seqs": [r["seq"] for r in drifted],
        "min_history_required": MIN_HISTORY,
    }


def _calibrate(rows: list) -> dict:
    """The two headline honesty rates + the overall calibration rate. PURE.

    Only COMPARABLE entries (CONFIRMED or DRIFTED) enter a denominator. A STALE-UNKNOWN
    entry is excluded entirely — it is never quietly counted as a correct past answer."""
    comparable = [r for r in rows if r["classification"] in (CLS_CONFIRMED, CLS_DRIFTED)]

    confident = [r for r in comparable if r["past_posture"] == POSTURE_NAME[CONFIDENT_RANK]]
    confident_ok = [r for r in confident if r["classification"] == CLS_CONFIRMED]

    abstained = [r for r in comparable
                 if r["past_posture"] == POSTURE_NAME[ABSTENTION_RANK]]
    abstained_ok = [r for r in abstained if r["classification"] == CLS_CONFIRMED]

    confirmed_total = sum(1 for r in comparable if r["classification"] == CLS_CONFIRMED)
    rate = _rate(confirmed_total, len(comparable))

    out = _empty_calibration()
    out.update({
        "confident_recorded": len(confident),
        "confident_still_grounded": len(confident_ok),
        "confident_confirmed_rate": _rate(len(confident_ok), len(confident)),
        "abstentions_recorded": len(abstained),
        "abstentions_still_justified": len(abstained_ok),
        "abstention_justified_rate": _rate(len(abstained_ok), len(abstained)),
        "calibration_rate": rate,
        # A doctrine-capped companion figure for any confidence-style display: never
        # 1.0, never 100%. The raw count ratio above is reported unmodified alongside it.
        "modeled_calibration": (None if rate is None
                                else float(round(min(rate, TRUST_CEILING), 6))),
    })
    return out


def _verdict(history: int, summary: dict) -> tuple:
    """Overall verdict. INSUFFICIENT-HISTORY is the honest default; DRIFT-DETECTED is
    never softened to WELL-CALIBRATED."""
    if history < MIN_HISTORY:
        return VERDICT_INSUFFICIENT_HISTORY, (
            f"the ephemeral query-audit ledger holds {history} recorded entr"
            f"{'y' if history == 1 else 'ies'}, fewer than the {MIN_HISTORY} required to "
            f"report a calibration rate; INSUFFICIENT-HISTORY is the honest default on a "
            f"fresh process (the ledger is in-memory and resets on restart)")
    if summary["comparable"] == 0:
        return VERDICT_INSUFFICIENT_HISTORY, (
            f"{summary['sampled']} entr{'y' if summary['sampled'] == 1 else 'ies'} "
            f"sampled but none was recomputable (all STALE-UNKNOWN), so no past answer "
            f"can be confirmed or refuted on evidence; INSUFFICIENT-HISTORY rather than a "
            f"fabricated rate")
    if summary["drifted"] > 0:
        return VERDICT_DRIFT_DETECTED, (
            f"{summary['drifted']} of {summary['comparable']} comparable entr"
            f"{'y' if summary['comparable'] == 1 else 'ies'} DRIFTED "
            f"({summary['drift_over_claim']} over-claim, "
            f"{summary['drift_over_caution']} over-caution); reported DRIFT-DETECTED and "
            f"never softened to WELL-CALIBRATED")
    return VERDICT_WELL_CALIBRATED, (
        f"all {summary['comparable']} comparable entr"
        f"{'y' if summary['comparable'] == 1 else 'ies'} CONFIRMED on recompute; "
        f"{summary['stale_unknown']} entr"
        f"{'y' if summary['stale_unknown'] == 1 else 'ies'} left STALE-UNKNOWN (excluded, "
        f"never assumed correct)")


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), never on GET.
# --------------------------------------------------------------------------- #

def _canonical_core(result: dict) -> str:
    """Deterministic canonical serialization of the calibration-bearing content (the
    volatile timestamp is excluded) so the digest attests the VERDICT + rates +
    per-entry classifications."""
    summary = result.get("summary") or {}
    calib = result.get("calibration") or {}
    core = {
        "label": result.get("label"),
        "verdict": result.get("verdict"),
        "ledger_status": result.get("ledger_status"),
        "history_entries": result.get("history_entries"),
        "summary": {kk: summary.get(kk) for kk in sorted(summary)},
        "calibration": {kk: calib.get(kk) for kk in sorted(calib)},
        "entries": [
            {
                "seq": r.get("seq"),
                "recorded_verdict": r.get("recorded_verdict"),
                "recomputed_verdict": r.get("recomputed_verdict"),
                "classification": r.get("classification"),
                "drift_direction": r.get("drift_direction"),
            }
            for r in (result.get("entries") or [])
        ],
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def content_receipt(result: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over a calibration record."""
    digest = hashlib.sha256(_canonical_core(result).encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainretro.calibration",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST retro/receipt)",
        "note": ("unsigned SHA-256 content digest of the retrospective calibration "
                 "record; RECEIPT-ON-WRITE, never on a GET read. No signature "
                 "fabricated, no proof claimed beyond the digest."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #

def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/retro/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/retro"
    return {
        "ok": True,
        "service": "a11oy.brain.retro",
        "endpoint": "brain/retro/info",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "title": ("Brain Retro — retrospective calibration of the brain's own past "
                  "answers"),
        "what": ("reads the append-only query-audit ledger (what the brain recorded it "
                 "answered), re-runs the CURRENT grounding for a sample of those same "
                 "queries, and compares. Of the past answers recorded as confident, how "
                 "many are STILL grounded? Of the past abstentions, how many were "
                 "justified (still ungrounded)? Pure honesty/observability accounting "
                 "over the knowledge-graph brain; advances no "
                 "detection/fusion/effector/targeting/cueing capability."),
        "what_this_is_not": [
            "NOT model training, fine-tuning, or a reward signal — nothing is written "
            "back into any model or graph, and no training data is produced or consumed",
            "NOT a claim of self-awareness, sentience, or consciousness — 'self-honesty' "
            "here means only recompute-and-compare arithmetic over a recorded ledger",
            "NOT a measurement of semantic truth — the top label is MODELED",
            "NOT a persistent audit history — see the ephemeral-ledger caveat below",
        ],
        "ephemeral_ledger_caveat": EPHEMERAL_CAVEAT,
        "persistence": _persistence_block(),
        "method": ("for each sampled ledger entry: take the RECORDED verdict verbatim, "
                   "recompute grounding now through a guarded szl_brainground.evaluate, "
                   "map both to an ordered posture (CONFIDENT / CAUTIOUS / ABSTAINED), "
                   "and compare. Both siblings are reached through GUARDED imports; an "
                   "absent sibling yields UNAVAILABLE, never a fabricated ledger and "
                   "never a fabricated grounding verdict."),
        "endpoints": {
            "info": f"GET  {base}/info",
            "retro": f"GET  {base}?sample=&k=",
            "receipt": f"POST {base}/receipt",
        },
        "receipt_body": {
            "sample": f"int — most-recent ledger entries to recompute (1..{MAX_SAMPLE})",
            "k": "int — retrieval breadth handed to the grounding recompute",
        },
        "classifications": [CLS_CONFIRMED, CLS_DRIFTED, CLS_STALE_UNKNOWN],
        "classification_legend": {
            CLS_CONFIRMED: ("the recorded posture STILL holds on recompute — a past "
                            "GROUNDED answer is still grounded, or a past abstention is "
                            "still ungrounded (the abstention was justified)"),
            CLS_DRIFTED: ("the recorded posture NO LONGER holds; direction is reported "
                          "honestly as OVER-CLAIM (past grounded, now ungrounded — a "
                          "real honesty risk) or OVER-CAUTION (past abstained, now "
                          "grounded)"),
            CLS_STALE_UNKNOWN: ("the comparison cannot be made — grounding is not "
                                "recomputable right now, or the recorded verdict is "
                                "outside the known posture vocabulary. Excluded from "
                                "every rate; a past answer is NEVER counted correct "
                                "without recomputed evidence"),
        },
        "drift_directions": [DRIFT_OVER_CLAIM, DRIFT_OVER_CAUTION],
        "verdicts": [VERDICT_WELL_CALIBRATED, VERDICT_DRIFT_DETECTED,
                     VERDICT_INSUFFICIENT_HISTORY],
        "verdict_legend": {
            VERDICT_WELL_CALIBRATED: (f"at least {MIN_HISTORY} recorded entries, at least "
                                      f"one comparable, and zero DRIFTED"),
            VERDICT_DRIFT_DETECTED: ("at least one sampled entry DRIFTED; never softened "
                                     "to WELL-CALIBRATED"),
            VERDICT_INSUFFICIENT_HISTORY: (f"the ledger is unavailable, empty, holds "
                                           f"fewer than {MIN_HISTORY} entries, or nothing "
                                           f"sampled was recomputable — the honest "
                                           f"default, and the expected state on a fresh "
                                           f"Space"),
        },
        "posture_vocabulary": {kk: POSTURE_NAME[vv] for kk, vv in POSTURE_RANK.items()},
        "rate_policy": ("every rate is a COUNT RATIO over comparable entries only. None "
                        "means 'nothing comparable' — never 0.0 and never 1.0 by "
                        "default. modeled_calibration is additionally capped at the "
                        "0.97 trust ceiling; the raw count ratio is reported unmodified "
                        "beside it."),
        "receipt": {
            "algorithm": "sha256",
            "mode": "UNSIGNED-CONTENT-DIGEST",
            "signed": False,
            "note": ("the receipt is an UNSIGNED content digest over the calibration "
                     "record. It is NOT a signature and NOT a proof of anything beyond "
                     "the content digest."),
        },
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — only POST /receipt mints an "
                           "unsigned SHA-256 receipt; GET reads mint nothing."),
        "sampling": {"default_sample": DEFAULT_SAMPLE, "max_sample": MAX_SAMPLE,
                     "default_k": DEFAULT_K},
        "siblings": {
            "szl_brainqueryaudit": "the ephemeral append-only ledger read (guarded)",
            "szl_brainground": "the grounding recompute (guarded)",
        },
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "additive retrospective calibration surface over the knowledge-graph brain; "
            "touches no locked formula and no kernel; Λ = Conjecture 1, never a theorem; "
            "no sentience claim; not model training."),
        "timestamp_utc": _now_iso(),
    }


def handle_manifest(ns: str = "a11oy") -> dict:
    """GET /brain/brainretro/manifest — this surface's OWN honesty manifest, at a path
    whose id SEGMENT equals the surface id so the Honesty Wall (szl_honestywall.py) and
    the Frontier Index (szl_frontier_index.py) can find and read it in-process.

    Why a second, id-named route: the wall collects a surface's manifest by looking for a
    registered a11oy GET route with a path segment equal (normalized) to the surface id.
    This surface's functional routes live under `brain/retro`, whose segments are `brain`
    and `retro` — neither equals `brainretro` — so without this route the wall can read
    nothing about brainretro and honestly marks it NO-MANIFEST. This route closes that gap
    by DECLARING the surface's true posture; it adds no capability and computes nothing.

    Everything declared here is the honest truth about this surface:
      * data label MODELED, verbatim, never upgraded to MEASURED — the calibration record
        is recompute-and-compare arithmetic over a recorded ledger, not a measurement of
        semantic truth.
      * the history behind it is EPHEMERAL and the manifest says so plainly, so the wall
        (and any reader) sees the caveat rather than an implied durable audit trail.
      * only the estate-wide doctrine invariants that ARE true estate-wide are declared.

    PURE READ — mints nothing.
    """
    base = f"/api/{ns}/v1/brain/retro"
    return {
        "ok": True,
        "service": "a11oy.brain.retro",
        "endpoint": f"brain/{SURFACE_ID}/manifest",
        "surface_id": SURFACE_ID,
        "title": ("Brain Retro — retrospective calibration of the brain's own past "
                  "answers"),
        # VERBATIM, never upgraded: this surface models calibration, it measures nothing.
        "label": LBL_MODELED,
        "data_label": LBL_MODELED,
        "native_backend": True,
        "provenance_coverage": 1.0,
        "what": ("declares the honesty posture of the brainretro retrospective-calibration "
                 "surface. brainretro reads the append-only query-audit ledger, recomputes "
                 "the CURRENT grounding for a sample of the queries recorded there, and "
                 "compares the two — reporting per entry CONFIRMED / DRIFTED / "
                 "STALE-UNKNOWN and an overall WELL-CALIBRATED / DRIFT-DETECTED / "
                 "INSUFFICIENT-HISTORY verdict. Pure honesty/observability accounting over "
                 "the knowledge-graph brain; advances no detection/fusion/effector/"
                 "targeting/cueing capability and no locked formula."),
        "honest_scope": [
            "the top label is MODELED and is never upgraded to MEASURED — no field here "
            "is read from a live instrument",
            "an entry that cannot be recomputed is STALE-UNKNOWN and is excluded from "
            "every numerator AND denominator; no past answer is ever counted correct "
            "without recomputed evidence",
            "the underlying query-audit ledger is EPHEMERAL, so on a fresh process this "
            "surface honestly reports INSUFFICIENT-HISTORY rather than a calibration rate",
            "not model training, fine-tuning, or a reward signal; nothing is written back "
            "into any model or graph",
            "not a claim of self-awareness, sentience, or consciousness — 'self-honesty' "
            "here means only recompute-and-compare arithmetic over a recorded ledger",
        ],
        "ephemeral_ledger_caveat": EPHEMERAL_CAVEAT,
        "persistence": _persistence_block(),
        "classifications": [CLS_CONFIRMED, CLS_DRIFTED, CLS_STALE_UNKNOWN],
        "verdicts": [VERDICT_WELL_CALIBRATED, VERDICT_DRIFT_DETECTED,
                     VERDICT_INSUFFICIENT_HISTORY],
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "endpoints": {
            "info": f"GET  {base}/info",
            "retro": f"GET  {base}?sample=&k=",
            "receipt": f"POST {base}/receipt",
            "manifest": f"GET  /api/{ns}/v1/brain/{SURFACE_ID}/manifest",
        },
        "doctrine": _doctrine_block(
            "honesty manifest for the brainretro surface; declarative only, computes "
            "nothing and adds no capability; Λ = Conjecture 1, never a theorem."),
        "conjecture_green": False,
        "honesty_invariants": {
            "observes_only_never_advances_capability": True,
            "label_never_upgraded": True,
            "never_claims_measured": True,
            "never_counts_a_past_answer_correct_without_recompute": True,
            "never_softens_drift_detected_to_well_calibrated": True,
            "unrecomputable_entries_excluded_from_every_rate": True,
            "reports_insufficient_history_rather_than_a_fabricated_rate": True,
            "ephemeral_history_disclosed_not_implied_durable": True,
            "absent_sibling_yields_unavailable_never_fabricated": True,
            "receipt_on_write_not_on_read": True,
            "receipt_unsigned_and_declared_unsigned": True,
            "lambda_is_conjecture_1_not_a_theorem": True,
            "adds_nothing_to_locked_8": True,
            "no_consciousness_claim": True,
            "is_not_model_training": True,
        },
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — this GET manifest mints "
                           "nothing; only POST /brain/retro/receipt mints an unsigned "
                           "SHA-256 content digest."),
        "timestamp_utc": _now_iso(),
    }


def handle_retro(sample: int = DEFAULT_SAMPLE, k: int = DEFAULT_K,
                 ns: str = "a11oy") -> dict:
    """GET /brain/retro — the calibration record. PURE READ (mints nothing, appends
    nothing). Never 500s: honest degraded response on error."""
    try:
        return evaluate(sample=sample, k=k, ns=ns)
    except Exception as exc:  # never 500 — honest degraded response
        return {
            "ok": False, "endpoint": "brain/retro", "label": LBL_UNAVAILABLE,
            "surface_id": SURFACE_ID, "verdict": VERDICT_INSUFFICIENT_HISTORY,
            "verdict_reason": ("calibration could not be computed; no rate fabricated"),
            "error": str(exc)[:200],
            "persistence": _persistence_block(),
            "doctrine": "v11: calibration unavailable; no fabricated verdict emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_receipt(sample: int = DEFAULT_SAMPLE, k: int = DEFAULT_K,
                   ns: str = "a11oy") -> dict:
    """POST /brain/retro/receipt — compute the calibration record and mint exactly ONE
    unsigned SHA-256 content-digest receipt over it (RECEIPT-ON-WRITE). Never 500s."""
    try:
        result = evaluate(sample=sample, k=k, ns=ns)
        return {
            "ok": True,
            "endpoint": "brain/retro/receipt",
            "surface_id": SURFACE_ID,
            "label": result.get("label", LBL_MODELED),
            "ns": ns,
            "verdict": result.get("verdict"),
            "verdict_reason": result.get("verdict_reason"),
            "summary": result.get("summary"),
            "calibration": result.get("calibration"),
            "entries": result.get("entries"),
            "history_entries": result.get("history_entries"),
            "ledger_status": result.get("ledger_status"),
            "receipt": content_receipt(result),
            "persistence": _persistence_block(),
            "receipt_policy": ("RECEIPT-ON-WRITE — this POST minted exactly ONE unsigned "
                               "SHA-256 content digest over the calibration record."),
            "doctrine": _doctrine_block(
                "unsigned content digest over the calibration record; no signature, no "
                "proof claimed. Λ = Conjecture 1, never a theorem."),
            "timestamp_utc": _now_iso(),
        }
    except Exception as exc:
        return {
            "ok": False, "endpoint": "brain/retro/receipt", "label": LBL_UNAVAILABLE,
            "surface_id": SURFACE_ID, "verdict": VERDICT_INSUFFICIENT_HISTORY,
            "error": str(exc)[:200],
            "doctrine": "v11: receipt unavailable; nothing minted, no verdict fabricated.",
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# FastAPI router registration.
#   GET  info/retro — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST receipt    — raw-Request handler via app.router.add_route (Starlette passes the
#                     Request positionally, version-proof under fastapi==0.137.x), with
#                     app.add_api_route as the fallback. The handler is annotated
#                     request: fastapi.Request. Registered BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #

def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/retro"

    # Honesty-manifest route: path segment == surface id, which is exactly how the
    # Honesty Wall / Frontier Index locate a surface's manifest in-process. Without it
    # the wall can read nothing about brainretro (segments of `brain/retro` are `brain`
    # and `retro`) and honestly marks it NO-MANIFEST. Declarative only; mints nothing.
    manifest_path = f"/api/{ns}/v1/brain/{SURFACE_ID}/manifest"

    @app.get(manifest_path)
    def _brainretro_manifest():
        """brainretro's OWN honesty manifest, readable by the Honesty Wall (pure read)."""
        return JSONResponse(handle_manifest(ns))

    @app.get(f"{base}/info")
    def _brainretro_info():
        """Self-describing brain-retro manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainretro_retro(sample: int = DEFAULT_SAMPLE, k: int = DEFAULT_K):
        """Retrospective calibration record (pure read; mints nothing)."""
        return JSONResponse(handle_retro(sample=sample, k=k, ns=ns))

    async def _brainretro_receipt(request):
        """POST: compute the calibration record + mint ONE unsigned SHA-256 content
        digest over it (RECEIPT-ON-WRITE). A missing/malformed body falls back to the
        defaults — never a fabricated verdict."""
        sample, k = DEFAULT_SAMPLE, DEFAULT_K
        try:
            raw = await request.body()
            if raw:
                body = json.loads(raw)
                if isinstance(body, dict):
                    if body.get("sample") is not None:
                        sample = int(body["sample"])
                    if body.get("k") is not None:
                        k = int(body["k"])
        except Exception:  # a malformed body still answers honestly, never a 500
            sample, k = DEFAULT_SAMPLE, DEFAULT_K
        return JSONResponse(handle_receipt(sample=sample, k=k, ns=ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature
    # analysis (in the add_api_route fallback path) treats the param as the request
    # object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _brainretro_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rec_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rec_path, _brainretro_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rec_path, _brainretro_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rec_path, _brainretro_receipt,
                                           methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainretro receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainretro-wired:3(get-only)"

    return "brainretro-wired:4"


# --------------------------------------------------------------------------- #
# Self-test — honest INSUFFICIENT-HISTORY default, honest drift, receipt on write only.
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys as _sys
    import types as _types

    print("=" * 72)
    print("szl_brainretro — self-test (retrospective calibration of past answers)")
    print("=" * 72)

    def _stub_siblings(entries, ground_map):
        qa = _types.ModuleType("szl_brainqueryaudit")
        qa._ledger = lambda ns: list(entries)
        bg = _types.ModuleType("szl_brainground")

        def _evaluate(q, k=12, ns="a11oy"):
            v = ground_map.get(q)
            if v is None:
                return {"ok": False, "verdict": "INSUFFICIENT-GROUNDING"}
            return {"ok": True, "verdict": v, "grounding_confidence": 0.5}

        bg.evaluate = _evaluate
        _sys.modules["szl_brainqueryaudit"] = qa
        _sys.modules["szl_brainground"] = bg

    def _drop_siblings():
        _sys.modules.pop("szl_brainqueryaudit", None)
        _sys.modules.pop("szl_brainground", None)

    # 1) empty ledger -> INSUFFICIENT-HISTORY (the honest default on a fresh process).
    _stub_siblings([], {})
    r = evaluate(ns="selftest")
    assert r["verdict"] == VERDICT_INSUFFICIENT_HISTORY, r["verdict"]
    assert r["calibration"]["calibration_rate"] is None, "no rate on empty history"
    assert "receipt" not in r, "GET must mint nothing (receipt-on-write)"
    print(f"[1] empty ledger => {r['verdict']}, no rate fabricated, GET mints "
          f"nothing  OK")

    # 2) CONFIRMED + DRIFTED classification over a stubbed ledger + stubbed grounding.
    #    (Λ is Conjecture 1, never a theorem — a detected drift changes no proof posture.)
    entries = [
        {"seq": 0, "query": "a", "returned_verdict": "GROUNDED"},
        {"seq": 1, "query": "b", "returned_verdict": "GROUNDED"},
        {"seq": 2, "query": "c", "returned_verdict": "INSUFFICIENT-GROUNDING"},
    ]
    _stub_siblings(entries, {"a": "GROUNDED", "b": "INSUFFICIENT-GROUNDING",
                             "c": "INSUFFICIENT-GROUNDING"})
    r = evaluate(ns="selftest")
    kinds = [e["classification"] for e in r["entries"]]
    assert kinds == [CLS_CONFIRMED, CLS_DRIFTED, CLS_CONFIRMED], kinds
    assert r["verdict"] == VERDICT_DRIFT_DETECTED, r["verdict"]
    assert r["entries"][1]["drift_direction"] == DRIFT_OVER_CLAIM
    assert r["calibration"]["abstention_justified_rate"] == 1.0
    assert r["calibration"]["modeled_calibration"] <= TRUST_CEILING
    print(f"[2] stubbed ledger: {kinds} => {r['verdict']} "
          f"(over-claim drift surfaced)  OK")

    # 3) grounding not recomputable -> STALE-UNKNOWN; never counted correct.
    _stub_siblings(entries, {})  # every evaluate() degrades ok=False
    r = evaluate(ns="selftest")
    assert all(e["classification"] == CLS_STALE_UNKNOWN for e in r["entries"])
    assert r["verdict"] == VERDICT_INSUFFICIENT_HISTORY
    assert r["calibration"]["calibration_rate"] is None
    print(f"[3] unrecomputable grounding => all STALE-UNKNOWN, {r['verdict']}, no past "
          f"answer claimed correct  OK")

    # 4) siblings absent -> UNAVAILABLE label, never a fabricated ledger.
    _drop_siblings()
    import builtins as _builtins
    _real_import = _builtins.__import__

    def _blocked(name, *a, **kw):
        if name in ("szl_brainqueryaudit", "szl_brainground"):
            raise ImportError(f"{name} blocked for self-test")
        return _real_import(name, *a, **kw)

    _builtins.__import__ = _blocked
    try:
        r = evaluate(ns="selftest")
    finally:
        _builtins.__import__ = _real_import
    assert r["label"] == LBL_UNAVAILABLE and r["ok"] is False
    assert r["verdict"] == VERDICT_INSUFFICIENT_HISTORY
    print(f"[4] ledger sibling absent => label={r['label']}, {r['verdict']}, no history "
          f"invented  OK")

    # 5) receipt is deterministic and only minted on write.
    _stub_siblings(entries, {"a": "GROUNDED", "b": "GROUNDED",
                             "c": "INSUFFICIENT-GROUNDING"})
    res = evaluate(ns="selftest")
    d1 = content_receipt(res)["content_sha256"]
    d2 = content_receipt(res)["content_sha256"]
    assert d1 == d2 and len(d1) == 64
    got = handle_receipt(ns="selftest")
    assert got["receipt"]["signed"] is False
    assert got["receipt"]["algorithm"] == "sha256"
    assert "receipt" not in handle_retro(ns="selftest")
    print(f"[5] receipt deterministic sha256 on write, nothing on GET  OK")

    # 6) doctrine: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 (never 100%).
    info = handle_info("selftest")
    d = info["doctrine"]
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0 and d["sentience_claim"] is False
    assert info["persistence"]["durable"] is False
    assert VERDICT_INSUFFICIENT_HISTORY in info["ephemeral_ledger_caveat"]
    assert LBL_MODELED in HONEST_LABELS
    print("[6] ephemeral caveat stated in /info; doctrine: locked-8 exact, +0, "
          "Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    # 7) the honesty manifest the wall reads: MODELED verbatim, doctrine invariants true,
    #    every declared honesty invariant asserted True, and the path segment == surface id.
    man = handle_manifest("selftest")
    assert man["label"] == LBL_MODELED and man["data_label"] == LBL_MODELED
    assert "MEASURED" not in (man["label"], man["data_label"])
    md = man["doctrine"]
    assert md["locked_proven"] == 8 and md["adds_to_locked_8"] == 0
    assert md["lambda"] == "Conjecture 1" and md["trust_ceiling"] <= 0.97
    assert md["trust_100_percent"] is False and md["sentience_claim"] is False
    assert 0.0 <= man["provenance_coverage"] <= 1.0
    assert all(v is True for v in man["honesty_invariants"].values())
    assert man["honesty_invariants"]["no_consciousness_claim"] is True
    assert EPHEMERAL_CAVEAT in man["ephemeral_ledger_caveat"]
    assert man["persistence"]["durable"] is False
    _wall_path = f"/api/selftest/v1/brain/{SURFACE_ID}/manifest"
    assert SURFACE_ID in [s for s in _wall_path.split("/") if s]
    print("[7] honesty manifest at an id-segment path: label MODELED (verbatim), "
          "doctrine invariants true, ephemeral caveat carried  OK")

    _drop_siblings()
    print("\nok:true checks:7")
    _sys.exit(0)
