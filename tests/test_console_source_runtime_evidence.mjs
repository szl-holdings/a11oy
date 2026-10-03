// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { Script, runInNewContext } from 'node:vm';

const html = readFileSync(new URL('../pages/console.html', import.meta.url), 'utf8');
const start = html.indexOf('/* source-runtime-evidence:begin');
const end = html.indexOf('/* source-runtime-evidence:end */');
assert.ok(start >= 0 && end > start, 'the shipped command console contains the evidence reader');
const script = html.slice(start, end);
const sha = 'a'.repeat(40);
const later = '2030-10-04T00:00:00Z';
const now = Date.parse('2030-10-03T00:00:00Z');
const paths = {
  build: '/api/build-info',
  series: '/api/a11oy/v1/series-a/status',
  steward: '/api/a11oy/v1/steward/status',
};

test('the changed inline scripts parse as shipped browser JavaScript', () => {
  const bodies = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(match => match[1]);
  const relevant = bodies.filter(body => body.includes('source-runtime-evidence:begin') ||
    body.includes("V.command={ title:'Command Center', badge:'LIVE · AUTO-POLL'"));
  assert.equal(relevant.length, 2);
  for (const body of relevant) assert.doesNotThrow(() => new Script(body));
});

function reader(fetch, el = () => null) {
  return runInNewContext(`${script}\n({ collect: sourceRuntimeCollect, refresh: sourceRuntimeEvidenceRefresh })`, {
    AbortController, TextDecoder, Uint8Array, Date, setTimeout, clearTimeout, fetch, el,
  });
}

function fixtures() {
  return {
    [paths.build]: {
      status: 'OBSERVED', receipt_minted: false,
      build: { state: 'OBSERVED', revision: sha, revision_source: 'env:SZL_GIT_SHA' },
    },
    [paths.series]: {
      schema: 'szl.series-a-status/v1', state: 'OBSERVED', terminal: true,
      source_revision: sha, valid_until: later, critical_failures: [],
      storage: { persistence_required: true, mount_verified: true },
    },
    [paths.steward]: {
      schema_version: 'szl.a11oy.steward.surface/v1', state: 'CURRENT',
      scope: 'PUBLIC_READ_ONLY', production_ready: false, snapshot_current: true,
      source: { repository: 'szl-holdings/szl-estate-os', revision: 'b'.repeat(40) },
    },
  };
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { 'content-type': 'application/json' },
  });
}

function fromFixtures(data, overrides = {}) {
  const calls = [];
  const fetch = async (path, options) => {
    calls.push({ path, options });
    return overrides[path] ?? json(data[path]);
  };
  return { fetch, calls };
}

test('reads only the three public same-origin contracts and preserves separate states', async () => {
  const { fetch, calls } = fromFixtures(fixtures());
  const result = await reader(fetch).collect(fetch, now);
  assert.equal(result.build.state, 'OBSERVED');
  assert.equal(result.build.revision, sha);
  assert.equal(result.series.state, 'OBSERVED');
  assert.equal(result.steward.state, 'CURRENT');
  assert.deepEqual(calls.map(x => x.path).sort(), Object.values(paths).sort());
  for (const { options } of calls) {
    assert.equal(options.method, 'GET');
    assert.equal(options.credentials, 'omit');
    assert.equal(options.mode, 'same-origin');
    assert.equal(options.redirect, 'error');
    assert.equal(options.cache, 'no-store');
    assert.equal(options.headers.Accept, 'application/json');
    assert.ok(options.signal);
  }
});

test('rejects an HTML 200 SPA fallback and does not mint a source revision', async () => {
  const data = fixtures();
  const fallback = new Response('<html>not an API</html>', {
    status: 200, headers: { 'content-type': 'text/html' },
  });
  const { fetch } = fromFixtures(data, { [paths.build]: fallback });
  const result = await reader(fetch).collect(fetch, now);
  assert.equal(result.build.state, 'UNAVAILABLE');
  assert.equal(result.build.revision, null);
  assert.equal(result.series.state, 'UNAVAILABLE');
});

test('preserves unavailable, malformed, and bounded response failures', async () => {
  const data = fixtures();
  const overrides = {
    [paths.build]: new Response('{oops', { headers: { 'content-type': 'application/json' } }),
    [paths.series]: new Response('x'.repeat(65537), { headers: { 'content-type': 'application/json' } }),
    [paths.steward]: json({ message: 'do not display this backend detail' }, 503),
  };
  const { fetch } = fromFixtures(data, overrides);
  const result = await reader(fetch).collect(fetch, now);
  assert.equal(result.build.state, 'UNAVAILABLE');
  assert.equal(result.series.state, 'UNAVAILABLE');
  assert.equal(result.steward.state, 'UNAVAILABLE');
  assert.doesNotMatch(JSON.stringify(result), /do not display this backend detail/);
});

