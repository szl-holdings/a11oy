# Hugging Face flagship migration

Effective 2026-09-04. This document supersedes the 2026-09-02 one-Space-per-vertical snapshot for the cyber-resilience family.

## Target architecture

`a-11-oy.com/products/` is the public product portfolio. Hugging Face is a deployment and discovery surface, not the portfolio itself. Closely coupled capability planes that share one operator, evidence chain and response boundary must not be presented as competing products.

Canonical public Space set:

| Product family | Product | Target Space | Canonical GitHub source |
|---|---|---|---|
| Command | A11oy Command | `SZLHOLDINGS/a11oy` | `szl-holdings/a11oy` |
| Cyber-physical resilience | Killinchu | `SZLHOLDINGS/killinchu` | `szl-holdings/killinchu` |
| Real estate | Terra | `SZLHOLDINGS/terra` | `szl-holdings/szl-real-estate` |
| Legal | PRISM Counsel | `SZLHOLDINGS/counsel` | `szl-holdings/counsel` or the currently admitted source recorded by its publisher |
| Finance | PURIQ Finance | `SZLHOLDINGS/finance` | `szl-holdings/puriq-live` |
| Observability | Lyte | `SZLHOLDINGS/lyte` | `szl-holdings/lyte-lattice` |
| Insurance | David Leads | `SZLHOLDINGS/david-leads` | `szl-holdings/david-leads` |
| Living system atlas | Living Anatomy | `betterwithage/anatomy` | `szl-holdings/anatomy` + handles-only `szl-holdings/szl-second-brain` projection |

## Killinchu product boundary

Killinchu is the sole public runtime for the Aegis cyber-resilience portfolio:

| Capability plane | Source of unique capability | Killinchu target | Legacy Space state |
|---|---|---|---|
| Sentra / Defend | `szl-holdings/szl-defensive-control-plane` | `/defend` and `/api/defend/*` | `SZLHOLDINGS/sentra` — migration required |
| IMMUNE | `szl-holdings/immune` | `/immune` and `/api/immune/*` | `SZLHOLDINGS/immune` — migration required |
| IMMUNE lattice | `szl-holdings/immune` Python runtime | `/immune` | `SZLHOLDINGS/immune-lattice` — parity audit required |
| Vessels / Maritime | `szl-holdings/killinchu` plus transitional `vertical-services` engine | `/vessels` and `/api/vessels/*` | `SZLHOLDINGS/vessels` — reference cleanup required |
| Aegis assurance | thin roadmap adapter | `/resilience` | `SZLHOLDINGS/aegis-assurance` — delete after reference cleanup |
| Counter-UAS / Airspace | `szl-holdings/killinchu` | `/airspace` and existing source-native routes | no separate Space |

Aegis is the internal portfolio name. Sentra, IMMUNE and Vessels remain independently testable capability identifiers. Killinchu is the external product and public Space.

The combined `SZLHOLDINGS/vertical-services` runtime may retain Sentra and Killinchu as separate internal engines. That is implementation modularity, not permission to recreate separate public product Spaces.

## Deletion gates

A legacy Space may be deleted only when every gate is true:

1. **Source captured** — unique code and licenses are present in a named GitHub repository or immutable release artifact.
2. **Product captured** — useful workflows are implemented on a same-origin Killinchu route; a link, iframe or reverse proxy to the old Space is insufficient.
3. **Evidence captured** — proof, receipts, benchmarks and source hashes remain preserved in GitHub or `a11oy.net`.
4. **Publisher removed** — active keep-lists, catalogs, workflows and factories cannot recreate or republish the legacy Space.
5. **Replacement verified** — `SZLHOLDINGS/killinchu` is reachable, exact-source bound and the replacement route passes its readiness contract.
6. **Secrets preserved** — no legacy Space contains the only copy of a required signing identity or configuration.
7. **Retirement receipted** — the irreversible deletion writes a secret-free receipt naming the legacy id, replacement route, source revision and observation time.

Deletion is the final step. Pausing/private is the safe intermediate state, but it is not terminal when the owner requires the old Space to disappear from the organization inventory.

## GitHub alignment

Killinchu is the canonical product source. `szl-defensive-control-plane` and `immune` remain component-engine sources until their contracts are imported or consumed through exact immutable releases with parity tests. They should not be deleted merely to make the product catalog smaller.

Other component repositories—KHIPU, Anatomy, receipt tooling, kernels, Forge, router, telemetry, evidence tooling and model infrastructure—are platform capabilities and should surface through a canonical product or proof route rather than consuming permanent public Space slots.

Archived repositories that retain unique source or release evidence remain available. Product consolidation removes duplicate public runtimes; it does not erase source history.
