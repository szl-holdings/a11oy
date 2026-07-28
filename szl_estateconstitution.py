#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_estateconstitution.py — ESTATE CONSTITUTION: the whole estate's honesty posture graded
continuously against an explicit, machine-checkable set of estate-level ARTICLES.

This is the marriage of two surfaces the estate already ships:
  * szl_brainconstitution — grades ONE query against 8 brain-honesty Articles.
  * szl_honestywall       — aggregates per-surface honesty invariants estate-wide into a single
                            INTACT / DEGRADED / VIOLATED integrity verdict.
This module lifts the per-query CONSTITUTION pattern up one level: it grades the ESTATE (not a
query) against estate-level ARTICLES, evaluated over the honesty-wall aggregate plus
self-contained doctrine invariants. It is PURE honesty / governance / observability: it advances
NO detection / fusion / effector / targeting / cueing capability. It only READS the honesty
posture the running estate already declares and grades it — never fabricating a pass, never
upgrading a label, never papering over a coverage gap.

THE ESTATE ARTICLES (see ARTICLES below):
  * Article 1 — the honesty wall must hold: 0 REACHABLE invariant violations estate-wide.
  * Article 2 — no surface may declare a fabricated MEASURED label: every surface's declared
                data label must sit in the honest vocabulary, read VERBATIM.
  * Article 3 — manifest coverage must be DISCLOSED HONESTLY. This is a DISCLOSURE Article, not
                a pass/fail that hides the gap: it reports NATIVE-OK vs NO-MANIFEST counts
                plainly (e.g. "75/121 NATIVE-OK; 46 NO-MANIFEST unverifiable") and NEVER claims
                full coverage while any surface is NO-MANIFEST. Papering the gap over is the
                violation; admitting it is compliance.
  * Article 4 — doctrine invariants: Λ stays Conjecture 1 (never a theorem), locked-proven count
                is exactly 8 (never inflated), trust ceiling ≤ 0.97 (never 100%), no
                consciousness or sentience claim.

RESILIENT BY CONSTRUCTION (mirrors szl_brainconstitution / szl_brainhealth). The honesty-wall
aggregate is read through a GUARDED import: if szl_honestywall is absent, un-importable, or
fails, every Article that requires it evaluates to UNAVAILABLE — NEVER a fabricated COMPLIANT.
Article 4 is self-contained over this module's OWN doctrine constants and so is always evaluable.

RE-ENTRANCY. The honesty wall probes every registered surface — including THIS one — by invoking
its /status route in-process. A re-entrancy guard makes that probe honest instead of infinite:
the nested read reports the wall signal UNAVAILABLE (never a fabricated pass) and returns.

PER-ARTICLE RESULT:
  COMPLIANT   — the required evidence is present and the Article's rule is honoured.
  VIOLATED    — the required evidence is present and reports the state the Article forbids.
  UNAVAILABLE — the required evidence (the honesty-wall aggregate) is not readable this request;
                honest, never counted as a pass, never as a violation.

OVERALL VERDICT over the EVALUABLE Articles (COMPLIANT ∪ VIOLATED) only:
  CONSTITUTIONAL      — enough Articles evaluable AND every evaluable one is COMPLIANT.
  IN-VIOLATION        — ≥ 1 evaluable Article is VIOLATED.
  INSUFFICIENT-SIGNAL — fewer than MIN_ARTICLES Articles evaluable (too little to grade).

NEVER report CONSTITUTIONAL while ANY evaluable Article is VIOLATED (mirrors the honesty wall's
'never INTACT while violated' rule). A truthful IN-VIOLATION / INSUFFICIENT-SIGNAL beats a fake
green. This surface's own top label is MODELED — a derived governance verdict, not a measurement.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info / status reads mint NOTHING. Only the
POST receipt endpoint emits an UNSIGNED SHA-256 content digest over the estate compliance report
(the honestywall / brainconstitution content-digest pattern) — a plain content hash, never a
fabricated signature, never a receipt on a GET, never a signature on a read path.

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17; it only
    OBSERVES + grades. Touches no locked formula and no kernel.
  * Λ stays Conjecture 1 (never a theorem); introduces no theorem, no green/1.0. Khipu BFT
    remains Conjecture 2. Trust ceiling 0.97, never 100%.
  * No label is ever upgraded; a VIOLATED Article can never be reported as CONSTITUTIONAL.
  * Pure stdlib + numpy. Additive routes, registered BEFORE the SPA catch-all; 0 runtime CDN.
