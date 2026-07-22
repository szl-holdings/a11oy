# SZL-Forge-1.5B — ReceiptAgent release program

This directory originated as a bounded, honesty-first release program for a
proposed model named **SZL-Forge-1.5B-ReceiptAgent-v1**. A public, weight-bearing
candidate now exists at `SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent`; that external
artifact does not retroactively satisfy this repository's broader admission or
promotion gates. The exact public revision qualified below remains a candidate,
not a promoted A11oy runtime dependency.

The purpose is narrow: a small model that produces a strict unsigned draft
containing an answer or abstention, evidence IDs, formula references,
uncertainty, and a non-executing tool proposal. Deterministic runtime code in
`receipt_runtime.py` resolves authoritative records, enforces policy, binds
canonical hashes, and builds the final response envelope only after verifying
a replay-protected DSSE receipt over every decision-bearing component. Its
HMAC-SHA256 path is experimental; public promotion still requires asymmetric
attestation and transparency logging. A useful release would make those controls measurable. It would not
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
| Formula admission | 146 formula crosswalk records + 2 SZL-Lake evidence records = 148 holdout tranche rows | All 148 are holdout; zero are admitted to train. Formula IDs are namespace-scoped. |
| Public candidate | HF revision `fa73dc1bd8eeece727d0b5c1db52448ec0703e8b`; raw `model.safetensors` SHA-256 `a797592fb35c32cc6ebf5739c0a1d9312123300acaf09987d207d86196bc6e7d` | `MEASURED` only by the bounded CPU contract qualification below; not promoted or deployed by this repository. |

## Exact-revision CPU qualification (2026-07-21)

`qualification/heldout-contract-v1.json` freezes the public artifact, public
source revision, output schema, six postdated project-authored prompts, greedy
decoding, and pass thresholds before inference. The deterministic runner
`qualify_public_candidate.py` then verifies:

- the 3,087,467,144-byte model and 147,770,496-byte adapter by raw and
  training-receipt directory digests;
- every inference-affecting config, tokenizer, chat template, generation
  config, and adapter config by exact byte count and SHA-256 at the frozen
  candidate revision;
- the byte-bound Apache-2.0 license file (a declared license observation, not a
  legal opinion);
- the owner-signed Ed25519 training/evaluation receipt chain against the
  repository-declared key;
- the exact `szl-holdings/szl-forge` source commit, evaluator/schema Git blobs,
  and five public curriculum hashes; and
- absence of every held-out prompt as exact text in those public curriculum
  blobs. Semantic contamination and private-corpus absence are not established.

The one bounded CPU run produced 3/3 raw JSON-schema-valid drafts, 3/3 valid
proposal-only boundaries, 3/3 `REFUSE`-prefixed adversarial responses, and zero
detected catastrophic execution/finalization events. Its unsigned local receipt
is `qualification/fa73dc1-cpu-qualification-receipt.json`, with canonical
SHA-256 `5abc85af639477f32951784c372beef33a608375586c111e517692207074ba7b`.

This is a narrow structural-contract result. It does **not** establish endpoint
existence, evidence grounding, citation correctness, general capability,
private-set noncontamination, hosted availability, deployment, promotion, or
human release approval. In particular, schema-valid evidence labels remain
claims to verify externally; this run does not resolve or probe the cited
endpoints. The local receipt is deliberately unsigned because no approved
independent qualification key was provided.

The current Brain and formula corpus are valuable as a governed retrieval and
evaluation substrate. They are not a training corpus until item-level rights,
provenance, revisions, freshness, deduplication, and split assignments pass.

## Contract

The adapter contract is `szl.forge-receipt-draft.v1`; the final runtime contract
is `szl.receipt-agent-output.v1`. They are deliberately different. The model
proposes. The deterministic runtime validates, resolves, gates, and receipts.

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
- 146 formula records plus 2 SZL-Lake evidence records reserved as 148/148 holdout rows, with F1-F23 namespace collisions;
- the ORPO candidate failing all 12 qualification checks;
- no independently pinned release key, third-party provenance review, or local
  promotion approval for the externally published candidate;
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

## Hugging Face family

The proposed family is declared in `release-manifest.json`. The first public
candidate is now externally observable; the remaining family members stay
planned until independently verified:

- `SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent` — public candidate carrying a
  merged safetensors artifact plus a separately bound adapter directory;
- `SZLHOLDINGS/SZL-Forge-ReceiptAgent-Eval` — frozen, rights-reviewed evaluation set;
- `SZLHOLDINGS/SZL-Forge-ReceiptAgent-Schemas` — schemas and conformance fixtures;
- `SZLHOLDINGS/SZL-Forge-ReceiptAgent-Demo` — fail-closed Space with live load and inference receipts; and
- `SZLHOLDINGS/SZL-Forge-Collection` — collection created last, after every member exists.

`release-manifest.json` remains a preregistration snapshot and still marks every
target `PLANNED_NOT_CREATED`; it must not be silently rewritten into historical
evidence. Live inventory now contradicts that state for the first candidate,
which is why this qualification binds the external revision explicitly. The
other IDs require separate live verification. A model card alone must not be
presented as a weight-bearing model.

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
