# Cross-repo handoff readiness

This runbook makes blocked sibling-repo work auditable while GitHub Enterprise
access is being configured. It is an A11oy-local queue, not a claim that the
target repositories have been updated.

The machine-readable ledger is
[`cross-repo-handoff-manifest.json`](cross-repo-handoff-manifest.json).

## Current boundary

- A11oy is writable from this environment.
- Several sibling repos have previously rejected direct pushes with `403`.
- Proxy patches and status files in `coordination/` are the safe fallback.
- Additional Enterprise seats help only after the correct account/app has org
  membership, target repo write permission, SSO/PAT authorization, or GitHub
  App installation scope.

## Handoff states

| State | Meaning |
| --- | --- |
| `ready-for-owner-apply` | Patch exists, local validation evidence exists, and owner/proxy can apply it to the target repo. |
| `needs-target-runner` | Patch exists, but target-native tools such as `lake build` must run in the sibling repo before completion claims. |
| `blocked-by-access` | Direct push remains blocked from this runtime. |
| `complete` | Reserved for future use only after target PR merge and green target CI evidence. |

## Operator flow after access is fixed

1. Run `npm run cross-repo:handoff:audit`.
2. Pick one handoff entry.
3. Apply the patch to the target repo feature branch.
4. Run all `targetValidationRequired` commands in that repo.
5. Open a target-repo PR.
6. Wait for target CI.
7. Only then update A11oy readiness from `roadmap` /
   `lean-backed-needs-upstream-ci` to a stronger status.

## Forbidden claims

Do not say:

- “complete”
- “production-ready”
- “all green”
- “zero sorry”
- “catalog accepted”
- “endorsed”
- “deployed to target repo”

unless the target repo has the patch applied, native validation passed, CI is
green, and public release/docs evidence exists.

## Validation

```bash
npm run cross-repo:handoff:audit
```

This validation is offline: it checks patch/status paths, patch SHA-256 values,
target repos against the Enterprise access checklist, and claim-boundary
language. It does not push to sibling repos.
