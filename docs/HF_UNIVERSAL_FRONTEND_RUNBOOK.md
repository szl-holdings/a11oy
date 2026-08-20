# Hugging Face universal frontend rollout runbook

## Protected source promotion

1. Review the exact GitHub pull request containing the controller, tests, contract, automatic read-only contract workflow, and manual rollout workflow.
2. Require the controller contract, repository test matrix, CodeQL, container, DCO, Doctrine, secret, vulnerability, and Hugging Face parity gates to complete at the exact head.
3. Merge through the normal protected squash path.
4. Do not treat the protected `main` push as rollout authorization. `hf-sync.yml` remains the sole automatic canonical Hugging Face writer.

## Owner-dispatched planning

1. Dispatch `HF universal frontend manual rollout` with `operation=plan` from the exact protected `main` revision.
2. Confirm the report names the tracked source-map path and SHA-256 digest from the exact checkout, then download the immutable plan and rollback-preimage index.
3. Review blocked, unsupported, and source-native assets. Planning performs no provider mutation, uses an anonymous public inventory, and needs no Hugging Face token. An `EXACT`, `INFERRED`, or `DIVERGENT` mapping must never appear in the direct Hub proposal set.

## Owner-dispatched execution

1. Dispatch the same workflow with `operation=execute` from exact current protected `main` only after reviewing the exact source and plan.
2. The execution job requires the managed organization token at runtime.
3. Supported Hub-native assets are changed only through revision-bound Hugging Face pull requests whose parent commits equal the observed Hub revisions. Direct Hub mutation is admissible only for a source-map `UNAVAILABLE` record whose Hub and README observations are bound to that same revision.
4. Confirm the report contains no private asset and treats created-but-unmerged pull requests as nonterminal.
5. Download the immutable rollout report and rollback-preimage artifact; issue synchronization is skipped if this upload fails.
6. Use the deterministic blocker issue to route unverified GitHub-source-bound or unsupported Spaces to their canonical repositories.
7. Repeat explicit owner dispatches until every asset is `CURRENT`, `MERGED` with immutable readback, or `SOURCE_BOUND_VERIFIED`, and the report is `complete: true`.

## Failure handling

- A changed Hub parent revision blocks that repository instead of overwriting newer work.
- An unsupported application shell receives no generic source rewrite.
- A GitHub-source-bound Space receives no direct Hub write and remains blocked until its public deployment/build source revision and running Space revision agree.
- A stale, missing, divergent, inferred, or revision-unbound source-map record denies direct Hub mutation. Repair and protect the source map or confirm/promote through the canonical source repository; do not bypass it with a manual Hub edit.
- Python application adapters preserve their legal preamble and reject generated source that does not parse.
- A card-only update is not treated as application-runtime verification.
- Any failed or blocked asset keeps the estate issue open and the owner-dispatched execution red.

## Rollback

Every changed path is archived under the rollout artifact with its repository identity and source SHA. Restore through a new revision-bound Hugging Face pull request; do not force-push or rewrite Hub history.
