# SZL-Forge-1.5B — governed training family

`SZL-Forge-1.5B` is the public family name. `ReceiptAgent-v1` is its first
profile. This directory contains an executable **offline, fail-closed** QLoRA
path; it does not contain a newly trained model and does not establish quality.

## What is trainable now

Only the deterministic, project-authored policy/schema curriculum under
`generated/` can enter gradients. It is built from `curriculum-source.json` and
the unsigned model-draft schema. The draft/final split is intentional: the
model proposes evidence IDs, formula references, an abstention, and a tool
request; deterministic A11oy code validates the proposal, computes hashes,
applies policy, requires human approval, and signs the final ReceiptAgent
envelope.

The following are **not training data**:

- 9,464 raw Brain nodes: all are quarantined; use them through retrieval after
  admission and use their receipts in evaluation.
- 148 formula crosswalk rows: all are holdout; use them only for frozen
  namespace/status-preservation evaluation.
- the historical 167-row adapter corpus: rights/privacy/contamination review is
  incomplete.
- the ORPO corpus/candidate: qualification is 0/12 and remains quarantined.

This boundary is what prevents a larger-looking corpus from silently destroying
the validity of later claims.

## Build and inspect without a GPU

```powershell
python model_release/szl-forge/szl_forge_training.py build
python model_release/szl-forge/szl_forge_training.py preflight `
  --base-snapshot C:\path\to\the\pinned\local\snapshot
```

`preflight` verifies every curriculum hash and every pinned base-file hash. It
does not sample the GPU unless `--check-gpu` is supplied and never starts a
model load.

## Queue a real governed run

The queue has two GPU gates: a three-sample probe, followed by an eleven-sample
training soak. Thresholds are fixed at at least 6,656 MiB free, at most 10%
utilization, and at most 60 C. The queue never closes applications, downloads a
model, uploads an artifact, or weakens a threshold.

```powershell
.\model_release\szl-forge\Invoke-SZLForgeQueue.ps1 `
  -Mode queue-train `
  -BaseSnapshot 'C:\path\to\the\pinned\local\snapshot' `
  -OutputDirectory 'C:\path\to\szl-forge-run' `
  -Confirmation 'TRAIN_SZL_FORGE_RECEIPT_AGENT_1_5B'
```

Heavy imports occur only after curriculum, base identity, confirmation, and GPU
admission pass. The runner forces Hugging Face/Transformers/Datasets offline,
trains a bounded 64-step QLoRA adapter, records artifact hashes and measured GPU
memory, reloads the adapter from disk, and runs the frozen eight-row
schema-conformance evaluation. A failed reload/evaluation remains
`NOT_PROMOTED`.

## Required before release

This training path is necessary, not sufficient. Public promotion still needs:

1. all ReceiptAgent preregistered suites, including the untouched 148-row
   formula holdout and admitted Brain retrieval receipts;
2. zero catastrophic identity, evidence, proof-status, receipt, and tool errors;
3. adapter/base/tokenizer/environment hashes, DSSE/in-toto attestation, and a
   readable transparency-log record;
4. legal/license review and human approval bound to the exact adapter digest;
5. a model card reporting measured results and failures, not aspirations.

The existing M1 adapter is a separate historical candidate. It must not be
renamed `SZL-Forge` or `ReceiptAgent` without passing this contract.
