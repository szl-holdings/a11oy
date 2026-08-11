<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# A11oy Codex control surface

This directory contains the repository-owned, reviewable runner for the A11oy lane of the canonical whole-thread workcell in `szl-holdings/.github#415`.

- `prompts/a11oy-finish-build-v1.md` is the fixed prompt.
- `a11oy-finish-build-task-v1.json` is the machine-readable contract.
- `a11oy-finish-build-output.schema.json` constrains the terminal result.
- `a11oy-github-snapshot-v1.py` captures bounded GitHub and public-surface evidence without secret values.
- `a11oy-run-gates-v1.sh` runs deterministic repository gates after Codex.
- `a11oy-secret-diff-scan-v1.py` rejects high-confidence credential material in changed lines.
- `a11oy-action-pin-scan-v1.py` rejects mutable external Action references in changed workflows.

## Invocation

The trusted workflow can be started manually, or by the exact owner-authored comment `/codex-finish whole-thread` on issue `#1266`.

The trigger comment is not prompt input. The workflow checks out protected `main`, records the exact base SHA, installs lockfile dependencies before Codex's no-network phase, runs Codex in a workspace-only sandbox, runs repository gates without provider credentials, then creates a non-protected pull request.

## Managed prerequisite

`OPENAI_API_KEY` must exist as a GitHub Actions secret. The workflow checks only whether the secret is present; it never prints or persists the value. A missing secret ends as `BLOCKED_MANAGED_PREREQUISITE`.

## Authority boundary

The runner may write source only to a new A11oy feature branch. It does not merge, deploy, mutate Hugging Face, mutate a database, change rulesets, or act in another repository.
