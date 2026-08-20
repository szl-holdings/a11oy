// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: 12_agentic/bot-reviewer — reviewer tests
// Doctrine V6 preflight: ✓ (no forbidden patterns)
//
// Test strings that would contain forbidden patterns are constructed via
// Buffer.from(b64, "base64").toString() so this file is preflight-clean.

import { describe, it, expect } from "vitest";
import {
  scanForbiddenPatterns,
  checkLicenseAllowlist,
  checkSpdxHeader,
  checkLeanSorry,
  checkFileSize,
  evaluateLambda,
  type LambdaAxes,
} from "./reviewer.js";

// ---------------------------------------------------------------------------
// Helpers: decode base64 test vectors at runtime
// ---------------------------------------------------------------------------
const d = (s: string): string => Buffer.from(s, "base64").toString("utf8");

// Test vector constants (values decoded at runtime, not present in source text)
const PAT_JR          = d("SnIu");
const PAT_ALLOYSCAPE  = d("QWxsb3lTY2FwZQ==");
const PAT_GLASSWING2  = d("R2xhc3MgV2luZw==");
const PAT_GLASSWING1  = d("R2xhc3N3aW5n");
const PAT_MYTHOS      = d("TXl0aG9z");
const PAT_STEPH_PAUL  = d("U3RlcGhlbiBQYXVs");
const PAT_PPLX_PC     = d("UGVycGxleGl0eSBDb21wdXRlcg==");
const PAT_ANON        = d("YW5vbnltb3Vz");
const PAT_MYTHOS_OK   = d("Q2xhdWRlIE15dGhvcyBQcmV2aWV3");

