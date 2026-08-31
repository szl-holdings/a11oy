# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO) + Perplexity Computer Agent — Stage-B corpus builder
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
build_corpus.py — turn the founder's SZL docs into a Stage-B instruction corpus.

HONEST STATUS (Doctrine v11): this is a TEMPLATE / SCAFFOLD the founder fills.
  It does NOT write instruction→output pairs on its own. Auto-generating the
  `output` (the "right answer") from raw docs would be fabrication — the model
  would learn hallucinated answers. Instead this tool:
    1. Walks the founder's doc roots (repos, papers) for .md / .txt / .rst.
    2. Chunks each doc into readable passages.
    3. Emits DRAFT rows with a real `input` (the source passage + its path) and
       a PLACEHOLDER `output` clearly marked "TODO(founder): write the answer".
    4. Prepends the Doctrine-v11 seed rows from corpus_template.jsonl so the
       adapter always learns the honest-label behavior.
  The founder then edits each DRAFT row's `output` (and `instruction`) by hand,
  deletes rows that aren't useful, and removes every "TODO(founder)" marker.

  `validate` mode refuses to bless a corpus that still contains TODO markers —
  so a half-written corpus can't silently reach train_lora.py.

Λ = Conjecture 1 (advisory). A corpus is a MODELED artifact; it proves nothing.

USAGE:
  # 1. Draft rows from your doc roots (repos + papers):
  python build_corpus.py draft \
      --src ~/szl/a11oy --src ~/szl/szl-papers \
      --template corpus_template.jsonl \
      --out corpus.draft.jsonl

  # 2. (Founder edits corpus.draft.jsonl by hand — fill every output.) Then:
  python build_corpus.py validate --corpus corpus.jsonl

Run `python build_corpus.py --help` for details.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

TODO_MARKER = "TODO(founder)"
_TEXT_EXT = (".md", ".txt", ".rst", ".mdx")
# Skip vendored / generated trees so drafts stay about the founder's own words.
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
              "dist", "build", "site", ".mypy_cache", ".pytest_cache"}


def _iter_docs(roots: list[str]):
    for root in roots:
        root = os.path.expanduser(root)
        if os.path.isfile(root):
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fn in filenames:
                if fn.lower().endswith(_TEXT_EXT):
                    yield os.path.join(dirpath, fn)


def _chunk(text: str, max_chars: int) -> list[str]:
    """Split on blank lines, then greedily pack paragraphs up to max_chars."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 2 <= max_chars:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                chunks.append(buf)
            buf = p if len(p) <= max_chars else p[:max_chars]
    if buf:
        chunks.append(buf)
    return chunks


def _load_seed(template: str) -> list[dict]:
    """Load the Doctrine-v11 seed rows (skips the TEMPLATE row so seeds are
    real, trainable examples). Fails loud if the template is missing."""
    if not os.path.exists(template):
        raise FileNotFoundError(f"template not found: {template}")
    seeds: list[dict] = []
    with open(template, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            blob = json.dumps(obj)
            if "TEMPLATE" in blob or TODO_MARKER in blob:
                continue  # drop the illustrative TEMPLATE row
            seeds.append(obj)
    return seeds


def cmd_draft(args: argparse.Namespace) -> int:
    seeds = _load_seed(args.template)
    n_draft = 0
    with open(args.out, "w", encoding="utf-8") as out:
        # 1. Honest-label seed rows first — always in the corpus.
        for s in seeds:
            out.write(json.dumps(s, ensure_ascii=False) + "\n")
        # 2. DRAFT rows from the founder's docs — real input, placeholder output.
        for path in _iter_docs(args.src):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            for chunk in _chunk(text, args.max_chars):
                row = {
                    "instruction": f"{TODO_MARKER}: write the question this passage from "
                                   f"{os.path.basename(path)} should answer, in the SZL voice.",
                    "input": f"[source: {path}]\n{chunk}",
                    "output": f"{TODO_MARKER}: write the doctrine-aligned answer. Honest labels; "
                              f"never claim Lambda is proven; cite this source; UNAVAILABLE if unsure.",
                }
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                n_draft += 1
    print(f"[DRAFT] wrote {len(seeds)} seed row(s) + {n_draft} DRAFT row(s) → {args.out}")
    print(f"  NEXT (founder): edit {args.out} — fill every '{TODO_MARKER}' output/instruction, "
          "delete rows you don't want, then rename to corpus.jsonl and run `validate`.")
    print("  Honest label: DRAFT — this file is NOT trainable until the TODO markers are gone.")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    if not os.path.exists(args.corpus):
        print(f"[UNAVAILABLE] corpus not found: {args.corpus}", file=sys.stderr)
        return 2
    todos = 0
    rows = 0
    bad = 0
    with open(args.corpus, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[FAIL] line {i}: invalid JSON: {e}", file=sys.stderr)
                bad += 1
                continue
            rows += 1
            if "instruction" not in obj or "output" not in obj:
                print(f"[FAIL] line {i}: missing 'instruction' or 'output'.", file=sys.stderr)
                bad += 1
            if TODO_MARKER in json.dumps(obj) or "TEMPLATE" in json.dumps(obj):
                todos += 1
    if bad or todos:
        print(f"[FAIL] corpus NOT ready: {rows} rows, {bad} malformed, "
              f"{todos} still contain '{TODO_MARKER}'/'TEMPLATE'. "
              "Fill/remove them before training.", file=sys.stderr)
        return 1
    print(f"[OK] corpus VALIDATED: {rows} rows, 0 TODO markers, 0 malformed. "
          "Ready for train_lora.py. Honest label: VALIDATED (not yet trained).")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Build a Stage-B instruction corpus from SZL docs (TEMPLATE the founder fills).")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("draft", help="Emit DRAFT rows from doc roots + doctrine seed rows.")
    d.add_argument("--src", action="append", required=True,
                   help="A doc root (repo dir or file). Repeatable: --src A --src B.")
    d.add_argument("--template", default="corpus_template.jsonl",
                   help="Doctrine-v11 seed rows (defaults to the shipped template).")
    d.add_argument("--out", default="corpus.draft.jsonl", help="Output DRAFT JSONL path.")
    d.add_argument("--max-chars", type=int, default=1200, help="Max chars per source chunk.")
    d.set_defaults(func=cmd_draft)

    v = sub.add_parser("validate", help="Refuse a corpus that still has TODO/TEMPLATE markers.")
    v.add_argument("--corpus", required=True, help="The corpus JSONL to validate.")
    v.set_defaults(func=cmd_validate)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
