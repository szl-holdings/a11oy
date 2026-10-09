import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const page = readFileSync(new URL('../pages/energy-ops.html', import.meta.url), 'utf8');
const declaration = page.match(/function renderTodayStatus\(t\) \{[\s\S]*?\n  \}\n\n  function refreshToday\(/)?.[0];
assert.ok(declaration, 'operator status renderer exists');
assert.match(page, /id="big-joules-chip">UNAVAILABLE/);
assert.match(page, /id="m-joules-chip">UNAVAILABLE/);

const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, { textContent: '' });
  return elements.get(id);
}
function counter() {
  return { value: null, clear() { this.value = null; }, set(value) { this.value = value; } };
}
const mTokens = counter();
const mJobs = counter();
const mJoules = counter();
const bigJoules = counter();
const context = {
  document: { getElementById: element },
  mTokens, mJobs, mJoules, bigJoules,
  isErr: (value) => !value || value.__error === true,
  num: (value) => { const parsed = typeof value === 'number' ? value : parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null; },
  setChip: (chip, label) => { chip.textContent = label; },
};
const fn = vm.runInNewContext(`(${declaration.replace(/\n\n  function refreshToday\($/, '')})`, context);

fn({ tokens_total: 8, jobs_done: 2, joules_measured_total: 0,
  joules_measured_label: 'UNAVAILABLE' });
assert.equal(mTokens.value, 8);
assert.equal(mJobs.value, 2);
assert.equal(mJoules.value, null);
assert.equal(bigJoules.value, null);
assert.equal(element('m-joules-chip').textContent, 'UNAVAILABLE');
assert.equal(element('big-joules-chip').textContent, 'UNAVAILABLE');

fn({ tokens_total: 9, jobs_done: 3, joules_measured_total: 12,
  joules_measured_label: 'MEASURED', attribution_verified: true,
  attribution_method: 'exclusive-job-window-v1', attribution_version: 1 });
assert.equal(mJoules.value, 12);
assert.equal(bigJoules.value, 12);
assert.equal(element('big-joules-chip').textContent, 'MEASURED');

fn({ __error: true });
assert.equal(mJoules.value, null);
assert.equal(bigJoules.value, null);
assert.equal(element('big-joules-chip').textContent, 'UNAVAILABLE');
console.log('energy ops downgrade and attribution truth: ok');
