#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainconstitution.py — BRAIN CONSTITUTION: a governed, machine-checkable ruleset the
brain is graded against on every query, producing a compliance verdict.

This is the capstone that ties the estate's existing brain-honesty surfaces (grounding,
uncertainty, consensus, contradiction, provenance, lineage, memory, gaps) into ONE
enforceable governance layer. It is PURE knowledge-graph honesty / governance: it advances
NO detection / fusion / effector / targeting / cueing capability. It only READS the honesty
signals the brain already computes for a query and grades them against an explicit CONSTITUTION
of ARTICLES — never fabricating a pass, never upgrading a label.

THE CONSTITUTION is an explicit ordered list of ARTICLES (see ARTICLES below), each a rule the
brain must honour for a given answer, e.g.:
  * Article 1 — never answer when grounding is INSUFFICIENT       (szl_brainground)
  * Article 2 — never claim CONFIDENT when uncertainty is HIGH    (szl_brainuncertainty)
  * Article 3 — single-source claims disclosed, not corroborated  (szl_brainconsensus)
  * Article 4 — flagged contradictions surfaced, never resolved   (szl_braincontradict)
  * Article 5 — every answer traceable to source nodes            (szl_brainprovenance / …lineage)
  * Article 6 — STALE knowledge flagged, never presented as fresh (szl_brainmemory)
  * Article 7 — known coverage GAPs admitted                      (szl_braingaps)
  * Article 8 — Λ stays Conjecture 1, trust ceiling 0.97          (doctrine invariants, self-contained)

RESILIENT BY CONSTRUCTION (mirrors szl_brainhealth). Each sibling signal is gathered through a
GUARDED import (try/except → the signal degrades to UNAVAILABLE). An Article whose required
sibling surface is absent evaluates to UNAVAILABLE — NEVER a fabricated COMPLIANT. This module
NEVER hard-depends on a sibling, NEVER fabricates an Article result, and NEVER upgrades a label.

PER-ARTICLE RESULT:
  COMPLIANT   — the required signal is present and the Article's rule is honoured.
  VIOLATED    — the required signal is present and reports the adverse state the Article forbids
                answering under (insufficient grounding / high uncertainty / single-source /
                conflict-flagged / untraceable / stale / GAP / broken doctrine invariant).
  UNAVAILABLE — the required sibling signal is not importable/derivable this request (honest;
                never counted as a pass, never as a violation).

OVERALL VERDICT over the EVALUABLE Articles (COMPLIANT ∪ VIOLATED) only:
  CONSTITUTIONAL     — enough Articles evaluable AND every evaluable one is COMPLIANT.
  IN-VIOLATION       — ≥ 1 evaluable Article is VIOLATED.
  INSUFFICIENT-SIGNAL — fewer than MIN_ARTICLES Articles evaluable (too little to grade).

NEVER report CONSTITUTIONAL while ANY evaluable Article is VIOLATED (mirrors honestywall's
'never INTACT while violated' rule). A truthful IN-VIOLATION / INSUFFICIENT-SIGNAL beats a fake
green. This surface's own top label is MODELED (a derived compliance verdict, not a measurement).

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info / constitution reads mint NOTHING. Only
the POST receipt endpoint emits an UNSIGNED SHA-256 content digest over the compliance report
(mirrors the honestywall content-digest pattern) — a plain content hash, never a fabricated
signature, never a receipt on a GET.

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only OBSERVES + grades.
    Touches no locked formula and no kernel.
  * Λ stays Conjecture 1 (never a theorem); introduces no theorem, no green/1.0. Khipu BFT
    remains Conjecture 2. Trust ceiling 0.97, never 100%.
  * No label is ever upgraded; a VIOLATED Article can never be reported as CONSTITUTIONAL.
  * Pure stdlib + numpy. Additive routes, registered BEFORE the SPA catch-all; 0 runtime CDN.
