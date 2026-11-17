// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// External commands are fixtures; the real Bash runner and TypeScript reporter execute.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const scripts = path.dirname(fileURLToPath(import.meta.url));
const checkout = path.resolve(scripts, '../../..');
const bash = process.env.BASH_BIN ??
  (process.platform === 'win32' ? 'C:/Program Files/Git/bin/bash.exe' : 'bash');
const shellPath = value => value.replaceAll('\\', '/');
const artifactNames = ['README.md', 'LUTAR_EVIDENCE.md', '.test-count', 'full-test-output.json'];
const baselineReadme = '# Fixture source\n\nHistorical content stays intact.\n';

function completeReport() {
  return recount({
    startTime: Date.now() - 1,
    testResults: [
      { name: '/fixture/src/existing.test.ts', status: 'passed', assertionResults: [
        { fullName: 'existing contract one', status: 'passed' },
        { fullName: 'existing contract two', status: 'passed' },
      ] },
      { name: '/fixture/packages/ouroboros/src/lutar-invariant-proof.test.ts',
        status: 'passed', assertionResults: ['A1', 'A2', 'A3', 'A4', 'Boundary'].map(group =>
          ({ fullName: group + ' exercised witness', status: 'passed' })) },
    ],
  });
}

function recount(data) {
  const assertions = data.testResults.flatMap(file => file.assertionResults);
  Object.assign(data, {
    success: true,
    numTotalTests: assertions.length,
    numPassedTests: assertions.filter(item => item.status === 'passed').length,
    numFailedTests: assertions.filter(item => item.status === 'failed').length,
    numPendingTests: assertions.filter(item => item.status === 'pending').length,
    numTodoTests: assertions.filter(item => item.status === 'todo').length,
    numFailedTestSuites: 0, numPendingTestSuites: 0,
  });
  return data;
}

function fixture(t, data = completeReport()) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'lutar-evidence-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const repo = path.join(dir, 'runtime/ouroboros');
  const bin = path.join(dir, 'bin');
  fs.mkdirSync(path.join(repo, 'scripts'), { recursive: true });
  fs.mkdirSync(bin);
  for (const name of ['run-lutar-evidence.sh', 'lutar-evidence-report.ts']) {
    fs.copyFileSync(path.join(scripts, name), path.join(repo, 'scripts', name));
  }
  fs.writeFileSync(path.join(dir, 'package.json'), JSON.stringify({
    repository: { url: 'git+https://github.com/szl-holdings/a11oy.git' },
  }));
  fs.writeFileSync(path.join(repo, 'package.json'), '{"name":"@szl-holdings/ouroboros"}');
  fs.writeFileSync(path.join(dir, 'pnpm-lock.yaml'), 'fixture dependency contract\n');
  fs.writeFileSync(path.join(dir, 'pnpm-workspace.yaml'), 'fixture workspace\n');
  fs.writeFileSync(path.join(repo, 'README.md'), baselineReadme);
  for (const name of artifactNames.slice(1)) fs.writeFileSync(path.join(repo, name), 'previous ' + name);
  const before = Object.fromEntries(artifactNames.map(name =>
    [name, fs.readFileSync(path.join(repo, name), 'utf8')]));
  const input = path.join(dir, 'fixture.json');
  const log = path.join(dir, 'calls.log');
  fs.writeFileSync(input, typeof data === 'string' ? data : JSON.stringify(data));
  fs.writeFileSync(path.join(bin, 'pnpm'), `#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$EVIDENCE_TEST_LOG"
test "$1" = '--dir'
shift 2
if [[ "$1" = install ]]; then
  test "$2" = '--frozen-lockfile'
  test "$3" = '--ignore-scripts'
  exit "\${EVIDENCE_TEST_INSTALL_EXIT:-0}"
fi
test "$1" = exec
shift
tool="$1"
shift
if [[ "$tool" = vitest ]]; then
  output=''
  for arg in "$@"; do
    case "$arg" in --outputFile=*) output="\${arg#*=}";; esac
  done
  test -n "$output"
  if [[ "\${EVIDENCE_TEST_NO_OUTPUT:-0}" != 1 ]]; then cp -- "$EVIDENCE_TEST_INPUT" "$output"; fi
  printf 'noisy Vitest progress: 123 widgets\\nJSON report written to %s\\n' "$output"
  exit "\${EVIDENCE_TEST_SUITE_EXIT:-0}"
fi
test "$tool" = tsx
exec "$EVIDENCE_TEST_NODE" "$EVIDENCE_TEST_TSX" "$@"
`);
  fs.chmodSync(path.join(bin, 'pnpm'), 0o755);
  const env = { ...process.env };
  const inheritedPath = env.PATH ?? env.Path ?? '';
  for (const key of Object.keys(env)) if (key.toLowerCase() === 'path') delete env[key];
  Object.assign(env, {
    PATH: bin + path.delimiter + inheritedPath,
    EVIDENCE_TEST_LOG: shellPath(log),
    EVIDENCE_TEST_INPUT: shellPath(input),
    EVIDENCE_TEST_NODE: shellPath(process.execPath),
    EVIDENCE_TEST_TSX: shellPath(path.join(checkout, 'node_modules/tsx/dist/cli.mjs')),
  });
  delete env.REPO_DIR;
  function run(extra = {}) {
    return spawnSync(bash, [shellPath(path.join(repo, 'scripts/run-lutar-evidence.sh'))], {
      cwd: dir, env: { ...env, ...extra }, encoding: 'utf8', timeout: 30000,
    });
  }
  function read(name) { return fs.readFileSync(path.join(repo, name), 'utf8'); }
  function calls() { return fs.existsSync(log) ? fs.readFileSync(log, 'utf8') : ''; }
  function rejected(result, reason) {
    assert.equal(result.error, undefined, String(result.error));
    assert.notEqual(result.status, 0, result.stdout + result.stderr);
    for (const name of artifactNames) assert.equal(read(name), before[name], name);
    assert.equal(fs.readdirSync(repo).filter(name => name.startsWith('.lutar-evidence.')).length, 0);
    if (reason) assert.match(result.stderr, reason);
  }
  return { repo, dir, run, read, calls, rejected, input };
}

