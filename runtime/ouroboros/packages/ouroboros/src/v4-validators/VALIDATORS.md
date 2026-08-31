# v4 Validator Functions — Codex-Aligned Semantics

This document maps each rule declared in `VALIDATOR_REGISTRY`
(`packages/ouroboros/src/validator-registry.ts`) to the runnable function
that realises it (`packages/ouroboros/src/v4-validators/validators.ts`).

These are **policy gate validators**, not Λ axis scores. Each returns a
`ValidatorResult { passed, note? }`. Aggregation is handled by the
existing `summarizeValidators`: any failed `error`-severity validator
halts the run.

All semantics are derived from material already in the repository —
the `rule` text in the registry, the ingestion contract requirements
(`runtime-contract.v4.test.ts`), and the v3/v4/v6 runtime contracts
(`docs/research/`). No new policy was invented.

## The 9 validators

| # | Validator id | Pass when | Fail when |
|---|---|---|---|
| 1 | `VAL_BUDGET_ENFORCER` | Tokens, steps, and elapsed-time are all under their respective ceilings (or unset) | Any usage exceeds its declared ceiling |
| 2 | `VAL_NO_SILENT_MUTATION` | Every recorded mutation has `recordedInTrace: true` | Any mutation has `recordedInTrace: false` |
| 3 | `VAL_PROOF_REQUIRED` | Either the run is not proof-bound, or the proof route was resolved | Run is proof-bound and the proof route was not resolved |
| 4 | `VAL_RISK_ESCALATION` | Tier below threshold, or escalated, or halted | Tier ≥ threshold and the run neither escalated nor halted |
| 5 | `VAL_APPROVAL_FOR_CRITICAL_ACTION` | Not a critical action, or approval required+granted | Critical action with no approval, no `required` flag, or `granted: false` |
| 6 | `VAL_SECURITY_PROOF_REQUIRED` | No security conclusion present, or evidence count > 0 | Security conclusion present with zero evidence artifacts |
| 7 | `VAL_SOURCE_PRIORITY_REQUIRED` | Not a data-convergence run, or every source has a numeric `precedenceRank` | Data-convergence run with zero sources, or any source missing precedenceRank |
| 8 | `VAL_MERGE_SAFETY` | No unsafe merge actions, or the run escalated or halted | Unsafe merge action(s) without escalation or halt |
| 9 | `VAL_CONSISTENCY_BEFORE_COMMIT` | Not an Amaru finalize, or `metric ≥ threshold` | Amaru finalize with no snapshot or `metric < threshold` |

## Composition with ingestion contracts

The Sentra and Amaru ingestion contracts in `INGESTION_CONTRACTS`
already declare which validator subsets they require:

- **Sentra** (`security_recursive_review`): `VAL_RISK_ESCALATION`,
  `VAL_SECURITY_PROOF_REQUIRED`, `VAL_APPROVAL_FOR_CRITICAL_ACTION`
- **Amaru** (`convergent_data_runtime`): `VAL_SOURCE_PRIORITY_REQUIRED`,
  `VAL_MERGE_SAFETY`, `VAL_CONSISTENCY_BEFORE_COMMIT`

`runValidators(ctx, INGESTION_CONTRACTS.Sentra.requiredValidators)`
runs only the Sentra subset. The integration test
`v4-validators-integration.test.ts` exercises both profiles end-to-end.

## Design principles

1. **Pure functions.** No side effects, no I/O, deterministic.
2. **Optional inputs.** A validator whose preconditions are absent
   passes (vacuous truth) — failure is reserved for material rule
   violation.
3. **Explicit failure notes.** Every `passed: false` carries a `note`
   that names the breach and (where applicable) the offending value.
4. **Replay-stable.** Same context → same result. Validators participate
   in append-only traces by virtue of their determinism.
5. **No new policy.** Each function realises a rule already declared in
   the registry. Adding behaviour beyond the registered rule is a v5
   discussion, not a v4 implementation detail.
