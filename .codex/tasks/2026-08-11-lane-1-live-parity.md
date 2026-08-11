# Lane 1 — Source-to-Production Parity and Readiness

## Mission

Close the current `a11oy` source/build/served drift through the repository's existing protected deployment path. Do not return another roadmap. Implement any source or workflow corrections that are actually required, then drive the protected deployment and readiness evidence chain to a truthful terminal state.

## Current-context warning

At seed time, protected `main` is `90ed8c7289efbda085d82f0dc60cf821b22f5caf`. The public readiness document has previously served cached repository and deployment values from an older generation. Re-read all sources directly at task start; never assume the older `3616dff...` deployed SHA or `367c049...` repository SHA remains current.

## Required investigation

1. Read root `AGENTS.md`, `KNOWN_GOTCHAS.md`, `hf-sync.yml`, `readiness-harness.yml`, the reusable Hugging Face deployer, canonical relock code, `/api/build-info`, `/api/a11oy/v1/readiness`, `/healthz`, and `/api/a11oy/v1/version` implementations.
2. Establish one exact tuple:
   - current protected-main SHA;
   - latest successful exact-head `hf-sync.yml` run;
   - immutable Hugging Face Space revision produced by that run;
   - direct Space-origin `/api/build-info` response;
   - public-domain `/api/build-info` response;
   - public readiness response;
   - readiness-harness run and artifacts.
3. Distinguish `SZL_GIT_SHA` source binding from optional `SZL_HF_SHA` repository-observability fields. Do not create a false red by equating unrelated identities; do not hide a genuinely unobserved field.
4. Reproduce all current failures before editing. If `hf-sync.yml` or relock logic has drifted from doctrine, repair the root cause with focused regressions.
5. Never publish an unmerged PR head. Use only protected merged source and the canonical writer.

## Implementation requirements

- Preserve `hf-sync.yml` as the only automatic writer to `SZLHOLDINGS/a11oy`.
- Require exact GitHub source binding through `SZL_GIT_SHA` and `/api/build-info`.
- Require two stable direct observations when the current contract does so.
- Keep dot-prefixed Dockerfile-derived paths, including `.well-known/security.txt`, in the deployment-set proof.
- Fail closed on missing, malformed, truncated, cached-only, or inconsistent evidence.
- Retarget when protected `main` moves during convergence; never deploy a now-stale head and call it current.
- Preserve live route registration before the SPA catch-all and all Dockerfile `COPY` completeness requirements.
- Do not weaken the readiness or source-bound gates to obtain green.

## Acceptance criteria

All of the following must be directly observed in the same current generation:

```text
protected_main_sha == deployed_git_sha
direct_build_info.build.revision == protected_main_sha
public_build_info.build.revision == protected_main_sha
direct_build_info.build.state == OBSERVED
public_build_info.build.state == OBSERVED
build_behind_by == 0
healthz == HTTP 200 and status ok
all readiness endpoints reachable
Hugging Face runtime stage == RUNNING
exact-head hf-sync run == success
exact-head readiness-harness run == success
immutable workflow artifacts retained
```

The app-reported Hugging Face repository SHA may remain `UNOBSERVED` only when the source-binding contract does not set it; that state must be explicit and non-authoritative, not silently treated as parity.

## Deliverable

Create a signed+DCO successor PR from exact current `main`. Run focused and relevant full tests, obtain protected exact-head checks, merge only through normal protections, execute the canonical deployment, and finish with the exact merged SHA, workflow run IDs, immutable Space revision, build-info digests, readiness artifact IDs, and any residual external blocker.
