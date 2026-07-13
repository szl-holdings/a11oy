# SZL-ReceiptAgent-1.5B release program

This directory specifies a bounded, honesty-first release program for a
proposed model named **SZL-ReceiptAgent-1.5B**. It is a release design, not a
model release. No ReceiptAgent-specific training run, weight artifact,
evaluation result, signature, upload, deployment, or promotion is represented
here.

The purpose is narrow: a small model that can produce a strict response
envelope binding an answer or abstention to evidence IDs, formula namespaces
and statuses, uncertainty, a non-executing tool proposal, and an external
receipt. A useful release would make those controls measurable. It would not
make a generic chat model rare, prove the model's identity from behavior, or
turn retrieved text into a mathematical proof.

## Current measured boundary

| Item | Current evidence | Release implication |
|---|---|---|
| Base | `unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit` at `d2f2dd02b071701d5100a04a7a49d6fb0bd305b7` | Lineage must remain explicit. |
| Existing SFT adapter | SHA-256 `682e2f0ea480d47c284b9de12c2e3d2d5170934c065e82fc375e3f069b4730ac` | Identifies the existing candidate only; it is not a new ReceiptAgent artifact. |
| Existing SFT data | 167 rows | License, privacy, and contamination review is incomplete, so reuse is blocked. |
| Existing evaluation | Incomplete | A 16-row loss direction exists, but general quality is not established. |
| ORPO candidate | 0/12 qualification checks | Quarantined; cannot influence release. |
| Brain | 9,464 raw nodes | All 9,464 are training-quarantined; zero raw-node text rows are admitted to train. |
| Formula crosswalk | 148 rows | All 148 are holdout; zero are admitted to train. Formula IDs are namespace-scoped. |
| Proposed model | No ReceiptAgent weight artifact | `NOT_PROMOTED`, `NOT_ESTABLISHED`, and unavailable for inference. |

The current Brain and formula corpus are valuable as a governed retrieval and
evaluation substrate. They are not a training corpus until item-level rights,
provenance, revisions, freshness, deduplication, and split assignments pass.

## Contract

`receipt-agent-output.schema.json` requires each response to separate:

1. exact model identity and release state;
2. `ANSWERED`, `ABSTAINED`, or `UNAVAILABLE` status;
3. answer text, which must be `null` when abstaining or unavailable;
4. evidence IDs, content hashes, support roles, and admission states;
5. formula ID, namespace, status, and explicit proof-transfer decision;
6. confidence and calibration state;
7. a typed abstention reason;
8. a proposal-only tool request that always requires human approval and cannot
   contain an execution receipt; and
9. request, evidence-set, policy, and external receipt bindings.

An `ANSWERED` response must have at least one `ADMITTED_REFERENCE`. The example
is deliberately `UNAVAILABLE`; it contains no fabricated answer or receipt.

## Admission gates

`admission-manifest.json` is fail-closed. Promotion requires every gate to pass
and permits zero catastrophic errors. Current blockers are:

- incomplete row-level governance for the existing 167-row dataset;
- 9,464/9,464 raw Brain nodes quarantined from training;
- 148/148 formula rows reserved for holdout, with F1-F23 namespace collisions;
- the ORPO candidate failing all 12 qualification checks;
- no ReceiptAgent-specific training receipt or weights;
- no frozen three-way evaluation;
- no signed DSSE/in-toto provenance or transparency-log record; and
- unresolved release/data licensing and no human release approval.

Passing base and adapter digest checks proves only which existing artifacts are
being discussed. It does not promote them or establish ReceiptAgent behavior.

## Evaluation design

`evaluation-manifest.json` fixes a three-column comparison:

- exact pinned base;
- exact existing SFT adapter; and
- exact future ReceiptAgent artifact.

The same frozen prompts, decoding parameters, tool policy, evidence snapshot,
and formula crosswalk must be used for all three. Required suites cover strict
schema validity, evidence existence, false support, formula status and
namespace preservation, required abstention, stale/quarantined-source refusal,
prompt injection, unauthorized tools, malformed receipts, identity honesty,
and separately reported p95 latency. Every matrix cell is currently `NOT_RUN`.

Latency is an operational measurement, not a quality score. Behavioral
fingerprints are supplemental regression signals, not proof of weight identity.

## Hugging Face family — planned, not created

The proposed family is declared in `release-manifest.json`:

- `SZLHOLDINGS/SZL-ReceiptAgent-1.5B` — PEFT adapter, never a renamed full base;
- `SZLHOLDINGS/SZL-ReceiptAgent-1.5B-Eval` — frozen, rights-reviewed evaluation set;
- `SZLHOLDINGS/SZL-ReceiptAgent-Schemas` — schemas and conformance fixtures;
- `SZLHOLDINGS/SZL-ReceiptAgent-Demo` — fail-closed Space with live load and inference receipts; and
- `SZLHOLDINGS/SZL-ReceiptAgent-Collection` — collection created last, after every member exists.

Each ID is `PLANNED_NOT_CREATED`. The family should be published only after
independent model-load, output-conformance, and inference receipts pass. A
model card alone must not be presented as a weight-bearing model.

## Identity, license, and naming

The base license is reported by existing local evidence as Apache-2.0. Adapter
and dataset release licenses remain blocked pending lineage and row-level rights
review. Promotion also requires hashes for base files, adapter config and
weights, tokenizer, chat template, dataset manifest and split, code commit,
environment lock, evaluation manifest, and output schema.

The final release must carry a signed DSSE/in-toto statement and an
independently readable transparency-log entry. It must disclose Qwen2.5-derived
lineage and non-affiliation with Alibaba/Qwen, Unsloth, Hugging Face, Anthropic,
and Claude. It must never use another vendor's model name to obscure lineage.

## Bounded implementation sequence

1. Resolve item-level data rights; do not admit raw Brain or formula holdout rows.
2. Build a new, owned or explicitly licensed ReceiptAgent curriculum that targets the v1 contract.
3. Preregister immutable train/eval splits and the full three-way evaluation matrix.
4. Train once from the pinned base and capture code, environment, seed, GPU, and artifact receipts.
5. Run every suite against base, existing SFT, and the new artifact under identical settings.
6. Stop on any catastrophic event or failed admission gate.
7. Have a human reviewer approve the model card, data statement, licenses, and evidence bundle.
8. Sign and log provenance; publish the adapter, eval data, schemas, and working Space; create the collection last.

## Local validation

The focused test uses only the Python standard library:

```powershell
python -m unittest tests.test_receipt_agent_release_program
```

It checks the JSON documents against the dependency-light schema subset used
here, asserts the exact repository facts, and exercises fail-closed contract
conditions. It performs no network calls or external mutations.
