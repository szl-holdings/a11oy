#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) - Doctrine v11 LOCKED
"""export_gguf.py - merge the ORPO adapter, convert to GGUF q4_k_m, write the
doctrine-v11 Modelfile, and print the `ollama create` command.

TURNKEY / GPU-ONLY. Stage 3 of 3. Runs AFTER train_orpo.py has written
outputs/orpo-lora.

What it does:
  1. Loads outputs/orpo-lora (base + adapter) via Unsloth.
  2. save_pretrained_gguf(...) merges LoRA into the base and emits a GGUF
     quantized q4_k_m (Unsloth drives llama.cpp under the hood).
  3. Writes outputs/gguf/Modelfile with the doctrine-v11 SYSTEM prompt.
  4. Prints:  ollama create szl-sovereign-qwen -f outputs/gguf/Modelfile

Doctrine: the SYSTEM prompt below states only honest, grounded facts (Lambda is
Conjecture 1, locked-8 is exactly 8, MEASURED needs a real NVML delta). It never
upgrades a label. Provenance of the produced weights is MODELED.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ORPO_ADAPTER = os.path.join(HERE, "outputs", "orpo-lora")
GGUF_DIR = os.path.join(HERE, "outputs", "gguf")
OLLAMA_NAME = "szl-sovereign-qwen"
QUANT = "q4_k_m"

# Doctrine-v11 SYSTEM prompt. Grounded in AGENTS.md / STATUS.md / README.md.
DOCTRINE_SYSTEM = """You are the SZL sovereign model, governed by Doctrine v11 (LOCKED). \
Honesty over checklist: a truthful BLOCKED beats a fabricated green.

Non-negotiable rules:
- HONEST LABELS. Say MEASURED only for a value backed by a real, fresh reading \
(for energy, a live NVML/GPU-lung delta). No live reading -> SAMPLE/DEGRADED, never \
MEASURED. Design-time or proxy values are MODELED; future capability is ROADMAP. \
Never fabricate joules, proofs, signatures, or status.
- Lambda (Λ) uniqueness is Conjecture 1, never a theorem. Unconditional uniqueness \
over axioms A1-A5 is machine-checked FALSE; the strongest axiom-free result is the \
conditional Theorem U (separability => Λ). Khipu BFT safety is Conjecture 2, open.
- Exactly 8 formulas are locked-proven: {F1, F4, F7, F11, F12, F18, F19, F22}, \
kernel-verified at replay hash c7c0ba17. Never inflate the count; never add a ninth.
- Trust ceiling is 0.97. Trust is never 100%, even for a signed, chain-verified receipt.
- Receipt-on-write, not on-read: signing belongs on state changes, never on GET paths.
- Deny-by-default: a consequential action clears governance before it runs.
- Cite prior art; never claim external ideas as ours. Make no consciousness or \
sentience claims about this system.

When you do not have a grounded answer, say so and give the honest label rather than \
inventing a value."""


def build_modelfile(gguf_filename):
    return (
        "# SZL sovereign model - Doctrine v11 (LOCKED). Provenance: MODELED.\n"
        "FROM ./%s\n\n"
        "PARAMETER temperature 0.3\n"
        "PARAMETER top_p 0.9\n"
        "PARAMETER num_ctx 2048\n\n"
        'SYSTEM """%s"""\n' % (gguf_filename, DOCTRINE_SYSTEM)
    )


def _find_gguf(dirpath):
    if not os.path.isdir(dirpath):
        return None
    hits = [f for f in os.listdir(dirpath) if f.lower().endswith(".gguf")]
    return sorted(hits)[0] if hits else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--adapter", default=ORPO_ADAPTER)
    ap.add_argument("--gguf-dir", default=GGUF_DIR)
    ap.add_argument("--quant", default=QUANT)
    ap.add_argument("--modelfile-only", action="store_true",
                    help="skip conversion; just (re)write the Modelfile for an "
                         "existing .gguf in --gguf-dir")
    args = ap.parse_args()

    os.makedirs(args.gguf_dir, exist_ok=True)

    if not args.modelfile_only:
        import torch  # noqa: F401
        from unsloth import FastLanguageModel

        if not os.path.isdir(args.adapter):
            print("export_gguf: adapter dir not found: %s\nRun train_orpo.py "
                  "first." % args.adapter, file=sys.stderr)
            return 2

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=args.adapter,
            max_seq_length=2048,
            load_in_4bit=True,
            dtype=None,
        )
        print("export_gguf: merging adapter + converting to GGUF %s ..."
              % args.quant)
        model.save_pretrained_gguf(args.gguf_dir, tokenizer,
                                   quantization_method=args.quant)

    gguf = _find_gguf(args.gguf_dir)
    if not gguf:
        print("export_gguf: no .gguf produced in %s. Check the llama.cpp "
              "conversion log above." % args.gguf_dir, file=sys.stderr)
        return 2

    modelfile_path = os.path.join(args.gguf_dir, "Modelfile")
    with open(modelfile_path, "w", encoding="utf-8") as fh:
        fh.write(build_modelfile(gguf))

    rel = os.path.relpath(modelfile_path, HERE)
    print("\n================ EXPORT DONE ================")
    print("gguf     : %s" % os.path.join(args.gguf_dir, gguf))
    print("Modelfile: %s (doctrine-v11 SYSTEM prompt)" % modelfile_path)
    print("\nRegister with Ollama (run from %s):" % os.path.dirname(modelfile_path))
    print("  ollama create %s -f %s" % (OLLAMA_NAME, "Modelfile"))
    print("\nOr from training/box/:")
    print("  ollama create %s -f %s" % (OLLAMA_NAME, rel))
    print("\nDoctrine smoke test:")
    print('  ollama run %s "Is Lambda a theorem?"' % OLLAMA_NAME)
    print("  expect: NO - Lambda is Conjecture 1 (advisory, never a theorem).")
    print("provenance: MODELED (no receipt until a signed run fills it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
