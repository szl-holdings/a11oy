#!/usr/bin/env bash
set -euo pipefail

# One-shot WSL/Linux launcher. It never retries a failed runtime or admission
# gate and never starts training unless --mode train is explicit.

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${SZL_NEMO_PYTHON:-$HOME/.venvs/szl-nemo-torch210-cu128/bin/python}"
RUNNER="$HERE/szl_nemo_finetune.py"
MODE="preflight"
BASE=""
OUTPUT=""
RECEIPT=""
CONFIRMATION=""
LICENSE_ACKNOWLEDGEMENT=""
PREFLIGHT_RECEIPT=""

usage() {
  cat <<'EOF'
Usage:
  run_wsl_governed.sh --base-snapshot PATH [--mode preflight]
  run_wsl_governed.sh --base-snapshot PATH --mode capacity --receipt PATH \
    --confirmation EXACT_PHRASE --license-acknowledgement EXACT_PHRASE
  run_wsl_governed.sh --base-snapshot PATH --mode calibrate --receipt PATH \
    --confirmation CALIBRATE_SZL_NEMO_LOW_VRAM_V1 \
    --license-acknowledgement EXACT_PHRASE
  run_wsl_governed.sh --base-snapshot PATH --mode activation-offload --receipt PATH \
    --confirmation CALIBRATE_SZL_NEMO_ACTIVATION_OFFLOAD_V1 \
    --license-acknowledgement EXACT_PHRASE

All modes accept --preflight-receipt PATH so a queue can bind the admission
receipt to one immutable attempt directory.
  run_wsl_governed.sh --base-snapshot PATH --mode train --output-dir PATH \
    --confirmation EXACT_PHRASE --license-acknowledgement EXACT_PHRASE
  run_wsl_governed.sh --base-snapshot PATH --mode evaluate --output-dir TRAINING_OUTPUT \
    --receipt PATH --confirmation EVALUATE_SZL_NEMO_GOVERNED_ADAPTER_V2 \
    --license-acknowledgement EXACT_PHRASE
EOF
}

while (($#)); do
  case "$1" in
    --mode) MODE="${2:?missing mode}"; shift 2 ;;
    --base-snapshot) BASE="${2:?missing base snapshot}"; shift 2 ;;
    --output-dir) OUTPUT="${2:?missing output directory}"; shift 2 ;;
    --receipt) RECEIPT="${2:?missing receipt path}"; shift 2 ;;
    --confirmation) CONFIRMATION="${2:?missing confirmation}"; shift 2 ;;
    --license-acknowledgement) LICENSE_ACKNOWLEDGEMENT="${2:?missing acknowledgement}"; shift 2 ;;
    --preflight-receipt) PREFLIGHT_RECEIPT="${2:?missing preflight receipt path}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "UNAVAILABLE: SZL-Nemo governed execution requires Linux/WSL2" >&2
  exit 4
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "UNAVAILABLE: pinned WSL Python is absent: $PYTHON" >&2
  exit 4
fi
if [[ ! -f "$RUNNER" || ! -d "$BASE" ]]; then
  echo "UNAVAILABLE: runner or immutable base snapshot is absent" >&2
  exit 4
fi
if [[ "$MODE" != "preflight" && "$MODE" != "capacity" && "$MODE" != "calibrate" && "$MODE" != "activation-offload" && "$MODE" != "evaluate" && "$MODE" != "train" ]]; then
  echo "Mode must be preflight, capacity, calibrate, activation-offload, evaluate, or train" >&2
  exit 2
fi
if [[ "$MODE" != "preflight" && ( -z "$CONFIRMATION" || -z "$LICENSE_ACKNOWLEDGEMENT" ) ]]; then
  echo "BLOCKED: capacity/train mode requires both exact acknowledgements" >&2
  exit 2
fi
if [[ ( "$MODE" == "capacity" || "$MODE" == "calibrate" || "$MODE" == "activation-offload" ) && -z "$RECEIPT" ]]; then
  echo "BLOCKED: capacity/calibration mode requires an explicit --receipt path" >&2
  exit 2
fi
if [[ "$MODE" == "train" && -z "$OUTPUT" ]]; then
  echo "BLOCKED: train mode requires --output-dir" >&2
  exit 2
fi
if [[ "$MODE" == "evaluate" && ( -z "$OUTPUT" || -z "$RECEIPT" ) ]]; then
  echo "BLOCKED: evaluate mode requires --output-dir and --receipt" >&2
  exit 2
fi

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export DO_NOT_TRACK=1
export WANDB_DISABLED=true
export TOKENIZERS_PARALLELISM=false
export NO_PROXY='*'

"$PYTHON" "$RUNNER" build

if [[ -z "$PREFLIGHT_RECEIPT" ]]; then
  PREFLIGHT_RECEIPT="$HERE/queue-state/wsl-preflight-$(date -u +%Y%m%dT%H%M%SZ).json"
fi
mkdir -p "$(dirname "$PREFLIGHT_RECEIPT")"
set +e
if [[ "$MODE" == "calibrate" || "$MODE" == "activation-offload" ]]; then
  "$PYTHON" "$RUNNER" preflight \
    --base-snapshot "$BASE" \
    --receipt "$PREFLIGHT_RECEIPT"
