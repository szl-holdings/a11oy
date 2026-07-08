#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) - Doctrine v11 LOCKED
"""train_orpo.py - ORPO doctrine alignment, continuing from the SFT adapter.

TURNKEY / GPU-ONLY. Stage 2 of 3. Runs AFTER train_sft.py has written
outputs/sft-lora. Continues that same LoRA adapter with ORPO preference
alignment on szl_orpo.jsonl, saves to outputs/orpo-lora, then runs the
held-out refusal-to-fabricate eval (szl_orpo_eval.jsonl) and prints the REAL
pass rate.

Config (grounded, do not drift): ORPO beta=0.1, lr=8e-6, per_device_batch=2,
grad_accum=4, max_seq_len=2048, bf16 (fp16 fallback), 1 epoch default.

Leader source (cited, never claimed as ours):
  ORPO: Hong, Lee & Thorne (2024), "ORPO: Monotonic Odds Ratio Preference
        Optimization without Reference Model", arXiv:2403.07691.

HONEST EVAL. The eval is a preference-accuracy check: for each held-out pair the
model scores the honest `chosen` answer against the fabricating `rejected` one
(mean token log-prob of each completion). A row PASSES only when the model
assigns higher likelihood to the honest answer. The printed pass rate is the
real fraction that passed - it is never hardcoded and a fake pass is a doctrine
failure. A truthful low number beats a fabricated green.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRAIN_DIR = os.path.dirname(HERE)                            # training/
ORPO = os.path.join(TRAIN_DIR, "szl_orpo.jsonl")             # preference pairs
EVAL = os.path.join(TRAIN_DIR, "szl_orpo_eval.jsonl")        # held-out eval
SFT_ADAPTER = os.path.join(HERE, "outputs", "sft-lora")
OUT_DIR = os.path.join(HERE, "outputs", "orpo-lora")

MAX_SEQ_LEN = 2048
ORPO_BETA = 0.1
LR = 8e-6
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


def _completion_nll(model, tokenizer, system, prompt, completion, device):
    """Mean negative log-likelihood the model assigns to `completion` tokens
    given the chat prompt. Lower = the model prefers this answer."""
    import torch

    head = [{"role": "system", "content": system},
            {"role": "user", "content": prompt}]
    prompt_ids = tokenizer.apply_chat_template(
        head, tokenize=True, add_generation_prompt=True)
    comp_ids = tokenizer(completion, add_special_tokens=False)["input_ids"]
    comp_ids = comp_ids + [tokenizer.eos_token_id]

    input_ids = torch.tensor([prompt_ids + comp_ids], device=device)
    labels = input_ids.clone()
    labels[0, :len(prompt_ids)] = -100          # score only completion tokens

    with torch.no_grad():
        out = model(input_ids=input_ids, labels=labels)
    return float(out.loss)                        # HF returns mean NLL over -100-masked labels


def run_eval(model, tokenizer):
    import torch
    from collections import defaultdict

    if not os.path.exists(EVAL):
        print("train_orpo: eval file missing: %s" % EVAL, file=sys.stderr)
        return None

    try:
        from unsloth import FastLanguageModel
        FastLanguageModel.for_inference(model)
    except Exception:
        model.eval()

    device = next(model.parameters()).device
    rows = _load_jsonl(EVAL)
    per_family = defaultdict(lambda: [0, 0])       # family -> [passed, total]
    passed = 0
    print("\n---- refusal-to-fabricate eval (szl_orpo_eval.jsonl) ----")
    for r in rows:
        nll_chosen = _completion_nll(model, tokenizer, r["system"],
                                     r["prompt"], r["chosen"], device)
        nll_rejected = _completion_nll(model, tokenizer, r["system"],
                                       r["prompt"], r["rejected"], device)
        ok = nll_chosen < nll_rejected             # honest answer more likely
        passed += int(ok)
        fam = r.get("family", "unknown")
        per_family[fam][0] += int(ok)
        per_family[fam][1] += 1
        print("  [%s] %-22s  chosen_nll=%.3f rejected_nll=%.3f  %s"
              % ("PASS" if ok else "FAIL", fam, nll_chosen, nll_rejected,
                 r["prompt"][:48]))

    total = len(rows)
    rate = passed / total if total else 0.0
    print("\n  per-family:")
    for fam in sorted(per_family):
        p, t = per_family[fam]
        print("    %-22s %d/%d" % (fam, p, t))
    print("\n  REFUSAL-TO-FABRICATE PASS RATE: %d/%d = %.1f%%  (REAL, not hardcoded)"
          % (passed, total, 100.0 * rate))
    return rate


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--epochs", type=int, default=1, help="ORPO epochs")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--batch", type=int, default=BATCH,
                    help="per_device_train_batch_size (lower to 1 on OOM)")
    ap.add_argument("--max-seq-len", type=int, default=MAX_SEQ_LEN)
    ap.add_argument("--eval-only", action="store_true",
                    help="skip training; just run the eval on outputs/orpo-lora")
    args = ap.parse_args()

    import torch
    from unsloth import FastLanguageModel
    from datasets import Dataset
    from trl import ORPOTrainer, ORPOConfig

    if not torch.cuda.is_available():
        print("train_orpo: no CUDA device visible; run on the box.",
              file=sys.stderr)
        return 2

    use_bf16 = bool(torch.cuda.is_bf16_supported())
    print("train_orpo: device=%s  bf16=%s (fp16=%s)"
          % (torch.cuda.get_device_name(0), use_bf16, not use_bf16))

    # Continue the SAME adapter the SFT stage produced. Unsloth loads the base
    # from the adapter's config and re-attaches the LoRA as trainable.
    load_from = args.out_dir if args.eval_only else SFT_ADAPTER
    if not os.path.isdir(load_from):
        print("train_orpo: adapter dir not found: %s\nRun train_sft.py first."
              % load_from, file=sys.stderr)
        return 2

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=load_from,
        max_seq_length=args.max_seq_len,
        load_in_4bit=True,
        dtype=None,
    )

    if args.eval_only:
        rate = run_eval(model, tokenizer)
        return 0 if rate is not None else 2

    if not os.path.exists(ORPO):
        print("train_orpo: corpus not found: %s" % ORPO, file=sys.stderr)
        return 2

    def _fmt(row):
        head = [{"role": "system", "content": row["system"]},
                {"role": "user", "content": row["prompt"]}]
        prompt = tokenizer.apply_chat_template(head, tokenize=False,
                                               add_generation_prompt=True)
        return {"prompt": prompt, "chosen": row["chosen"],
                "rejected": row["rejected"]}

    pairs = _load_jsonl(ORPO)
    orpo_ds = Dataset.from_list([_fmt(r) for r in pairs])
    print("train_orpo: %d preference pairs from %s"
          % (len(pairs), os.path.relpath(ORPO, HERE)))

    orpo_args = ORPOConfig(
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=GRAD_ACCUM,
        num_train_epochs=args.epochs,
        learning_rate=LR,
        beta=ORPO_BETA,
        warmup_ratio=WARMUP_RATIO,
        logging_steps=1,
        optim="paged_adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=SEED_RNG,
        bf16=use_bf16,
        fp16=not use_bf16,
        max_length=args.max_seq_len,
        max_prompt_length=args.max_seq_len // 2,
        output_dir=os.path.join(HERE, "outputs", "orpo-trainer"),
        report_to="none",
    )
    trainer = ORPOTrainer(model=model, tokenizer=tokenizer,
                          train_dataset=orpo_ds, args=orpo_args)
    result = trainer.train()

    vram_gb = torch.cuda.max_memory_reserved() / 1e9
    steps = int(result.global_step)
    final_loss = float(result.training_loss)

    os.makedirs(args.out_dir, exist_ok=True)
    model.save_pretrained(args.out_dir)
    tokenizer.save_pretrained(args.out_dir)

    print("\n================ ORPO DONE ================")
    print("peak VRAM reserved : %.2f GB (torch.cuda, real reading)" % vram_gb)
    print("optimizer steps    : %d" % steps)
    print("final train loss   : %.4f" % final_loss)
    print("adapter saved      : %s" % args.out_dir)

    rate = run_eval(model, tokenizer)

    print("\nnext               : python export_gguf.py")
    print("provenance         : MODELED (no receipt until a signed run fills it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
