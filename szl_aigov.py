"""
szl_aigov.py — SZL AIGOV: an AI-Governance Conformance surface that MAPS a11oy
model/inference evidence onto the real regulated-AI control frameworks and reports
a Λ-ADVISORY readiness score (never green, ≤0.97) with HONEST gaps.

This is an SZL governance SYNTHESIS surface: it takes the real, cited control
catalogs that enterprises must answer to —

  (1) EU AI ACT (Regulation (EU) 2024/1689) — the ANNEX IV technical-documentation
      items + the high-risk obligations they reference (risk management Art. 9,
      data governance Art. 10, record-keeping Art. 12, transparency Art. 13, human
      oversight Art. 14, accuracy/robustness/cybersecurity Art. 15, post-market
      monitoring Art. 72);
  (2) NIST AI RMF 1.0 (NIST AI 100-1) — the GOVERN / MAP / MEASURE / MANAGE
      functions and representative subcategories;
  (3) ISO/IEC 42001:2023 — the AI management-system Annex A controls (AI policy,
      roles, impact assessment, life cycle, data, information to parties, third
      parties);

— and CROSS-WALKS each control to the a11oy artifact that would evidence it (the
signed Khipu receipt chain, the DSSE/in-toto supply chain, the doctrine gate +
Λ restraint, the energy ledger, the honest-label discipline). The surface then
scores a MODELED per-control evidence strength, rolls it up into a per-framework
and overall Λ-ADVISORY readiness figure, and lists the honest GAPS.

  GET  /api/<ns>/v1/frontier/aigov?seed=&fw=

HONEST STATUS — READ THIS BEFORE TRUSTING A NUMBER
  MODELED — the control catalog is real and cited, and the cross-walk to a11oy
    artifacts is a genuine design mapping; but the per-control evidence STRENGTH,
    the coverage rates, and the readiness score are a DETERMINISTIC MODEL over that
    mapping, not the output of an accredited audit. They are COMPUTED and reported,
    not fabricated — but they are a self-assessment MODEL.
  CONJECTURE — the readiness score is an ADVISORY CONJECTURE (Λ = Conjecture 1,
    gray, NEVER green). It is NOT a compliance guarantee, NOT an attestation, and
    NOT an Authorization To Operate (ATO). This surface never emits the words
    "certified" or "compliant" about the system; the honest verdict is
    "SELF-ASSESSED / ADVISORY — third-party conformity assessment REQUIRED".

DOCTRINE v11
  Nothing here is in the locked-8 (adds 0). Λ = Conjecture 1 (gray, never green).
  Readiness is capped at 0.97 and is NEVER 1.0 / never green. No fabricated
  evidence. Pure stdlib. Deterministic with seed. 0 runtime CDN. RECEIPT-ON-WRITE,
  NOT ON-READ: this GET signs nothing and appends to no provenance chain.
  Overclaiming AND underclaiming both banned — the label is the honest one.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-07):
  EU AI Act — Regulation (EU) 2024/1689 of the European Parliament and of the
    Council laying down harmonised rules on artificial intelligence (Annex IV
    technical documentation; Arts. 9,10,12,13,14,15,72). Official Journal, 2024.
    https://eur-lex.europa.eu/eli/reg/2024/1689/oj
  NIST AI RMF 1.0 — Artificial Intelligence Risk Management Framework
    (NIST AI 100-1), U.S. National Institute of Standards and Technology, 2023.
    https://doi.org/10.6028/NIST.AI.100-1
  ISO/IEC 42001:2023 — Information technology — Artificial intelligence —
    Management system. International Organization for Standardization, 2023.
    https://www.iso.org/standard/81230.html
  COMPL-AI Framework: A Technical Interpretation and LLM Benchmarking Suite for
    the EU Artificial Intelligence Act — Guldimann et al. 2024, arXiv:2410.07959
    https://arxiv.org/abs/2410.07959
"""
import hashlib
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import JSONResponse

CITATIONS = {
    "EU AI Act — Regulation (EU) 2024/1689 (Annex IV; Arts. 9,10,12,13,14,15,72)": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
    "NIST AI RMF 1.0 — Artificial Intelligence Risk Management Framework (NIST AI 100-1, 2023)": "https://doi.org/10.6028/NIST.AI.100-1",
    "ISO/IEC 42001:2023 — Information technology — Artificial intelligence — Management system": "https://www.iso.org/standard/81230.html",
    "COMPL-AI: Technical Interpretation + LLM Benchmarking Suite for the EU AI Act — Guldimann et al. 2024 arXiv:2410.07959": "https://arxiv.org/abs/2410.07959",
}

