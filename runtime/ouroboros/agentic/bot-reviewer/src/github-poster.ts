// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: 12_agentic/bot-reviewer — GitHub PR review poster
// Doctrine V6 preflight: ✓ (no forbidden patterns)
//
// NON-INTERACTIVE: no CLI calls at module-init time.
// GITHUB_TOKEN is read from env at call time.
// Pass --dry-run to print what would be posted without calling gh.

import { spawnSync } from "node:child_process";
import type { ReviewResult } from "./reviewer.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PostReviewOptions {
  owner: string;
  repo: string;
  pr: number;
  result: ReviewResult;
  /** When true, print the review body to stdout instead of calling gh. */
  dryRun?: boolean;
}

export interface PostReviewOutcome {
  success: boolean;
  body: string;
  error?: string;
}

// ---------------------------------------------------------------------------
// Body builder
// ---------------------------------------------------------------------------

/**
 * Builds the markdown body for a GitHub PR review comment from a ReviewResult.
 */
export function buildReviewBody(result: ReviewResult): string {
  const status = result.pass ? "PASS" : "FAIL";
  const badge = result.pass
    ? "![PASS](https://img.shields.io/badge/Doctrine%20V6-PASS-brightgreen)"
    : "![FAIL](https://img.shields.io/badge/Doctrine%20V6-FAIL-red)";

  const lines: string[] = [
    `## Doctrine V6 Bot Review — ${status}`,
    "",
    badge,
    "",
  ];

  if (result.pass) {
    lines.push("All Doctrine V6 checks passed. This PR is clear to merge.");
  } else {
    lines.push(
      `**${result.violations.length} violation(s) found.** Please resolve before merging.`,
      "",
      "| # | Rule | File | Detail |",
      "|---|------|------|--------|",
    );
    // Markdown table cell sanitization: escape backslash FIRST (CodeQL js/incomplete-sanitization),
    // then pipe, then collapse newlines and backticks. Order matters — escaping pipe before
    // backslash would re-escape our own added backslashes.
    const escapeCell = (s: string): string =>
      s
        .replace(/\\/g, "\\\\")
        .replace(/\|/g, "\\|")
        .replace(/`/g, "\\`")
        .replace(/\r?\n/g, " ");
    result.violations.forEach((v, idx) => {
      const safeDetail = escapeCell(v.detail);
      const safeFile = escapeCell(v.filePath);
      lines.push(`| ${idx + 1} | \`${v.rule}\` | \`${safeFile}\` | ${safeDetail} |`);
    });
  }

  lines.push(
    "",
    "---",
    "*Automated by [@szl/bot-reviewer](https://github.com/stephenlutar2-hash) — Doctrine V6*",
  );

  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Poster
// ---------------------------------------------------------------------------

/**
 * Posts a PR review to GitHub using the `gh` CLI.
 * The GITHUB_TOKEN environment variable must be set before calling this.
 * Pass dryRun: true to print the body without calling gh.
 *
 * The gh CLI is invoked via child_process.spawnSync — this module never
 * calls gh at import time.
 */
export function postReview(opts: PostReviewOptions): PostReviewOutcome {
  const { owner, repo, pr, result, dryRun = false } = opts;
  const body = buildReviewBody(result);

  if (dryRun) {
    console.log("=== DRY RUN — would post the following review ===");
    console.log(`Target: ${owner}/${repo} PR#${pr}`);
    console.log("---");
    console.log(body);
    console.log("=== END DRY RUN ===");
    return { success: true, body };
  }

  // Ensure GITHUB_TOKEN is available
  const token = process.env["GITHUB_TOKEN"];
  if (!token) {
    const error =
      "GITHUB_TOKEN not set in environment — cannot post review without authentication";
    console.error(error);
    return { success: false, body, error };
  }

  // Invoke the gh CLI
  const spawnResult = spawnSync(
    "gh",
    [
      "pr",
      "review",
      String(pr),
      "--repo",
      `${owner}/${repo}`,
      "--comment",
      "--body",
      body,
    ],
    {
      encoding: "utf8",
      env: { ...process.env, GITHUB_TOKEN: token },
      stdio: "pipe",
    },
  );

  if (spawnResult.status !== 0) {
    const error = [
      `gh exited with status ${String(spawnResult.status)}`,
      spawnResult.stderr?.trim() ?? "",
    ]
      .filter(Boolean)
      .join(": ");
    console.error(error);
    return { success: false, body, error };
  }

  return { success: true, body };
}

// ---------------------------------------------------------------------------
// CLI entry
// ---------------------------------------------------------------------------

const isMain =
  typeof process !== "undefined" &&
  process.argv[1] != null &&
  (process.argv[1].endsWith("github-poster.ts") ||
    process.argv[1].endsWith("github-poster.js"));

if (isMain) {
  // Usage: tsx src/github-poster.ts <owner> <repo> <pr> [--dry-run]
  // Reads review result from stdin as JSON.
  const args = process.argv.slice(2);
  const dryRun = args.includes("--dry-run");
  const positional = args.filter((a) => a !== "--dry-run");

  if (positional.length < 3) {
    console.error(
      "Usage: tsx src/github-poster.ts <owner> <repo> <pr> [--dry-run]",
    );
    console.error("  Review result JSON is read from stdin.");
    process.exit(1);
  }

  const [owner, repo, prStr] = positional;
  const pr = Number(prStr);
  if (!Number.isInteger(pr) || pr <= 0) {
    console.error(`Invalid PR number: ${prStr}`);
    process.exit(1);
  }

  let stdinData = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk: string) => {
    stdinData += chunk;
  });
  process.stdin.on("end", () => {
    let result: ReviewResult;
    try {
      result = JSON.parse(stdinData) as ReviewResult;
    } catch {
      console.error("Could not parse review result JSON from stdin");
      process.exit(1);
    }

    const outcome = postReview({ owner: owner!, repo: repo!, pr, result, dryRun });
    process.exit(outcome.success ? 0 : 1);
  });
}
