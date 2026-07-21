---
language:
- en
license: other
base_model: unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit
base_model_relation: adapter
library_name: peft
pipeline_tag: text-generation
inference: false
tags:
- structured-output
- provenance
- abstention
- agentic-ai
- formal-verification
- sovereign-ai
- experimental
---

# SZL-Forge-1.5B — ReceiptAgent profile

> **MODEL PROGRAM - NOT A WEIGHT RELEASE**<br>
> Release: `NOT_PROMOTED` | Quality: `NOT_ESTABLISHED` | Weights: `NOT_CREATED` | Inference: `UNAVAILABLE`

**A small sovereign agent that must carry its evidence, uncertainty, formula status, and execution boundary inside every response.**

This card is the prerelease contract for `SZL-Forge-1.5B-ReceiptAgent-v1`, the first governed profile in the SZL-Forge family. It is intentionally published before weights so that the model is judged against a frozen contract rather than a story written after training. A card-only repository must never be counted as a loadable model.

## Why this model should exist

Most language models optimize the answer. ReceiptAgent is designed to optimize the **verifiability of the decision boundary**:

```text
retrieve -> propose -> bind evidence -> preserve formula status
         -> quantify uncertainty -> abstain or request approval
         -> external policy gate -> external execution -> signed receipt
```

The model does not execute tools, sign receipts, prove theorems, or decide whether its own evidence is legally admissible. Those powers remain outside the weights in A11oy's governed runtime. The model proposes a schema-valid object; independent services validate, approve, execute, observe, and receipt it.

### The differentiator

ReceiptAgent is not positioned as a Claude imitation, an "uncensored" derivative, or a generic chat fine-tune. Its release target is a compact, locally runnable agent with five measurable properties:

1. **Evidence binding** - an answered claim references admitted, content-addressed evidence.
2. **Status preservation** - a conjecture, executable check, reported result, and kernel-checked theorem remain different types.
3. **Calibrated restraint** - unsupported requests produce typed abstention, never confident filler.
4. **Proposal-only agency** - tool calls require an external human/policy gate and cannot contain a fabricated execution receipt.
5. **Attested identity** - lineage comes from immutable revisions, hashes, signatures, and transparency records, not from what the model says it is.

## Architecture boundary

| Layer | Role | Inside the weights? |
|---|---|---:|
| Qwen2.5 1.5B base | Language and instruction prior | Yes |
| ReceiptAgent PEFT adapter | Unsigned structured draft proposals | Planned |
| 9,464-node A11oy Brain | Retrieval and evaluation substrate | No |
| Formula crosswalk / Lean / mathlib status | Namespaced evidence and verification targets | No |
| Ouroboros loop | Retrieve, verify, approve, observe, learn orchestration | No |
| Deterministic ReceiptAgent runtime | Resolve evidence/formulae, bind hashes, and build the final envelope | No |
| A11oy policy gates | Authorization and effect control | No |
| DSSE/in-toto receipt layer | Signing, identity, and replay verification | No |

Keeping these controls outside the model is deliberate. It prevents a weight artifact from grading its own proof, granting its own authority, or manufacturing its own receipt.

## Exact lineage

| Artifact | Identity | Current meaning |
|---|---|---|
| Base | `unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit` | Reported Apache-2.0 Qwen2.5-derived base |
| Base revision | `d2f2dd02b071701d5100a04a7a49d6fb0bd305b7` | Immutable revision required for reproduction |
| Existing local SFT adapter | `sha256:682e2f0ea480d47c284b9de12c2e3d2d5170934c065e82fc375e3f069b4730ac` | Experimental predecessor; not established as ReceiptAgent |
| ReceiptAgent weights | Not created | A new training and artifact receipt is required |

The existing adapter showed a directional loss improvement on a 16-row observation, but that result does not establish general quality, safety, evidence binding, or ReceiptAgent behavior.

## Data boundary: what is and is not being trained

| Source | Observed | Train-admitted | Current state |
|---|---:|---:|---|
| Existing SFT dataset | 167 rows | 0 approved for reuse | Rights/privacy/contamination review incomplete |
| A11oy Brain | 9,464 raw nodes | 0 | All raw nodes training-quarantined |
| Formula admission | 146 formula crosswalk records + 2 SZL-Lake evidence records = 148 holdout rows | 0 | Frozen holdout; namespace/status evaluation only |
| ORPO candidate | 12 qualification checks | 0 | 0/12 passed; quarantined |

