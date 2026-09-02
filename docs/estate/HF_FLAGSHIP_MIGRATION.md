# Hugging Face flagship migration

Effective 2026-09-02.

## Target architecture

`a-11-oy.com/products/` is the public product portfolio. Hugging Face is not the portfolio. It is a deployment/discovery surface for one flagship demo per vertical.

Canonical Space set:

| Vertical | Product | Target Space | Canonical GitHub source |
|---|---|---|---|
| Command | A11oy Command | `SZLHOLDINGS/a11oy` | `szl-holdings/a11oy` |
| Defense | Killinchu | `SZLHOLDINGS/killinchu` | `szl-holdings/killinchu` |
| Real estate | Terra | `SZLHOLDINGS/terra` | `szl-holdings/szl-real-estate` |
| Cybersecurity | Sentra | `SZLHOLDINGS/sentra` | `szl-holdings/szl-defensive-control-plane` |
| Legal | PRISM Counsel | `SZLHOLDINGS/counsel` | `szl-holdings/counsel` |
| Finance | PURIQ Finance | `SZLHOLDINGS/finance` | `szl-holdings/puriq-live` |
| Maritime | Vessels | `SZLHOLDINGS/vessels` | `szl-holdings/szl-fleet-overlay` |
| Observability | Lyte | `SZLHOLDINGS/lyte` | `szl-holdings/lyte-lattice` |
| Insurance | David Leads | `SZLHOLDINGS/david-leads` | `szl-holdings/david-leads` |

Everything else that is a Space is a migration source, not a permanent public product surface. Models, datasets, collections and artifacts are unaffected by this Space policy.

## Deletion gates

A legacy Space may be deleted only when all four gates are true:

1. **Source captured** — unique code is present in a named GitHub repository or intentionally folded into `a11oy`.
2. **Product captured** — useful user-facing copy, workflows, screenshots or concepts are represented on `a-11-oy.com/products/` or a linked product route.
3. **Evidence captured** — proof/receipt/benchmark links that remain useful are preserved in GitHub or `a11oy.net`.
4. **Replacement verified** — the surviving flagship for that vertical is reachable and its source owner is explicit.

Deletion is the final step. Pausing/private is the safe intermediate state.

## GitHub alignment

The vertical repositories above are canonical product sources. Component repositories such as KHIPU, IMMUNE, Anatomy, receipt tooling, kernels, Forge, router, telemetry, evidence tooling and model infrastructure are platform products/capabilities and should surface through `a-11-oy.com`, not consume permanent Hugging Face Space slots.

Archived repos that are canonical sources for a surviving vertical must be reviewed before final deletion. In particular, an archived source cannot be treated as the active canonical product repository without either unarchiving it or folding its maintained code into an active repository.
