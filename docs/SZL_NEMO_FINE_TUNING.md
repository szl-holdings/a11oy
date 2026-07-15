# SZL-Nemo governed fine-tuning path

Status: **pinned candidate; native-Windows training unavailable; governed
WSL2/Linux Mamba import lane qualified; capacity/training not run; no SZL-Nemo
adapter has been trained or promoted**.

This path creates a distinct LoRA/QLoRA candidate. It does not modify the
runtime-qualified `szl-nemo:latest` Ollama recipe and does not rename NVIDIA's
weights as SZL weights.

## Pinned base and license lineage

- repository: `nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16`
- immutable revision: `dfaf35de3e30f1867dd8dbc38a7fc9fb52d3914f`
- architecture: `NemotronHForCausalLM` / `nemotron_h`
- weight SHA-256: recorded in the machine-readable
  `model_release/szl-nemo/training-contract.json` receipt
- tokenizer SHA-256: recorded in the same machine-readable receipt
- license: NVIDIA Nemotron Open Model License
- official license URL:
  <https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/>

The upstream configuration contains NVIDIA's hybrid pattern character `-` for
dense MLP layers. The built-in Transformers 5.5 implementation does not accept
that pattern, so using it would alter or reject the official architecture. The
trainer therefore permits `trust_remote_code=True` only for the two upstream
NVIDIA files pinned into the immutable snapshot:

- `configuration_nemotron_h.py` — SHA-256
  `07fa66e5b3da7e6a71c1a263e3dd68da11c8afa9178b47c49510ba628746fcff`
- `modeling_nemotron_h.py` — SHA-256
  `ea982af0b805f181573f919ecb001d5bbc0153459923cf4b2f1ccae194e415a4`

The custom implementation imports `mamba_ssm` and `causal_conv1d` CUDA
extensions. NVIDIA declares Linux as the supported operating system. Native
Windows is therefore fail-closed as `UNAVAILABLE_MAMBA_KERNELS`; the training
lane is WSL2/Linux with NVIDIA CUDA. Preflight now imports the pinned custom
configuration and model class in addition to verifying hashes, so a file-only
check cannot be mistaken for runtime readiness. Training also requires an
explicit acknowledgement of the pinned upstream license. This is an engineering
control, not legal advice.

## Admitted curriculum

The committed source contains eight SZL-authored behavior scenarios. The
deterministic builder renders 24 training records and keeps eight separately
authored prompts as held-out evaluation records. It binds every generated file
to the source and schema hashes and refuses train/eval prompt overlap.

The following stay outside gradients:

- all 9,464 raw Brain nodes;
- the formula curriculum and formula-admission tranche;
- the historical seed, Brain, and formula corpora;
- the failed ORPO candidate; and
- private receipts, API responses, and runtime traces.

They remain retrieval or evaluation sources until row-level rights, privacy,
provenance, freshness, and contamination decisions authorize a later tranche.

## Commands

Use Python 3.12 only through the pinned WSL2/Linux environment. Native Windows
Python is an explicit non-retryable refusal for this architecture.

```bash
cd /mnt/c/Users/steph/Documents/Codex/2026-07-11/i-w/work/a11oy-frontier-wave18

# Network-capable dependency provisioning, with exact official wheel digests.
./model_release/szl-nemo/setup_wsl_runtime.sh

BASE="$PWD/model_release/szl-nemo/base-snapshot"
ACK="ACK_NVIDIA_NEMOTRON_LICENSE_dfaf35de3e30f1867dd8dbc38a7fc9fb52d3914f"
CONFIRM="TRAIN_SZL_NEMO_GOVERNED_ADAPTER_V1"

# Imports, pinned dynamic-code hashes, kernel symbols, and the fixed GPU gate.
./model_release/szl-nemo/run_wsl_governed.sh \
  --mode preflight --base-snapshot "$BASE"

# Required before training: isolated 4-bit load plus one in-memory LoRA
# forward/backward/optimizer step. No adapter is saved and no quality is claimed.
./model_release/szl-nemo/run_wsl_governed.sh \
  --mode capacity --base-snapshot "$BASE" \
  --receipt "$PWD/attestations/szl-nemo-capacity-2026-07-15.json" \
  --confirmation "$CONFIRM" --license-acknowledgement "$ACK"

# Only after the capacity receipt passes and the reviewed source scope is clean.
./model_release/szl-nemo/run_wsl_governed.sh \
  --mode train --base-snapshot "$BASE" \
  --output-dir "$PWD/model_release/szl-nemo/runs/governed-adapter-v1" \
  --confirmation "$CONFIRM" --license-acknowledgement "$ACK"
```

