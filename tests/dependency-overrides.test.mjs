// SPDX-License-Identifier: Apache-2.0
// Source consistency and known dependency advisory regressions, not a security scan.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
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
function verifyFastUri(version) {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(version);
  assert.ok(match, 'a stable inspectable fast-uri resolution is required');
  const [major, minor, patch] = match.slice(1).map(Number);
  // GHSA-hrr3-gc8f-f4qj: fixes are specific to the supported 2, 3 and 4 lines.
  const minimum = { 2: [4, 7], 3: [1, 8], 4: [1, 5] }[major];
  assert.ok(minimum, 'an explicitly reviewed fast-uri release line is required');
  assert.ok(minor > minimum[0] || (minor === minimum[0] && patch >= minimum[1]), version);
}
function fastUriPolicy(overrides) {
  assert.ok(overrides !== null && typeof overrides === 'object' && !Array.isArray(overrides),
    'explicit override object required');
  assert.equal(overrides['fast-uri@<3.1.8'], '3.1.8', 'reviewed compatible fast-uri override required');
  assert.deepEqual(Object.keys(overrides).filter((key) => key === 'fast-uri' || key.startsWith('fast-uri@')),
    ['fast-uri@<3.1.8'], 'stale or ambiguous fast-uri override selectors are rejected');
  return overrides['fast-uri@<3.1.8'];
}
function verifyNpmFastUri(pkg, lock) {
  // npm also permits nested package-specific override objects for other dependencies.
  const selected = fastUriPolicy(pkg.overrides);
  assert.equal(selected, fastUriPolicy(mapping(pkg.pnpm?.overrides)), 'npm and pnpm fast-uri policy differs');
  assert.ok(lock.packages && typeof lock.packages === 'object' && !Array.isArray(lock.packages));
  const resolutions = Object.entries(lock.packages).filter(([path]) => path.endsWith('node_modules/fast-uri'));
  assert.ok(resolutions.length > 0, 'expected npm fast-uri resolution is absent');
  for (const [, entry] of resolutions) {
    verifyFastUri(entry.version);
    assert.equal(entry.version, selected, 'npm fast-uri resolution differs from reviewed policy');
    assert.equal(entry.resolved, `https://registry.npmjs.org/fast-uri/-/fast-uri-${entry.version}.tgz`);
    assert.ok(typeof entry.integrity === 'string' && entry.integrity.startsWith('sha512-'));
  }
}
function verify(pkg, workspace, lock) {
  const expected = mapping(pkg.pnpm?.overrides);
  assert.deepEqual(mapping(workspace.overrides), expected, 'workspace policy differs from package.json');
  assert.deepEqual(mapping(lock.overrides), expected, 'lock policy differs from package.json');
  verifyBraceExpansion(expected['brace-expansion']);
  const selectedFastUri = fastUriPolicy(expected);
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
    const uriKeys = Object.keys(section).filter((name) => name.startsWith('fast-uri@'));
    assert.ok(uriKeys.length > 0, `${sectionName}: expected fast-uri resolution is absent`);
    for (const key of uriKeys) {
      const match = /^fast-uri@(\d+\.\d+\.\d+)(?:\([^\r\n]*\))?$/.exec(key);
      assert.ok(match, 'a stable inspectable fast-uri resolution is required');
      verifyFastUri(match[1]);
      assert.equal(match[1], selectedFastUri, 'resolved fast-uri differs from override');
    }
  }
}
function fixture() {
  const policy = { 'js-yaml@<4.3.2': '4.3.2', browserslist: '4.28.8', 'brace-expansion': '5.0.12', 'fast-uri@<3.1.8': '3.1.8' };
  const packages = { 'js-yaml@4.3.2': {}, 'js-yaml@5.4.1': {}, 'browserslist@4.28.8': {}, 'brace-expansion@5.0.12': {}, 'fast-uri@3.1.8': {} };
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

test('affected fast-uri versions, unsupported lines and prereleases are rejected', () => {
  for (const version of ['1.0.0', '2.4.6', '3.0.0', '3.1.7', '4.0.0', '4.1.4', '3.1.8-rc.1']) {
    assert.throws(() => verifyFastUri(version));
  }
});

test('patched fast-uri release-line floors remain accepted', () => {
  for (const version of ['2.4.7', '3.1.8', '4.1.5']) verifyFastUri(version);
});

test('the old fast-uri conditional selector cannot exclude the vulnerable 3.1.7', () => {
  const values = fixture();
  for (const overrides of [values[0].pnpm.overrides, values[1].overrides, values[2].overrides]) {
    delete overrides['fast-uri@<3.1.8'];
    overrides['fast-uri@<3.1.7'] = '3.1.8';
  }
  assert.throws(() => verify(...values));
});

test('affected or prerelease fast-uri resolutions cannot hide behind patched pnpm headers', () => {
  for (const section of ['packages', 'snapshots']) {
    for (const version of ['2.4.6', '3.1.7', '4.1.4', '3.1.8-rc.1']) {
      const values = fixture(); values[2][section][`fast-uri@${version}`] = {};
      assert.throws(() => verify(...values));
    }
  }
});

test('missing fast-uri package or snapshot observations are rejected', () => {
  for (const section of ['packages', 'snapshots']) {
    const values = fixture(); delete values[2][section]['fast-uri@3.1.8'];
    assert.throws(() => verify(...values));
  }
});

test('the actual npm manifest and regenerated lock select compatible fast-uri 3.1.8', () => {
  verifyNpmFastUri(JSON.parse(source('package.json')), JSON.parse(source('package-lock.json')));
});

test('npm stale selectors, vulnerable lines, prereleases and missing resolutions are rejected', () => {
  const policy = { 'fast-uri@<3.1.8': '3.1.8' };
  const pkg = { overrides: { ...policy }, pnpm: { overrides: { ...policy } } };
  const entry = { version: '3.1.8', resolved: 'https://registry.npmjs.org/fast-uri/-/fast-uri-3.1.8.tgz', integrity: 'sha512-fixture' };
  const lock = { packages: { 'node_modules/fast-uri': entry } };
  verifyNpmFastUri(pkg, lock);
  for (const version of ['2.4.6', '3.1.7', '4.1.4', '3.1.8-rc.1']) {
    assert.throws(() => verifyNpmFastUri(pkg, { packages: { 'node_modules/fast-uri': { ...entry, version } } }));
  }
  assert.throws(() => verifyNpmFastUri(pkg, { packages: {} }));
  assert.throws(() => verifyNpmFastUri({ ...pkg, overrides: { 'fast-uri@<3.1.7': '3.1.8' } }, lock));
});

test('the actually installed Ajv URI parser normalizes encoded uppercase host octets consistently', () => {
  const ajvRequire = createRequire(import.meta.resolve('ajv'));
  const uri = ajvRequire('fast-uri');
  const installed = ajvRequire('fast-uri/package.json');
  assert.equal(installed.version, '3.1.8', 'actual Ajv dependency must match the reviewed lock');
  for (const encoded of ['//%41.com', '//%61.com', '//A.com']) {
    assert.equal(uri.parse(encoded).host, 'a.com');
    assert.equal(uri.normalize(encoded), '//a.com');
    assert.equal(uri.equal(encoded, '//a.com'), true);
  }
  assert.equal(uri.equal('//%41.com', '//b.com'), false, 'different hosts must remain distinct');
  assert.equal(uri.parse('https://EXAMPLE.com/a%2Fb').host, 'example.com');
  assert.equal(uri.normalize('https://example.com/a%2Fb'), 'https://example.com/a%2Fb', 'reserved path octets remain data');
});

test('every source-map-js resolution uses the reviewed GHSA-68fv-2mgg-jv7q patch', () => {
  const pkg = JSON.parse(source('package.json'));
  const workspace = yaml.load(source('pnpm-workspace.yaml'));
  const lock = yaml.load(source('pnpm-lock.yaml'));
  for (const policy of [pkg.overrides, pkg.pnpm.overrides, workspace.overrides, lock.overrides]) {
    assert.equal(policy['source-map-js'], '1.2.2');
  }
  for (const section of ['packages', 'snapshots']) {
    const copies = Object.keys(lock[section]).filter((key) => key.startsWith('source-map-js@'));
    assert.deepEqual(copies, ['source-map-js@1.2.2'], `${section}: inspect every resolved copy`);
  }
  assert.equal(lock.packages['source-map-js@1.2.2'].resolution.integrity,
    'sha512-KGj/8Y43x35aZVDtt+J4mK1hoLGHULMYfSkODJNQjNDC3oW1PqPoxMwo0pLUsWM/UEGzON/NxeHywEfNXNP3Vw==');
  for (const [key, snapshot] of Object.entries(lock.snapshots)) {
    if (snapshot.dependencies?.['source-map-js']) {
      assert.equal(snapshot.dependencies['source-map-js'], '1.2.2', key);
    }
  }
});

test('the installed PostCSS source-map dependency preserves ordinary mapping round trips', () => {
  const knowledgeRequire = createRequire(new URL('../packages/a11oy-knowledge/package.json', import.meta.url));
  const vitestRequire = createRequire(knowledgeRequire.resolve('vitest/package.json'));
  const viteRequire = createRequire(vitestRequire.resolve('vite/package.json'));
  const postcssRequire = createRequire(viteRequire.resolve('postcss/package.json'));
  assert.equal(postcssRequire('source-map-js/package.json').version, '1.2.2');
  const { SourceMapGenerator, SourceMapConsumer } = postcssRequire('source-map-js');
  const generator = new SourceMapGenerator({ file: 'output.css' });
  generator.addMapping({ generated: { line: 1, column: 0 },
    original: { line: 3, column: 2 }, source: 'input.css', name: 'color' });
  generator.setSourceContent('input.css', '.sample { color: blue; }');
  const consumer = new SourceMapConsumer(generator.toJSON());
  assert.deepEqual(consumer.originalPositionFor({ line: 1, column: 0 }),
    { source: 'input.css', line: 3, column: 2, name: 'color' });
  assert.equal(consumer.sourceContentFor('input.css'), '.sample { color: blue; }');
});
