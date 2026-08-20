// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Unit tests for G36–G40 formula extension gates (Doctrine v6).
//
// G37 VCGTruthfulness is STAGED-ADVISORY: enforced=false by default.
// All tests exercise factory-pattern gates via (input) => GateResult.
//
// Lean commit anchor: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
// lutar-lean PR companion: szl-holdings/lutar-lean#116

import assert from "node:assert/strict";
import {
  gaussianMechanismDPGate,
  vcgTruthfulnessGate,
  rdpCompositionGate,
  certifiedRobustnessGate,
  reedSolomonSingletonGate,
} from "../index.ts";

const LEAN_COMMIT = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

function assertLeanAnchor(decision: {
  leanCommitSha: string;
  rationale: string;
  leanFile: string;
}): void {
  assert.equal(decision.leanCommitSha, LEAN_COMMIT);
  assert.match(decision.rationale, /Lean:/);
  assert.match(decision.leanFile, /^Lutar\//);
}

function assertDsseExtensionPresent(ext: object): void {
  assert.ok(typeof ext === "object" && ext !== null, "dsse_extension must be an object");
}

// ──────────────────────────────────────────────────────────────────────────────
// G36 GaussianMechanismDP
// σ_min = Δ₂f · √(2 · ln(1.25/δ)) / ε
// ──────────────────────────────────────────────────────────────────────────────

{
  // Pass: σ_claimed (10.0) ≥ σ_required (~7.55 for Δ₂f=1, ε=0.5, δ=1e-3)
  const gate = gaussianMechanismDPGate({});
  const allow = gate({
    dp_epsilon:      0.5,
    dp_delta:        1e-3,
    l2_sensitivity:  1.0,
    sigma_claimed:   10.0,
  });
  assert.equal(allow.allow, true);
  assert.equal(allow.dp_calibration_valid, true);
  assert.ok(allow.sigma_claimed >= allow.sigma_required);
  assertLeanAnchor(allow);
  assertDsseExtensionPresent(allow.dsse_extension);
  assert.equal(typeof allow.dsse_extension.dp.epsilon, "number");
  assert.equal(typeof allow.dsse_extension.dp.lean_theorem_sha, "string");
}

{
  // Fail: σ_claimed (5.0) < σ_required (~7.55 for Δ₂f=1, ε=0.5, δ=1e-3)
  const gate = gaussianMechanismDPGate({});
  const deny = gate({
    dp_epsilon:      0.5,
    dp_delta:        1e-3,
    l2_sensitivity:  1.0,
    sigma_claimed:   5.0,
  });
  assert.equal(deny.allow, false);
  assert.equal(deny.dp_calibration_valid, false);
  assert.ok(deny.sigma_claimed < deny.sigma_required);
  assertLeanAnchor(deny);
  assert.match(deny.rationale, /DENY/);
}

{
  // Fail: delta exceeds configured maxDelta
  const gate = gaussianMechanismDPGate({ maxDelta: 1e-6 });
  const deny = gate({
    dp_epsilon:      0.5,
    dp_delta:        1e-3,
    l2_sensitivity:  1.0,
    sigma_claimed:   100.0,
  });
  assert.equal(deny.allow, false);
  assert.match(deny.rationale, /maxDelta/);
}

{
  // Throw: invalid epsilon (out of range)
  const gate = gaussianMechanismDPGate({});
  assert.throws(
    () => gate({ dp_epsilon: 0, dp_delta: 1e-5, l2_sensitivity: 1, sigma_claimed: 5 }),
    /dp_epsilon must be in/
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// G37 VCGTruthfulness — STAGED-ADVISORY (enforced=false by default)
// p_i = max_{x} Σ_{j≠i} v_j(x) − Σ_{j≠i} v_j(x*)
// ──────────────────────────────────────────────────────────────────────────────

{
  // Pass: correct VCG payments declared — advisory mode, allow=true always
  const gate = vcgTruthfulnessGate({ paymentTolerance: 1e-9 });
  const outcomes = ["o1", "o2"];
  // A: values o1=10, o2=2 | B: values o1=6, o2=8
  // x* = o1 (SW=16 vs 10), Clarke payments:
  //   p_A = max(6,8) - 6 = 2, p_B = max(10,2) - 10 = 0
  const allow = gate({
    outcomes,
    attester_valuations: [
      { attester_id: "A", valuations: { o1: 10, o2: 2 } },
      { attester_id: "B", valuations: { o1: 6,  o2: 8 } },
    ],
    declared_payments: { A: 2, B: 0 },
  });
  assert.equal(allow.allow, true);
  assert.equal(allow.is_advisory, true);
  assert.equal(allow.vcg_truthfulness_valid, true);
  assert.equal(allow.vcg_outcome, "o1");
  assertLeanAnchor(allow);
  assertDsseExtensionPresent(allow.dsse_extension);
  assert.equal(allow.dsse_extension.mechanism_design.mechanism_type, "VCG");
}

{
  // Advisory: wrong payments declared — still allow=true (STAGED), but vcg_truthfulness_valid=false
  const gate = vcgTruthfulnessGate({ paymentTolerance: 1e-9 });
  const advisory = gate({
    outcomes: ["o1", "o2"],
    attester_valuations: [
      { attester_id: "A", valuations: { o1: 10, o2: 2 } },
      { attester_id: "B", valuations: { o1: 6,  o2: 8 } },
    ],
    declared_payments: { A: 99, B: 99 }, // wrong
  });
  assert.equal(advisory.allow, true);          // STAGED → still passes
  assert.equal(advisory.is_advisory, true);
  assert.equal(advisory.vcg_truthfulness_valid, false);
  assert.ok(advisory.payment_errors.length > 0);
  assert.match(advisory.rationale, /ADVISORY/);
}

{
  // Enforced mode: wrong payments → deny
  const gate = vcgTruthfulnessGate({ enforced: true });
  const deny = gate({
    outcomes: ["o1", "o2"],
    attester_valuations: [
      { attester_id: "A", valuations: { o1: 10, o2: 2 } },
      { attester_id: "B", valuations: { o1: 6,  o2: 8 } },
    ],
    declared_payments: { A: 999, B: 999 },
  });
  assert.equal(deny.allow, false);
  assert.equal(deny.is_advisory, false);
}

// ──────────────────────────────────────────────────────────────────────────────
// G38 RDPSequentialComposition
// ε_dp = Σᵢ εᵢ + ln(1/δ) / (α − 1)
// ──────────────────────────────────────────────────────────────────────────────

{
  // Pass: total ε_dp within budget
  const gate = rdpCompositionGate({});
  const allow = gate({
    rdp_alpha:                8.0,
    rdp_epsilon_steps:        [0.5, 0.5, 0.5],
    dp_delta:                 1e-5,
    budget_epsilon_threshold: 10.0,
  });
  assert.equal(allow.allow, true);
  assert.equal(allow.rdp_budget_valid, true);
  assert.equal(allow.step_count, 3);
  assert.ok(Math.abs(allow.rdp_epsilon_total - 1.5) < 1e-9);
  assert.ok(allow.dp_epsilon_converted <= 10.0);
  assertLeanAnchor(allow);
  assertDsseExtensionPresent(allow.dsse_extension);
  assert.equal(allow.dsse_extension.rdp_accounting.alpha, 8.0);
}

{
  // Fail: total ε_dp exceeds tight budget
  const gate = rdpCompositionGate({});
  const deny = gate({
    rdp_alpha:                2.0,
    rdp_epsilon_steps:        [1.0, 1.0, 1.0, 1.0, 1.0], // ε_total=5
    dp_delta:                 1e-5,
    budget_epsilon_threshold: 3.0,
    // ε_dp = 5 + ln(1e5)/(2-1) = 5 + 11.51 = 16.51 >> 3
  });
  assert.equal(deny.allow, false);
  assert.equal(deny.rdp_budget_valid, false);
  assert.match(deny.rationale, /DENY/);
}

{
  // Throw: invalid alpha ≤ 1
  const gate = rdpCompositionGate({});
  assert.throws(
    () => gate({ rdp_alpha: 1.0, rdp_epsilon_steps: [0.1], dp_delta: 1e-5, budget_epsilon_threshold: 5 }),
    /rdp_alpha must be > 1/
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// G39 CertifiedRobustnessRadius
// R = (σ/2) · (Φ⁻¹(p̄_A) − Φ⁻¹(p̄_B))
// ──────────────────────────────────────────────────────────────────────────────

{
  // Pass: radius > 0 with reasonable smoothing sigma
  const gate = certifiedRobustnessGate({ minSafetyRadius: 0.1 });
  const allow = gate({
    smoothing_sigma: 1.0,
    p_A_lower:       0.9,
    p_B_upper:       0.05,
  });
  assert.equal(allow.allow, true);
  assert.equal(allow.radius_sufficient, true);
  assert.ok(allow.certified_radius > 0);
  assertLeanAnchor(allow);
  assertDsseExtensionPresent(allow.dsse_extension);
  assert.equal(
    typeof allow.dsse_extension.certified_robustness.certified_radius,
    "number"
  );
}

{
  // Fail: radius < minSafetyRadius (tiny sigma, marginal probabilities)
  const gate = certifiedRobustnessGate({ minSafetyRadius: 5.0 });
  const deny = gate({
    smoothing_sigma: 0.1,
    p_A_lower:       0.51,
    p_B_upper:       0.49,
  });
  // R ≈ (0.1/2) * (Φ⁻¹(0.51) - Φ⁻¹(0.49)) ≈ very small
  assert.equal(deny.allow, false);
  assert.equal(deny.radius_sufficient, false);
  assert.match(deny.rationale, /DENY/);
}

{
  // Throw: p_A_lower must be in (0.5, 1)
  const gate = certifiedRobustnessGate({});
  assert.throws(
    () => gate({ smoothing_sigma: 1.0, p_A_lower: 0.4, p_B_upper: 0.1 }),
    /p_A_lower must be in/
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// G40 ReedSolomonSingletonBound
// d = n − k + 1 (MDS); t_era ≤ n − k
// ──────────────────────────────────────────────────────────────────────────────

{
  // Pass: RS(7,3,5)_251 — standard RS code, 7-3+1=5, claim t=4 ≤ 4
  const gate = reedSolomonSingletonGate({});
  const allow = gate({
    rs_n: 7,
    rs_k: 3,
    rs_d: 5,
    rs_q: 251,
    claimed_erasure_capacity: 4,
  });
  assert.equal(allow.allow, true);
  assert.equal(allow.is_mds, true);
  assert.equal(allow.singleton_bound, 5);
  assert.equal(allow.erasure_correction_capacity, 4);
  assert.equal(allow.error_correction_capacity, 2);
  assertLeanAnchor(allow);
  assertDsseExtensionPresent(allow.dsse_extension);
  assert.equal(allow.dsse_extension.erasure_coding.scheme, "Reed-Solomon");
}

{
  // Fail: claimed erasure capacity exceeds n-k
  const gate = reedSolomonSingletonGate({});
  const deny = gate({
    rs_n: 7,
    rs_k: 3,
    rs_d: 5,
    rs_q: 251,
    claimed_erasure_capacity: 5, // > n-k = 4
  });
  assert.equal(deny.allow, false);
  assert.ok(deny.failures.some((f) => f.includes("claimed_erasure_capacity")));
}

{
  // Fail: d ≠ n-k+1 (not MDS)
  const gate = reedSolomonSingletonGate({ requireMDS: true });
  const deny = gate({
    rs_n: 10,
    rs_k: 4,
    rs_d: 5,  // should be 7
    rs_q: 251,
    claimed_erasure_capacity: 3,
  });
  assert.equal(deny.allow, false);
  assert.ok(deny.failures.some((f) => f.includes("not an MDS code")));
}

{
  // Fail: n > q (invalid RS field parameter)
  const gate = reedSolomonSingletonGate({});
  const deny = gate({
    rs_n: 300,
    rs_k: 150,
    rs_d: 151,
    rs_q: 251, // 300 > 251
    claimed_erasure_capacity: 149,
  });
  assert.equal(deny.allow, false);
  assert.ok(deny.failures.some((f) => f.includes("field size")));
}

console.log(
  "G36–G40 formula extension gate tests passed (15 assertions in 5 groups). " +
  "G37 VCGTruthfulness: STAGED-ADVISORY — enforced=false by default."
);
