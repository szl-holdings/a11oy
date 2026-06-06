import assert from 'node:assert/strict';
import {
  wrapIngress,
  verifyIngress,
  ingressDist,
} from './css_ingress.ts';

function run(name: string, fn: () => void) {
  try { fn(); console.log(`  ok    ${name}`); }
  catch (e) { console.error(`  FAIL  ${name}`); console.error(e); process.exitCode = 1; }
}

console.log('Rosie QEC CSS ingress');

run('wrap then verify round-trip', () => {
  const r = wrapIngress(0x42);
  assert.equal(verifyIngress(r), true);
});

run('wrap 0x00 verifies', () => {
  assert.equal(verifyIngress(wrapIngress(0x00)), true);
});

run('wrap 0xFF verifies', () => {
  assert.equal(verifyIngress(wrapIngress(0xff)), true);
});

run('tampered payload fails verification', () => {
  const r = wrapIngress(0x55);
  const tampered = { ...r, payloadDigest: 0xaa };
  assert.equal(verifyIngress(tampered), false);
});

run('tampered stabilizer fails verification', () => {
  const r = wrapIngress(0x55);
  const tampered = { ...r, stabilizer: { xParity: 0x55, zParity: 0x00 } };
  assert.equal(verifyIngress(tampered), false);
});

run('identical receipts have ingress distance 0', () => {
  const a = wrapIngress(0x42);
  const b = wrapIngress(0x42);
  assert.equal(ingressDist(a, b), 0);
});

run('differing receipts have positive ingress distance', () => {
  const a = wrapIngress(0x00);
  const b = wrapIngress(0xff);
  assert.equal(ingressDist(a, b), 8);
});

console.log(process.exitCode === 1 ? '\nFAIL' : '\nall green (7 tests)');