# Λ-advisory / readiness hyperparameters (reported verbatim; not trained).
_LAMBDA_MIN = 0.02        # Λ advisory lower bound (gray floor)
_LAMBDA_MAX = 0.94        # Λ advisory upper bound (NEVER 1.0 — Conjecture 1)
_READINESS_CAP = 0.97     # doctrine hard cap on readiness (never green / never 1.0)
_SATISFIED_AT = 0.75      # >= => modeled status "SATISFIED (advisory)"
_PARTIAL_AT = 0.45        # >= => "PARTIAL"; below => "GAP"

# Modeled evidence-freshness window (a sampled-recency multiplier over the
# intrinsic strength — models "how fresh is the evidence for this control").
_FRESH_LO = 0.86
_FRESH_HI = 1.00

# ── CONTROL CATALOG ─────────────────────────────────────────────────────────
# Each control is a REAL, cited framework item cross-walked to the a11oy artifact
# that would evidence it. `base` is the INTRINSIC honest evidence strength of that
# a11oy artifact for that control (design self-assessment, deliberately NOT all
# high — several are honest GAPS): e.g. the signed-receipt / doctrine-gate story is
# strong, but post-market monitoring, carbon accounting and third-party conformity
# assessment are genuine gaps. Overclaiming AND underclaiming are both banned, so
# these are the honest design numbers, reported verbatim.
_CONTROLS = [
    # EU AI Act — Regulation (EU) 2024/1689
    {"fw": "EU AI Act", "id": "AnnexIV.1", "title": "General description of the AI system", "ref": "Annex IV(1)", "evidence": "system card + honest capability map (docs/architecture.md)", "base": 0.80},
    {"fw": "EU AI Act", "id": "Art.9", "title": "Risk management system", "ref": "Art. 9 / Annex IV(4)", "evidence": "doctrine gate + Λ restraint (deny-by-default governance/)", "base": 0.72},
    {"fw": "EU AI Act", "id": "Art.10", "title": "Data & data governance", "ref": "Art. 10 / Annex IV(2)(d)", "evidence": "dataset provenance + corpus honesty guards", "base": 0.58},
    {"fw": "EU AI Act", "id": "Art.12", "title": "Record-keeping / automatic logging", "ref": "Art. 12", "evidence": "signed Khipu receipt chain (receipt-on-write)", "base": 0.83},
    {"fw": "EU AI Act", "id": "Art.13", "title": "Transparency & instructions for use", "ref": "Art. 13 / Annex IV(3)", "evidence": "honest-label discipline + per-tile honesty banners", "base": 0.74},
    {"fw": "EU AI Act", "id": "Art.14", "title": "Human oversight", "ref": "Art. 14 / Annex IV(2)(e)", "evidence": "Λ trust gate is ADVISORY — human-in-the-loop by design", "base": 0.55},
    {"fw": "EU AI Act", "id": "Art.15", "title": "Accuracy, robustness & cybersecurity", "ref": "Art. 15 / Annex IV(2)(g)", "evidence": "eval arena + backend hardening; robustness only PARTIAL", "base": 0.60},
    {"fw": "EU AI Act", "id": "Art.72", "title": "Post-market monitoring plan", "ref": "Art. 72 / Annex IV(8)", "evidence": "observability exists; formal post-market plan is a GAP", "base": 0.34},
    # NIST AI RMF 1.0 — NIST AI 100-1
    {"fw": "NIST AI RMF 1.0", "id": "GOVERN.1.1", "title": "Legal & regulatory requirements understood/managed", "ref": "GOVERN 1.1", "evidence": "this conformance crosswalk + governance gateway", "base": 0.70},
    {"fw": "NIST AI RMF 1.0", "id": "GOVERN.4.1", "title": "Safety-first organizational risk culture", "ref": "GOVERN 4.1", "evidence": "doctrine v11 (honest-over-checklist) + honest-status review", "base": 0.78},
    {"fw": "NIST AI RMF 1.0", "id": "MAP.1.1", "title": "Context & intended purpose established", "ref": "MAP 1.1", "evidence": "surface capability map + honest scope disclaimers", "base": 0.73},
    {"fw": "NIST AI RMF 1.0", "id": "MEASURE.2.1", "title": "Test sets & evaluation metrics applied", "ref": "MEASURE 2.1", "evidence": "eval arena (governed eval / red-team suite)", "base": 0.64},
    {"fw": "NIST AI RMF 1.0", "id": "MEASURE.2.7", "title": "Security & resilience evaluated", "ref": "MEASURE 2.7", "evidence": "gitleaks + backend hardening + adversarial tests", "base": 0.62},
    {"fw": "NIST AI RMF 1.0", "id": "MEASURE.2.11", "title": "Fairness & bias evaluated", "ref": "MEASURE 2.11", "evidence": "no dedicated fairness harness wired — GAP", "base": 0.30},
    {"fw": "NIST AI RMF 1.0", "id": "MANAGE.4.1", "title": "Post-deployment monitoring & response", "ref": "MANAGE 4.1", "evidence": "live watchdogs + receipts; response runbook PARTIAL", "base": 0.52},
    # ISO/IEC 42001:2023 — Annex A controls
    {"fw": "ISO/IEC 42001", "id": "A.2", "title": "AI policy", "ref": "Annex A.2", "evidence": "AGENTS.md doctrine + GOVERNANCE.md as AI policy", "base": 0.76},
    {"fw": "ISO/IEC 42001", "id": "A.3", "title": "Internal organization & roles", "ref": "Annex A.3", "evidence": "founder-gated signing + ownership map", "base": 0.68},
    {"fw": "ISO/IEC 42001", "id": "A.5", "title": "Assessing impacts of AI systems", "ref": "Annex A.5", "evidence": "impact assessment is DESIGN-only — PARTIAL", "base": 0.48},
    {"fw": "ISO/IEC 42001", "id": "A.6", "title": "AI system life cycle management", "ref": "Annex A.6", "evidence": "signed supply chain (DSSE/in-toto/SLSA roadmap)", "base": 0.61},
    {"fw": "ISO/IEC 42001", "id": "A.7", "title": "Data for AI systems", "ref": "Annex A.7", "evidence": "corpus provenance + freshness guards", "base": 0.57},
    {"fw": "ISO/IEC 42001", "id": "A.8", "title": "Information for interested parties", "ref": "Annex A.8", "evidence": "public honest disclosure + honesty labels", "base": 0.71},
    {"fw": "ISO/IEC 42001", "id": "A.10", "title": "Third-party & supplier relationships", "ref": "Annex A.10", "evidence": "third-party conformity assessment NOT done — GAP", "base": 0.33},
]

