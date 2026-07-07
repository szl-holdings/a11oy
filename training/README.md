<!--
SPDX-License-Identifier: Apache-2.0
(c) Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) - Doctrine v11 LOCKED
-->

# training/ — SZL sovereign-model doctrine fine-tune (TRACK C, STAGE 1)

This directory holds the **data + scripts** to fine-tune a local base model into a
**doctrine-native SZL sovereign model**. It produces two corpora from the a11oy
estate and a QLoRA + Unsloth + ORPO training driver. **No training happens in this
repo** — there is no GPU here, nothing here is imported by `serve.py`, and nothing
is `COPY`-ed into the Dockerfile image. Training is run by the operator on the
sovereign tower (the `omen` / `betterwithage` GPU boxes).

Doctrine v11 governs the content: honest labels, `Λ = Conjecture 1`, locked-8 =
exactly `{F1, F4, F7, F11, F12, F18, F19, F22}` @ kernel `c7c0ba17`, trust ceiling
`0.97`, and never a fabricated `MEASURED` value. The produced weights' provenance
is labelled **MODELED** until a real run fills the receipt.

## Files

| File | Role | Runs here? |
|---|---|---|
| `build_seed.py` | Deterministic, pure-stdlib miner → `szl_seed.jsonl` (SFT, chat format). | ✅ stdlib |
| `szl_seed.jsonl` | The generated seed corpus (hand-verifiable, derived from the repo). | data |
| `build_orpo.py` | Builds the 6-family doctrine-preference corpus + eval split. | ✅ stdlib |
| `szl_orpo.jsonl` | ORPO `{prompt, chosen, rejected}` training pairs. | data |
| `szl_orpo_eval.jsonl` | Held-out 10%/family refusal-to-fabricate eval. | data |
| `train_sovereign.py` | QLoRA + Unsloth + ORPO driver. **ROADMAP / GPU-only.** | ❌ GPU only |
| `provenance_stub.py` | Emits the szl-lake chain-of-title receipt (provenance MODELED). | ✅ stdlib |

Regenerate the corpora at any time (deterministic — byte-identical output):

```bash
python training/build_seed.py     # -> training/szl_seed.jsonl
python training/build_orpo.py     # -> training/szl_orpo.jsonl + szl_orpo_eval.jsonl
python training/build_seed.py --check   # verify count in [150,300], no banned tokens
python training/build_orpo.py --check   # verify 6 balanced families
```

## Leader sources (cited, never claimed as ours)

- **QLoRA** — Dettmers, Pagnoni, Holtzman, Zettlemoyer (2023), *QLoRA: Efficient
  Finetuning of Quantized LLMs*, [arXiv:2305.14314](https://arxiv.org/abs/2305.14314).
- **Unsloth** — [unsloth.ai](https://unsloth.ai) — memory-efficient LoRA/QLoRA
  kernels and GGUF export.
- **ORPO** — Hong, Lee & Thorne (2024), *ORPO: Monotonic Odds Ratio Preference
  Optimization without Reference Model*,
  [arXiv:2403.07691](https://arxiv.org/abs/2403.07691).

---

## Windows runbook (sovereign tower: omen / betterwithage)

Unsloth's fast path is Linux/WSL2. On a Windows GPU box, run training inside
**WSL2 (Ubuntu)** with the NVIDIA CUDA driver exposed to WSL. The steps below use
PowerShell to enter WSL, then bash inside WSL.

### STAGE 0 — environment

```powershell
# PowerShell (Windows) — once
wsl --install -d Ubuntu        # if WSL2 not present; reboot if prompted
wsl                            # drop into Ubuntu
```

```bash
# inside WSL2 Ubuntu
nvidia-smi                     # confirm the GPU is visible in WSL
python3 -m venv ~/szl-train && source ~/szl-train/bin/activate
python -m pip install --upgrade pip
# Unsloth (pulls a matching torch + bitsandbytes for your CUDA):
pip install "unsloth[cu121] @ git+https://github.com/unslothai/unsloth.git"
pip install trl peft accelerate datasets bitsandbytes
```

> Honest note: exact CUDA tag (`cu121` / `cu118`) must match your driver. If
> bitsandbytes fails to find CUDA, fix the driver/toolkit before proceeding —
> a truthful BLOCKED beats a fake green.

### STAGE 1 — get the corpora onto the box

```bash
git clone https://github.com/szl-holdings/a11oy.git && cd a11oy
python training/build_seed.py && python training/build_orpo.py
python training/build_seed.py --check && python training/build_orpo.py --check
```

### STAGES 2–4 — DIAGNOSTIC run first (r=2, 50 steps)

Always smoke-test cheaply before committing GPU-hours:

```bash
export SZL_ALLOW_TRAIN=1        # required guard: refuses to train unless set
python training/train_sovereign.py --diagnostic
```

Inspect the loss curve. If it descends sanely, proceed to the full run.

### STAGES 5–6 — full SFT + ORPO

```bash
python training/train_sovereign.py           # full: SFT on seed, then ORPO
# LoRA targets ALL linear layers; rsLoRA auto-enables when r>32 (default r=64).
```

Preview the plan any time without a GPU:

```bash
python training/train_sovereign.py --dry-run
```

### STAGE 7 — GGUF export + Ollama

`train_sovereign.py` exports a `q4_k_m` GGUF and writes a `Modelfile`. Register it
with Ollama:

```bash
cd training/out/gguf
ollama create llama3-szl-finetuned-q4 -f Modelfile
ollama run llama3-szl-finetuned-q4 "Is Λ a theorem?"
# expect: "No. Λ is Conjecture 1 ..."
```

Point the a11oy sovereign mesh at it by exporting `SZL_LOCAL_LLM_URL`
(single node) or `A11OY_SOVEREIGN_GATEWAY_URL` (LiteLLM over omen + betterwithage);
the registry only reports `wired=true` when the node answers live.

### Provenance receipt (szl-lake chain-of-title)

```bash
# stub (before a real run) — provenance MODELED, eval UNAVAILABLE:
python training/provenance_stub.py > training/provenance_receipt.json

# after a real run — fill measured fields:
python training/provenance_stub.py \
    --gguf-sha256 "$(sha256sum training/out/gguf/*.gguf | awk '{print $1}')" \
    --base-sha256 "<base-model-sha>" \
    --eval training/eval_scores.json > training/provenance_receipt.json
```

The receipt records corpus sha256s, `%synthetic`, base sha, LoRA/ORPO config,
GGUF sha256, and eval scores. Until a real training run fills it, the receipt is
honestly labelled `MODELED` and the DSSE `signature` is a `PLACEHOLDER`.
