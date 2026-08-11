# Production activation

Local success must not be promoted to production truth. A3/A4 autonomy requires all gates below to bind the same immutable source, policy, model/tool epochs, deployment revision, and action subject.

## Identity and independence

- Separate SPIFFE identities for Authority, Sentinel, Verifier, Value, aggregator, executor, witness, monitor, and projector.
- Separate managed signing keys with rotation and revocation evidence.
- At least the production policy minimums across operator, provider account, trust domain, implementation, model lineage, evidence domain, and retrieval path.
- Periodic correlation audit; aliases and shared upstream dependencies are disclosed.

## Durable orchestration

- Temporal or equivalent workflow history with deterministic replay.
- Provider-specific idempotency and ambiguous-attempt reconciliation.
- Checkpoint and recovery drills.
- Compensation and rollback proof for each production effector.
- Stop-loss and kill-switch controls outside model authority.

## Policy

- Reviewed OPA/Rego or equivalent policies.
- Root policy changes use a separate promotion council.
- Policy bundle signatures, exact revision, tests, and rollback.
- Human-owned exception path.

## Proof and transparency

- Persistent KMS/HSM signing authority.
- Durable SCITT-compatible transparency service.
- Public or partner-verifiable checkpoints.
- Independent monitor gossip, stale observation refusal, key-epoch replay, and portable fork evidence.
- Offline verifier and retention policy.

## Supply chain

- Immutable reviewed container base digest; the Dockerfile `PYTHON_IMAGE` argument must not remain a floating tag in production.
- Reproducible wheel/source archive, SBOM, dependency review, secret scan, and full-SHA GitHub Action pins.
- Signed provenance bound to the exact source tree and deployment digest.

## Execution and read-back

- Pre-action snapshot and exact target binding.
- Provider receipt plus independent postcondition probes.
- Negative tests for denied target, stale policy, revoked identity, duplicate idempotency key, excessive budget, and failed proof.
- External deployment digest read-back.
- Browser/API/mobile smoke and rollback drill.

## Statistical release gate

The included gate is empirical. A production calibrated gate needs:

- task/risk-stratified calibration data;
- explicit exchangeability or drift assumptions;
- false-green risk budget;
- holdout and transfer evaluation;
- coverage monitoring and recalibration triggers;
- role/field-level controls for high-risk tool arguments;
- fail-closed behavior when sample support is insufficient.

## Terminal status

Only a release capsule that verifies all external packets may state `OPERATIONAL_VERIFIED`. Otherwise the state remains `BLOCKED`, `PREAUTH_READY`, or `LOCAL_VERIFIED` with exact blockers.
