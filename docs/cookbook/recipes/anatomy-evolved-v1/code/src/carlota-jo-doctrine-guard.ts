/**
 * carlota-jo-doctrine-guard.ts — ban-list grep at bundle and verdict time
 * Organ: carlota-jo (IMMUNE SYSTEM / DOCTRINE GUARD)
 * Source: szl_master_payload.md §A — Doctrine v6 ban-list
 * Author: Stephen P. Lutar Jr., SZL Holdings
 * INVARIANT: no banned token appears in any output, ever.
 */

export const BANNED_TOKENS = [
  "AlloyScape",
  "Glass Wing",
  "Glasswing",
  "Mythos",
  "Stephen Paul",
] as const;

export type BannedToken = (typeof BANNED_TOKENS)[number];

export interface DoctrineScanResult {
  passed: boolean;
  violations: Array<{ token: BannedToken; positions: number[] }>;
  scannedLength: number;
}

/** Case-insensitive scan of any string for banned tokens */
export function scanForBannedTokens(text: string): DoctrineScanResult {
  const violations: DoctrineScanResult["violations"] = [];
  const lower = text.toLowerCase();
  for (const token of BANNED_TOKENS) {
    const positions: number[] = [];
    let pos = 0;
    const t = token.toLowerCase();
    while ((pos = lower.indexOf(t, pos)) !== -1) {
      positions.push(pos);
      pos += t.length;
    }
    if (positions.length > 0) violations.push({ token, positions });
  }
  return { passed: violations.length === 0, violations, scannedLength: text.length };
}

/** Assert no violations — throws with full report if any found */
export function assertDoctrineCompliance(text: string, context: string = "output"): void {
  const result = scanForBannedTokens(text);
  if (!result.passed) {
    const details = result.violations
      .map(v => `  "${v.token}" at positions [${v.positions.join(", ")}]`)
      .join("\n");
    throw new Error(`DOCTRINE VIOLATION in ${context}:\n${details}`);
  }
}

/** Scan a bundle of files — call at build time */
export function scanBundle(files: Record<string, string>): Record<string, DoctrineScanResult> {
  const results: Record<string, DoctrineScanResult> = {};
  for (const [path, content] of Object.entries(files)) {
    results[path] = scanForBannedTokens(content);
  }
  return results;
}

// ─── Usage Example ────────────────────────────────────────────────────────────
/*
assertDoctrineCompliance("Welcome, Stephen P. Lutar Jr.", "greeting"); // passes
try {
  assertDoctrineCompliance("Contact Stephen Paul for support"); // throws
} catch (e) {
  console.error(e.message); // DOCTRINE VIOLATION: "Stephen Paul" at positions [8]
}
*/