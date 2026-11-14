<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Model inventory gap observations, 2026-11-11

Two model repositories that are in the local regeneration of
`docs/huggingface-ecosystem-manifest.json` at 2026-11-11T15:08:20Z, absent from
the committed 2026-11-06 inventory, and absent from
`docs/model-inference-support.json` now have a dated assessment and a
provider-mapping observation. The machine-readable record is
[`model-inference-inventory-gap-2026-11-11.json`](model-inference-inventory-gap-2026-11-11.json).

Unlike the 2026-11-10 record, the regeneration this record was read against is
committed with this change instead of restored. It held 90 model repositories,
the same 90 ids the catalog now lists, so
`scripts/collect_model_inference_support.py --check` exits 0 against it, and
`scripts/render_public_estate_alignment.py` passes with every public Space
classified by the committed contract. The reviewed public-inventory refresh
workflow remains the actor-gated path that would regenerate and commit these
generated files.

## What the reads returned

Each call used the catalog mapping URL, anonymous GET, no redirect, and the
256 KiB response limit. Both returned HTTP 200. Every `inferenceProviderMapping`
was an empty object, recorded as `NO_PROVIDER_MAPPING`. The recursive file list
at the returned revision returned HTTP 200 for both. `README.md` at the revision
root returned HTTP 404 for both. No weight file was downloaded and no model was
run.

| Result | Count |
|---|---:|
| Mapping HTTP 200 and empty | 2 |
| Mapping populated or lookup failed | 0 |
| Assessments written | 2 |
| Rows whose returned sha matches the inventory sha | 2 |
| Rows whose returned sha differs from the inventory sha | 0 |
| `README.md` HTTP 200 | 0 |
| `README.md` HTTP 404 | 2 |
| Inference admission authority | 0 |
| Exclusion authority | 0 |
| Prior support rows left unchanged | 88 |
| Catalog rows after this record | 90 |
| Inventory models outside this record | 0 |

Artifact classes come from revision file names: 1 `adapter_bundle`
(`abstention-v2-candidate`, whose recursive revision file list shows training
checkpoint directories with `adapter_config.json` and
`adapter_model.safetensors` and no root-level serving bundle) and 1
`non_provider_artifact` (`physics-master-v1-candidate`, whose revision lists
only `.gitattributes`). An empty mapping does not make an adapter or an empty
shell eligible to serve. Authority flags stay false, and no support discussion
was submitted.

## Sha differences

None. Both mapping responses returned the sha in the committed regeneration.
A later committed refresh can observe a newer revision. The row keeps the
revision that was fetched.

## Still open

- `SZLHOLDINGS/abstention-v2-candidate` has no `README.md` at its revision root;
  `README.md` exists only inside its checkpoint directories. Its assessment
  source URL is the card path the schema requires, and that path returned 404.
- `SZLHOLDINGS/physics-master-v1-candidate` has no `README.md` at its observed
  revision and lists no weight file at all.

## Tests

`tests/test_model_inference_inventory_gap_dossier_2026_11_11.py` checks this
record against the catalog, including the exact 2-id set and the regeneration
time. The 2026-11-07 and 2026-11-10 dossier tests now add the rows named here
when they check exact catalog membership. Their per-row assertions are
unchanged; the 2026-11-10 test's support-file count assertions now pin the
values that record observed instead of the live catalog size, because this
later record grew the catalog.

## Rows

| Decision | Model id | Observed sha | Inventory sha | Class | README |
|---|---|---|---|---|---|
| D01 | `SZLHOLDINGS/abstention-v2-candidate` | `2025383caf3a1d1341d51f0fd98634072262ae76` | same | `adapter_bundle` | 404 |
| D02 | `SZLHOLDINGS/physics-master-v1-candidate` | `b6aa4f01476421acce9beeec60fe42cd00e594a3` | same | `non_provider_artifact` | 404 |

Admission was not granted for any row. `selected` remains null.
