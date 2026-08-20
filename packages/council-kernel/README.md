# A11oy Council Kernel

The Council is implemented as a deterministic authority kernel, not as one privileged language model.

Models and other advisers may submit assessments. They do not receive execution authority. The kernel owns capability checks, exact-target authorization, role coverage, categorical vetoes, correlation-aware diversity, decision state, minority reports, budgets, and receipts.

## Council roles

- **Authority** checks mandate, capability, target, and budget.
- **Sentinel** evaluates safety and may issue a categorical veto.
- **Verifier** evaluates evidence and postcondition feasibility and may issue a categorical veto.
- **Value** evaluates expected benefit, cost, and opportunity loss.

Every assessment is committed before reveal. A reveal is accepted only when its canonical payload and nonce match the prior commitment.

## Decision states

- `ACT` means the proposal passed capability, role, veto, evidence, diversity, risk, and score gates.
- `ESCALATE` means the evidence or independence threshold is not sufficient for autonomous action.
- `BLOCK` means authority is absent, an exact target is unauthorized, a categorical veto is present, a commitment is invalid, or policy requires denial.

The kernel preserves dissent and counterevidence in the decision record. Apparent agreement from correlated advisers is discounted across operator, key, model lineage, implementation, provider, retrieval path, evidence domain, and trust domain.

## Receipts and state

Decision and action records use canonical JSON and SHA-256 content identities. Hash-chain integrity and signature state are separate fields. An unsigned record is labeled `UNSIGNED`; a record is labeled `SIGNED` only when an injected signer produces a signature.

The included ledger can remain in memory or append JSON Lines to a caller-selected path. It verifies every previous-hash link and entry digest. Production key custody, durable transparency, external witnesses, and provider execution remain deployment concerns outside this package.

## Run the package tests

```bash
PYTHONPATH=packages/council-kernel/src \
  python -m unittest discover -s packages/council-kernel/tests -v
```

The package has no runtime dependency outside the Python standard library.

## Truth boundary

This directory is executable source and test coverage. Its presence in a branch does not establish protected-main promotion, external deployment, independent Council operators, managed signing keys, public transparency, model independence, or production autonomy.
