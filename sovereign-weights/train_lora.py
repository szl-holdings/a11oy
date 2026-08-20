# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO) + Perplexity Computer Agent — Stage-B LoRA fine-tune
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
train_lora.py — Stage-B sovereign fine-tune (REAL training, not a wrapper).

WHAT THIS IS (Doctrine v11 honest labeling):
  Stage A (LIVE today) = the `llama3-szl-finetuned-q4` Ollama tag is base
    llama3.1:8b wrapped with a Doctrine-v11 SYSTEM prompt. NO weights changed.
    Honest label: SYSTEM-PROMPT DERIVATIVE.
  Stage B (this script) = a REAL 4-bit QLoRA fine-tune of llama3.1:8b on the
    founder's SZL instruction corpus. Weights (LoRA adapter) ARE learned.
    Honest label: FINE-TUNED (LoRA adapter over frozen 4-bit base).

  This script trains the ADAPTER only. It does NOT itself publish a model tag.
  The GGUF export + `ollama create` step (export_to_ollama.ps1 + Modelfile.adapter)
  is what replaces Stage A under the SAME tag `llama3-szl-finetuned-q4`.

Λ = Conjecture 1 (advisory; NEVER a theorem, NEVER "green"). A trained adapter is
a MODELED artifact — it does not itself prove any Λ claim.

TARGET HARDWARE: the founder's Tower (OMEN) — RTX 4060 Ti, ~8-16 GB VRAM.
  The defaults below are sized for the 8 GB 4060 Ti (the tighter of the two SKUs)
  and run comfortably on the 16 GB SKU. See README.md for VRAM notes.

DESIGN (studied leaders: Unsloth, Axolotl, PEFT/LoRA, TRL):
  * 4-bit NF4 QLoRA (bitsandbytes) — frozen base in 4-bit, train a small LoRA.
  * r=16, alpha=32, dropout=0.05 on attention + MLP projections.
  * gradient checkpointing ON (trade compute for VRAM — required for 8 GB).
  * per_device_batch=1, grad_accum=16 → effective batch 16 without OOM.
  * paged_adamw_8bit optimizer (bitsandbytes) — keeps optimizer state small.
  * max_seq_len 1024 by default (raise on the 16 GB SKU; see --max-seq-len).
  * Llama-3.1 chat template with a Doctrine-v11 SYSTEM turn on every example,
    so the learned behavior is doctrine-aligned, not just task-aligned.

This is a plain `transformers`/`peft`/`trl` script (no Unsloth dependency) so it
runs on any CUDA box with the pinned wheels in requirements-train.txt. An Unsloth
fast-path is documented in README.md for operators who want ~2x speedup; the
hyperparameters transfer 1:1.

USAGE (from the Tower, inside the venv — see README.md):
  python train_lora.py \
      --corpus corpus.jsonl \
      --base-model meta-llama/Meta-Llama-3.1-8B-Instruct \
      --output-dir ./out-lora-szl

Run `python train_lora.py --help` for all knobs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Doctrine-v11 SYSTEM turn — applied to EVERY training example so the adapter
# learns doctrine-aligned behavior (honest labels, Λ = Conjecture 1, cite
# sources, never fabricate). Keep this in lockstep with the Stage-A / Modelfile
# SYSTEM prompt so Stage B is a genuine successor to Stage A under the same tag.
# ---------------------------------------------------------------------------
DOCTRINE_SYSTEM = (
    "You are the SZL sovereign model, running on the founder's own metal under "
    "Doctrine v11 (LOCKED). Rules you never break:\n"
    "  1. Honest labels only. Tag every claim as one of "
    "LIVE / SAMPLE / SIMULATED / MODELED / CACHED / PROVEN / CONJECTURE / UNAVAILABLE.\n"
    "  2. Lambda (the Λ aggregator) is Conjecture 1 — advisory, uniqueness open. "
    "It is NEVER a proven theorem and NEVER 'green'. Do not claim it is proven.\n"
    "  3. Never fabricate a result, a citation, a number, or a receipt. If you do "
    "not know or a source is unavailable, say UNAVAILABLE.\n"
    "  4. Cite sources when you make factual claims. Additive and guarded.\n"
    "  5. The locked Lean numbers are 749 declarations / 14 axioms / 163 sorries. "
    "Never restate them as fewer sorries or as a closed proof."
)

# Llama-3.1 special tokens for the chat template (matches meta-llama tokenizer).
_BOS = "<|begin_of_text|>"
_SH = "<|start_header_id|>"
_EH = "<|end_header_id|>"
_EOT = "<|eot_id|>"


