#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) - Doctrine v11 LOCKED
"""train_sft.py - Unsloth QLoRA SFT for the SZL sovereign model (Qwen2.5-3B).

TURNKEY / GPU-ONLY. Run this by hand on the box (OMEN, RTX 5050 Laptop, ~8GB
VRAM, Blackwell / native bf16). Nothing here is imported by serve.py or COPY-ed
into the image; this is offline training tooling isolated under training/box/.

Stage 1 of 3:
  1. train_sft.py   -> outputs/sft-lora     (this file)
  2. train_orpo.py  -> outputs/orpo-lora
  3. export_gguf.py -> GGUF q4_k_m + Modelfile + `ollama create`

Config is grounded in research/TRAINING_LEADERS_DEEP.md and must not drift:
  base = unsloth/Qwen2.5-3B-Instruct-bnb-4bit, load_in_4bit, nf4,
  target_modules = all-linear, r=16, alpha=32, dropout=0,
  optim = paged_adamw_8bit, bf16 (fp16 fallback), gradient_checkpointing,
  lr=2e-4, per_device_batch=2, grad_accum=4, max_seq_len=2048,
  warmup_ratio=0.03, epochs=1-3 (default 3).

Leader sources (cited, never claimed as ours):
  QLoRA:   Dettmers et al., arXiv:2305.14314.
  Unsloth: unsloth.ai (low-VRAM LoRA/QLoRA kernels).

Doctrine: the produced adapter's provenance is MODELED until a real run fills
the receipt. This script fabricates no eval score and no MEASURED joule figure;
the VRAM figure it prints is a real torch.cuda reading from this process.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRAIN_DIR = os.path.dirname(HERE)                       # training/
SEED = os.path.join(TRAIN_DIR, "szl_seed.jsonl")        # SFT chat corpus
OUT_DIR = os.path.join(HERE, "outputs", "sft-lora")

BASE_MODEL = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"
MAX_SEQ_LEN = 2048
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0
LR = 2e-4
BATCH = 2
GRAD_ACCUM = 4
WARMUP_RATIO = 0.03
SEED_RNG = 3407


def _load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--epochs", type=int, default=3, help="SFT epochs (1-3)")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--batch", type=int, default=BATCH,
                    help="per_device_train_batch_size (lower to 1 on OOM)")
    ap.add_argument("--max-seq-len", type=int, default=MAX_SEQ_LEN,
                    help="lower to 1024 on OOM")
    args = ap.parse_args()

    # Heavy deps imported here so --help works without a GPU stack.
    import torch
    from unsloth import FastLanguageModel
    from datasets import Dataset
    from trl import SFTTrainer, SFTConfig

    if not torch.cuda.is_available():
        print("train_sft: no CUDA device visible. This is a GPU-only script; "
              "run it on the box.", file=sys.stderr)
        return 2

    # Blackwell has native bf16; fall back to fp16 honestly if unsupported.
    use_bf16 = bool(torch.cuda.is_bf16_supported())
    print("train_sft: device=%s  bf16=%s (fp16=%s)"
          % (torch.cuda.get_device_name(0), use_bf16, not use_bf16))

    if not os.path.exists(SEED):
        print("train_sft: corpus not found: %s" % SEED, file=sys.stderr)
        return 2

    # QLoRA load (4-bit, nf4).
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=args.max_seq_len,
        load_in_4bit=True,
        dtype=None,                    # Unsloth auto-detects bf16/fp16
    )

    # LoRA on ALL linear layers.
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules="all-linear",
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=SEED_RNG,
    )

    seed_rows = _load_jsonl(SEED)
    sft_ds = Dataset.from_dict({
        "text": [
            tokenizer.apply_chat_template(r["messages"], tokenize=False,
                                          add_generation_prompt=False)
            for r in seed_rows
        ]
    })
    print("train_sft: %d SFT examples from %s"
          % (len(seed_rows), os.path.relpath(SEED, HERE)))

    sft_args = SFTConfig(
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=GRAD_ACCUM,
        num_train_epochs=args.epochs,
        learning_rate=LR,
        warmup_ratio=WARMUP_RATIO,
        logging_steps=1,
        optim="paged_adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=SEED_RNG,
        bf16=use_bf16,
        fp16=not use_bf16,
        output_dir=os.path.join(HERE, "outputs", "sft-trainer"),
        max_seq_length=args.max_seq_len,
        dataset_text_field="text",
        report_to="none",
    )
    trainer = SFTTrainer(model=model, tokenizer=tokenizer,
                         train_dataset=sft_ds, args=sft_args)

    result = trainer.train()

    # Honest, real readings from this process (never fabricated).
    vram_gb = torch.cuda.max_memory_reserved() / 1e9
    steps = int(result.global_step)
    final_loss = float(result.training_loss)

    os.makedirs(args.out_dir, exist_ok=True)
    model.save_pretrained(args.out_dir)
    tokenizer.save_pretrained(args.out_dir)

    print("\n================ SFT DONE ================")
    print("peak VRAM reserved : %.2f GB (torch.cuda, real reading)" % vram_gb)
    print("optimizer steps    : %d" % steps)
    print("final train loss   : %.4f" % final_loss)
    print("adapter saved      : %s" % args.out_dir)
    print("next               : python train_orpo.py")
    print("provenance         : MODELED (no receipt until a signed run fills it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
