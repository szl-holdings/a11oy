// SPDX-License-Identifier: Apache-2.0
// Source consistency and known js-yaml advisory regressions, not a security scan.
import assert from 'node:assert/strict';
import { readFileSync, statSync } from 'node:fs';
import test from 'node:test';
import * as yaml from 'js-yaml';

const root = new URL('../', import.meta.url);
const decoder = new TextDecoder('utf-8', { fatal: true });
function source(name) {
  const path = new URL(name, root);
  assert.ok(statSync(path).size <= 2 * 1024 * 1024, 'bounded source file required');
  return decoder.decode(readFileSync(path));
}
function mapping(value) {
  assert.ok(value !== null && typeof value === 'object' && !Array.isArray(value));
  assert.ok(Object.keys(value).length > 0, 'explicit nonempty override map required');
  for (const [key, selected] of Object.entries(value)) {
    assert.ok(key.length > 0 && typeof selected === 'string' && selected.length > 0);
  }
  return value;
}
function verify(pkg, workspace, lock) {
  const expected = mapping(pkg.pnpm?.overrides);
  assert.deepEqual(mapping(workspace.overrides), expected, 'workspace policy differs from package.json');
  assert.deepEqual(mapping(lock.overrides), expected, 'lock policy differs from package.json');
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
  }
}
function fixture() {
  const policy = { 'js-yaml@<4.3.2': '4.3.2', browserslist: '4.28.8' };
  const packages = { 'js-yaml@4.3.2': {}, 'js-yaml@5.4.1': {}, 'browserslist@4.28.8': {} };
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
