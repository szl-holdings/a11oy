# SZL-Nemo governed fine-tuning path

Status: **executable candidate; no SZL-Nemo adapter has been trained or
promoted**.

This path creates a distinct LoRA/QLoRA candidate. It does not modify the
runtime-qualified `szl-nemo:latest` Ollama recipe and does not rename NVIDIA's
weights as SZL weights.

## Pinned base and license lineage

- repository: `nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16`
- immutable revision: `dfaf35de3e30f1867dd8dbc38a7fc9fb52d3914f`
- architecture: `NemotronHForCausalLM` / `nemotron_h`
- weight SHA-256: `55d4e2519456c4a9bddf596b0748d630e3b2ce6ff6f4c2b7ed3e07e2b00dad42`
- tokenizer SHA-256: `623c34567aebb18582765289fbe23d901c62704d6518d71866e0e58db892b5b7`
- license: NVIDIA Nemotron Open Model License
- official license URL:
  <https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/>

The trainer uses the built-in Transformers `nemotron_h` implementation with
`trust_remote_code=False`. Training requires an explicit acknowledgement of the
pinned upstream license. This is an engineering control, not legal advice.

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

Use the same Python 3.12 environment recorded in the contract.

```powershell
$Python = 'C:\Users\steph\AppData\Local\Programs\Python\Python312\python.exe'
$Runner = 'model_release\szl-nemo\szl_nemo_finetune.py'

# Deterministically rebuild and validate the project-authored curriculum.
& $Python $Runner build

# Separate, explicit network stage. This fetches only the pinned public base.
& $Python $Runner fetch-base `
  --destination 'model_release\szl-nemo\base-snapshot' `
  --confirmation 'FETCH_SZL_NEMO_BASE_dfaf35de3e30f1867dd8dbc38a7fc9fb52d3914f'

# Local-only validation. Add --check-gpu --probe for the fixed 3-sample gate.
& $Python $Runner preflight `
  --base-snapshot 'model_release\szl-nemo\base-snapshot'

# Queue without weakening thresholds or stopping another process.
& 'model_release\szl-nemo\Invoke-SZLNemoFineTuneQueue.ps1' `
  -Mode queue-train `
  -BaseSnapshot 'model_release\szl-nemo\base-snapshot' `
  -OutputDirectory 'model_release\szl-nemo\runs' `
  -Confirmation 'TRAIN_SZL_NEMO_GOVERNED_ADAPTER_V1' `
  -LicenseAcknowledgement 'ACK_NVIDIA_NEMOTRON_LICENSE_dfaf35de3e30f1867dd8dbc38a7fc9fb52d3914f' `
  -Python $Python `
  -GitExecutable 'C:\Users\steph\AppData\Local\OpenAI\Codex\tools\mingit-2.55.0.2\cmd\git.exe'
```

The queue performs a three-sample probe. The runner then performs a fixed
eleven-sample soak before model load. Current gates require at least 6,656 MiB
free VRAM, at most 10% utilization, and at most 60 C. They are intentionally not
weakened and the queue never stops another process. ReceiptAgent and SZL-Nemo
also share the same exclusive GPU-training lease, so their queues cannot train
concurrently even if both probes pass.

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

At the time this path was added:

- the exact BF16 snapshot was not present in the local Hugging Face cache;
- the laptop showed 5,215 MiB free VRAM and 69 C, below the fixed admission
  requirement of 6,656 MiB free and above the 60 C temperature ceiling;
- no Nemotron-compatible SZL adapter existed; and
- no trained-candidate reload, held-out evaluation, organization DSSE,
  transparency-log, or Hub readback receipt existed.

Therefore the honest current state remains **not trained**. The path is now
executable and evidence-producing, but it will wait rather than fabricate a
successful fine-tune.
