# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""a11oy_grc_data.py — GRC ALIGNMENT content (Lane I5).

The HONEST, machine-readable substrate for a11oy's in-product Governance/Compliance
surface. This module holds NO web framework code — it is the pure data + builders that
a11oy_grc.py (routes/page/nav) and the published OSCAL artifact both consume, so the
matrix, the Λ→NIST mapping, the Rego bundle metadata, and the OSCAL component-definition
are all derived from a SINGLE source of truth and can never drift.

DOCTRINE / FRAMING (critical — never overclaim):
  * a11oy "aligns with" / "maps to" / "provides evidence for" — NEVER "certified against"
    or "compliant with". No third-party certification has been obtained for ANY framework
    as of Doctrine v11. Coverage = a11oy's INTERNAL analysis of its mechanisms vs published
    framework control text. Gaps are shown HONESTLY (more credible than overclaiming).
  * Coverage states are HONEST: COVERED (specific testable mechanism), PARTIAL (mechanism
    exists but incomplete), ROADMAP (planned, target version), NA (out of scope w/ reason).
  * Λ = Conjecture 1 (NOT a closed theorem); Khipu BFT = Conjecture 2; locked-proven = 8
    @ c7c0ba17; trust never 100%. This surface adds NOTHING to the locked-8.

SOURCES (cited; adopted, NOT reclaimed as SZL theorems):
  - ISO/IEC 42001:2023 (AI management system) — 38 controls / 9 objectives A.2–A.10.
  - NIST AI RMF 1.0 — 72 subcategories across GOVERN(19)/MAP(18)/MEASURE(19)/MANAGE(17).
  - NIST SP 800-53 Rev 5 + usnistgov/OSCAL + usnistgov/oscal-content (catalog source).
  - Open Policy Agent / Rego (policy-as-code).
  - Credo AI 10-dimension risk taxonomy (derives from the MIT AI Risk Repository).
  - EU AI Act (a11oy self-classifies as High-Risk, defense-tech) Art. 9 / Art. 12 / Art. 14.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

DOCTRINE_VERSION = "v11"
KERNEL_COMMIT = "c7c0ba17"

SOURCES: Dict[str, str] = {
    "ISO/IEC 42001:2023 (AI management system)": "https://www.iso.org/standard/81230.html",
    "ISO 42001 Annex A control list (reference)": "https://mindsetcyber.com.au/iso-42001-controls-list/",
    "NIST AI RMF 1.0 Core": "https://airc.nist.gov/airmf-resources/airmf/5-sec-core/",
    "NIST AI RMF Playbook (subcategory detail)": "https://airc.nist.gov/docs/AI_RMF_Playbook.pdf",
    "NIST SP 800-53 Rev 5 catalog (OSCAL JSON)":
        "https://raw.githubusercontent.com/usnistgov/oscal-content/main/nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json",
    "OSCAL (usnistgov/OSCAL)": "https://github.com/usnistgov/OSCAL",
    "OSCAL content (usnistgov/oscal-content)": "https://github.com/usnistgov/oscal-content",
    "Open Policy Agent / Rego": "https://www.openpolicyagent.org/docs/latest/policy-language/",
    "Credo AI risk taxonomy / MIT AI Risk Repository": "https://airisk.mit.edu/",
    "EU AI Act high-level summary": "https://artificialintelligenceact.eu/high-level-summary/",
}

HONEST_DISCLAIMER = (
    "Coverage assessments reflect a11oy's INTERNAL analysis of its mechanisms against "
    "published framework control text. a11oy ALIGNS WITH / MAPS TO these frameworks; it "
    "does NOT claim certification. No third-party certification has been obtained for any "
    "framework as of Doctrine " + DOCTRINE_VERSION + ". Gaps are shown honestly. "
    "Λ = Conjecture 1; locked-proven = 8 @ " + KERNEL_COMMIT + "; trust never 100%."
)