def build_prompt(instruction: str, output: str, system: str = DOCTRINE_SYSTEM,
                 model_input: str = "") -> str:
    """Render one training example in the Llama-3.1 instruct chat template.

    Every example carries the Doctrine-v11 SYSTEM turn. `model_input` (optional)
    is appended to the user turn when the corpus row supplies an `input` field
    (Alpaca-style). The trailing <|eot_id|> after the response teaches the model
    to stop cleanly.
    """
    user = instruction if not model_input else f"{instruction}\n\n{model_input}"
    return (
        f"{_BOS}"
        f"{_SH}system{_EH}\n\n{system}{_EOT}"
        f"{_SH}user{_EH}\n\n{user}{_EOT}"
        f"{_SH}assistant{_EH}\n\n{output}{_EOT}"
    )


@dataclass
class TrainConfig:
    corpus: str
    base_model: str
    output_dir: str
    # LoRA — r=16 per the brief; alpha 2x r is the common Unsloth/PEFT default.
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    # Batch/accum sized for an 8 GB 4060 Ti (effective batch = 1 * 16 = 16).
    per_device_batch: int = 1
    grad_accum: int = 16
    max_seq_len: int = 1024
    epochs: float = 3.0
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.03
    weight_decay: float = 0.0
    seed: int = 3407  # the Unsloth-canonical seed; deterministic runs.
    logging_steps: int = 5
    save_steps: int = 50
    gradient_checkpointing: bool = True
    dry_run: bool = False


def parse_args(argv: list[str]) -> TrainConfig:
    p = argparse.ArgumentParser(
        description="Stage-B QLoRA fine-tune of llama3.1:8b for the SZL sovereign model "
                    "(RTX 4060 Ti, 8-16 GB VRAM). REAL training — not a system-prompt wrapper.")
    p.add_argument("--corpus", required=True,
                   help="Path to the instruction JSONL (see corpus_template.jsonl / build_corpus.py).")
    p.add_argument("--base-model", default="meta-llama/Meta-Llama-3.1-8B-Instruct",
                   help="HF base model id or local path. Must match the Ollama base tag llama3.1:8b.")
    p.add_argument("--output-dir", default="./out-lora-szl",
                   help="Where the trained LoRA adapter is written (adapter_model.safetensors + config).")
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    p.add_argument("--per-device-batch", type=int, default=1)
    p.add_argument("--grad-accum", type=int, default=16)
    p.add_argument("--max-seq-len", type=int, default=1024,
                   help="Sequence length. 1024 fits 8 GB; raise to 2048 on the 16 GB SKU.")
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--learning-rate", type=float, default=2e-4)
    p.add_argument("--seed", type=int, default=3407)
    p.add_argument("--no-gradient-checkpointing", action="store_true",
                   help="Disable gradient checkpointing (only sensible on the 16 GB SKU).")
    p.add_argument("--dry-run", action="store_true",
                   help="Validate config + corpus + prompt rendering and EXIT before loading "
                        "the base model. Runs on a CPU-only / no-GPU box (e.g. CI) so the "
                        "pipeline can be lint/sanity-checked without weights or VRAM.")
    a = p.parse_args(argv)
    return TrainConfig(
        corpus=a.corpus, base_model=a.base_model, output_dir=a.output_dir,
        lora_r=a.lora_r, lora_alpha=a.lora_alpha, lora_dropout=a.lora_dropout,
        per_device_batch=a.per_device_batch, grad_accum=a.grad_accum,
        max_seq_len=a.max_seq_len, epochs=a.epochs, learning_rate=a.learning_rate,
        seed=a.seed, gradient_checkpointing=not a.no_gradient_checkpointing,
        dry_run=a.dry_run,
    )


