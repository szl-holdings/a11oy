import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const page = readFileSync(new URL('../pages/energy-ops.html', import.meta.url), 'utf8');
const declaration = page.match(/function renderTodayStatus\(t\) \{[\s\S]*?\n  \}\n\n  function refreshToday\(/)?.[0];
assert.ok(declaration, 'operator status renderer exists');
assert.match(page, /id="big-joules-chip">UNAVAILABLE/);
assert.match(page, /id="m-joules-chip">UNAVAILABLE/);
assert.match(page, /class="chip chip-unavailable" id="stream-chip">UNAVAILABLE/,
  'power stream must not claim a measurement before the first read');

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

const liveDeclaration = page.match(/function renderLive\(d\) \{[\s\S]*?\n  \}\n\n  function renderNodeCards\(/)?.[0];
assert.ok(liveDeclaration, 'live power renderer exists');
const liveElements = new Map();
function liveElement(id) {
  if (!liveElements.has(id)) {
    const classes = new Set();
    liveElements.set(id, {
      textContent: '',
      classList: {
        add: (name) => classes.add(name),
        remove: (name) => classes.delete(name),
        toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name),
        contains: (name) => classes.has(name),
      },
    });
  }
  return liveElements.get(id);
}
const samples = [];
const gaugeReads = [];
const liveContext = {
  document: { getElementById: liveElement },
  isErr: context.isErr,
  num: context.num,
  setChip: context.setChip,
  markLive: () => {},
  gTotal: { set: (watts, available) => gaugeReads.push({ watts, available }) },
  fmt: (value, decimals) => value.toFixed(decimals),
  esc: String,
  pushSample: (watts, offline) => samples.push({ watts, offline }),
  renderNodeCards: () => {},
};
const renderLive = vm.runInNewContext(
  `(${liveDeclaration.replace(/\n\n  function renderNodeCards\($/, '')})`, liveContext);

const qualified = {
  label: 'MEASURED', watts_label: 'MEASURED', joules_label: 'MEASURED',
  meter_status: 'ok', total_watts: 100, total_joules: 5, exporter: 'NVML', nodes: [],
};
renderLive(qualified);
assert.equal(samples.at(-1).offline, false, 'successful ok meter must not become offline');
assert.equal(samples.at(-1).watts, 100);
assert.equal(gaugeReads.at(-1).available, true);
assert.equal(liveElement('stream-chip').textContent, 'MEASURED');
assert.equal(liveElement('gauge-total-val').textContent, '100.0');

renderLive({ ...qualified, label: 'UNAVAILABLE', joules_label: 'UNAVAILABLE',
  total_watts: 80, total_joules: null });
assert.equal(samples.at(-1).offline, false, 'valid power remains visible without joules');
assert.equal(samples.at(-1).watts, 80);
assert.equal(liveElement('stream-chip').textContent, 'MEASURED');
assert.match(liveElement('gauge-total-sub').textContent, /Σ joules —/);
assert.equal(liveElement('stream-note').textContent, 'on-box NVML power, live');

renderLive({ ...qualified, watts_label: 'UNAVAILABLE' });
assert.equal(samples.at(-1).offline, true, 'unqualified watts must not be graphed');
assert.equal(liveElement('stream-chip').textContent, 'UNAVAILABLE');

renderLive({ ...qualified, meter_status: 'http-530' });
assert.equal(samples.at(-1).offline, true, 'failed meter read must fail closed');
assert.equal(liveElement('stream-chip').textContent, 'UNAVAILABLE');
assert.equal(liveElement('gauge-total-val').textContent, '—');
renderLive({ __error: true, status: 530 });
assert.equal(samples.at(-1).offline, true, 'failed API fetch must fail closed');
assert.equal(gaugeReads.at(-1).available, false);
console.log('energy ops downgrade and attribution truth: ok');
