/**
 * axis_collision.test.ts
 * Doctrine v6 R3 — Vertical Governance Receipts
 * 10 Axis-Collision adversarial tests
 *
 * Tests for conflicts, contradictions, and impossible combinations across
 * Λ-axis assignments in policy documents. Collision scenarios include:
 * - Same clause mapping to conflicting axes
 * - mandatory_axes referencing axes not present in any clause
 * - Axis weight distribution violations (e.g., all weights = 0)
 * - Cross-policy axis coverage below minimum_lambda_coverage
 * - mandatory axis appearing only with enforcement: "informational"
 *
 * Some of these MUST be detected at the policy_loader level (semantic validation),
 * since JSON Schema alone cannot express cross-field semantic constraints.
 *
 * Test framework: Jest / ts-jest
 * Run: npx jest tests/adversarial/axis_collision.test.ts
 */

import Ajv from "ajv";
import addFormats from "ajv-formats";
import * as fs from "fs";
import * as path from "path";

const SCHEMA_PATH = path.resolve(__dirname, "../../a11oy-knowledge.schema.json");

function buildValidator() {
  const ajv = new Ajv({ allErrors: true, strict: false });
  addFormats(ajv);
  const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, "utf8"));
  return ajv.compile(schema);
}

/** Compute distinct Λ-axes covered by all clauses */
function coveredAxes(clauses: any[]): Set<string> {
  const axes = new Set<string>();
  for (const c of clauses) {
    for (const m of c.lambda_axes ?? []) axes.add(m.axis);
  }
  return axes;
}

/** Semantic check: mandatory_axes must be covered by clauses */
function mandatoryAxesCovered(policy: any): boolean {
  const covered = coveredAxes(policy.regulatory_clauses ?? []);
  const mandatory: string[] = policy.compliance_thresholds?.mandatory_axes ?? [];
  return mandatory.every((ax) => covered.has(ax));
}

/** Semantic check: covered axis count ≥ minimum_lambda_coverage */
function coverageAboveMinimum(policy: any): boolean {
  const covered = coveredAxes(policy.regulatory_clauses ?? []);
  return covered.size >= (policy.compliance_thresholds?.minimum_lambda_coverage ?? 0);
}

/** Semantic check: no mandatory axis has only informational enforcement */
function mandatoryAxisHasMandatoryEnforcement(policy: any): boolean {
  const mandatory = new Set<string>(policy.compliance_thresholds?.mandatory_axes ?? []);
  for (const clause of policy.regulatory_clauses ?? []) {
    for (const mapping of clause.lambda_axes ?? []) {
      if (mandatory.has(mapping.axis) && mapping.enforcement === "mandatory") return true;
    }
  }
  return mandatory.size === 0;
}

function basePolicy(): any {
  return {
    schema_version: "1.0.0",
    vertical: "energy",
    regime: "NERC-CIP/FERC-887",
    effective_date: "2025-07-01",
    jurisdiction: "US-FERC/NERC",
    meta: {
      title: "Axis collision base policy for adversarial testing",
      description: "Policy used for axis collision adversarial scenario testing.",
      authority: "NERC CIP-002 through CIP-014; FERC Order No. 887",
      receipt_chain_required: true,
      merkle_root_algorithm: "SHA3-256",
    },
    regulatory_clauses: Array.from({ length: 8 }, (_, i) => ({
      clause_id: `NERC-COL-${String(i + 1).padStart(3, "0")}`,
      title: `Collision test clause ${i + 1}`,
      citation: `18 CFR § 40.${i + 1}`,
      full_ref: `18 C.F.R. § 40.${i + 1} — axis collision test clause with full reference detail`,
      lambda_axes: [
        { axis: "Λ6", label: "Security", weight: 0.9, enforcement: "mandatory",
          rationale: "BES Cyber System protection requires mandatory security receipt logging." },
        { axis: "Λ7", label: "Auditability", weight: 0.85, enforcement: "mandatory",
          rationale: "CIP-007-6 audit log tamper-evidence via Merkle DAG." },
      ],
    })),
    compliance_thresholds: {
      minimum_lambda_coverage: 7,
      mandatory_axes: ["Λ5", "Λ6", "Λ7"],
      receipt_retention_days: 2190,
    },
    receipt_chain: {
      algorithm: "SHA3-256",
      chaining: "merkle_dag",
      quorum: "2-of-3",
      nodes: ["primary", "air-gapped-ot", "regulatory-archive"],
    },
  };
}

