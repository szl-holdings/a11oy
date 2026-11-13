<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Model inventory gap observations, 2026-11-10

Fourteen model repositories that are in a local regeneration of
`docs/huggingface-ecosystem-manifest.json`, absent from the committed 2026-11-06
inventory, and absent from `docs/model-inference-support.json` now have a dated
assessment and a provider-mapping observation. The machine-readable record is
[`model-inference-inventory-gap-2026-11-10.json`](model-inference-inventory-gap-2026-11-10.json).

The inventory was regenerated locally at 2026-11-10T11:13:26Z to read twelve of
these rows, and again at 2026-11-10T17:55:29Z to read the last two
(`SZLHOLDINGS/a11oy-code-r1-candidate` and
`SZLHOLDINGS/hatun-24-doctrine-math-r1-candidate`). Both regenerations were
restored. This change does not include them. The later one held 88 model
repositories, the same 88 ids the catalog now lists. Each row keeps the
regeneration and observation time it was read against. The reviewed
public-inventory refresh workflow is the step that would regenerate and commit
the inventory. Against a fresh local regeneration,
`scripts/collect_model_inference_support.py --check` exits 0 with this catalog.
That is the workflow's model coverage step only. A local run of the workflow's
steps still stopped earlier, at `scripts/render_public_estate_alignment.py`,
because the Space `SZLHOLDINGS/immune-lattice` is public and has no contract
classification. That Space is outside this record.

## What the reads returned

Each call used the catalog mapping URL, anonymous GET, no redirect, and the
256 KiB response limit. All 14 returned HTTP 200. Every `inferenceProviderMapping`
was an empty object, recorded as `NO_PROVIDER_MAPPING`. The file list at the
returned revision returned HTTP 200 for all 14. `README.md` at that revision
returned HTTP 200 for 13 and HTTP 404 for `SZLHOLDINGS/szl-brain`. No weight
file was downloaded and no model was run.

| Result | Count |
|---|---:|
| Mapping HTTP 200 and empty | 14 |
| Mapping populated or lookup failed | 0 |
| Assessments written | 14 |
| Rows whose returned sha matches the inventory sha | 14 |
| Rows whose returned sha differs from the inventory sha | 0 |
| `README.md` HTTP 200 | 13 |
| `README.md` HTTP 404 | 1 |
| Inference admission authority | 0 |
| Exclusion authority | 0 |
| Prior support rows left unchanged | 74 |
| Catalog rows after this record | 88 |
| Inventory models outside this record | 0 |

Artifact classes come from revision file names: 11 `standalone_weight_bundle`,
2 `adapter_bundle` (`a11oy-code-r1-candidate` and
`hatun-24-doctrine-math-r1-candidate`, whose revisions list
`adapter_config.json` and `adapter_model.safetensors` and no `config.json`),
and 1 `non_provider_artifact` (`szl-brain`, whose revision lists only
`.gitattributes`). An empty mapping does not make a weight bundle or an
adapter eligible to serve. Authority flags stay false, and no support
discussion was submitted.

## Retries

Two reads failed and were repeated. The first `forge-v3` file-list read
returned HTTP 429, a rate-limit response, and was repeated after the wait it
stated; the repeat at the same revision returned HTTP 200. The first
`szl-brain` mapping read returned `UNAVAILABLE` with `HTTP_ERROR`. The
collector keeps only the error class, so that read's HTTP status and cause are
unknown. The repeat returned HTTP 200 and is the recorded observation. Both
earlier attempts are kept in the JSON record.

## Sha differences

All 14 mapping responses returned the sha in the regeneration each row was
read against: 2026-11-10T11:13:26Z for D01 to D12 and 2026-11-10T17:55:29Z for
D13 and D14. A later committed refresh can observe a newer revision. The row
keeps the revision that was fetched.

## Still open

