#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) - Doctrine v11 LOCKED
"""build_formula_corpus.py - deterministic SZL-formula Q/A miner (TRACK C / STAGE 1).

Reads the live SZL formula registry (``training/data/formulas_live.json``, the
``{count, formulas}`` payload of ``/api/a11oy/v1/formulas``) and emits a
HIGH-QUALITY supervised fine-tune corpus in chat format at
``training/szl_formula_corpus.jsonl`` teaching each formula from its REAL fields:
``name``, ``signature``, ``proof_status``, ``doc`` and (when present) ``chakra``.

HONEST-LABEL DISCIPLINE (never upgrade a proof status)
------------------------------------------------------
Every assistant answer quotes the formula's ``proof_status`` VERBATIM and phrases
its meaning honestly by the recorded status - never upgrading it:

  * PROVEN(...)   -> proven exactly as recorded (with its stated hypotheses).
  * AXIOM(...)    -> an assumed axiom, NOT a proved theorem.
  * SORRY(...)    -> NOT yet proven: the Lean proof still carries a `sorry`.
  * REAL(...)     -> a real external integration as recorded (e.g. Sigstore/Rekor).

Λ (``lambda_aggregate``) is a load-bearing case: its recorded status is
"PROVEN(A1-A4); uniqueness CONJECTURE", so the corpus states Λ-aggregation as
proven on A1-A4 while Λ-uniqueness stays **Conjecture 1** - never a theorem. A
separate doctrine fact records that the proof-carrying canonical registry admits
exactly five locked formulas {F1, F11, F12, F18, F19}; F4/F7/F22 remain
source-present experimental entries. The
registry indexing here is not folded into that count and no entry is re-badged.

DETERMINISM: no randomness, no clock, no network. Same registry -> byte-identical
output (formulas iterated in file order; output sorted by prompt). Pure stdlib.

DOCTRINE SELF-GUARD: the emitted corpus is CLEAN and NOT allowlisted. Any candidate
example that would trip the authoritative banned-token gate
(scripts/check_banned_tokens.py) is DROPPED; the guard is IMPORTED from the gate so
this file never enumerates a banned token itself.

Usage:
    python training/build_formula_corpus.py            # writes szl_formula_corpus.jsonl
    python training/build_formula_corpus.py --check     # verify only, no write
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "training", "data", "formulas_live.json")
MASTER = os.path.join(REPO, "training", "data", "formula_corpus_master.md")
OUT = os.path.join(REPO, "training", "szl_formula_corpus.jsonl")

SYSTEM = "You are the SZL sovereign model. Doctrine v11."

# ── DOCTRINE SELF-GUARD (imported, never enumerated here) ──────────────────────
sys.path.insert(0, os.path.join(REPO, "scripts"))
from check_banned_tokens import (  # noqa: E402
    BANNED_NO_LEADING,
    LEADING_RE,
    TAILWIND_LEADING_RE,
)


def _clean(text):
    if BANNED_NO_LEADING.search(text):
        return False
    if LEADING_RE.search(text) and not TAILWIND_LEADING_RE.search(text):
        return False
    return True


def _status_gloss(status):
    """Honest, non-upgrading gloss keyed on the recorded proof_status prefix."""
    s = status.strip()
    head = s.split("(")[0].split(";")[0].strip().upper()
    if head == "PROVEN":
        base = ("proven exactly as recorded, on its stated hypotheses - not "
                "extended beyond them")
    elif head == "AXIOM":
        base = ("an assumed AXIOM, not a proved theorem - it is taken as a "
                "hypothesis, never presented as proven")
    elif head == "SORRY":
        base = ("NOT yet proven: the Lean proof still carries a `sorry` "
                "placeholder, so it is honestly open")
    elif head == "REAL":
        base = ("a real external integration as recorded (e.g. Sigstore/Rekor), "
                "labelled for what it actually is")
    else:
        base = "recorded with the status shown, stated verbatim and never upgraded"
    # Λ uniqueness is always called out as Conjecture 1.
    if "CONJECTURE" in s.upper():
        base += (". Any uniqueness / conjecture part stays a conjecture - for Λ "
                 "that is Conjecture 1, never a theorem")
    return base


def formula_examples(f):
    name = str(f.get("name", "")).strip()
    sig = str(f.get("signature", "")).strip()
    status = str(f.get("proof_status", "")).strip()
    doc = str(f.get("doc", "")).strip()
    chakra = f.get("chakra")
    gloss = _status_gloss(status)
    chakra_line = (" Registry chakra index: %s." % chakra) if chakra is not None else ""

    out = []
    # T1 - state the formula (signature + doc + verbatim status).
    u1 = "State the %s formula from the SZL registry." % name
    a1 = ("%s has signature %s. %s Its recorded proof status is \"%s\", stated "
          "verbatim; it is %s.%s"
          % (name, sig, doc, status, gloss, chakra_line))
    out.append((u1, a1))

    # T2 - what it governs / covers (doc-grounded).
    if doc:
        u2 = "What does the SZL formula %s govern?" % name
        a2 = ("%s: %s Recorded proof status \"%s\" - %s." % (name, doc, status, gloss))
        out.append((u2, a2))

    # T3 - is it proven? (strictly from the recorded status).
    u3 = "Is the SZL formula %s proven?" % name
    a3 = ("Its recorded proof status is \"%s\". In honest terms it is %s. I quote "
          "the registry status verbatim and never upgrade it." % (status, gloss))
    out.append((u3, a3))
    return out


def meta_examples(count):
    return [
        ("How many formulas are in the SZL formula registry?",
         "The registry (/api/a11oy/v1/formulas) records %d formulas, each carrying "
         "its own verbatim proof_status. That registry count is distinct from the "
         "kernel-locked-proven set." % count),
        ("How many formulas are locked-proven, and which ones?",
         "Exactly 5: {F1, F11, F12, F18, F19}, admitted by the proof-carrying "
         "canonical registry. F4, F7, and F22 remain source-present experimental "
         "entries and are not folded into the locked set."),
        ("Is Lambda (Λ) a proven theorem in the formula registry?",
         "No. Λ (lambda_aggregate) is recorded as \"PROVEN(A1-A4); uniqueness "
         "CONJECTURE\": Λ-aggregation is proven on axioms A1-A4, but Λ-uniqueness "
         "is Conjecture 1 - never a theorem. I state both out loud."),
        ("Can I upgrade a formula's SORRY or AXIOM status if it looks correct?",
         "No. A `sorry` means the Lean proof is incomplete (honestly open) and an "
         "AXIOM is an assumed hypothesis, not a theorem. Neither is ever re-badged "
         "PROVEN; the recorded status is quoted verbatim."),
    ]


def build():
    with open(DATA, "r", encoding="utf-8") as fh:
        reg = json.load(fh)
    formulas = reg["formulas"]
    seen = set()
    examples = []
    pairs = list(meta_examples(reg.get("count", len(formulas))))
    for f in formulas:
        pairs.extend(formula_examples(f))
    for user, ans in pairs:
        if not (_clean(user) and _clean(ans)):
            continue
        key = user.strip()
        if key in seen:
            continue
        seen.add(key)
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user.strip()},
            {"role": "assistant", "content": ans.strip()},
        ]})
    examples.sort(key=lambda e: e["messages"][1]["content"])
    return examples


def main():
    ap = argparse.ArgumentParser(description="Build the SZL formula corpus.")
    ap.add_argument("--check", action="store_true",
                    help="verify counts/cleanliness only; do not write")
    args = ap.parse_args()

    examples = build()
    n = len(examples)
    assert 40 <= n <= 200, "formula corpus count %d outside expected [40,200]" % n
    for ex in examples:
        for msg in ex["messages"]:
            assert _clean(msg["content"]), "banned token leaked into formula corpus"

    if args.check:
        print("build_formula_corpus: OK - %d clean examples (would write %s)"
              % (n, OUT))
        return 0

    with open(OUT, "w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex, ensure_ascii=False, sort_keys=True) + "\n")
    print("build_formula_corpus: wrote %d examples -> %s" % (n, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
