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

## What it does not change

The canonical training gate remains 6,656 MiB free, at most 10% utilization,
and at most 60 degrees C across its fixed sample window. A calibration pass does
not lower that threshold, authorize training, write an adapter, upload a file,
publish a model, or promote a candidate.

SZL Mesh routes whole inference requests. It does not pool laptop and tower VRAM
or shard this training process. CUDA on WSL does not provide a supported
oversubscription mechanism that turns host memory into additional physical GPU
memory for this lane.

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

## Research basis

- QLoRA: https://arxiv.org/abs/2305.14314
- bitsandbytes optimizers: https://huggingface.co/docs/bitsandbytes/optimizers
- PEFT quantization: https://huggingface.co/docs/peft/developer_guides/quantization
- CUDA on WSL limitations: https://docs.nvidia.com/cuda/wsl-user-guide/
- Windows DXGI GPU preference: https://learn.microsoft.com/windows/win32/api/dxgi1_6/ne-dxgi1_6-dxgi_gpu_preference
- PyTorch CUDA cache semantics: https://docs.pytorch.org/docs/stable/generated/torch.cuda.memory.empty_cache.html
- NVIDIA Nemotron 4B base: https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16