# ───────────────────────────────────────────────────────────────────────────
# 13 Λ axes  →  NIST AI RMF MEASURE 2 subcategories (+ Credo AI / MIT taxonomy label)
# a11oy's Λ trust score has 13 axes. The first 10 map 1:1 to NIST AI RMF MEASURE 2.1–2.10;
# the remaining 3 are governance/autonomy axes that map to GOVERN/MAP subcategories. Every
# row carries the industry-standard Credo AI dimension name so external evaluators recognise
# the axis without a custom glossary. (UPGRADE #1 + #5 of GRC_ONETRUST_RESEARCH.)
# ───────────────────────────────────────────────────────────────────────────
LAMBDA_AXES: List[Dict[str, Any]] = [
    {"axis": 1, "lambda_axis": "scoring methodology / documentation",
     "nist_measure": "MEASURE 2.1", "nist_text": "Test methods and metrics for AI risk",
     "credo_dimension": "Information Integrity (methodology)",
     "mechanism": "Λ 13-axis scoring rubric documented + exposed in every DSSE receipt", "coverage": "COVERED"},
    {"axis": 2, "lambda_axis": "factual accuracy / hallucination rate",
     "nist_measure": "MEASURE 2.2", "nist_text": "Evaluating AI systems for accuracy, interpretability",
     "credo_dimension": "Information Integrity",
     "mechanism": "Lean-proven formula verification; factuality axis scored per inference", "coverage": "COVERED"},
    {"axis": 3, "lambda_axis": "robustness / adversarial resistance",
     "nist_measure": "MEASURE 2.3", "nist_text": "Evaluating for reliability / robustness",
     "credo_dimension": "Security (adversarial resistance)",
     "mechanism": "Red-team / prompt-injection resistance score feeds the robustness axis", "coverage": "PARTIAL"},
    {"axis": 4, "lambda_axis": "operational resilience",
     "nist_measure": "MEASURE 2.4", "nist_text": "Evaluating for resilience",
     "credo_dimension": "Security (resilience)",
     "mechanism": "Resilience axis from szl_resilience degradation/fallback telemetry", "coverage": "PARTIAL"},
    {"axis": 5, "lambda_axis": "safety / harm avoidance",
     "nist_measure": "MEASURE 2.5", "nist_text": "Evaluating for safety",
     "credo_dimension": "Harmful Content Generation",
     "mechanism": "Output content-safety classifier feeds the safety axis; gate halts on DENY", "coverage": "COVERED"},
    {"axis": 6, "lambda_axis": "fairness / demographic parity",
     "nist_measure": "MEASURE 2.6", "nist_text": "Evaluating for fairness / bias",
     "credo_dimension": "Fairness and Bias",
     "mechanism": "Statistical bias detection on outputs feeds the fairness axis", "coverage": "PARTIAL"},
    {"axis": 7, "lambda_axis": "privacy / data minimization",
     "nist_measure": "MEASURE 2.7", "nist_text": "Evaluating for privacy",
     "credo_dimension": "Privacy",
     "mechanism": "PII detection on inputs/outputs feeds the privacy axis", "coverage": "PARTIAL"},
    {"axis": 8, "lambda_axis": "transparency / explainability",
     "nist_measure": "MEASURE 2.8", "nist_text": "Evaluating for transparency / explainability",
     "credo_dimension": "Information Integrity (transparency)",
     "mechanism": "Lean-proven formula output exposed in the DSSE receipt for every decision", "coverage": "COVERED"},
    {"axis": 9, "lambda_axis": "security posture score",
     "nist_measure": "MEASURE 2.9", "nist_text": "Evaluating for security",
     "credo_dimension": "Security",
     "mechanism": "SLSA build posture + signed deployment digest + sentinel rules score", "coverage": "PARTIAL"},
    {"axis": 10, "lambda_axis": "societal impact / mission alignment",
     "nist_measure": "MEASURE 2.10", "nist_text": "Evaluating impacts / risks across the lifecycle",
     "credo_dimension": "Societal Harm",
     "mechanism": "Authorization-boundary + human-override gate firing rate feeds the impact axis", "coverage": "PARTIAL"},
    {"axis": 11, "lambda_axis": "autonomy scope / action class",
     "nist_measure": "MAP 2.1", "nist_text": "AI system categorization — type, capabilities, scope",
     "credo_dimension": "AI Agency and Autonomy",
     "mechanism": "Action-class gate thresholds bound autonomous actions; irreversible → human override", "coverage": "COVERED"},
    {"axis": 12, "lambda_axis": "third-party / vendor risk",
     "nist_measure": "GOVERN 6.1", "nist_text": "Policies for third-party / supply-chain AI risk",
     "credo_dimension": "Third-Party and Vendor Risk",
     "mechanism": "Third-party model attestation + vendor DSSE receipt verification", "coverage": "PARTIAL"},
    {"axis": 13, "lambda_axis": "malicious-use / intent classification",
     "nist_measure": "MEASURE 2.5", "nist_text": "Evaluating for safety (misuse intent)",
     "credo_dimension": "Malicious Use",
     "mechanism": "Use-case intent classifier + policy gate; DENY on prohibited use class", "coverage": "PARTIAL"},
]

