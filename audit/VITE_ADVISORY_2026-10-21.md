# Standalone Vite dependency repair - 2026-10-21

Evidence class: MEASURED for commands below. Provider publication, production deployment and runtime readiness: NOT RUN.

## Cause and scope

Grype run 39563152193 identified GHSA-587h-7wmj-h5pm (High) and two Medium findings in standalone `pnpm-lock.yaml` Vite 6.4.3. The [official advisory](https://github.com/advisories/GHSA-587h-7wmj-h5pm) identifies 6.4.4 as the patched 6.x release. Pin Vite 6.4.4 in the root and workspace overrides and update its lock record and peer edges. This retains the existing Vite major and consumer API. The vendored Platform SPA has a separate dependency graph and is outside this patch.

The [official npm release metadata](https://registry.npmjs.org/vite/6.4.4) supplies the recorded tarball integrity. Vite 6.4.3 and 6.4.4 have identical dependency ranges. All unrelated package records, dependency versions and peer edges remain identical to base `251faf26d6745731c7f5f55b30d0517e6c016fd4`. The final lock retains the Vite records produced by CI-pinned pnpm 10.33.3; unrelated optional-peer normalization from the package manager was discarded. Parsed comparisons verify the final Vite records, affected Vitest importer and snapshots equal the generated result, and all other graph entries equal the base. Frozen installation validates the final narrow lock.

## Commands and results

- `pnpm install --frozen-lockfile --ignore-scripts --store-dir <owned-store>` with pnpm 10.33.3: passed on both base and final lock. The final command skipped resolution and completed successfully across all nine workspace projects.
- `node --test tests/dependency-overrides.test.mjs`: 27 passed, zero failed or skipped.
- `pnpm typecheck:doctrine`: passed before and after, including actual connection build/typecheck and core typecheck.
- `pnpm test:doctrine`: all 80 assertions passed across the nine existing standalone core scripts.
- `pnpm test:knowledge:lookup`: passed through the package's intended standalone runner.
- `pnpm --dir packages/a11oy-knowledge test`: unchanged baseline failure before and after. Vitest executes 27 tests: 26 pass, TH2 proof-sketch axiom references fail. A separate custom-runner lookup file also fails Vitest collection with "No test suite found". The lookup file passes through its intended runner above. No assertion or fixture was weakened.
- Actual installed Vite 6.4.4, resolved through the knowledge package's Vitest peer, successfully built a SAMPLE HTML/module fixture and served its transformed module over localhost. The final harness awaited dependency scanning and request completion, asserted no Vite logger error, and closed the server. An initial harness module-resolution failure and a second attempt's premature-shutdown diagnostic are retained; neither is presented as the final qualification run.
- `pnpm audit --json`: exit 0, zero advisories at every severity for this standalone graph.
- Official checksum-verified Grype 0.118.0, database built 2026-10-21T06:31:02Z, `grype dir:<bounded-root-lock-input> -o json --file <report> --fail-on high`: final lock zero matches, exit 0. The exact previous lock scanned with the same database is a positive control: one High (GHSA-587h-7wmj-h5pm), two Medium (GHSA-698v-4r3x-3vcv and GHSA-r825-w8mm-5pxw), exit 2. This is a root-lock scan; full repository CI remains separate.
- `git diff --check`: passed.

## Evidence anchors

Command-bound receipts and complete logs are retained under `outputs/a11oy-vite-*` in the parent task workspace. The aggregate security receipt is `outputs/a11oy-vite-security-20261021/receipt.json`; the final Vite fixture receipt is `outputs/a11oy-vite-consumer-smoke-final-20261021/receipt.json`. Official metadata, both Grype inputs/reports, and earlier expanded lock attempts are retained alongside these receipts.

| Artifact | SHA-256 |
| --- | --- |
| Security comparison receipt | 9fe7a16e63b4b38a09c8fce69c6ae28a5136a22f986bb97e9d7e07220195b1c6 |
| Root package.json | 6b0be8904f10b783bcc004c322c1914e18d4274ab7ccb991a4d66d564add4475 |
| pnpm-workspace.yaml | d83f17b3358d6805cdc8a2ab4a318a57182d4372acaebb1ced74e6b6e5ae53c8 |
| pnpm-lock.yaml | ee910847f2d69cca153dad98efba3c99fb05763d2095df65ee9ba543b98d8db0 |
| Final Vite smoke command output | 3c89a8dab5b6836abd13856320a72630d1d399e1529338a433ed17b56681ddaa |

No audit ignore, severity threshold, workflow, credential, provider configuration or runtime authorization changed. These results qualify this source dependency repair; they do not establish deployment or operational readiness.
