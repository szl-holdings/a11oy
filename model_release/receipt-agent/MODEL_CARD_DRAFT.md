---
language:
- en
license: other
base_model: unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit
base_model_relation: adapter
library_name: peft
pipeline_tag: text-generation
tags:
- structured-output
- provenance
- abstention
- experimental
---

# SZL-ReceiptAgent-1.5B — draft only

> **Release state: NOT_PROMOTED. Quality: NOT_ESTABLISHED. Weights: NOT
> CREATED. Inference: UNAVAILABLE.** This document is a release-card template,
> not a published model card.

## Proposed purpose

SZL-ReceiptAgent-1.5B is proposed as a narrow, Qwen2.5-derived PEFT adapter for
producing the `szl.receipt-agent-output.v1` response envelope. The intended
capability is structured evidence and abstention behavior, not open-ended model
impersonation, autonomous execution, theorem proving, or proof discovery.

## Lineage

- Base: `unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit`
- Immutable base revision: `d2f2dd02b071701d5100a04a7a49d6fb0bd305b7`
- Existing SFT adapter under review: SHA-256
  `682e2f0ea480d47c284b9de12c2e3d2d5170934c065e82fc375e3f069b4730ac`
- Relation to existing adapter: that adapter is a measured local candidate but
  is not established as ReceiptAgent. A new training receipt and artifact are
  required.

The base license is reported by current local evidence as Apache-2.0. The
adapter's final release license remains `PENDING_LEGAL_AND_LINEAGE_REVIEW`.

## Data statement

No ReceiptAgent curriculum is admitted yet. The existing adapter used 167 rows,
but its license, privacy, and contamination review is incomplete. The 9,464
current raw Brain nodes are all quarantined from training. The 148 formula
crosswalk rows are all holdout, with zero train rows. The ORPO candidate passed
0 of 12 qualification checks and remains quarantined.

The final card must list every admitted source family, rights basis, row count,
deduplication decision, immutable split, contamination analysis, and manifest
digest. It must not say the model was trained on the Brain, formulas, Lean,
Mathlib, publications, GitHub, or Hugging Face unless a row-level admission
receipt proves that claim.

## Evaluation

The prerelease matrix compares the exact pinned base, exact existing SFT
adapter, and exact future ReceiptAgent artifact. All ReceiptAgent suites are
currently `NOT_RUN`. A historical 16-row loss observation is directional only
and does not establish general quality or ReceiptAgent capability.

Promotion requires strict schema validity, valid evidence bindings, formula
namespace/status preservation, calibrated abstention, injection resistance,
no unauthorized tool execution, malformed-receipt refusal, and identity
honesty. The catastrophic-error budget is zero.

## Intended use

- experimental research on evidence-bound structured responses;
- offline evaluation of abstention and provenance controls; and
- human-reviewed tool proposals that are executed by a separate governed
  system only after approval.

## Out-of-scope use

- autonomous tool execution;
- claims of mathematical proof without independent formal verification;
- legal, medical, financial, defense, or safety-critical decisions without a
  qualified human decision-maker;
- model identity claims based only on behavior; and
- presentation as Claude, Anthropic technology, or any unrelated vendor model.

## Limitations

No specialized model artifact exists yet. The existing adapter's broad quality,
calibration, safety, provenance accuracy, formula-status preservation, and
deployment behavior are unestablished. Quantization, local hardware, and
structured prompting can change observed behavior and must be reported with
each receipt.

## Provenance and non-affiliation

The promoted artifact must publish exact cryptographic fingerprints, a signed
DSSE/in-toto attestation, and a transparency-log reference. Behavioral
fingerprints may supplement regression testing but are not proof of identity.

SZL Holdings is not affiliated with, sponsored by, or endorsed by Alibaba/Qwen,
Unsloth, Hugging Face, Anthropic, or Claude. All third-party marks belong to
their respective owners.