test('expires a reported observed Series A status and refuses an unsafe or unbound SHA', async () => {
  const expired = fixtures();
  expired[paths.series].valid_until = '2030-10-02T23:59:59Z';
  const expiredFetch = fromFixtures(expired).fetch;
  assert.equal((await reader(expiredFetch).collect(expiredFetch, now)).series.state, 'STALE');

  const unsafe = fixtures();
  unsafe[paths.build].build.revision = 'https://attacker.example/?key=secret';
  const unsafeFetch = fromFixtures(unsafe).fetch;
  const unsafeResult = await reader(unsafeFetch).collect(unsafeFetch, now);
  assert.equal(unsafeResult.build.revision, null);
  assert.equal(unsafeResult.series.state, 'UNAVAILABLE');

  const unbound = fixtures();
  unbound[paths.build].build.revision_source = 'git:HEAD';
  const unboundFetch = fromFixtures(unbound).fetch;
  assert.equal((await reader(unboundFetch).collect(unboundFetch, now)).build.state, 'UNAVAILABLE');

  const zeros = fixtures();
  zeros[paths.build].build.revision = '0'.repeat(40);
  const zeroFetch = fromFixtures(zeros).fetch;
  const zeroResult = await reader(zeroFetch).collect(zeroFetch, now);
  assert.equal(zeroResult.build.revision, null);
  assert.equal(zeroResult.series.state, 'UNAVAILABLE');
});

test('checks validity at completion, after the API reads return', async () => {
  const data = fixtures();
  data[paths.series].valid_until = '2030-10-03T00:00:01Z';
  let finish;
  const gate = new Promise(resolve => { finish = resolve; });
  const fetch = async path => { await gate; return json(data[path]); };
  let clock = Date.parse('2030-10-03T00:00:00Z');
  const pending = reader(fetch).collect(fetch, () => clock);
  clock = Date.parse('2030-10-03T00:00:02Z');
  finish();
  assert.equal((await pending).series.state, 'STALE');
});

test('network failure keeps every row unavailable', async () => {
  const fetch = async () => { throw new Error('credential=must-not-leak'); };
  const result = await reader(fetch).collect(fetch, now);
  for (const key of ['build', 'series', 'steward']) {
    assert.equal(result[key].state, 'UNAVAILABLE');
  }
  assert.doesNotMatch(JSON.stringify(result), /credential=must-not-leak/);
});

test('the visible card starts without a commit link and labels external destinations as links only', () => {
  const finalCommand = html.indexOf("V.command={ title:'Command Center', badge:'LIVE · AUTO-POLL'");
  assert.ok(finalCommand > 0, 'the final Command Center overlay exists');
  const card = html.indexOf('id="source-runtime-evidence"');
  assert.ok(card > finalCommand, 'the card is mounted in the final shipped Command Center render');
  const block = html.slice(card, card + 2600);
  assert.match(block, /id="source-runtime-commit"[^>]*hidden/);
  assert.match(block, /Hugging Face Space · link only/);
  assert.match(block, /Product domain · link only/);
  assert.match(block, /Proof domain · link only/);
  assert.match(block, /do not verify provider parity, proof-domain health, or production readiness/);
  assert.match(html.slice(card, card + 3100), /sourceRuntimeEvidenceRefresh\(\)/);
});

test('the rendered commit link appears only for a validated environment-bound revision', async () => {
  const ids = [
    'source-runtime-build-state', 'source-runtime-build-detail',
    'source-runtime-series-state', 'source-runtime-series-detail',
    'source-runtime-steward-state', 'source-runtime-steward-detail',
    'source-runtime-commit', 'source-runtime-observed',
  ];
  const elements = new Map(ids.map(id => [id, {
    textContent: '', className: '', hidden: false, href: '',
    removeAttribute(name) { if (name === 'href') this.href = ''; },
  }]));
  const validFetch = fromFixtures(fixtures()).fetch;
  await reader(validFetch, id => elements.get(id)).refresh();
  const commit = elements.get('source-runtime-commit');
  assert.equal(commit.hidden, false);
  assert.equal(commit.href, `https://github.com/szl-holdings/a11oy/commit/${sha}`);
  assert.equal(elements.get('source-runtime-build-state').textContent, 'OBSERVED');

  const unsafe = fixtures();
  unsafe[paths.build].build.revision = 'https://attacker.example';
  const unsafeFetch = fromFixtures(unsafe).fetch;
  await reader(unsafeFetch, id => elements.get(id)).refresh();
  assert.equal(commit.hidden, true);
  assert.equal(commit.href, '');
  assert.equal(elements.get('source-runtime-build-state').textContent, 'UNAVAILABLE');
});

test('a delayed earlier refresh cannot overwrite the newer browser read', async () => {
  const ids = [
    'source-runtime-build-state', 'source-runtime-build-detail',
    'source-runtime-series-state', 'source-runtime-series-detail',
    'source-runtime-steward-state', 'source-runtime-steward-detail',
    'source-runtime-commit', 'source-runtime-observed',
  ];
  const elements = new Map(ids.map(id => [id, {
    textContent: '', className: '', hidden: false, href: '',
    removeAttribute(name) { if (name === 'href') this.href = ''; },
  }]));
  const first = fixtures();
  const second = fixtures();
  second[paths.build].build.revision = 'c'.repeat(40);
  second[paths.series].source_revision = 'c'.repeat(40);
  const delayed = [];
  let calls = 0;
  const fetch = (path) => {
    calls += 1;
    if (calls <= 3) return new Promise(resolve => delayed.push(() => resolve(json(first[path]))));
    return Promise.resolve(json(second[path]));
  };
  const page = reader(fetch, id => elements.get(id));
  const firstRead = page.refresh();
  const secondRead = page.refresh();
  await secondRead;
  assert.equal(elements.get('source-runtime-commit').href,
    `https://github.com/szl-holdings/a11oy/commit/${'c'.repeat(40)}`);
  delayed.forEach(release => release());
  await firstRead;
  assert.equal(elements.get('source-runtime-commit').href,
    `https://github.com/szl-holdings/a11oy/commit/${'c'.repeat(40)}`);
});
