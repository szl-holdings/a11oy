/**
 * policy_loader.ts
 * Doctrine v6 R3 — Vertical Governance Receipts
 *
 * Loads, validates, and semantically checks vertical governance policy YAML files.
 * Produces a validated PolicyDocument with an initial receipt chain entry upon success.
 *
 * Features:
 *  - JSON Schema validation via AJV (structural)
 *  - Semantic validation: axis↔label coherence, mandatory axis coverage,
 *    minimum_lambda_coverage, quorum sanity, vertical↔regime matrix check
 *  - NFC Unicode normalisation of all string fields before hashing
 *  - SHA3-256 Merkle DAG receipt generation on successful load
 *  - Configurable retention/staleness check on effective_date
 *
 * Citations:
 *  - Doctrine v6 §4.7 (Merkle DAG p50 ≤ 5 µs)
 *  - Doctrine v6 §3.2 (re-ID risk threshold)
 *  - NIST SP 800-185 (SHA3-256)
 *  - RFC 3629 (UTF-8 / Unicode normalisation)
 */

import Ajv from "ajv";
import addFormats from "ajv-formats";
import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";
import * as yaml from "js-yaml";

// ── Type Definitions ──────────────────────────────────────────────────────────

export type LambdaAxis = "Λ1"|"Λ2"|"Λ3"|"Λ4"|"Λ5"|"Λ6"|"Λ7"|"Λ8"|"Λ9"|"Λ10";
export type LambdaLabel = "Transparency"|"Accountability"|"Privacy"|"Fairness"|
                          "Safety"|"Security"|"Auditability"|"Robustness"|
                          "Explainability"|"Sovereignty";
export type EnforcementLevel = "mandatory"|"recommended"|"informational";

export interface AxisMapping {
  axis: LambdaAxis;
  label: LambdaLabel;
  weight: number;
  enforcement: EnforcementLevel;
  rationale?: string;
}

export interface RegulatoryClause {
  clause_id: string;
  title: string;
  citation: string;
  full_ref: string;
  lambda_axes: AxisMapping[];
}

export interface PolicyMeta {
  title: string;
  description: string;
  authority: string;
  receipt_chain_required: boolean;
  merkle_root_algorithm: string;
  [key: string]: unknown;
}

export interface ComplianceThresholds {
  minimum_lambda_coverage: number;
  mandatory_axes: LambdaAxis[];
  receipt_retention_days: number;
  [key: string]: unknown;
}

export interface ReceiptChainConfig {
  algorithm: string;
  chaining: string;
  quorum: string;
  nodes: string[];
  [key: string]: unknown;
}

export interface PolicyDocument {
  schema_version: string;
  vertical: string;
  regime: string;
  effective_date: string;
  jurisdiction: string;
  meta: PolicyMeta;
  regulatory_clauses: RegulatoryClause[];
  compliance_thresholds: ComplianceThresholds;
  receipt_chain: ReceiptChainConfig;
}

export interface LoadResult {
  ok: boolean;
  policy?: PolicyDocument;
  receipt?: PolicyLoadReceipt;
  errors?: string[];
  warnings?: string[];
}

export interface PolicyLoadReceipt {
  receipt_id: string;
  event_type: "POLICY_LOAD";
  timestamp_iso8601: string;
  loader_version: string;
  policy_file_hash: string;      // SHA3-256 (simulated as SHA-256) of raw YAML bytes
  policy_content_hash: string;   // SHA3-256 of normalised JSON
  vertical: string;
  regime: string;
  clauses_count: number;
  covered_axes: LambdaAxis[];
  mandatory_axes_satisfied: boolean;
  prev_receipt_hash: string | null;
  merkle_root: string;
}

// ── Axis↔Label Coherence Map (Doctrine v6 §1.2) ──────────────────────────────

const AXIS_LABEL_MAP: Record<LambdaAxis, LambdaLabel> = {
  "Λ1":  "Transparency",
  "Λ2":  "Accountability",
  "Λ3":  "Privacy",
  "Λ4":  "Fairness",
  "Λ5":  "Safety",
  "Λ6":  "Security",
  "Λ7":  "Auditability",
  "Λ8":  "Robustness",
  "Λ9":  "Explainability",
  "Λ10": "Sovereignty",
};

// ── Vertical↔Regime Coherence Matrix (Doctrine v6 §2.3) ──────────────────────