- `SZLHOLDINGS/szl-brain` has no `README.md` at its observed revision. Its
  assessment source URL is the card path the schema requires, and that path
  returned 404.

## Card self-labels

Nine rows carry inventory tags in which the card describes its own status:
`research-candidate` on eight rows, and `research-candidate` with
`not-promoted` on `SZL-GovernedDistill-0.8B-v1`. These two tags are recorded as
self-labels for the first time here. A card tag is not an exclusion record and
grants nothing.

## Tests

`tests/test_model_inference_inventory_gap_dossier_2026_11_10.py` checks this
record against the catalog, including the exact 14-id set and the two
regeneration times. The 2026-11-07 dossier test now adds the rows named
here when it checks exact catalog membership. Its per-row assertions are
unchanged.

## Rows

| Decision | Model id | Observed sha | Inventory sha | Class | README |
|---|---|---|---|---|---|
| D01 | `SZLHOLDINGS/SZL-AcousticGovernance-0.8B-v1` | `bf12e89bb5049efcf48c58613c49bb41ee8cb81b` | same | `standalone_weight_bundle` | 200 |
| D02 | `SZLHOLDINGS/SZL-FreeEnergy-0.8B-DPO-v1` | `f3bd9aeca3596269d499761eaad43678b9c92182` | same | `standalone_weight_bundle` | 200 |
| D03 | `SZLHOLDINGS/SZL-GovernedDistill-0.8B-v1` | `d454bd3238680f119920fd3a993a3573ca564e34` | same | `standalone_weight_bundle` | 200 |
| D04 | `SZLHOLDINGS/abstain-doctrine-r1` | `41cb72545e75b284ec62d271499e4487b75876d5` | same | `standalone_weight_bundle` | 200 |
| D05 | `SZLHOLDINGS/doctrine-v2-r2-candidate` | `0806db1aa7b9c5cec89836c22b91bbe9e70a9c7e` | same | `standalone_weight_bundle` | 200 |
| D06 | `SZLHOLDINGS/doctrine1-r1-candidate` | `0c26c6ba127f87863f1c3d98ab96120264aba91a` | same | `standalone_weight_bundle` | 200 |
| D07 | `SZLHOLDINGS/forge-v3` | `19b57bbe5668fe39233e36ceebf489143d65f1bc` | same | `standalone_weight_bundle` | 200 |
| D08 | `SZLHOLDINGS/freeenergy-r1-candidate` | `d038e7ffb0ee9563be9e35513d2b33e3f76db32d` | same | `standalone_weight_bundle` | 200 |
| D09 | `SZLHOLDINGS/ouroboros-r2-candidate` | `07e422d37a3d0fb4a2517e95bafde7795ce6d0e9` | same | `standalone_weight_bundle` | 200 |
| D10 | `SZLHOLDINGS/szl-brain` | `8ede51bbdb8fb382d1a6b3ff7eef47e3cda0c5e1` | same | `non_provider_artifact` | 404 |
| D11 | `SZLHOLDINGS/willay-r1-candidate` | `abdb04de040c71b491d7b39eb887fba72989c916` | same | `standalone_weight_bundle` | 200 |
| D12 | `SZLHOLDINGS/willay-r2-candidate` | `a165ea780c7b4972dba19ce70fbfd28a5bb8603c` | same | `standalone_weight_bundle` | 200 |

Read against the 2026-11-10T17:55:29Z regeneration:

| Decision | Model id | Observed sha | Inventory sha | Class | README |
|---|---|---|---|---|---|
| D13 | `SZLHOLDINGS/a11oy-code-r1-candidate` | `541951e09431269c32b7093141a64643eb51113a` | same | `adapter_bundle` | 200 |
| D14 | `SZLHOLDINGS/hatun-24-doctrine-math-r1-candidate` | `470fff332953b352fede85419140b8d76c2122e2` | same | `adapter_bundle` | 200 |

Admission was not granted for any row. `selected` remains null.