The Brain and formula system can make the released model more useful **without being copied into the weights**. They remain external retrieval, holdout, contradiction, freshness, and proof-status infrastructure. A future training curriculum must be newly assembled from owned or explicitly licensed rows with item-level provenance, deduplication, contamination analysis, and immutable split receipts.

No card may claim training on "all 200 formulas," the Brain, Lean, mathlib, GitHub, publications, or Hugging Face until row-level admission evidence proves the exact statement. The current repository evidence supports 146 formula crosswalk records plus 2 SZL-Lake evidence records in a 148-row holdout tranche, not a verified 200-formula training set.

## Two-stage output contract

The adapter is intended to be trained to emit only `szl.forge-receipt-draft.v1`; ReceiptAgent-specific weights do not yet exist. It cannot admit evidence, grant proof status, authorize execution, or sign a receipt. `receipt_runtime.py` validates a candidate draft, resolves identifiers against immutable catalogs, applies policy, computes canonical hashes, and builds `szl.receipt-agent-output.v1`. It can validate and bind model identity fields supplied in a caller-provided external run-receipt mapping; it does not independently query or authenticate the serving runtime, so public promotion still requires a trusted model-load receipt verifier.

An `ANSWERED` final envelope is impossible unless the runtime cryptographically verifies a replay-protected receipt binding the draft, answer, model identity, request, evidence set, formula set, calibration, tool proposal, and policy snapshot. Otherwise the bridge returns a typed abstention. The local bridge supports non-stub HMAC-SHA256 DSSE for experimental operation; public promotion still requires asymmetric DSSE/in-toto attestation and an independently readable transparency-log record. The final envelope separates:

- model identity and release state;
- `ANSWERED`, `ABSTAINED`, or `UNAVAILABLE` status;
- admitted evidence IDs and content hashes;
- namespaced formula IDs and exact proof/status labels;
- calibrated uncertainty and abstention reason;
- a non-executing tool proposal requiring approval; and
- request, evidence-set, policy-snapshot, and external-receipt bindings.

An answered response without at least one `ADMITTED_REFERENCE` is invalid. An abstained or unavailable response cannot carry answer text. A proposed tool action cannot carry an execution receipt. Proof transfer is forbidden unless the formula status and independent verification receipt authorize it. The model itself never emits the signed final envelope.

Illustrative **unavailable** response:

```json
{
  "schema_version": "szl.receipt-agent-output.v1",
  "response_id": "response:unavailable-example-0001",
  "model_identity": {
    "candidate_id": "SZL-Forge-1.5B-ReceiptAgent-v1",
    "release_state": "NOT_PROMOTED",
    "base_repository": "unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit",
    "base_revision": "d2f2dd02b071701d5100a04a7a49d6fb0bd305b7",
    "adapter_sha256": null
  },
  "status": "UNAVAILABLE",
  "answer": null,
  "evidence": [],
  "formulae": [],
  "uncertainty": {
    "confidence": null,
    "calibration_state": "NOT_EVALUATED",
    "basis": "No promoted ReceiptAgent artifact exists and no inference was run."
  },
  "abstention": {
    "required": true,
    "code": "MODEL_UNAVAILABLE",
    "detail": "The release program is a specification only. Training, evaluation, attestation, publication, and promotion remain incomplete."
  },
  "tool_proposal": {
    "state": "NONE",
    "tool_id": null,
    "arguments_sha256": null,
    "requires_human_approval": true,
    "execution_receipt_id": null
  },
  "receipt_binding": {
    "state": "NOT_AVAILABLE",
    "request_sha256": "7a4e67e8fc8037691c60e8fe7a869f268e9b3bc375421850fd5770e03e66d121",
    "evidence_set_sha256": null,
    "policy_snapshot_sha256": "4755a60949f3a7636e70185b8048c6341915b9f6f403711730d89f5ac83b0687",
    "receipt_id": null
  }
}
```

This example is intentionally not impressive text. It demonstrates the behavior that matters when the system cannot support an answer.

## Preregistered evaluation

The release compares three immutable columns under identical prompts, decoding parameters, evidence snapshots, policy, and hardware reporting:

1. exact pinned base;
2. exact existing SFT adapter; and
3. exact future ReceiptAgent artifact.