else
  "$PYTHON" "$RUNNER" preflight \
    --base-snapshot "$BASE" \
    --check-gpu \
    --probe \
    --receipt "$PREFLIGHT_RECEIPT"
fi
PREFLIGHT_EXIT=$?
set -e
if ((PREFLIGHT_EXIT != 0)); then
  echo "BLOCKED: preflight returned $PREFLIGHT_EXIT; training was not started" >&2
  exit "$PREFLIGHT_EXIT"
fi

if [[ "$MODE" == "preflight" ]]; then
  echo "PASS: preflight only; training was not started"
  exit 0
fi

if ! command -v unshare >/dev/null 2>&1; then
  echo "UNAVAILABLE: util-linux unshare is absent" >&2
  exit 4
fi
if ! unshare --user --map-root-user --net -- true; then
  echo "UNAVAILABLE: this WSL kernel does not permit an isolated user/network namespace" >&2
  exit 4
fi

if [[ "$MODE" == "capacity" ]]; then
  mkdir -p "$(dirname "$RECEIPT")"
  exec unshare --user --map-root-user --net -- \
    env \
      HF_HUB_OFFLINE=1 \
      TRANSFORMERS_OFFLINE=1 \
      HF_DATASETS_OFFLINE=1 \
      HF_HUB_DISABLE_TELEMETRY=1 \
      DO_NOT_TRACK=1 \
      WANDB_DISABLED=true \
      TOKENIZERS_PARALLELISM=false \
      NO_PROXY='*' \
    "$PYTHON" "$RUNNER" capacity-probe \
      --base-snapshot "$BASE" \
      --receipt "$RECEIPT" \
      --confirmation "$CONFIRMATION" \
      --license-acknowledgement "$LICENSE_ACKNOWLEDGEMENT"
fi

if [[ "$MODE" == "calibrate" ]]; then
  mkdir -p "$(dirname "$RECEIPT")"
  exec unshare --user --map-root-user --net -- \
    env \
      HF_HUB_OFFLINE=1 \
      TRANSFORMERS_OFFLINE=1 \
      HF_DATASETS_OFFLINE=1 \
      HF_HUB_DISABLE_TELEMETRY=1 \
      DO_NOT_TRACK=1 \
      WANDB_DISABLED=true \
      TOKENIZERS_PARALLELISM=false \
      NO_PROXY='*' \
    "$PYTHON" "$RUNNER" calibrate-vram \
      --base-snapshot "$BASE" \
      --receipt "$RECEIPT" \
      --confirmation "$CONFIRMATION" \
      --license-acknowledgement "$LICENSE_ACKNOWLEDGEMENT"
fi

if [[ "$MODE" == "activation-offload" ]]; then
  mkdir -p "$(dirname "$RECEIPT")"
  exec unshare --user --map-root-user --net -- \
    env \
      HF_HUB_OFFLINE=1 \
      TRANSFORMERS_OFFLINE=1 \
      HF_DATASETS_OFFLINE=1 \
      HF_HUB_DISABLE_TELEMETRY=1 \
      DO_NOT_TRACK=1 \
      WANDB_DISABLED=true \
      TOKENIZERS_PARALLELISM=false \
      NO_PROXY='*' \
    "$PYTHON" "$RUNNER" calibrate-activation-offload \
      --base-snapshot "$BASE" \
      --receipt "$RECEIPT" \
      --confirmation "$CONFIRMATION" \
      --license-acknowledgement "$LICENSE_ACKNOWLEDGEMENT"
fi

if [[ "$MODE" == "evaluate" ]]; then
  mkdir -p "$(dirname "$RECEIPT")"
  exec unshare --user --map-root-user --net -- \
    env \
      HF_HUB_OFFLINE=1 \
      TRANSFORMERS_OFFLINE=1 \
      HF_DATASETS_OFFLINE=1 \
      HF_HUB_DISABLE_TELEMETRY=1 \
      DO_NOT_TRACK=1 \
      WANDB_DISABLED=true \
      TOKENIZERS_PARALLELISM=false \
      NO_PROXY='*' \
    "$PYTHON" "$RUNNER" evaluate-adapter \
      --base-snapshot "$BASE" \
      --training-output "$OUTPUT" \
      --receipt "$RECEIPT" \
      --confirmation "$CONFIRMATION" \
      --license-acknowledgement "$LICENSE_ACKNOWLEDGEMENT"
fi

mkdir -p "$OUTPUT"
exec unshare --user --map-root-user --net -- \
  env \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_DATASETS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    DO_NOT_TRACK=1 \
    WANDB_DISABLED=true \
    TOKENIZERS_PARALLELISM=false \
    NO_PROXY='*' \
  "$PYTHON" "$RUNNER" train \
    --base-snapshot "$BASE" \
    --output-dir "$OUTPUT" \
    --confirmation "$CONFIRMATION" \
    --license-acknowledgement "$LICENSE_ACKNOWLEDGEMENT"
