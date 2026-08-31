// SPDX-License-Identifier: Apache-2.0
// © 2026 SZL Holdings · Author: Lutar, Stephen P. <stephen@szlholdings.com>
// Tests for github-poster.ts — covers CVE-class sanitization (CodeQL js/incomplete-sanitization).

import { describe, it, expect } from "vitest";
import { buildReviewBody } from "./github-poster";
import type { ReviewResult } from "./reviewer";

const passingResult: ReviewResult = {
  pass: true,
  violations: [],
};

describe("buildReviewBody — markdown injection safety (CodeQL js/incomplete-sanitization)", () => {
  it("escapes backslashes in violation details so they don't form unintended escape pairs", () => {
    const result: ReviewResult = {
      ...passingResult,
      pass: false,
      violations: [
        {
          rule: "test",
          filePath: "src/foo.ts",
          detail: "input contains a\\b literal", // raw backslash
        },
      ],
    };
    const body = buildReviewBody(result);
    // The raw "a\b" must appear as "a\\b" in the rendered cell (backslash escaped)
    expect(body).toContain("a\\\\b literal");
    // It must NOT appear as the unescaped raw "a\b"
    // (would be: "a\\b" in JS string literal, single backslash in text)
    const lines = body.split("\n");
    const tableRow = lines.find((l) => l.includes("test"));
    expect(tableRow).toBeDefined();
    // Single-backslash variant should not be in the rendered row (only the doubled one)
    expect(tableRow!).toMatch(/a\\\\b/);
  });

  it("escapes pipe characters in cells without double-escaping", () => {
    const result: ReviewResult = {
      ...passingResult,
      pass: false,
      violations: [
        {
          rule: "test",
          filePath: "src/foo.ts",
          detail: "value is a|b|c",
        },
      ],
    };
    const body = buildReviewBody(result);
    expect(body).toContain("a\\|b\\|c");
  });

  it("escapes backslash BEFORE pipe so combined input is safe", () => {
    // This is the CodeQL-flagged case: input "a\|b" should not become "a\\|b" (which would
    // unescape the pipe). It must become "a\\\\\\|b" — backslash doubled, then pipe escaped.
    const result: ReviewResult = {
      ...passingResult,
      pass: false,
      violations: [
        {
          rule: "test",
          filePath: "src/foo.ts",
          detail: "a\\|b", // backslash followed by pipe
        },
      ],
    };
    const body = buildReviewBody(result);
    // Expected: backslash → \\, then pipe → \|. So "a\|b" → "a\\\|b" (rendered)
    expect(body).toContain("a\\\\\\|b");
  });

  it("escapes backticks so they don't break the inline code spans in the table", () => {
    const result: ReviewResult = {
      ...passingResult,
      pass: false,
      violations: [
        {
          rule: "test`escape",
          filePath: "src/foo.ts",
          detail: "uses `eval` here",
        },
      ],
    };
    const body = buildReviewBody(result);
    expect(body).toContain("uses \\`eval\\` here");
  });

  it("collapses newlines so multi-line violations don't break the table row", () => {
    const result: ReviewResult = {
      ...passingResult,
      pass: false,
      violations: [
        {
          rule: "test",
          filePath: "src/foo.ts",
          detail: "line one\nline two\r\nline three",
        },
      ],
    };
    const body = buildReviewBody(result);
    // Find the table row for "test" — it must be a single line
    const lines = body.split("\n");
    const tableRow = lines.find((l) => l.includes("test") && l.includes("line one"));
    expect(tableRow).toBeDefined();
    expect(tableRow!).toContain("line one line two line three");
    // No literal \n inside the row
    expect(tableRow!).not.toContain("\n");
  });

  it("emits 'all checks passed' when pass=true with no violations", () => {
    const body = buildReviewBody(passingResult);
    expect(body).toContain("All Doctrine V6 checks passed");
    expect(body).not.toContain("| # | Rule");
  });

  it("includes the canonical Doctrine V6 footer", () => {
    const body = buildReviewBody(passingResult);
    expect(body).toContain("Doctrine V6");
    expect(body).toContain("bot-reviewer");
  });
});
