# Killinchu public Space exception

- **Date:** 2026-07-25
- **Status:** Accepted, conditional
- **Decision:** Option A — retain killinchu as a justified sixth operational
  Hugging Face surface
- **Authority:** SZL Holdings release authority
- **Review:** 2026-10-23, or sooner if its unique counter-UAS capability is
  migrated into the approved five

## Context

The public-Space policy limits the normal flagship footprint to five. Killinchu
is an active, distinct counter-UAS product and deployment staging surface. It is
also referenced in older estate documents as one of "the five flagships." That
product taxonomy does not by itself authorize an additional public deployment
surface.

At the time of this decision, killinchu's runtime identity is divergent:

- GitHub `main`: `c0e06d8c3c1b3a9c2cf550451132bd8c96ece1f3`
- Hugging Face repository:
  `cb2ba6a7e63d9f07461a93491590086e354b40be`
- live version endpoint:
  `9f4e60297f77242fe1fc85e81a7546ea5413dee7`
- live health endpoint: a fourth, abbreviated commit identity

`RUNNING` therefore proves transport availability only. It does not prove that
the intended source is serving.

## Decision

Killinchu may remain public as a dated exception to the five-Space cap because
its counter-UAS role is operationally distinct. This decision authorizes
retention, not promotion of inherited health or provenance claims.

The exception is valid only while all of the following controls are enforced:

1. GitHub is the single editable source for Docker and runtime manifests.
2. Hugging Face deployment files are generated from the immutable GitHub
   revision; duplicate hand-edited deployment copies are removed or archived.
3. CI rejects undefined aliases, missing organ files, mutable source checkout,
   and incomplete Docker `COPY` coverage.
4. Post-deploy attestation compares GitHub SHA, Hugging Face SHA, image digest,
   runtime-reported source SHA, registered organs, and required routes.
5. Any mismatch is published as `DIVERGENT`; `RUNNING`, liveness, or an
   optimistic readiness response cannot override it.
6. Killinchu remains outside the product-domain primary navigation until the
   reconciliation gate passes.

## Consequences

- The estate has five normal public flagship slots plus this one conditional
  operational exception.
- Documents that describe killinchu as a product flagship may remain, but they
  must not be used to obscure the public-Space exception or the current
  `DIVERGENT` deployment state.
- No additional public Space is authorized by analogy with this exception.
- At review, the release authority must either renew the exception with current
  evidence or select Option B: migrate the unique capability and retire the
  separate public Space.
