#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
"""Receipted Unsloth — take the speed, bind the knobs, refuse the folklore.

Unsloth TAKE (HUB, not MEASURED here):
  4-bit QLoRA · fused QK-RoPE / SwiGLU Triton kernels · adamw_8bit
  use_gradient_checkpointing="unsloth" · lora_dropout=0 · bias="none"
  auto padding-free packing (1.1–2×, ~30% VRAM, loss comparable)

Unsloth LEAVE:
  packing=True              — Unsloth's own docs: changes the loss scale
  LoftQ                     — start-of-run VRAM spike; not worth it on 0.5B–1.5B
  MoE Split-LoRA            — these organs are dense Qwen, not gpt-oss / Qwen3-MoE
  GGUF as the signed object — derived. Always.
  seed 3407                 — house seed is 20260721
  invented joules / 3× as MEASURED — their blog, not our receipt

SZL CUT (unique per organ, this file):
  willay        r=8  rsLoRA  attn+mlp   packing=false  short ctx   doctrine mouth
  chaski        r=8  rsLoRA  attn-only  packing=auto               courier cannot author
  chaski-5050   r=16 rsLoRA  attn+mlp   packing=auto               mix is the identity
  chaski-r2     r=8  rsLoRA  attn-only  packing=false  lr=5e-5     R2 refinement; R1 stays
  khipu         r=16         attn+mlp   packing=auto   4bit        navigator, loss-comparable
  receiptagent  r=16         attn+mlp   packing=false              receipt-first SFT
  khipu-r2      r=16         attn+mlp   packing=false              lineage, not overwrite

Every knob lands in training_receipt.json BEFORE merge.
Sign that envelope. Then merge. GGUF is derived.

  python receipted_unsloth.py --profile willay --receipt-only
  python receipted_unsloth.py --profile chaski --data doctrine.jsonl --out out/chaski
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

SEED = 20260721
ATTN = ("q_proj", "k_proj", "v_proj", "o_proj")
ATTN_MLP = ATTN + ("gate_proj", "up_proj", "down_proj")

# Unique silhouettes. Rank/alpha keep alpha/r >= 1 (Unsloth hyperparameter guide).
# rsLoRA scales alpha/sqrt(r) — used on the small ranks so they do not vanish.
PROFILES: dict[str, dict[str, Any]] = {
    "khipu": {
        "base": "Qwen/Qwen2.5-1.5B-Instruct",
        "r": 16, "alpha": 16, "rslora": False, "targets": ATTN_MLP,
        "packing": "auto", "max_seq": 2048, "lr": 2e-4, "steps": 120,
        "warmup": 10, "batch": 2, "accum": 4, "load_in_4bit": True,
        "cut": "Navigator. 7 modules so the schema can be emitted. packing=auto keeps loss comparable to signed 0.0245. Not retrained here.",
    },
    "khipu-r2": {
        "base": "Qwen/Qwen2.5-1.5B-Instruct",
        "r": 16, "alpha": 16, "rslora": False, "targets": ATTN_MLP,
        "packing": "false", "max_seq": 2048, "lr": 1e-4, "steps": 80,
        "warmup": 8, "batch": 2, "accum": 4, "load_in_4bit": True,
        "cut": "Lineage sibling. packing=false so R2 loss is comparable to R1. Do not overwrite R1.",
    },
    "receiptagent": {
        "base": "Qwen/Qwen2.5-1.5B-Instruct",
        "r": 16, "alpha": 16, "rslora": False, "targets": ATTN_MLP,
        "packing": "false", "max_seq": 1536, "lr": 2e-4, "steps": 100,
        "warmup": 10, "batch": 2, "accum": 4, "load_in_4bit": True,
        "cut": "Receipt-first SFT. packing=false: the loss on the receipt tokens is the point.",
    },
    "willay": {
        "base": "Qwen/Qwen2.5-0.5B-Instruct",
        "r": 8, "alpha": 16, "rslora": True, "targets": ATTN_MLP,
        "packing": "false", "max_seq": 1024, "lr": 1e-4, "steps": 160,
        "warmup": 20, "batch": 2, "accum": 4, "load_in_4bit": True,
        "cut": "Doctrine mouth. rsLoRA so rank-8 does not vanish. packing=false so silence/tell loss stays comparable. Short ctx: honesty set is short.",
    },
    "chaski": {
        "base": "Qwen/Qwen3.5-0.8B",
        "r": 8, "alpha": 16, "rslora": True, "targets": ATTN,
        "packing": "auto", "max_seq": 1536, "lr": 1e-4, "steps": 120,
        "warmup": 12, "batch": 2, "accum": 4, "load_in_4bit": True,
        "cut": "Courier. Attention-only LoRA — MLP stays frozen so the runner cannot author the payload. Unique cut. Dense 0.8B, 4bit is allowed (MoE QLoRA is the thing Unsloth warns against).",
    },
    "chaski-5050": {
        "base": "Qwen/Qwen3.5-0.8B",
        "r": 16, "alpha": 16, "rslora": True, "targets": ATTN_MLP,
        "packing": "auto", "max_seq": 1536, "lr": 1e-4, "steps": 120,
        "warmup": 12, "batch": 2, "accum": 4, "load_in_4bit": True,
        "cut": "50/50 cutting mix. Extra MLP rank so the courier is allowed to STOP. Mix is the identity.",
    },
    "chaski-r2": {
        "base": "Qwen/Qwen3.5-0.8B",
        "r": 8, "alpha": 16, "rslora": True, "targets": ATTN,
        "packing": "false", "max_seq": 1536, "lr": 5e-5, "steps": 80,
        "warmup": 8, "batch": 2, "accum": 4, "load_in_4bit": True,
        "cut": "Round-2 refinement. packing=false + lower lr. R1 stays up. Do not overwrite.",
    },
}

TECHNIQUES = {
    "take": [
        "4-bit QLoRA (load_in_4bit)",
        "fused QK-RoPE + SwiGLU Triton kernels (automatic in FastLanguageModel)",
        "adamw_8bit",
        "use_gradient_checkpointing='unsloth'",
        "lora_dropout=0, bias='none' (Unsloth-optimized)",
        "auto padding-free packing when packing=auto",
        "rsLoRA (alpha/sqrt(r)) on small-rank organs",
    ],
    "leave": [
        "packing=True (changes loss scale — Unsloth docs)",
        "LoftQ (start-of-run VRAM spike)",
        "MoE Split-LoRA (not a MoE organ)",
        "GGUF as the signed object",
        "seed 3407",
        "tokens-per-joule invented",
        "3×/5× speed cited as MEASURED — that is Unsloth's HUB claim",
    ],
    "cut": "Every knob in the receipt. Unique rank/targets/packing per organ. House seed 20260721. Sign before merge.",
}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def effective_scale(alpha: int, r: int, rslora: bool) -> float:
    return (alpha / (r ** 0.5)) if rslora else (alpha / r)


def mint_receipt(profile: str, cfg: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    rec = {
        "schema": "szl.training_receipt.v2",
        "profile": profile,
        "base": cfg["base"],
        "cut": cfg["cut"],
        "lora": {
            "r": cfg["r"],
            "alpha": cfg["alpha"],
            "rslora": cfg["rslora"],
            "effective_scale": round(effective_scale(cfg["alpha"], cfg["r"], cfg["rslora"]), 6),
            "targets": list(cfg["targets"]),
            "dropout": 0,
            "bias": "none",
            "loftq": False,
        },
        "unsloth": {
            "load_in_4bit": cfg["load_in_4bit"],
            "gradient_checkpointing": "unsloth",
            "optim": "adamw_8bit",
            "packing": cfg["packing"],
            "max_seq": cfg["max_seq"],
            "lr": cfg["lr"],
            "max_steps": cfg["steps"],
            "warmup": cfg["warmup"],
            "batch": cfg["batch"],
            "grad_accum": cfg["accum"],
            "techniques": TECHNIQUES,
        },
        "seed": SEED,
        "proven_trust": False,
        "energy_j": None,
        "energy_status": "UNAVAILABLE",
        "gguf": "derived — never the signed object",
        "note": "Sign this envelope (DSSE/Ed25519) BEFORE merge. Do not GPU-retrain 1.5B from this atelier.",
    }
    rec.update(extra)
    if rec.get("proven_trust") is True:
        raise ValueError("refusing proven_trust true")
    if rec.get("energy_j") not in (None,):
        raise ValueError("refusing to fabricate joules")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description="Receipted Unsloth. Unique cut per organ.")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="khipu")
    ap.add_argument("--data", default="doctrine.jsonl")
    ap.add_argument("--out", default="out/adapter")
    ap.add_argument("--receipt-only", action="store_true", help="Mint the recipe receipt. No GPU. No fit.")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--packing", choices=["auto", "true", "false"], default=None)
    ap.add_argument("--i-accept-incomparable-loss", action="store_true")
    args = ap.parse_args()

    if args.list:
        for name, cfg in PROFILES.items():
            print(f"{name:14} r={cfg['r']:<3} rsLoRA={str(cfg['rslora']):5} pack={cfg['packing']:5} "
                  f"tgt={len(cfg['targets'])} {cfg['base']}")
            print(f"               {cfg['cut']}")
        return 0

    cfg = dict(PROFILES[args.profile])
    if args.packing:
        cfg["packing"] = args.packing
    if cfg["packing"] == "true" and not args.i_accept_incomparable_loss:
        print("refusing packing=true: Unsloth docs say it changes the loss scale. "
              "Pass --i-accept-incomparable-loss if you still want it.", file=sys.stderr)
        return 2

    data_path = Path(args.data)
    extra: dict[str, Any] = {
        "dataset": str(data_path),
        "dataset_sha256": sha256_file(data_path) if data_path.exists() else None,
        "dataset_status": "MEASURED" if data_path.exists() else "UNAVAILABLE",
        "honesty": "RECIPE" if args.receipt_only else "REPORTED",
    }

    if args.receipt_only:
        rec = mint_receipt(args.profile, cfg, extra)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "training_receipt.json").write_text(json.dumps(rec, indent=2) + "\n")
        print(json.dumps(rec, indent=2))
        return 0

    if not data_path.exists():
        print(f"missing dataset {data_path} — pass --receipt-only to mint the recipe without GPU", file=sys.stderr)
        return 2

    extra["dataset_sha256"] = sha256_file(data_path)
    extra["dataset_status"] = "MEASURED"

    from unsloth import FastLanguageModel
    from datasets import load_dataset
    from trl import SFTConfig, SFTTrainer

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=cfg["base"],
        max_seq_length=cfg["max_seq"],
        load_in_4bit=cfg["load_in_4bit"],
        full_finetuning=False,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=cfg["r"],
        lora_alpha=cfg["alpha"],
        target_modules=list(cfg["targets"]),
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=SEED,
        use_rslora=cfg["rslora"],
        loftq_config=None,
        max_seq_length=cfg["max_seq"],
    )
    ds = load_dataset("json", data_files=str(data_path), split="train")
    sft_kw: dict[str, Any] = dict(
        output_dir=args.out,
        per_device_train_batch_size=cfg["batch"],
        gradient_accumulation_steps=cfg["accum"],
        max_steps=cfg["steps"],
        learning_rate=cfg["lr"],
        warmup_steps=cfg["warmup"],
        logging_steps=10,
        seed=SEED,
        optim="adamw_8bit",
        max_seq_length=cfg["max_seq"],
        lr_scheduler_type="cosine",
        weight_decay=0.01,
    )
    if cfg["packing"] == "true":
        sft_kw["packing"] = True
    elif cfg["packing"] == "false":
        sft_kw["packing"] = False
    # packing=auto: omit the flag — Unsloth padding-free default, loss comparable.

    trainer = SFTTrainer(model=model, tokenizer=tokenizer, train_dataset=ds, args=SFTConfig(**sft_kw))
    t0 = time.time()
    trainer.train()
    Path(args.out).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.out)
    loss = None
    if trainer.state.log_history:
        last = trainer.state.log_history[-1]
        loss = last.get("train_loss") or last.get("loss")
    extra.update({"final_loss": loss, "seconds": round(time.time() - t0, 3), "honesty": "REPORTED"})
    rec = mint_receipt(args.profile, cfg, extra)
    Path(args.out, "training_receipt.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
