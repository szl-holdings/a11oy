/**
 * a11oy-povm.ts — POVM verdict semantics for governance
 * Organ: a11oy (BRAIN / GOVERNANCE CORTEX)
 *
 * STATUS: TUTORIAL FIXTURE — runnable copy for the recipe smoke tests.
 *   The CANONICAL implementation is:
 *     a11oy/web/packages/a11oy-core/src/quantum/povm.ts
 *
 * Source: Preskill (2015) Ch. 3; Davies & Lewis (1970); R08 quantum_bohr_povm.ts
 *         Lean theorem: povm_completeness (lutar-lean/Lutar/Quantum/POVM.lean)
 * Author: Stephen P. Lutar Jr., SZL Holdings
 */

export interface POVMElement {
  id: string;
  label: string;
  probability: number;   // p(m) = tr(ρ E_m)
  operator: number[][];  // E_m — 2×2 positive semidefinite matrix
}

export interface POVM {
  elements: POVMElement[];
  isComplete: boolean;  // Σ_m E_m = I (verified at construction)
}

export interface POVMVerdict {
  outcome: string;
  probability: number;
  confidence: number;
}

/** Build a canonical 3-outcome policy POVM (accept/abstain/reject)
 *  E_ACCEPT  = α·|0⟩⟨0|
 *  E_REJECT  = β·|1⟩⟨1|
 *  E_ABSTAIN = I − E_ACCEPT − E_REJECT  = diag(1-α, 1-β)
 *  Σ E_m = I  ✓
 */
export function buildCanonicalPolicyPOVM(alpha: number, beta: number): POVM {
  if (alpha < 0 || alpha > 1) throw new Error("α must be in [0,1]");
  if (beta < 0 || beta > 1) throw new Error("β must be in [0,1]");
  const elements: POVMElement[] = [
    {
      id: "ACCEPT", label: "Accept",
      probability: alpha,
      operator: [[alpha, 0], [0, 0]],
    },
    {
      id: "ABSTAIN", label: "Abstain",
      probability: (1 - alpha) + (1 - beta) - 1, // tr(E_ABSTAIN) / 2 not meaningful here
      operator: [[1 - alpha, 0], [0, 1 - beta]],
    },
    {
      id: "REJECT", label: "Reject",
      probability: beta,
      operator: [[0, 0], [0, beta]],
    },
  ];
  return { elements, isComplete: verifyPOVMCompleteness(elements) };
}

/** Verify completeness: Σ_m E_m = I */
export function verifyPOVMCompleteness(elements: POVMElement[]): boolean {
  const n = 2;
  const sum = Array.from({ length: n }, () => Array(n).fill(0));
  for (const el of elements) {
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        sum[i][j] += el.operator[i][j];
      }
    }
  }
  const tol = 1e-9;
  return Math.abs(sum[0][0] - 1) < tol && Math.abs(sum[1][1] - 1) < tol &&
         Math.abs(sum[0][1]) < tol && Math.abs(sum[1][0]) < tol;
}

/** Apply POVM to a density matrix ρ and return verdicts */
export function applyPOVM(povm: POVM, rho: number[][]): POVMVerdict[] {
  return povm.elements.map(el => {
    // p(m) = tr(ρ E_m) = Σ_ij ρ_ij (E_m)_ji
    let p = 0;
    for (let i = 0; i < 2; i++) {
      for (let j = 0; j < 2; j++) {
        p += rho[i][j] * el.operator[j][i];
      }
    }
    return { outcome: el.id, probability: Math.max(0, Math.min(1, p)), confidence: p };
  });
}

// ─── Usage Example ────────────────────────────────────────────────────────────
/*
const povm = buildCanonicalPolicyPOVM(0.7, 0.2);
console.log("POVM complete:", povm.isComplete); // true
const rho = [[0.9, 0.1], [0.1, 0.1]]; // mixed state
const verdicts = applyPOVM(povm, rho);
verdicts.forEach(v => console.log(v.outcome, v.probability.toFixed(3)));
*/