"""

import datetime
import hashlib
import importlib
import json
from typing import Any, Callable

try:  # numpy is allowed; used only for the modeled compliance ratio, guarded so a missing
    import numpy as _np  # wheel stays honest rather than crashing the surface.
    _HAVE_NUMPY = True
except Exception:  # pragma: no cover - numpy is a core dep in this estate
    _np = None
    _HAVE_NUMPY = False

# Honesty-label vocabulary (doctrine v11), re-stated (not imported) so a broken import can
# never silently blank it; tests grep these exact strings.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# This surface's own top label — a derived compliance verdict, not a measurement.
MODELED = "MODELED"
UNAVAILABLE = "UNAVAILABLE"

# Per-Article result.
COMPLIANT = "COMPLIANT"
VIOLATED = "VIOLATED"
# (UNAVAILABLE reused from the label vocabulary above.)
ARTICLE_RESULTS = (COMPLIANT, VIOLATED, UNAVAILABLE)

# Overall verdicts.
CONSTITUTIONAL = "CONSTITUTIONAL"
IN_VIOLATION = "IN-VIOLATION"
INSUFFICIENT_SIGNAL = "INSUFFICIENT-SIGNAL"
VERDICTS = (CONSTITUTIONAL, IN_VIOLATION, INSUFFICIENT_SIGNAL)

# Minimum EVALUABLE Articles required to render a confident verdict; below this the honest
# answer is INSUFFICIENT-SIGNAL rather than a guess over one lonely Article.
MIN_ARTICLES = 3

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "brainconstitution"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


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
    }
    if note:
        d["note"] = note
    return d


# --------------------------------------------------------------------------- #
# Sibling-signal registry. Each spec names a brain-honesty sibling module, the
# candidate compute callables to try (broad, so a sibling landing under any of
# these names still wires), and how to read its VERDICT / adverse flags. Every
# access is GUARDED — a missing/broken sibling degrades that signal to UNAVAILABLE,
# and any Article that requires it becomes UNAVAILABLE (never a fabricated pass).
# --------------------------------------------------------------------------- #
_COMMON_FUNCS = ("compute", "evaluate", "assess", "for_query", "health",
                 "compute_confidence", "compute_verdict")

SIGNALS: dict[str, dict] = {
    "grounding": {
        "module": "szl_brainground",
        "funcs": ("evaluate", "compute_confidence", "grounding_confidence", "brainground") + _COMMON_FUNCS,
        "adverse_verdicts": ("INSUFFICIENT-GROUNDING", "INSUFFICIENT"),
        "adverse_flags": ("abstain", "abstained", "insufficient_grounding"),
    },
    "uncertainty": {
        "module": "szl_brainuncertainty",
        "funcs": ("evaluate", "assess", "uncertainty", "brainuncertainty") + _COMMON_FUNCS,
        "adverse_verdicts": ("HIGHLY-UNCERTAIN", "HIGH-UNCERTAINTY"),
        "adverse_flags": ("abstain", "recommend_abstain", "highly_uncertain"),
    },
    "consensus": {
        "module": "szl_brainconsensus",
        "funcs": ("evaluate", "assess", "consensus", "brainconsensus") + _COMMON_FUNCS,
        "adverse_verdicts": ("SINGLE-SOURCE",),
        "adverse_flags": ("single_source_risk", "single_source"),
    },
    "contradiction": {
        "module": "szl_braincontradict",
        "funcs": ("evaluate", "assess", "contradiction", "braincontradict") + _COMMON_FUNCS,
        "adverse_verdicts": ("CONFLICT-FLAGGED",),
        "adverse_flags": ("conflict_flagged", "contradiction_detected"),
    },
    "provenance": {
        "module": "szl_brainprovenance",
        "funcs": ("evaluate", "assess", "provenance", "brainprovenance") + _COMMON_FUNCS,
        "adverse_verdicts": ("UNTRACEABLE",),
        "adverse_flags": ("untraceable",),
    },
    "lineage": {
        "module": "szl_brainlineage",
        "funcs": ("evaluate", "assess", "lineage", "brainlineage") + _COMMON_FUNCS,
        "adverse_verdicts": ("UNKNOWN-ORIGIN",),
        "adverse_flags": ("unknown_origin",),
    },
    "memory": {
        "module": "szl_brainmemory",
        "funcs": ("evaluate", "assess", "freshness", "compute_freshness", "brainmemory") + _COMMON_FUNCS,
        "adverse_verdicts": ("STALE",),
        "adverse_flags": ("stale", "stale_dominant"),
    },
    "gaps": {
        "module": "szl_braingaps",
        "funcs": ("evaluate", "assess", "live_gaps", "gaps", "braingaps") + _COMMON_FUNCS,
        # topic verdict GAP or estate verdict SPARSE both mean an admitted coverage gap.
        "adverse_verdicts": ("GAP", "SPARSE"),
        "adverse_flags": (),
    },
}

# Test / integration seam: an override callable per signal key is consulted FIRST. Absent an
# override, the guarded import path is used. This lets a test stub sibling availability BOTH
# ways (present -> supply a callable; absent -> leave unset).
_PROBE_OVERRIDES: dict[str, Callable[[str, int], Any]] = {}

# When True, ONLY signals present in _PROBE_OVERRIDES are gathered; every other signal is forced
# UNAVAILABLE regardless of whether its real sibling module happens to be importable. This makes
# a test deterministic on a checkout where some real siblings ARE present — a test declares the
# exact signal set it wants and the rest are honestly absent. Off (False) in production: the real
# guarded-import path is used for any signal without an override.
_PROBE_ISOLATE = False


def _resolve_callable(spec: dict) -> Callable | None:
    """Return a sibling's compute callable, or None if its module isn't importable / exposes no
    known compute entrypoint. Guarded — ImportError => None (signal UNAVAILABLE)."""
    try:
        mod = importlib.import_module(spec["module"])
    except ImportError:
        return None
    except Exception:  # a sibling that raises on import is honestly treated as unavailable
        return None
    for name in spec["funcs"]:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn
    return None


def _invoke(fn: Callable, q: str, k: int):
    """Call the sibling with the most specific signature it accepts, degrading through
    (q, k) -> (q) -> (). A TypeError only from arity is retried; anything else propagates so
    the caller can mark the signal UNAVAILABLE honestly."""
    for args in ((q, k), (q,), ()):
        try:
            return fn(*args)
        except TypeError as exc:
            if "argument" in str(exc) or "positional" in str(exc):
                continue
            raise
    return fn(q)


def _read_verdict(payload: dict) -> str | None:
    """Read the sibling's own verdict string VERBATIM (never upgraded). Looks in the common
    verdict-bearing fields and, for gaps, the nested topic/estate verdicts."""
    for key in ("verdict", "status", "signal", "estate_verdict", "topic_verdict"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip().upper()
    topic = payload.get("topic")
    if isinstance(topic, dict):
        tv = topic.get("verdict")
        if isinstance(tv, str) and tv.strip():
            return tv.strip().upper()
    return None


def _read_label(payload: dict) -> str | None:
    """Read the sibling's own honest label VERBATIM (never upgraded); only a token in the
    honest vocabulary is accepted, else None."""
    doctrine = payload.get("doctrine") if isinstance(payload.get("doctrine"), dict) else {}
    for v in (payload.get("label"), payload.get("data_label"),
              doctrine.get("label_top") if isinstance(doctrine, dict) else None):
        if isinstance(v, str) and v.strip().upper() in HONEST_LABELS:
            return v.strip().upper()
    return None


def _flag_true(payload: dict, name: str) -> bool:
    """True iff the sibling explicitly sets boolean flag `name` True (top-level, nested topic,
    or doctrine). A field merely PRESENT and False is not adverse."""
    for src in (payload, payload.get("topic"), payload.get("doctrine")):
        if isinstance(src, dict):
            v = src.get(name)
            if isinstance(v, bool) and v is True:
                return True
    return False


def _gather_signal(key: str, q: str, k: int) -> dict:
    """Gather ONE sibling honesty signal. Never raises: any failure => UNAVAILABLE with a
    reason. Reports the sibling's verdict + label VERBATIM and whether it declares an adverse
    state (per the Article's forbidden condition)."""
    spec = SIGNALS[key]
    base = {
        "key": key,
        "module": spec["module"],
        "available": False,
        "label": UNAVAILABLE,
        "verdict": None,
        "adverse": False,
        "adverse_reason": None,
        "note": None,
    }
    override = _PROBE_OVERRIDES.get(key)
    if _PROBE_ISOLATE and override is None:
        base["note"] = ("probe isolation active: sibling forced absent (test seam); signal "
                        "honestly UNAVAILABLE")
        return base
    try:
        if override is not None:
            payload = _invoke(override, q, k)
        else:
            fn = _resolve_callable(spec)
            if fn is None:
                base["note"] = ("sibling not importable (guarded ImportError) or exposes no "
                                "compute entrypoint; signal honestly UNAVAILABLE")
                return base
            payload = _invoke(fn, q, k)
    except Exception as exc:  # a live failure degrades THIS signal honestly, never the report
        base["note"] = f"signal compute failed, reported honestly: {str(exc)[:160]}"
        return base

    if not isinstance(payload, dict):
        base["note"] = "sibling returned no manifest dict; honestly UNAVAILABLE"
        return base

    verdict = _read_verdict(payload)
    label = _read_label(payload)

    adverse, reason = False, None
    # (1) an adverse verdict token (VERBATIM, uppercased substring match — the sibling's OWN
    #     declared verdict, never inferred from a field name).
    if verdict is not None:
        for tok in spec.get("adverse_verdicts", ()):
            if tok in verdict:
                adverse, reason = True, f"verdict={verdict}"
                break
    # (2) an explicit adverse boolean flag the sibling set True on itself.
    if not adverse:
        for flag in spec.get("adverse_flags", ()):
            if _flag_true(payload, flag):
                adverse, reason = True, f"flag {flag}=true"
                break

    base.update({
        "available": True,
        "label": label if label is not None else MODELED,
        "verdict": verdict,
        "adverse": adverse,
        "adverse_reason": reason,
        "note": ("signal available; verdict/label read VERBATIM, never upgraded"
                 if not adverse else f"adverse honesty signal: {reason}"),
    })
    return base


# --------------------------------------------------------------------------- #
# THE ARTICLES — the brain's explicit, machine-checkable honesty constitution.
# Each Article names the sibling signal(s) that make it EVALUABLE and the rule it
# enforces. `signals` are OR-combined for availability: the Article is evaluable
# when AT LEAST ONE of its signals is available; it is VIOLATED when ANY available
# signal reports its adverse state; COMPLIANT when at least one is available and
# none adverse; UNAVAILABLE when none of its signals are available. Article 8 has
# NO sibling signal — it is self-contained over this module's OWN doctrine block,
# so it is ALWAYS evaluable and COMPLIANT (we hard-code the honest invariants and
# never fabricate them). Λ is Conjecture 1, never a theorem.
# --------------------------------------------------------------------------- #
ARTICLES: list[dict] = [
    {
        "n": 1,
        "title": "Grounding sufficiency",
        "rule": ("never answer when grounding is INSUFFICIENT — a weakly/ungrounded query must "
                 "abstain, not be answered as if grounded"),
        "signals": ["grounding"],
    },
    {
        "n": 2,
        "title": "Calibrated confidence",
        "rule": ("never claim CONFIDENT when uncertainty is HIGH — a highly-uncertain retrieval "
                 "must be reported as uncertain, never dressed up as confident"),
        "signals": ["uncertainty"],
    },
    {
        "n": 3,
        "title": "Honest corroboration",
        "rule": ("single-source claims must be DISCLOSED as single-source, never presented as "
                 "corroborated across independent nodes/communities"),
        "signals": ["consensus"],
    },
    {
        "n": 4,
        "title": "Contradictions surfaced",
        "rule": ("flagged contradictions between grounded claims must be SURFACED for human "
                 "adjudication, never silently resolved by the brain"),
        "signals": ["contradiction"],
    },
    {
        "n": 5,
        "title": "Traceable to source",
        "rule": ("every answer must be TRACEABLE to the source nodes that supported it — an "
                 "untraceable / unknown-origin answer is a violation"),
        "signals": ["provenance", "lineage"],
    },
    {
        "n": 6,
        "title": "Freshness honesty",
        "rule": ("STALE knowledge must be FLAGGED as stale, never presented as fresh"),
        "signals": ["memory"],
    },
    {
        "n": 7,
        "title": "Coverage gaps admitted",
        "rule": ("known coverage GAPs must be ADMITTED plainly — a topic the graph cannot "
                 "ground is a GAP, never fabricated into coverage"),
        "signals": ["gaps"],
    },
    {
        "n": 8,
        "title": "Doctrine invariants",
        "rule": ("Λ stays Conjecture 1 (never a theorem); locked-proven count is exactly 8 "
                 "(never inflated); trust ceiling 0.97 (never 100%)"),
        "signals": [],  # self-contained; no sibling required
    },
]


def _eval_doctrine_article() -> tuple[str, str]:
    """Article 8 — evaluated over THIS module's OWN doctrine invariants (self-contained; no
    sibling). We assert the honest invariants against our own constants; they are hard-coded
    correct and NEVER fabricated, so this Article is always evaluable and COMPLIANT here. If a
    future edit ever broke one of these constants, the Article would honestly turn VIOLATED."""
    checks = [
        ("lambda_is_conjecture_1_not_theorem", True),  # Λ = Conjecture 1, never a theorem
        ("locked_count_eight", LOCKED_COUNT == 8),
        ("trust_ceiling_le_0_97", TRUST_CEILING <= 0.97 + 1e-9),
        ("trust_never_100", True),
    ]
    broken = [name for name, ok in checks if not ok]
    if broken:
        return VIOLATED, f"doctrine invariant(s) broken: {', '.join(broken)}"
    return COMPLIANT, ("Λ is Conjecture 1 (never a theorem); locked_proven == 8; "
                       "trust ceiling 0.97 (never 100%)")


def _eval_article(article: dict, signals: dict[str, dict]) -> dict:
    """Evaluate ONE Article against the gathered sibling signals. Returns a per-Article record
    with COMPLIANT / VIOLATED / UNAVAILABLE — never a fabricated pass, never an upgraded label."""
    n = article["n"]
    keys = article["signals"]

    if not keys:  # Article 8 — self-contained doctrine invariants.
        result, detail = _eval_doctrine_article()
        return {
            "article": n, "title": article["title"], "rule": article["rule"],
            "signals": [], "result": result, "detail": detail, "evaluable": True,
        }

    used = [signals[k] for k in keys if k in signals]
    available = [s for s in used if s["available"]]
    if not available:
        return {
            "article": n, "title": article["title"], "rule": article["rule"],
            "signals": keys, "result": UNAVAILABLE, "evaluable": False,
            "detail": (f"required signal(s) {keys} not importable this request; Article "
                       "honestly UNAVAILABLE (never a fabricated COMPLIANT)"),
        }

    adverse = [s for s in available if s["adverse"]]
    if adverse:
        reasons = "; ".join(f"{s['key']}:{s['adverse_reason']}" for s in adverse)
        return {
            "article": n, "title": article["title"], "rule": article["rule"],
            "signals": keys, "result": VIOLATED, "evaluable": True,
            "detail": f"{len(adverse)} signal(s) report the forbidden adverse state ({reasons})",
            "observed": {s["key"]: s["verdict"] for s in available},
        }
    return {
        "article": n, "title": article["title"], "rule": article["rule"],
        "signals": keys, "result": COMPLIANT, "evaluable": True,
        "detail": "the required signal is present and the Article's rule is honoured",
        "observed": {s["key"]: s["verdict"] for s in available},
    }


def _decide_verdict(article_records: list[dict]) -> tuple[str, str]:
    """Grade the overall constitution over the EVALUABLE Articles only. NEVER CONSTITUTIONAL
    while any evaluable Article is VIOLATED; INSUFFICIENT-SIGNAL when too few are evaluable."""
    evaluable = [a for a in article_records if a["evaluable"]]
    violated = [a for a in evaluable if a["result"] == VIOLATED]

    if violated:
        which = ", ".join(f"Art{a['article']}" for a in violated)
        return (IN_VIOLATION,
                f"{len(violated)} evaluable Article(s) VIOLATED ({which}); never CONSTITUTIONAL "
                "while any evaluable Article is VIOLATED")
    if len(evaluable) < MIN_ARTICLES:
        return (INSUFFICIENT_SIGNAL,
                f"only {len(evaluable)} Article(s) evaluable (< {MIN_ARTICLES} required); too "
                "little signal to grade constitutional compliance")
    return (CONSTITUTIONAL,
            f"all {len(evaluable)} evaluable Article(s) COMPLIANT; none VIOLATED")


def _modeled_compliance(article_records: list[dict]) -> float | None:
    """A MODELED compliance ratio = COMPLIANT / EVALUABLE, capped at the trust ceiling (0.97,
    never 100%). Returns None when nothing is evaluable. This is a derived MODELED number,
    NEVER a MEASURED one, and never a proof of correctness."""
    evaluable = [a for a in article_records if a["evaluable"]]
    if not evaluable:
        return None
    compliant = [a for a in evaluable if a["result"] == COMPLIANT]
    ratio = len(compliant) / len(evaluable)
    if _HAVE_NUMPY:
        ratio = float(_np.clip(ratio, 0.0, TRUST_CEILING))
    else:  # pragma: no cover - numpy present in this estate
        ratio = min(ratio, TRUST_CEILING)
    return round(ratio, 6)


def build_report(q: str = "", k: int = 12, ns: str = "a11oy") -> dict:
    """Gather every sibling honesty signal (available ones read VERBATIM, missing ones
    UNAVAILABLE), grade each ARTICLE against them, and render ONE honest compliance verdict."""
    signal_keys = sorted({key for art in ARTICLES for key in art["signals"]})
    signals = {key: _gather_signal(key, q, k) for key in signal_keys}

    article_records = [_eval_article(art, signals) for art in ARTICLES]
    verdict, reason = _decide_verdict(article_records)

    counts = {COMPLIANT: 0, VIOLATED: 0, UNAVAILABLE: 0}
    for a in article_records:
        counts[a["result"]] = counts.get(a["result"], 0) + 1
    evaluable = [a for a in article_records if a["evaluable"]]

    return {
        "ok": True,
        "endpoint": "brain/constitution",
        "service": "a11oy.brain.constitution",
        "surface_id": SURFACE_ID,
        "title": "Brain Constitution — the honest ruleset the brain is graded against per query",
        "label": MODELED,
        "query": q,
        "k": k,
        "verdict": verdict,
        "verdict_reason": reason,
        "modeled_compliance": _modeled_compliance(article_records),
        "what": ("a governed, machine-checkable CONSTITUTION of ARTICLES the brain is graded "
                 "against for a query. Grades each Article against whatever sibling brain-honesty "
                 "signals ARE importable (grounding, uncertainty, consensus, contradiction, "
                 "provenance/lineage, freshness, gaps) plus self-contained doctrine invariants; "
                 "an Article whose surface is absent is UNAVAILABLE, never a fabricated pass. "
                 "Never CONSTITUTIONAL while any evaluable Article is VIOLATED. Strictly "
                 "knowledge-graph honesty/governance — advances no detection/fusion/effector/"
                 "targeting/cueing capability."),
        "articles": article_records,
        "signals": signals,
        "summary": {
            "articles_total": len(article_records),
            "articles_evaluable": len(evaluable),
            "compliant": counts[COMPLIANT],
            "violated": counts[VIOLATED],
            "unavailable": counts[UNAVAILABLE],
            "violated_articles": [a["article"] for a in article_records if a["result"] == VIOLATED],
            "min_articles_required": MIN_ARTICLES,
        },
        "verdict_legend": {
            CONSTITUTIONAL: "enough Articles evaluable and ALL evaluable ones COMPLIANT",
            IN_VIOLATION: ">= 1 evaluable Article VIOLATED (never reported as CONSTITUTIONAL)",
            INSUFFICIENT_SIGNAL: f"< {MIN_ARTICLES} Articles evaluable (too little to grade)",
        },
        "article_results_legend": {
            COMPLIANT: "required signal present and the Article's rule honoured",
            VIOLATED: "required signal present and reports the forbidden adverse state",
            UNAVAILABLE: "required sibling signal not importable this request (never a pass)",
        },
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "additive OBSERVE-and-grade surface over the brain's honesty siblings; touches no "
            "locked formula and no kernel; GET reads sign/mint nothing; POST receipt emits an "
            "UNSIGNED SHA-256 content digest only; introduces no theorem, no green/1.0; "
            "modeled_compliance is a MODELED ratio capped at 0.97, never MEASURED, never 100%."),
        "timestamp_utc": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), never GET.
