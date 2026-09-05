<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Public experience v1 architecture

## Boundary and data flow

The existing FastAPI process remains the sole runtime. `serve.py` registers the
experience service before the generic API proxy and SPA catch-all. The service
loads two strict, versioned allowlists at startup and reconciles the estate
projection against `governance/public-estate.v1.json`. Any registration failure
installs the same nine route shapes as explicit `503 UNAVAILABLE` JSON handlers
instead of allowing HTML fallback to masquerade as API success.

```text
governance/public-estate.v1.json ----+
                                     +--> strict startup reconciliation
config/public-experience/*.json ----+             |
                                                   v
browser controller --> /api/experience/v1/* --> typed state machine
      |                                            |
      +--> semantic lifecycle <--- ordered SSE ----+
      +--> lazy 3D or designed 2D renderer          |
      +--> evidence and receipt inspectors <--------+
```

## State, effects, and receipts

The service accepts one of five server-defined scenarios. The client cannot
supply a tool name, URL, effect adapter, or terminal state. Each session uses an
opaque identifier, deterministic scenario seed, monotonically increasing
sequence, previous/current event hashes, bounded TTL, and bounded storage.

Every public execution is `SIMULATION`. Approval-required scenarios return a
single bounded capability only in the creation response. The capability is
scope-, session-, scenario-, sequence-, expiry-, and nonce-bound; read paths do
not return it. Idempotent creation accepts only a canonical lowercase UUIDv4;
the key is unguessable replay capability material, is stored only inside a
one-way scope digest, and must never be logged or echoed. A replay returns the
same pending capability without minting a second authority; after consumption,
it returns no capability. Approval cannot authorize a real-world effect.

Receipt assertions are separated into four independent dimensions:

- event-chain integrity;
- cryptographic signer state;
- simulated effect/result;
- verification result.

The receipt verify route compares the submitted bytes with the stored receipt,
recomputes the deterministic statement, validates the event chain, then asks
the host verifier to validate the canonical envelope. A hash-continuous receipt
is not relabeled as cryptographically verified. Ephemeral signing identity is
reported as ephemeral, not promoted to durable external authority.

## Frontend responsibility split

`a11oy_landing.html` owns concise product copy, controls, drawers, and a complete
semantic seven-movement lifecycle. The controller owns API/SSE orchestration,
keyboard search, cancellation, stale-response suppression, safe link routing,
focus management, and honest state labels. The lazy renderer owns visual
projection only; it cannot advance the lifecycle.

The renderer is optional. Reduced motion, unavailable WebGL/WebGPU, failed
module loading, and an off-screen stage all retain the same data and controls in
the semantic 2D representation. The controller caps pending work and aborts
superseded requests so older sessions cannot overwrite current state.

## Public search

Search indexes only the reconciled estate projection and the five published
scenarios. Links are accepted only when they are relative public routes or
HTTPS URLs already derived from the canonical estate allowlist. No raw HTML is
inserted from API content, and no private repository discovery occurs in the
browser.

## Design references

The interaction model borrows only general public principles: operate an AI
workflow and inspect its context; retain collaborative investigative threads;
show command-and-control state spatially; and route errors to actionable
evidence. The references are public product documentation from
[Palantir AIP](https://www.palantir.com/docs/foundry/aip/aip-features),
[Palantir Threads](https://www.palantir.com/docs/foundry/threads/getting-started),
[Anduril Lattice](https://www.anduril.com/lattice/command-and-control), and
[New Relic Errors Inbox](https://docs.newrelic.com/docs/errors-inbox/getting-started/).
No vendor source, asset, wording, layout, trademark treatment, or identity is
copied.

## Taxonomy

`a11oy_public_experience.py` is a `services`-layer adapter. It projects existing
governance, estate, signing, and verification authorities into a bounded public
experience; it does not replace those authorities.
