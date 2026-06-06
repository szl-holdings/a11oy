# Lutar Invariant Λ — Empirical Axiom Evidence

**Date:** 2026-05-02
**Repo:** szl-holdings/ouroboros
**File:** packages/ouroboros/src/lutar-invariant-proof.test.ts
**Total assertions:** 22
**Passed:** 22
**Failed:** 0

## Λ definition

Λ(x_1, ..., x_9; w_1, ..., w_9) = ∏ xᵢ^wᵢ — the weighted geometric mean of nine independent runtime-trust axis scores in [0, 1] under non-negative weights summing to 1.

## Axiom-level evidence

| Axiom | Tests | Passed | Failed | Status |
|---|---|---|---|---|
| A1 | 4 | 4 | 0 | demonstrated |
| A2 | 4 | 4 | 0 | demonstrated |
| A3 | 4 | 4 | 0 | demonstrated |
| A4 | 4 | 4 | 0 | demonstrated |
| Boundary / sanity | 6 | 6 | 0 | demonstrated |

## Per-test detail

### A1

- ✓ A1 — Monotonicity Λ is non-decreasing in each axis (equal weights)
- ✓ A1 — Monotonicity Λ is non-decreasing in each axis (Egyptian weights)
- ✓ A1 — Monotonicity Λ is non-increasing when any axis is lowered
- ✓ A1 — Monotonicity strict monotonicity when weight is positive

### A2

- ✓ A2 — Zero-pinning any single axis at 0 collapses Λ to 0
- ✓ A2 — Zero-pinning multiple axes at 0 still yield Λ = 0
- ✓ A2 — Zero-pinning Λ = 0 only when at least one axis with positive weight is 0
- ✓ A2 — Zero-pinning a zero-weight axis at 0 does NOT collapse Λ (definitional edge case)

### A3

- ✓ A3 — Egyptian inspectability the standard weight set is a sum of distinct unit fractions
- ✓ A3 — Egyptian inspectability weight set is bit-exact reproducible (rational reconstruction)
- ✓ A3 — Egyptian inspectability Λ under Egyptian weights matches a rational evaluator on rational inputs
- ✓ A3 — Egyptian inspectability the equal-weight set 9 × (1/9) is also a valid Egyptian decomposition

### A4

- ✓ A4 — Page-curve concavity concavity along a line segment in [ε, 1]^9
- ✓ A4 — Page-curve concavity concavity on a stress segment (one axis varying, others held)
- ✓ A4 — Page-curve concavity Λ ≤ weighted arithmetic mean (AM–GM corollary)
- ✓ A4 — Page-curve concavity Λ achieves arithmetic mean iff all axes equal (corollary)

### Boundary

- ✓ Boundary and sanity Λ(perfect) = 1
- ✓ Boundary and sanity Λ(typical) ≈ 0.7
- ✓ Boundary and sanity Λ(degraded with one axis at 0.1) drops below arithmetic mean
- ✓ Boundary and sanity Λ is symmetric under axis permutation when weights are uniform
- ✓ Boundary and sanity axes are labeled as the thesis declares
- ✓ Boundary and sanity weights sum to 1 (both standard sets)

## What this evidence does and does not establish

**Establishes:** the closed-form Λ = ∏ xᵢ^wᵢ, evaluated in IEEE-754 double precision, satisfies its four axioms (monotonicity, zero-pinning, Egyptian inspectability, Page-curve concavity) on the test points exercised above.

**Does not establish:** that any specific runtime configuration in production has been audited, that any third-party body has reviewed this work, that the runtime is deployed in any product. The runtime is open-source under the licenses declared in this repository. Empire APEX (administered by NYSTEC) is a procurement-counseling resource the founder engaged with on 2026-04-30; it is not an audit.

**Reproduce:**

```bash
pnpm install
npx vitest run packages/ouroboros/src/lutar-invariant-proof.test.ts
```

