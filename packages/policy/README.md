# @szl-holdings/a11oy-policy

A11oy policy loader and Layer 6 formula gates.

## What is real today

- `policy_loader.ts` loads vertical governance policy YAML, validates it
  structurally and semantically, and emits a policy-load receipt.
- `src/gates/` exposes five executable Layer 6 formula gates:
  - `adversarialRobustnessGate`
  - `falsePositionGate`
  - `liuHuiPiGate`
  - `madhavaBoundGate`
  - `summationInvariantGate`
- `npm test --prefix packages/policy` runs all gate allow/deny/error path tests.

## What this is not

- Not a claim that every Lean theorem is closed.
- Not a replacement for `web/packages/a11oy-core`; this package is the policy
  boundary and formula-gate surface.
- Not a cryptographic signer. Receipts produced by the policy loader are local
  integrity records unless downstream signing is wired in.

