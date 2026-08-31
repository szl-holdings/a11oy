#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) - Doctrine v11 LOCKED
"""train_sovereign.py - QLoRA + Unsloth + ORPO doctrine fine-tune (ROADMAP / GPU).

STATUS: ROADMAP - REQUIRES A GPU. This script MUST NOT run in the a11oy repo CI
or the HF Space; it is neither imported by serve.py nor COPY-ed into the image.
It is the TRACK C training driver the operator runs on the sovereign tower
(omen / betterwithage) after STAGE 1 produced the corpora.

Pipeline (Program STAGE 0-7, see training/README.md):
  * STAGE 0  env / GPU sanity.
  * STAGE 1  load szl_seed.jsonl (SFT, chat format) + szl_orpo.jsonl (preference).
  * STAGE 2  load base in 4-bit (QLoRA / bitsandbytes NF4) via Unsloth FastLanguageModel.
  * STAGE 3  attach LoRA to ALL linear layers; rsLoRA when r>32.
  * STAGE 4  DIAGNOSTIC run first: r=2, max_steps=50 (fast smoke test, cheap).
  * STAGE 5  full SFT on the seed (TRL SFTTrainer).
  * STAGE 6  ORPO preference alignment on {prompt,chosen,rejected} (TRL ORPOTrainer).
  * STAGE 7  merge/export -> GGUF q4_k_m -> `ollama create llama3-szl-finetuned-q4`.

Leader sources (cited, never claimed as ours):
  * QLoRA:  Dettmers et al., arXiv:2305.14314.
  * Unsloth: unsloth.ai (2x faster / less-VRAM LoRA/QLoRA kernels).
  * ORPO:   Hong, Lee & Thorne (2024), "ORPO: Monotonic Odds Ratio Preference
            Optimization without Reference Model", arXiv:2403.07691.

Doctrine: the produced weights' provenance is MODELED until a real training run
fills the receipt (see training/provenance_stub.py). Nothing here fabricates an
eval score or a MEASURED energy figure.

This module intentionally imports GPU-only deps (unsloth/trl/peft/torch) INSIDE
main(), so `python train_sovereign.py --dry-run` works with pure stdlib and is
the only path exercised off-GPU (it prints the plan and exits without training).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, "szl_seed.jsonl")
ORPO = os.path.join(HERE, "szl_orpo.jsonl")

# ── Defaults (override via CLI) ────────────────────────────────────────────────
DEFAULTS = {
    "base_model": "unsloth/llama-3-8b-Instruct-bnb-4bit",
    "max_seq_len": 2048,
    "lora_r": 64,          # full run; diagnostic overrides to 2
    "lora_alpha": 64,
    "lora_dropout": 0.0,
    "target_modules": [    # ALL linear layers (attention + MLP projections)
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    "sft_epochs": 3,
    "orpo_epochs": 1,
    "orpo_beta": 0.1,       # ORPO odds-ratio lambda (Hong 2024)
    "lr_sft": 2e-4,
    "lr_orpo": 8e-6,
    "batch_size": 2,
    "grad_accum": 4,
    "seed": 3407,
    "out_dir": os.path.join(HERE, "out"),
    "gguf_quant": "q4_k_m",
    "ollama_name": "llama3-szl-finetuned-q4",
}


def _load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _plan(cfg):
    seed_n = len(_load_jsonl(SEED)) if os.path.exists(SEED) else 0
    orpo_n = len(_load_jsonl(ORPO)) if os.path.exists(ORPO) else 0
    r = cfg["lora_r"]
    return {
        "base_model": cfg["base_model"],
        "seed_examples": seed_n,
        "orpo_pairs": orpo_n,
        "lora_r": r,
        "use_rslora": r > 32,
        "target_modules": cfg["target_modules"],
        "quant": "nf4 (QLoRA, bitsandbytes)",
        "gguf": cfg["gguf_quant"],
        "ollama_create": "ollama create %s -f Modelfile" % cfg["ollama_name"],
        "note": "provenance MODELED until a real GPU run fills the receipt",
    }


def _to_chat_text(tokenizer, messages):
    return tokenizer.apply_chat_template(messages, tokenize=False,
                                         add_generation_prompt=False)


def run(cfg, diagnostic):
    """Real GPU path. Imports heavy deps lazily so --dry-run stays stdlib-only."""
    # STAGE 0 - imports / GPU sanity.
    import torch  # noqa: F401  (import proves CUDA stack is present)
    from unsloth import FastLanguageModel
    from datasets import Dataset
    from trl import SFTTrainer, SFTConfig, ORPOTrainer, ORPOConfig

    if diagnostic:
        cfg = dict(cfg, lora_r=2, sft_epochs=1, orpo_epochs=1)

    # STAGE 2 - load base in 4-bit (QLoRA).
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=cfg["base_model"],
        max_seq_length=cfg["max_seq_len"],
        load_in_4bit=True,
        dtype=None,
    )

    # STAGE 3 - LoRA on ALL linear layers; rsLoRA when r>32.
    model = FastLanguageModel.get_peft_model(
        model,
        r=cfg["lora_r"],
        lora_alpha=cfg["lora_alpha"],
        lora_dropout=cfg["lora_dropout"],
        target_modules=cfg["target_modules"],
        bias="none",
        use_gradient_checkpointing="unsloth",
        use_rslora=cfg["lora_r"] > 32,
        random_state=cfg["seed"],
    )

    # STAGE 1 - datasets.
    seed_rows = _load_jsonl(SEED)
    sft_ds = Dataset.from_dict({
        "text": [_to_chat_text(tokenizer, r["messages"]) for r in seed_rows]
    })

    # STAGE 4/5 - SFT (diagnostic: max_steps=50).
    sft_args = SFTConfig(
        per_device_train_batch_size=cfg["batch_size"],
        gradient_accumulation_steps=cfg["grad_accum"],
        num_train_epochs=cfg["sft_epochs"],
        max_steps=50 if diagnostic else -1,
        learning_rate=cfg["lr_sft"],
        logging_steps=1,
        optim="adamw_8bit",
        seed=cfg["seed"],
        output_dir=os.path.join(cfg["out_dir"], "sft"),
        max_seq_length=cfg["max_seq_len"],
    )
    SFTTrainer(model=model, tokenizer=tokenizer, train_dataset=sft_ds,
               dataset_text_field="text", args=sft_args).train()

    if diagnostic:
        print("train_sovereign: DIAGNOSTIC r=2/50-steps SFT complete; stop here, "
              "inspect loss, then re-run full without --diagnostic.")
        return 0

    # STAGE 6 - ORPO preference alignment.
    def _fmt(row):
        head = [{"role": "system", "content": row["system"]},
                {"role": "user", "content": row["prompt"]}]
        prompt = tokenizer.apply_chat_template(head, tokenize=False,
                                               add_generation_prompt=True)
        return {"prompt": prompt, "chosen": row["chosen"],
                "rejected": row["rejected"]}

    orpo_ds = Dataset.from_list([_fmt(r) for r in _load_jsonl(ORPO)])
    orpo_args = ORPOConfig(
        per_device_train_batch_size=cfg["batch_size"],
        gradient_accumulation_steps=cfg["grad_accum"],
        num_train_epochs=cfg["orpo_epochs"],
        learning_rate=cfg["lr_orpo"],
        beta=cfg["orpo_beta"],
        logging_steps=1,
        optim="adamw_8bit",
        seed=cfg["seed"],
        max_length=cfg["max_seq_len"],
        max_prompt_length=cfg["max_seq_len"] // 2,
        output_dir=os.path.join(cfg["out_dir"], "orpo"),
    )
    ORPOTrainer(model=model, tokenizer=tokenizer, train_dataset=orpo_ds,
                args=orpo_args).train()

    # STAGE 7 - GGUF export + Ollama Modelfile.
    gguf_dir = os.path.join(cfg["out_dir"], "gguf")
    model.save_pretrained_gguf(gguf_dir, tokenizer,
                               quantization_method=cfg["gguf_quant"])
    print("train_sovereign: exported GGUF -> %s" % gguf_dir)
    print("Next: ollama create %s -f %s/Modelfile"
          % (cfg["ollama_name"], gguf_dir))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="print the training plan and exit (stdlib only; no GPU)")
    ap.add_argument("--diagnostic", action="store_true",
                    help="r=2, max_steps=50 smoke test (Program STAGE 4)")
    ap.add_argument("--base-model", default=DEFAULTS["base_model"])
    ap.add_argument("--out-dir", default=DEFAULTS["out_dir"])
    ap.add_argument("--lora-r", type=int, default=DEFAULTS["lora_r"])
    args = ap.parse_args()

    cfg = dict(DEFAULTS)
    cfg["base_model"] = args.base_model
    cfg["out_dir"] = args.out_dir
    cfg["lora_r"] = args.lora_r

    if args.dry_run:
        print(json.dumps({"stage": "PLAN (ROADMAP - requires GPU; not run here)",
                          "plan": _plan(cfg)}, indent=2, sort_keys=True))
        return 0

    if os.environ.get("SZL_ALLOW_TRAIN") != "1":
        print("train_sovereign: REFUSING to train. This is a ROADMAP / GPU-only "
              "script and must not run in CI or the HF Space.\n"
              "Set SZL_ALLOW_TRAIN=1 on the sovereign tower to proceed, or use "
              "--dry-run to preview the plan.", file=sys.stderr)
        return 2

    return run(cfg, diagnostic=args.diagnostic)


if __name__ == "__main__":
    sys.exit(main())