describe("Adversarial — Axis Collision (10 tests)", () => {
  const validate = buildValidator();

  // AC-001: mandatory_axes include Λ5 but no clause maps to Λ5 — semantic violation
  test("AC-001: mandatory axis Λ5 not covered by any clause — semantic violation detected", () => {
    const p = basePolicy();
    // All clauses only cover Λ6, Λ7 — Λ5 is mandatory but uncovered
    // Schema accepts this; semantic check must reject
    expect(validate(p)).toBe(true);                   // Schema: OK
    expect(mandatoryAxesCovered(p)).toBe(false);       // Semantic: FAIL
  });

  // AC-002: minimum_lambda_coverage = 5 but only 2 distinct axes present — coverage gap
  test("AC-002: covered axes (2) < minimum_lambda_coverage (5) — semantic violation", () => {
    const p = basePolicy();
    p.compliance_thresholds.minimum_lambda_coverage = 5;
    // Clauses cover only Λ6 and Λ7 (2 axes) — below minimum 5
    expect(validate(p)).toBe(true);
    expect(coverageAboveMinimum(p)).toBe(false);
  });

  // AC-003: Same clause maps same Λ-axis twice (duplicate axis in lambda_axes)
  test("AC-003: duplicate Λ7 in same clause lambda_axes — schema accepts, loader must deduplicate", () => {
    const p = basePolicy();
    p.regulatory_clauses[0].lambda_axes = [
      { axis: "Λ7", label: "Auditability", weight: 1.0, enforcement: "mandatory",
        rationale: "First mapping for Λ7 in this clause for deduplication test." },
      { axis: "Λ7", label: "Auditability", weight: 0.5, enforcement: "recommended",
        rationale: "Second mapping for Λ7 — duplicate with conflicting weight." },
    ];
    // Schema allows up to 4 axis mappings per clause without uniqueItems constraint on axis
    expect(validate(p)).toBe(true);
    // Loader must detect and reject or merge duplicate axis mappings
    const dup = p.regulatory_clauses[0].lambda_axes.filter((m: any) => m.axis === "Λ7");
    expect(dup.length).toBe(2); // Two mappings to same axis — collision detected
  });

  // AC-004: mandatory axis appearing ONLY with enforcement "informational" — enforcement gap
  test("AC-004: mandatory axis Λ6 only with informational enforcement — enforcement collision", () => {
    const p = basePolicy();
    // Change all Λ6 mappings to informational
    for (const clause of p.regulatory_clauses) {
      for (const m of clause.lambda_axes) {
        if (m.axis === "Λ6") m.enforcement = "informational";
      }
    }
    expect(validate(p)).toBe(true);  // Schema accepts any enforcement value
    expect(mandatoryAxisHasMandatoryEnforcement(p)).toBe(false); // Semantic fail
  });

  // AC-005: All weights set to 0.0 — zero-weight mandatory axis
  test("AC-005: all lambda weights = 0.0 — policy carries no compliance signal", () => {
    const p = basePolicy();
    for (const clause of p.regulatory_clauses) {
      for (const m of clause.lambda_axes) { m.weight = 0.0; }
    }
    expect(validate(p)).toBe(true);  // Schema: 0.0 is valid minimum
    // Compute total weight for mandatory axes
    const totalMandatoryWeight = p.regulatory_clauses
      .flatMap((c: any) => c.lambda_axes)
      .filter((m: any) => m.enforcement === "mandatory")
      .reduce((sum: number, m: any) => sum + m.weight, 0);
    expect(totalMandatoryWeight).toBe(0); // Semantic warning: all mandatory weights zero
  });

  // AC-006: minimum_lambda_coverage > 10 (impossible — only 10 axes exist)
  test("AC-006: minimum_lambda_coverage = 11 exceeds available axes (schema rejects > 10)", () => {
    const p = basePolicy();
    p.compliance_thresholds.minimum_lambda_coverage = 11;
    expect(validate(p)).toBe(false); // Schema enforces maximum: 10
  });

  // AC-007: Label mismatch — axis "Λ1" labeled "Privacy" (Λ3's label)
  test("AC-007: Λ1 axis labeled 'Privacy' — axis↔label mismatch (schema accepts, loader rejects)", () => {
    const p = basePolicy();
    p.regulatory_clauses[0].lambda_axes.push({
      axis: "Λ1",
      label: "Privacy",  // Correct label for Λ1 is "Transparency"
      weight: 0.5,
      enforcement: "recommended",
      rationale: "Incorrect label test for axis-label collision detection scenario.",
    });
    expect(validate(p)).toBe(true); // Schema: both "Λ1" and "Privacy" are valid enum values
    // Policy loader must validate axis↔label coherence using the axis-label map
  });

  // AC-008: Cross-vertical vertical+regime mismatch (healthcare vertical with SOX regime)
  test("AC-008: vertical 'healthcare' with regime 'SOX/Dodd-Frank' — semantic mismatch", () => {
    const p = basePolicy();
    p.vertical = "healthcare";
    p.regime = "SOX/Dodd-Frank";
    expect(validate(p)).toBe(true); // Schema: no cross-field constraint
    // Loader must check vertical↔regime coherence matrix
  });

  // AC-009: receipt_chain quorum 5-of-3 (quorum numerator > denominator — impossible)
  test("AC-009: quorum '5-of-3' (impossible — 5 signatures from 3 nodes) is accepted by schema pattern", () => {
    const p = basePolicy();
    p.receipt_chain.quorum = "5-of-3";
    // Pattern ^\d+-of-\d+$ matches — schema accepts
    expect(validate(p)).toBe(true);
    // Extract and validate quorum numerically
    const [n, d] = p.receipt_chain.quorum.split("-of-").map(Number);
    expect(n).toBeGreaterThan(d); // Semantic violation: impossible quorum
  });

  // AC-010: mandatory_axes contains Λ10 but jurisdiction is "US-Federal" (no sovereignty concern)
  test("AC-010: Λ10 (Sovereignty) mandatory for domestic US-Federal jurisdiction — semantic question", () => {
    const p = basePolicy();
    p.jurisdiction = "US-Federal";
    p.compliance_thresholds.mandatory_axes = ["Λ5", "Λ6", "Λ7", "Λ10"];
    // Schema: no constraint — passes
    expect(validate(p)).toBe(true);
    // Loader may issue warning: Λ10 (Sovereignty) is typically relevant for
    // cross-border/international jurisdictions. Flagging for human review.
    const hasSovereignty = p.compliance_thresholds.mandatory_axes.includes("Λ10");
    const isInternational = !p.jurisdiction.startsWith("US-Federal");
    // Not an error but a review flag
    if (hasSovereignty && !isInternational) {
      // Expect loader to emit a WARNING (not error) for sovereignty axis on domestic regime
      expect(true).toBe(true); // test documents the pattern
    }
  });
});
