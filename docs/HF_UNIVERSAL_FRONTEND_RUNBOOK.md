# Hugging Face universal frontend rollout runbook

## Protected source promotion

1. Review the exact GitHub pull request containing the controller, tests, contract, automatic read-only contract workflow, and manual rollout workflow.
2. Require the controller contract, repository test matrix, CodeQL, container, DCO, Doctrine, secret, vulnerability, and Hugging Face parity gates to complete at the exact head.
3. Merge through the normal protected squash path.
4. Do not treat the protected `main` push as rollout authorization. `hf-sync.yml` remains the sole automatic canonical Hugging Face writer.

## Owner-dispatched planning

1. Dispatch `HF universal frontend manual rollout` with `operation=plan` from the exact protected `main` revision.
2. Download the immutable plan and rollback-preimage index.
3. Review blocked, unsupported, and source-native assets. Planning performs no provider mutation and needs no Hugging Face token.

## Owner-dispatched execution

1. Dispatch the same workflow with `operation=execute` only after reviewing the exact protected source and plan.
2. The execution job requires the managed organization token at runtime.
3. Supported assets are changed only through revision-bound Hugging Face pull requests whose parent commits equal the observed Hub revisions.
4. Download the immutable rollout report and rollback-preimage artifact.
5. Use the deterministic blocker issue to route GitHub-source-bound or unsupported Spaces to their canonical repositories.
6. Repeat explicit owner dispatches until the report is `complete: true`.

## Failure handling

- A changed Hub parent revision blocks that repository instead of overwriting newer work.
- An unsupported application shell receives no generic source rewrite.
- A GitHub-source-bound Space receives no direct Hub write.
- A card-only update is not treated as application-runtime verification.
- Any failed or blocked asset keeps the estate issue open and the owner-dispatched execution red.

## Rollback

Every changed path is archived under the rollout artifact with its repository identity and source SHA. Restore through a new revision-bound Hugging Face pull request; do not force-push or rewrite Hub history.