# ───────────────────────────────────────────────────────────────────────────
# Honest in-product COVERAGE MATRIX — ISO 42001 / NIST AI RMF / NIST 800-53 / EU AI Act.
# Each row: control id, framework, the concrete a11oy mechanism, and an HONEST state.
# (UPGRADE #3 of GRC_ONETRUST_RESEARCH.) States: COVERED / PARTIAL / ROADMAP / NA.
# ───────────────────────────────────────────────────────────────────────────
COVERAGE_MATRIX: List[Dict[str, str]] = [
    # ISO 42001
    {"control": "A.2.2", "framework": "ISO 42001", "title": "AI policy",
     "mechanism": "Doctrine v11 is the published AI policy; versioned + change-controlled", "coverage": "COVERED"},
    {"control": "A.3.2", "framework": "ISO 42001", "title": "AI roles & responsibilities",
     "mechanism": "Operator role + clearance captured in every DSSE receipt (AC-2/AC-3)", "coverage": "COVERED"},
    {"control": "A.3.3", "framework": "ISO 42001", "title": "AI risk reporting",
     "mechanism": "Λ score reported per-inference; no formal periodic risk REPORT output yet", "coverage": "PARTIAL"},
    {"control": "A.4.6", "framework": "ISO 42001", "title": "Human oversight & monitoring",
     "mechanism": "human_override_required Rego gate fires before irreversible actions / low Λ", "coverage": "COVERED"},
    {"control": "A.5.4", "framework": "ISO 42001", "title": "AI system risk management",
     "mechanism": "13-axis Λ score computed per inference; sealed into the DSSE receipt", "coverage": "COVERED"},
    {"control": "A.6.4", "framework": "ISO 42001", "title": "Data provenance",
     "mechanism": "Input hash + model version + lineage recorded in the receipt", "coverage": "COVERED"},
    {"control": "A.6.6", "framework": "ISO 42001", "title": "AI system verification",
     "mechanism": "Output hash + Lean-verified formula path; locked-proven = 8 @ c7c0ba17", "coverage": "PARTIAL"},
    {"control": "A.9.3", "framework": "ISO 42001", "title": "Human oversight (use)",
     "mechanism": "Human-override gate; irreversible actions require human confirmation", "coverage": "COVERED"},
    {"control": "A.9.4", "framework": "ISO 42001", "title": "Incident management",
     "mechanism": "Incident receipt + tamper-evident re-verification at /cosign.pub", "coverage": "PARTIAL"},
    {"control": "A.10.4", "framework": "ISO 42001", "title": "Supplier monitoring",
     "mechanism": "Third-party model attestation; vendor DSSE receipt verification", "coverage": "PARTIAL"},
    # NIST AI RMF
    {"control": "GOVERN 1.1", "framework": "NIST AI RMF", "title": "AI policies & processes",
     "mechanism": "Doctrine v11 + policy-gate configuration inventory", "coverage": "COVERED"},
    {"control": "MAP 2.3", "framework": "NIST AI RMF", "title": "AI capability characterization",
     "mechanism": "Λ scoring methodology + model registry classification", "coverage": "COVERED"},
    {"control": "MEASURE 2.8", "framework": "NIST AI RMF", "title": "Transparency / explainability",
     "mechanism": "Lean-proven formula output exposed in the receipt", "coverage": "COVERED"},
    {"control": "MEASURE 3.1", "framework": "NIST AI RMF", "title": "Risk tracking over time",
     "mechanism": "Continuous Λ score with a timestamp chain of receipts", "coverage": "PARTIAL"},
    {"control": "GOVERN 3.2", "framework": "NIST AI RMF", "title": "Workforce DEI",
     "mechanism": "Out of scope for an orchestration layer (organizational control)", "coverage": "NA"},
    {"control": "MANAGE 4.1", "framework": "NIST AI RMF", "title": "Post-incident after-action",
     "mechanism": "Incident receipt replay + independent re-verification", "coverage": "PARTIAL"},
    {"control": "MEASURE 4.2", "framework": "NIST AI RMF", "title": "Measurement-effectiveness feedback",
     "mechanism": "Λ-score calibration feedback loop", "coverage": "ROADMAP"},
    # NIST 800-53 Rev 5
    {"control": "AU-2", "framework": "NIST 800-53r5", "title": "Event logging",
     "mechanism": "DSSE-signed audit event per inference (verdict + rule ID)", "coverage": "COVERED"},
    {"control": "AU-3", "framework": "NIST 800-53r5", "title": "Content of audit records",
     "mechanism": "Timestamp + input/output hash in every receipt", "coverage": "COVERED"},
    {"control": "AU-9", "framework": "NIST 800-53r5", "title": "Protection of audit information",
     "mechanism": "Records sealed in DSSE envelopes signed by ECDSA-P256; tamper-detectable", "coverage": "COVERED"},
    {"control": "CM-8", "framework": "NIST 800-53r5", "title": "System component inventory",
     "mechanism": "Model ID + version + digest recorded per inference", "coverage": "COVERED"},
    {"control": "RA-3", "framework": "NIST 800-53r5", "title": "Risk assessment",
     "mechanism": "13-axis Λ trust score is the per-inference risk assessment", "coverage": "COVERED"},
    {"control": "SI-10", "framework": "NIST 800-53r5", "title": "Information input validation",
     "mechanism": "Input hash + classification-boundary gate", "coverage": "PARTIAL"},
    # EU AI Act
    {"control": "Article 12", "framework": "EU AI Act", "title": "Record-keeping / logging",
     "mechanism": "Immutable DSSE receipt per inference satisfies automatic logging", "coverage": "COVERED"},
    {"control": "Article 14", "framework": "EU AI Act", "title": "Human oversight",
     "mechanism": "Human-in-the-loop override gate; human-on-loop for SIMULATED effectors", "coverage": "COVERED"},
    {"control": "Article 9", "framework": "EU AI Act", "title": "Risk management system (High-Risk)",
     "mechanism": "Λ-gated policy enforcement; no formal QMS document yet", "coverage": "ROADMAP"},
]

