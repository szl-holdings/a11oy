<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Hugging Face public inventory source review

This assistant source review reconciles the public inventory collected at
2026-11-16T23:19:02Z with the source contracts. It remains subject to human PR
review. It is an unsigned metadata review, not a model evaluation, release
approval, execution receipt, or deployment attestation.

The final native collector ran on source `ac68b78415eecd21cf47f09fa725ed8a6e72fc78`
in [run 43978161790](https://github.com/szl-holdings/a11oy/actions/runs/43978161790).
Artifact 14281856187 was checked against its native metadata, run/source binding,
archive size, SHA-256, single archive member, schema, scope, and freshness.
The exact candidate bytes are the updated `docs/huggingface-ecosystem-manifest.json`.

The earlier source-628b collector binding is retained in `review.json`. The final
candidate changed only two broken URL line breaks in the public organization card;
`native-candidate-refresh.json` binds both revisions and the exact semantic delta.

## Reviewed changes

- Public observation: 147 model repositories, 88 datasets, 23 Spaces and 14 native kernels.
- Three governed revisions changed only README or publication metadata. The complete
  before/after public file trees are in `governed-trees.json`; model, adapter,
  tokenizer and executable artifacts remain unchanged at those revisions.
- ReceiptAgent publication source binding was independently checked against all ten
  files at its exact GitHub source revision. Hashes and byte counts match;
  `publication-source-binding.json` records this check without reproducing source bodies.
- Gated repositories retain public-metadata-only observations, null card digests and
  `ACCESS_RESTRICTED`. No authenticated gated text is included in this review.
- Sixteen new model-support rows use real anonymous provider API observations and
  exact-revision file/configuration evidence in `new-model-observations.json`.
  All sixteen report no provider mapping. Thirteen contain standalone weight bundles;
  three contain LoRA adapters under `final/`. No weights were downloaded or executed.
- All 131 earlier model assessments and support-request records are retained unchanged.
  The existing collector refreshed provider observations for all 147 models with
  anonymous metadata GETs; all returned no provider mapping. This replaces stale
  availability observations without changing any qualification or support request.
  `provider-observation-refresh.json` binds the resulting source bytes.
- A repeated live comparison found identical semantic rows but a changed opaque
  pagination cursor. `cursor-drift.json` retains the transport-only difference;
  raw endpoint provenance stays recorded while comparison ignores only valid cursor bytes.
- Twelve no-longer-public Spaces are removed from the current public classification.
  Constellation is recorded as inventory-only/FOLD under the existing keep policy.
  Its owner visibility decision remains pending; this change does not alter visibility.

The ten-Space keep policy, source release decisions, model qualifications, routing,
training eligibility and production authorization remain unchanged. An inventory
row does not grant any of those capabilities. The review's facts and file hashes
are retained in `review.json`. The generated GitHub, Hub and proof-site fragments,
ecosystem stage matrix and model-pretraining projection come from the existing generators.
