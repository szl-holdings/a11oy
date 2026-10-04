'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const entries = JSON.parse(fs.readFileSync(path.join(root, 'data', 'genome.json'), 'utf8'));
const html = fs.readFileSync(path.join(root, 'web', 'trust.html'), 'utf8');
const byId = new Map(entries.map(entry => [entry.id, entry]));
const guardSource = html.match(/\/\* ---------- fail-closed guard[\s\S]*?\*\/([\s\S]*?)\/\* Kernel locked-proven/);
assert.ok(guardSource, 'Trust page must keep a testable source-binding guard');
const sandbox = {};
vm.runInNewContext(
  guardSource[1] + '\n;globalThis.trustGuard={hasAbsentLeanAnchor,semanticRowHasUsableRef,semanticDisplayState};',
  sandbox,
);
const guard = sandbox.trustGuard;
const tierBody = html.match(/\(async function loadTiers\(\)\{([\s\S]*?)\n\}\)\(\);/);
assert.ok(tierBody, 'Trust page must keep its tier renderer testable');

test('invalid legacy Lean anchors are evidence-backed without fabricated replacements', () => {
  const affected = ['Q4-LAKE-05', 'Q4-OTEL-02', 'Q4-OTEL-03', 'Q4-TRUST-02', 'Q4-DOCTRINE-02', 'Q4-DOCTRINE-03'];
  for (const id of affected) {
    assert.equal(byId.get(id).tag, 'evidence-backed', id);
    assert.equal(byId.get(id).lean_ref, null, id);
  }
  assert.equal(entries.length, 144);
  assert.equal(entries.filter(entry => entry.tag === 'LOCKED-PROVEN').length, 25);
  assert.equal(entries.filter(entry => entry.tag === 'SEMANTIC-VERIFIED').length, 6);
});

test('receipt transduction catalog distinguishes its theorem from the body corollary', () => {
  const receipt = byId.get('SV-RECEIPT');
  assert.equal(receipt.tag, 'SEMANTIC-VERIFIED');
  assert.equal(receipt.lean_ref, 'Lutar/Transduction/ReceiptInvariant.lean::receipt_transduction_invariant');
  assert.equal(
    receipt.meaning,
    'Under the explicit round-trip identity g ∘ f = id, receipt_transduction_invariant preserves contentId; body preservation is a separate corollary.',
  );
  assert.equal(receipt.locations[0].line, '23-29 (contentId theorem); 32-38 (body corollary)');
  assert.match(receipt.notes, /c7c0ba17.*no sorry.*h_round/);
  assert.doesNotMatch(receipt.meaning, /1 sorry|round-trip preserves body/);
});

test('Trust renderer withholds known absent anchors and refuses the reported count', () => {
  const good = byId.get('SV-LAMBDA-BOUNDS');
  assert.equal(guard.semanticRowHasUsableRef(good), true);
  const absentFiles = ['Soundness', 'STL', 'Gates', 'Receipt', 'Lambda'];
  for (const file of absentFiles) {
    const missing = { ...good, id: `fake-${file}`, lean_ref: `Lutar/${file}.lean::unverified` };
    assert.equal(guard.semanticRowHasUsableRef(missing), false, missing.id);
  }
  const missing = { ...good, id: 'fake-soundness', lean_ref: 'Lutar/Soundness.lean::gate_pass_implies_lambda_floor' };
  const noRef = { ...good, id: 'fake-unbound', lean_ref: null };
  const misleadingText = { ...good, id: 'fake-text', meaning: 'Proven by Lutar/Receipt.lean::dsse_seal_binding' };
  for (const row of [missing, noRef, misleadingText]) {
    assert.equal(guard.semanticRowHasUsableRef(row), false, row.id);
  }
  const state = guard.semanticDisplayState([good, missing, noRef, misleadingText], 4);
  assert.equal(state.rows.length, 1);
  assert.equal(state.rows[0].id, good.id);
  assert.equal(state.withheld, 3);
  assert.equal(state.count, null);
  assert.equal(guard.semanticDisplayState([good], 2).count, null, 'backend count mismatch must fail closed');
  assert.equal(guard.semanticDisplayState([good], 1).count, 1);
  assert.match(html, /\$\('semantic-rows'\)\.innerHTML = withheld\+\(sem\.length/);
  assert.match(html, /semantic\.count==null\?'N\/A'/);
});

test('rendered semantic rows hide an injected invalid anchor while locked-eight stays sourced from honest', async () => {
  const elements = new Map();
  const getElement = id => {
    if (!elements.has(id)) {
      const classes = new Set();
      elements.set(id, { firstChild: { nodeValue: '' }, classList: { add: value => classes.add(value), contains: value => classes.has(value) }, innerHTML: '', textContent: '' });
    }
    return elements.get(id);
  };
  const good = byId.get('SV-LAMBDA-BOUNDS');
  const injected = { ...good, id: 'bad-anchor', lean_ref: 'Lutar/Soundness.lean::gate_pass_implies_lambda_floor' };
  const context = {
    $: getElement,
    getJSON: async url => url.endsWith('/honest')
      ? { locked_formula_count: 8, locked_formula_ids: [] }
      : { count: 2, tier_counts: { 'LOCKED-PROVEN': 25, 'SEMANTIC-VERIFIED': 2, 'evidence-backed': 0, CONJECTURE: 0 }, entries: [good, injected] },
    kernelFromHonest: h => ({ count: h.locked_formula_count, ids: h.locked_formula_ids }),
    esc: value => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
  };
  vm.runInNewContext(guardSource[1] + '\nglobalThis.loadTiers=async function loadTiers(){' + tierBody[1] + '\n};', context);
  await context.loadTiers();
  assert.equal(getElement('cnt-locked').firstChild.nodeValue, 8);
  assert.equal(getElement('cnt-semantic').firstChild.nodeValue, 'N/A');
  assert.equal(getElement('d-genome').classList.contains('down'), true);
  assert.match(getElement('semantic-rows').innerHTML, /SV-LAMBDA-BOUNDS/);
  assert.match(getElement('semantic-rows').innerHTML, /1 SEMANTIC-VERIFIED row\(s\) withheld/);
  assert.doesNotMatch(getElement('semantic-rows').innerHTML, /Soundness\.lean|bad-anchor/);
});