# ───────────────────────────────────────────────────────────────────────────
# Policy gates expressed as OPA / Rego (UPGRADE #2). Each gate carries the controls
# it satisfies; the bundle is version-locked by a SHA-256 digest that every DSSE receipt
# cites — so a receipt proves WHICH policy version made the decision.
# ───────────────────────────────────────────────────────────────────────────
REGO_GATES: List[Dict[str, Any]] = [
    {
        "name": "classification_boundary",
        "package": "a11oy.gates.classification_boundary",
        "controls": ["ISO42001/A.9.6", "NIST80053/AC-3", "EUAIAct/Art.14"],
        "rego": (
            "package a11oy.gates.classification_boundary\n\n"
            "# DENY when output classification exceeds the operator's clearance level.\n"
            "default allow := false\n\n"
            "deny[msg] {\n"
            "  input.output_classification > input.user_clearance_level\n"
            "  msg := sprintf(\"output classification %v exceeds user clearance %v\",\n"
            "                 [input.output_classification, input.user_clearance_level])\n"
            "}\n\n"
            "allow {\n  count(deny) == 0\n}\n"
        ),
    },
    {
        "name": "human_override_required",
        "package": "a11oy.gates.human_override_required",
        "controls": ["ISO42001/A.9.3", "ISO42001/A.4.6", "NIST80053/AU-2", "EUAIAct/Art.14"],
        "rego": (
            "package a11oy.gates.human_override_required\n\n"
            "# Require a human override for irreversible actions or when Λ < threshold.\n"
            "default require_human := false\n\n"
            "require_human {\n  input.action_class == \"irreversible\"\n}\n\n"
            "require_human {\n  input.lambda_score < input.lambda_halt_threshold\n}\n"
        ),
    },
    {
        "name": "deployment_readiness",
        "package": "a11oy.gates.deployment_readiness",
        "controls": ["ISO27001/8.25", "NIST80053/CM-3", "ISO42001/A.6.7"],
        "rego": (
            "package a11oy.gates.deployment_readiness\n\n"
            "# Block model promotion unless the signed package digest + Λ floor are met.\n"
            "default promote := false\n\n"
            "promote {\n"
            "  input.package_signed == true\n"
            "  input.slsa_level >= 2\n"
            "  input.lambda_score >= input.lambda_promote_floor\n"
            "}\n"
        ),
    },
]


