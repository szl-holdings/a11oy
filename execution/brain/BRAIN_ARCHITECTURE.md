# Holographic brain architecture

The brain is an evidence-governed coordination plane, not a decorative organ and
not a standalone AGI claim.

## Layers

1. Source events: GitHub PRs, commits, Hugging Face model/dataset/Space revisions,
   site deployment receipts, and manual operator decisions.
2. Provenance-bound ingestion: every event carries source, actor, timestamp, and
   immutable revision when available.
3. Durable memory: append-only records with replayable content digests, then
   signatures when an approved key path exists.
4. Entity graph: repos, Spaces, models, datasets, formulas, papers, routes, and
   deployments become nodes with backlinks.
5. Retrieval and reasoning: graph search, neighborhoods, lineage, contradictions,
   gaps, constitution checks, and uncertainty remain label-bound.
6. Proposal loop: generated recommendations must pass sandbox checks before any
   PR is opened.
7. Governance: protected PRs, independent review, green required checks, and no
   admin bypass.
8. Outcome memory: merged or rejected outcomes write back into memory.

## Status vocabulary

- OPERATIONAL: live, evidenced, replayable, and not relying on a stub.
- PARTIALLY OPERATIONAL: real route or artifact exists, with known gaps.
- MODELED: deterministic analysis or proxy, not a direct measurement.
- SIMULATED: stub, local-only, ephemeral, or non-signing path.
- EXPERIMENTAL: research capability not admitted into production claims.
- UNAVAILABLE: no evidence sufficient for a claim.

## Immediate build target

Use `/api/a11oy/v1/brain/capabilities` as the frontend/backbone contract for the
holographic brain. The next code slice should make the surface read this route
and display the status next to each lobe.
