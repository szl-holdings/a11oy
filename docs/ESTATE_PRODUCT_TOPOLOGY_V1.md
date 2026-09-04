# SZL Estate Product Topology v1

## Public products

The public estate has exactly five independently presented products:

| Product | Public Space | Public job |
|---|---|---|
| Killinchu | `SZLHOLDINGS/killinchu` | Defense, cyber-resilience, and maritime command |
| Terra | `SZLHOLDINGS/terra` | Real-estate intelligence |
| PRISM Counsel | `SZLHOLDINGS/counsel` | Legal matter intelligence |
| PURIQ Finance | `SZLHOLDINGS/finance` | Financial intelligence |
| Lyte | `SZLHOLDINGS/lyte` | Business observability |

`SZLHOLDINGS/vertical-services` is shared infrastructure, not a sixth customer-facing product.

## Capability planes and labels

- **Sentra** is an independently testable defensive-control capability plane inside Killinchu. Its canonical public route is `SZLHOLDINGS/killinchu` at `/defend`.
- **Vessels** is an independently testable maritime capability plane inside Killinchu. Its canonical public product is Killinchu.
- **Aegis** is the defense and resilience portfolio label. It does not create another runtime or state authority.
- **IMMUNE** is migration-gated. It must not be silently claimed as consolidated until its unique admission, signed-authority, and tripwire contracts are imported, tested, and source-bound.

## Non-negotiable completion contract

A release is complete only when all of the following are measured at the same time:

1. all five public Spaces are in the `RUNNING` state;
2. every required public route returns a successful, product-identifiable response;
3. each `/api/build-info` revision equals the current GitHub default-branch revision of its declared deployment source;
4. Killinchu exposes live `/defend` and `/resilience` product routes plus the Defend status, readiness, and source APIs;
5. `vertical-services` declares Sentra non-public, points its public route to Killinchu `/defend`, identifies Aegis as `killinchu:defend`, and leaves IMMUNE `MIGRATION_REQUIRED`;
6. standalone Sentra and Vessels Spaces are absent or immutable retirement tombstones that point to Killinchu;
7. no public product, model, kernel, agent, or Hatun review path is represented as having consequential authorization it does not possess.

## Witness

`scripts/estate_product_topology.py` is the executable contract. It uses fixed-origin, credential-free `GET` requests, retains response hashes rather than response bodies, emits `estate-product-topology.json`, and fails closed when topology, availability, or source binding drifts.

The scheduled GitHub workflow preserves every witness as a 90-day immutable artifact. A failed live witness is a release blocker, not a presentation warning.
