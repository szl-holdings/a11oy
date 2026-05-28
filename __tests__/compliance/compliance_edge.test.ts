/**
 * compliance_edge.test.ts
 * Doctrine v6 R3 — Vertical Governance Receipts
 * 10 EDGE cases: boundary conditions, degenerate-but-valid inputs, and
 * schema-legal extremes that must validate correctly (or reject as expected).
 *
 * Test framework: Jest / ts-jest
 * Run: npx jest tests/compliance/compliance_edge.test.ts
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

function basePolicy(overrides: Partial<any> = {}): any {
  return Object.assign(
    {
      schema_version: "1.0.0",
      vertical: "financial",
      regime: "SOX/Dodd-Frank",
      effective_date: "2025-01-01",
      jurisdiction: "US-Federal",
      meta: {
        title: "Financial AI Policy base for edge testing",
        description: "Base policy for edge case compliance testing with sufficient description length.",
        authority: "Pub. L. 107-204; Pub. L. 111-203",
        receipt_chain_required: true,
        merkle_root_algorithm: "SHA3-256",
      },
      regulatory_clauses: Array.from({ length: 8 }, (_, i) => ({
        clause_id: `SOX-EDGE-${String(i + 1).padStart(3, "0")}`,
        title: `Edge test clause ${i + 1}`,
        citation: `17 CFR § 240.${i + 10}`,
        full_ref: `Full reference: 17 C.F.R. § 240.${i + 10} — Edge test clause for compliance testing`,
        lambda_axes: [
          { axis: "Λ7", label: "Auditability", weight: 1.0, enforcement: "mandatory", rationale: "Tamper-evident receipt chain required for all financial AI decisions." },
        ],
      })),
      compliance_thresholds: {
        minimum_lambda_coverage: 7,
        mandatory_axes: ["Λ2", "Λ7"],
        receipt_retention_days: 2555,
      },
      receipt_chain: {
        algorithm: "SHA3-256",
        chaining: "merkle_dag",
        quorum: "2-of-3",
        nodes: ["primary", "secondary", "audit"],
      },
    },
    overrides
  );
}

describe("Compliance EDGE — boundary and degenerate-valid cases", () => {
  const validate = buildValidator();

  // EDGE-001: Exactly 8 regulatory_clauses (lower boundary, must pass)
  test("EDGE-001: exactly 8 regulatory_clauses (lower bound) is accepted", () => {
    const p = basePolicy();
    expect(p.regulatory_clauses.length).toBe(8);
    expect(validate(p)).toBe(true);
  });

  // EDGE-002: Exactly 12 regulatory_clauses (upper boundary, must pass)
  test("EDGE-002: exactly 12 regulatory_clauses (upper bound) is accepted", () => {
    const p = basePolicy();
    p.regulatory_clauses = Array.from({ length: 12 }, (_, i) => ({
      clause_id: `SOX-UP-${String(i + 1).padStart(3, "0")}`,
      title: `Upper bound clause ${i + 1}`,
      citation: `17 CFR § 240.${i + 50}`,
      full_ref: `Full reference: 17 C.F.R. § 240.${i + 50} — upper boundary test clause`,
      lambda_axes: [
        { axis: "Λ2", label: "Accountability", weight: 0.8, enforcement: "mandatory", rationale: "Accountability requirement for financial AI systems under SOX." },
      ],
    }));
    expect(validate(p)).toBe(true);
  });

  // EDGE-003: weight exactly 0.0 (minimum) is accepted
  test("EDGE-003: lambda weight 0.0 (minimum) is accepted", () => {
    const p = basePolicy();
    p.regulatory_clauses[0].lambda_axes[0].weight = 0.0;
    expect(validate(p)).toBe(true);
  });

  // EDGE-004: weight exactly 1.0 (maximum) is accepted
  test("EDGE-004: lambda weight 1.0 (maximum) is accepted", () => {
    const p = basePolicy();
    p.regulatory_clauses[0].lambda_axes[0].weight = 1.0;
    expect(validate(p)).toBe(true);
  });

  // EDGE-005: mandatory_axes with single element (minimum array) is accepted
  test("EDGE-005: mandatory_axes with 1 element is accepted", () => {
    const p = basePolicy();
    p.compliance_thresholds.mandatory_axes = ["Λ7"];
    expect(validate(p)).toBe(true);
  });

  // EDGE-006: mandatory_axes with all 10 axes (maximum) is accepted
  test("EDGE-006: mandatory_axes with all 10 Λ-axes is accepted", () => {
    const p = basePolicy();
    p.compliance_thresholds.mandatory_axes = ["Λ1","Λ2","Λ3","Λ4","Λ5","Λ6","Λ7","Λ8","Λ9","Λ10"];
    expect(validate(p)).toBe(true);
  });

  // EDGE-007: receipt_retention_days exactly 365 (minimum) is accepted
  test("EDGE-007: receipt_retention_days 365 (minimum) is accepted", () => {
    const p = basePolicy();
    p.compliance_thresholds.receipt_retention_days = 365;
    expect(validate(p)).toBe(true);
  });

  // EDGE-008: nodes array with exactly 2 elements (minimum) is accepted
  test("EDGE-008: receipt_chain nodes with 2 elements (minimum) is accepted", () => {
    const p = basePolicy();
    p.receipt_chain.nodes = ["primary", "backup"];
    expect(validate(p)).toBe(true);
  });

  // EDGE-009: nodes array with 7 elements (maximum) is accepted
  test("EDGE-009: receipt_chain nodes with 7 elements (maximum) is accepted", () => {
    const p = basePolicy();
    p.receipt_chain.nodes = ["n1","n2","n3","n4","n5","n6","n7"];
    expect(validate(p)).toBe(true);
  });

  // EDGE-010: nodes array with 8 elements (exceeds maximum 7) is rejected
  test("EDGE-010: receipt_chain nodes with 8 elements (> max 7) is rejected", () => {
    const p = basePolicy();
    p.receipt_chain.nodes = ["n1","n2","n3","n4","n5","n6","n7","n8"];
    expect(validate(p)).toBe(false);
  });
});