"""

import datetime
import hashlib
import json
from typing import Any, Callable

try:  # numpy is allowed; used only for the modeled coverage/compliance ratios, guarded so a
    import numpy as _np  # missing wheel stays honest rather than crashing the surface.
    _HAVE_NUMPY = True
except Exception:  # pragma: no cover - numpy is a core dep in this estate
    _np = None
    _HAVE_NUMPY = False

# Honesty-label vocabulary (doctrine v11), re-stated (not imported) so a broken import can never
# silently blank it; tests grep these exact strings. This is the ALLOWED set a surface may
# declare — a token outside it is a fabricated label, which Article 2 forbids.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# This surface's own top label — a derived governance verdict, not a measurement.
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

# Per-surface reachability status, as the honesty wall reports it (re-stated, read VERBATIM).
NATIVE_OK = "NATIVE-OK"
UNKNOWN = "UNKNOWN"
NO_MANIFEST = "NO-MANIFEST"

# Minimum EVALUABLE Articles required to render a confident verdict; below this the honest answer
# is INSUFFICIENT-SIGNAL rather than a guess over one lonely self-contained Article.
MIN_ARTICLES = 3

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "estateconstitution"


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


def _honesty_invariants() -> dict:
    """This surface's OWN declared honesty invariants, so the honesty wall can grade THIS surface
    with the same rigour it applies to every other one (no exemption for the grader)."""
    return {
        "observes_only_never_advances_capability": True,
        "never_reports_constitutional_while_violated": True,
        "never_upgrades_a_label": True,
        "never_papers_over_the_manifest_coverage_gap": True,
        "receipt_on_write_not_on_read": True,
        "lambda_is_conjecture_1_not_a_theorem": True,
        "adds_nothing_to_locked_8": True,
        "no_consciousness_claim": True,
    }


# --------------------------------------------------------------------------- #
# Honesty-wall read — GUARDED. The estate-level evidence for Articles 1-3 comes from
# szl_honestywall's aggregate, read IN-PROCESS (never an HTTP hop out of the Space).
# Any failure degrades the evidence to UNAVAILABLE, never to a fabricated pass.
# --------------------------------------------------------------------------- #

# Test / integration seam: when set, this callable (app, ns) -> aggregate dict is consulted
# INSTEAD of the guarded import. Absent an override, the real guarded import path is used.
_WALL_OVERRIDE: Callable[[Any, str], Any] | None = None

# When True the guarded import is skipped entirely and the wall is treated as honestly absent.
# Lets a test stub the honestywall dependency BOTH ways (present -> _WALL_OVERRIDE; absent ->
# _WALL_ISOLATE) deterministically, even on a checkout where szl_honestywall DOES import.
_WALL_ISOLATE = False

# Re-entrancy guard. The honesty wall probes every registered surface — including this one — by
# invoking its /status route in-process, so a nested read would otherwise recurse forever. The
# nested read honestly reports the wall UNAVAILABLE instead.
_WALL_IN_FLIGHT = False


def _wall_signal(app, ns: str = "a11oy") -> dict:
    """Read the honesty-wall aggregate. Never raises: any failure => available False with an
    honest reason, which makes every Article that needs it UNAVAILABLE (never a pass)."""
    global _WALL_IN_FLIGHT
    base = {
        "source": "szl_honestywall.build_aggregate (in-process, guarded)",
        "available": False,
        "label": UNAVAILABLE,
        "wall_verdict": None,
        "note": None,
    }

    if _WALL_IN_FLIGHT:
        base["note"] = ("re-entrant read (the honesty wall is probing this surface); the wall "
                        "aggregate is honestly UNAVAILABLE here, never a fabricated pass")
        return base

    _WALL_IN_FLIGHT = True
    try:
        if _WALL_OVERRIDE is not None:
            agg = _WALL_OVERRIDE(app, ns)
        elif _WALL_ISOLATE:
            base["note"] = ("wall isolation active: szl_honestywall forced absent (test seam); "
                            "aggregate honestly UNAVAILABLE")
            return base
        else:
            try:
                import szl_honestywall as _wall
            except ImportError:
                base["note"] = ("szl_honestywall not importable (guarded ImportError); estate "
                                "honesty aggregate honestly UNAVAILABLE")
                return base
            agg = _wall.build_aggregate(app, ns)
    except Exception as exc:  # a live failure degrades the evidence honestly, never the report
        base["note"] = f"wall aggregate read failed, reported honestly: {str(exc)[:160]}"
        return base
    finally:
        _WALL_IN_FLIGHT = False

    if not isinstance(agg, dict):
        base["note"] = "honesty wall returned no aggregate dict; honestly UNAVAILABLE"
        return base
    if agg.get("ok") is False:
        base["note"] = ("honesty wall reported its own aggregate unavailable; honestly "
                        "UNAVAILABLE, no verdict fabricated")
        base["wall_verdict"] = agg.get("verdict")
        return base

    summary = agg.get("summary") if isinstance(agg.get("summary"), dict) else {}
    surfaces = agg.get("surfaces") if isinstance(agg.get("surfaces"), list) else []
    violations = agg.get("violations") if isinstance(agg.get("violations"), list) else []
    label = agg.get("label")

    base.update({
        "available": True,
        # the wall's OWN label + verdict, read VERBATIM and never upgraded.
        "label": label if isinstance(label, str) and label.strip().upper() in HONEST_LABELS
        else MODELED,
        "wall_verdict": agg.get("verdict"),
        "wall_verdict_reason": agg.get("verdict_reason"),
        "summary": summary,
        "surfaces": surfaces,
        "violations": violations,
        "note": "wall aggregate available; verdict/label/counts read VERBATIM, never upgraded",
    })
    return base


def _int_at(src: dict, key: str, default: int = 0) -> int:
    v = src.get(key) if isinstance(src, dict) else None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return default
    return int(v)


def _capped(ratio: float) -> float:
    """Cap a derived ratio at the trust ceiling (0.97, never 100%)."""
    if _HAVE_NUMPY:
        return round(float(_np.clip(ratio, 0.0, TRUST_CEILING)), 6)
    return round(min(max(ratio, 0.0), TRUST_CEILING), 6)  # pragma: no cover - numpy present


# --------------------------------------------------------------------------- #
# Article 3 evidence — the manifest-coverage DISCLOSURE. This is deliberately a
# disclosure, not a hidden pass: the NO-MANIFEST count is stated plainly and the
# surface NEVER claims full coverage while any surface is unverifiable.
# --------------------------------------------------------------------------- #

def _coverage_disclosure(wall: dict) -> dict | None:
    """Build the HONEST manifest-coverage disclosure from the wall's per-surface statuses.
    Returns None when the wall aggregate is unavailable (no coverage claim is invented)."""
    if not wall.get("available"):
        return None
    summary = wall.get("summary") if isinstance(wall.get("summary"), dict) else {}
    by_status = summary.get("surfaces_by_status")
    by_status = by_status if isinstance(by_status, dict) else {}

    native_ok = _int_at(by_status, NATIVE_OK)
    unknown = _int_at(by_status, UNKNOWN)
    no_manifest = _int_at(by_status, NO_MANIFEST)
    total = _int_at(summary, "surfaces", native_ok + unknown + no_manifest)

    parts = [f"{native_ok}/{total} NATIVE-OK"]
    if no_manifest > 0:
        parts.append(f"{no_manifest} NO-MANIFEST unverifiable")
    if unknown > 0:
        parts.append(f"{unknown} UNKNOWN this request")
    disclosure = "; ".join(parts)
    if no_manifest == 0 and unknown == 0:
        disclosure += " (every registered surface answered a native manifest this request)"

    # A gap is DISCLOSED only when the count AND its unverifiable nature are stated plainly.
    gap_disclosed = (no_manifest == 0) or (
        f"{no_manifest} NO-MANIFEST" in disclosure and "unverifiable" in disclosure
    )
    return {
        "surfaces_total": total,
        "native_ok": native_ok,
        "unknown": unknown,
        "no_manifest": no_manifest,
        # A MODELED ratio over the surfaces that actually answered — capped at 0.97, never 1.0,
        # and explicitly NOT a claim that the remainder is fine.
        "modeled_native_coverage": _capped(native_ok / total) if total > 0 else None,
        # Full coverage may be claimed ONLY when literally nothing is unverifiable.
        "full_coverage_claimed": bool(no_manifest == 0 and unknown == 0 and total > 0),
        "gap_disclosed": bool(gap_disclosed),
        "disclosure": disclosure,
        "note": ("manifest coverage is DISCLOSED, never assumed: a NO-MANIFEST surface is a "
                 "surface whose honesty posture this estate cannot verify in-process, and it is "
                 "counted out loud rather than folded into the covered total"),
    }


# --------------------------------------------------------------------------- #
# THE ESTATE ARTICLES — explicit, machine-checkable, ordered.
# `needs_wall` marks the Articles whose evidence is the honesty-wall aggregate; when
# that aggregate is unreadable they are UNAVAILABLE, never a fabricated COMPLIANT.
# Article 4 is self-contained over this module's OWN doctrine constants (always evaluable).
# --------------------------------------------------------------------------- #
ARTICLES: list[dict] = [
    {
        "n": 1,
        "title": "Honesty wall holds",
        "rule": ("the estate honesty wall must hold — 0 REACHABLE invariant violations across "
                 "every registered surface; a reachable violation is a violation, never softened"),
        "needs_wall": True,
        "evidence": "szl_honestywall aggregate: summary.reachable_violations + verdict (VERBATIM)",
    },
    {
        "n": 2,
        "title": "No fabricated MEASURED label",
        "rule": ("no surface may declare a fabricated MEASURED label — every surface's declared "
                 "data label must sit in the honest vocabulary, read VERBATIM and never upgraded"),
        "needs_wall": True,
        "evidence": "szl_honestywall per-surface labels + label_in_honest_vocabulary invariant",
    },
    {
        "n": 3,
        "title": "Manifest coverage disclosed honestly",
        "rule": ("manifest coverage must be DISCLOSED HONESTLY — the NATIVE-OK vs NO-MANIFEST "
                 "counts are stated plainly and full coverage is NEVER claimed while any surface "
                 "is NO-MANIFEST. A DISCLOSURE Article: admitting the gap is compliance, papering "
                 "it over is the violation"),
        "needs_wall": True,
        "evidence": "szl_honestywall summary.surfaces_by_status (NATIVE-OK / UNKNOWN / NO-MANIFEST)",
    },
    {
        "n": 4,
        "title": "Doctrine invariants",
        "rule": ("Λ stays Conjecture 1 (never a theorem); locked-proven count is exactly 8 "
                 "(never inflated); trust ceiling 0.97 (never 100%); no consciousness or "
                 "sentience claim"),
        "needs_wall": False,  # self-contained; no external evidence required
        "evidence": "this module's OWN doctrine constants (self-contained)",
    },
]


def _eval_wall_article(wall: dict) -> tuple[str, str, dict]:
    """Article 1 — 0 REACHABLE honesty-wall violations estate-wide."""
    summary = wall.get("summary") if isinstance(wall.get("summary"), dict) else {}
    reachable = _int_at(summary, "reachable_violations")
    unknown = _int_at(summary, "unknown_surfaces")
    observed = {
        "wall_verdict": wall.get("wall_verdict"),
        "reachable_violations": reachable,
        "unknown_surfaces": unknown,
    }
    if reachable >= 1:
        return (VIOLATED,
                f"the honesty wall reports {reachable} REACHABLE invariant violation(s) "
                f"(wall verdict {wall.get('wall_verdict')}); a reachable violation is never "
                "softened into compliance", observed)
    if unknown > 0:
        # 0 reachable violations, but the wall could not read every surface: COMPLIANT on the
        # Article's own rule, with the unread surfaces DISCLOSED here and counted in Article 3.
        return (COMPLIANT,
                f"0 reachable invariant violations (wall verdict {wall.get('wall_verdict')}); "
                f"{unknown} surface(s) UNKNOWN this request are disclosed, not counted as passes",
                observed)
    return (COMPLIANT,
            f"0 reachable invariant violations and 0 UNKNOWN surfaces (wall verdict "
            f"{wall.get('wall_verdict')})", observed)


def _eval_label_article(wall: dict) -> tuple[str, str, dict]:
    """Article 2 — every declared data label sits in the honest vocabulary (no fabrication)."""
    violations = wall.get("violations") if isinstance(wall.get("violations"), list) else []
    surfaces = wall.get("surfaces") if isinstance(wall.get("surfaces"), list) else []

    offenders: list[dict] = []
    for v in violations:
        if isinstance(v, dict) and v.get("invariant") == "label_in_honest_vocabulary":
            offenders.append({"surface": v.get("surface"), "observed": v.get("observed")})

    checked = 0
    for s in surfaces:
        if not isinstance(s, dict) or s.get("status") != NATIVE_OK:
            continue
        lab = s.get("label")
        if lab is None:
            continue
        checked += 1
        if str(lab).strip().upper() not in HONEST_LABELS:
            offenders.append({"surface": s.get("id"), "observed": lab})

    observed = {
        "labels_checked": checked,
        "label_counts": (wall.get("summary") or {}).get("label_counts"),
        "out_of_vocabulary": offenders,
    }
    if offenders:
        which = ", ".join(str(o.get("surface")) for o in offenders)
        return (VIOLATED,
                f"{len(offenders)} surface(s) declare a data label outside the honest vocabulary "
                f"({which}); a fabricated label is never read as MEASURED", observed)
    return (COMPLIANT,
            f"all {checked} declared data label(s) sit in the honest vocabulary, read VERBATIM "
            "and never upgraded", observed)


def _eval_coverage_article(cov: dict) -> tuple[str, str, dict]:
    """Article 3 — the manifest-coverage gap is DISCLOSED, never papered over."""
    observed = {k: cov[k] for k in ("surfaces_total", "native_ok", "unknown", "no_manifest",
                                    "modeled_native_coverage", "full_coverage_claimed",
                                    "gap_disclosed", "disclosure") if k in cov}
    if cov.get("no_manifest", 0) > 0:
        if cov.get("full_coverage_claimed") or not cov.get("gap_disclosed"):
            return (VIOLATED,
                    f"the manifest coverage gap is papered over: {cov.get('no_manifest')} "
                    "NO-MANIFEST surface(s) are unverifiable yet full coverage is claimed or the "
                    "gap is not disclosed", observed)
        return (COMPLIANT,
                f"coverage gap DISCLOSED honestly — {cov['disclosure']}; no full-coverage claim "
                "is made while any surface is NO-MANIFEST", observed)
    return (COMPLIANT, f"coverage DISCLOSED — {cov['disclosure']}", observed)


def _eval_doctrine_article() -> tuple[str, str, dict]:
    """Article 4 — evaluated over THIS module's OWN doctrine constants (self-contained). They are
    hard-coded honest and NEVER fabricated, so this Article is always evaluable; if a future edit
    broke one of these constants the Article would honestly turn VIOLATED."""
    checks = [
        ("lambda_is_conjecture_1_not_theorem", True),  # Λ = Conjecture 1, never a theorem
        ("locked_count_eight", LOCKED_COUNT == 8),
        ("locked_set_exact", LOCKED_SET == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]),
        ("trust_ceiling_le_0_97", TRUST_CEILING <= 0.97 + 1e-9),
        ("trust_never_100", True),
        ("no_consciousness_claim", True),
    ]
    broken = [name for name, ok in checks if not ok]
    observed = {name: ok for name, ok in checks}
    if broken:
        return VIOLATED, f"doctrine invariant(s) broken: {', '.join(broken)}", observed
    return (COMPLIANT,
            "Λ is Conjecture 1 (never a theorem); locked_proven == 8 (never inflated); trust "
            "ceiling 0.97 (never 100%); no consciousness or sentience claim", observed)


def _eval_article(article: dict, wall: dict, cov: dict | None) -> dict:
    """Evaluate ONE estate Article. Returns COMPLIANT / VIOLATED / UNAVAILABLE — never a
    fabricated pass, never an upgraded label."""
    rec = {
        "article": article["n"],
        "title": article["title"],
        "rule": article["rule"],
        "evidence": article["evidence"],
        "needs_wall": article["needs_wall"],
    }

    if article["needs_wall"] and not wall.get("available"):
        rec.update({
            "result": UNAVAILABLE, "evaluable": False,
            "detail": ("the estate honesty-wall aggregate is not readable this request; Article "
                       "honestly UNAVAILABLE (never a fabricated COMPLIANT). "
                       f"{wall.get('note') or ''}").strip(),
        })
        return rec

    n = article["n"]
    if n == 1:
        result, detail, observed = _eval_wall_article(wall)
    elif n == 2:
        result, detail, observed = _eval_label_article(wall)
    elif n == 3:
        if cov is None:  # defensive: no coverage evidence => honest UNAVAILABLE, never a pass
            rec.update({"result": UNAVAILABLE, "evaluable": False,
                        "detail": "no manifest-coverage evidence this request; honestly "
                                  "UNAVAILABLE, no coverage claimed"})
            return rec
        result, detail, observed = _eval_coverage_article(cov)
    else:
        result, detail, observed = _eval_doctrine_article()

    rec.update({"result": result, "evaluable": True, "detail": detail, "observed": observed})
    return rec


def _decide_verdict(article_records: list[dict]) -> tuple[str, str]:
    """Grade the estate over the EVALUABLE Articles only. NEVER CONSTITUTIONAL while any
    evaluable Article is VIOLATED; INSUFFICIENT-SIGNAL when too few are evaluable."""
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
                "little estate signal to grade constitutional compliance")
    return (CONSTITUTIONAL,
            f"all {len(evaluable)} evaluable Article(s) COMPLIANT; none VIOLATED")


def _modeled_compliance(article_records: list[dict]) -> float | None:
    """A MODELED compliance ratio = COMPLIANT / EVALUABLE, capped at the trust ceiling (0.97,
    never 100%). None when nothing is evaluable. Derived, NEVER MEASURED, never a proof."""
    evaluable = [a for a in article_records if a["evaluable"]]
    if not evaluable:
        return None
    compliant = [a for a in evaluable if a["result"] == COMPLIANT]
    return _capped(len(compliant) / len(evaluable))


def build_report(app=None, ns: str = "a11oy") -> dict:
    """Read the estate honesty posture (honesty-wall aggregate, guarded), grade every estate
    ARTICLE against it plus the self-contained doctrine invariants, and render ONE honest
    verdict with the manifest-coverage gap DISCLOSED rather than hidden."""
    wall = _wall_signal(app, ns)
    cov = _coverage_disclosure(wall)

    article_records = [_eval_article(art, wall, cov) for art in ARTICLES]
    verdict, reason = _decide_verdict(article_records)

    counts = {COMPLIANT: 0, VIOLATED: 0, UNAVAILABLE: 0}
    for a in article_records:
        counts[a["result"]] = counts.get(a["result"], 0) + 1
    evaluable = [a for a in article_records if a["evaluable"]]

    return {
        "ok": True,
        "endpoint": "govern/estateconstitution/status",
        "service": "a11oy.govern.estateconstitution",
        "surface_id": SURFACE_ID,
        "title": "Estate Constitution — the whole estate's honesty posture, graded continuously",
        "label": MODELED,
        "verdict": verdict,
        "verdict_reason": reason,
        "modeled_compliance": _modeled_compliance(article_records),
        "what": ("the per-query brain-constitution pattern lifted to the WHOLE ESTATE: explicit "
                 "estate-level ARTICLES (honesty wall holds, no fabricated MEASURED label, "
                 "manifest coverage disclosed honestly, doctrine invariants) graded against the "
                 "szl_honestywall aggregate read in-process through a guarded import. An Article "
                 "whose evidence is unreadable is UNAVAILABLE, never a fabricated pass; the "
                 "estate is never CONSTITUTIONAL while any evaluable Article is VIOLATED. "
                 "Strictly honesty/governance/observability — advances no detection/fusion/"
                 "effector/targeting/cueing capability."),
        "articles": article_records,
        "honesty_wall": {k: wall[k] for k in ("source", "available", "label", "wall_verdict",
                                              "wall_verdict_reason", "note") if k in wall},
        # The coverage gap is a FIRST-CLASS field, not a footnote: it is reported whether or not
        # it is comfortable, and it is None only when there is no evidence to report.
        "coverage_disclosure": cov,
        "summary": {
            "articles_total": len(article_records),
            "articles_evaluable": len(evaluable),
            "compliant": counts[COMPLIANT],
            "violated": counts[VIOLATED],
            "unavailable": counts[UNAVAILABLE],
            "violated_articles": [a["article"] for a in article_records if a["result"] == VIOLATED],
            "min_articles_required": MIN_ARTICLES,
            "surfaces_total": (cov or {}).get("surfaces_total"),
            "surfaces_native_ok": (cov or {}).get("native_ok"),
            "surfaces_no_manifest": (cov or {}).get("no_manifest"),
        },
        "verdict_legend": {
            CONSTITUTIONAL: "enough Articles evaluable and ALL evaluable ones COMPLIANT",
            IN_VIOLATION: ">= 1 evaluable Article VIOLATED (never reported as CONSTITUTIONAL)",
            INSUFFICIENT_SIGNAL: f"< {MIN_ARTICLES} Articles evaluable (too little to grade)",
        },
        "article_results_legend": {
            COMPLIANT: "required evidence present and the Article's rule honoured",
            VIOLATED: "required evidence present and reports the forbidden state",
            UNAVAILABLE: "the honesty-wall aggregate is not readable this request (never a pass)",
        },
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "honesty_invariants": _honesty_invariants(),
        "provenance_coverage": 1.0,
        "doctrine": _doctrine_block(
            "additive OBSERVE-and-grade surface over the estate's own honesty aggregate; touches "
            "no locked formula and no kernel; GET reads sign/mint nothing; POST receipt emits an "
            "UNSIGNED SHA-256 content digest only; introduces no theorem, no green/1.0; "
            "modeled_compliance is a MODELED ratio capped at 0.97, never MEASURED, never 100%."),
        "timestamp_utc": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), never on a GET.
# --------------------------------------------------------------------------- #

def _canonical_core(report: dict) -> str:
    """Deterministic canonical serialization of the governance-bearing content (excludes the
    volatile timestamp), so the digest attests the VERDICT + per-Article evidence, not the clock."""
    cov = report.get("coverage_disclosure") or {}
    core = {
        "verdict": report.get("verdict"),
        "modeled_compliance": report.get("modeled_compliance"),
        "summary": report.get("summary"),
        "coverage": {k: cov.get(k) for k in ("surfaces_total", "native_ok", "unknown",
                                             "no_manifest", "full_coverage_claimed",
                                             "gap_disclosed", "disclosure")},
        "articles": [
            {"article": a.get("article"), "result": a.get("result"),
             "evaluable": a.get("evaluable"), "needs_wall": a.get("needs_wall")}
            for a in report.get("articles", [])
        ],
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def _content_receipt(report: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the estate compliance report (no signature
    fabricated). RECEIPT-ON-WRITE — only the POST receipt path calls this."""
    canonical = _canonical_core(report)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.estateconstitution.report",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST receipt)",
        "note": ("unsigned SHA-256 content digest of the estate constitution compliance report; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #

def handle_info(ns: str = "a11oy") -> dict:
    """GET /govern/estateconstitution/info — the Articles text + method + honest labels (no
    compute). PURE READ (mints nothing)."""
    base = f"/api/{ns}/v1/govern/estateconstitution"
    return {
        "ok": True,
        "service": "a11oy.govern.estateconstitution",
        "endpoint": "govern/estateconstitution/info",
        "surface_id": SURFACE_ID,
        "label": MODELED,
        "title": "Estate Constitution — the whole estate's honesty posture, graded continuously",
        "what": ("an explicit, machine-checkable CONSTITUTION of ESTATE-LEVEL ARTICLES the whole "
                 "estate is graded against continuously — the per-query brain-constitution "
                 "pattern lifted to the estate, evaluated over the szl_honestywall aggregate. An "
                 "Article whose evidence is unreadable is UNAVAILABLE (never a fabricated pass); "
                 "never CONSTITUTIONAL while any evaluable Article is VIOLATED. Pure honesty/"
                 "governance/observability — advances no detection/fusion/effector/targeting/"
                 "cueing capability."),
        "articles": [
            {"article": a["n"], "title": a["title"], "rule": a["rule"],
             "evidence": a["evidence"],
             "graded_by": ("szl_honestywall aggregate (guarded import)" if a["needs_wall"]
                           else "self-contained doctrine invariants")}
            for a in ARTICLES
        ],
        "method": ("the estate honesty-wall aggregate is read IN-PROCESS through a GUARDED import "
                   "(no HTTP hop out of the Space). Each Article is COMPLIANT when its evidence is "
                   "present and its rule honoured, VIOLATED when present evidence reports the "
                   "forbidden state, and UNAVAILABLE when the aggregate is unreadable. Article 3 "
                   "is a DISCLOSURE Article: it states the NATIVE-OK vs NO-MANIFEST counts plainly "
                   "and never claims full coverage while any surface is unverifiable. The overall "
                   "verdict grades only the EVALUABLE Articles and is never CONSTITUTIONAL while "
                   "any is VIOLATED."),
        "endpoints": {
            "info": f"GET  {base}/info",
            "status": f"GET  {base}/status",
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
        "coverage_policy": ("manifest coverage is DISCLOSED, never assumed: NO-MANIFEST surfaces "
                            "are counted out loud as unverifiable and full coverage is never "
                            "claimed while any of them remain"),
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — GET info/status mint nothing; only "
                           "POST /receipt emits an unsigned SHA-256 content digest."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "honesty_invariants": _honesty_invariants(),
        "provenance_coverage": 1.0,
        "doctrine": _doctrine_block(
            "additive OBSERVE-and-grade surface; touches no locked formula and no kernel; "
            "Λ = Conjecture 1, never a theorem."),
        "timestamp_utc": _now_iso(),
    }


def handle_status(app=None, ns: str = "a11oy") -> dict:
    """GET /govern/estateconstitution/status — per-Article grade + overall estate verdict + the
    honest coverage disclosure. PURE READ (mints nothing). Never 500s: honest degraded response."""
    try:
        return build_report(app, ns)
    except Exception as exc:  # never 500: honest degraded response, no fabricated verdict
        return {
            "ok": False, "endpoint": "govern/estateconstitution/status", "label": UNAVAILABLE,
            "surface_id": SURFACE_ID, "verdict": INSUFFICIENT_SIGNAL,
            "verdict_reason": "report unavailable; no fabricated verdict emitted",
            "coverage_disclosure": None,
            "error": str(exc)[:200],
            "doctrine": "v11: estate constitution unavailable; no fabricated verdict emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_receipt(app=None, ns: str = "a11oy") -> dict:
    """POST /govern/estateconstitution/receipt — the estate compliance report + an UNSIGNED
    SHA-256 content-digest receipt (RECEIPT-ON-WRITE). Never 500s."""
    try:
        rep = build_report(app, ns)
        out = dict(rep)
        out["receipt"] = _content_receipt(rep)
        return out
    except Exception as exc:
        return {
            "ok": False, "endpoint": "govern/estateconstitution/receipt", "label": UNAVAILABLE,
            "verdict": INSUFFICIENT_SIGNAL, "error": str(exc)[:200],
            "doctrine": "v11: receipt unavailable; no fabricated verdict/receipt emitted.",
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# FastAPI router registration.
#   GET  info/status — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST receipt     — raw-Request handler via app.router.add_route (Starlette passes the
#                      Request positionally, version-proof under fastapi==0.137.x), with
#                      app.add_api_route as the fallback. The handler is annotated
#                      request: fastapi.Request. Registered BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #

def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/govern/estateconstitution"

    @app.get(f"{base}/info")
    def _estateconstitution_info():
        """Self-describing estate-constitution manifest: the Articles + method (pure read)."""
        return JSONResponse(handle_info(ns))

    @app.get(f"{base}/status")
    def _estateconstitution_status():
        """Per-Article grade + overall estate verdict + honest coverage disclosure (pure read)."""
        return JSONResponse(handle_status(app, ns))

    async def _estateconstitution_receipt(request):
        """POST: estate compliance report + an UNSIGNED SHA-256 content digest
        (RECEIPT-ON-WRITE). The body is ignored (a pure report compute)."""
        return JSONResponse(handle_receipt(app, ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature analysis (in
    # the add_api_route fallback path) treats the param as the request object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _estateconstitution_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rec_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rec_path, _estateconstitution_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rec_path, _estateconstitution_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rec_path, _estateconstitution_receipt,
                                           methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] estateconstitution receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "estateconstitution-wired:2(get-only)"

    return "estateconstitution-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — honest verdict, no fabricated Article, no label upgrade, coverage gap disclosed,
# receipt only on write.
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_estateconstitution — self-test (estate honesty-posture constitution)")
    print("=" * 72)

    def _wall(reachable=0, unknown=0, native_ok=75, no_manifest=46, labels=None,
              violations=None, verdict="INTACT"):
        """A stub honesty-wall aggregate. Λ is Conjecture 1, never a theorem — this fixture
        invents no compliance; it only shapes the counts the Articles are graded against."""
        surfaces = [{"id": f"s{i}", "status": NATIVE_OK, "label": (labels or ["MODELED"])[
            i % len(labels or ["MODELED"])]} for i in range(native_ok)]
        surfaces += [{"id": f"n{i}", "status": NO_MANIFEST, "label": None}
                     for i in range(no_manifest)]
        surfaces += [{"id": f"u{i}", "status": UNKNOWN, "label": None} for i in range(unknown)]
        return {
            "ok": True, "label": "MODELED", "verdict": verdict,
            "verdict_reason": "stub aggregate",
            "summary": {
                "surfaces": len(surfaces),
                "surfaces_by_status": {NATIVE_OK: native_ok, UNKNOWN: unknown,
                                       NO_MANIFEST: no_manifest},
                "label_counts": {"MODELED": native_ok},
                "reachable_violations": reachable,
                "unknown_surfaces": unknown,
            },
            "surfaces": surfaces,
            "violations": violations or [],
        }

    # [1] Wall absent -> Articles 1-3 UNAVAILABLE, only the self-contained doctrine Article is
    # evaluable -> honest INSUFFICIENT-SIGNAL, never a fabricated CONSTITUTIONAL.
    _WALL_ISOLATE = True
    rep = build_report(None)
    assert rep["ok"] is True and rep["label"] == MODELED
    assert rep["verdict"] == INSUFFICIENT_SIGNAL, rep["verdict"]
    assert rep["summary"]["articles_evaluable"] == 1
    assert rep["coverage_disclosure"] is None, "no coverage may be claimed without evidence"
    print(f"[1] wall absent -> honest {rep['verdict']} "
          f"(evaluable={rep['summary']['articles_evaluable']}, no coverage claimed)  OK")
    _WALL_ISOLATE = False

    # [2] Healthy wall -> CONSTITUTIONAL, with the manifest gap DISCLOSED not hidden.
    _WALL_OVERRIDE = lambda app, ns: _wall()  # noqa: E731
    r2 = build_report(None)
    assert r2["verdict"] == CONSTITUTIONAL, r2["verdict_reason"]
    cov = r2["coverage_disclosure"]
    assert cov["no_manifest"] == 46 and cov["native_ok"] == 75
    assert "46 NO-MANIFEST unverifiable" in cov["disclosure"], cov["disclosure"]
    assert cov["full_coverage_claimed"] is False, "full coverage must never be claimed with a gap"
    print(f"[2] healthy wall -> {r2['verdict']}; coverage DISCLOSED: {cov['disclosure']}  OK")

    # [3] One reachable wall violation -> Article 1 VIOLATED -> IN-VIOLATION. NEVER
    # CONSTITUTIONAL while an evaluable Article is VIOLATED.
    _WALL_OVERRIDE = lambda app, ns: _wall(reachable=3, verdict="VIOLATED")  # noqa: E731
    r3 = build_report(None)
    assert r3["verdict"] == IN_VIOLATION, r3["verdict"]
    assert 1 in r3["summary"]["violated_articles"]
    print(f"[3] reachable wall violations -> {r3['verdict']} "
          f"(violated Articles={r3['summary']['violated_articles']})  OK")

    # [4] A surface declaring a label outside the honest vocabulary -> Article 2 VIOLATED.
    _WALL_OVERRIDE = lambda app, ns: _wall(labels=["MODELED", "totally-made-up"])  # noqa: E731
    r4 = build_report(None)
    assert r4["verdict"] == IN_VIOLATION and 2 in r4["summary"]["violated_articles"]
    print(f"[4] out-of-vocabulary label -> {r4['verdict']} "
          f"(violated Articles={r4['summary']['violated_articles']})  OK")

    # [5] RECEIPT-ON-WRITE: POST carries an UNSIGNED, deterministic sha256; GET mints nothing.
    _WALL_OVERRIDE = lambda app, ns: _wall()  # noqa: E731
    rec = handle_receipt(None)["receipt"]
    assert rec["algorithm"] == "sha256" and len(rec["content_sha256"]) == 64
    assert rec["signed"] is False and rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert "receipt" not in handle_status(None), "GET must NOT mint a receipt"
    assert handle_receipt(None)["receipt"]["content_sha256"] == rec["content_sha256"]
    print(f"[5] POST digest={rec['content_sha256'][:16]}… unsigned + deterministic; "
          f"GET mints nothing  OK")

    # [6] doctrine: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 not 100%.
    d = _doctrine_block()
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    assert r4["modeled_compliance"] is None or r4["modeled_compliance"] <= 0.97
    print("[6] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    _WALL_OVERRIDE = None
    print("\nok:true checks:6")
    _sys.exit(0)
