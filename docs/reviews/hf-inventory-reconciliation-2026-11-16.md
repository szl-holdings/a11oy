# Hugging Face inventory reconciliation source review

**State: SOURCE_REVIEW_REQUIRED.** This dossier is a reviewable evidence package. It does not refresh governed pins, change visibility or keep policy, regenerate public source projections, or authorize inference.

Source: [`szl-holdings/a11oy@f6e30e83343674e544af0ad83a03c058d9c9d53b`](https://github.com/szl-holdings/a11oy/commit/f6e30e83343674e544af0ad83a03c058d9c9d53b). Branch: `review/hf-inventory-reconciliation-20261116`.

Machine-readable evidence: [hf-inventory-reconciliation-2026-11-16.json](hf-inventory-reconciliation-2026-11-16.json). Exact SHA-256: `01414af229f7973c937195ab5e52ecfd37623a8d47bb3eabb8734b64fb651e2e`. It contains every observed ID, immutable revision, file metadata, card byte hash, preserved prior row, proposed catalog row and validation result.

## Measured public membership

The canonical anonymous collector completed all four namespaces without errors. Its `hf-public-author-membership/v2` predicate includes gated/disabled public metadata and the reserved public `SZLHOLDINGS/README` Space. Models and kernels retain separate namespace identities. Counts are not a total of trained, usable or independently qualified models.

| Namespace | Tracked source | Observed public | Added IDs | Absent tracked IDs |
| --- | ---: | ---: | ---: | ---: |
| models | 131 | 147 | 16 | 0 |
| datasets | 71 | 88 | 17 | 0 |
| spaces | 34 | 23 | 1 | 12 |
| kernels | 14 | 14 | 0 | 0 |

The current Space author-list observation has 22 rows; the explicit public README lookup adds one, yielding 23. This explains the reserved-card count difference. The older 21-plus-README observation was not reused as a fresh count.

Membership SHA-256: `4e19e3e12022fa6b6e1866bcc93df7eef2e70f7a7f3cd09ae3a5df7e6fbe4213`. Scope SHA-256: `26f86974de30ba163e4efdb53d022cf1d8b46dc741d0cca860fa2a17198ae835`.

Evidence assembly records completion at `2026-11-16T23:07:16.156771+00:00`. The original membership wrapper did not record its exact start time, so none is invented. Later model and visibility reads retain individual timestamps. This is a changing estate, not a transactional snapshot.

## Public topology blocker

The [keep-list](https://github.com/szl-holdings/a11oy/blob/f6e30e83343674e544af0ad83a03c058d9c9d53b/docs/series-a/hf-space-keep-list.yaml) retains exactly ten organization Spaces. All ten were observed public. The [contract](https://github.com/szl-holdings/a11oy/blob/f6e30e83343674e544af0ad83a03c058d9c9d53b/static/shared/public-estate-contract.v1.json) and keep-list comments record 13 batch-2 folds and explicitly hold `SZLHOLDINGS/szl-constellation` public pending an owner visibility decision.

Saved-session metadata reads of those 13 IDs and Constellation record only identity and visibility: twelve remain private, Sentra is public again, and Constellation is public. No private file or runtime content was read for those checks.

| State | IDs |
| --- | --- |
| Ten keepers observed public | `a11oy`, `anatomy`, `counsel`, `curation-atlas`, `david-leads`, `finance`, `killinchu`, `lyte`, `szl-foundation-confirmation`, `terra` |
| Recorded folds observed private | `estate-gardener`, `eternal-auditor`, `immune`, `oac-system-health-lab`, `szl-chief-engineer`, `szl-cyber-shield`, `szl-dream-architect`, `szl-energy-ledger`, `szl-infra-warden`, `szl-marketing-1-1`, `szl-provenance-pitch`, `szl-research-council` |
| Recorded fold public again | `sentra` |
| Explicit hold public | `szl-constellation` |

The unchanged [`inventory_only_spaces()` validator](https://github.com/szl-holdings/a11oy/blob/f6e30e83343674e544af0ad83a03c058d9c9d53b/scripts/render_public_estate_alignment.py) allows `ORG_CARD` only for README and requires `FOLD` for every other inventory-only Space. An in-memory candidate removed the twelve private stale declarations and added Constellation as `INVENTORY_ONLY`, `governedKeep=false`, `disposition=HOLD`, citing canonical policy. The validator rejected it: `inventory-only Space must retain its FOLD disposition`.

Assigning Constellation `FOLD` would misstate the explicit hold. Adding a topology binding would introduce a public topology claim. The remaining choice is a narrowly reviewed held-public inventory disposition or the separate owner visibility decision. Neither is implemented. Historical fold evidence is retained separately from current visibility.

## Three governed revision reviews

All three model records remain `GOVERNED_EXACT`. Forge remains auto gated; Lambda manually gated; Nemo public and ungated. The saved SDK session was used only for exact gated README/publication files. Public metadata and Nemo files used anonymous reads. Every examined file was checked against the API Git blob hash, SHA-256 and byte count.

| Model | Old immutable revision | Reviewed new immutable revision | Changed metadata paths |
| --- | --- | --- | --- |
| `SZL-Forge-1.5B-ReceiptAgent` | `d3c0b7e7a3a7242e6cd279bcd8e0bc67c16d7ce2` | `aa357f2a7849bc5f42991d7382f3ae2cffadca53` | `README.md`, `publication.json` |
| `szl-lambda-gate` | `083d760878a3bd2e77cff5ab5c3c348327b0de47` | `613c4a3e28c72c182399b888ffca6693fab3dc8e` | `README.md` |
| `szl-nemo` | `37890b4504cdb11590f7a9fb9ee5054261206e30` | `130cce3ae8c7a047b065749c2604aa37e751c041` | `README.md` |

**Forge ReceiptAgent:** README adds dated curated facts. Publication changes only `observed_hub_revision_before_binding`, `source.revision` and `source_revision`. Ten canonical source files were read through the normal GitHub API at old source `55f56487a52f3f3cf6f32c0e5ee3637660dfc90a` and new source `c94e9218093e0815745cbd5dccaddea1797379a3`: all twenty readbacks match publication byte counts and SHA-256 claims; all ten contents are unchanged. Limited-evidence, unsigned-readback and no-runtime-probe boundaries remain. No new cryptographic signature verification is claimed.

**Lambda model twin:** README points to the distinct native kernel repository and states that the model namespace has no loadable build. Other file metadata is unchanged. This does not turn a model commit into a kernel revision or change their revision classes.

**Nemo:** README retains historical scorer quarantine/no-approved-checkpoint text and adds dated curated facts. Other file metadata is unchanged. No training or runtime qualification is established.

All three reviewed revisions match the public membership capture. Reviewable metadata changes do not authorize routine automation to accept later governed head moves. Unchanged file metadata or Git pointer objects do not verify undownloaded weight bytes.

## Sixteen model source additions

The catalog contains 131 rows; the measured public model namespace has 147. Fresh canonical provider-mapping GETs for all sixteen additions returned `NO_PROVIDER_MAPPING`. Each normalized API capture retains its actual timestamp, exact revision and integrity hash. Exact-revision tree metadata and README byte hashes are included. No weights/adapter payloads were downloaded and no model was run.

Thirteen IDs have removed rows in the [November 15 dossier](https://github.com/szl-holdings/a11oy/blob/f6e30e83343674e544af0ad83a03c058d9c9d53b/docs/reviews/model-inference-inventory-gap-2026-11-15.json). Those entire records remain unchanged under `prior_record`; their old observations are not relabeled as current. Three new candidate repos expose adapter metadata under `final/`. Artifact classes describe observed file structure, not qualification.

| Model addition | Observed immutable revision | Metadata class | Prior reviewed record |
| --- | --- | --- | --- |
| `Nemotron-Mini-4B-Instruct-st` | `89432644e5ff1e64e35e8fe809587319b81e7e02` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-AcousticGovernance-0.8B-v1` | `e3606c990ced50c3f4ed1264d19a70512cf06040` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-AncientMath-0.8B-v1` | `9f432894f63d6cff18db291643537907972b4250` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-FreeEnergy-0.8B-DPO-v1` | `b7d6790d12f0d42e4aa00fdc23460c04ff20c94f` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-FreeEnergy-0.8B-v1` | `c3a6ccf6b243aa0c84d85f49931268f313c4ec83` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-GovernedDistill-0.8B-v1` | `94a70d088dc632af9e14134dd2e09bdf673e17a8` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-Nemotron-Mini-4B-Doctrine-v1` | `a302b62e7ee73990170229e0264559f3e51a2f00` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-Nemotron-Mini-4B-Estate-DPO-v1` | `05657f8fe5b63ebb58b4931baac445013e55776e` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-Nemotron-Mini-4B-Estate-DPO-v2` | `9cbd5527d7f3ca4d41883fddbd814377d53b3c75` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-Nemotron-Mini-4B-Estate-v1` | `272514fd62729db94dc4fb66052753c7ab6397d7` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-Reasoning-0.8B-v1` | `5ec45d7976f836f1fd04a02b6a742f61e0bb3d40` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-Showcase-Systems-v1` | `d20544d382156f8f1afb6208448648e9e481a6e6` | `standalone_weight_bundle` | Preserved removed row |
| `SZL-Specialized-Domains-v1` | `058a617209921299f9934a4863f88553a0eb029d` | `standalone_weight_bundle` | Preserved removed row |
| `absrl-grpo-r1-candidate` | `4f117f77cb410c55785f9ebb3956eae73b938e61` | `adapter_bundle` | No prior row |
| `absrl-grpo-r2-candidate` | `48241a20b45565512dceeaa22a998bead2d5372c` | `adapter_bundle` | No prior row |
| `abstention-doctrine-r1-candidate` | `8934164c409963c34378d1222f756a0e8915d624` | `adapter_bundle` | No prior row |

Each addition has a `proposed_catalog_row`. A 147-row catalog built in memory passed unchanged `a11oy_model_support.validate_document` and exact membership validation. All 131 existing rows and unmatched requests were preserved exactly. No source catalog was written. Candidate canonical digest: `979b4e71efa79fe2b75e2171d512e8588cde8772aca61adb3285e06c982224c4` at generated time `2026-11-16T23:12:44.385069+00:00`. Generated time does not refresh existing observation times.

## Validation and limits

| Check | Result |
| --- | --- |
| Dossier counts, unique IDs, scope and membership digests | PASS |
| Sixteen exact revision/mapping/tree/README bindings | PASS |
| Three old/new governed reviews; eight exact file byte bindings | PASS |
| Twelve canonical A11oy Git object bindings | PASS |
| Ten Forge source claims at both immutable revisions | PASS |
| Existing catalog and tracked public contract | PASS |
| In-memory 147-row catalog with history preserved | PASS |
| Existing contract against observed public membership | REJECTED: 12 private stale declarations; Constellation undeclared |
| Existing 131-row catalog against observed public membership | REJECTED: 16 IDs absent |
| In-memory Constellation HOLD candidate | REJECTED: schema requires FOLD |
| `python -S scripts/test_hf_gated_public_inventory.py` | PASS: 14 tests; exit 0 |
| `python -m unittest discover -s tests -p test_hf_public_inventory.py` | PASS: 52 tests; exit 0 |
| `python scripts/collect_model_inference_support.py --check` | PASS: 131 source rows; exit 0 |

The rejected coverage and hold probes are source-review gates, not a passed full refresh. Provider captures are normalized API evidence, not independent attestations. No runtime probe, support submission, provider grant, promotion, routing change or production authorization is claimed.

## Required source-review sequence

1. Resolve held-public classification while retaining the ten-keeper policy and explicit hold. Review removing the twelve currently private IDs from measured public classification. Preserve historical execution records and current Sentra visibility.
2. Review the sixteen proposed catalog rows as conservative metadata assessments. Preserve prior request/qualification state. New observations require actual GET timestamps.
3. Review the exact three governed changes. Keep governed/gated protections and routine automation unable to accept unreviewed governed moves.
4. After source decisions, regenerate via native collection and the canonical projection workflow, inspect fresh drift and run complete source coverage/parity gates. These observed counts are evidence, not constants to hand-edit into outputs.
5. After the A11oy source change is reviewed and merged, bind the organization profile to exact merged manifest bytes, immutable source commit and Git blob. Run its check and estate parity/source-binding verification. A pre-merge candidate is not current-source parity.

Canonical generation/check commands are in the JSON and bound [workflow](https://github.com/szl-holdings/a11oy/blob/f6e30e83343674e544af0ad83a03c058d9c9d53b/.github/workflows/public-inventory-refresh.yml). They were not used to write projections. The profile follow-on is `scripts/render_profile_inventory.py --manifest <exact-manifest> --source-revision <merged-a11oy-sha> --source-git-blob <manifest-git-blob>`, followed by the same invocation with `--check`.

## Change boundary

Only this Markdown and companion JSON are added. Canonical manifests, matrices, support source, revision policy, public contract, generated projections and provider state remain unchanged. This worktree performs no push, pull request creation, merge or external publication.