| Suite | Promotion question | Current state |
|---|---|---|
| Schema conformance | Does every response validate? | `NOT_RUN` |
| Evidence existence and support | Do cited hashes exist and support the claim? | `NOT_RUN` |
| Formula namespace/status | Are collisions and proof states preserved? | `NOT_RUN` |
| Required abstention | Does the model refuse unsupported/stale/quarantined evidence? | `NOT_RUN` |
| Injection resistance | Can evidence or retrieved text override policy? | `NOT_RUN` |
| Tool authorization | Does the model avoid unauthorized execution claims? | `NOT_RUN` |
| Receipt integrity | Does it reject malformed or invented receipts? | `NOT_RUN` |
| Identity honesty | Does it avoid behavioral self-provenance claims? | `NOT_RUN` |
| General instruction following | What capability is retained outside the narrow task? | `NOT_RUN` |
| Runtime profile | Load, p50/p95 latency, VRAM, energy, restart | `NOT_RUN` |

The catastrophic-error budget is **zero** for fabricated receipts, unauthorized tool execution, proof-status promotion, evidence-hash mismatch, or identity misrepresentation. Latency is reported as an operational metric, never a quality score.

## Intended use

- local and sovereign evidence-bound assistants;
- human-reviewed research and engineering workflows;
- retrieval systems that need explicit support/contradiction/uncertainty labels;
- formula and theorem-status navigation with independent formal verification; and
- proposal-only agents whose actions are authorized and receipted elsewhere.

## Out-of-scope use

- autonomous execution or self-approval;
- claims of new mathematical proof without independent kernel verification;
- legal, medical, financial, defense, or safety-critical decisions without a qualified human decision-maker;
- identity or lineage claims inferred from behavioral prompts;
- surveillance, targeting, or weapon release decisions; and
- presentation as Claude, Anthropic technology, or any unrelated vendor model.

## Known limitations

- No ReceiptAgent-specific weights exist yet.
- The existing adapter's broad quality, calibration, safety, and deployment behavior are unestablished.
- Quantization, prompts, retrieval snapshots, and hardware can materially change behavior.
- Retrieval provenance does not by itself establish copyright, permission, freshness, or truth.
- Formal verification applies only to the exact checked statement and assumptions; it does not transfer automatically to generated prose.
- A signed receipt proves what a system recorded, not that the underlying world claim is true.

## Release gates

The adapter will be published only after all of the following are independently readable:

- admitted curriculum manifest with row-level rights and immutable splits;
- training code commit, environment lock, seed, hardware, and run receipt;
- base, tokenizer, template, adapter, dataset, schema, and evaluation hashes;
- reload test on a clean runtime;
- completed three-way evaluation with zero catastrophic events;
- measured load/latency/VRAM/energy/restart receipts;
- human review of the model card, dataset statement, licenses, and limitations;
- DSSE/in-toto attestation and transparency-log reference; and
- a working fail-closed Space whose model-load and inference probes pass separately.

## Planned Hugging Face release family

- `SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent` - PEFT adapter; never a renamed full base
- `SZLHOLDINGS/SZL-Forge-ReceiptAgent-Eval` - frozen rights-reviewed evaluation set
- `SZLHOLDINGS/SZL-Forge-ReceiptAgent-Schemas` - schemas and conformance fixtures
- `SZLHOLDINGS/SZL-Forge-ReceiptAgent-Demo` - fail-closed Space with live receipts
- `SZLHOLDINGS/SZL-Forge-Collection` - created last, after every member resolves

All five targets are currently `PLANNED_NOT_CREATED`.

## Reproduction contract

The final release must disclose exact commands and hashes for environment creation, adapter load, schema validation, evaluation, quantization, and receipt verification. A reproduction that changes base revision, tokenizer, chat template, quantization, dataset split, or decoding configuration is a new experiment and must produce a new receipt.

## Licensing and non-affiliation

The base license is reported by current local evidence as Apache-2.0. The adapter and dataset release licenses remain `PENDING_LEGAL_AND_LINEAGE_REVIEW`. Third-party traces or outputs cannot enter training without explicit rights and policy review.

SZL Holdings is not affiliated with, sponsored by, or endorsed by Alibaba/Qwen, Unsloth, Hugging Face, Anthropic, or Claude. All third-party marks belong to their respective owners.

## Citation

A stable citation will be added only after a promoted release and verified archival record exist. Until then, cite the repository commit containing this preregistration and identify it as a **model program specification, not a released model**.

## Status

The ambitious part is not a larger claim. It is a smaller model with a harder release contract. Today that contract exists; the model does not. The next milestone is an admitted curriculum and a receipted training/evaluation run, not a promotional upload.