test('publishes one complete result; noisy command output never becomes a count', t => {
  const f = fixture(t);
  const result = f.run();
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(f.read('.test-count'), '7\n');
  assert.match(f.read('README.md'), /\*\*7\/7 passing\*\*/);
  assert.match(f.read('README.md'), /Historical content stays intact/);
  assert.doesNotMatch(f.read('README.md'), /noisy Vitest|JSON report written/);
  assert.equal(f.calls().split('\n').filter(line => line.includes(' exec vitest ')).length, 1);
  assert.doesNotMatch(f.calls(), /npx|dlx/);
  const digest = createHash('sha256').update(f.read('full-test-output.json')).digest('hex');
  assert.ok(f.read('LUTAR_EVIDENCE.md').includes(digest));
  assert.match(f.read('LUTAR_EVIDENCE.md'), /helper is defined inside the test file/);
});

test('installation failure preserves prior evidence and never runs tests', t => {
  const f = fixture(t);
  f.rejected(f.run({ EVIDENCE_TEST_INSTALL_EXIT: '23' }));
  assert.doesNotMatch(f.calls(), /exec/);
});

test('a failed complete suite cannot publish even if it writes a successful-looking report', t => {
  const f = fixture(t);
  f.rejected(f.run({ EVIDENCE_TEST_SUITE_EXIT: '17' }));
  assert.doesNotMatch(f.calls(), /exec tsx/);
});

test('a successful command with no JSON cannot publish', t => {
  const f = fixture(t);
  f.rejected(f.run({ EVIDENCE_TEST_NO_OUTPUT: '1' }), /Evidence rejected/);
});

const rejectedReports = [
  ['empty report', () => recount({ testResults: [] }), /must contain tests/],
  ['missing A4', data => {
    data.testResults[1].assertionResults.splice(3, 1);
    return recount(data);
  }, /Missing exercised cases for A4/],
  ['skipped assertion', data => {
    data.testResults[1].assertionResults[0].status = 'pending';
    return recount(data);
  }, /Not all declared tests passed/],
  ['future timestamp', data => ({ ...data, startTime: Date.now() + 60000 }), /future test-run timestamp/],
  ['failed report', data => ({ ...data, success: false }), /did not report success/],
  ['inconsistent count', data => ({ ...data, numTotalTests: 8, numPassedTests: 8 }),
    /count does not match/],
  ['unknown group', data => {
    data.testResults[1].assertionResults[0].fullName = 'A5 unrecognized';
    return data;
  }, /Unrecognized/],
  ['duplicate witness file', data => {
    data.testResults.push(structuredClone(data.testResults[1]));
    return recount(data);
  }, /exactly one/],
  ['witness-only result', data => {
    data.testResults.shift();
    return recount(data);
  }, /existing suite/],
  ['empty test file', data => {
    data.testResults[0].assertionResults = [];
    return recount(data);
  }, /contains no assertions/],
  ['unknown assertion status', data => {
    data.testResults[0].assertionResults[0].status = 'unknown';
    return data;
  }, /unknown status/],
  ['missing zero counter', data => {
    delete data.numTodoTests;
    return data;
  }, /missing numTodoTests/],
];
for (const [name, modify, reason] of rejectedReports) {
  test('rejects ' + name + ' without replacing prior evidence', t => {
    const f = fixture(t, modify(completeReport()));
    f.rejected(f.run(), reason);
  });
}

test('rejects malformed JSON', t => {
  const f = fixture(t, '{broken');
  f.rejected(f.run(), /Evidence rejected/);
});

test('rejects the wrong package before installation', t => {
  const f = fixture(t);
  fs.writeFileSync(path.join(f.repo, 'package.json'), '{"name":"wrong-package"}');
  f.rejected(f.run(), /canonical/);
  assert.equal(f.calls(), '');
});

test('rejects a missing lockfile before installation', t => {
  const f = fixture(t);
  fs.unlinkSync(path.join(f.dir, 'pnpm-lock.yaml'));
  f.rejected(f.run(), /pnpm-lock/);
  assert.equal(f.calls(), '');
});

test('repeated publication replaces one managed status block with the current numeric count', t => {
  const f = fixture(t);
  const first = f.run();
  assert.equal(first.status, 0, first.stdout + first.stderr);
  const data = completeReport();
  data.testResults[0].assertionResults.push({ fullName: 'new baseline check', status: 'passed' });
  fs.writeFileSync(f.input, JSON.stringify(recount(data)));
  const next = f.run();
  assert.equal(next.status, 0, next.stdout + next.stderr);
  assert.equal(f.read('.test-count'), '8\n');
  assert.equal(f.read('README.md').split('<!-- lutar-evidence:start -->').length - 1, 1);
  assert.match(f.read('README.md'), /\*\*8\/8 passing\*\*/);
  assert.doesNotMatch(f.read('README.md'), /7\/7 passing/);
});
