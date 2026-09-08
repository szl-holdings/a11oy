<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Brain Frontier refresh transaction

The scheduled reader materializes the existing 72 public metadata handles and runs
the focused validation suites with read-only repository access. Only the following
proposal job receives write permissions. It opens a review PR affecting
`console/assets/brain-frontier-v7.json`; it does not merge or publish to a provider.
The controller belongs to the supply-chain layer and does not serve a runtime route.

The branch name binds the first 16 hexadecimal characters of the full snapshot
digest. A pre-existing branch is usable only when its full snapshot digest, candidate
set, automation commit metadata, source ancestry and changed-file boundary match.
An orphan branch receives a PR. An existing open PR is reused only at the observed
head. An unmerged closed PR at that head is reopened and read back. An old branch can
advance using an ordinary push with both the old branch and current main as parents;
its resulting tree is exactly current main plus the snapshot. A concurrent push or
moving main is rechecked and cannot be reported as a successful stale proposal.

## Credential prerequisite

The proposal step accepts the optional repository secret `BRAIN_FRONTIER_PR_TOKEN`,
limited to `szl-holdings/a11oy` with Contents write and Pull requests write. A
fine-grained automation credential can supply this secret; configure its expiry and
renewal through the existing credential owner. No credential is printed or included
in the receipt. Administration read is optional for observing the Actions policy.
The controller never changes that policy.

Without that secret the workflow uses `GITHUB_TOKEN`, but refuses to push until the
repository policy can be read and explicitly allows Actions to create PRs. GitHub's
policy read endpoint requires Administration read, which the workflow token normally
cannot request. A missing observation is `UNAVAILABLE`, so a scoped automation
credential is the practical operational path. A repository setting alone does not
provide that read capability. Repository policy was observed as disabled on
2026-09-08; this dated observation is not a statement about future configuration.

Actions events created with an ordinary automation credential can trigger the PR
validation workflows. Events created with `GITHUB_TOKEN` normally do not trigger
another workflow. See GitHub's
[workflow permissions API](https://docs.github.com/en/rest/actions/permissions#get-default-workflow-permissions-for-a-repository)
and [workflow triggering rules](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow).

## Terminal evidence

Each run attempts to retain `brain-frontier-v7-refresh-<run>-<attempt>` before its
final outcome gate. A digest-valid unsigned receipt records the source SHA,
materialization result, snapshot and candidate-set digests, proposal state, PR URL
and observed head. It is workflow evidence, not an independent signature or proof of
deployment.

- `NO_CHANGE` requires successful materialization and validation.
- `REVIEW_PR_OPEN` requires an open PR at the observed branch head with every source
  and digest binding intact.
- `FAILED_CLOSED` includes missing inputs, blocked credentials, failed validation,
  stale main, a conflicting branch, failed PR creation, and failed readback.

An existing branch without a PR is never a successful terminal state. A receipt
upload failure also leaves the job failed. Workflow cancellation and runner loss can
prevent artifact retention; absence of a receipt remains missing evidence.

The offline suite uses temporary local Git repositories to verify ordinary branch
pushes, retries and preservation of newer main content. Run it with:

```sh
python -m pytest -q tests/test_brain_frontier_v7_refresh.py tests/test_brain_frontier_v7.py tests/test_brain_frontier_v7_surface.py
```
