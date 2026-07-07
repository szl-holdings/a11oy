<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
-->
# sovereign-weights/ — Stage-B LoRA fine-tune pipeline (SZL sovereign model)

Runnable tooling to take the SZL sovereign model from **Stage A** (a system-prompt
wrapper) to **Stage B** (a real LoRA fine-tune), on the founder's Tower
(OMEN, **RTX 4060 Ti**, ~8–16 GB VRAM). Everything here is *tooling* — none of it
is registered in `serve.py`, so there is no Dockerfile COPY-guard concern.

## Honest framing — Stage A vs Stage B (Doctrine v11)

| | Stage A (LIVE today) | Stage B (this directory) |
|---|---|---|
| What changes | **Nothing in the weights.** Base `llama3.1:8b` + a Doctrine-v11 `SYSTEM` prompt. | A **real 4-bit QLoRA fine-tune** — a LoRA adapter is *trained* on the founder's corpus. |
| Honest label | `SYSTEM-PROMPT DERIVATIVE` | `FINE-TUNED (LoRA adapter over frozen 4-bit base)` |
| Ollama tag | `llama3-szl-finetuned-q4` | **same** `llama3-szl-finetuned-q4` (Stage B *replaces* Stage A under the same tag) |
| Proves anything about Λ? | No — Λ = **Conjecture 1** (advisory) | No — a trained adapter is a `MODELED` artifact; it proves no Λ claim |

Because Stage B keeps the **same tag**, the a11oy sovereign backend
(`szl_llm_registry.py`, model slug `llama3-szl-finetuned-q4`) needs **no change** —
it keeps routing to `SZL_LOCAL_LLM_URL` and now gets the fine-tuned behavior.

> Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem, NEVER "green").
> Honest labels throughout: LIVE / SAMPLE / SIMULATED / MODELED / CACHED / PROVEN / CONJECTURE / UNAVAILABLE.

## Files

| File | Role |
|---|---|
| `train_lora.py` | 4-bit QLoRA fine-tune of `llama3.1:8b`. r=16, gradient checkpointing, batch/accum sized for 8–16 GB. Doctrine-v11 prompt template baked into every example. `--dry-run` validates with no GPU/weights. |
| `corpus_template.jsonl` | The instruction corpus **TEMPLATE the founder fills** — 4 real doctrine seed rows + 1 illustrative `TEMPLATE` row. |
| `build_corpus.py` | Scaffolds a corpus from SZL docs (repos/papers) into DRAFT instruction pairs with real `input` + placeholder `output`. `validate` refuses a corpus that still has `TODO(founder)` markers. |
| `Modelfile.adapter` | Ollama Modelfile: `FROM llama3.1:8b` + `ADAPTER` (the trained GGUF LoRA) + the Doctrine-v11 `SYSTEM` prompt. |
| `export_to_ollama.ps1` | Converts the LoRA adapter → GGUF (llama.cpp) and runs `ollama create llama3-szl-finetuned-q4` — replacing Stage A under the same tag. Fails loud (UNAVAILABLE), never fabricates a tag. |
| `requirements-train.txt` | Training deps — install **on the Tower**, not in CI. |

## Exact Tower run order (OMEN, RTX 4060 Ti)

Run these **on the Tower** (the box is NOT reachable from CI/cloud). All paths are examples.

```powershell
# 0) One-time: base model + tools present
ollama pull llama3.1:8b
git clone https://github.com/ggml-org/llama.cpp $env:USERPROFILE\llama.cpp
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements-train.txt

# 1) Build the corpus FROM your docs (draft), then EDIT it by hand
python build_corpus.py draft --src $env:USERPROFILE\szl\a11oy --src $env:USERPROFILE\szl\szl-papers `
    --template corpus_template.jsonl --out corpus.draft.jsonl
#    ... edit corpus.draft.jsonl: fill every TODO(founder) output, delete junk rows ...
Rename-Item corpus.draft.jsonl corpus.jsonl
python build_corpus.py validate --corpus corpus.jsonl        # must print [OK]

# 2) Sanity-check the trainer WITHOUT a GPU (fast, no weights)
python train_lora.py --corpus corpus.jsonl --dry-run

# 3) REAL Stage-B QLoRA fine-tune (this is where the 4060 Ti works)
python train_lora.py --corpus corpus.jsonl `
    --base-model meta-llama/Meta-Llama-3.1-8B-Instruct `
    --output-dir .\out-lora-szl

# 4) Export adapter -> GGUF -> ollama create (SAME tag replaces Stage A)
powershell -ExecutionPolicy Bypass -File .\export_to_ollama.ps1 `
    -AdapterDir .\out-lora-szl -LlamaCpp $env:USERPROFILE\llama.cpp

# 5) Smoke test
ollama run llama3-szl-finetuned-q4 "State your doctrine in one line."
```

After step 4 the a11oy sovereign health endpoint
(`GET /api/a11oy/v1/llm/sovereign/health`) will report the same tag, now serving
Stage-B weights — no registry edit needed.

## VRAM notes (RTX 4060 Ti)

The 4060 Ti ships in **8 GB** and **16 GB** SKUs. Defaults target the **8 GB** case
(the tighter one) and run comfortably on 16 GB.

* **4-bit NF4 base** (bitsandbytes, double-quant): the frozen `llama3.1:8b` base is
  ~5–6 GB in 4-bit — the reason QLoRA fits an 8 GB card at all.
* **Gradient checkpointing = ON** (`--no-gradient-checkpointing` to disable): trades
  compute for activation memory. Required on 8 GB; optional on 16 GB.
* **batch 1 × grad-accum 16** → effective batch 16 with a tiny live footprint.
* **`max_seq_len` = 1024** by default. Raise to **2048** on the 16 GB SKU
  (`--max-seq-len 2048`); on 8 GB keep it at 1024 (or 768 if you still OOM).
* **`paged_adamw_8bit`** optimizer keeps optimizer state paged and small.
* If you OOM on 8 GB: lower `--max-seq-len` to 768, keep `--per-device-batch 1`,
  and confirm nothing else is using the GPU (`nvidia-smi`).

Rough headroom: on 8 GB expect training to sit around 7–7.5 GB with these defaults;
on 16 GB you have room to raise seq-len and/or batch.

## Optional: Unsloth fast-path

For ~2× speed / lower memory, operators can swap `train_lora.py`'s model load for
Unsloth's `FastLanguageModel.from_pretrained(..., load_in_4bit=True)` +
`FastLanguageModel.get_peft_model(...)`. The hyperparameters here (r=16, alpha=32,
dropout=0.05, the seven target modules, batch/accum, seq-len, the Doctrine-v11
template) transfer 1:1. The plain `transformers`/`peft`/`trl` path shipped here is
dependency-light and needs no extra wheels beyond `requirements-train.txt`.

## What this is NOT

* Not a proof of anything — Λ stays **Conjecture 1** (advisory).
* Not runnable in CI/cloud — the Tower is the only box with the GPU; cloud paths
  degrade to honest **UNAVAILABLE** (see `train_lora.py` when no CUDA is visible).
* Not an auto-answer generator — `build_corpus.py` never writes the `output` for
  you; that would be fabrication. The founder authors the answers.
