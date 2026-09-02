# Holographic Experience v2 dependency remediation

This record documents the fail-closed dependency repair performed while preparing the Holographic Experience v2 rollout.

## Remediated findings

| Component | Previous resolution | Remediated resolution | Evidence |
|---|---:|---:|---|
| `step-security/harden-runner` | `b09bb98e06d4d774595224525879c09bc6e98c40` | `bf7454d06d71f1098171f2acdf0cd4708d7b5920` (`v2.20.0`) | Both `hf-module-drift` jobs now use the estate-standard fixed commit. |
| `browserslist` | `4.28.2` | `4.28.7` | `package.json` constrains vulnerable releases through `4.28.6`; pnpm 10.26.1 regenerated the lockfile and its integrity hash. |

## Advisory boundary

- `GHSA-73wf-gq98-2v4g`: affected `browserslist <= 4.28.6`; patched in `4.28.7`.
- `GHSA-c83g-rgw3-j3cx`: affected `browserslist <= 4.28.6`; patched in `4.28.7`.
- The Harden-Runner pin now resolves beyond the advisories affecting the prior 2.15-era commit.

## Verification contract

The repository continues to fail closed on Grype findings at HIGH or CRITICAL severity. No scanner suppression, ignore rule, severity downgrade, or `continue-on-error` was added to the protected scan step. The next CI pass must independently rediscover the repository and return green before merge.

This file records source remediation only. It is not a claim that an external deployment, DNS route, or Hugging Face runtime is healthy.
