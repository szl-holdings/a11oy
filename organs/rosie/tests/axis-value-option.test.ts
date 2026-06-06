/**
 * axis-value-option.test.ts — Brahmi-zero distinction tests (R4-I2).
 *
 * Run: node --experimental-strip-types tests/axis-value-option.test.ts
 */

import assert from 'node:assert/strict';
import {
  AXIS_ABSENT,
  measuredAxis,
  isAbsent,
  isMeasured,
  serializeAxis,
  parseAxis,
  axisEqual,
  lambdaGeomeanOption,
  type AxisValue,
} from '../src/axis-value-option.ts';

const results: Array<{ id: string; ok: boolean; detail?: string }> = [];

function test(id: string, fn: () => void) {
  try {
    fn();
    results.push({ id, ok: true });
  } catch (e) {
    results.push({ id, ok: false, detail: e instanceof Error ? e.message : String(e) });
  }
}

test('T_brahmi_measured_zero_ne_absent', () => {
  // The load-bearing distinction: measured(0) is NOT absent.
  const mz = measuredAxis(0);
  assert.ok(!axisEqual(mz, AXIS_ABSENT));
  assert.notEqual(serializeAxis(mz), serializeAxis(AXIS_ABSENT));
});

test('T_brahmi_predicates_dichotomy', () => {
  const m = measuredAxis(1.5);
  assert.equal(isMeasured(m), true);
  assert.equal(isAbsent(m), false);
  assert.equal(isMeasured(AXIS_ABSENT), false);
  assert.equal(isAbsent(AXIS_ABSENT), true);
});

test('T_brahmi_serialize_canonical', () => {
  assert.equal(serializeAxis(AXIS_ABSENT), 'A');
  assert.equal(serializeAxis(measuredAxis(0)), 'M:0');
  assert.equal(serializeAxis(measuredAxis(1.5)), 'M:1.5');
  assert.equal(serializeAxis(measuredAxis(-7)), 'M:-7');
});

test('T_brahmi_roundtrip_serialize_parse', () => {
  const cases: AxisValue[] = [
    AXIS_ABSENT,
    measuredAxis(0),
    measuredAxis(1),
    measuredAxis(-1.25),
    measuredAxis(1e10),
  ];
  for (const c of cases) {
    const round = parseAxis(serializeAxis(c));
    assert.ok(axisEqual(c, round), `roundtrip failed for ${serializeAxis(c)}`);
  }
});

test('T_brahmi_parse_rejects_malformed', () => {
  assert.throws(() => parseAxis(''), /malformed/);
  assert.throws(() => parseAxis('X'), /malformed/);
  assert.throws(() => parseAxis('M:nope'), /non-finite/);
});

test('T_brahmi_constructor_rejects_non_finite', () => {
  assert.throws(() => measuredAxis(Number.NaN), /non-finite/);
  assert.throws(() => measuredAxis(Number.POSITIVE_INFINITY), /non-finite/);
});

test('T_brahmi_geomean_skips_absent', () => {
  // Absent axes do NOT lower the geomean.
  const axes: AxisValue[] = [measuredAxis(4), AXIS_ABSENT, measuredAxis(9)];
  const g = lambdaGeomeanOption(axes);
  assert.ok(g !== null);
  assert.ok(Math.abs(g! - 6) < 1e-9, `geomean(4,9) = 6 expected, got ${g}`);
});

test('T_brahmi_geomean_zero_propagates_when_measured', () => {
  // measured(0) propagates to geomean 0 (not skipped).
  const axes: AxisValue[] = [measuredAxis(4), measuredAxis(0), measuredAxis(9)];
  assert.equal(lambdaGeomeanOption(axes), 0);
});

test('T_brahmi_geomean_all_absent_returns_null', () => {
  assert.equal(lambdaGeomeanOption([AXIS_ABSENT, AXIS_ABSENT]), null);
  assert.equal(lambdaGeomeanOption([]), null);
});

test('T_brahmi_freeze_absent_singleton', () => {
  // AXIS_ABSENT is frozen — receipts that reuse it cannot mutate it.
  assert.ok(Object.isFrozen(AXIS_ABSENT));
});

const failed = results.filter((r) => !r.ok);
for (const r of results) {
  console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.id}${r.detail ? '  — ' + r.detail : ''}`);
}
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length === 0 ? 0 : 1);
