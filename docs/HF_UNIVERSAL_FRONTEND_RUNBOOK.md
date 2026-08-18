# Hugging Face universal frontend rollout runbook

## Protected execution

1. Review the exact GitHub pull request containing the controller, tests, contract, and workflow.
2. Require the controller contract and public plan jobs to complete.
3. Merge through repository policy.
4. The protected `main` push creates revision-bound Hugging Face pull requests and merges only deterministic changes.
5. Download the immutable report and rollback-preimage artifact.
6. Use the deterministic blocker issue to route GitHub-source-bound or unsupported Spaces to their canonical repositories.
7. Repeat until the report is `complete: true`.

## Failure handling

- A changed Hub parent revision blocks that repository instead of overwriting newer work.
- An unsupported application shell receives no generic source rewrite.
- A GitHub-source-bound Space receives no direct Hub write.
- A card-only update is not treated as application-runtime verification.
- Any failed or blocked asset keeps the estate issue open and the rollout workflow red.

## Rollback

Every changed path is archived under the rollout artifact with its repository identity and source SHA. Restore through a new revision-bound Hugging Face pull request; do not force-push or rewrite Hub history.
