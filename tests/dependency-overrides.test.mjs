// SPDX-License-Identifier: Apache-2.0
// Source consistency and known dependency advisory regressions, not a security scan.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import * as yaml from 'js-yaml';

const root = new URL('../', import.meta.url);
const decoder = new TextDecoder('utf-8', { fatal: true });
function source(name) {
  const path = new URL(name, root);
  const bytes = readFileSync(path);
  assert.ok(bytes.byteLength <= 2 * 1024 * 1024, 'bounded source file required');
  return decoder.decode(bytes);
}
function mapping(value) {
  assert.ok(value !== null && typeof value === 'object' && !Array.isArray(value));
  assert.ok(Object.keys(value).length > 0, 'explicit nonempty override map required');
  for (const [key, selected] of Object.entries(value)) {
    assert.ok(key.length > 0 && typeof selected === 'string' && selected.length > 0);
  }
  return value;
}
function verifyBraceExpansion(version) {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(version);
  assert.ok(match, 'a stable inspectable brace-expansion resolution is required');
  const [major, minor, patch] = match.slice(1).map(Number);
  // GHSA-q2hr-2g5m-vwhr: all supported older release lines have separate fixes.
  const minimum = { 1: [1, 21], 2: [1, 7], 3: [0, 9], 5: [0, 12] }[major];
  assert.ok(minimum, 'an explicitly reviewed brace-expansion release line is required');
  assert.ok(minor > minimum[0] || (minor === minimum[0] && patch >= minimum[1]), version);
}
function verifyRae1Vitest(version) {
  const match = /^4\.(\d+)\.(\d+)$/.exec(version);
  assert.ok(match, 'the reviewed stable Vitest 4 release line is required');
  const [minor, patch] = match.slice(1).map(Number);
  // GHSA-82fw-gwwq-j7x9 has no maintained Vitest 3 backport.
  assert.ok(minor > 1 || (minor === 1 && patch >= 11), version);
}
function verify(pkg, workspace, lock) {
  const expected = mapping(pkg.pnpm?.overrides);
  assert.deepEqual(mapping(workspace.overrides), expected, 'workspace policy differs from package.json');
  assert.deepEqual(mapping(lock.overrides), expected, 'lock policy differs from package.json');
  verifyBraceExpansion(expected['brace-expansion']);
  for (const sectionName of ['packages', 'snapshots']) {
    const section = lock[sectionName];
    assert.ok(section !== null && typeof section === 'object' && !Array.isArray(section));
    const parserKeys = Object.keys(section).filter((name) => name.startsWith('js-yaml@'));
    assert.ok(parserKeys.length > 0, `${sectionName}: expected parser resolution is absent`);
    for (const key of parserKeys) {
      const match = /^js-yaml@(\d+)\.(\d+)\.(\d+)(?:\([^\r\n]*\))?$/.exec(key);
      assert.ok(match, 'a stable inspectable js-yaml resolution is required');
      const [, majorText, minorText, patchText] = match;
      const [major, minor, patch] = [majorText, minorText, patchText].map(Number);
      // GHSA-2883-xcg3-v3hh: fixed in 3.15.2 and 4.3.2.
      if (major === 3) assert.ok(minor > 15 || (minor === 15 && patch >= 2), key);
      if (major === 4) assert.ok(minor > 3 || (minor === 3 && patch >= 2), key);
    }
    const browserKeys = Object.keys(section).filter((name) => name.startsWith('browserslist@'));
    assert.ok(browserKeys.length > 0, `${sectionName}: expected browserslist resolution is absent`);
    assert.ok(/^\d+\.\d+\.\d+$/.test(expected.browserslist), 'exact browserslist policy required');
    for (const key of browserKeys) {
      assert.equal(key.split('(')[0], `browserslist@${expected.browserslist}`);
    }
    const braceKeys = Object.keys(section).filter((name) => name.startsWith('brace-expansion@'));
    assert.ok(braceKeys.length > 0, `${sectionName}: expected brace-expansion resolution is absent`);
    for (const key of braceKeys) {
      const match = /^brace-expansion@(\d+\.\d+\.\d+)(?:\([^\r\n]*\))?$/.exec(key);
      assert.ok(match, 'a stable inspectable brace-expansion resolution is required');
      verifyBraceExpansion(match[1]);
      assert.equal(match[1], expected['brace-expansion'], 'resolved brace-expansion differs from override');
    }
  }
}
function fixture() {
  const policy = { 'js-yaml@<4.3.2': '4.3.2', browserslist: '4.28.8', 'brace-expansion': '5.0.12' };
  const packages = { 'js-yaml@4.3.2': {}, 'js-yaml@5.4.1': {}, 'browserslist@4.28.8': {}, 'brace-expansion@5.0.12': {} };
  return [{ pnpm: { overrides: { ...policy } } }, { overrides: { ...policy } },
    { overrides: { ...policy }, packages: structuredClone(packages), snapshots: structuredClone(packages) }];
}

