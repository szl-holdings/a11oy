/**
 * lutar-evidence-report.ts
 *
 * Reads vitest JSON output and emits a one-page human-readable
 * report summarizing whether each axiom is empirically demonstrated.
 *
 * Usage (after vitest run):
 *   npx vitest run --reporter=json --outputFile=test-output.json
 *   npx tsx scripts/lutar-evidence-report.ts test-output.json > LUTAR_EVIDENCE.md
 */

import * as fs from 'node:fs';

const inputPath = process.argv[2] ?? 'test-output.json';
const data = JSON.parse(fs.readFileSync(inputPath, 'utf8'));

interface AssertionResult {
  fullName?: string;
  status: string;
  title?: string;
}
interface FileResult {
  testFilePath?: string;
  name?: string;
  assertionResults?: AssertionResult[];
}

const files: FileResult[] = data.testResults ?? [];
const proofFile = files.find(f => (f.testFilePath ?? f.name ?? '').includes('lutar-invariant-proof'));
if (!proofFile) {
  console.error('ERROR: lutar-invariant-proof.test results not found in test output');
  process.exit(1);
}
const all = proofFile.assertionResults ?? [];

const groups = ['A1', 'A2', 'A3', 'A4', 'Boundary'];
const groupCounts: Record<string, { passed: number; failed: number; tests: string[] }> = {};
for (const g of groups) groupCounts[g] = { passed: 0, failed: 0, tests: [] };

for (const a of all) {
  const name = a.fullName ?? a.title ?? '';
  let g = 'Boundary';
  if (name.startsWith('A1')) g = 'A1';
  else if (name.startsWith('A2')) g = 'A2';
  else if (name.startsWith('A3')) g = 'A3';
  else if (name.startsWith('A4')) g = 'A4';
  if (a.status === 'passed') groupCounts[g].passed++;
  else groupCounts[g].failed++;
  groupCounts[g].tests.push(`${a.status === 'passed' ? '✓' : '✗'} ${name}`);
}

const total = all.length;
const passed = all.filter(a => a.status === 'passed').length;
const failed = total - passed;

const today = new Date().toISOString().slice(0, 10);

const lines: string[] = [];
lines.push(`# Lutar Invariant Λ — Empirical Axiom Evidence`);
lines.push(``);
lines.push(`**Date:** ${today}`);
lines.push(`**Repo:** szl-holdings/ouroboros`);
lines.push(`**File:** packages/ouroboros/src/lutar-invariant-proof.test.ts`);
lines.push(`**Total assertions:** ${total}`);
lines.push(`**Passed:** ${passed}`);
lines.push(`**Failed:** ${failed}`);
lines.push(``);
lines.push(`## Λ definition`);
lines.push(``);
lines.push(`Λ(x_1, ..., x_9; w_1, ..., w_9) = ∏ xᵢ^wᵢ — the weighted geometric mean of nine independent runtime-trust axis scores in [0, 1] under non-negative weights summing to 1.`);
lines.push(``);
lines.push(`## Axiom-level evidence`);
lines.push(``);
lines.push(`| Axiom | Tests | Passed | Failed | Status |`);
lines.push(`|---|---|---|---|---|`);
for (const g of ['A1', 'A2', 'A3', 'A4']) {
  const c = groupCounts[g];
  const total = c.passed + c.failed;
  const status = c.failed === 0 ? 'demonstrated' : 'FAILED';
  lines.push(`| ${g} | ${total} | ${c.passed} | ${c.failed} | ${status} |`);
}
{
  const c = groupCounts.Boundary;
  const total = c.passed + c.failed;
  lines.push(`| Boundary / sanity | ${total} | ${c.passed} | ${c.failed} | ${c.failed === 0 ? 'demonstrated' : 'FAILED'} |`);
}
lines.push(``);
lines.push(`## Per-test detail`);
lines.push(``);
for (const g of groups) {
  lines.push(`### ${g}`);
  lines.push(``);
  for (const t of groupCounts[g].tests) lines.push(`- ${t}`);
  lines.push(``);
}
lines.push(`## What this evidence does and does not establish`);
lines.push(``);
lines.push(`**Establishes:** the closed-form Λ = ∏ xᵢ^wᵢ, evaluated in IEEE-754 double precision, satisfies its four axioms (monotonicity, zero-pinning, Egyptian inspectability, Page-curve concavity) on the test points exercised above.`);
lines.push(``);
lines.push(`**Does not establish:** that any specific runtime configuration in production has been audited, that any third-party body has reviewed this work, that the runtime is deployed in any product. The runtime is open-source under the licenses declared in this repository. Empire APEX (administered by NYSTEC) is a procurement-counseling resource the founder engaged with on 2026-04-30; it is not an audit.`);
lines.push(``);
lines.push(`**Reproduce:**`);
lines.push(``);
lines.push('```bash');
lines.push(`pnpm install`);
lines.push(`npx vitest run packages/ouroboros/src/lutar-invariant-proof.test.ts`);
lines.push('```');
lines.push(``);

console.log(lines.join('\n'));