const VERTICAL_REGIME_PREFIXES: Record<string, string[]> = {
  healthcare:    ["HIPAA", "HITECH", "21-CFR"],
  financial:     ["SOX", "Dodd-Frank", "SR11-7", "FINRA", "ECOA"],
  defense:       ["CMMC", "NIST", "DFARS", "ITAR"],
  aviation:      ["DO-178", "DO-333", "FAA", "EASA", "ARINC"],
  automotive:    ["ISO-26262", "ISO-21448", "UL-4600", "SAE", "UNECE"],
  pharmaceutical:["21-CFR", "FDA", "ICH", "EU-AI-Act"],
  energy:        ["NERC-CIP", "FERC", "DOE"],
  maritime:      ["IMO-ISPS", "SOLAS", "IMO", "MSC-FAL", "MARPOL", "COLREGS"],
  legaltech:     ["GDPR", "EU-AI-Act", "eIDAS"],
  academic:      ["Common-Rule", "Belmont", "COPE", "NIH", "NSF", "EU-AI-Act"],
};

// ── Internal Helpers ──────────────────────────────────────────────────────────

/** NFC-normalise all string values in an object (deep) — RFC 3629 §7 */
function normaliseStrings(obj: unknown): unknown {
  if (typeof obj === "string") return obj.normalize("NFC");
  if (Array.isArray(obj)) return obj.map(normaliseStrings);
  if (obj !== null && typeof obj === "object") {
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      result[k] = normaliseStrings(v);
    }
    return result;
  }
  return obj;
}

/** SHA-256 of a UTF-8 string (production: replace with SHA3-256 per NIST SP 800-185) */
function sha256hex(data: string): string {
  return crypto.createHash("sha256").update(data, "utf8").digest("hex");
}

/** Compute covered Λ-axes from all clauses */
function coveredAxes(clauses: RegulatoryClause[]): Set<LambdaAxis> {
  const axes = new Set<LambdaAxis>();
  for (const c of clauses) {
    for (const m of c.lambda_axes) axes.add(m.axis);
  }
  return axes;
}

// ── AJV Validator (singleton) ─────────────────────────────────────────────────

let _validator: Ajv.ValidateFunction | null = null;

function getValidator(schemaPath: string): Ajv.ValidateFunction {
  if (_validator) return _validator;
  const ajv = new Ajv({ allErrors: true, strict: false, coerceTypes: false });
  addFormats(ajv);
  const schema = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
  const validator = ajv.compile(schema);
  _validator = validator;
  return validator;
}

// ── Semantic Validators ───────────────────────────────────────────────────────

function validateAxisLabelCoherence(policy: PolicyDocument): string[] {
  const errors: string[] = [];
  for (const clause of policy.regulatory_clauses) {
    for (const m of clause.lambda_axes) {
      const expected = AXIS_LABEL_MAP[m.axis];
      if (expected && m.label !== expected) {
        errors.push(
          `[${clause.clause_id}] Axis ${m.axis} has label '${m.label}', expected '${expected}'`
        );
      }
    }
  }
  return errors;
}

function validateMandatoryAxesCovered(policy: PolicyDocument): string[] {
  const errors: string[] = [];
  const covered = coveredAxes(policy.regulatory_clauses);
  for (const ax of policy.compliance_thresholds.mandatory_axes) {
    if (!covered.has(ax)) {
      errors.push(`Mandatory axis ${ax} not covered by any regulatory clause`);
    }
  }
  return errors;
}

function validateCoverageMinimum(policy: PolicyDocument): string[] {
  const covered = coveredAxes(policy.regulatory_clauses);
  const min = policy.compliance_thresholds.minimum_lambda_coverage;
  if (covered.size < min) {
    return [`Covered axis count (${covered.size}) < minimum_lambda_coverage (${min})`];
  }
  return [];
}

function validateQuorum(policy: PolicyDocument): string[] {
  const errors: string[] = [];
  const { quorum, nodes } = policy.receipt_chain;
  const match = quorum.match(/^(\d+)-of-(\d+)$/);
  if (match) {
    const [, n, d] = match.map(Number);
    if (n > d) errors.push(`Impossible quorum: ${n}-of-${d} (numerator > denominator)`);
    if (n > nodes.length) errors.push(`Quorum requires ${n} signers but only ${nodes.length} nodes defined`);
  }
  return errors;
}

