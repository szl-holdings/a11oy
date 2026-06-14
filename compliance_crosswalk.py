# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""compliance_crosswalk — SZL doctrine-v11 controls mapped to recognized AI-governance
frameworks (NIST AI RMF · ISO/IEC 42001 · EU AI Act), as STRUCTURED, HONEST data.

WHY (GAP 3): we have rigorous internal doctrine but, until now, NO mapping to a
recognized framework. For a defense / AI play selling into regulated buyers that is the
difference between "impressive demo" and "procurable". This module is the machine-readable
spine: the same crosswalk humans read in COMPLIANCE.md, but as data a procurement bot,
the a11oy mesh, or an auditor can ingest. It also COMPUTES an honest coverage score.

HONESTY (Doctrine v11, HARD — this module is itself a doctrine surface):
  * Every cell carries an explicit status: IMPLEMENTED | PARTIAL | ROADMAP. We NEVER mark a
    cell IMPLEMENTED for a control we do not actually ship. `coverage()` counts ONLY
    IMPLEMENTED cells toward "covered"; PARTIAL and ROADMAP are reported separately and
    NEVER inflate the score. A framework is reported at 100% ONLY if every control we map to
    it is IMPLEMENTED — there is an explicit assertion guarding that invariant.
  * Λ = Conjecture 1: a mapping to a framework is ADVISORY alignment, NOT a certification.
    SZL holds NO third-party AI-governance certificate today. This crosswalk is a self-
    asserted alignment statement, not a conformity assessment or CE mark.
  * The framework definitions (NIST subcategory IDs, ISO clause numbers, EU article numbers)
    are CITED from the official / authoritative sources, never claimed as SZL's. The
    NIST→ISO 42001 clause mappings below follow NIST's OWN published crosswalk.
  * No fabricated numbers. The only numbers this module emits are integer COUNTS of cells it
    can see in its own table, plus their honest ratio.

SOURCES (carried in SOURCES, cited in COMPLIANCE.md / FINDINGS.md):
  * NIST AI RMF 1.0 — NIST AI 100-1 (Jan 2023). Functions: Govern / Map / Measure / Manage.
    https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf
  * NIST "AI RMF to ISO/IEC FDIS 42001 AI Management system Crosswalk" (official):
    https://airc.nist.gov/docs/NIST_AI_RMF_to_ISO_IEC_42001_Crosswalk.pdf
  * ISO/IEC 42001:2023 — Artificial intelligence management system (AIMS). Clauses 4–10 +
    Annex A/B controls. https://www.iso.org/standard/81230.html
  * EU AI Act — Regulation (EU) 2024/1689. Art. 9 (risk mgmt), 10 (data governance),
    12 (record-keeping / logging), 13 (transparency), 14 (human oversight), 15 (accuracy /
    robustness / cybersecurity), 17 (quality management system), 50 (transparency / marking
    of AI-generated content, enforceable 2 Aug 2026). https://artificialintelligenceact.eu/

