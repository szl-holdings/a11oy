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
| `szl_seed.jsonl` | The 167 hand-verified doctrine seed examples. | data |
| `build_brain_corpus.py` | Mines the live brain graph (`data/brain_graph.json`) → `szl_brain_corpus.jsonl`. Grounded ONLY in each node's real fields — never fabricated. | ✅ stdlib |
| `szl_brain_corpus.jsonl` | Brain-graph Q/A (title/kind/layer/label/connectivity), honesty label verbatim. | data |
| `build_formula_corpus.py` | Mines the formula registry (`data/formulas_live.json`) → `szl_formula_corpus.jsonl`, quoting each `proof_status` verbatim. | ✅ stdlib |
| `szl_formula_corpus.jsonl` | Per-formula Q/A; never upgrades a label (Λ stays Conjecture 1). | data |
| `build_full_corpus.py` | Merges seed + brain + formula + surfaces, dedups near-identical prompts → **`szl_seed_full.jsonl`** (the corpus to train on). | ✅ stdlib |
| `szl_seed_full.jsonl` | **The full SFT corpus the sovereign model trains on.** | data |
| `data/brain_graph.json` | Copy of the live 9,343-node / 12,009-link brain graph (`/api/a11oy/v1/brain/graph`). | data |
| `data/formulas_live.json` | Copy of the 22-formula registry (`/api/a11oy/v1/formulas`). | data |
| `build_orpo.py` | Builds the 6-family doctrine-preference corpus + eval split. | ✅ stdlib |
| `szl_orpo.jsonl` | ORPO `{prompt, chosen, rejected}` training pairs. | data |
| `szl_orpo_eval.jsonl` | Held-out 10%/family refusal-to-fabricate eval. | data |
| `train_sovereign.py` | QLoRA + Unsloth + ORPO driver. **ROADMAP / GPU-only.** | ❌ GPU only |
| `provenance_stub.py` | Emits the szl-lake chain-of-title receipt (provenance MODELED). | ✅ stdlib |

### Corpus sources (SFT) and honest counts

`szl_seed_full.jsonl` is assembled deterministically from four grounded sources,
with near-duplicate prompts collapsed (first wins, in the order below):

| Source | Grounded in | Raw → kept |
|---|---|---|
| SEED | 167 hand-verified doctrine examples (`szl_seed.jsonl`, verbatim) | 167 → 167 |
| BRAIN | live 9,343-node brain graph — real node fields only, no fabrication | 1233 → 1233 |
| FORMULA | 22-formula registry — `proof_status` quoted verbatim, never upgraded | 70 → 70 |
| SURFACE | one honest Q/A per live 3D estate surface (SURFACES manifest) | 86 → 86 |
| **TOTAL** | | **1556** |

Brain answers are built **strictly** from each node's real fields (`id`, `kind`,
`layer`, `title`, `label`, `degree`, and any `path`/`axis`); nodes with only a
title get a modest honest description, never an invented capability. Every answer
carries the node's real honesty label (`HARVESTED` / `MODELED` / `LIVE`) verbatim,
and discloses that the 9,343 total includes 5,235 arXiv co-author person nodes so
the honest distinct-artifact count is 4,108. Formula answers quote the recorded
`proof_status` verbatim and never re-badge a `SORRY`/`AXIOM` as `PROVEN`; Λ stays
**Conjecture 1** and the locked-8 count stays exactly 8.

Regenerate the corpora at any time (deterministic — byte-identical output):

```bash
python training/build_seed.py           # -> training/szl_seed.jsonl (167)
python training/build_brain_corpus.py    # -> training/szl_brain_corpus.jsonl (1233)
python training/build_formula_corpus.py  # -> training/szl_formula_corpus.jsonl (70)
python training/build_full_corpus.py     # -> training/szl_seed_full.jsonl (1556, the train corpus)
python training/build_orpo.py            # -> training/szl_orpo.jsonl + szl_orpo_eval.jsonl

python training/build_brain_corpus.py --check    # 800 <= n <= 3000, no banned tokens
python training/build_formula_corpus.py --check  # 40 <= n <= 200, no banned tokens
python training/build_full_corpus.py --check     # 1000 <= n <= 5000, per-source counts
python training/build_orpo.py --check            # verify 6 balanced families
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
python training/build_brain_corpus.py && python training/build_formula_corpus.py
python training/build_full_corpus.py && python training/build_orpo.py
python training/build_full_corpus.py --check && python training/build_orpo.py --check
# SFT trains on training/szl_seed_full.jsonl; ORPO on training/szl_orpo.jsonl.
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