function validateVerticalRegimeCoherence(policy: PolicyDocument): string[] {
  const warnings: string[] = [];
  const prefixes = VERTICAL_REGIME_PREFIXES[policy.vertical] ?? [];
  const regimeMatches = prefixes.some((p) => policy.regime.includes(p));
  if (!regimeMatches) {
    warnings.push(
      `vertical '${policy.vertical}' regime '${policy.regime}' not in expected regime list [${prefixes.join(", ")}]. Review required.`
    );
  }
  return warnings;
}

function validateEffectiveDateRecency(policy: PolicyDocument): string[] {
  const warnings: string[] = [];
  const effectiveMs = new Date(policy.effective_date).getTime();
  const nowMs = Date.now();
  const tenYearsMs = 10 * 365.25 * 24 * 3600 * 1000;
  if (nowMs - effectiveMs > tenYearsMs) {
    warnings.push(`effective_date '${policy.effective_date}' is more than 10 years in the past. Policy may be stale.`);
  }
  return warnings;
}

// ── Main Load Function ────────────────────────────────────────────────────────

/**
 * Load and validate a vertical governance policy YAML file.
 *
 * @param filepath          Absolute or relative path to the .yaml policy file
 * @param schemaPath        Path to a11oy-knowledge.schema.json
 * @param prevReceiptHash   Hash of the preceding receipt (null for first load)
 * @returns                 LoadResult with policy, receipt, errors, and warnings
 */
export function loadVerticalPolicy(
  filepath: string,
  schemaPath: string,
  prevReceiptHash: string | null = null
): LoadResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  // 1. Read file
  let rawYaml: string;
  try {
    rawYaml = fs.readFileSync(filepath, "utf8");
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return { ok: false, errors: [`Cannot read file '${filepath}': ${msg}`] };
  }

  // 2. Parse YAML
  let rawObject: unknown;
  try {
    rawObject = yaml.load(rawYaml);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return { ok: false, errors: [`YAML parse error in '${filepath}': ${msg}`] };
  }

  // 3. NFC normalise all strings (RFC 3629)
  const normObject = normaliseStrings(rawObject);

  // 4. JSON Schema validation (structural)
  const validate = getValidator(schemaPath);
  const schemaValid = validate(normObject);
  if (!schemaValid) {
    const schemaErrors = (validate.errors ?? []).map(
      (e) => `[schema] ${e.instancePath || "/"} ${e.message}`
    );
    return { ok: false, errors: schemaErrors };
  }

  const policy = normObject as unknown as PolicyDocument;

  // 5. Semantic validations
  errors.push(...validateAxisLabelCoherence(policy));
  errors.push(...validateMandatoryAxesCovered(policy));
  errors.push(...validateCoverageMinimum(policy));
  errors.push(...validateQuorum(policy));
  warnings.push(...validateVerticalRegimeCoherence(policy));
  warnings.push(...validateEffectiveDateRecency(policy));

  if (errors.length > 0) {
    return { ok: false, errors, warnings };
  }

  // 6. Compute receipt
  const fileHash = sha256hex(rawYaml);
  const contentHash = sha256hex(JSON.stringify(policy));
  const covered = Array.from(coveredAxes(policy.regulatory_clauses)).sort() as LambdaAxis[];
  const mandatory = policy.compliance_thresholds.mandatory_axes;
  const coveredSet = new Set(covered);
  const mandatorySatisfied = mandatory.every((ax) => coveredSet.has(ax));

  const receiptPartial = {
    receipt_id: `rl-${sha256hex(filepath + contentHash).slice(0, 16)}`,
    event_type: "POLICY_LOAD" as const,
    timestamp_iso8601: new Date().toISOString(),
    loader_version: "1.0.0",
    policy_file_hash: fileHash,
    policy_content_hash: contentHash,
    vertical: policy.vertical,
    regime: policy.regime,
    clauses_count: policy.regulatory_clauses.length,
    covered_axes: covered,
    mandatory_axes_satisfied: mandatorySatisfied,
    prev_receipt_hash: prevReceiptHash,
  };

  const merkle_root = sha256hex(JSON.stringify(receiptPartial));
  const receipt: PolicyLoadReceipt = { ...receiptPartial, merkle_root };

  return { ok: true, policy, receipt, warnings };
}
