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
model, uploads an artifact, or weakens a threshold. An exclusive process lease
prevents two Forge runs from passing the soak and loading the GPU concurrently.

```powershell
.\model_release\szl-forge\Invoke-SZLForgeQueue.ps1 `
  -Mode queue-train `
  -BaseSnapshot 'C:\path\to\the\pinned\local\snapshot' `
  -OutputDirectory 'C:\path\to\szl-forge-run' `
  -Confirmation 'TRAIN_SZL_FORGE_RECEIPT_AGENT_1_5B'
```

Heavy imports occur only after curriculum, base identity, confirmation, and GPU
admission pass. The runner pins and measures the Python/Torch/CUDA/package/GPU
identity before model load, forces Hugging Face/Transformers/Datasets offline,
and denies Python socket connections. That socket control is not claimed as an
OS network namespace; native-extension isolation remains `NOT_ESTABLISHED` in
the receipt. A run also refuses to start unless the training-critical Forge,
base-identity, and regression-test paths are clean and bound to a measured Git
commit; unrelated working-tree paths do not weaken or silently broaden that
scope.

Git is an explicit runtime prerequisite for that provenance gate. It may be on
`PATH`, or an absolute reviewed executable path may be supplied through
`SZL_FORGE_GIT` (or the queue's `-GitExecutable` parameter); the executable
itself is hashed into the receipt. An absent or invalid executable is a fatal
gate refusal, never a reason to skip provenance. Preflight reports this as the
separate `SOURCE_CONTROL` check before it begins any GPU sampling.

The admitted train/eval rows and every pinned base-model file are copied into a
private, hash-verified, read-only run snapshot before model load. Training and
reload evaluation consume that snapshot rather than the mutable cache path.
The fixed admission thresholds are sampled again after the private copy and
once more immediately before model load, closing the staging/import contention
window without weakening the original eleven-sample soak.
The original base, contract, source, schema, runner, manifest, and curriculum
are also rehashed after evaluation; any change makes the candidate
`NOT_PROMOTED`. The output volume must have at least 4 GiB free before staging.
A cooperative watchdog samples temperature during imports, load, training, and
reload, and enforces both the 80 C training ceiling and the two-hour wall-clock
contract at stage/step boundaries. It is not a hard process supervisor and does
not claim to interrupt native code that never returns control to Python.

The historical `training/box/requirements-box.txt` lock describes a legacy
CUDA 12.8 environment and is retained only as provenance. It is not runtime
authority for this path. The measured, fail-closed runtime policy in
`training-contract.json` is authoritative and records the exact package and GPU
identity in the training receipt before model load.

The runner trains a bounded 64-step QLoRA adapter, records safetensors artifact
hashes and measured GPU memory, reloads the adapter from disk, and runs the
frozen eight-row evaluation. Each output must satisfy the full dependency-light
draft contract **and** exactly match its preregistered expected JSON. Bounded
local output text plus a full SHA-256 is retained for audit. A failed runtime
identity, reload, semantic evaluation, or final input recheck remains
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

## Exit codes

- `0`: the requested non-training operation passed, or a bounded candidate run
  completed its exact reload evaluation (still `NOT_PROMOTED`).
- `3`: a preflight/GPU admission gate refused; the queue may retry later.
- `4`: training completed but exact reload evaluation failed.
- `5`: a persistent or fatal training contract/runtime gate refused; operator
  repair is required rather than an automatic retry.

The queue reads `training_started_at_unix_ns` from the attempt receipt instead
of inferring that training occurred from a process exit code. An exit `3` from
the train command is reserved for the eleven-sample GPU soak refusing before
model load; later contract failures are non-retryable and preserve whether the
trainer actually began.
