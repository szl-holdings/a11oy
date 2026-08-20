# SZL Proof-Obligation Queue and Receipt-Scoped Formula Crosswalk

Version `0.1.0` is a **local, unpublished release candidate**. Its DOI is
**PENDING**. It has not been uploaded, minted, peer reviewed, independently
replicated, or admitted for model training.

This companion dataset turns the existing formula-admission evidence into a
bounded review queue. It does not create mathematical proof. It preserves the
existing status of each namespace-scoped formula record and makes the next
evidence obligation explicit.

## What is included

| Artifact | Rows | Meaning |
|---|---:|---|
| `data/formula-id-crosswalk.json` | 146 | Byte-identical copy of the canonical formula crosswalk. |
| `data/admission-tranche.jsonl` | 148 | Byte-identical holdout tranche: 146 formula metadata rows and two SZL-Lake evidence rows. |
| `data/source-artifact-receipt.json` | n/a | Byte-identical unsigned content receipt for the source admission artifacts. |
| `data/source-admission-manifest.json` | n/a | Byte-identical fail-closed source admission manifest. |
| `data/proof-obligation-queue.jsonl` | 146 | Deterministic queue derived from the crosswalk and bound to source row receipts. |
| `data/brain-evidence-summary.json` | n/a | Receipt-scoped summary of the local retrieval pilot; no raw Brain text, canonical document text, query text, or per-query output. |

The queue contains 144 action-required records and two audit-only records. Its
status distribution is 115 `OPEN`, 28 `CONDITIONAL`, two
`KERNEL_ACCEPTED`, and one `REFUTED`. All 148 admission-tranche rows are
`HOLDOUT`; zero are training-eligible.

## Why receipt-scoped matters

`F1` through `F23` are reused in two namespaces:

- `puriq-runtime-registry` for executable runtime/numerical statements; and
- `puriq-lean-proof-pack` for Lean/thesis statements.

An identical formula ID is not an identical claim. Every queue row therefore
binds its namespace, claim hash, source row receipt, crosswalk receipt, and
artifact receipt. Proof transfer is false by default. Executability remains a
separate axis and never establishes proof.

## Local build and verification

The builder uses only the Python standard library. It verifies every source
content receipt and file digest before emitting the package.

```powershell
python .\dataset_release\szl-proof-obligation-queue\build_package.py
python -m unittest tests.test_proof_obligation_dataset_release
```

The build is deterministic over the pinned source artifacts. It makes no
network request and performs no training, upload, signing, DOI minting,
deployment, publication, or other external mutation.

## Release gate

The archive shape is prepared, but publication intentionally fails closed.
Before any public deposit:

1. complete item-level rights and license review;
2. obtain explicit human release approval;
3. rerun the builder and focused test in the release commit;
4. create and inspect the archive without changing its bytes;
5. upload only through the approved archive workflow;
6. read the deposited record back and verify every checksum; and
7. replace `PENDING` only with the DOI returned by the archive.

Until those gates pass, do not cite a DOI, describe this as peer reviewed, or
describe any row as training-eligible. See `PROVENANCE.md`, `LIMITATIONS.md`,
and `LICENSE.md` before reuse.
