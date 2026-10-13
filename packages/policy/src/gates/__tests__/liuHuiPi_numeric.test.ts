import assert from "node:assert/strict";
import { liuHuiPi } from "../../../../../runtime/ouroboros/agentic/formulas/src/liuHuiPi.ts";
import { liuHuiPiGate } from "../liuHuiPi_gate.ts";

// Truncated 80-digit values of the rationalized real recurrence.
// The bound is float64 agreement with that reference, not a proof that
// the real sequence converges to pi.
const reference: Record<number, number> = {
  0: 3,
  4: 3.1410319508905096381113529264596601070364,
  12: 3.1415926450336908966721415089192384127226,
  24: 3.141592653589792728479202222288057457376,
  27: 3.1415926535897932304941521151390111674024,
  50: 3.1415926535897932384626433832793896451255,
};

for (const [rawK, ref] of Object.entries(reference)) {
  const k = Number(rawK);
  const formula = liuHuiPi({ k });
  const gate = liuHuiPiGate({ threshold: 1 })({ k });
  assert.notEqual(formula.piEstimate, 0, `formula collapsed at k=${k}`);
  assert.ok(formula.sideSquared > 0 && formula.sideSquared <= 4, `sideSquared at k=${k}`);
  assert.ok(Math.abs(formula.piEstimate - ref) < 1e-15, `formula reference k=${k}`);
  assert.equal(gate.piEstimate, formula.piEstimate, `gate drifted from formula at k=${k}`);
  assert.equal(gate.absError, formula.absError, `gate residual drifted at k=${k}`);
  assert.match(gate.rationale, /does not identify it with π/);
  assert.equal(gate.leanTheorem, "sideSquared_bounds");
}

const early = liuHuiPiGate({ threshold: 1e-12 })({ k: 12 });
assert.equal(early.allow, false);
assert.ok(early.absError > 1e-12);

const late = liuHuiPiGate({ threshold: 1e-12 })({ k: 27 });
assert.equal(late.allow, true);
assert.ok(late.absError < 1e-12);
assert.notEqual(late.piEstimate, 0);

assert.throws(() => liuHuiPi({ k: 51 }), /supported domain/);
assert.throws(() => liuHuiPi({ k: 1.5 }), /non-negative integer/);
assert.throws(() => liuHuiPiGate()({ k: true as unknown as number }), /k must be in/);
