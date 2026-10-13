import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const page = readFileSync(new URL('../pages/fabric.html', import.meta.url), 'utf8');
const inline = page.match(/<script>\s*([\s\S]*?)<\/script>/i)?.[1];
assert.ok(inline, 'fabric inline script exists');
assert.match(inline, /\nloadAll\(\);\s*$/);
assert.doesNotMatch(page, /0 J \(unmeasured\)|joules MEASURED per node/);

const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    elements.set(id, {
      innerHTML: '', textContent: '',
      querySelector: () => null,
    });
  }
  return elements.get(id);
}
const context = {
  window: {},
  document: { getElementById: element },
  console,
};
vm.createContext(context);
vm.runInContext(inline.replace(/\nloadAll\(\);\s*$/, ''), context);

const unavailable = {
  joules_measured_total: 0,
  joules_measured_label: 'UNAVAILABLE',
  measured_token_joules: 0,
  measured_jobs: 0,
  jobs_done: 2,
  by_node: { omen: { jobs: 2, tokens: 20, joules_measured: 0, joules_label: 'PENDING_EXPORTER' } },
};
context.renderKpis({ counts: {} }, unavailable);
assert.match(element('kpis').innerHTML, /Attributed job joules[\s\S]*?UNAVAILABLE/);
assert.doesNotMatch(element('kpis').innerHTML, /Joules total[\s\S]*?MEASURED/);
context.renderEnergy(unavailable);
assert.match(element('energy').innerHTML, /Attributed job joules[\s\S]*?UNAVAILABLE/);
assert.match(element('byNode').innerHTML, /<td>—<\/td><td><span[^>]*>UNAVAILABLE/);
context.renderNodes({ nodes: [{ name: 'omen', kind: 'gpu', reachable: true, sovereign: true }] }, unavailable);
assert.match(element('nodes').innerHTML, /energy: —[\s\S]*?UNAVAILABLE/);
assert.doesNotMatch(element('nodes').innerHTML, /0 J/);
context.renderOrbit({ counts: {} }, unavailable);
assert.match(element('orbJ').innerHTML, /JOB JOULES UNAVAILABLE/);
context.renderKVerify({ data: { ran: true, n: 5, pass: 4,
  joules_measured: 12, joules_label: 'MEASURED' } });
assert.match(element('kv-state').innerHTML, /attributed job energy: <b>—<\/b>[\s\S]*?UNAVAILABLE/);

const attested = {
  ...unavailable,
  joules_measured_total: 12,
  joules_measured_label: 'MEASURED',
  attribution_verified: true,
  attribution_method: 'exclusive-job-window-v1',
  attribution_version: 1,
  by_node: { omen: { jobs: 2, tokens: 20, joules_measured: 12, joules_label: 'MEASURED',
    attribution_verified: true, attribution_method: 'exclusive-job-window-v1',
    attribution_version: 1 } },
};
context.renderEnergy(attested);
assert.match(element('energy').innerHTML, /Attributed job joules[\s\S]*?MEASURED/);
assert.match(element('byNode').innerHTML, /12 J/);
context.renderEnergy(unavailable);
assert.doesNotMatch(element('energy').innerHTML, /12 J/);
assert.doesNotMatch(element('byNode').innerHTML, /12 J/);
console.log('fabric energy attribution truth: ok');
