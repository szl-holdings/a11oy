/**
 * compliance_reject.test.ts
 * Doctrine v6 R3 — Vertical Governance Receipts
 * 10 REJECT cases: malformed or non-compliant policy documents are correctly
 * rejected by schema validation.
 *
 * Each test constructs a deliberately invalid policy object and asserts that
 * AJV validation returns false (the schema rejects it).
 *
 * Test framework: Jest / ts-jest
 * Run: npx jest tests/compliance/compliance_reject.test.ts
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

// ── Minimal valid base object (used as mutation seed) ─────────────────────────
function basePolicy(): any {
  return {
    schema_version: "1.0.0",
    vertical: "healthcare",
    regime: "HIPAA/HITECH",
    effective_date: "2025-07-01",
    jurisdiction: "US-Federal",
    meta: {
      title: "Healthcare AI Governance Policy — HIPAA Alignment",
      description: "Maps HIPAA provisions to Doctrine v6 axes for AI systems processing PHI.",
      authority: "45 CFR Parts 160, 162, 164",
      receipt_chain_required: true,
      merkle_root_algorithm: "SHA3-256",
    },
    regulatory_clauses: Array.from({ length: 8 }, (_, i) => ({
      clause_id: `CLAUSE-${i + 1}`,
      title: `Test clause ${i + 1}`,
      citation: `45 CFR § 164.${i + 100}`,
      full_ref: `Full reference for test clause ${i + 1} with adequate detail`,
      lambda_axes: [
        { axis: "Λ3", label: "Privacy", weight: 0.9, enforcement: "mandatory", rationale: "Test rationale for this axis mapping with sufficient length." },
      ],
    })),
    compliance_thresholds: {
      minimum_lambda_coverage: 6,
      mandatory_axes: ["Λ3", "Λ6", "Λ7"],
      receipt_retention_days: 2555,
    },
    receipt_chain: {
      algorithm: "SHA3-256",
      chaining: "merkle_dag",
      quorum: "2-of-3",
      nodes: ["primary", "backup", "audit"],
    },
  };
}

describe("Compliance REJECT — invalid policy documents rejected", () => {
  const validate = buildValidator();

  // REJECT-001: Missing required top-level field (schema_version)
  test("REJECT-001: missing schema_version is rejected", () => {
    const p = basePolicy();
    delete p.schema_version;
    expect(validate(p)).toBe(false);
  });

  // REJECT-002: Invalid vertical enum value
  test("REJECT-002: unknown vertical 'blockchain' is rejected", () => {
    const p = basePolicy();
    p.vertical = "blockchain";
    expect(validate(p)).toBe(false);
  });

  // REJECT-003: effective_date format violation (not ISO 8601 YYYY-MM-DD)
  test("REJECT-003: effective_date '07/01/2025' (MM/DD/YYYY) is rejected", () => {
    const p = basePolicy();
    p.effective_date = "07/01/2025";
    expect(validate(p)).toBe(false);
  });

  // REJECT-004: regulatory_clauses count below minimum (< 8)
  test("REJECT-004: fewer than 8 regulatory_clauses is rejected", () => {
    const p = basePolicy();
    p.regulatory_clauses = p.regulatory_clauses.slice(0, 5);
    expect(validate(p)).toBe(false);
  });

  // REJECT-005: regulatory_clauses count above maximum (> 12)
  test("REJECT-005: more than 12 regulatory_clauses is rejected", () => {
    const p = basePolicy();
    const extra = Array.from({ length: 5 }, (_, i) => ({
      clause_id: `EXTRA-${i}`,
      title: `Extra clause ${i}`,
      citation: `45 CFR § 999.${i}`,
      full_ref: `Full reference for extra clause ${i} with adequate length`,
      lambda_axes: [
        { axis: "Λ1", label: "Transparency", weight: 0.5, enforcement: "recommended", rationale: "Extra rationale for testing purposes." },
      ],
    }));
    p.regulatory_clauses = [...p.regulatory_clauses, ...extra];
    expect(validate(p)).toBe(false);
  });

  // REJECT-006: Invalid Λ-axis identifier (not in enum)
  test("REJECT-006: lambda axis 'Λ11' (out of range) is rejected", () => {
    const p = basePolicy();
    p.regulatory_clauses[0].lambda_axes[0].axis = "Λ11";
    expect(validate(p)).toBe(false);
  });

  // REJECT-007: weight out of range (> 1.0)
  test("REJECT-007: lambda weight 1.5 (> 1.0) is rejected", () => {
    const p = basePolicy();
    p.regulatory_clauses[0].lambda_axes[0].weight = 1.5;
    expect(validate(p)).toBe(false);
  });

  // REJECT-008: invalid receipt chain algorithm
  test("REJECT-008: receipt chain algorithm 'MD5' is rejected", () => {
    const p = basePolicy();
    p.receipt_chain.algorithm = "MD5";
    expect(validate(p)).toBe(false);
  });

  // REJECT-009: receipt_retention_days below minimum (< 365)
  test("REJECT-009: receipt_retention_days 30 (< 365) is rejected", () => {
    const p = basePolicy();
    p.compliance_thresholds.receipt_retention_days = 30;
    expect(validate(p)).toBe(false);
  });

  // REJECT-010: quorum string not matching N-of-M pattern
  test("REJECT-010: quorum 'majority' (not N-of-M format) is rejected", () => {
    const p = basePolicy();
    p.receipt_chain.quorum = "majority";
    expect(validate(p)).toBe(false);
  });
});
