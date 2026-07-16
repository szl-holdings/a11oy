#!/usr/bin/env bash
set -euo pipefail

# Reproducible Linux/WSL execution lane for the pinned NVIDIA Nemotron-H code.
# The environment lives outside the repository so generated packages cannot be
# mistaken for release artifacts.

VENV_PATH="${SZL_NEMO_VENV:-$HOME/.venvs/szl-nemo-torch210-cu128}"
CACHE_PATH="${SZL_NEMO_WHEEL_CACHE:-$HOME/.cache/szl-nemo-wheels}"

MAMBA_WHEEL="mamba_ssm-2.3.2.post1+cu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl"
MAMBA_URL="https://github.com/state-spaces/mamba/releases/download/v2.3.2.post1/mamba_ssm-2.3.2.post1%2Bcu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl"
MAMBA_SHA256="7a67070c1e7e99c95abd1319623f044e8a1b3fb46f774bfdea949f0a4fc79638"

CAUSAL_WHEEL="causal_conv1d-1.6.2.post1+cu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl"
CAUSAL_URL="https://github.com/Dao-AILab/causal-conv1d/releases/download/v1.6.2.post1/causal_conv1d-1.6.2.post1%2Bcu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl"
CAUSAL_SHA256="c16c1c48d4fa63415cc797e02d69f97248c57c04627d99e394d5bb0ef266e288"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "UNAVAILABLE: this runtime is Linux-only" >&2
  exit 3
fi

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "UNAVAILABLE: pinned wheels require Linux x86_64" >&2
  exit 3
fi

if [[ "$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != "3.12" ]]; then
  echo "UNAVAILABLE: pinned wheels require Python 3.12" >&2
  exit 3
fi

mkdir -p "$(dirname "$VENV_PATH")" "$CACHE_PATH"
python3 -m venv --clear "$VENV_PATH"
# shellcheck disable=SC1091
source "$VENV_PATH/bin/activate"

python -m pip install --upgrade \
  pip==26.1.1 \
  setuptools==80.10.2 \
  wheel==0.46.3 \
  packaging==26.0 \
  ninja==1.13.0

# PyTorch's official previous-versions matrix publishes this CUDA 12.8 build.
python -m pip install \
  torch==2.10.0 \
  --index-url https://download.pytorch.org/whl/cu128

# NVIDIA's model card says its Transformers example was tested on 4.48.3.
python -m pip install \
  transformers==4.48.3 \
  accelerate==1.12.0 \
  bitsandbytes==0.49.2 \
  safetensors==0.7.0 \
  einops==0.8.2

fetch_verified_wheel() {
  local url="$1"
  local filename="$2"
  local expected="$3"
  local target="$CACHE_PATH/$filename"

  if [[ ! -f "$target" ]] || ! echo "$expected  $target" | sha256sum --check --status; then
    rm -f "$target"
    curl --fail --location --retry 3 --output "$target" "$url"
  fi
  echo "$expected  $target" | sha256sum --check
}

fetch_verified_wheel "$CAUSAL_URL" "$CAUSAL_WHEEL" "$CAUSAL_SHA256"
fetch_verified_wheel "$MAMBA_URL" "$MAMBA_WHEEL" "$MAMBA_SHA256"

# These are official release assets, selected for the exact Python/Torch/CUDA
# ABI above. --no-deps prevents pip from silently replacing the pinned stack.
python -m pip install --no-deps \
  "$CACHE_PATH/$CAUSAL_WHEEL" \
  "$CACHE_PATH/$MAMBA_WHEEL"

# mamba-ssm 2.3.2.post1 declares these runtime families. Their unconstrained
# resolver can replace the measured Torch/CUDA ABI, so install a complete,
# exact dependency closure with --no-deps and let `pip check` validate it.
python -m pip install --no-deps \
  tilelang==0.1.8 \
  apache-tvm-ffi==0.1.9 \
  quack-kernels==0.3.4 \
  torch-c-dlpack-ext==0.1.5 \
  cloudpickle==3.1.2 \
  ml-dtypes==0.5.4 \
  z3-solver==4.15.4.0 \
  nvidia-cutlass-dsl==4.4.2 \
  nvidia-cutlass-dsl-libs-base==4.4.2 \
  cuda-python==12.9.1

# The supervised fine-tuning lane is pinned to versions whose published
# requirements include Transformers 4.48.3. Repeating the already measured
# Torch/Transformers/HF core in the same resolver transaction prevents an
# apparently convenient training package from silently changing the ABI or
# custom-code surface qualified above.
python -m pip install \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  torch==2.10.0 \
  transformers==4.48.3 \
  accelerate==1.12.0 \
  tokenizers==0.21.4 \
  huggingface-hub==0.36.2 \
  trl==0.15.2 \
  peft==0.14.0 \
  datasets==3.2.0

python - <<'PY'
import json
import platform

import bitsandbytes
import causal_conv1d
import datasets
import mamba_ssm
import peft
import torch
import transformers
import trl

payload = {
    "platform": platform.platform(),
    "python": platform.python_version(),
    "torch": torch.__version__,
    "torch_cuda": torch.version.cuda,
    "torch_cuda_available": torch.cuda.is_available(),
    "torch_cxx11_abi": torch.compiled_with_cxx11_abi(),
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    "transformers": transformers.__version__,
    "mamba_ssm": getattr(mamba_ssm, "__version__", "UNKNOWN"),
    "causal_conv1d": getattr(causal_conv1d, "__version__", "UNKNOWN"),
    "bitsandbytes": bitsandbytes.__version__,
    "datasets": datasets.__version__,
    "peft": peft.__version__,
    "trl": trl.__version__,
}
print(json.dumps(payload, sort_keys=True))
if not payload["torch_cuda_available"]:
    raise SystemExit("UNAVAILABLE: CUDA is not visible inside WSL")

expected = {
    "torch": "2.10.0+cu128",
    "transformers": "4.48.3",
    "datasets": "3.2.0",
    "peft": "0.14.0",
    "trl": "0.15.2",
}
for package, version in expected.items():
    if payload[package] != version:
        raise SystemExit(
            f"UNAVAILABLE: {package} version drifted: {payload[package]} != {version}"
        )
PY

python -m pip check