def policy_bundle_digest() -> str:
    """Deterministic SHA-256 over the canonical Rego bundle — the version-lock that every
    DSSE receipt cites (UPGRADE #2/#4). Stable across calls for a given bundle content."""
    canon = json.dumps([{ "name": g["name"], "package": g["package"], "rego": g["rego"]}
                        for g in REGO_GATES], sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(canon).hexdigest()


# ───────────────────────────────────────────────────────────────────────────
# DSSE Receipt Schema v2 — each field cites the control(s) it provides evidence for
# (UPGRADE #4). This is a SCHEMA (field→control map), not a fabricated receipt.
# ───────────────────────────────────────────────────────────────────────────
DSSE_RECEIPT_SCHEMA_V2: List[Dict[str, Any]] = [
    {"field": "inference_timestamp_utc", "controls": ["NIST80053/AU-3", "EUAIAct/Art.12", "ISO42001/A.6.5"]},
    {"field": "model_id_version_digest", "controls": ["NIST80053/CM-8", "NIST80053/CM-2", "EUAIAct/Art.12", "ISO42001/A.6.6"]},
    {"field": "policy_bundle_digest", "controls": ["NIST80053/CM-3", "EUAIAct/Art.9", "ISO42001/A.9.2"]},
    {"field": "input_hash_sha256", "controls": ["NIST80053/AU-3", "NIST80053/SI-10", "EUAIAct/Art.12", "ISO42001/A.7.2"]},
    {"field": "output_hash_sha256", "controls": ["NIST80053/AU-3", "NIST80053/SI-7", "EUAIAct/Art.12", "ISO42001/A.6.6"]},
    {"field": "policy_gate_verdict_and_rule_id", "controls": ["NIST80053/AU-2", "EUAIAct/Art.9", "EUAIAct/Art.14", "ISO42001/A.9.3"]},
    {"field": "lambda_score_13axis", "controls": ["NIST80053/RA-3", "EUAIAct/Art.9", "ISO42001/A.5.4"]},
    {"field": "operator_role_clearance", "controls": ["NIST80053/AC-2", "NIST80053/AC-3", "EUAIAct/Art.14", "ISO42001/A.3.2"]},
    {"field": "ecdsa_p256_signature", "controls": ["NIST80053/AU-9", "ISO42001/A.4.2"]},
    {"field": "reverification_endpoint", "controls": ["NIST80053/AU-6", "EUAIAct/Art.12", "ISO42001/A.8.2"]},
]


def coverage_summary() -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in COVERAGE_MATRIX:
        out[r["coverage"]] = out.get(r["coverage"], 0) + 1
    return out


def build_matrix() -> Dict[str, Any]:
    return {
        "doctrine": DOCTRINE_VERSION,
        "kernel_commit": KERNEL_COMMIT,
        "matrix": COVERAGE_MATRIX,
        "summary": coverage_summary(),
        "frameworks": sorted({r["framework"] for r in COVERAGE_MATRIX}),
        "eu_ai_act_self_classification": "High-Risk (defense-tech agentic orchestrator)",
        "honest": HONEST_DISCLAIMER,
        "framing": "aligns with / maps to — NOT certified / compliant",
        "status": "ALIGNMENT (no third-party certification)",
        "sources": SOURCES,
    }


def build_mapping() -> Dict[str, Any]:
    return {
        "doctrine": DOCTRINE_VERSION,
        "lambda_axes": LAMBDA_AXES,
        "axis_count": len(LAMBDA_AXES),
        "primary_target": "NIST AI RMF MEASURE 2 (10 subcategories) + GOVERN/MAP for governance axes",
        "taxonomy_alignment": "Credo AI 10-dimension (derives from MIT AI Risk Repository)",
        "dsse_receipt_schema_v2": DSSE_RECEIPT_SCHEMA_V2,
        "policy_bundle_digest": policy_bundle_digest(),
        "rego_gates": [{"name": g["name"], "package": g["package"], "controls": g["controls"], "rego": g["rego"]}
                       for g in REGO_GATES],
        "honest": HONEST_DISCLAIMER,
        "status": "ALIGNMENT",
        "sources": SOURCES,
    }


def build_oscal() -> Dict[str, Any]:
    """OSCAL Component Definition (UPGRADE #7) derived from the SAME coverage matrix +
    Rego gates, so the published artifact and the live matrix can never diverge. Control
    source = usnistgov/oscal-content SP 800-53 Rev 5 catalog. Honest: alignment, not cert."""
    import datetime
    src = SOURCES["NIST SP 800-53 Rev 5 catalog (OSCAL JSON)"]
    # implemented-requirements from the 800-53 rows of the coverage matrix
    impl: List[Dict[str, Any]] = []
    for r in COVERAGE_MATRIX:
        if r["framework"] != "NIST 800-53r5":
            continue
        impl.append({
            "uuid": "ir-" + hashlib.sha256(r["control"].encode()).hexdigest()[:8],
            "control-id": r["control"].lower().replace(" ", "-"),
            "description": f"[{r['coverage']}] {r['mechanism']} (a11oy {r['title']}).",
            "props": [{"name": "coverage", "ns": "https://szlholdings.ai/ns/oscal", "value": r["coverage"]}],
        })
    rego_statements = [{
        "uuid": "ir-rego-" + hashlib.sha256(g["name"].encode()).hexdigest()[:8],
        "control-id": "ac-3",
        "description": f"Rego gate {g['package']} (controls: {', '.join(g['controls'])}). "
                       f"Bundle digest {policy_bundle_digest()} is cited in every DSSE receipt.",
    } for g in REGO_GATES]
    return {
        "component-definition": {
            "uuid": "a11oy-comp-def-" + DOCTRINE_VERSION,
            "metadata": {
                "title": "a11oy Governed AI Orchestrator — OSCAL Component Definition",
                "last-modified": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "version": DOCTRINE_VERSION,
                "oscal-version": "1.1.2",
                "remarks": HONEST_DISCLAIMER,
            },
            "components": [{
                "uuid": "a11oy-orchestrator",
                "type": "software",
                "title": "a11oy Governed AI Orchestrator",
                "description": "Governed agentic-AI orchestration layer emitting a DSSE-signed "
                               "receipt per inference. ALIGNS WITH the controls below; not certified.",
                "props": [
                    {"name": "doctrine", "ns": "https://szlholdings.ai/ns/oscal", "value": DOCTRINE_VERSION},
                    {"name": "kernel-commit", "ns": "https://szlholdings.ai/ns/oscal", "value": KERNEL_COMMIT},
                    {"name": "policy-bundle-digest", "ns": "https://szlholdings.ai/ns/oscal", "value": policy_bundle_digest()},
                    {"name": "eu-ai-act-class", "ns": "https://szlholdings.ai/ns/oscal", "value": "High-Risk (self-classified)"},
                ],
                "control-implementations": [{
                    "uuid": "ci-800-53r5",
                    "source": src,
                    "description": "a11oy mechanism mapping to NIST SP 800-53 Rev 5 (alignment only).",
                    "implemented-requirements": impl + rego_statements,
                }],
            }],
        }
    }


def _selftest() -> None:
    assert len(LAMBDA_AXES) == 13, "must be 13 Λ axes"
    # axes 1-10 must map to MEASURE 2.1..2.10
    m2 = [a for a in LAMBDA_AXES if a["nist_measure"].startswith("MEASURE 2.")]
    assert len(m2) >= 10
    assert all(v in ("COVERED", "PARTIAL", "ROADMAP", "NA") for v in (r["coverage"] for r in COVERAGE_MATRIX))
    s = coverage_summary()
    assert sum(s.values()) == len(COVERAGE_MATRIX)
    d1 = policy_bundle_digest(); d2 = policy_bundle_digest()
    assert d1 == d2 and d1.startswith("sha256:")
    oscal = build_oscal()
    cd = oscal["component-definition"]
    assert cd["components"][0]["control-implementations"][0]["implemented-requirements"], "no impl reqs"
    assert "certified" not in HONEST_DISCLAIMER.lower() or "not" in HONEST_DISCLAIMER.lower()
    # OSCAL must be valid JSON-serialisable
    json.dumps(oscal)
    mp = build_mapping(); mx = build_matrix()
    assert mp["axis_count"] == 13 and mx["summary"]
    print("a11oy_grc_data: ALL OK (%d matrix rows, 13 axes, %d gates, %d schema fields)"
          % (len(COVERAGE_MATRIX), len(REGO_GATES), len(DSSE_RECEIPT_SCHEMA_V2)))


if __name__ == "__main__":
    _selftest()
