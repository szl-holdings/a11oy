#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) - Doctrine v11 LOCKED
"""build_full_corpus.py - assemble the full SZL sovereign-model SFT corpus.

Concatenates, deduplicates and emits the corpus the sovereign model actually
trains on at ``training/szl_seed_full.jsonl`` (chat format), from four sources:

  1. SEED    - the original hand-verified doctrine seed (training/szl_seed.jsonl,
               167 examples). Read verbatim so the hand-checked answers are exact;
               falls back to build_seed.build() only if the file is absent.
  2. BRAIN   - build_brain_corpus.build(): Q/A grounded in the live 9,343-node
               brain graph (training/data/brain_graph.json). Never fabricated.
  3. FORMULA - build_formula_corpus.build(): Q/A grounded in the 22-formula
               registry (training/data/formulas_live.json), verbatim proof-status.
  4. SURFACE - one honest example per live 3D estate surface parsed from the
               szl3d_holographic.py SURFACES manifest.

DEDUP: near-identical prompts (normalised: lower-cased, whitespace-collapsed,
trailing punctuation stripped) are collapsed, keeping the FIRST occurrence in
source order (SEED > BRAIN > FORMULA > SURFACE), so the hand-verified seed wins
any collision. Per-source and post-dedup counts are printed.

DETERMINISM: no randomness, no clock, no network. Output is sorted by prompt ->
byte-identical on re-run. Pure Python standard library only.

DOCTRINE SELF-GUARD: the emitted corpus is CLEAN and NOT allowlisted. Every
example is re-checked against the authoritative banned-token gate
(scripts/check_banned_tokens.py, imported); any hit is dropped.

Usage:
    python training/build_full_corpus.py            # writes szl_seed_full.jsonl
    python training/build_full_corpus.py --check     # verify only, no write
"""
import argparse
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "training", "szl_seed_full.jsonl")
SEED_JSONL = os.path.join(REPO, "training", "szl_seed.jsonl")
HOLO = os.path.join(REPO, "szl3d_holographic.py")

SYSTEM = "You are the SZL sovereign model. Doctrine v11."

sys.path.insert(0, os.path.join(REPO, "training"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import build_brain_corpus  # noqa: E402
import build_formula_corpus  # noqa: E402
import build_seed  # noqa: E402
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


def _norm_prompt(p):
    """Normalise a prompt for near-duplicate detection."""
    p = re.sub(r"\s+", " ", p.strip().lower())
    return p.rstrip(" .?!:;")


def load_seed():
    """The 167 hand-verified seed examples, verbatim from the committed jsonl."""
    if os.path.isfile(SEED_JSONL):
        out = []
        with open(SEED_JSONL, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out
    return build_seed.build()


def _msg(user, ans):
    return {"messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user.strip()},
        {"role": "assistant", "content": ans.strip()},
    ]}


def load_surfaces():
    """One honest Q/A per live 3D estate surface from the SURFACES manifest."""
    out = []
    try:
        with open(HOLO, "r", encoding="utf-8") as fh:
            src = fh.read()
    except OSError:
        return out
    block = re.search(r"SURFACES[^\[]*\[(.*?)\n\]", src, re.DOTALL)
    if not block:
        return out
    for line in block.group(1).splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        mid = re.search(r'"id":\s*"([^"]+)"', line)
        mcat = re.search(r'"cat":\s*"([^"]+)"', line)
        mtitle = re.search(r'"title":\s*"([^"]+)"', line)
        if not (mid and mtitle):
            continue
        sid, title = mid.group(1), mtitle.group(1)
        cat = mcat.group(1) if mcat else "estate"
        user = ("What is the '%s' surface in the a11oy estate, and what is its "
                "endpoint and honest label?" % title)
        ans = ("'%s' (id '%s', category '%s') is one of the a11oy 3D estate "
               "surfaces served by szl3d_holographic.py under the /holographic "
               "shell (manifest at /api/a11oy/v1/holographic/info). Each of its "
               "traces polls a real a11oy endpoint and carries that endpoint's own "
               "honesty label; nothing is rendered as MEASURED unless it comes "
               "from a live reading, and any Λ-signal stays advisory (≤0.97, "
               "Conjecture 1). It renders with 0 runtime CDN (three.js vendored) "
               "and no purple." % (title, sid, cat))
        out.append(_msg(user, ans))
    return out


def build():
    sources = [
        ("seed", load_seed()),
        ("brain", build_brain_corpus.build()),
        ("formula", build_formula_corpus.build()),
        ("surface", load_surfaces()),
    ]
    seen = set()
    merged = []
    per_source = {}
    kept_source = {}
    for name, exs in sources:
        per_source[name] = len(exs)
        kept = 0
        for ex in exs:
            msgs = ex["messages"]
            user = next(m["content"] for m in msgs if m["role"] == "user")
            ans = next(m["content"] for m in msgs if m["role"] == "assistant")
            if not (_clean(user) and _clean(ans)):
                continue
            key = _norm_prompt(user)
            if key in seen:
                continue
            seen.add(key)
            merged.append(ex)
            kept += 1
        kept_source[name] = kept
    merged.sort(key=lambda e: next(m["content"] for m in e["messages"]
                                   if m["role"] == "user"))
    return merged, per_source, kept_source


def main():
    ap = argparse.ArgumentParser(description="Build the full SZL SFT corpus.")
    ap.add_argument("--check", action="store_true",
                    help="verify counts/cleanliness only; do not write")
    args = ap.parse_args()

    merged, per_source, kept_source = build()
    n = len(merged)
    for ex in merged:
        for msg in ex["messages"]:
            assert _clean(msg["content"]), "banned token leaked into full corpus"
    assert 1000 <= n <= 5000, "full corpus count %d outside expected [1000,5000]" % n

    raw = sum(per_source.values())
    print("build_full_corpus: sources (raw -> kept after clean+dedup):")
    for name in ("seed", "brain", "formula", "surface"):
        print("  %-8s %5d -> %5d" % (name, per_source[name], kept_source[name]))
    print("  %-8s %5d -> %5d (%d near-duplicate/unclean dropped)"
          % ("TOTAL", raw, n, raw - n))

    if args.check:
        print("build_full_corpus: OK - %d clean examples (would write %s)" % (n, OUT))
        return 0

    with open(OUT, "w", encoding="utf-8") as fh:
        for ex in merged:
            fh.write(json.dumps(ex, ensure_ascii=False, sort_keys=True) + "\n")
    print("build_full_corpus: wrote %d examples -> %s" % (n, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
