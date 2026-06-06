import assert from 'node:assert/strict';
import {
  assetToSite,
  detectLocalDrift,
} from './posture_drift_lattice';

function run(name: string, fn: () => void) {
  try { fn(); console.log(`  ok    ${name}`); }
  catch (e) { console.error(`  FAIL  ${name}`); console.error(e); process.exitCode = 1; }
}

console.log('Sentra QEC posture drift lattice');

run('assetToSite is deterministic', () => {
  const a = assetToSite({ asset: 'web-srv-01', slice: 5 });
  const b = assetToSite({ asset: 'web-srv-01', slice: 5 });
  assert.deepEqual(a, b);
});

run('different assets hash to different sites', () => {
  const a = assetToSite({ asset: 'web-srv-01', slice: 0 });
  const b = assetToSite({ asset: 'web-srv-02', slice: 0 });
  assert.notDeepEqual(a, b);
});

run('no drift -> no syndrome', () => {
  const detected = detectLocalDrift(
    { asset: 'a', slice: 0 },
    { asset: 'b', slice: 1 },
    { asset: 'c', slice: 0 },
    { asset: 'd', slice: 2 },
    new Set<string>(),
  );
  assert.equal(detected, false);
});

run('one asset drifted -> syndrome detected', () => {
  const detected = detectLocalDrift(
    { asset: 'a', slice: 0 },
    { asset: 'b', slice: 1 },
    { asset: 'c', slice: 0 },
    { asset: 'd', slice: 2 },
    new Set(['a']),
  );
  assert.equal(detected, true);
});

run('all 4 assets drifted -> parity cancels (weight-4 undetectable)', () => {
  const detected = detectLocalDrift(
    { asset: 'a', slice: 0 },
    { asset: 'b', slice: 1 },
    { asset: 'c', slice: 0 },
    { asset: 'd', slice: 2 },
    new Set(['a', 'b', 'c', 'd']),
  );
  assert.equal(detected, false);
});

run('off-lattice drift -> no syndrome', () => {
  const detected = detectLocalDrift(
    { asset: 'a', slice: 0 },
    { asset: 'b', slice: 1 },
    { asset: 'c', slice: 0 },
    { asset: 'd', slice: 2 },
    new Set(['unrelated-asset']),
  );
  assert.equal(detected, false);
});

console.log(process.exitCode === 1 ? '\nFAIL' : '\nall green (6 tests)');