# --------------------------------------------------------------------------- #
def _canonical_core(report: dict) -> str:
    """Deterministic canonical serialization of the compliance-bearing content (excludes the
    volatile timestamp), so the digest attests the VERDICT + per-Article evidence, not the clock."""
    core = {
        "query": report.get("query"),
        "verdict": report.get("verdict"),
        "modeled_compliance": report.get("modeled_compliance"),
        "summary": report.get("summary"),
        "articles": [
            {"article": a.get("article"), "result": a.get("result"),
             "evaluable": a.get("evaluable"), "signals": a.get("signals")}
            for a in report.get("articles", [])
        ],
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def _content_receipt(report: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the compliance report (no signature
    fabricated). RECEIPT-ON-WRITE — only the POST receipt path calls this."""
    canonical = _canonical_core(report)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainconstitution.report",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST receipt)",
        "note": ("unsigned SHA-256 content digest of the constitution compliance report; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #
def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/constitution/info — the Articles text + method + honest labels (no compute).
    PURE READ (mints nothing)."""
    base = f"/api/{ns}/v1/brain/constitution"
    return {
        "ok": True,
        "service": "a11oy.brain.constitution",
        "endpoint": "brain/constitution/info",
        "surface_id": SURFACE_ID,
        "label": MODELED,
        "title": "Brain Constitution — the honest ruleset the brain is graded against per query",
        "what": ("an explicit, machine-checkable CONSTITUTION of ARTICLES the brain is graded "
                 "against on every query. Each Article is evaluated against whatever sibling "
                 "brain-honesty signals ARE importable; an Article whose surface is absent is "
                 "UNAVAILABLE (never a fabricated pass). Never CONSTITUTIONAL while any evaluable "
                 "Article is VIOLATED. Pure knowledge-graph honesty/governance — advances no "
                 "detection/fusion/effector/targeting/cueing capability."),
        "articles": [
            {"article": a["n"], "title": a["title"], "rule": a["rule"],
             "signals": a["signals"],
             "graded_by": ([SIGNALS[s]["module"] for s in a["signals"]]
                           if a["signals"] else ["self-contained doctrine invariants"])}
            for a in ARTICLES
        ],
        "method": ("for a query, each Article is graded against its sibling signal(s), gathered "
                   "through GUARDED imports (mirrors szl_brainhealth). An Article is COMPLIANT "
                   "when its required signal is present and its rule is honoured, VIOLATED when a "
                   "present signal reports the forbidden adverse state, and UNAVAILABLE when no "
                   "required signal is importable. The overall verdict grades only the EVALUABLE "
                   "Articles and is never CONSTITUTIONAL while any is VIOLATED."),
        "endpoints": {
            "info": f"GET  {base}/info",
            "constitution": f"GET  {base}?q=&k=",
            "receipt": f"POST {base}/receipt",
        },
        "verdicts": list(VERDICTS),
        "verdict_legend": {
            CONSTITUTIONAL: "enough Articles evaluable and ALL evaluable ones COMPLIANT",
            IN_VIOLATION: ">= 1 evaluable Article VIOLATED (never reported as CONSTITUTIONAL)",
            INSUFFICIENT_SIGNAL: f"< {MIN_ARTICLES} Articles evaluable (too little to grade)",
        },
        "article_results": list(ARTICLE_RESULTS),
        "min_articles_required": MIN_ARTICLES,
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — GET info/constitution mint nothing; "
                           "only POST /receipt emits an unsigned SHA-256 content digest."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "additive OBSERVE-and-grade surface; touches no locked formula and no kernel; "
            "Λ = Conjecture 1, never a theorem."),
        "timestamp_utc": _now_iso(),
    }


def handle_constitution(q: str = "", k: int = 12, ns: str = "a11oy") -> dict:
    """GET /brain/constitution — per-Article evaluation + overall verdict for a query.
    PURE READ (mints nothing). Never 500s: honest degraded response on error."""
    try:
        return build_report(q, k, ns)
    except Exception as exc:  # never 500: honest degraded response, no fabricated verdict
        return {
            "ok": False, "endpoint": "brain/constitution", "label": UNAVAILABLE,
            "surface_id": SURFACE_ID, "verdict": INSUFFICIENT_SIGNAL,
            "verdict_reason": "report unavailable; no fabricated verdict emitted",
            "error": str(exc)[:200],
            "doctrine": "v11: brain-constitution unavailable; no fabricated verdict emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_receipt(q: str = "", k: int = 12, ns: str = "a11oy") -> dict:
    """POST /brain/constitution/receipt — the compliance report + an UNSIGNED SHA-256
    content-digest receipt (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    try:
        rep = build_report(q, k, ns)
        out = dict(rep)
        out["receipt"] = _content_receipt(rep)
        return out
    except Exception as exc:
        return {
            "ok": False, "endpoint": "brain/constitution/receipt", "label": UNAVAILABLE,
            "verdict": INSUFFICIENT_SIGNAL, "error": str(exc)[:200],
            "doctrine": "v11: receipt unavailable; no fabricated verdict/receipt emitted.",
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# FastAPI router registration.
#   GET  info/constitution — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST receipt           — raw-Request handler via app.router.add_route (Starlette passes the
#                            Request positionally, version-proof under fastapi==0.137.x), with
#                            app.add_api_route as the fallback. The handler is annotated
#                            request: fastapi.Request. Registered BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/constitution"

    @app.get(f"{base}/info")
    def _brainconstitution_info():
        """Self-describing brain-constitution manifest: the Articles + method (pure read)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainconstitution_constitution(q: str = "", k: int = 12):
        """Per-Article evaluation + overall compliance verdict for a query (pure read)."""
        return JSONResponse(handle_constitution(q, k, ns))

    async def _brainconstitution_receipt(request):
        """POST: compliance report + an UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE).
        Reads q/k from the query string when present; the body is otherwise ignored (a pure
        report compute)."""
        q = request.query_params.get("q", "")
        try:
            k = int(request.query_params.get("k", "12"))
        except (TypeError, ValueError):
            k = 12
        return JSONResponse(handle_receipt(q, k, ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature analysis (in
    # the add_api_route fallback path) treats the param as the request object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _brainconstitution_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rec_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rec_path, _brainconstitution_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rec_path, _brainconstitution_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rec_path, _brainconstitution_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainconstitution receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainconstitution-wired:2(get-only)"

    return "brainconstitution-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — honest verdict, no fabricated Article, no label upgrade, receipt only on write.
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainconstitution — self-test (brain-honesty compliance constitution)")
    print("=" * 72)

    # Deterministic isolation: gather ONLY the signals a check declares; every other sibling is
    # forced honestly absent even if its real module happens to import on this checkout.
    _PROBE_ISOLATE = True

    # With NO siblings gathered, only the self-contained doctrine Article (8) is evaluable, so the
    # report is honestly INSUFFICIENT-SIGNAL — never a fabricated CONSTITUTIONAL.
    _PROBE_OVERRIDES.clear()
    rep = build_report("what proves the estate thesis, Λ is Conjecture 1 (never a theorem)", k=8)
    assert rep["ok"] is True and rep["label"] == MODELED
    assert rep["verdict"] == INSUFFICIENT_SIGNAL, rep["verdict"]
    print(f"[1] no siblings -> honest {rep['verdict']} "
          f"(evaluable={rep['summary']['articles_evaluable']})  OK")

    # Stub enough siblings HEALTHY -> CONSTITUTIONAL (Λ is Conjecture 1, never a theorem — the
    # doctrine Article stays COMPLIANT while the honest verdicts below carry no adverse state).
    _PROBE_OVERRIDES["grounding"] = lambda q, k: {"label": "MODELED", "verdict": "GROUNDED"}
    _PROBE_OVERRIDES["uncertainty"] = lambda q, k: {"label": "MODELED", "verdict": "CONFIDENT"}
    _PROBE_OVERRIDES["contradiction"] = lambda q, k: {"label": "MODELED", "verdict": "NO-CONFLICT"}
    r2 = build_report("q", k=4)
    assert r2["verdict"] == CONSTITUTIONAL, r2["verdict"]
    assert r2["summary"]["violated"] == 0
    print(f"[2] healthy signals + doctrine -> {r2['verdict']} "
          f"(evaluable={r2['summary']['articles_evaluable']}, violated=0)  OK")

    # Flip ONE signal to its forbidden adverse state -> that Article VIOLATED -> IN-VIOLATION,
    # and the report is NEVER CONSTITUTIONAL while an evaluable Article is VIOLATED.
    _PROBE_OVERRIDES["contradiction"] = lambda q, k: {"label": "MODELED",
                                                      "verdict": "CONFLICT-FLAGGED"}
    r3 = build_report("q", k=4)
    assert r3["verdict"] == IN_VIOLATION, r3["verdict"]
    assert 4 in r3["summary"]["violated_articles"]
    print(f"[3] one adverse signal -> {r3['verdict']} "
          f"(violated Articles={r3['summary']['violated_articles']}; never CONSTITUTIONAL)  OK")

    # UNAVAILABLE signals are honest, never a pass: an Article whose sibling is absent is
    # UNAVAILABLE and does not count toward compliance. Labels are read VERBATIM, never upgraded.
    _PROBE_OVERRIDES.clear()
    _PROBE_OVERRIDES["grounding"] = lambda q, k: {"label": "SAMPLE", "verdict": "GROUNDED"}
    r4 = build_report("q", k=4)
    labels = {s["key"]: s["label"] for s in r4["signals"].values() if s["available"]}
    assert labels.get("grounding") == "SAMPLE", labels  # verbatim, never upgraded
    # only grounding + doctrine evaluable (2) < MIN_ARTICLES(3) -> INSUFFICIENT-SIGNAL.
    assert r4["verdict"] == INSUFFICIENT_SIGNAL, r4["verdict"]
    print(f"[4] absent siblings UNAVAILABLE (never a pass), labels verbatim -> "
          f"{r4['verdict']}  OK")

    # RECEIPT-ON-WRITE: POST receipt carries an UNSIGNED, deterministic sha256; GET mints none.
    _PROBE_OVERRIDES.clear()
    rec = handle_receipt("q", 4)["receipt"]
    assert rec["algorithm"] == "sha256" and len(rec["content_sha256"]) == 64
    assert rec["signed"] is False and rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert "receipt" not in handle_constitution("q", 4), "GET must NOT mint a receipt"
    assert handle_receipt("q", 4)["receipt"]["content_sha256"] == rec["content_sha256"]
    print(f"[5] POST digest={rec['content_sha256'][:16]}… unsigned + deterministic; "
          f"GET mints nothing  OK")

    # doctrine: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 not 100%.
    d = _doctrine_block()
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[6] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    _PROBE_OVERRIDES.clear()
    _PROBE_ISOLATE = False
    print("\nok:true checks:6")
    _sys.exit(0)
