# Estate release controller permissions — 2026-10-05

Base: `54738e29006453f2b8f60d0f7cf7df40b0ce0508`. Workcell: SZL-ESTATE-PR-READONLY-20261005.

Plan: separate proposed-controller observation from protected-main provider-dispatch and incident permissions. Retain candidate tests and public observation evidence while removing actions:write and issues:write from every pull-request execution of this controller.

The new `verify-pr` job grants actions/contents/issues read only, checks out the exact event SHA without persisted credentials, runs the original offline controller suite and observation steps, and uploads immutable evidence. It has no provider-dispatch, incident-write, secret or alignment-enforcement steps.

The retained `verify` job excludes pull_request, requires main, checks successful same-repository/main upstream completion, and checks out its exact protected event SHA. Existing explicit manual repair, source-vector validation, downstream completion barriers, incident lifecycle and final alignment enforcement remain intact. Canonical writer serialization and PR-specific concurrency groups are preserved.

Verification: 161 focused existing and new stdlib tests pass. New contracts enforce reader permissions and absence of mutation/secret steps; operational job trust conditions; exact checkout; preserved candidate proof and protected dispatch/enforcement. Both offline paths execute the permission contract. Workflow YAML parses correctly. No provider dispatch, issue mutation, secret change, deployment, or runtime readiness was performed or inferred.

Rollback: reviewed revert of this bounded workflow/test/proof change. Hosted exact-head checks remain required before admission.

