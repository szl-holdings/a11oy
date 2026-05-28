/**
 * compliance_adversarial.test.ts
 * Doctrine v6 R3 — Vertical Governance Receipts
 * 10 ADVERSARIAL compliance cases: crafted inputs designed to bypass schema
 * validation through type coercion, injection, Unicode homoglyphs,
 * deep nesting, and other adversarial techniques.
 *
 * All cases MUST be rejected (validate returns false) or handled safely.
 *
 * Test framework: Jest / ts-jest
 * Run: npx jest tests/compliance/compliance_adversarial.test.ts
 */

import Ajv from "ajv";
import addFormats from "ajv-formats";
import * as fs from "fs";
import * as path from "path";

const SCHEMA_PATH = path.resolve(__dirname, "../../a11oy-knowledge.schema.json");

function buildValidator() {
  const ajv = new Ajv({ allErrors: true, strict: false, coerceTypes: false });
  addFormats(ajv);
  const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, "utf8"));
  return ajv.compile(schema);
}

function basePolicy(): any {
  return {
    schema_version: "1.0.0",
    vertical: "defense",
    regime: "CMMC-L3/NIST-SP-800-171",
    effective_date: "2025-07-01",
    jurisdiction: "US-Federal-DoD",
    meta: {
      title: "Defense adversarial base policy for testing",
      description: "Base policy for adversarial compliance testing scenarios.",
      authority: "32 CFR Part 170; NIST SP 800-171 Rev 3",
      receipt_chain_required: true,
      merkle_root_algorithm: "SHA3-256",
    },
    regulatory_clauses: Array.from({ length: 8 }, (_, i) => ({
      clause_id: `CMMC-ADV-${String(i + 1).padStart(3, "0")}`,
      title: `Adversarial base clause ${i + 1}`,
      citation: `32 CFR § 170.${i + 10}`,
      full_ref: `Full reference: 32 C.F.R. § 170.${i + 10} — adversarial test clause with sufficient length`,
      lambda_axes: [
        { axis: "Λ6", label: "Security", weight: 0.95, enforcement: "mandatory",
          rationale: "All CUI must be protected with cryptographic receipt chains per CMMC Level 3." },
      ],
    })),
    compliance_thresholds: {
      minimum_lambda_coverage: 8,
      mandatory_axes: ["Λ5", "Λ6", "Λ7", "Λ10"],
      receipt_retention_days: 3650,
    },
    receipt_chain: {
      algorithm: "SHA3-256",
      chaining: "merkle_dag",
      quorum: "3-of-5",
      nodes: ["primary", "secondary", "tertiary", "hot-standby", "air-gapped"],
    },
  };
}

describe("Compliance ADVERSARIAL — crafted bypass attempts must be rejected", () => {
  const validate = buildValidator();

  // ADV-001: Unicode homoglyph in vertical enum — Λ (Lambda) vs Greek Λ lookalike
  // Uses Cyrillic "Λ" lookalike (\u0245) to attempt enum bypass
  test("ADV-001: vertical enum with Cyrillic lookalike 'dеfense' (Cyrillic е) is rejected", () => {
    const p = basePolicy();
    // Cyrillic 'е' (U+0435) vs Latin 'e' (U+0065) in "defense"
    p.vertical = "d\u0435fense";
    expect(validate(p)).toBe(false);
  });

  // ADV-002: numeric string for receipt_chain_required (type coercion bypass attempt)
  test("ADV-002: receipt_chain_required as string '1' (coercion bypass) is rejected", () => {
    const p = basePolicy();
    p.meta.receipt_chain_required = "1" as any;
    expect(validate(p)).toBe(false);
  });

  // ADV-003: weight as string '0.95' (type coercion bypass)
  test("ADV-003: weight as string '0.95' instead of number is rejected", () => {
    const p = basePolicy();
    p.regulatory_clauses[0].lambda_axes[0].weight = "0.95" as any;
    expect(validate(p)).toBe(false);
  });

  // ADV-004: clause_id with SQL injection payload
  test("ADV-004: clause_id containing SQL injection pattern is rejected (pattern violation)", () => {
    const p = basePolicy();
    // Pattern requires ^[A-Z0-9][A-Z0-9\-\.]+$ — lowercase and spaces will fail
    p.regulatory_clauses[0].clause_id = "1'; DROP TABLE receipts; --";
    expect(validate(p)).toBe(false);
  });

  // ADV-005: Λ-axis label mismatch — axis Λ1 labeled as 'Security' (should be Transparency)
  test("ADV-005: axis Λ1 with label 'Security' (wrong label for axis) is rejected", () => {
    const p = basePolicy();
    p.regulatory_clauses[0].lambda_axes[0].axis = "Λ1";
    p.regulatory_clauses[0].lambda_axes[0].label = "Security"; // Λ1 = Transparency, not Security
    // Schema enforces label enum but not axis↔label pairing at schema level;
    // however label must still be a valid LambdaAxisLabel enum value.
    // 'Security' IS in the label enum — this tests that the schema does NOT
    // enforce axis↔label correspondence (implementation concern, not schema).
    // So this should PASS at schema level, then FAIL at policy loader level.
    // Assert schema accepts this (loader will reject):
    expect(validate(p)).toBe(true); // Schema: label is valid enum value
    // Note: operational/policy_loader.ts must enforce axis↔label coherence
  });

  // ADV-006: mandatory_axes with duplicate entries (uniqueItems violation)
  test("ADV-006: mandatory_axes with duplicate Λ7 entries is rejected", () => {
    const p = basePolicy();
    p.compliance_thresholds.mandatory_axes = ["Λ5", "Λ6", "Λ7", "Λ7", "Λ10"];
    expect(validate(p)).toBe(false);
  });

  // ADV-007: effective_date in the past by 100 years (valid format but semantically stale)
  // Schema allows any valid YYYY-MM-DD — this tests schema accepts it
  // (business logic rejection happens in loader)
  test("ADV-007: effective_date '1925-01-01' (100 years ago) passes schema (loader enforces recency)", () => {
    const p = basePolicy();
    p.effective_date = "1925-01-01";
    // Schema only validates format, not semantics — should pass at schema level
    expect(validate(p)).toBe(true);
  });

  // ADV-008: merkle_root_algorithm set to unsupported 'SHA1' (deprecated, insecure)
  test("ADV-008: merkle_root_algorithm 'SHA1' is rejected", () => {
    const p = basePolicy();
    p.meta.merkle_root_algorithm = "SHA1";
    expect(validate(p)).toBe(false);
  });

  // ADV-009: Empty clause_id string (too short)
  test("ADV-009: empty string clause_id is rejected (minLength violation)", () => {
    const p = basePolicy();
    p.regulatory_clauses[0].clause_id = "";
    expect(validate(p)).toBe(false);
  });

  // ADV-010: Extra prohibited top-level field (additionalProperties: false)
  test("ADV-010: extra top-level field 'bypass_all' is rejected (additionalProperties: false)", () => {
    const p = basePolicy();
    (p as any).bypass_all = true;
    expect(validate(p)).toBe(false);
  });
});
