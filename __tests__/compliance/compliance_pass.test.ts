/**
 * compliance_pass.test.ts
 * Doctrine v6 R3 — Vertical Governance Receipts
 * 10 PASSING compliance cases: valid policy documents correctly accepted by schema and loader.
 *
 * Test framework: Jest / ts-jest
 * Run: npx jest tests/compliance/compliance_pass.test.ts
 */

import Ajv from "ajv";
import addFormats from "ajv-formats";
import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";

// ── Helpers ──────────────────────────────────────────────────────────────────

const SCHEMA_PATH = path.resolve(__dirname, "../../a11oy-knowledge.schema.json");
const POLICIES_DIR = path.resolve(__dirname, "../../policies/vertical");

function loadSchema() {
  const raw = fs.readFileSync(SCHEMA_PATH, "utf8");
  return JSON.parse(raw);
}

function loadPolicy(filename: string): unknown {
  const filepath = path.join(POLICIES_DIR, filename);
  const raw = fs.readFileSync(filepath, "utf8");
  return yaml.load(raw);
}

function buildValidator() {
  const ajv = new Ajv({ allErrors: true, strict: false });
  addFormats(ajv);
  const schema = loadSchema();
  return ajv.compile(schema);
}

// ── Test Suite ────────────────────────────────────────────────────────────────

describe("Compliance PASS — valid vertical policies accepted", () => {
  const validate = buildValidator();

  // PASS-001: Healthcare HIPAA policy validates against schema
  test("PASS-001: healthcare-hipaa.yaml validates against a11oy schema", () => {
    const policy = loadPolicy("healthcare-hipaa.yaml");
    const valid = validate(policy);
    if (!valid) console.error("Validation errors:", validate.errors);
    expect(valid).toBe(true);
  });

  // PASS-002: Financial SOX policy validates against schema
  test("PASS-002: financial-sox.yaml validates against a11oy schema", () => {
    const policy = loadPolicy("financial-sox.yaml");
    const valid = validate(policy);
    if (!valid) console.error("Validation errors:", validate.errors);
    expect(valid).toBe(true);
  });

  // PASS-003: Defense CMMC-L3 policy validates against schema
  test("PASS-003: defense-cmmc-l3.yaml validates against a11oy schema", () => {
    const policy = loadPolicy("defense-cmmc-l3.yaml");
    const valid = validate(policy);
    if (!valid) console.error("Validation errors:", validate.errors);
    expect(valid).toBe(true);
  });

  // PASS-004: Aviation DO-178C policy validates against schema
  test("PASS-004: aviation-do178c.yaml validates against a11oy schema", () => {
    const policy = loadPolicy("aviation-do178c.yaml");
    const valid = validate(policy);
    if (!valid) console.error("Validation errors:", validate.errors);
    expect(valid).toBe(true);
  });

  // PASS-005: Automotive ISO-26262 policy validates against schema
  test("PASS-005: automotive-iso26262.yaml validates against a11oy schema", () => {
    const policy = loadPolicy("automotive-iso26262.yaml");
    const valid = validate(policy);
    if (!valid) console.error("Validation errors:", validate.errors);
    expect(valid).toBe(true);
  });

  // PASS-006: Pharmaceutical 21CFR11 policy validates against schema
  test("PASS-006: pharma-21cfr11.yaml validates against a11oy schema", () => {
    const policy = loadPolicy("pharma-21cfr11.yaml");
    const valid = validate(policy);
    if (!valid) console.error("Validation errors:", validate.errors);
    expect(valid).toBe(true);
  });

  // PASS-007: Energy NERC-CIP policy validates against schema
  test("PASS-007: energy-nerc-cip.yaml validates against a11oy schema", () => {
    const policy = loadPolicy("energy-nerc-cip.yaml");
    const valid = validate(policy);
    if (!valid) console.error("Validation errors:", validate.errors);
    expect(valid).toBe(true);
  });

  // PASS-008: Maritime IMO-ISPS policy validates against schema
  test("PASS-008: maritime-imo-isps.yaml validates against a11oy schema", () => {
    const policy = loadPolicy("maritime-imo-isps.yaml");
    const valid = validate(policy);
    if (!valid) console.error("Validation errors:", validate.errors);
    expect(valid).toBe(true);
  });

  // PASS-009: LegalTech GDPR policy validates against schema
  test("PASS-009: legaltech-gdpr.yaml validates against a11oy schema", () => {
    const policy = loadPolicy("legaltech-gdpr.yaml");
    const valid = validate(policy);
    if (!valid) console.error("Validation errors:", validate.errors);
    expect(valid).toBe(true);
  });

  // PASS-010: Academic research ethics policy validates against schema
  test("PASS-010: academic-research-ethics.yaml validates against a11oy schema", () => {
    const policy = loadPolicy("academic-research-ethics.yaml");
    const valid = validate(policy);
    if (!valid) console.error("Validation errors:", validate.errors);
    expect(valid).toBe(true);
  });
});

// ── Structural Invariants ─────────────────────────────────────────────────────

describe("Compliance PASS — structural invariants across all policies", () => {
  const validate = buildValidator();
  const policyFiles = [
    "healthcare-hipaa.yaml",
    "financial-sox.yaml",
    "defense-cmmc-l3.yaml",
    "aviation-do178c.yaml",
    "automotive-iso26262.yaml",
    "pharma-21cfr11.yaml",
    "energy-nerc-cip.yaml",
    "maritime-imo-isps.yaml",
    "legaltech-gdpr.yaml",
    "academic-research-ethics.yaml",
  ];

  for (const file of policyFiles) {
    test(`INV: ${file} — regulatory_clauses count ∈ [8, 12]`, () => {
      const policy = loadPolicy(file) as any;
      const count = policy.regulatory_clauses.length;
      expect(count).toBeGreaterThanOrEqual(8);
      expect(count).toBeLessThanOrEqual(12);
    });

    test(`INV: ${file} — receipt_retention_days ≥ 365`, () => {
      const policy = loadPolicy(file) as any;
      expect(policy.compliance_thresholds.receipt_retention_days).toBeGreaterThanOrEqual(365);
    });

    test(`INV: ${file} — receipt chain algorithm is SHA3-256`, () => {
      const policy = loadPolicy(file) as any;
      expect(policy.receipt_chain.algorithm).toBe("SHA3-256");
    });

    test(`INV: ${file} — quorum format matches N-of-M`, () => {
      const policy = loadPolicy(file) as any;
      expect(policy.receipt_chain.quorum).toMatch(/^\d+-of-\d+$/);
    });
  }
});
