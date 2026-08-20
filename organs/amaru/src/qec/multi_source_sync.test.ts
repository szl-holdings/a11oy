import assert from 'node:assert/strict';
import {
  convergeSources,
  detectCorruptedSources,
  sourcePairDistance,
  SourceDelta,
} from './multi_source_sync';

function run(name: string, fn: () => void) {
  try { fn(); console.log(`  ok    ${name}`); }
  catch (e) { console.error(`  FAIL  ${name}`); console.error(e); process.exitCode = 1; }
}

console.log('Amaru QEC multi-source sync');

const cleanSources: SourceDelta[] = [
  { sourceId: 'A', payload: 0x42, lineage: 0xa5 },
  { sourceId: 'B', payload: 0x42, lineage: 0xa5 },
  { sourceId: 'C', payload: 0x42, lineage: 0xa5 },
];

run('5 clean sources converge to payload', () => {
  assert.equal(convergeSources(cleanSources), 0x42);
});

run('zero sources gives zero', () => {
  assert.equal(convergeSources([]), 0);
});

run('single source converges to itself', () => {
  assert.equal(convergeSources([{ sourceId: 'X', payload: 0x99, lineage: 0x00 }]), 0x99);
});

run('detect 0 corruption when all clean', () => {
  assert.equal(detectCorruptedSources(cleanSources), 0);
});

run('detect 1 corruption', () => {
  const sources = [
    ...cleanSources,
    { sourceId: 'D', payload: 0xFF, lineage: 0xa5 },
  ];
  assert.equal(detectCorruptedSources(sources), 1);
});

run('Hamming distance between identical sources is 0', () => {
  assert.equal(sourcePairDistance(cleanSources[0], cleanSources[1]), 0);
});

run('Hamming distance fingerprints drift', () => {
  const drifted = { sourceId: 'D', payload: 0x43, lineage: 0xa5 };
  // 0x42 ^ 0x43 = 0x01 → 1 bit
  assert.equal(sourcePairDistance(cleanSources[0], drifted), 1);
});

console.log(process.exitCode === 1 ? '\nFAIL' : '\nall green (7 tests)');