The launcher performs a three-sample probe, and the trainer performs a fixed
eleven-sample soak before model load. Current gates require at least 6,656 MiB
free VRAM, at most 10% utilization, and at most 60 C. They are not weakened and
the launcher never stops another process. Capacity and training execute inside
`unshare --user --map-root-user --net`, with only loopback present. ReceiptAgent
and SZL-Nemo use the same fail-closed repository GPU lease; a second acquisition
is refused rather than allowing concurrent training.

## Bounded WSL queue

For unattended admission watching, use the Linux-only durable queue instead of
an open-ended shell loop. It requires the exact training and NVIDIA-license
acknowledgements before creating a queue, and records only their SHA-256
digests. Every transition is appended to `events.jsonl`; every completed stage
and attempt gets an immutable receipt; `state.json` is an atomic current-state
projection. A crash leaves the queue locked for operator review rather than
guessing whether training ran.

```bash
QUEUE="$PWD/model_release/szl-nemo/szl_nemo_wsl_queue.py"
PYTHON="$HOME/.venvs/szl-nemo-torch210-cu128/bin/python"

"$PYTHON" "$QUEUE" run \
  --base-snapshot "$BASE" \
  --output-root "$PWD/model_release/szl-nemo/runs" \
  --python "$PYTHON" \
  --confirmation "$CONFIRM" \
  --license-acknowledgement "$ACK" \
  --max-attempts 30 \
  --retry-seconds 120
```

The only retryable outcomes are a pure fixed GPU-admission refusal and an
already-held shared GPU lease. A malformed receipt, runtime failure, capacity
failure after model load, or any failure after training is invoked stops the
queue for operator review. The queue never runs dependency setup or base fetch,
never weakens the 6,656 MiB / 10% / 60 C admission gates, never terminates a
process, and never uploads, publishes, deploys, or promotes an artifact.

Inspect a queue without mutating it:

```bash
"$PYTHON" "$QUEUE" status \
  --queue-dir "$PWD/model_release/szl-nemo/queue-state/wsl/<queue-id>"
```

## Candidate outputs and receipts

A completed run must contain:

- `adapter/adapter_model.safetensors` plus its exact inventory;
- preflight, runtime, GPU, training, and input-identity evidence;
- an exact-base adapter reload;
- results for all eight held-out behavior rows, including failures;
- a DSSE candidate summary; and
- an immutable terminal training receipt.

Even a passing run is only `CANDIDATE_GENERATED_NOT_PROMOTED`. Public promotion
still requires a verified organization-identity DSSE signature, transparency-log
entry, cold restart, served-tag attestation, independent Hub readback, preserved
NVIDIA notice, and human approval. The scripts do not upload, publish, deploy, or
promote.

## Current measured blockers

Current measured state:

- the exact 7,947,142,640-byte BF16 weight and tokenizer are locally present and
  hash-verified;
- the two exact NVIDIA custom-code files are locally present and hash-verified;
- native Windows rejects the official custom model class because the required
  Mamba CUDA extension is unavailable;
- WSL2 sees the NVIDIA GPU; Torch 2.10.0+cu128, Transformers 4.48.3, Mamba
  2.3.2.post1, causal-conv1d 1.6.2.post1, the C++11 ABI, and `pip check` have
  passed in the isolated environment;
- every custom-code command uses a fresh, process-unique `HF_MODULES_CACHE`
  after the pinned NVIDIA snapshot hashes pass, then re-hashes the executed
  config/model sources against those pins;
- training freezes admitted train/eval rows in memory and rechecks their exact
  file identities and the reviewed Git scope before a candidate summary can be
  signed;
- a pinned dynamic-class import receipt, quantized model-load capacity receipt,
  and actual training receipt are still required before any adapter claim;
- no Nemotron-compatible SZL adapter exists; and
- no trained-candidate reload, held-out evaluation, organization DSSE,
  transparency-log, or Hub readback receipt exists.

Therefore the honest current state remains **not trained**. Kernel compatibility
is established; model capacity, optimization, held-out quality, and promotion
are not. The path waits rather than fabricating a successful fine-tune.
