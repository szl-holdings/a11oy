# Memory scope policy

Status: MODELED

Every memory belongs to one tenant and an explicit project, repository, branch,
and environment. Retrieval is deny-by-default across those boundaries.

## Allowed scope transitions

- Branch to repository: only an admitted, non-WORKING record with provenance.
- Repository to project: only if `propagation_allowed` is true and policy permits it.
- Project to ecosystem: only HUMAN_REVIEWED public or internal evidence.
- Tenant crossing: prohibited without a named export policy and receiving-tenant admission.

The retrieval layer must intersect caller authorization, record classification,
allowed consumers, retention state, and requested scope. A missing field denies access.
Secrets, raw credentials, private prompts, and personal data never enter public memory.