test('the actual root manifest, workspace and generated lock agree', () => {
  verify(JSON.parse(source('package.json')), yaml.load(source('pnpm-workspace.yaml')),
    yaml.load(source('pnpm-lock.yaml')));
});
test('coherent security resolutions are accepted', () => verify(...fixture()));
test('stale workspace overrides are rejected', () => {
  const values = fixture(); values[1].overrides['js-yaml@<4.3.1'] = '4.3.1';
  assert.throws(() => verify(...values));
});
test('stale lock overrides are rejected', () => {
  const values = fixture(); values[2].overrides.browserslist = '4.28.7';
  assert.throws(() => verify(...values));
});
test('missing and malformed policy maps are rejected', () => {
  for (const invalid of [null, [], {}, { x: 1 }]) {
    const values = fixture(); values[0].pnpm.overrides = invalid;
    assert.throws(() => verify(...values));
  }
});
test('affected js-yaml 4.3.1 is rejected in either resolution section', () => {
  for (const section of ['packages', 'snapshots']) {
    const values = fixture(); values[2][section]['js-yaml@4.3.1'] = {};
    assert.throws(() => verify(...values));
  }
});
test('affected js-yaml 3.15.1 is rejected', () => {
  const values = fixture(); values[2].packages['js-yaml@3.15.1'] = {};
  assert.throws(() => verify(...values));
});
test('patched js-yaml 3.15.2 remains accepted', () => {
  const values = fixture(); values[2].packages['js-yaml@3.15.2'] = {};
  verify(...values);
});
test('a prerelease is not assumed to contain the stable security fix', () => {
  const values = fixture(); values[2].packages['js-yaml@4.3.2-rc.1'] = {};
  assert.throws(() => verify(...values));
});
test('missing package observations are not a successful security result', () => {
  const values = fixture(); values[2].snapshots = { 'browserslist@4.28.8': {} };
  assert.throws(() => verify(...values));
});
test('stale resolved browserslist is rejected even when override headers agree', () => {
  const values = fixture(); values[2].snapshots['browserslist@4.28.7'] = {};
  assert.throws(() => verify(...values));
});
test('the actual YAML parser rejects duplicate override keys', () => {
  assert.throws(() => yaml.load('overrides:\n  browserslist: 4.28.8\n  browserslist: 4.28.7\n'));
});
test('affected brace-expansion versions are rejected on every reviewed release line', () => {
  for (const version of ['1.1.20', '2.1.6', '3.0.8', '4.0.0', '5.0.9', '5.0.11', '5.0.12-rc.1']) {
    assert.throws(() => verifyBraceExpansion(version));
  }
});
test('patched brace-expansion release-line floors remain accepted', () => {
  for (const version of ['1.1.21', '2.1.7', '3.0.9', '5.0.12']) verifyBraceExpansion(version);
});
test('stale brace-expansion package or snapshot cannot hide behind a patched override', () => {
  for (const section of ['packages', 'snapshots']) {
    const values = fixture(); values[2][section]['brace-expansion@5.0.11'] = {};
    assert.throws(() => verify(...values));
  }
});
test('missing brace-expansion resolutions are not a successful security result', () => {
  const values = fixture(); delete values[2].snapshots['brace-expansion@5.0.12'];
  assert.throws(() => verify(...values));
});
test('the actual npm policy and generated lock select the reviewed brace-expansion version', () => {
  const pkg = JSON.parse(source('package.json'));
  assert.equal(pkg.overrides['brace-expansion'], pkg.pnpm.overrides['brace-expansion']);
  const lock = JSON.parse(source('package-lock.json'));
  const resolutions = Object.entries(lock.packages).filter(([path]) => path.endsWith('node_modules/brace-expansion'));
  assert.ok(resolutions.length > 0, 'expected npm brace-expansion resolution is absent');
  for (const [, entry] of resolutions) {
    verifyBraceExpansion(entry.version);
    assert.equal(entry.version, pkg.overrides['brace-expansion']);
    assert.equal(entry.resolved, `https://registry.npmjs.org/brace-expansion/-/brace-expansion-${entry.version}.tgz`);
    assert.ok(typeof entry.integrity === 'string' && entry.integrity.startsWith('sha512-'));
  }
});
test('RAE1 rejects affected and prerelease test runners', () => {
  for (const version of ['3.2.6', '4.0.0', '4.1.10', '4.1.11-rc.1']) {
    assert.throws(() => verifyRae1Vitest(version));
  }
  verifyRae1Vitest('4.1.11');
});
test('the actual RAE1 standalone manifest and lock preserve patched tooling and Node 20 compatibility', () => {
  const pkg = JSON.parse(source('packages/rae1/package.json'));
  const lock = JSON.parse(source('packages/rae1/package-lock.json'));
  assert.deepEqual(lock.packages[''].devDependencies, pkg.devDependencies);
  assert.equal(pkg.engines.node, '>=20.0.0');
  assert.equal(lock.packages[''].engines.node, pkg.engines.node);
  verifyRae1Vitest(pkg.devDependencies.vitest.replace(/^\^/, ''));
  for (const name of ['vitest', '@vitest/mocker']) {
    const resolutions = Object.entries(lock.packages).filter(([path]) => path.endsWith(`node_modules/${name}`));
    assert.ok(resolutions.length > 0, `expected RAE1 ${name} resolution is absent`);
    for (const [, entry] of resolutions) {
      verifyRae1Vitest(entry.version);
      assert.ok(entry.resolved.startsWith('https://registry.npmjs.org/'));
      assert.ok(typeof entry.integrity === 'string' && entry.integrity.startsWith('sha512-'));
    }
  }
  assert.match(pkg.devDependencies.vite, /^\^6\.\d+\.\d+$/);
  assert.match(lock.packages['node_modules/vite'].version, /^6\.\d+\.\d+$/);
});
