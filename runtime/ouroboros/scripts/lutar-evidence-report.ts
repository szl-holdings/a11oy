// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// Usage: pnpm exec tsx <this-file> <full-vitest.json> <README.md> <staging-dir>

import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';

interface AssertionResult {
  fullName?: string;
  status?: string;
  title?: string;
}
interface FileResult {
  testFilePath?: string;
  name?: string;
  status?: string;
  assertionResults?: AssertionResult[];
}
interface Report {
  success?: boolean;
  startTime?: number;
  numTotalTests?: number;
  numPassedTests?: number;
  numFailedTests?: number;
  numPendingTests?: number;
  numTodoTests?: number;
  numFailedTestSuites?: number;
  numPendingTestSuites?: number;
  testResults?: FileResult[];
}

function requireCondition(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function prepareEvidence(inputPath: string, readmePath: string, outputDir: string) {
  const input = fs.readFileSync(inputPath, 'utf8');
  const data: Report = JSON.parse(input);
  requireCondition(data !== null && typeof data === 'object', 'Invalid Vitest report');
  requireCondition(data.success === true, 'Vitest did not report success');
  requireCondition(Number.isSafeInteger(data.numTotalTests) && data.numTotalTests! > 0,
    'The complete suite must contain tests');
  requireCondition(data.numPassedTests === data.numTotalTests, 'Not all declared tests passed');
  for (const key of ['numFailedTests', 'numPendingTests', 'numTodoTests',
    'numFailedTestSuites', 'numPendingTestSuites'] as const) {
    requireCondition(data[key] === 0, `Nonzero or missing ${key}`);
  }
  requireCondition(Number.isSafeInteger(data.startTime) && data.startTime! > 0 && data.startTime! <= Date.now(),
    'Missing, invalid, or future test-run timestamp');
  requireCondition(Array.isArray(data.testResults) && data.testResults.length > 0,
    'Missing test-file results');
  const files = data.testResults;
  const assertions: AssertionResult[] = [];
  for (const file of files) {
    requireCondition(file && file.status === 'passed', 'A test file did not pass');
    requireCondition(Array.isArray(file.assertionResults) && file.assertionResults.length > 0,
      'A test file contains no assertions');
    for (const assertion of file.assertionResults) {
      requireCondition(assertion && assertion.status === 'passed',
        'A test assertion failed, was skipped, or has an unknown status');
      assertions.push(assertion);
    }
  }
  requireCondition(assertions.length === data.numTotalTests,
    'Declared test count does not match the assertion results');

  const proofFiles = files.filter(file =>
    /(?:^|\/)packages\/ouroboros\/src\/lutar-invariant-proof\.test\.ts$/
      .test((file.testFilePath ?? file.name ?? '').replace(/\\/g, '/')));
  requireCondition(proofFiles.length === 1, 'Expected exactly one legacy Lutar witness test file');
  const proofAssertions = proofFiles[0].assertionResults!;
  requireCondition(assertions.length > proofAssertions.length,
    'The full result must include the existing suite, not only the witness file');
  const groups = ['A1', 'A2', 'A3', 'A4', 'Boundary'];
  const grouped = new Map(groups.map(group => [group, [] as string[]]));
  for (const assertion of proofAssertions) {
    const name = assertion.fullName ?? assertion.title ?? '';
    const group = /^(A[1-4]|Boundary)\b/.exec(name)?.[1];
    requireCondition(group && grouped.has(group), 'Unrecognized Lutar witness group');
    grouped.get(group)!.push(name);
  }
  for (const group of groups) {
    requireCondition(grouped.get(group)!.length > 0, `Missing exercised cases for ${group}`);
  }

  const total = assertions.length;
  const generatedAt = new Date().toISOString();
  const digest = createHash('sha256').update(input).digest('hex');
  const lines = [
    '# Lutar Invariant: local test evidence', '',
    `**Generated at:** ${generatedAt}`,
    `**Test run started:** ${new Date(data.startTime!).toISOString()}`,
    '**Source:** szl-holdings/a11oy, runtime/ouroboros',
    `**Configured root suite:** ${total}/${total} assertions passed; none failed or skipped.`,
    `**Legacy witness file:** ${proofAssertions.length} assertions.`,
    '**Input:** [full-test-output.json](full-test-output.json)',
    `**Input SHA-256:** \`${digest}\``, '',
    '## Exercised legacy groups', '',
    '| Group | Passed cases | Status |',
    '|---|---:|---|',
    ...groups.map(group =>
      `| ${group} | ${grouped.get(group)!.length} | Passed exercised cases |`),
    '', '## Evidence boundary', '',
    'These are finite numerical checks from the Ouroboros Thesis v3 witness suite ' +
      '(https://doi.org/10.5281/zenodo.19951520). Its weighted-geometric-mean helper ' +
      'is defined inside the test file; this report does not establish that a deployed ' +
      'implementation is equivalent to that helper.',
    'The root Vitest configuration covers src/ and packages/; agentic/ and runtime/ ' +
      'subpackage suites are outside this run.',
    'Passing examples do not prove universal axioms, current Lean theorem coverage, ' +
      'Lambda uniqueness, production readiness, energy measurement, or third-party audit. ' +
      'The A1-A4 names below are the legacy v3 test labels.', '',
    '## Witness cases', '',
  ];
  for (const group of groups) {
    lines.push(`### ${group}`, '',
      ...grouped.get(group)!.map(name => `- PASS: ${name.replace(/[\r\n]/g, ' ')}`), '');
  }
  lines.push('## Reproduce', '', 'From the a11oy checkout with Node.js 24 and pnpm 10.26.1 installed:',
    '', '\`\`\`bash', 'bash runtime/ouroboros/scripts/run-lutar-evidence.sh', '\`\`\`', '',
    'The runner uses the committed workspace lockfile and local pnpm executables. ' +
      'It publishes only after the full suite and report validation succeed.', '');

  const begin = '<!-- lutar-evidence:start -->';
  const end = '<!-- lutar-evidence:end -->';
  const readme = fs.readFileSync(readmePath, 'utf8');
  const begins = readme.split(begin).length - 1;
  const ends = readme.split(end).length - 1;
  requireCondition(begins === ends && begins <= 1 &&
    (begins === 0 || readme.indexOf(begin) < readme.indexOf(end)),
    'Malformed README evidence markers');
  const block = [
    begin, '## Local Lutar test evidence', '',
    `**${total}/${total} passing** at ${generatedAt}; no failed or skipped assertions.`,
    '[Report and evidence boundary](LUTAR_EVIDENCE.md) · ' +
      '[Exact test output](full-test-output.json).',
    'This is a dated local test result, not a production or formal-proof claim.',
    end,
  ].join('\n');
  const nextReadme = begins
    ? readme.slice(0, readme.indexOf(begin)) + block + readme.slice(readme.indexOf(end) + end.length)
    : readme.trimEnd() + '\n\n' + block + '\n';

  // Validate everything before writing even the staging outputs.
  fs.writeFileSync(path.join(outputDir, 'LUTAR_EVIDENCE.md'), lines.join('\n'));
  fs.writeFileSync(path.join(outputDir, 'README.md'), nextReadme);
  fs.writeFileSync(path.join(outputDir, '.test-count'), `${total}\n`);
  console.log(`Validated ${total} passing assertions and all five legacy witness groups.`);
}

try {
  const [inputPath, readmePath, outputDir] = process.argv.slice(2);
  requireCondition(inputPath && readmePath && outputDir,
    'Usage: lutar-evidence-report.ts <full-vitest.json> <README.md> <staging-dir>');
  prepareEvidence(inputPath, readmePath, outputDir);
} catch (error) {
  console.error(`Evidence rejected: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
