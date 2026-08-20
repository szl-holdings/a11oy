# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""a11oy_grc_restraint.py — Restraint control contribution to the GRC surface (R5).

ADDITIVE-ONLY. This module contributes the a11oy Restraint capability (R1's governed
code-minimization / dependency-frugality ladder, /api/a11oy/v1/restraint/*) as a REAL
control contribution to the live /grc coverage matrix + OSCAL component-definition,
WITHOUT touching the shared a11oy_grc_data.py bytes (that file is owned elsewhere).
a11oy_grc.py imports this module and MERGES these rows into its /grc/matrix, /grc/oscal
and the /grc page.

WHY this is a real control contribution (not theatre): less code + fewer dependencies
is a measurable reduction in attack surface, supply-chain exposure and long-term
maintenance burden. The Restraint ladder (YAGNI → stdlib → native → installed-dep →
one-line → minimal-viable) is exactly the secure-by-design "economy of mechanism /
least functionality" principle applied before a diff is written, and every restraint
decision is a signed DSSE receipt + Λ-scored. We therefore honestly map it to the
supply-chain + maintainability + secure-engineering controls below.

HONEST (Doctrine v11): a11oy ALIGNS WITH / MAPS TO these frameworks — NEVER "certified"
or "compliant". No third-party certification obtained. Λ = Conjecture 1 (advisory, <1.0);
trust never 100%; 0 runtime CDN; the Restraint benchmark numbers are MODELED/MEASURED,
never overclaimed. Coverage states are HONEST: COVERED (specific testable mechanism),
PARTIAL (mechanism exists but incomplete), ROADMAP (planned). Gaps shown honestly.

Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List

CAPABILITY = "a11oy Restraint — governed code-minimization / dependency-frugality"
RESTRAINT_ENDPOINTS = "/api/a11oy/v1/restraint/{evaluate,bench,info}"

# Honest framing string, reused in payloads.
HONEST = ("a11oy Restraint contributes a code-minimization / dependency-frugality control: "
          "every code diff descends a governed 6-rung frugality ladder (YAGNI, stdlib, native, "
          "installed dependency, one line, then minimal viable code) BEFORE it is written, and "
          "each decision is a signed DSSE receipt + advisory Λ score. Less code and fewer "
          "dependencies => smaller attack/maintenance surface. ALIGNS WITH / MAPS TO the controls "
          "below — NOT a certification. Numbers are MODELED/MEASURED, never overclaimed.")

# ───────────────────────────────────────────────────────────────────────────
# Restraint coverage rows — same row shape as a11oy_grc_data.COVERAGE_MATRIX
# (control / framework / title / mechanism / coverage). These are MERGED into the
# live matrix by a11oy_grc.py; the shared data module is NOT edited.
# Frameworks chosen for supply-chain + maintainability + secure-engineering:
#   NIST 800-53r5: SA-8 (security engineering principles — economy of mechanism /
#     least functionality), SA-15 (development process), SR-3 (supply-chain controls),
#     CM-7 (least functionality).
#   NIST AI RMF: MANAGE 2.3 (manage residual / supply-chain risk).
#   ISO/IEC 42001: A.6.2 (AI system lifecycle / responsible development),
#     A.10.x supplier-adjacent (third-party / dependency frugality).
# ───────────────────────────────────────────────────────────────────────────
RESTRAINT_MATRIX_ROWS: List[Dict[str, str]] = [
    {"control": "SA-8", "framework": "NIST 800-53r5",
     "title": "Security engineering principles (economy of mechanism)",
     "mechanism": "Restraint 6-rung frugality ladder runs before every diff; the agent emits the "
                  "minimal viable code (fewest files, smallest surface); each decision is a signed "
                  "DSSE receipt + Λ score (/api/a11oy/v1/restraint/evaluate)",
     "coverage": "COVERED"},
    {"control": "CM-7", "framework": "NIST 800-53r5",
     "title": "Least functionality",
     "mechanism": "YAGNI rung skips speculative abstractions; the ladder prefers stdlib/native over "
                  "bespoke code, minimising functionality + attack surface. Auto-Review rule AR-006 "
                  "(prefer-minimal-diff) narrows a bloated diff that skipped the ladder",
     "coverage": "COVERED"},
    {"control": "SA-15", "framework": "NIST 800-53r5",
     "title": "Development process, standards & tools",
     "mechanism": "Restraint is wired into the dev path as a pre-write reflex with a promptfoo-style "
                  "two-arm benchmark (baseline vs restraint), honestly labelled MEASURED-or-SAMPLE/"
                  "ROADMAP; restraint: ceiling comments name each deliberate simplification's upgrade path",
     "coverage": "PARTIAL"},
    {"control": "SR-3", "framework": "NIST 800-53r5",
     "title": "Supply chain controls & processes",
     "mechanism": "Dependency-frugality: the 'already-installed dependency' rung prefers deps already "
                  "in the image and discourages adding new third-party packages, shrinking supply-chain "
                  "exposure. No formal SBOM gate on the restraint path yet",
     "coverage": "PARTIAL"},
    {"control": "MANAGE 2.3", "framework": "NIST AI RMF",
     "title": "Manage residual / supply-chain risk (code & dependency frugality)",
     "mechanism": "Restraint reduces residual maintenance + supply-chain risk by minimising generated "
                  "code and new dependencies; the Auto-Review classifier consumes the restraint verdict "
                  "as a governance signal (AR-006) and seals the rung into the signed verdict",
     "coverage": "COVERED"},
    {"control": "A.6.2", "framework": "ISO 42001",
     "title": "AI system lifecycle — responsible design & development",
     "mechanism": "Frugality ladder is applied in the design/development phase of the AI code agent; "
                  "deliberate simplifications are documented via restraint: ceiling comments and signed "
                  "receipts, supporting responsible, auditable development",
     "coverage": "PARTIAL"},
]

# OSCAL namespace prop (matches a11oy_grc_data convention).
_NS = "https://szlholdings.ai/ns/oscal"


def restraint_oscal_implemented_requirements() -> List[Dict[str, Any]]:
    """OSCAL implemented-requirements for the 800-53 restraint rows, in the same
    shape a11oy_grc_data.build_oscal() produces for its 800-53 rows. Merged into the
    live component-definition by a11oy_grc.py."""
    impl: List[Dict[str, Any]] = []
    for r in RESTRAINT_MATRIX_ROWS:
        if r["framework"] != "NIST 800-53r5":
            continue
        impl.append({
            "uuid": "ir-restraint-" + hashlib.sha256(("restraint:" + r["control"]).encode()).hexdigest()[:8],
            "control-id": r["control"].lower().replace(" ", "-"),
            "description": f"[{r['coverage']}] {r['mechanism']} (a11oy Restraint — {r['title']}).",
            "props": [
                {"name": "coverage", "ns": _NS, "value": r["coverage"]},
                {"name": "capability", "ns": _NS, "value": "a11oy-restraint"},
                {"name": "endpoint", "ns": _NS, "value": RESTRAINT_ENDPOINTS},
            ],
        })
    return impl


def restraint_descriptor() -> Dict[str, Any]:
    """Compact descriptor surfaced in /grc/matrix + /grc/info so the contribution
    is honestly attributed to the Restraint capability."""
    return {
        "capability": CAPABILITY,
        "endpoints": RESTRAINT_ENDPOINTS,
        "rows": len(RESTRAINT_MATRIX_ROWS),
        "controls": sorted({r["control"] for r in RESTRAINT_MATRIX_ROWS}),
        "frameworks": sorted({r["framework"] for r in RESTRAINT_MATRIX_ROWS}),
        "auto_review_rule": "AR-006-prefer-minimal-diff (OSCAL SA-8/SA-15/CM-7; NIST AI RMF MANAGE 2.3)",
        "honest": HONEST,
        "framing": "aligns with / maps to — NOT certified / compliant",
        "label": "ALIGNMENT",
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    assert all(r["coverage"] in ("COVERED", "PARTIAL", "ROADMAP", "NA") for r in RESTRAINT_MATRIX_ROWS)
    assert len(RESTRAINT_MATRIX_ROWS) >= 5
    irs = restraint_oscal_implemented_requirements()
    assert len(irs) == sum(1 for r in RESTRAINT_MATRIX_ROWS if r["framework"] == "NIST 800-53r5")
    print(json.dumps(restraint_descriptor(), indent=2))
    print("a11oy_grc_restraint: OK — %d rows, %d OSCAL implemented-requirements"
          % (len(RESTRAINT_MATRIX_ROWS), len(irs)))
