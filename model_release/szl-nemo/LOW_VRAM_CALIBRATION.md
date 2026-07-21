# SZL-Nemo low-VRAM calibration

This lane measures whether the exact pinned Nemotron-H 4B snapshot can execute
one bounded NF4 QLoRA optimizer step on the RTX 5050 laptop below the canonical
training admission floor. It is a characterization experiment, not training.

## What it changes

- Capacity and calibration use the contract's `paged_adamw_8bit` optimizer.
- Canonical capacity now exercises an exact padded 768-token training shape;
  the 128-token calibration profile cannot substitute for that gate.
- Calibration has a distinct receipt schema and exact confirmation phrase.
- The queue accepts only the canonical capacity receipt; calibration can never
  enqueue training.
- Model placement is explicit single-CUDA placement. CPU/disk model offload and
  `device_map="auto"` are refused by the reviewed path.
- A Windows inventory helper reports the physical free-memory gap and likely
  WDDM GPU consumers without stopping processes or changing GPU preferences.
- A second, separately acknowledged 768-token experiment uses PyTorch's native
  `torch.autograd.graph.save_on_cpu(pin_memory=False, device_type="cuda")`
  around both forward and backward. It records host RSS, peak GPU memory,
  gradients, loss, timing, and context entry/exit without authorizing training.
- The activation-offload lane reads Linux `/proc/meminfo` and
  `/proc/self/status` before model load and throughout the step. It refuses on
  UNKNOWN evidence, less than 6,144 MiB `MemAvailable`, process RSS/HWM above
  16,384 MiB, or growth above 12,288 MiB.
- Physical free VRAM is sampled with `nvidia-smi` at declared phases. A
  calibration can complete while its adoption assessment remains `FAIL` or
  `NOT_EVALUATED`; at least 384 MiB free headroom plus independent review is
  required before a separately versioned profile could ever be proposed.

## What it does not change

The canonical training gate remains 6,656 MiB free, at most 10% utilization,
and at most 60 degrees C across its fixed sample window. A calibration pass does
not lower that threshold, authorize training, write an adapter, upload a file,
publish a model, or promote a candidate.

The free-memory gap is a pre-load admission-policy comparison, not proof of a
CUDA OOM. Activation offload cannot make `nvidia-smi` report more free memory
before launch. The lower 5,120 MiB experiment floor exists only so the exact
768-token experiment can measure whether a separately versioned optimized
profile is defensible. Adoption requires at least 384 MiB measured headroom,
finite adapter gradients, no frozen-base gradients, and independent review.

SZL Mesh routes whole inference requests. It does not pool laptop and tower VRAM
or shard this training process. CUDA on WSL does not provide a supported
oversubscription mechanism that turns host memory into additional physical GPU
memory for this lane.

### Source identity prerequisite

Run the governed launcher from a native WSL/Linux Git checkout at the exact
reviewed commit. A linked worktree created by Windows Git stores a `C:/...`
Git-directory pointer; Linux Git does not resolve that pointer and the runner
correctly refuses because it cannot measure the source commit. Do not edit or
translate the pointer by hand. Create a clean native checkout, confirm that the
contract-declared source scope is clean, and invoke the launcher from that
checkout. The immutable base snapshot may remain on a read-only `/mnt/c` path.

## Operator workflow

1. Record the current Windows-side inventory:

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
     .\model_release\szl-nemo\Measure-SZLNemoGpuInventory.ps1 `
     -OutputPath .\attestations\szl-nemo-gpu-inventory-local.json
   ```

2. Manually move or close GPU-accelerated browser, overlay, and desktop
   workloads. On Windows 11, prefer **Settings → System → Display → Graphics →
   Options → Power saving** for browser/UI applications, then fully restart
   those applications. The helper never terminates them or changes the setting.
3. Cool the laptop and rerun the inventory. One sample is diagnostic only.
4. Run the isolated calibration only after intentionally supplying the exact
   calibration phrase and NVIDIA acknowledgement:

   ```bash
   export SZL_NEMO_PYTHON="$HOME/.venvs/szl-nemo-torch210-cu128/bin/python"
   BASE=/mnt/c/Users/steph/Documents/Codex/2026-07-11/i-w/work/a11oy-frontier-wave18/model_release/szl-nemo/base-snapshot
   bash ./model_release/szl-nemo/run_wsl_governed.sh \
     --mode calibrate \
     --base-snapshot "$BASE" \
     --receipt "$PWD/attestations/szl-nemo-low-vram-calibration-local.json" \
     --confirmation CALIBRATE_SZL_NEMO_LOW_VRAM_V1 \
     --license-acknowledgement ACK_NVIDIA_NEMOTRON_LICENSE_dfaf35de3e30f1867dd8dbc38a7fc9fb52d3914f
   ```

