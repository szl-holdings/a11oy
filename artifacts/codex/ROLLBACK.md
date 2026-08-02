# Rollback plan for PR branch changes

If this task branch needs to be reverted from deployment, follow these steps in order:

1. Identify the deployment revision currently tied to commit `dfddeb73450510622e88d4840d069841c52ff84a`.
2. Promote or restore the previous stable revision using the normal environment rollback path (no force operations in production).
3. Remove the PR from release train by merging a guarded rollback PR with reversal PR code and evidence.
4. For this repository history, revert `codex/finish-operational-build-2026-07-28` changes or cherry-pick a later follow-up commit that reverts:
   - `routers/series_a_control_plane.py`
   - `routers/governed_graph_operations.py`
   - `a11oy_frontier_page.py`
   - `serve.py`
   - related payload/evidence scripts under `scripts/`
5. Re-run the baseline and gate check list from `artifacts/codex/BASELINE.json` and `artifacts/codex/TEST_REPORT.json`.
6. Verify that no undocumented stateful side-effects remain in production before continuing.

Notes:
- This branch is additive and route-safe; rollback can be done with normal reverse-engineering PR if required.
- Artifact generation must be retained in git history even on rollback PRs unless explicitly deleted in the same scoped evidence plan.
