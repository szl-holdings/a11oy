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

## Later same-day pass: 16 further measured rows and 7 restored rows

The committed manifest regenerated again at 2026-11-15T03:48:57Z and now
inventories 121 public model repositories. A later pass the same day read
the 23 ids that had no support row. 16 of them are repositories no earlier
record had covered; 7 of them are rows this record removed in its first
pass as absent from the then-measured inventory, and the regenerated
manifest now re-includes them at new revisions, so their removals are
reversed and their rows are restored with fresh measured observations.
Each anonymous public read returned an empty inference-provider mapping at
the revision recorded in the committed manifest. No row gains admission,
exclusion, routing, or deployment authority from this extension:
decisions D06-D21 are recorded as `RECORDED_NO_PROVIDER_MAPPING` and
D22-D28 as `RECORDED_RESTORED_NO_PROVIDER_MAPPING`, each with admission
`NOT_GRANTED`, blocked by the same two missing proofs as D01-D05.

| Model id | Disposition | Artifact class | Observed revision |
| --- | --- | --- | --- |
| SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent-laptop-lora | added | adapter_bundle | d61c815f53be5c3a551fa90fec7b8a2e3a61045e |
| SZLHOLDINGS/SZL-Khipu-1.5B-laptop-lora | added | adapter_bundle | e31d71ac3d5e09b0ebc8bdd6a22d4cdea31232f9 |
| SZLHOLDINGS/brain-navigator-r2-laptop-lora | added | adapter_bundle | 60b6fdd72bb745bb8b195f3a1e9120f2e05a0562 |
| SZLHOLDINGS/chaski-5050-laptop-lora | added | adapter_bundle | 7072215ed8bb74d9b9996748467d0d1cc79a56cf |
| SZLHOLDINGS/chaski-laptop-lora | added | adapter_bundle | 824aa4610537b76e646b2ab14b1cff8812317e7d |
| SZLHOLDINGS/chaski-r2-laptop-lora | added | adapter_bundle | cfff1cd2274af706028c5c6a1c08eeaf2a1d2695 |
| SZLHOLDINGS/chaski-r4-laptop-lora | added | adapter_bundle | d3da618277263d012ac5fbfb50cecd6553380cd3 |
| SZLHOLDINGS/doctrine-math-r1-candidate | added | non_provider_artifact | 640062012ff0d003c74239911272d58d752ac820 |
| SZLHOLDINGS/khipu-r3-laptop-lora | added | adapter_bundle | 0cd399061064bdf30b2636b4815bc61214951b63 |
| SZLHOLDINGS/qwen2.5-0.5b-laptop-lora | added | adapter_bundle | 29f815ba8069d1fc9060b5e906e83cc8a7a1c2eb |
| SZLHOLDINGS/receiptagent-v3-laptop-lora | added | adapter_bundle | a009f6cc5195c834475a368fb52310284d04c43c |
| SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2-laptop-lora | added | adapter_bundle | 97809211c5470d1abb9dddb1d4ccba21fa94c0f0 |
| SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2-merged-laptop-lora | added | adapter_bundle | f68bb5cf1e51cbdbaf7a929ed140af81421138fa |
| SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3-candidate | added | adapter_bundle | 5d33565030f04ac1bf0b2fdb012b90f238cc5dc0 |
| SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3-laptop-lora | added | adapter_bundle | 033108dd8a6a0205995216d3849387fcc3ec36d1 |
| SZLHOLDINGS/szl-triage-qwen3.5-0.8b-lora-laptop-lora | added | adapter_bundle | 17592f5fff6ee1119986af297dc16b745ed2b4c5 |
| SZLHOLDINGS/brain-navigator-r2-estate-sft-v1 | restored | standalone_weight_bundle | 1943a58d83a8fbe3aa974dd243233d0354defcc8 |
| SZLHOLDINGS/chaski-5050-estate-sft-v1 | restored | standalone_weight_bundle | b8034b05d39f3aff2cf059918d1b020129d0de15 |
| SZLHOLDINGS/chaski-estate-sft-v1 | restored | standalone_weight_bundle | bb457141f3ac910b41e1b951d5b3d735cbec2838 |
| SZLHOLDINGS/chaski-r2-estate-sft-v1 | restored | standalone_weight_bundle | 532ef3fb751a828c6211af252c68025995b266c9 |
| SZLHOLDINGS/khipu-r3-estate-sft-v1 | restored | standalone_weight_bundle | 882ac37445b6cefa865992474737246758434b44 |
| SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2m-estate-sft-v1 | restored | standalone_weight_bundle | ad7833f225c28771b52c34351cebb1b9a95689dc |
| SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3-estate-sft-v1 | restored | standalone_weight_bundle | 7ce8a2303b97b490f33c8b22da013868b4863ef0 |

## Inventory-refresh preparation pass: 10 further measured rows, 1 prior discussion absorbed

The manifest was regenerated again for the public-inventory refresh
preparation and now inventories 131 public model repositories. This pass
read the 10 ids that had no catalog row: an anonymous public file-listing
read and an anonymous provider-mapping read at each measured revision. Every
provider-mapping read returned HTTP 200 with an empty object, so no row
gains admission, exclusion, routing, or deployment authority from this
extension: decisions D29-D38 are recorded as `RECORDED_NO_PROVIDER_MAPPING`,
each with admission `NOT_GRANTED`, blocked by the same two missing proofs as
D01-D28. Because the regenerated manifest re-observed
`SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2-merged` as public, the prior
discussion 12788 moved from the unmatched prior-discussion list into the
model row itself with its evidence preserved verbatim.

| Model id | Disposition | Artifact class | Observed revision |
| --- | --- | --- | --- |
| SZLHOLDINGS/KHIPU-R2-laptop-lora | added | adapter_bundle | ec55c4cbd36243371ecffaeb85e762f0ed2c7f3c |
| SZLHOLDINGS/SZL-Khipu-1.5B-abstain-laptop-lora | added | adapter_bundle | d78c85e2ce1c91fa80d4c25b94c115a8cda31bbf |
| SZLHOLDINGS/WILLAY-laptop-lora | added | adapter_bundle | 85b7dffeca94837eb93b88fb6ebc294b6254cd43 |
| SZLHOLDINGS/forge-v3 | added | standalone_weight_bundle | 0c80e886f7787a59a4ca01a4fc56d74b4711d98a |
| SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-dpo-v1 | added | standalone_weight_bundle | 51319f2213cb9dc1cc1a498967ccbd37117fe740 |
| SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-dpo-v2 | added | standalone_weight_bundle | 119fb1c68ee5a83d0f09d5649e78d432ea4c7eab |
| SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-sft-v3 | added | standalone_weight_bundle | 376a55e6120673d5404a3c7d48a5540a4d7b97b5 |
| SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2-merged | added | standalone_weight_bundle | fe55644363dd1e794a14fe5438903dd626726b4f |
| SZLHOLDINGS/szl-triage-qwen3.5-0.8b-lora | added | adapter_bundle | 94391aef62614a5ec48eb2adeaf1ac4dd24bbfed |
| SZLHOLDINGS/szl-triage-qwen3.5-0.8b-lora-study5-laptop-lora | added | adapter_bundle | 31b32c70a3f52a63c9446b8fd885f8e1023c01ec |
