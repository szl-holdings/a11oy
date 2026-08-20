# Delayed outcome learning

The Council does not treat execution as proof of success. A learning candidate is promotion-eligible only after a source-bound delayed outcome contract is evaluated.

## Outcome contracts

Each `OutcomeContract` binds:

- the exact Council decision digest;
- one metric and direction (`AT_LEAST`, `AT_MOST`, or `EQUAL`);
- baseline, target, and tolerance;
- an explicit deadline;
- required evidence references.

An `OutcomeObservation` binds its metric value, observation time, evidence references, completeness state, and source digest. Missing, incomplete, late, or source-unbound observations resolve to `PENDING` or `INCONCLUSIVE`; they cannot be promoted as success.

## Negative capability

`NegativeCapabilityLedger` records facts the system does not yet know. Each unknown has an immutable identifier, statement, evidence required for closure, opening time, expiry, and optional source decision.

A claim remains `OPEN` when evidence is incomplete. It becomes `EXPIRED`, not resolved, when evidence arrives after its bounded window. Claim identifiers cannot be rebound to different statements.

## Promotion

`OutcomeLearningGate` returns:

- `PENDING` before an outcome is terminal;
- `BLOCKED` when the target is not met, evidence is inconclusive, unknown claims remain, or policy findings remain;
- `ELIGIBLE` only when the outcome is met and all associated unknown and policy gates are closed.

Eligibility is not automatic model, prompt, policy, adapter, or weight promotion. It is a proof-carrying candidate for a separate governed promotion process.
