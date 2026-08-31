/**
 * rx-unitarity.test.ts — DARUAN Rx gate unitarity verification
 *
 * Failure mode this catches: a sign error in the Rx implementation can leave
 * the gate non-unitary, breaking the boundedness guarantee documented in
 * Nielsen & Chuang 2010 §4.2 eq. 4.4. The 25/25 cookbook smoke suite tests
 * only that DARUAN runs end-to-end; it does not verify U†U = I or
 * |α|² + |β|² = 1 across random angles.
 *
 * Reference: Nielsen, M. A. & Chuang, I. L. (2010). Quantum Computation and
 *   Quantum Information, §4.2.
 */

import { rx, rz, type QubitState } from "../qkan-fwp";

function norm2(s: QubitState): number {
  return (
    s.alpha[0] * s.alpha[0] +
    s.alpha[1] * s.alpha[1] +
    s.beta[0] * s.beta[0] +
    s.beta[1] * s.beta[1]
  );
}

function randAngle(): number {
  return (Math.random() - 0.5) * 4 * Math.PI;
}

function randState(): QubitState {
  const a0 = Math.random() - 0.5;
  const a1 = Math.random() - 0.5;
  const b0 = Math.random() - 0.5;
  const b1 = Math.random() - 0.5;
  const n = Math.sqrt(a0 * a0 + a1 * a1 + b0 * b0 + b1 * b1);
  return { alpha: [a0 / n, a1 / n], beta: [b0 / n, b1 / n] };
}

const TOL = 1e-10;

function assertClose(actual: number, expected: number, tol: number, msg: string): void {
  if (Math.abs(actual - expected) > tol) {
    throw new Error(`${msg}: |${actual} - ${expected}| = ${Math.abs(actual - expected)} > ${tol}`);
  }
}

// 100 random angles × random initial states — norm must be preserved exactly.
for (let trial = 0; trial < 100; trial++) {
  const psi = randState();
  const theta = randAngle();
  const phi = randAngle();

  const afterRx = rx(psi, theta);
  assertClose(norm2(afterRx), 1, TOL, `Rx norm preservation, trial ${trial}`);

  const afterRz = rz(psi, phi);
  assertClose(norm2(afterRz), 1, TOL, `Rz norm preservation, trial ${trial}`);

  // Rx(θ) Rx(-θ) = I (Rx is its own inverse with negated angle)
  const round = rx(rx(psi, theta), -theta);
  assertClose(round.alpha[0], psi.alpha[0], TOL, `Rx round-trip α_re, trial ${trial}`);
  assertClose(round.alpha[1], psi.alpha[1], TOL, `Rx round-trip α_im, trial ${trial}`);
  assertClose(round.beta[0], psi.beta[0], TOL, `Rx round-trip β_re, trial ${trial}`);
  assertClose(round.beta[1], psi.beta[1], TOL, `Rx round-trip β_im, trial ${trial}`);
}

// Repeated application — 1000 random rotations must not drift the norm.
let state: QubitState = { alpha: [1, 0], beta: [0, 0] };
for (let i = 0; i < 1000; i++) {
  state = rx(state, randAngle());
  state = rz(state, randAngle());
}
assertClose(norm2(state), 1, 1e-8, "norm drift after 1000 rotations");

console.log("PASS: Rx/Rz unitarity verified across 100 random states + 1000-step drift test");
