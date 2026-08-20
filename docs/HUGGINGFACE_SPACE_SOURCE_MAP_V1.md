# Hugging Face Space Source Map v1

## Purpose

A frontend failure may be repaired only in the application’s canonical source repository and promoted through its existing deployment writer. This map removes name-guessing and competing-writer risk from the SZLHOLDINGS Space remediation program.

## Evidence classes

- `EXACT` — one explicit `github.com/szl-holdings/*` source URL is present in the public Space README/card and the repository exists.
- `INFERRED` — no explicit source URL is present, but exactly one normalized Space-name repository exists. This remains inferred evidence and requires owner review before write operations.
- `DIVERGENT` — explicit links are missing, unresolved, or point to multiple repositories; or multiple normalized name matches exist.
- `UNAVAILABLE` — no public source mapping can be established.

`EXACT` identifies a canonical source repository for owner-reviewed source changes and promotion through that repository's protected writer. It does not authorize a direct Hugging Face mutation. `INFERRED` may be used for investigation only, while `DIVERGENT` and `UNAVAILABLE` remain blocked pending explicit ownership evidence.

## Captured state

For each public Space, the map records:

- Hugging Face repository and runtime revisions
- README bytes fetched from the exact recorded Hugging Face repository revision
- runtime stage and SDK
- public README hash and front-matter keys
- explicit SZL Holdings GitHub links
- verified or inferred source-repository candidates
- canonical source-repository default branch, exact branch-head revision, visibility, and archival state
- deployment-workflow filename candidates under `.github/workflows` at that exact GitHub revision

A single workflow filename candidate is not proof of single-writer authority. It is labeled only as a candidate until workflow contents, target resource, and protected promotion behavior are reviewed.

Candidate records in a `DIVERGENT` mapping retain repository identity only. Mutable branch, visibility, and archival fields are omitted, and workflow discovery remains blocked until exactly one canonical repository has been established.

## Mutation boundary

The map performs public/read-only Hugging Face and GitHub API calls. It does not create branches, pull requests, releases, deployments, Hub commits, model updates, dataset updates, collection changes, secrets, hardware allocations, storage mounts, or visibility changes.

## Use in the remediation pipeline

1. The estate-wide browser census identifies a blocked Space.
2. This map resolves the canonical source repository.
3. The universal frontend adapter is installed in that repository.
4. Existing CI, protected merge, and the canonical Hub writer promote the repair.
5. The browser census proves all five viewport classes and immutable runtime identity.
6. The asset closes only after the source map, deployment evidence, and live readback agree.
