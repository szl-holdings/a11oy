# Knowledge graph schema

Status: MODELED; the existing visualization is not evidence of a durable graph store.

## Nodes

`Tenant`, `Project`, `Repository`, `Commit`, `Deployment`, `Model`, `Dataset`,
`Space`, `Kernel`, `Claim`, `Evidence`, `Decision`, `Outcome`, `Person`, `Policy`,
and `Receipt`.

Each node carries a stable identifier, tenant, classification, provenance,
epistemic status, validity interval, source revision, and content digest.

## Edges

`CONTAINS`, `DERIVED_FROM`, `DEPLOYED_AS`, `USES`, `SUPPORTS`, `CONTRADICTS`,
`SUPERSEDES`, `DECIDED_BY`, `PRODUCED`, `VERIFIED_BY`, and `GOVERNED_BY`.

Edges are directed, time-scoped, source-backed, and independently retractable.
Contradictory claims coexist as separate nodes; confidence never overwrites history.
