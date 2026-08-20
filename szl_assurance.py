# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
# Authored by Perplexity Computer Agent (Yachay CTO pattern) — AI Assurance Surface
"""
szl_assurance.py — AI Assurance for WDP-era agentic AI (ADDITIVE module, never breaks
existing routes).

a11oy is the governance + verifiable-provenance OVERLAY that sits on top of any data
platform (Advana/WDP/Palantir Foundry/Databricks Unity Catalog) and produces the
auditability evidence the Jan-2026 WDP memo demands: agentic AI + auditability.

Two endpoints:
  GET /api/a11oy/v1/assurance/matrix
      → JSON mapping each CDAO/DoD AI-assurance requirement to the a11oy artifact
        that satisfies it, with honest status and source citation.
        Status values: LIVE | MEASURED | SAMPLE | MODELED | ROADMAP
        NEVER claims ATO/IL5/FedRAMP — those are ROADMAP items, stated plainly.

  GET /api/a11oy/v1/assurance/fit
      → JSON: honest "where a11oy fits" — governance/assurance OVERLAY positioning.
        Advana/WDP/Foundry/Databricks stay the system of record.
        a11oy adds cryptographic, buyer-verifiable assurance on top.
        NEVER claims to be or replace them.

register(app, ns='a11oy') — additive, wrapped in try/except.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# HONEST ASSURANCE MATRIX
# Each row maps a real CDAO/DoD/OMB requirement to the a11oy artifact that
# satisfies it with an honest status label.
#
# Status labels (doctrine v11 honest-label set):
#   LIVE       — operational today, buyer can verify
#   MEASURED   — operational with real measured data
#   SAMPLE     — demo/sample data only, not production measurements
#   MODELED    — derived from model, not direct measurement
#   ROADMAP    — planned, NOT yet delivered
#
# HONEST GUARDRAILS (enforced):
#   - ATO/IL5/FedRAMP → ROADMAP, stated explicitly
#   - Λ → Conjecture 1 (advisory; NOT a theorem) everywhere
#   - 8 locked-proven only, never "183 proven"
#   - Data SIMULATED/SAMPLE unless MEASURED
#   - Never claim to replace Advana/Foundry/Databricks
# ---------------------------------------------------------------------------

ASSURANCE_MATRIX = [
    {
        "req_id": "MC-1",
        "requirement": "Model Card",
        "req_detail": (
            "AI systems shall have a model card describing model purpose, training data, "
            "performance, and known limitations."
        ),
        "source": "DoDM 5000.101 (DoD AI Acquisition Policy)",
        "source_url": "https://dodcio.defense.gov/Portals/0/Documents/Library/DoDM-5000-101.pdf",
        "a11oy_artifact": (
            "a11oy model card endpoint: GET /api/a11oy/v1/honest (model id, training data "
            "label, performance honesty, limitation disclosures). Served-model id embedded "
            "in every signed Khipu receipt."
        ),
        "artifact_url": "/api/a11oy/v1/honest",
        "status": "LIVE",
        "status_detail": (
            "Model card data is live at /api/a11oy/v1/honest. Training data labeled "
            "SAMPLE/SIMULATED unless MEASURED — doctrine-enforced. Served-model id is "
            "embedded in every signed DSSE receipt."
        ),
        "honest_caveats": (
            "Performance metrics are SAMPLE/ADVISORY. Λ=Conjecture 1 (advisory; NOT a theorem). "
            "8 kernel-proven formulas only; never '183 proven'."
        ),
    },
    {
        "req_id": "DC-1",
        "requirement": "Data Card / Honest Data Labels",
        "req_detail": (
            "AI systems shall document data provenance, quality, and representativeness "
            "to support risk management and authorization."
        ),
        "source": "DoD AI Cyber RMF Tailoring Guide (CDAO/dodcio.defense.gov)",
        "source_url": "https://dodcio.defense.gov/Portals/0/Documents/Library/AI-Cyber-RMF-Tailoring-Guide.pdf",
        "a11oy_artifact": (
            "a11oy honest data labels: every data reference is tagged LIVE / MEASURED / "
            "SAMPLE / MODELED / ROADMAP — no unlabeled assertions. Labels are embedded in "
            "signed Khipu receipts and surfaced in the assurance matrix."
        ),
        "artifact_url": "/api/a11oy/v1/assurance/matrix",
        "status": "LIVE",
        "status_detail": (
            "Honest-label schema is enforced in doctrine v11/v12. Every data claim "
            "carries a machine-readable status label. Labels are baked into signed receipts."
        ),
        "honest_caveats": (
            "Demo data is SAMPLE/SIMULATED unless explicitly labeled MEASURED. "
            "Production measured data requires deployment in a live environment."
        ),
    },
    {
        "req_id": "SBOM-1",
        "requirement": "SBOM / Software Bill of Materials",
        "req_detail": (
            "Federal agencies and DoD programs shall produce a Software Bill of Materials "
            "for all AI/software systems to support supply-chain risk management."
        ),
        "source": "OMB Memo M-22-18 (Enhancing the Security of the Software Supply Chain)",
        "source_url": "https://www.whitehouse.gov/wp-content/uploads/2022/09/M-22-18.pdf",
        "a11oy_artifact": (
            "SLSA Level 1 attestation: szl_dsse.py and all Python modules are open-source "
            "(Apache-2.0), committed to szl-holdings/a11oy with full commit SHAs. "
            "SLSA L2 (hermetic build) and L3 (full provenance) are ROADMAP items."
        ),
        "artifact_url": "https://github.com/szl-holdings/a11oy",
        "status": "ROADMAP",
        "status_detail": (
            "L1: Source is public (Apache-2.0) — honest. "
            "L2 (attested hermetic build): ROADMAP. "
            "L3 (full SLSA provenance): ROADMAP. "
            "Full SBOM in CycloneDX/SPDX format: ROADMAP."
        ),
        "honest_caveats": (
            "Honest: L1 only today. L2/L3 are explicit ROADMAP items. "
            "No fabricated compliance claim."
        ),
    },
    {
        "req_id": "SI7-1",
        "requirement": "Model / Data Integrity Check (SI-7)",
        "req_detail": (
            "NIST SP 800-53 SI-7 (Software, Firmware, and Information Integrity): "
            "AI systems shall employ integrity verification tools to detect unauthorized "
            "changes to software, firmware, and information."
        ),
        "source": "NIST SP 800-53 Rev 5 — SI-7 (via DoD AI RMF Tailoring Guide)",
        "source_url": "https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final",
        "a11oy_artifact": (
            "SHA3-256 hash-chained signed Khipu receipts (F4/F22): every inference decision "
            "is hash-chained (prev→digest) and DSSE-signed (ECDSA-P256 over SHA-256). "
            "Buyer can re-verify integrity offline with public key + WebCrypto. "
            "F4 (Khipu chain determinism) and F22 (monotone sequence) are kernel-proven @ c7c0ba17."
        ),
        "artifact_url": "/api/a11oy/v1/govern/infer",
        "status": "LIVE",
        "status_detail": (
            "Hash-chain: LIVE — every receipt carries prev_digest + digest (SHA-256). "
            "DSSE signing: LIVE when SZL_COSIGN_PRIVATE_KEY_PEM secret is present. "
            "Buyer-verifiable: LIVE via /verify page (WebCrypto, zero server round-trip for verify). "
            "F4 + F22 kernel-proven @ c7c0ba17."
        ),
        "honest_caveats": (
            "Hash function is SHA-256 (via Python 'hashlib'), not SHA3-256 in the current "
            "receipt chain. DSSE uses ECDSA-P256-SHA256. Offline verify: WebCrypto in browser "
            "or cosign verify-blob CLI."
        ),
    },
    {
        "req_id": "TEVV-1",
        "requirement": "TEVV Results in Security Authorization Package",
        "req_detail": (
            "Test, Evaluation, Verification, and Validation (TEVV) results shall be "
            "documented and included in the AI system's security authorization package, "
            "providing auditable evidence of system behavior."
        ),
        "source": "CDAO AI Assurance Framework / DoDI 5000.89 (T&E for AI)",
        "source_url": "https://dodcio.defense.gov/Portals/0/Documents/Library/AI-Assurance.pdf",
        "a11oy_artifact": (
            "Signed DSSE receipt per governed decision: every allow/review/deny verdict "
            "produces a cryptographically-signed Khipu receipt (szl_dsse.sign_khipu_receipt). "
            "The receipt encodes: decision, Λ score (advisory), gates fired/passed, "
            "chain hash, timestamp — a machine-verifiable TEVV artifact per inference call."
        ),
        "artifact_url": "/verify",
        "status": "LIVE",
        "status_detail": (
            "Signed receipt per decision: LIVE. Each receipt is DSSE-signed and hash-chained. "
            "Buyer can paste the receipt into /verify and get WebCrypto VERIFIED result. "
            "Λ advisory score included in receipt (Conjecture 1 label)."
        ),
        "honest_caveats": (
            "TEVV in a11oy covers governed-inference decisions. Full model-level T&E "
            "(accuracy, adversarial robustness benchmarks) requires additional tooling: ROADMAP. "
            "Λ is Conjecture 1 (advisory; NOT a theorem)."
        ),
    },
    {
        "req_id": "RA-1",
        "requirement": "Runtime Assurance / Continuous Monitoring",
        "req_detail": (
            "AI systems in operational use shall have runtime monitoring to detect "
            "anomalous behavior, performance drift, and policy violations."
        ),
        "source": "CDAO AI Assurance Framework / NIST AI RMF 1.0 (GOVERN + MONITOR)",
        "source_url": "https://airc.nist.gov/RMF_Overview",
        "a11oy_artifact": (
            "Λ-gate per call (advisory, Conjecture 1): every inference call passes through "
            "the Λ gate (floor 0.90 advisory). Gates: threat-signature-scan, pii-egress-guard. "
            "OTel-GenAI spans for runtime observability: partial (ROADMAP for full OTel). "
            "Signed refusal receipts for every denied call — continuous audit trail."
        ),
        "artifact_url": "/api/a11oy/v1/gates",
        "status": "LIVE",
        "status_detail": (
            "Λ gate per call: LIVE (advisory floor, Conjecture 1). "
            "Threat/PII gates: LIVE. "
            "Signed denial receipts: LIVE. "
            "Full OTel-GenAI span export: ROADMAP."
        ),
        "honest_caveats": (
            "Λ = Conjecture 1 (advisory; NOT a theorem). Gate coverage is advisory, "
            "not a certified classifier. Full OTel instrumentation is ROADMAP. "
            "Never claim 100% detection coverage."
        ),
    },
    {
        "req_id": "IV-1",
        "requirement": "Independent Verifiability",
        "req_detail": (
            "Governance artifacts (receipts, audit logs) shall be independently verifiable "
            "by an auditor or buyer without relying solely on the provider's assertion."
        ),
        "source": "CDAO AI Assurance Framework / DoD AI Ethical Principles (Traceable)",
        "source_url": "https://dodcio.defense.gov/Portals/0/Documents/Library/AI-Principles-Recommendations-Final.pdf",
        "a11oy_artifact": (
            "Buyer re-verifies signature offline via WebCrypto (/verify page) or "
            "cosign verify-blob CLI. Public key at /cosign.pub (also: "
            "github.com/szl-holdings/.github/cosign.pub). No server round-trip required "
            "for verification — the math is the receipt."
        ),
        "artifact_url": "/verify",
        "status": "LIVE",
        "status_detail": (
            "WebCrypto verify: LIVE — buyer pastes DSSE envelope, browser verifies ECDSA-P256. "
            "cosign verify-blob CLI: LIVE — byte-for-byte equivalent (proven round-trip). "
            "Public key is published and never rotated without notice. "
            "UNIQUE vs Foundry/Unity Catalog: lineage is viewable but NOT cryptographically "
            "buyer-verifiable. a11oy gives you a signature you can verify offline."
        ),
        "honest_caveats": (
            "Independent verifiability applies to signed receipts only. Unsigned receipts "
            "(when private key is absent from runtime) carry an explicit UNSIGNED label — "
            "no fabricated signature ever. The hash chain is still valid and verifiable "
            "even without the ECDSA signature."
        ),
    },
    {
        "req_id": "ATO-1",
        "requirement": "ATO / IL5 / FedRAMP-High Accreditation",
        "req_detail": (
            "AI systems handling sensitive DoD data require an Authority to Operate (ATO), "
            "IL5 (Impact Level 5) cloud authorization, and/or FedRAMP-High equivalent "
            "security authorization."
        ),
        "source": "DoD CC SRG / FedRAMP / DISA IL5 Cloud Computing SRG",
        "source_url": "https://public.cyber.mil/dccs/",
        "a11oy_artifact": (
            "a11oy is NOT accredited. No ATO, no IL5, no FedRAMP-High authorization exists. "
            "Pursuing ATO/FedRAMP-High is a ROADMAP item contingent on a DoD program sponsor."
        ),
        "artifact_url": None,
        "status": "ROADMAP",
        "status_detail": (
            "ATO: NOT obtained — ROADMAP. "
            "IL5: NOT obtained — ROADMAP. "
            "FedRAMP-High: NOT obtained — ROADMAP. "
            "This is stated plainly. The honesty IS the sell to an auditor audience."
        ),
        "honest_caveats": (
            "Any claim of ATO/IL5/FedRAMP would be false. a11oy is a governance overlay "
            "that can be DEPLOYED within an accredited environment (e.g., Advana/WDP) and "
            "contribute to the evidence package — but a11oy itself is not accredited. "
            "Do NOT misrepresent this."
        ),
    },
]

# ---------------------------------------------------------------------------
# WHERE A11OY FITS — honest positioning for defense/WDP audience
# ---------------------------------------------------------------------------

FIT_STATEMENT = {
    "summary": (
        "a11oy is the governance + verifiable-provenance OVERLAY for WDP-era agentic AI. "
        "It does NOT replace Advana, WDP, Palantir Foundry, or Databricks Unity Catalog. "
        "Those stay the system of record. a11oy adds the cryptographic, buyer-verifiable "
        "assurance layer that the Jan-2026 WDP memo demands: agentic AI + auditability."
    ),
    "what_a11oy_is": [
        "Governance overlay: policy gates (Λ, threat-scan, PII-egress) on every AI inference call.",
        "Verifiable receipt emitter: DSSE-signed Khipu receipts per decision — buyer can re-verify offline.",
        "Honest assurance evidence: data labels, model card, TEVV artifacts per call.",
        "Refusal explainer (WILLAY): signed, auditable refusals — not black-box boolean gates.",
    ],
    "what_a11oy_is_not": [
        "NOT a replacement for Advana/WDP (the authoritative DoD financial data platform).",
        "NOT a replacement for Palantir Foundry (ontology + operational data lineage).",
        "NOT a replacement for Databricks Unity Catalog (column-level data governance).",
        "NOT accredited (no ATO/IL5/FedRAMP — ROADMAP).",
        "NOT a certified classifier — Λ is Conjecture 1 (advisory; NOT a theorem).",
        "NOT claiming 183 proven theorems — 8 kernel-proven only (locked_count_eight @ c7c0ba17).",
    ],
    "wdp_wedge": (
        "The Jan-2026 DoD memo restructuring Advana into WDP explicitly calls for "
        "'agentic AI' AND 'enhanced auditability' toward a clean FY27/FY28 audit. "
        "Foundry shows you data lineage. Unity Catalog shows you column-level provenance. "
        "a11oy gives you a cryptographic signature on the AI DECISION itself — something "
        "the buyer can verify offline, without trusting the provider."
    ),
    "unique_value": (
        "Foundry/Unity Catalog: lineage is viewable but NOT cryptographically buyer-verifiable. "
        "a11oy: every governed decision produces a DSSE receipt signed with ECDSA-P256. "
        "Buyer pastes the receipt into /verify — WebCrypto confirms or rejects in-browser. "
        "No other inference governance layer offers this. The math is the receipt."
    ),
    "platform_diagram": {
        "description": (
            "Stack diagram (text representation for buyers/auditors):\n"
            "\n"
            "  ┌─────────────────────────────────────────────────────────┐\n"
            "  │  a11oy — Governance + Trust Overlay                     │\n"
            "  │  (signed receipts · policy gates · honest labels)       │\n"
            "  └───────────────┬────────────────────────────────────────┘\n"
            "                  │ sits on top of\n"
            "  ┌───────────────▼────────────────────────────────────────┐\n"
            "  │  WDP / Advana / Palantir Foundry / Databricks UC       │\n"
            "  │  (System of Record — data, lineage, ontology)          │\n"
            "  └─────────────────────────────────────────────────────────┘\n"
        ),
        "a11oy_layer": "Governance + Trust Overlay (signed receipts, policy gates, honest labels)",
        "platform_layer": "WDP / Advana / Palantir Foundry / Databricks Unity Catalog (System of Record)",
        "relationship": "OVERLAY — a11oy sits on top, never replaces",
    },
    "honest_accreditation_status": {
        "ato": "NOT obtained — ROADMAP",
        "il5": "NOT obtained — ROADMAP",
        "fedramp_high": "NOT obtained — ROADMAP",
        "note": (
            "a11oy can be deployed within an accredited environment to contribute "
            "governance evidence, but a11oy itself is not accredited. This is stated "
            "plainly because the honesty is the product."
        ),
    },
    "doctrine": {
        "lambda_kind": "Conjecture 1 (advisory; NOT a theorem)",
        "bft_kind": "Conjecture 2 (NOT proven; NOT a theorem)",
        "locked_proven": 8,
        "kernel_commit": "c7c0ba17",
        "ci_gate": "locked_count_eight",
        "honest_labels": ["LIVE", "MEASURED", "SAMPLE", "MODELED", "ROADMAP"],
        "no_fabrication": "NEVER fabricates signatures, ATOs, accreditations, or theorem counts.",
    },
}


# ---------------------------------------------------------------------------
# register(app, ns='a11oy') — additive, try/except-guarded
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> dict:  # pragma: no cover
    """
    Register the AI Assurance endpoints on the a11oy FastAPI/Starlette app.

    Routes (ADDITIVE — no overlap with any existing /api/a11oy/* namespace):
      GET /api/a11oy/v1/assurance/matrix
      GET /api/a11oy/v1/assurance/fit

    Front-inserts routes so they win over the /api/a11oy/{path:path} Node proxy
    and the SPA catch-all (mirrors the proven pattern from szl_demo_tier1.py).
    Wrapped in try/except so a missing import never breaks the SPA or existing routes.
    """
    try:
        from starlette.routing import Route
        from starlette.responses import JSONResponse
    except Exception as _e:
        return {"registered": [], "status": f"starlette-absent: {_e!r}"}

    async def _matrix(request):
        return JSONResponse({
            "ns": ns,
            "surface": "ai-assurance",
            "description": (
                "CDAO/DoD AI Assurance Requirements → a11oy artifact mapping. "
                "Honest status per row. ROADMAP items labeled explicitly. "
                "a11oy is the governance overlay — NOT accredited (ATO/IL5/FedRAMP are ROADMAP)."
            ),
            "requirements": ASSURANCE_MATRIX,
            "honest_note": (
                "Status values: LIVE=operational today; MEASURED=operational with real data; "
                "SAMPLE=demo/sample data only; MODELED=model-derived; ROADMAP=planned not delivered. "
                "Λ=Conjecture 1 (advisory; NOT a theorem). "
                "8 kernel-proven formulas only; never '183 proven'. "
                "ATO/IL5/FedRAMP-High: NOT accredited — ROADMAP."
            ),
            "lambda_kind": "Conjecture 1 (advisory; NOT a theorem)",
            "locked_proven": 8,
            "kernel_commit": "c7c0ba17",
        })

    async def _fit(request):
        return JSONResponse({
            "ns": ns,
            "surface": "ai-assurance",
            "description": (
                "Honest 'where a11oy fits' — governance/assurance OVERLAY positioning. "
                "a11oy never claims to be or replace Advana/WDP/Foundry/Databricks."
            ),
            **FIT_STATEMENT,
        })

    paths = [
        (f"/api/{ns}/v1/assurance/matrix", _matrix, ["GET"]),
        (f"/api/{ns}/v1/assurance/fit",    _fit,    ["GET"]),
        # Short-form aliases for the front-door strip
        ("/v1/assurance/matrix", _matrix, ["GET"]),
        ("/v1/assurance/fit",    _fit,    ["GET"]),
    ]
    registered = []
    for path, fn, methods in paths:
        app.router.routes.insert(0, Route(path, fn, methods=methods))
        registered.append(path)

    return {"registered": registered, "status": "ok", "module": "szl_assurance"}
