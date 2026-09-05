<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Public experience v1 release evidence

Evidence is cumulative and layer-specific. A passing source test does not imply
merge, deployment, domain propagation, or external authority.

## Current source candidate

- Branch: `feat/holographic-front-door-v1-20260904`
- Taxonomy home for `a11oy_public_experience.py`: `services`
- Candidate commit: `UNCOMMITTED`
- Protected base: `origin/main` reconciliation pending
- Pull request: `NOT_OPEN`

## Local verification observed 2026-09-05

| Layer | Command | Result |
|---|---|---|
| Backend, frontend, and harness behavior | `python -B -m pytest -q tests/test_a11oy_public_experience.py tests/test_public_experience_frontend_v1.py tests/test_verify_public_experience.py` | `70 passed`, one Starlette deprecation warning |
| Source and config gate | `python -B scripts/verify_public_experience.py --repo . --strict` | `11 passed`, `0 failed` |
| Build-inclusive release gate | `python -B scripts/verify_public_experience.py --repo . --strict --run-build` | `15 passed`, `0 failed`; command output withheld by design |
| YAML parse and whitespace | `python -B -c "import yaml; ..."` and `git diff --check` | Passed |

These observations were made before rebasing onto the latest protected base and
must be repeated after conflict resolution.

## Browser evidence

- Desktop interaction: `NOT_RUN`
- Mobile interaction: `NOT_RUN`
- Keyboard and focus flow: `NOT_RUN`
- Reduced motion and 2D fallback: `NOT_RUN`
- Console errors: `NOT_RUN`
- Horizontal overflow: `NOT_RUN`
- Real performance timing: `NOT_MEASURED`

## Release evidence

- Signed candidate commit: `NOT_CREATED`
- Pull-request checks: `NOT_RUN`
- Merge revision: `NOT_MERGED`
- Canonical Space deploy run: `NOT_RUN`
- `szlholdings-a11oy.hf.space` build-info equality: `NOT_VERIFIED`
- Five live bounded simulations: `NOT_EXERCISED`
- `a-11-oy.com` currency and lifecycle: `NOT_VERIFIED`
- `a11oy.net`: intentionally unchanged; separate proof origin
- Flagship generator/runtime propagation: `NOT_VERIFIED`

The deploy workflow now contains a post-deploy public-experience job that runs
all five bounded simulations and uploads the redacted machine-readable report.
No approval capability or response body is persisted in that artifact.

## Rollback

Revert the public-experience merge commit through a protected pull request and
let the same single-writer `hf-sync.yml` workflow republish and source-bind the
previous Docker closure. Do not manually rewrite the Space, bypass the relock,
or alter DNS as a frontend rollback shortcut.