_FRAMEWORKS = ["EU AI Act", "NIST AI RMF 1.0", "ISO/IEC 42001"]


def _u01(seed, i, salt=0):
    """Deterministic uniform in [0,1) from (seed, i, salt) via two LCG rounds."""
    s = ((i + 1) * 2654435761 + seed * 40503 + salt * 2246822519) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    return s / 4294967295.0


def _status(strength):
    if strength >= _SATISFIED_AT:
        return "SATISFIED (advisory)"
    if strength >= _PARTIAL_AT:
        return "PARTIAL"
    return "GAP"


def _assess(seed=42, fw_filter=None):
    """Deterministic MODELED conformance self-assessment.

    For each cited control, the intrinsic a11oy evidence `base` is multiplied by a
    modeled evidence-FRESHNESS factor in [_FRESH_LO,_FRESH_HI] (seed-driven — models
    how recently the evidence was refreshed) to yield a per-control STRENGTH. The
    control's modeled status (SATISFIED-advisory / PARTIAL / GAP) and a per-control
    Λ advisory (gray, bounded so it is NEVER 1.0) follow from the strength. Scores
    roll up per-framework (mean strength) and overall (equal framework weight so no
    single framework dominates), HARD-CAPPED at _READINESS_CAP so readiness is never
    green / never 1.0. The whole readiness figure is ADVISORY CONJECTURE, never a
    compliance guarantee.
    """
    controls = _CONTROLS
    if fw_filter:
        controls = [c for c in controls if c["fw"] == fw_filter]
    if not controls:
        controls = _CONTROLS  # never return an empty catalog

    rows = []
    for idx, c in enumerate(controls):
        fresh = _FRESH_LO + (_FRESH_HI - _FRESH_LO) * _u01(seed, idx, salt=7)
        strength = round(min(0.99, c["base"] * fresh), 6)
        status = _status(strength)
        lam = round(min(_LAMBDA_MAX, max(_LAMBDA_MIN, strength)), 6)
        rows.append({
            "fw": c["fw"],
            "id": c["id"],
            "title": c["title"],
            "ref": c["ref"],
            "a11oy_evidence": c["evidence"],
            "evidence_strength": strength,
            "status": status,
            "lambda_advisory": lam,
            "satisfied": bool(status.startswith("SATISFIED")),
        })

    # per-framework readiness (mean strength across that framework's controls)
    per_fw = []
    for fw in _FRAMEWORKS:
        fw_rows = [r for r in rows if r["fw"] == fw]
        if not fw_rows:
            continue
        mean_strength = sum(r["evidence_strength"] for r in fw_rows) / len(fw_rows)
        readiness = round(min(_READINESS_CAP, mean_strength), 6)
        sat = sum(1 for r in fw_rows if r["satisfied"])
        gaps = sum(1 for r in fw_rows if r["status"] == "GAP")
        partial = sum(1 for r in fw_rows if r["status"] == "PARTIAL")
        per_fw.append({
            "framework": fw,
            "controls": len(fw_rows),
            "satisfied_advisory": sat,
            "partial": partial,
            "gaps": gaps,
            "coverage_rate": round(sat / len(fw_rows), 6),
            "readiness_advisory": readiness,
        })

    # overall readiness — EQUAL framework weight (so a framework with many controls
    # does not dominate), hard-capped, never green / never 1.0.
    overall = round(min(_READINESS_CAP, sum(f["readiness_advisory"] for f in per_fw) / len(per_fw)), 6) if per_fw else 0.0

    total = len(rows)
    sat_total = sum(1 for r in rows if r["satisfied"])
    gap_total = sum(1 for r in rows if r["status"] == "GAP")
    partial_total = sum(1 for r in rows if r["status"] == "PARTIAL")

    # HONEST GAPS — every control that is not fully SATISFIED-advisory, verbatim.
    honest_gaps = [
        {"fw": r["fw"], "id": r["id"], "title": r["title"], "status": r["status"],
         "ref": r["ref"], "why": r["a11oy_evidence"]}
        for r in rows if r["status"] != "SATISFIED (advisory)"
    ]

    return {
        "controls": rows,
        "frameworks": per_fw,
        "summary": {
            "frameworks": len(per_fw),
            "controls_total": total,
            "satisfied_advisory": sat_total,
            "partial": partial_total,
            "gaps": gap_total,
            "coverage_rate": round(sat_total / total, 6) if total else 0.0,
        },
        "readiness": {
            "status": "Λ-ADVISORY readiness (Λ = Conjecture 1, gray — NEVER green, not a theorem)",
            "score_advisory": overall,
            "score_cap": _READINESS_CAP,
            "green": False,
            "verdict": "SELF-ASSESSED / ADVISORY — third-party conformity assessment REQUIRED",
            "is_compliance_guarantee": False,
            "is_attestation": False,
            "authorization_to_operate": False,
            "lambda_bounds": {"min": _LAMBDA_MIN, "max": _LAMBDA_MAX},
        },
        "honest_gaps": honest_gaps,
    }


