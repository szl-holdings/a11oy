<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Dependency security candidate, 2026-09-24

Base: `fe46a6da0dd14a158f56a86a3e1b24cc319ac02b`.
This is source maintenance, not a deployed-bundle or runtime remediation claim.

## Scope and cause

- Remove the unused `maplibre-gl` declaration from the mirrored `web/package.json`.
  That declaration allowed versions affected by
  [GHSA-jrc7-96c5-q579](https://github.com/advisories/GHSA-jrc7-96c5-q579).
  No mirrored web source imports that package. The actual `build:web` command
  uses `vendor/platform/artifacts/a11oy`, pinned to
  `6e0dc7b423fbcfb2c165348e60b41cd55a9b9ace`; its manifest and complete parent
  lockfile do not contain MapLibre. No submodule or deployed frontend changed.
- Restore Mermaid `^11.17.2`, the supported major before PR #2164.
  The declared Mermaid 12 dependency fails ordinary npm resolution because
  `vitepress-plugin-mermaid@2.0.17` declares peer support for `10 || 11`.
  The failure was reproduced with `npm ci --dry-run --ignore-scripts --no-audit
  --no-fund` against the unchanged base manifests. No force or legacy-peer
  exception was used.
- Pin all docs-site `lodash-es` resolutions to `4.18.1`, which was already the
  top-level locked version. The regenerated dependency closure removes three
  vulnerable nested `4.17.23` copies and the no-longer-needed Mermaid 12 parser
  chain. The override also prevents a transitive exact pin from reintroducing
  versions affected by
  [GHSA-r5fr-rjxr-66jc](https://github.com/advisories/GHSA-r5fr-rjxr-66jc).

## Local evidence

- Node `24.19.0`, npm `11.17.0`.
- Ordinary `npm install --package-lock-only --ignore-scripts --no-audit
  --no-fund`: passed; npm generated the lockfile.
- `npm audit --package-lock-only --json`: zero reported vulnerabilities;
  311 dependencies. This is a lockfile advisory check, not an installed-tree
  or exploitability proof.
- `python -B -m pytest -q -p no:cacheprovider
  tests/test_docs_dependency_security.py`: three passed, with
  `PYTHONDONTWRITEBYTECODE=1` because the host was low on disk space.
- `git diff --check`: passed.
- `npm ci --ignore-scripts --no-audit --no-fund`: failed during package
  extraction with `ENOSPC`. A complete clean install and docs build have not
  been established locally. No install or build failure was hidden or waived.

The new Python tests cover manifest/lock contracts only. The additive, read-only
`docs-dependency-security.yml` workflow invokes them, installs with `npm ci`,
audits the installed tree, builds the docs and checks that installation did not
rewrite the committed lock. Its result must be read at the final candidate head;
adding a workflow is not evidence of a passing run. Main-branch alerts, protected admission,
publication, deployment and live verification remain separate gates. Existing
CI definitions, security thresholds, provider settings and publishing authority
are unchanged.