Pure stdlib → sovereign, own-metal, auditable, 0 runtime CDN.
"""
from __future__ import annotations

import json
from typing import Dict, List

# --------------------------------------------------------------------------- #
# Status vocabulary (the ONLY three honest states).                           #
# --------------------------------------------------------------------------- #
IMPLEMENTED = "IMPLEMENTED"  # shipping in the estate today, demonstrable
PARTIAL = "PARTIAL"          # real but incomplete (e.g. signer wired, CI guard manual)
ROADMAP = "ROADMAP"          # designed/intended, NOT yet shipping — never counted as covered
VALID_STATUSES = (IMPLEMENTED, PARTIAL, ROADMAP)

DOCTRINE = (
    "v11 LOCKED: a framework MAPPING is ADVISORY alignment, NOT a certification — SZL holds "
    "no third-party AI-governance certificate today. Λ=Conjecture 1 (advisory, never 'proven "
    "trust'/'proven compliant'). Each cell labelled IMPLEMENTED/PARTIAL/ROADMAP honestly; "
    "coverage() counts ONLY IMPLEMENTED; a framework reads 100% ONLY if every mapped control "
    "is IMPLEMENTED. Framework IDs CITED from official sources, not claimed as SZL's. "
    "Sovereign own-metal, 0 CDN, no fabricated numbers."
)

LAMBDA_NOTE = (
    "Λ = Conjecture 1 (advisory). 'Aligned' = 'this SZL control supports the framework "
    "requirement', NEVER 'certified' or 'proven compliant'. Deny-by-default posture; a "
    "signature/attestation is NOT proof of safety (GAP1 lesson)."
)

SOURCES = {
    "nist_ai_rmf": {
        "title": "NIST AI Risk Management Framework (AI RMF 1.0), NIST AI 100-1",
        "url": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf",
        "note": "Functions: Govern, Map, Measure, Manage. Published Jan 2023.",
    },
    "nist_iso42001_crosswalk": {
        "title": "NIST AI RMF to ISO/IEC FDIS 42001 AI Management System Crosswalk (official)",
        "url": "https://airc.nist.gov/docs/NIST_AI_RMF_to_ISO_IEC_42001_Crosswalk.pdf",
        "note": "Authoritative NIST-published subcategory -> ISO 42001 clause/Annex mapping.",
    },
    "iso_42001": {
        "title": "ISO/IEC 42001:2023 — Information technology — AI — Management system",
        "url": "https://www.iso.org/standard/81230.html",
        "note": "AIMS clauses 4-10 + Annex A/B controls.",
    },
    "eu_ai_act": {
        "title": "EU AI Act — Regulation (EU) 2024/1689",
        "url": "https://artificialintelligenceact.eu/",
        "note": "Art. 9,10,12,13,14,15,17,50. Art. 50 marking enforceable 2 Aug 2026.",
    },
    "eu_ai_act_art50": {
        "title": "EU AI Act Article 50 — Transparency obligations (AI-generated content marking)",
        "url": "https://artificialintelligenceact.eu/article/50/",
        "note": "Machine-readable marking of synthetic content; enforceable 2 Aug 2026.",
    },
    "eu_ai_act_art12": {
        "title": "EU AI Act Article 12 — Record-keeping / automatic logging",
        "url": "https://artificialintelligenceact.eu/article/12/",
        "note": "Tamper-evident, traceable event logs over system lifetime.",
    },
}

# --------------------------------------------------------------------------- #
# Our REAL controls (doctrine v11). The canonical id-set; every crosswalk row  #
# MUST reference a control that appears here. GAP1/GAP2 are included with their #
# honest live status (PARTIAL = engine built in this gap-closure, not yet fully #
# wired into the production a11oy deploy by Forge).                             #
# --------------------------------------------------------------------------- #
CONTROLS: Dict[str, Dict] = {
    "deny_by_default_lambda_gate": {
        "name": "Deny-by-default Λ-gate (advisory governance gate)",
        "status": IMPLEMENTED,
        "evidence": (
            "Λ = Conjecture 1 admission gate, deny-by-default; ALLOW/NOMINAL = 'passed SZL "
            "admission policy', never 'proven trust'. Live in pnt_resilience fused detector "
            "and the mesh route table."
        ),
    },
    "measured_modeled_labeling": {
        "name": "MEASURED vs MODELED vs SAMPLE labeling on every value",
        "status": IMPLEMENTED,
        "evidence": (
            "Every emitted value carries a provenance label; PINN compute-bounds certificate "
            "labels each input MEASURED and each derived bound MODELED. Honest 'NOT MODELED' "
            "where physics/data is incomplete."
        ),
    },
    "signed_dsse_provenance_rekor": {
        "name": "Signed DSSE provenance (Ed25519) + Rekor transparency",
        "status": PARTIAL,
        "evidence": (
            "DSSE Ed25519 envelope pattern + FA-001 + cosign.pub anchor + Rekor transparency "
            "are designed and the hash CHAIN is real and verified; per the authoritative "
            "docs/compliance.md the cosign SIGNING in CI is PENDING (DSSE-PLACEHOLDER) — so "
            "honestly PARTIAL, not IMPLEMENTED, until signing lands."
        ),
    },
    "overclaim_ledger_ci_guard": {
        "name": "Overclaim ledger + CI guard (banned-claim tripwire)",
        "status": IMPLEMENTED,
        "evidence": (
            "Banned-claim ledger (e.g. 'SLSA L3', 'proven trust') with a CI guard / tripwire "
            "T02 (measurabilityHonesty). Authoritative posture page enforces it."
        ),
    },
    "clean_room": {
        "name": "Clean-room engineering (cite-never-plagiarize)",
        "status": IMPLEMENTED,
        "evidence": (
            "Bounds/physics re-derived clean-room from papers; kshana method cited (Apache-2.0, "
            "DOI) not copied. Provenance of method documented."
        ),
    },
    "sovereign_own_metal": {
        "name": "Sovereign own-metal deployment (no hyperscaler dependency)",
        "status": IMPLEMENTED,
        "evidence": (
            "2 own GPUs, air-gap-capable, sovereign deployment model. No hyperscaler runtime "
            "dependency."
        ),
    },
    "zero_cdn": {
        "name": "Zero runtime CDN",
        "status": IMPLEMENTED,
        "evidence": "0 runtime CDN; all assets served from sovereign own-metal.",
    },
    "behavioural_artifact_monitor": {
        "name": "Behavioural artifact monitor (runtime, GAP1 — inward SDA/spoof fusion)",
        "status": PARTIAL,
        "evidence": (
            "GAP1 engine: turns the deny-by-default SDA/spoof-fusion detector inward onto our "
            "OWN build/deploy artifacts (anomaly on tarball size, egress, unexpected file "
            "injection) — the behavioural half the npm/TanStack SLSA-signed-malware story "
            "proved necessary. Built in this gap-closure cycle; PARTIAL until Forge wires it "
            "into the production deploy pipeline."
        ),
    },
    "c2pa_content_credentials": {
        "name": "C2PA Content Credentials on generated assets (GAP2)",
        "status": PARTIAL,
        "evidence": (
            "GAP2 engine: signed C2PA manifests (tool, edits, AI-or-not) on estate-generated "
            "assets, using existing cosign/DSSE identity, for EU AI Act Art. 50 marking. Built "
            "in this gap-closure cycle; PARTIAL until production assets emit it by default."
        ),
    },
    "pqc_ml_dsa_signatures": {
        "name": "Post-quantum (ML-DSA) signature option for DSSE signer (GAP6)",
        "status": ROADMAP,
        "evidence": (
            "GAP6: ML-DSA (FIPS 204) as an optional PQ signature alongside Ed25519, per the IETF "
            "Agent Trust Negotiation draft. NOT shipping — explicitly a roadmap option. Included "
            "here ONLY as ROADMAP so the crosswalk shows the honest gap; it is never counted as "
            "covered by coverage()."
        ),
    },
}

# --------------------------------------------------------------------------- #
# The CROSSWALK. Each entry maps ONE of our controls to one cell of one        #
# framework. NIST->ISO 42001 clause references follow NIST's OWN published     #
# crosswalk; EU AI Act articles follow the Regulation text. The per-cell       #
# `status` is the HONEST status of OUR control as it supports that requirement #
# (it may be capped below the control's own status if our support is partial). #
# --------------------------------------------------------------------------- #
# frameworks
NIST = "NIST_AI_RMF"
ISO = "ISO_IEC_42001"
EU = "EU_AI_ACT"
FRAMEWORKS = (NIST, ISO, EU)

CROSSWALK: List[Dict] = [
    # ---- Deny-by-default Λ-gate -------------------------------------------- #
    {"control": "deny_by_default_lambda_gate", "framework": NIST,
     "ref": "GOVERN 1.1 / GOVERN 1.2", "ref_name": "Policies & processes to govern AI risk",
     "status": IMPLEMENTED,
     "rationale": "Deny-by-default admission policy IS a documented risk-governance process."},
    {"control": "deny_by_default_lambda_gate", "framework": ISO,
     "ref": "Clause 6.1.3 / Annex B.6.2.6", "ref_name": "AI risk treatment; AI system operation & monitoring",
     "status": IMPLEMENTED,
     "rationale": "Gate is an operational risk-treatment control on the AI system at runtime."},
    {"control": "deny_by_default_lambda_gate", "framework": EU,
     "ref": "Article 9 / Article 14", "ref_name": "Risk management system; human oversight",
     "status": PARTIAL,
     "rationale": "Supports Art.9 risk mgmt & Art.14 oversight, but no formal high-risk QMS yet."},

    # ---- MEASURED/MODELED labeling ----------------------------------------- #
    {"control": "measured_modeled_labeling", "framework": NIST,
     "ref": "MEASURE 2.9 / MEASURE 2.5", "ref_name": "Model explained; mechanisms valid & reliable",
     "status": IMPLEMENTED,
     "rationale": "Provenance labels make every value's epistemic status explicit and testable."},
    {"control": "measured_modeled_labeling", "framework": ISO,
     "ref": "Annex B.6.2.7 / B.7.4", "ref_name": "AI system technical documentation; quality of data",
     "status": IMPLEMENTED,
     "rationale": "Labels are technical-documentation evidence of data/derivation quality."},
    {"control": "measured_modeled_labeling", "framework": EU,
     "ref": "Article 13 / Article 15", "ref_name": "Transparency; accuracy & robustness",
     "status": PARTIAL,
     "rationale": "Labels support transparency & honest accuracy claims; not a full Art.13 deployer pack."},

    # ---- Signed DSSE provenance + Rekor (PARTIAL control) ------------------ #
    {"control": "signed_dsse_provenance_rekor", "framework": NIST,
     "ref": "MEASURE 2.9 / MANAGE 4.1", "ref_name": "Model documented; post-deployment monitoring",
     "status": PARTIAL,
     "rationale": "Provenance + transparency log support traceability; signing in CI still PENDING."},
    {"control": "signed_dsse_provenance_rekor", "framework": ISO,
     "ref": "Annex B.7.5 / B.6.2.8", "ref_name": "Data provenance; recording of event logs",
     "status": PARTIAL,
     "rationale": "DSSE + Rekor are provenance & event-log evidence; PARTIAL until signer wired."},
    {"control": "signed_dsse_provenance_rekor", "framework": EU,
     "ref": "Article 12", "ref_name": "Record-keeping / automatic logging (tamper-evident)",
     "status": PARTIAL,
     "rationale": "Rekor transparency log is tamper-evident record-keeping; signing PENDING."},

    # ---- Overclaim ledger + CI guard --------------------------------------- #
    {"control": "overclaim_ledger_ci_guard", "framework": NIST,
     "ref": "GOVERN 1.2 / MEASURE 4.2", "ref_name": "Accountability structures; feedback on claims",
     "status": IMPLEMENTED,
     "rationale": "CI guard structurally blocks overclaims — an accountability control."},
    {"control": "overclaim_ledger_ci_guard", "framework": ISO,
     "ref": "Annex B.2.2 / Clause 10.2", "ref_name": "AI policy; nonconformity & corrective action",
     "status": IMPLEMENTED,
     "rationale": "Banned-claim ledger enforces policy; a failing guard is a corrective-action trigger."},
    {"control": "overclaim_ledger_ci_guard", "framework": EU,
     "ref": "Article 13", "ref_name": "Transparency & provision of information to deployers",
     "status": PARTIAL,
     "rationale": "Prevents misleading capability claims; not the full Art.13 instruction set."},

    # ---- Clean-room -------------------------------------------------------- #
    {"control": "clean_room", "framework": NIST,
     "ref": "MAP 4.1 / GOVERN 6.1", "ref_name": "3rd-party/IP risk mapped; supply-chain accountability",
     "status": IMPLEMENTED,
     "rationale": "Cite-never-plagiarize controls IP/provenance risk of reused methods."},
    {"control": "clean_room", "framework": ISO,
     "ref": "Annex B.10.3 / B.4.2", "ref_name": "Suppliers; resource documentation",
     "status": IMPLEMENTED,
     "rationale": "Documented provenance of third-party methods/data — a supplier/resource control."},
    {"control": "clean_room", "framework": EU,
     "ref": "Article 10", "ref_name": "Data & data governance",
     "status": PARTIAL,
     "rationale": "Supports lawful, documented data/method provenance; not full Art.10 dataset governance."},

    # ---- Sovereign own-metal ----------------------------------------------- #
    {"control": "sovereign_own_metal", "framework": NIST,
     "ref": "MANAGE 2.1 / MAP 4.1", "ref_name": "Resources to manage risk; supply-chain risk",
     "status": IMPLEMENTED,
     "rationale": "No-hyperscaler posture removes a class of supply-chain/availability risk."},
    {"control": "sovereign_own_metal", "framework": ISO,
     "ref": "Annex B.4.5", "ref_name": "System & computing resources",
     "status": IMPLEMENTED,
     "rationale": "Own-metal is a documented, controlled computing-resource posture."},
    {"control": "sovereign_own_metal", "framework": EU,
     "ref": "Article 15", "ref_name": "Accuracy, robustness & cybersecurity",
     "status": PARTIAL,
     "rationale": "Air-gap-capable own-metal aids robustness/cyber posture; not a full Art.15 conformity test."},

    # ---- Zero CDN ---------------------------------------------------------- #
    {"control": "zero_cdn", "framework": NIST,
     "ref": "MANAGE 1.3 / MAP 4.1", "ref_name": "Risk treatment; third-party dependency risk",
     "status": IMPLEMENTED,
     "rationale": "Removing runtime CDN removes a third-party tamper/availability dependency."},
    {"control": "zero_cdn", "framework": ISO,
     "ref": "Annex B.4.5 / B.10.3", "ref_name": "Computing resources; suppliers",
     "status": IMPLEMENTED,
     "rationale": "No third-party CDN supplier in the runtime path — a documented supplier control."},
    {"control": "zero_cdn", "framework": EU,
     "ref": "Article 15", "ref_name": "Accuracy, robustness & cybersecurity",
     "status": PARTIAL,
     "rationale": "Reduces runtime attack surface; supports but does not satisfy Art.15 alone."},

    # ---- Behavioural artifact monitor (GAP1, PARTIAL) ---------------------- #
    {"control": "behavioural_artifact_monitor", "framework": NIST,
     "ref": "MANAGE 4.1 / MEASURE 2.6", "ref_name": "Post-deployment monitoring; safety/efficacy in deployment",
     "status": PARTIAL,
     "rationale": "Runtime behavioural anomaly monitor on our own artifacts; built, not yet prod-wired."},
    {"control": "behavioural_artifact_monitor", "framework": ISO,
     "ref": "Annex B.6.2.6 / B.6.2.8", "ref_name": "AI system operation & monitoring; event logs",
     "status": PARTIAL,
     "rationale": "Operational monitoring control producing event logs; PARTIAL pending deploy wiring."},
    {"control": "behavioural_artifact_monitor", "framework": EU,
     "ref": "Article 72 / Article 12", "ref_name": "Post-market monitoring; record-keeping",
     "status": PARTIAL,
     "rationale": "Behavioural monitor feeds post-market monitoring & logs; not yet a formal PMM system."},

    # ---- C2PA Content Credentials (GAP2, PARTIAL) -------------------------- #
    {"control": "c2pa_content_credentials", "framework": NIST,
     "ref": "MEASURE 2.9 / GOVERN 1.2", "ref_name": "Output documented/traceable; transparency policy",
     "status": PARTIAL,
     "rationale": "Signed content manifests make generated outputs traceable AI-or-not."},
    {"control": "c2pa_content_credentials", "framework": ISO,
     "ref": "Annex B.7.5 / B.8.2", "ref_name": "Data provenance; system docs & info for users",
     "status": PARTIAL,
     "rationale": "Content Credentials are provenance metadata informing users; PARTIAL pending default-on."},
    {"control": "c2pa_content_credentials", "framework": EU,
     "ref": "Article 50", "ref_name": "Transparency: machine-readable marking of AI-generated content",
     "status": PARTIAL,
     "rationale": "C2PA is the named mechanism for Art.50 marking (enforceable 2 Aug 2026); built, not default-on."},

    # ---- Post-quantum ML-DSA signatures (GAP6, ROADMAP) -------------------- #
    {"control": "pqc_ml_dsa_signatures", "framework": NIST,
     "ref": "MANAGE 1.3 / GOVERN 1.2", "ref_name": "Risk treatment; security policy (crypto agility)",
     "status": ROADMAP,
     "rationale": "PQ crypto agility is a designed risk-treatment option; NOT shipping yet (roadmap)."},
    {"control": "pqc_ml_dsa_signatures", "framework": ISO,
     "ref": "Annex B.6.2.8 / Clause 10.1", "ref_name": "Event logs integrity; continual improvement",
     "status": ROADMAP,
     "rationale": "PQ signatures would future-proof log/provenance integrity; roadmap, not implemented."},
    {"control": "pqc_ml_dsa_signatures", "framework": EU,
     "ref": "Article 15", "ref_name": "Accuracy, robustness & cybersecurity",
     "status": ROADMAP,
     "rationale": "PQ readiness strengthens long-term cybersecurity posture; explicitly roadmap."},
]


# --------------------------------------------------------------------------- #
# Integrity helpers.                                                           #
# --------------------------------------------------------------------------- #
def _validate() -> None:
    """Fail loudly if the table is internally dishonest or malformed.

    Doctrine: a crosswalk that references a control we don't have, or a status outside the
    three honest states, is itself an overclaim. Run at import so it can never silently rot.
    """
    for cid, c in CONTROLS.items():
        if c["status"] not in VALID_STATUSES:
            raise ValueError(f"control {cid} has invalid status {c['status']!r}")
    for i, row in enumerate(CROSSWALK):
        if row["control"] not in CONTROLS:
            raise ValueError(f"crosswalk row {i} references unknown control {row['control']!r}")
        if row["framework"] not in FRAMEWORKS:
            raise ValueError(f"crosswalk row {i} references unknown framework {row['framework']!r}")
        if row["status"] not in VALID_STATUSES:
            raise ValueError(f"crosswalk row {i} has invalid status {row['status']!r}")
        # A cell may never claim MORE than its own control. (Can be capped lower, e.g. a
        # control that is IMPLEMENTED overall but only PARTIALLY supports an EU article.)
        rank = {ROADMAP: 0, PARTIAL: 1, IMPLEMENTED: 2}
        if rank[row["status"]] > rank[CONTROLS[row["control"]]["status"]]:
            raise ValueError(
                f"crosswalk row {i} ({row['control']}->{row['framework']}) claims "
                f"{row['status']} but the control is only {CONTROLS[row['control']]['status']}"
            )


def coverage() -> Dict:
    """Score, HONESTLY, how much of each framework our REAL controls cover.

    Counts ONLY cells whose status == IMPLEMENTED toward `covered`. PARTIAL and ROADMAP are
    reported in their own buckets and NEVER inflate the covered count or the percentage.

    Returns a labelled report. The `pct_implemented` is MEASURED off the table itself (a
    count of this module's own cells) — it is NOT a claim of certified coverage; see
    `interpretation`. A framework's `fully_implemented` flag is True ONLY if EVERY mapped
    cell for it is IMPLEMENTED.
    """
    report: Dict = {
        "label": "MEASURED (cell counts of this crosswalk table) — NOT a certification",
        "doctrine": DOCTRINE,
        "lambda": LAMBDA_NOTE,
        "frameworks": {},
        "totals": {},
    }
    grand = {IMPLEMENTED: 0, PARTIAL: 0, ROADMAP: 0, "total": 0}
    for fw in FRAMEWORKS:
        cells = [r for r in CROSSWALK if r["framework"] == fw]
        counts = {IMPLEMENTED: 0, PARTIAL: 0, ROADMAP: 0}
        for r in cells:
            counts[r["status"]] += 1
        total = len(cells)
        implemented = counts[IMPLEMENTED]
        pct = round(100.0 * implemented / total, 1) if total else 0.0
        fully = (implemented == total and total > 0)
        report["frameworks"][fw] = {
            "total_mapped_cells": total,
            "implemented": implemented,
            "partial": counts[PARTIAL],
            "roadmap": counts[ROADMAP],
            "pct_implemented": pct,
            "fully_implemented": fully,
        }
        # HONESTY INVARIANT: never report 100% unless every mapped cell is IMPLEMENTED.
        if pct >= 100.0:
            assert fully, f"{fw}: 100% reported without every cell IMPLEMENTED — overclaim"
        for k in (IMPLEMENTED, PARTIAL, ROADMAP):
            grand[k] += counts[k]
        grand["total"] += total
    report["totals"] = {
        "implemented": grand[IMPLEMENTED],
        "partial": grand[PARTIAL],
        "roadmap": grand[ROADMAP],
        "total_mapped_cells": grand["total"],
        "pct_implemented": (
            round(100.0 * grand[IMPLEMENTED] / grand["total"], 1) if grand["total"] else 0.0
        ),
    }
    report["interpretation"] = (
        "pct_implemented = fraction of MAPPED cells our IMPLEMENTED controls currently support. "
        "It is an honest self-assessment of alignment coverage, NOT third-party-certified "
        "coverage and NOT a claim that the framework as a whole is satisfied. SZL holds no "
        "AI-governance certificate today; PARTIAL/ROADMAP cells are the honest gap to close."
    )
    return report


def to_servable() -> Dict:
    """Build the machine-readable artifact the a11oy mesh exposes at
    /api/a11oy/v1/compliance. Deterministic, stdlib-serializable, doctrine-labelled."""
    return {
        "schema": "szl.compliance.crosswalk/v1",
        "doctrine": DOCTRINE,
        "lambda": LAMBDA_NOTE,
        "disclaimer": (
            "Self-asserted ADVISORY alignment to recognized AI-governance frameworks. NOT a "
            "certification or conformity assessment. SZL holds no third-party AI-governance "
            "certificate as of this artifact's generation."
        ),
        "frameworks": {
            NIST: SOURCES["nist_ai_rmf"],
            ISO: SOURCES["iso_42001"],
            EU: SOURCES["eu_ai_act"],
        },
        "sources": SOURCES,
        "status_vocabulary": {
            IMPLEMENTED: "Shipping in the estate today; demonstrable.",
            PARTIAL: "Real but incomplete (e.g. engine built, not yet production-wired).",
            ROADMAP: "Designed/intended; NOT yet shipping. Never counted as covered.",
        },
        "controls": CONTROLS,
        "crosswalk": CROSSWALK,
        "coverage": coverage(),
    }


def to_json(indent: int = 2) -> str:
    return json.dumps(to_servable(), indent=indent, sort_keys=False)


# Validate at import — a dishonest table must never load silently.
_validate()


if __name__ == "__main__":  # pragma: no cover
    rep = coverage()
    print("SZL compliance crosswalk — honest coverage (MEASURED cell counts):")
    for fw, d in rep["frameworks"].items():
        print(f"  {fw:14s} implemented={d['implemented']:>2}/{d['total_mapped_cells']:<2} "
              f"({d['pct_implemented']:>5.1f}%) partial={d['partial']} roadmap={d['roadmap']} "
              f"fully={d['fully_implemented']}")
    t = rep["totals"]
    print(f"  {'TOTAL':14s} implemented={t['implemented']}/{t['total_mapped_cells']} "
          f"({t['pct_implemented']}%) partial={t['partial']} roadmap={t['roadmap']}")