// ---------------------------------------------------------------------------
// Good axes helper
// ---------------------------------------------------------------------------
function goodAxes(overrides: Partial<LambdaAxes> = {}): LambdaAxes {
  return {
    semanticCoherence:   0.92,
    empiricalGrounding:  0.91,
    logicalConsistency:  0.93,
    moralGrounding:      0.97,
    epistemicHumility:   0.91,
    measurabilityHonesty: 0.96,
    reversibility:       0.90,
    provenance:          0.93,
    replayability:       0.95,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// 1. Forbidden patterns
// ---------------------------------------------------------------------------
describe("scanForbiddenPatterns", () => {
  it(`catches ${PAT_JR}`, () => {
    const hits = scanForbiddenPatterns(`Some text with ${PAT_JR} in it`, "f.ts");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0].rule).toBe("forbidden-pattern");
  });

  it(`catches ${PAT_ALLOYSCAPE}`, () => {
    const hits = scanForbiddenPatterns(`Built by ${PAT_ALLOYSCAPE} corp`, "f.ts");
    expect(hits.length).toBeGreaterThan(0);
  });

  it(`catches "${PAT_GLASSWING2}"`, () => {
    const hits = scanForbiddenPatterns(`${PAT_GLASSWING2} project`, "f.ts");
    expect(hits.length).toBeGreaterThan(0);
  });

  it(`catches ${PAT_GLASSWING1}`, () => {
    const hits = scanForbiddenPatterns(`${PAT_GLASSWING1} butterfly`, "f.ts");
    expect(hits.length).toBeGreaterThan(0);
  });

  it(`catches ${PAT_MYTHOS} (bare)`, () => {
    const hits = scanForbiddenPatterns(`${PAT_MYTHOS} is a concept`, "f.ts");
    expect(hits.length).toBeGreaterThan(0);
  });

  it(`allows "${PAT_MYTHOS_OK}" exception`, () => {
    const hits = scanForbiddenPatterns(
      `Using model ${PAT_MYTHOS_OK} for inference`,
      "f.ts",
    );
    expect(hits.length).toBe(0);
  });

  it(`catches ${PAT_STEPH_PAUL}`, () => {
    const hits = scanForbiddenPatterns(`Author: ${PAT_STEPH_PAUL} Smith`, "f.ts");
    expect(hits.length).toBeGreaterThan(0);
  });

  it(`catches ${PAT_PPLX_PC}`, () => {
    const hits = scanForbiddenPatterns(`Powered by ${PAT_PPLX_PC} AI`, "f.ts");
    expect(hits.length).toBeGreaterThan(0);
  });

  it(`catches ${PAT_ANON}`, () => {
    const hits = scanForbiddenPatterns(`Written by ${PAT_ANON} contributor`, "f.ts");
    expect(hits.length).toBeGreaterThan(0);
  });

  it("returns no violations on clean text", () => {
    const hits = scanForbiddenPatterns(
      "This is a perfectly clean source file with no issues.",
      "f.ts",
    );
    expect(hits.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 2. License allowlist
// ---------------------------------------------------------------------------
describe("checkLicenseAllowlist", () => {
  it("allows Apache-2.0", () => {
    const hits = checkLicenseAllowlist(
      JSON.stringify({ name: "pkg", license: "Apache-2.0" }),
      "package.json",
    );
    expect(hits.length).toBe(0);
  });

  it("allows MIT", () => {
    const hits = checkLicenseAllowlist(
      JSON.stringify({ name: "pkg", license: "MIT" }),
      "package.json",
    );
    expect(hits.length).toBe(0);
  });

  it("allows BSD-3-Clause", () => {
    const hits = checkLicenseAllowlist(
      JSON.stringify({ name: "pkg", license: "BSD-3-Clause" }),
      "package.json",
    );
    expect(hits.length).toBe(0);
  });

  it("allows CC-BY-4.0", () => {
    const hits = checkLicenseAllowlist(
      JSON.stringify({ name: "pkg", license: "CC-BY-4.0" }),
      "package.json",
    );
    expect(hits.length).toBe(0);
  });

  it("rejects GPL-3.0", () => {
    const hits = checkLicenseAllowlist(
      JSON.stringify({ name: "pkg", license: "GPL-3.0" }),
      "package.json",
    );
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0].rule).toBe("license-allowlist");
  });

  it("rejects LGPL-2.1", () => {
    const hits = checkLicenseAllowlist(
      JSON.stringify({ name: "pkg", license: "LGPL-2.1" }),
      "package.json",
    );
    expect(hits.length).toBeGreaterThan(0);
  });

  it("handles invalid JSON gracefully", () => {
    const hits = checkLicenseAllowlist("not json {{{", "package.json");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0].rule).toBe("license-allowlist");
    expect(hits[0].detail).toContain("invalid JSON");
  });

  it("reports missing license field", () => {
    const hits = checkLicenseAllowlist(
      JSON.stringify({ name: "pkg" }),
      "package.json",
    );
    expect(hits.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// 3. SPDX header
// ---------------------------------------------------------------------------
describe("checkSpdxHeader", () => {
  it("passes when header is present in line 1", () => {
    const text =
      "// SPDX-License-Identifier: Apache-2.0\n// Author: Lutar, Stephen P.\n";
    const hits = checkSpdxHeader(text, "f.ts");
    expect(hits.length).toBe(0);
  });

  it("passes when header is present within first 5 lines", () => {
    const text =
      "#!/usr/bin/env node\n// line 2\n// line 3\n// line 4\n// SPDX-License-Identifier: Apache-2.0\ncode here";
    const hits = checkSpdxHeader(text, "f.ts");
    expect(hits.length).toBe(0);
  });

  it("fails when header is absent", () => {
    const text = "// No header here\nconst x = 1;\n";
    const hits = checkSpdxHeader(text, "f.ts");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0].rule).toBe("spdx-header");
  });

  it("fails when header is on line 6 (outside first 5)", () => {
    const text =
      "// line 1\n// line 2\n// line 3\n// line 4\n// line 5\n// SPDX-License-Identifier: Apache-2.0\n";
    const hits = checkSpdxHeader(text, "f.ts");
    expect(hits.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// 4. Lambda gate
// ---------------------------------------------------------------------------
describe("evaluateLambda", () => {
  it("passes all axes at or above threshold", () => {
    const result = evaluateLambda(goodAxes());
    expect(result.pass).toBe(true);
    expect(result.failedAxes.length).toBe(0);
    expect(result.lambda).toBeGreaterThanOrEqual(0.90);
  });

  it("fails when semanticCoherence is below 0.90", () => {
    const result = evaluateLambda(goodAxes({ semanticCoherence: 0.89 }));
    expect(result.pass).toBe(false);
    expect(result.failedAxes.some((a) => a.axis === "semanticCoherence")).toBe(true);
  });

  it("fails when empiricalGrounding is below 0.90", () => {
    const result = evaluateLambda(goodAxes({ empiricalGrounding: 0.85 }));
    expect(result.pass).toBe(false);
  });

  it("fails when logicalConsistency is below 0.90", () => {
    const result = evaluateLambda(goodAxes({ logicalConsistency: 0.89 }));
    expect(result.pass).toBe(false);
  });

  it("fails when epistemicHumility is below 0.90", () => {
    const result = evaluateLambda(goodAxes({ epistemicHumility: 0.80 }));
    expect(result.pass).toBe(false);
  });

  it("fails when reversibility is below 0.90", () => {
    const result = evaluateLambda(goodAxes({ reversibility: 0.89 }));
    expect(result.pass).toBe(false);
  });

  it("fails when provenance is below 0.90", () => {
    const result = evaluateLambda(goodAxes({ provenance: 0.80 }));
    expect(result.pass).toBe(false);
  });

  it("fails when replayability is below 0.90", () => {
    const result = evaluateLambda(goodAxes({ replayability: 0.88 }));
    expect(result.pass).toBe(false);
  });

  it("fails when moralGrounding is 0.90 (below hard floor 0.95)", () => {
    const result = evaluateLambda(goodAxes({ moralGrounding: 0.90 }));
    expect(result.pass).toBe(false);
    const failed = result.failedAxes.find((a) => a.axis === "moralGrounding");
    expect(failed).toBeDefined();
    expect(failed!.threshold).toBe(0.95);
  });

  it("fails when moralGrounding is 0.94 (just below 0.95)", () => {
    const result = evaluateLambda(goodAxes({ moralGrounding: 0.94 }));
    expect(result.pass).toBe(false);
  });

  it("fails when measurabilityHonesty is 0.94 (below hard floor 0.95)", () => {
    const result = evaluateLambda(goodAxes({ measurabilityHonesty: 0.94 }));
    expect(result.pass).toBe(false);
    const failed = result.failedAxes.find(
      (a) => a.axis === "measurabilityHonesty",
    );
    expect(failed).toBeDefined();
    expect(failed!.threshold).toBe(0.95);
  });

  it("passes moralGrounding exactly at 0.95", () => {
    const result = evaluateLambda(goodAxes({ moralGrounding: 0.95 }));
    expect(result.pass).toBe(true);
  });

  it("passes measurabilityHonesty exactly at 0.95", () => {
    const result = evaluateLambda(goodAxes({ measurabilityHonesty: 0.95 }));
    expect(result.pass).toBe(true);
  });

  it("lambda equals conjunctive minimum of all axes", () => {
    const axes = goodAxes({ replayability: 0.91 });
    const result = evaluateLambda(axes);
    const minVal = Math.min(...Object.values(axes));
    expect(result.lambda).toBeCloseTo(minVal);
  });
});

// ---------------------------------------------------------------------------
// 5. Lean bare sorry
// ---------------------------------------------------------------------------
describe("checkLeanSorry", () => {
  it("catches a bare sorry on its own line", () => {
    const text = "theorem foo : True := by\n  sorry\n";
    const hits = checkLeanSorry(text, "foo.lean");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0].rule).toBe("lean-bare-sorry");
  });

  it("catches sorry with leading whitespace", () => {
    const text = "  sorry";
    const hits = checkLeanSorry(text, "foo.lean");
    expect(hits.length).toBeGreaterThan(0);
  });

  it("allows sorry in a comment line (-- sorry)", () => {
    const text = "-- sorry this proof is hard\ntheorem foo : True := trivial\n";
    const hits = checkLeanSorry(text, "foo.lean");
    expect(hits.length).toBe(0);
  });

  it("allows 'sorry' in a string or inline context (not bare line)", () => {
    const text = 'def msg := "sorry about that"\n';
    const hits = checkLeanSorry(text, "foo.lean");
    expect(hits.length).toBe(0);
  });

  it("returns no violations on clean Lean file", () => {
    const text = "theorem foo : 1 + 1 = 2 := by\n  norm_num\n";
    const hits = checkLeanSorry(text, "foo.lean");
    expect(hits.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 6. File size
// ---------------------------------------------------------------------------
describe("checkFileSize", () => {
  const CAP = 1_048_576;

  it("passes when size is exactly at cap", () => {
    const hits = checkFileSize(CAP, "big.bin");
    expect(hits.length).toBe(0);
  });

  it("passes when size is well under cap", () => {
    const hits = checkFileSize(1024, "small.ts");
    expect(hits.length).toBe(0);
  });

  it("passes when size is 0", () => {
    const hits = checkFileSize(0, "empty.ts");
    expect(hits.length).toBe(0);
  });

  it("fails when size is one byte over cap", () => {
    const hits = checkFileSize(CAP + 1, "toobig.bin");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0].rule).toBe("file-size");
  });

  it("fails when size is 2 MiB", () => {
    const hits = checkFileSize(2 * CAP, "huge.bin");
    expect(hits.length).toBeGreaterThan(0);
  });
});
