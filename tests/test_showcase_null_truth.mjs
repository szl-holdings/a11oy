import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../static/3d/energy_showcase/showcase.js', import.meta.url), 'utf8');
const numFunction = source.match(/function num\(v\) \{[\s\S]*?\n\}/)?.[0];
assert.ok(numFunction, 'numeric parser exists');
const num = vm.runInNewContext(`(${numFunction})`);
assert.equal(num(null), null);
assert.equal(num(undefined), null);
assert.equal(num(''), null);
assert.equal(num('  '), null);
assert.equal(num(false), null);
assert.equal(num(0), 0);
assert.equal(num('12.5'), 12.5);

assert.match(source, /json\.attribution_verified === true/);
assert.match(source, /Number\.isInteger\(json\.attribution_version\)/);
assert.match(source, /Number\.isInteger\(totals\.attribution_version\)/);
assert.match(source, /llabel\(mi\.joules_measured\) !== "MEASURED"/);
assert.match(source, /mode === "dry-run" && wouldCharge != null/);
assert.match(source, /host\.setLabel\(len > 0 \? "REPORTED" : "STRUCTURAL-ONLY"\)/);
assert.doesNotMatch(source, /host\.setLabel\(len > 0 \? "MEASURED"/);
console.log('showcase null/attribution contract: ok');