The receipt path is append-only. A CUDA OOM is retained as negative evidence
and is never converted into a pass.

5. To measure the dependency-free saved-activation offload lane instead, use a
   fresh append-only receipt and its distinct acknowledgement:

   ```bash
   export SZL_NEMO_PYTHON="$HOME/.venvs/szl-nemo-torch210-cu128/bin/python"
   BASE=/mnt/c/Users/steph/Documents/Codex/2026-07-11/i-w/work/a11oy-frontier-wave18/model_release/szl-nemo/base-snapshot
   bash ./model_release/szl-nemo/run_wsl_governed.sh \
     --mode activation-offload \
     --base-snapshot "$BASE" \
     --receipt "$PWD/attestations/szl-nemo-activation-offload-calibration-local.json" \
     --confirmation CALIBRATE_SZL_NEMO_ACTIVATION_OFFLOAD_V1 \
     --license-acknowledgement ACK_NVIDIA_NEMOTRON_LICENSE_dfaf35de3e30f1867dd8dbc38a7fc9fb52d3914f
   ```

No run was performed by this code change. The exact acknowledgements remain an
intent boundary, and neither an activation-offload pass nor a short calibration
receipt is accepted by the training queue.

The canonical capacity receipt is versioned independently and now binds finite,
non-negative loss plus internally consistent adapter-gradient evidence. A
calibration receipt cannot be relabeled as canonical capacity: the queue also
requires offload to be explicitly disabled at both receipt levels.

## Measured first-backward root cause and bounded response

The canonical sequence-768 receipt reached a finite forward loss, then failed
inside gradient-checkpoint recomputation before the first optimizer step.  The
CUDA allocator requested exactly 9.00 GiB.  This request is explained exactly
by the hash-verified NVIDIA `torch_forward` expression that constructs
`G_intermediate` from pairwise `C * B` terms.  With batch 1, three 256-token
chunks, 96 Mamba heads, 128 state dimensions, and float32 storage, its shape is
`[1, 3, 256, 256, 96, 128]`: 2,415,919,104 elements or 9,663,676,416 bytes
(9.00 GiB).  This modeled allocator request must not be conflated with the
independently sampled physical peak or PyTorch reserved-memory counter.

Saved-tensor CPU offload moves tensors retained for backward; it cannot prevent
this new 9.00 GiB temporary from being materialized during recomputation.
Paged optimizer state is also not the cause because the failure precedes the
first optimizer step.  FSDP is not a single-GPU fix for a per-rank temporary.

The reviewed single-GPU response keeps the pinned NVIDIA CUDA convolution and
chunk-scan implementation but selects its decomposed branch per Mamba mixer.
That official branch calls the PEFT-wrapped `out_proj` module, preserving LoRA,
and does not construct the pure-PyTorch pairwise tensor.  Binding is allowed
only when the pinned NVIDIA source hash, all expected Mamba mixers, CUDA
residency, fast-path availability, bitsandbytes `Linear4bit` base, and matching
LoRA adapter sets are measured.  It changes no pinned source file or module
global and restores the mixer's training flag even on failure.

A fresh canonical capacity receipt is still required.  It must independently
record the `[1, 768]` input shape, packing disabled, non-reentrant gradient
checkpointing active, zero optimizer tensor state before backward, a finite
completed forward, all 21 mixer bindings, a completed backward and optimizer
step, and physical GPU headroom.  Until that receipt passes, training remains
unauthorized.

## Research basis

- QLoRA: https://arxiv.org/abs/2305.14314
- bitsandbytes optimizers: https://huggingface.co/docs/bitsandbytes/optimizers
- PEFT quantization: https://huggingface.co/docs/peft/developer_guides/quantization
- CUDA on WSL limitations: https://docs.nvidia.com/cuda/wsl-user-guide/
- Windows DXGI GPU preference: https://learn.microsoft.com/windows/win32/api/dxgi1_6/ne-dxgi1_6-dxgi_gpu_preference
- PyTorch CUDA cache semantics: https://docs.pytorch.org/docs/stable/generated/torch.cuda.memory.empty_cache.html
- PyTorch saved-tensor CPU offload: https://docs.pytorch.org/docs/stable/autograd.html#torch.autograd.graph.save_on_cpu
- PyTorch activation checkpointing: https://docs.pytorch.org/docs/stable/checkpoint.html
- Liger Kernel: https://github.com/linkedin/Liger-Kernel
- Apple Cut Cross Entropy: https://github.com/apple/ml-cross-entropy
- bitsandbytes FSDP-QLoRA: https://huggingface.co/docs/bitsandbytes/en/fsdp_qlora
- DeepSpeed ZeRO/Infinity: https://www.deepspeed.ai/tutorials/zero/
- NVIDIA Nemotron 4B base: https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16
