<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Frontier Now Estate Cockpit Proof Packet

## Candidate identity

- Repository: `szl-holdings/a11oy`
- Branch: `agent/frontier-now-estate-cockpit-20260811`
- Tracking issue: `#1258` (W1 public truth and terminal-state runtime)
- Exact branch point: `main@19ae60fdf6f0f95ce3c2c2a7a3f3f9b9f5d3a2b1c`
- Candidate state when this packet was opened: `LOCAL_VALIDATED_UNPUBLISHED`
- Operating mode: `OBSERVE_ONLY`
- Sign on read: `false`
- External effectors added by this candidate: `0`

## Current provider and runtime readback

The following is a bounded 2026-08-11 read-only observation, not eternal truth:

- GitHub exposed 58 organization repositories and 15 open pull requests during
  the audit. The candidate does not expose repository names through its public
  inventory projection.
- Public Hugging Face APIs exposed 16 models, 27 datasets, and 26 Spaces. Of
  those Spaces, 16 returned a running HTTP surface and 10 were paused and
  returned HTTP 503. Paused or quota-blocked Spaces remain unavailable.
- `https://a-11-oy.com/api/build-info` reported source revision
  `63f651f691b566f1fbeefcfcd7eba1e87050ff45`.
- The A11oy Hugging Face repository/runtime revision was independently reported
  as `f5c395e81eaa306b2eb1c8bbf8773f07664ce564`.
- The source-attestation route does not bind the GitHub source, Hugging Face
  overlay, and a runtime artifact digest into exact equivalence. The candidate
  therefore reports that relationship as `UNAVAILABLE` and holds public claims.
- Authenticated Hugging Face administration/publication was unavailable in
  this lane. No model, dataset, bucket, kernel, or Space mutation was attempted.

## Local automated verification

Observed on the candidate worktree with bundled Python and Node runtimes:

- `pytest tests/test_frontier_now_control_plane.py tests/test_series_a_control_plane.py -q`
  completed: `47 passed`, with one Starlette/httpx deprecation warning.
- The exact always-on CI command over `tests/test_demo_critical_routes.py`,
  `tests/test_frontier_now_control_plane.py`, and
  `tests/test_holographic_static_route_runtime.py` completed: `58 passed`.
- A bounded production-app assembly assertion imported `serve.app`, found
  `1546` routes, and proved all 12 Frontier Now page, asset, alias, summary, and
  inventory routes are uniquely owned by
  `routers.frontier_now_control_plane`, support GET/HEAD, and precede both the
  generic A11oy API proxy and SPA catchall.
- The same production-app import emitted an existing non-fatal local
  auto-review SQLite warning (`unable to open database file`). This candidate
  does not treat that unrelated local subsystem as green.
- `node --check routers/frontier_now_web/app.js`: passed.
- Python bytecode compilation for the new router and focused route tests:
  passed.
- `.github/workflows/tests.yml` YAML parse: passed.
- `git diff --check`: passed.

The always-on `python-demo-critical-routes` CI job now includes the complete
focused Frontier Now suite, in addition to the real assembled route-table guard.

## Browser observation and limit

A live local FastAPI assembly was opened with a deliberately MODELED fixture;
provider tokens were removed from that process. This was layout/interaction
evidence only, not a live-provider or deployed-runtime claim.

At a 1440 x 1000 viewport, the browser observed:

- title `A11oy Frontier NOW · Estate Proof Surface`;
- estate state `MODELED` and claim state `FAILED_CLOSED`;
- 10 rendered capability rows;
- no document-level horizontal overflow;
- no third-party page assets; and
- no console warning or error entries.

At a 390 x 844 viewport, the browser found document-level horizontal overflow
caused by the unbroken source/runtime evidence reason. The candidate was changed
to wrap that reason and a static regression now requires
`overflow-wrap: anywhere`. The browser subsequently blocked the localhost
reload under its URL policy, so the post-fix mobile frame is `UNAVAILABLE`, not
claimed as visually witnessed. Pre-fix screenshots are not part of the patch or
proof catalog.

## Security boundary

No public mutation control was added. The live OpenAPI contract did not declare
a security scheme for mutation-shaped operations, and representative CORS
preflights reflected an arbitrary origin during the read-only audit. This is not
proof that middleware authorization is absent, but it blocks action wiring.
Effectors must remain disabled until authentication, authorization, CSRF/origin
controls, rate limits, body limits, idempotency, one-canary budgets, rollback,
and effect receipts are independently observed.

## Publication boundary

This packet distinguishes local validation from a pushed branch, protected pull
request, merged source, Hugging Face publication, deployed runtime, and exact
deployment readback. Later stages must be appended only after they are directly
observed.