def _mapping_digest(payload, seed):
    """UNSIGNED content-hash preview of the conformance mapping (design only).

    RECEIPT-ON-WRITE, NOT ON-READ: this GET mints NOTHING and appends to no
    provenance chain. A plain SHA3-256 hash over a canonical summary is returned as
    a clearly-UNSIGNED preview so the mapping is reproducibly identifiable without
    signing on a read path.
    """
    s = payload["summary"]
    r = payload["readiness"]
    canonical = "|".join([
        f"seed={seed}",
        f"frameworks={s['frameworks']}",
        f"controls={s['controls_total']}",
        f"satisfied={s['satisfied_advisory']}",
        f"partial={s['partial']}",
        f"gaps={s['gaps']}",
        f"readiness={r['score_advisory']}",
        "ids=" + ",".join(c["id"] for c in payload["controls"]),
    ])
    digest = hashlib.sha3_256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "conformance-mapping preview (SZL synthesis — advisory, design-only)",
        "signed": False,
        "minted_on_this_get": False,
        "mapping_preview_digest": digest,
        "preview_digest_alg": "SHA3-256 over a canonical conformance summary (UNSIGNED preview only)",
        "doctrine": "RECEIPT-ON-WRITE, NOT ON-READ — a GET signs nothing and grows no chain.",
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _h_aigov(req: Request):
    seed = _ii(req, "seed", 42)
    fw = req.query_params.get("fw")
    if fw is not None:
        fw = fw.strip()
        # accept a case-insensitive framework name; ignore an unknown filter.
        match = next((f for f in _FRAMEWORKS if f.lower() == fw.lower()), None)
        fw = match

    p = _assess(seed=seed, fw_filter=fw)
    p["mapping_preview"] = _mapping_digest(p, seed)
    p.update({
        "label": "MODELED",
        "model": ("AI-governance conformance crosswalk (EU AI Act / NIST AI RMF 1.0 / "
                  "ISO/IEC 42001) with a Λ-advisory readiness score"),
        "seed": seed,
        "framework_filter": fw,
        "parts_labeled": {
            "MODELED": [
                "control catalog cross-walk to a11oy artifacts (real cited frameworks)",
                "per-control evidence strength (intrinsic base × modeled freshness)",
                "per-framework + overall coverage / readiness roll-up",
            ],
            "CONJECTURE": [
                "readiness score is ADVISORY (Λ = Conjecture 1, gray — never green)",
                "the readiness is NOT a compliance guarantee / NOT an attestation / NOT an ATO",
                "the governed-conformance surface as one advisory artifact (unshipped synthesis)",
            ],
        },
        "honest_note": (
            "MODELED + CONJECTURE. The control catalog is REAL and cited (EU AI Act "
            "Regulation (EU) 2024/1689 Annex IV + Arts. 9/10/12/13/14/15/72; NIST AI "
            "RMF 1.0 GOVERN/MAP/MEASURE/MANAGE; ISO/IEC 42001:2023 Annex A), and the "
            "cross-walk to a11oy artifacts is a genuine design mapping. The per-control "
            "evidence strengths, coverage rates and readiness score are a DETERMINISTIC "
            "SELF-ASSESSMENT MODEL over that mapping — genuinely computed and reported, "
            "NOT fabricated, but NOT the output of an accredited audit. The readiness "
            "score is an ADVISORY CONJECTURE (Λ = Conjecture 1, gray, NEVER green); it "
            "is capped at 0.97 and is never 1.0. It is NOT a compliance guarantee, NOT "
            "an attestation, and NOT an Authorization To Operate — the honest verdict is "
            "SELF-ASSESSED / ADVISORY, third-party conformity assessment REQUIRED. This "
            "surface never claims the system is 'certified' or 'compliant'. Honest gaps "
            "are listed verbatim (e.g. post-market monitoring, fairness/bias evaluation, "
            "impact assessment, third-party conformity assessment). RECEIPT-ON-WRITE, "
            "never on a GET: the mapping_preview_digest is a plain UNSIGNED content hash, "
            "not a signature. Cites EU AI Act (2024/1689), NIST AI RMF 1.0 (NIST AI "
            "100-1), ISO/IEC 42001:2023, and COMPL-AI (arXiv:2410.07959) for the "
            "technical-interpretation method. SZL claims NONE of these frameworks as its "
            "own. Nothing here is in the locked-8."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    # Surface reads label at top level OR payload.label, metrics from payload.
    return JSONResponse({"label": "MODELED", "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/frontier/aigov onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/frontier"
    handlers = [(f"{base}/aigov", _h_aigov)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    p = _assess(seed=42)
    p["mapping_preview"] = _mapping_digest(p, 42)
    r = p["readiness"]
    s = p["summary"]
    assert 0.0 <= r["score_advisory"] <= _READINESS_CAP, "readiness must be capped at 0.97"
    assert r["score_advisory"] < 1.0, "readiness must never reach 1.0 (never green)"
    assert r["green"] is False and r["is_compliance_guarantee"] is False
    assert r["authorization_to_operate"] is False, "no ATO claim"
    assert r["lambda_bounds"]["max"] < 1.0, "Λ advisory must never reach 1.0 (Conjecture 1)"
    assert p["mapping_preview"]["signed"] is False, "no signing on a read path"
    assert s["satisfied_advisory"] + s["partial"] + s["gaps"] == s["controls_total"]
    assert s["gaps"] > 0, "honest self-assessment must surface real gaps, never all-green"
    assert len(p["honest_gaps"]) == s["partial"] + s["gaps"]
    print("frameworks:", s["frameworks"], "controls:", s["controls_total"])
    print("satisfied(advisory):", s["satisfied_advisory"], "partial:", s["partial"], "gaps:", s["gaps"])
    print("coverage_rate:", s["coverage_rate"])
    for f in p["frameworks"]:
        print("  -", f["framework"], "readiness:", f["readiness_advisory"], "cov:", f["coverage_rate"])
    print("overall readiness (advisory, cap", _READINESS_CAP, "):", r["score_advisory"], "green:", r["green"])
    print("verdict:", r["verdict"])
    print("mapping preview digest:", p["mapping_preview"]["mapping_preview_digest"][:16], "... signed:", p["mapping_preview"]["signed"])
    print("label: MODELED (readiness advisory CONJECTURE)")