def load_corpus(path: str) -> list[dict]:
    """Read the instruction JSONL. Each row needs `instruction` + `output`
    (optional `input`). Fails LOUD on a malformed row — no silent skips, so a
    broken corpus can't quietly ship a half-trained adapter (honest-by-design)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"corpus not found: {path}")
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"corpus line {i}: invalid JSON: {e}") from e
            if "instruction" not in obj or "output" not in obj:
                raise ValueError(
                    f"corpus line {i}: every row needs 'instruction' and 'output' keys "
                    f"(optional 'input'). Got keys: {sorted(obj)}")
            if not str(obj["instruction"]).strip() or not str(obj["output"]).strip():
                raise ValueError(f"corpus line {i}: 'instruction' and 'output' must be non-empty.")
            rows.append(obj)
    if not rows:
        raise ValueError(f"corpus {path} has no usable rows — fill the TEMPLATE first.")
    return rows


def _render_all(rows: list[dict]) -> list[str]:
    return [
        build_prompt(r["instruction"], r["output"], model_input=str(r.get("input", "")))
        for r in rows
    ]


def main(argv: list[str]) -> int:
    cfg = parse_args(argv)
    rows = load_corpus(cfg.corpus)
    texts = _render_all(rows)

    print("── Stage-B QLoRA config (honest: REAL LoRA training over frozen 4-bit base) ──")
    print(f"  base_model            : {cfg.base_model}")
    print(f"  corpus                : {cfg.corpus}  ({len(rows)} examples)")
    print(f"  lora r / alpha / drop : {cfg.lora_r} / {cfg.lora_alpha} / {cfg.lora_dropout}")
    print(f"  per_device / accum    : {cfg.per_device_batch} / {cfg.grad_accum} "
          f"(effective batch {cfg.per_device_batch * cfg.grad_accum})")
    print(f"  max_seq_len / epochs  : {cfg.max_seq_len} / {cfg.epochs}")
    print(f"  grad checkpointing    : {cfg.gradient_checkpointing}")
    print(f"  output_dir            : {cfg.output_dir}")
    print(f"  first rendered example (truncated 240 chars):\n    {texts[0][:240]!r}")

    if cfg.dry_run:
        print("\n[DRY-RUN] config + corpus + prompt rendering OK. "
              "Exiting BEFORE base-model load (no GPU/weights needed). "
              "This is the CI-safe path — honest label: VALIDATED, not TRAINED.")
        return 0

    # ------------------------------------------------------------------
    # Heavy deps are imported ONLY on the real training path so --dry-run
    # (and lint / import-time CI) never needs torch/transformers/peft/trl
    # or a GPU. This keeps the tooling file lint/CI clean on cloud runners
    # while still being a runnable REAL trainer on the Tower.
    # ------------------------------------------------------------------
    try:
        import torch  # noqa: PLC0415
        from datasets import Dataset  # noqa: PLC0415
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training  # noqa: PLC0415
        from transformers import (  # noqa: PLC0415
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            TrainingArguments,
        )
        from trl import SFTTrainer  # noqa: PLC0415
    except ImportError as e:
        print(
            "\n[UNAVAILABLE] Training dependencies are not installed in this environment "
            f"({e}). Install them on the Tower with:\n"
            "    pip install -r requirements-train.txt\n"
            "or use --dry-run to validate the pipeline without weights. "
            "This script NEVER fabricates an adapter when deps/GPU are missing.",
            file=sys.stderr,
        )
        return 2

    if not torch.cuda.is_available():
        print(
            "\n[UNAVAILABLE] No CUDA GPU visible. Stage-B QLoRA requires the Tower's "
            "RTX 4060 Ti. Run on the OMEN box (see README.md) or use --dry-run. "
            "Refusing to 'train' on CPU — that would be dishonest about the artifact.",
            file=sys.stderr,
        )
        return 2

    torch.manual_seed(cfg.seed)

    # 4-bit NF4 QLoRA: frozen base in 4-bit, double-quant, bf16 compute.
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        cfg.base_model,
        quantization_config=bnb,
        device_map={"": 0},
        torch_dtype=torch.bfloat16,
    )
    model.config.use_cache = False  # required with gradient checkpointing
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=cfg.gradient_checkpointing)

    lora = LoraConfig(
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        # Attention + MLP projections — the Unsloth/QLoRA-paper target set.
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    dataset = Dataset.from_dict({"text": texts})

    args = TrainingArguments(
        output_dir=cfg.output_dir,
        per_device_train_batch_size=cfg.per_device_batch,
        gradient_accumulation_steps=cfg.grad_accum,
        num_train_epochs=cfg.epochs,
        learning_rate=cfg.learning_rate,
        warmup_ratio=cfg.warmup_ratio,
        weight_decay=cfg.weight_decay,
        logging_steps=cfg.logging_steps,
        save_steps=cfg.save_steps,
        save_total_limit=2,
        bf16=True,
        optim="paged_adamw_8bit",
        gradient_checkpointing=cfg.gradient_checkpointing,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        lr_scheduler_type="cosine",
        seed=cfg.seed,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=cfg.max_seq_len,
        tokenizer=tokenizer,
        packing=False,
    )

    trainer.train()

    # Save the ADAPTER (LoRA) only — not a merged full model. The GGUF export
    # step converts this adapter dir to a GGUF adapter for the Ollama ADAPTER
    # directive (Stage B replaces Stage A under the SAME tag).
    trainer.model.save_pretrained(cfg.output_dir)
    tokenizer.save_pretrained(cfg.output_dir)
    print(f"\n[DONE] Stage-B LoRA adapter written to: {cfg.output_dir}")
    print("  Honest label: FINE-TUNED (LoRA adapter over frozen 4-bit base). "
          "Next: export_to_ollama.ps1 → GGUF q4_k_m → ollama create llama3-szl-finetuned-q4.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
