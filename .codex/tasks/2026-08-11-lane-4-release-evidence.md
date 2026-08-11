# Lane 4 — Release Identity, Evidence, and Control-Plane Wiring

## Mission

Make the release and evidence control plane mechanically consistent from source commit through build, publication, deployment, verification, rollback, and public truth surfaces. This lane does not duplicate Lane 1's deployment work or Lane 2's content redesign; it fixes the contracts, identities, receipts, and automation that let those lanes prove their outcomes.

## Required identity model

Define and enforce one explicit immutable tuple with separate fields for:

- GitHub repository and protected source commit;
- build workflow/run and build subject digest;
- container/image or Space build identity;
- Hugging Face repository revision;
- deployed runtime revision reported by `/api/build-info`;
- release/tag/version identity;
- model/tokenizer/adapter/runtime/hardware identity when applicable;
- evidence signer, trust root, scope, issued time, and evidence digest.

Never overload one SHA field to mean several different systems. Unknown or unconfigured identities remain `UNOBSERVED` or `BLOCKED`, not empty strings, zero digests, or inferred equality.

## Required work

1. Audit release, readiness, relock, deployment, SBOM, provenance, alert, rollback, restore, and incident workflows at exact current `main`.
2. Remove stale assumptions such as pinned historical source SHAs, fake sentinel values, self-trusting embedded public keys, mutable aliases, or readiness copied from documentation.
3. Make the final decision validator require the exact expected gate inventory with no missing, duplicate, or extra gates.
4. Bind evidence to exact source, workflow generation, body/config digest, environment, and scope.
5. Preserve external trust-root requirements; local ephemeral qualification signatures must never authorize production.
6. Ensure source, image/Space, deployment, and public-readback receipts are retained with deterministic digests and privacy-safe summaries.
7. Ensure canary, restart, restore, rollback, alert retry, and tamper-negative tests exist and fail closed.
8. Reconcile public README, investor/proof surfaces, `/honest`, `/version`, `/readiness`, and release evidence so they cannot contradict current observed state.
9. Do not promote Nemo, adapters, Mooncake/LMCache, GPU fleets, or measured-energy claims without their own actual topology and hardware evidence.

## Required automation behavior

- A protected merge may trigger deployment, but the deployment must still prove exact merged-source identity.
- A successful deployment must not close a release issue until live readback and negative verification pass.
- Main movement during a run must retarget or invalidate stale evidence.
- Missing secret-manager, signer, registry, Hugging Face, GPU, or production authority must produce an exact blocker without exposing credential values.
- Public evidence must be reproducible from retained artifacts and immutable refs.

## Acceptance criteria

```text
source_identity_ambiguity == 0
release_gate_inventory_mismatch == 0
self_asserted_production_trust == 0
mutable_production_identity == 0
public_truth_contradiction_count == 0
stale_pinned_source_assumption_count == 0
receipt_tamper_negative_tests == PASS
rollback_restore_alert_drills == PASS or explicitly BLOCKED_EXTERNAL_AUTHORITY
completion_claim_without_live_readback == 0
```

## Deliverable

Create signed+DCO PRs from exact current protected source. Coordinate file ownership with the other lanes to avoid branch conflicts. Run contract, security, provenance, restore/rollback, and public-truth tests. Finish with exact PRs and merge SHAs, evidence schemas, gate inventory, workflow/artifact IDs, trust-root state, live-readback evidence, and every external blocker.
