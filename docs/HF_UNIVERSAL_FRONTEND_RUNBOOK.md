# Hugging Face universal frontend rollout runbook

## Protected source promotion

1. Review the exact GitHub pull request containing the controller, tests, contract, automatic read-only contract workflow, and manual rollout workflow.
2. Require the controller contract, repository test matrix, CodeQL, container, DCO, Doctrine, secret, vulnerability, and Hugging Face parity gates to complete at the exact head.
3. Merge through the normal protected squash path.
4. Do not treat the protected `main` push as rollout authorization. `hf-sync.yml` remains the sole automatic canonical Hugging Face writer.
5. Require the immutable Space source map and both hash-locked universal-frontend requirement files to be present in the exact protected tree.

## Owner-dispatched planning

1. Dispatch `HF universal frontend manual rollout` with `operation=plan` only from `refs/heads/main`. A branch, tag, stale-main, or checkout mismatch is rejected.
2. Download the immutable plan and rollback-preimage index.
3. Confirm the report used an anonymous public inventory and `docs/huggingface-space-source-map-v1.json` from that exact protected revision.
4. Review missing, stale, inferred, divergent, unavailable, unsupported, and source-native assets. Planning performs no provider mutation, needs no Hugging Face token, and can never report estate completion.

## Owner-dispatched execution

1. Dispatch the same workflow with `operation=execute` from the exact current `refs/heads/main` only after reviewing the exact protected source and plan.
2. The execution job requires the managed organization token at runtime.
3. The workflow rechecks current main after checkout, before every provider create/merge, and before every issue write. Any advance requires a new plan and dispatch.
4. Supported model and dataset cards are changed only through revision-bound Hugging Face pull requests whose parent commits equal the observed Hub revisions. Spaces receive no direct Hub write in source-map v1.
5. Download the immutable rollout report and rollback-preimage artifact. Issue synchronization is skipped if upload fails. Require `MERGED_VERIFIED` plus exact changed-path hashes for every merged transaction.
6. Use the unique deterministic blocker issue to route source-bound or unresolved Spaces to canonical-source review. Multiple matching issues fail the run.
7. Repeat explicit owner dispatches until the report is completion-eligible and `complete: true`.

## Failure handling

- A changed Hub parent revision blocks that repository instead of overwriting newer work.
- A missing or stale immutable source map blocks the rollout.
- `EXACT`, `INFERRED`, `DIVERGENT`, and `UNAVAILABLE` Space mappings all prohibit direct Hub writes.
- An unsupported application shell receives no generic source rewrite; Python source-native adapters preserve legal preambles and reject generated code that does not parse.
- A GitHub-source-bound Space receives no direct Hub write.
- A card-only update is not treated as application-runtime verification.
- A missing, unchanged, or byte-mismatched post-merge readback is terminal.
- Any failed or blocked asset keeps the estate issue open and the owner-dispatched execution red.

## Rollback

Every changed path is archived under the rollout artifact with its repository identity and source SHA. Restore through a new revision-bound Hugging Face pull request; do not force-push or rewrite Hub history.
