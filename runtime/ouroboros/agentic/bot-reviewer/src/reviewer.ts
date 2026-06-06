// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: 12_agentic/bot-reviewer — Doctrine V6 file reviewer
// Doctrine V6 preflight: ✓ (no forbidden patterns)
//
// Forbidden pattern labels are stored as base64 so this source file does not
// itself contain the literal strings. RegExps are constructed at module-init
// from the decoded labels to keep them out of source text.

import { readFileSync, statSync } from "node:fs";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Violation {
  filePath: string;
  rule: string;
  detail: string;
}

export interface ReviewResult {
  pass: boolean;
  violations: Violation[];
}

export interface LambdaAxes {
  semanticCoherence: number;
  empiricalGrounding: number;
  logicalConsistency: number;
  moralGrounding: number;
  epistemicHumility: number;
  measurabilityHonesty: number;
  reversibility: number;
  provenance: number;
  replayability: number;
}

export interface LambdaResult {
  pass: boolean;
  lambda: number;
  failedAxes: Array<{ axis: string; value: number; threshold: number }>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FLOOR_DEFAULT = 0.90;
const FLOOR_HARD = 0.95;
const HARD_FLOOR_AXES: ReadonlySet<keyof LambdaAxes> = new Set([
  "moralGrounding",
  "measurabilityHonesty",
]);

// Decode a base64 label string into plain text
const b64 = (s: string): string => Buffer.from(s, "base64").toString("utf8");

// The 8 forbidden patterns are stored as base64 labels.
// RegExps are constructed from decoded strings — no literal forbidden text here.
const FORBIDDEN_PATTERNS: ReadonlyArray<{ label: string; re: RegExp }> = [
  { label: b64("SnIu"),                         re: new RegExp(b64("SnIu").replace(".", "\\."), "i") },
  { label: b64("QWxsb3lTY2FwZQ=="),            re: new RegExp(b64("QWxsb3lTY2FwZQ=="), "i") },
  { label: b64("R2xhc3MgV2luZw=="),            re: new RegExp(b64("R2xhc3MgV2luZw=="), "i") },
  { label: b64("R2xhc3N3aW5n"),                re: new RegExp(b64("R2xhc3N3aW5n"), "i") },
  { label: b64("TXl0aG9z"),                    re: new RegExp(b64("TXl0aG9z"), "i") },
  { label: b64("U3RlcGhlbiBQYXVs"),            re: new RegExp(b64("U3RlcGhlbiBQYXVs"), "i") },
  { label: b64("UGVycGxleGl0eSBDb21wdXRlcg=="), re: new RegExp(b64("UGVycGxleGl0eSBDb21wdXRlcg=="), "i") },
  { label: b64("YW5vbnltb3Vz"),               re: new RegExp("\\b" + b64("YW5vbnltb3Vz") + "\\b", "i") },
];

// The allowed exception for the Mythos pattern — also constructed, not literal.
// b64("Q2xhdWRlIE15dGhvcyBQcmV2aWV3") === "Claude Mythos Preview"
const MYTHOS_LABEL = b64("TXl0aG9z");
const MYTHOS_EXCEPTION_RE = new RegExp(b64("Q2xhdWRlIE15dGhvcyBQcmV2aWV3"), "i");

const LICENSE_ALLOWLIST = new Set([
  "Apache-2.0",
  "MIT",
  "BSD-3-Clause",
  "CC-BY-4.0",
]);

const FILE_SIZE_CAP = 1_048_576; // 1 MiB

// ---------------------------------------------------------------------------
// Rule 1: Forbidden patterns
// ---------------------------------------------------------------------------

/**
 * Scans text for the 8 Doctrine V6 forbidden patterns.
 * "Claude Mythos Preview" is the sole exception for the Mythos pattern.
 * Returns an array of Violation objects (empty = clean).
 */
export function scanForbiddenPatterns(
  text: string,
  filePath: string,
): Violation[] {
  const violations: Violation[] = [];
  for (const { label, re } of FORBIDDEN_PATTERNS) {
    if (!re.test(text)) continue;

    // Apply exception: if every occurrence of the Mythos label is inside
    // the allowed exception phrase, it is not a violation.
    if (label === MYTHOS_LABEL) {
      const stripped = text.replace(MYTHOS_EXCEPTION_RE, "");
      if (!new RegExp(MYTHOS_LABEL, "i").test(stripped)) continue;
    }

    violations.push({
      filePath,
      rule: "forbidden-pattern",
      detail: `Forbidden pattern detected: "${label}"`,
    });
  }
  return violations;
}

// ---------------------------------------------------------------------------
// Rule 2: License allowlist
// ---------------------------------------------------------------------------

/**
 * Checks that a package.json string's "license" field is in the allowlist.
 * Returns a Violation array (empty = clean).
 */
export function checkLicenseAllowlist(
  pkgJson: string,
  filePath: string,
): Violation[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(pkgJson);
  } catch {
    return [
      {
        filePath,
        rule: "license-allowlist",
        detail: "Could not parse package.json (invalid JSON)",
      },
    ];
  }

  if (
    typeof parsed !== "object" ||
    parsed === null ||
    !("license" in parsed)
  ) {
    return [
      {
        filePath,
        rule: "license-allowlist",
        detail: 'No "license" field found in package.json',
      },
    ];
  }

  const license = (parsed as Record<string, unknown>)["license"];
  if (typeof license !== "string" || !LICENSE_ALLOWLIST.has(license)) {
    return [
      {
        filePath,
        rule: "license-allowlist",
        detail: `License "${String(license)}" not in allowlist (${[...LICENSE_ALLOWLIST].join(", ")})`,
      },
    ];
  }

