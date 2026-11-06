// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import * as qec from '../packages/qec-integrity/src/qec_lineage.ts';
import { executeProperties } from './qec_properties.mjs';

assert.equal(process.argv.length, 2, 'no test filters or collection-only mode supported');
// An absent module/import error fails before execution. Empty/no-op suites and
// assertion/runtime errors must be failures rather than zero-test successes.
assert.throws(() => executeProperties(qec, []), /must not be empty/);
assert.throws(() => executeProperties(qec, [['empty', () => {}]]), /no completed input/);
assert.throws(() => executeProperties(qec, [['failure', (_, check) => check(() => assert.fail('fixture'))]]), /fixture/);
assert.throws(() => executeProperties(qec, [['error', () => { throw new Error('fixture'); }]]), /fixture/);
const baseline = executeProperties(qec);
console.log(JSON.stringify({ kind: 'qec-properties', scope: 'classical byte and receipt helpers only', ...baseline }));

const source = await readFile(new URL('../packages/qec-integrity/src/qec_lineage.ts', import.meta.url), 'utf8');
const mutants = [
  ['byte distance constant', 'return count;', 'return 0;'],
  ['boolean distance constant', 'return d;', 'return 0;'],
  ['length mismatch ignored', 'if (a.length !== b.length)', 'if (false)'],
  ['weight constant', 'return w;', 'return 0;'],
  ['minimum becomes maximum', 'if (d < m) m = d;', 'if (d > m) m = d;'],
  ['eight receipts', 'length: 9', 'length: 8'],
  ['aliased receipts', '() => ({ ...logical })', '() => logical'],
  ['lineage discarded', '() => ({ ...logical })', '() => ({ payload: logical.payload, lineage: 0 })'],
  ['first receipt wins', 'if (c > bestCount)', 'if (false)'],
  ['wrong CSS complement', '(codeword ^ 0xff) & 0xff', 'codeword & 0xff'],
  ['CSS accepts corruption', '(pair.xParity ^ pair.zParity) === 0xff', 'true'],
  ['vertex drops west edge', 'errs(v.n) !== errs(v.s) !== errs(v.e) !== errs(v.w)', 'errs(v.n) !== errs(v.s) !== errs(v.e)'],
  ['site ignores slice', 'a.agent === b.agent && a.slice === b.slice', 'a.agent === b.agent'],
  ['site ignores agent', 'a.agent === b.agent && a.slice === b.slice', 'a.slice === b.slice'],
];
const directory = await mkdtemp(join(tmpdir(), 'a11oy-qec-mutations-'));
const detected = [];
try {
  for (const [index, [name, before, after]] of mutants.entries()) {
    assert.equal(source.split(before).length - 1, 1, `${name}: mutation source anchor drift`);
    const path = join(directory, `mutant-${index}.mts`);
    await writeFile(path, source.replace(before, after));
    // Import/syntax failure is a harness error, not a detected regression.
    const mutant = await import(pathToFileURL(path).href);
    let failure;
    try { executeProperties(mutant); } catch (error) { failure = error; }
    assert.ok(failure instanceof assert.AssertionError, `${name}: survived or failed outside an assertion`);
    detected.push(name);
  }
} finally {
  await rm(directory, { recursive: true, force: true });
}
assert.equal(detected.length, mutants.length);
console.log(JSON.stringify({ kind: 'qec-mutations', detected: detected.length, total: mutants.length, mutants: detected }));
