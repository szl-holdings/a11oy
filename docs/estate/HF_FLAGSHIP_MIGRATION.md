# Hugging Face flagship migration

Effective 2026-09-04. This document materializes owner directive
`owner-2026-09-04-sentra-assurance-command` and supersedes the earlier
same-day cyber-resilience consolidation wherever it folded Sentra or routed
Aegis assurance to Killinchu.

## Target architecture

`a-11-oy.com/products/` is the public product portfolio. Hugging Face is a deployment and discovery surface, not the portfolio itself. Closely coupled capability planes that share one operator, evidence chain and response boundary must not be presented as competing products.

Canonical public Space set:

| Product family | Product | Target Space | Canonical GitHub source |
|---|---|---|---|
| Command | A11oy Command | `SZLHOLDINGS/a11oy` | `szl-holdings/a11oy` |
| Cyber-physical resilience | Killinchu | `SZLHOLDINGS/killinchu` | `szl-holdings/killinchu` |
| Assurance | Sentra | `SZLHOLDINGS/sentra` | publisher in `szl-holdings/a11oy`; assurance engine source `szl-holdings/szl-defensive-control-plane` |
| Real estate | Terra | `SZLHOLDINGS/terra` | `szl-holdings/szl-real-estate` |
| Legal | PRISM Counsel | `SZLHOLDINGS/counsel` | `szl-holdings/counsel` or the currently admitted source recorded by its publisher |
| Finance | PURIQ Finance | `SZLHOLDINGS/finance` | `szl-holdings/puriq-live` |
| Observability | Lyte | `SZLHOLDINGS/lyte` | `szl-holdings/lyte-lattice` |
| Insurance | David Leads | `SZLHOLDINGS/david-leads` | `szl-holdings/david-leads` |
| Living system atlas | Living Anatomy | `SZLHOLDINGS/anatomy` | `szl-holdings/anatomy` + handles-only `szl-holdings/szl-second-brain` projection |

The seven core dynamic product surfaces are A11oy, Killinchu, Sentra, Lyte,
Finance, Terra, and Counsel. David Leads remains a separate commercial workflow
and Living Anatomy remains a creator-profile atlas; neither is silently promoted
into the seven-product core.

## Killinchu product boundary

Killinchu is the sole Cyber-Physical Resilience Command:

| Capability plane | Source of unique capability | Killinchu target | Legacy Space state |
|---|---|---|---|
| Vessels / Maritime | `szl-holdings/killinchu` plus transitional `vertical-services` engine | `/vessels` and `/api/vessels/*` | `SZLHOLDINGS/vessels` — reference cleanup required |
| Counter-UAS / Airspace | `szl-holdings/killinchu` | `/airspace` and existing source-native routes | no separate Space |

Vessels remains an independently testable capability identifier but not a
separate public flagship. Killinchu owns the maritime and counter-UAS command
boundary. It does not own assurance.

## Sentra product boundary

Sentra is the sole Assurance Command:

| Assurance plane | Source of unique capability | Sentra target | Prior surface state |
|---|---|---|---|
| GATE admission | `szl-holdings/szl-defensive-control-plane` | Sentra assurance flow | active flagship plane |
| YAWAR receipt verification | existing receipt-chain contracts | Sentra evidence plane | active flagship plane |
| IMMUNE | `szl-holdings/immune` | engine/library under Sentra | independent flagship disallowed; migration/parity proof still required |
| Aegis assurance | retained historical evidence | Sentra | `SZLHOLDINGS/aegis-assurance` decommissioned; mission routes to Sentra |

Aegis is absorbed history, not a competing portfolio or runtime. Decommissioning
does not erase source, release, or receipt evidence. IMMUNE retains its source
repository and explicit external-authority limits while serving as an engine
under Sentra rather than as a duplicate flagship shell.

The combined `SZLHOLDINGS/vertical-services` runtime may retain Sentra,
Killinchu, and maritime contracts as separate internal engines. That is
implementation modularity, not permission to recreate Vessels, Aegis, or
IMMUNE as duplicate public product Spaces.

## Deletion gates

A legacy Space may be deleted only when every gate is true:

1. **Source captured** — unique code and licenses are present in a named GitHub repository or immutable release artifact.
2. **Product captured** — useful workflows are implemented on a same-origin Killinchu route; a link, iframe or reverse proxy to the old Space is insufficient.
3. **Evidence captured** — proof, receipts, benchmarks and source hashes remain preserved in GitHub or `a11oy.net`; decommissioned nodes remain in historical evidence.
4. **Publisher removed** — active keep-lists, catalogs, workflows and factories cannot recreate or republish the legacy Space.
5. **Replacement verified** — the declared successor is reachable, exact-source bound and its replacement route passes its readiness contract.
6. **Secrets preserved** — no legacy Space contains the only copy of a required signing identity or configuration.
7. **Retirement receipted** — the irreversible deletion writes a secret-free receipt naming the legacy id, replacement route, source revision and observation time.

Deletion is the final step. Pausing/private is the safe intermediate state, but it is not terminal when the owner requires the old Space to disappear from the organization inventory.

## GitHub alignment

Killinchu is the canonical product source. `szl-defensive-control-plane` and `immune` remain component-engine sources until their contracts are imported or consumed through exact immutable releases with parity tests. They should not be deleted merely to make the product catalog smaller.

Other component repositories—KHIPU, Anatomy, receipt tooling, kernels, Forge, router, telemetry, evidence tooling and model infrastructure—are platform capabilities and should surface through a canonical product or proof route rather than consuming permanent public Space slots.

Archived repositories that retain unique source or release evidence remain available. Product consolidation removes duplicate public runtimes; it does not erase source history.