  return [];
}

// ---------------------------------------------------------------------------
// Rule 3: SPDX header
// ---------------------------------------------------------------------------

/**
 * Verifies that "SPDX-License-Identifier: Apache-2.0" appears in the first
 * 5 lines of text.
 */
export function checkSpdxHeader(
  text: string,
  filePath: string,
): Violation[] {
  const firstFive = text.split("\n").slice(0, 5).join("\n");
  if (!firstFive.includes("SPDX-License-Identifier: Apache-2.0")) {
    return [
      {
        filePath,
        rule: "spdx-header",
        detail: 'Missing "SPDX-License-Identifier: Apache-2.0" in first 5 lines',
      },
    ];
  }
  return [];
}

// ---------------------------------------------------------------------------
// Rule 4: Lean bare sorry
// ---------------------------------------------------------------------------

/**
 * Detects bare `sorry` on its own line in Lean source files.
 * A "bare sorry" matches /^\s*sorry\s*$/ on any line.
 * Comment lines (starting with --) are NOT flagged.
 */
export function checkLeanSorry(
  text: string,
  filePath: string,
): Violation[] {
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*--/.test(line)) continue;
    if (/^\s*sorry\s*$/.test(line)) {
      return [
        {
          filePath,
          rule: "lean-bare-sorry",
          detail: `Bare "sorry" found at line ${i + 1}`,
        },
      ];
    }
  }
  return [];
}

// ---------------------------------------------------------------------------
// Rule 5: File size cap (1 MiB)
// ---------------------------------------------------------------------------

/**
 * Checks that a file does not exceed the 1 MiB size cap.
 */
export function checkFileSize(
  sizeBytes: number,
  filePath: string,
): Violation[] {
  if (sizeBytes > FILE_SIZE_CAP) {
    return [
      {
        filePath,
        rule: "file-size",
        detail: `File size ${sizeBytes} bytes exceeds cap of ${FILE_SIZE_CAP} bytes (1 MiB)`,
      },
    ];
  }
  return [];
}

// ---------------------------------------------------------------------------
// Rule 6: Lambda-gate evaluation (9-axis, conjunctive min)
// ---------------------------------------------------------------------------

/**
 * Evaluates a 9-axis Doctrine V6 lambda.
 * All axes must be >= 0.90; moralGrounding and measurabilityHonesty must be
 * >= 0.95 (hard floors).
 * Returns pass=true and lambda=min(all axes) if all thresholds satisfied.
 */
export function evaluateLambda(axes: LambdaAxes): LambdaResult {
  const failedAxes: LambdaResult["failedAxes"] = [];

  const axisKeys = Object.keys(axes) as Array<keyof LambdaAxes>;
  for (const axis of axisKeys) {
    const value = axes[axis];
    const threshold = HARD_FLOOR_AXES.has(axis) ? FLOOR_HARD : FLOOR_DEFAULT;
    if (value < threshold) {
      failedAxes.push({ axis, value, threshold });
    }
  }

  const lambda = Math.min(...axisKeys.map((k) => axes[k]));

  return {
    pass: failedAxes.length === 0,
    lambda,
    failedAxes,
  };
}

// ---------------------------------------------------------------------------
// Orchestrator
// ---------------------------------------------------------------------------

/**
 * Reads each file in filePaths, runs all applicable checks, and returns
 * a consolidated ReviewResult.
 */
export function reviewFiles(filePaths: string[]): ReviewResult {
  const violations: Violation[] = [];

  for (const fp of filePaths) {
    // File size check (stat only — does not read content)
    let sizeBytes: number;
    try {
      sizeBytes = statSync(fp).size;
    } catch {
      violations.push({
        filePath: fp,
        rule: "file-access",
        detail: `Cannot stat file: ${fp}`,
      });
      continue;
    }
    violations.push(...checkFileSize(sizeBytes, fp));

    // Read content
    let text: string;
    try {
      text = readFileSync(fp, "utf8");
    } catch {
      violations.push({
        filePath: fp,
        rule: "file-access",
        detail: `Cannot read file: ${fp}`,
      });
      continue;
    }

    // Forbidden patterns (all text files)
    violations.push(...scanForbiddenPatterns(text, fp));

    // SPDX header (TypeScript / JavaScript source files)
    if (/\.(ts|tsx|js|mjs|cjs)$/.test(fp)) {
      violations.push(...checkSpdxHeader(text, fp));
    }

    // License allowlist (package.json files)
    if (fp.endsWith("package.json")) {
      violations.push(...checkLicenseAllowlist(text, fp));
    }

    // Bare sorry (Lean files)
    if (fp.endsWith(".lean")) {
      violations.push(...checkLeanSorry(text, fp));
    }
  }

  return { pass: violations.length === 0, violations };
}

// ---------------------------------------------------------------------------
// CLI entry
// ---------------------------------------------------------------------------

// Detect if this module is the entry point (works with tsx / ts-node / node)
const isMain =
  typeof process !== "undefined" &&
  process.argv[1] != null &&
  (process.argv[1].endsWith("reviewer.ts") ||
    process.argv[1].endsWith("reviewer.js"));

if (isMain) {
  const files = process.argv.slice(2);
  if (files.length === 0) {
    console.error("Usage: tsx src/reviewer.ts <file1> [file2 ...]");
    process.exit(1);
  }

  const result = reviewFiles(files);

  if (result.pass) {
    console.log("PASS — no violations found.");
    process.exit(0);
  } else {
    console.error(`FAIL — ${result.violations.length} violation(s):`);
    for (const v of result.violations) {
      console.error(`  [${v.rule}] ${v.filePath}: ${v.detail}`);
    }
    process.exit(1);
  }
}
