# js-yaml dependency closure follow-through

Observed 2026-09-10 00:54 UTC. This note records source maintenance, not a
production deployment or successful release attestation.

A11oy PR 2077 repairs GHSA-2883-xcg3-v3hh without changing scanner severity,
ignore rules, branch protection, or model/runtime authority. Initial candidate
`d9e4524ea0e8a8f6f6aa0679380e8c41c39a681c` passed its security scans but failed
`npm ci` in run 34422272199, job 102700081084, because the npm lock lacked the
browserslist dependency closure. The error preceded the policy test execution;
it was not a policy-test failure.

The existing bounded maintenance workflow subsequently generated commit
`8c2fef52474449396ea94e29e7107b8e9d801c97`. The inspected diff restores
baseline-browser-mapping, caniuse-lite, electron-to-chromium, node-releases,
update-browserslist-db, and browserslist npm records. Both override systems now
bind browserslist 4.28.8. Patched transitive js-yaml 4.3.2 remains distinct from
the retained direct 5.4.1 dependency. The revised generator includes an npm
clean-install dry run in addition to pnpm frozen-lockfile validation; the full
hosted npm clean install and policy tests are still required.

At the observation time, the generated commit had zero GitHub check-runs.
Earlier successful checks cannot be reused as proof for different source bytes.
This evidence-only owner-session commit requests fresh existing PR checks on
the generated closure. It does not edit the package managers' output or the
active maintenance workflow, and does not manufacture a status or approval.

A11oy PRs 2075 and 2076 depend on the admitted dependency repair. Their own
candidate checks and canonical deployment/readiness steps remain required.
Normal protected merge only after the current complete candidate passes.
