<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Model inference inventory gap review - 2026-11-15

The committed `docs/huggingface-ecosystem-manifest.json` regeneration measured 98
public model-namespace repositories. The committed
`docs/model-inference-support.json` catalog listed 138 model ids. This review
reconciles the catalog to the measured namespace so the source-review coverage
check (`scripts/collect_model_inference_support.py --check`) and the inventory
refresh preflight validate again.

## Removed: 45 retired model-namespace repositories

The following ids were in the catalog but are absent from the current measured
namespace; their rows were removed:

SZLHOLDINGS/Nemotron-Mini-4B-Instruct-st, SZLHOLDINGS/SZL-AcousticGovernance-0.8B-v1,
SZLHOLDINGS/SZL-AncientMath-0.8B-v1, SZLHOLDINGS/SZL-FreeEnergy-0.8B-DPO-v1,
SZLHOLDINGS/SZL-FreeEnergy-0.8B-v1, SZLHOLDINGS/SZL-GovernedDistill-0.8B-v1,
SZLHOLDINGS/SZL-Nemotron-Mini-4B-Doctrine-v1, SZLHOLDINGS/SZL-Nemotron-Mini-4B-Estate-DPO-v1,
SZLHOLDINGS/SZL-Nemotron-Mini-4B-Estate-DPO-v2, SZLHOLDINGS/SZL-Nemotron-Mini-4B-Estate-v1,
SZLHOLDINGS/SZL-Reasoning-0.8B-v1, SZLHOLDINGS/SZL-Showcase-Systems-v1,
SZLHOLDINGS/SZL-Specialized-Domains-v1, SZLHOLDINGS/a11oy-v19-substrate,
SZLHOLDINGS/abstain-doctrine-r1, SZLHOLDINGS/brain-navigator-r2-estate-sft-v1,
SZLHOLDINGS/chaski-5050-estate-sft-v1, SZLHOLDINGS/chaski-estate-sft-v1,
SZLHOLDINGS/chaski-r2-estate-sft-v1, SZLHOLDINGS/doctrine-v2-r2-candidate,
SZLHOLDINGS/doctrine1-r1-candidate, SZLHOLDINGS/forge-v3,
SZLHOLDINGS/freeenergy-r1-candidate, SZLHOLDINGS/governed-inference-meter,
SZLHOLDINGS/khipu-abstain-r3-candidate, SZLHOLDINGS/khipu-r3-estate-sft-v1,
SZLHOLDINGS/miniembed-nano-r1-candidate, SZLHOLDINGS/ouroboros-r2-candidate,
SZLHOLDINGS/szl-block-kv, SZLHOLDINGS/szl-brain, SZLHOLDINGS/szl-energy-attest,
SZLHOLDINGS/szl-khipu-kernels, SZLHOLDINGS/szl-maskmod, SZLHOLDINGS/szl-receipt-attn,
SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-dpo-v1, SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-dpo-v2,
SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-sft-v3, SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2-merged,
SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2m-estate-sft-v1,
SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3-estate-sft-v1, SZLHOLDINGS/szl-specdecode,
SZLHOLDINGS/szl-triage-qwen3.5-0.8b-lora, SZLHOLDINGS/szl-triage-qwen3.5-0.8b-lora-study5,
SZLHOLDINGS/willay-r1-candidate, SZLHOLDINGS/willay-r2-candidate.

## Preserved discussion evidence for retired models

- Discussion 10649 (`PRIOR_DISCUSSION`, author betterwithage, recorded open) for the
  retired `SZLHOLDINGS/a11oy-v19-substrate` moved unchanged to
  `unmatched_prior_requests`.
- Discussion 12788 was a `VERIFIED_SUBMISSION` for the retired
  `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2-merged`. The catalog contract only
  records `PRIOR_DISCUSSION` rows without submission proof in
  `unmatched_prior_requests`, so the row is recorded there as a prior discussion;
  the full verified readback evidence is preserved here verbatim:
  requested_at 2026-10-04T15:56:34.858230+00:00, readback_at 2026-10-04T15:56:34.986721+00:00,
  model_revision 0ef9ed208b66c258e1d11e9112f0721c3b5c7565,
  body_sha256 23421f091ed4c5f57f3811b573f503b28e897a90fec82989a9ddaee946eaaa0a,
  readback_body_sha256 c6f87678f89baacea7d21a06765d7331ee0568178a48bbfd637259cd051f4567,
  readback_normalization HUB_REMOVED_ONE_TERMINAL_NEWLINE, recorded_status open.

## Added: 5 newly measured model-namespace repositories

The following ids were measured in the namespace and absent from the catalog.
Each was assessed from its public revision file list and a provider-mapping read
(HTTP 200 with an empty object, so `NO_PROVIDER_MAPPING`); each lists a README.md
plus a NumPy artifact bundle with TRAINING_RECEIPT.json, provenance.json,
status.json, and bom/model-bom.cdx.json, so each is a `numpy_model_bundle` row.
No support discussion was submitted for them.

| id | hub revision |
|---|---|
| SZLHOLDINGS/KILLINCHU-EYE | cfa50a3e80d0bd0a7b5f7c5584d71a52c6904f2d |
| SZLHOLDINGS/chakana | 3454b7153b6481e7b9738182a7a846e985376212 |
| SZLHOLDINGS/qantu | cd3e7b1596967638c3138e3a96288d192b6aced0 |
| SZLHOLDINGS/tinku | fff3d37ed54fcb631f9fea6ecbecb6c228fa9b12 |
| SZLHOLDINGS/waman | 54716cf3e06a4305eb193e93e7f496a3d70bde06 |

After this reconciliation the catalog ids equal the 98 measured model ids, the
verified-submission discussions are 12781-12787, 12789, and 12790 (9), and the
model rows carry 4 recorded prior discussions. A row is catalog coverage, not
routing, qualification, promotion, or deployment authority.
## Dossier record

This review carries a JSON dossier,
`docs/reviews/model-inference-inventory-gap-2026-11-15.json`. It records the 5
measured additions with their provider-mapping evidence, the final catalog snapshots
of the 45 removed rows (with their removal reasons and evidence destinations),
and 48 rows that had entered the catalog after 2026-11-11 without a dated
record. This reconciliation absorbs those 48 rows so the recorded catalog
coverage is exact again: 5 additions plus 48 absorbed plus 45 preserved rows
equal the 98 measured catalog ids. No row gains admission, exclusion, routing,
or deployment authority from this record.
