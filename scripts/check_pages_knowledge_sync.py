#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Signed-off-by: Forge (Replit task agent) <forge@szl-holdings>
#
# Knowledge-corpus consistency + honesty guard  (pages/knowledge.json <- knowledge.json).
#
# a11oy ships TWO copies of the corpus:
#   * root  knowledge.json        — the CANONICAL, kernel-derived corpus (theorems /
#                                    formulas / axioms + honesty labels + proof_summary).
#                                    This is what killinchu mirrors byte-for-byte.
#   * pages/knowledge.json        — a lighter copy SERVED by the a11oy console.
#
# Unlike the killinchu mirror, pages/knowledge.json is NOT byte-identical to root by
# design (the console serves a trimmed view: fewer fields, its own version string).
# So this is a CONSISTENCY guard, not a byte-identity guard. The danger it closes:
# the served copy can quietly OVERCLAIM relative to the canonical corpus (e.g. mark
# Conjecture 1 / Λ-uniqueness "proven" when root honestly keeps it "conjectured") or
# drop the honesty ledger entirely, with no CI catching it.
#
# root is the SOURCE OF TRUTH. This guard FAILS if:
#   * the SERVED copy overclaims relative to root — any theorem, FORMULA or AXIOM
#     present (and honesty-labelled) in BOTH copies must carry the SAME maturity in
#     pages as in root (pages may carry a SUBSET of items, or omit the label
#     entirely as a lighter view, but never a stronger honesty label), AND the
#     honesty ledger that governs Conjecture 1 (proof_summary.conjecture /
#     locked_ids / locked_count_theorem) must match root, OR
#   * EITHER copy violates a Doctrine-v11 honesty invariant (so a dishonest corpus
#     can never be served silently).
#
# Honesty invariants enforced (Doctrine v11) — identical to the killinchu
# knowledge-corpus-sync guard, reused verbatim so the two organs apply the SAME
# honesty logic. These catch OVERCLAIMS, not legitimate corpus growth:
#   * The corpus parses as JSON and declares a top-level `version`.
#   * The corpus self-declares Doctrine v11 (the `v11` token is present).
#   * Λ-uniqueness / Conjecture 1 stays OPEN: the Λ_uniqueness theorem (TH_L1) has
#     maturity == "conjectured" (NEVER "proven"); proof_summary.conjecture lists
#     "F23"; and "F23" is NOT in proof_summary.locked_ids. (Unconditional
#     Λ-uniqueness (Conjecture 1) is machine-FALSE under A1-A5; only the conditional
#     theorem holds.)
#   * The locked kernel count is machine-pinned (proof_summary.locked_count_theorem
#     present) — the exact number is NOT pinned here, it evolves with the kernel.
#   * Theorem U (if the corpus mentions it) is qualified "conditional".
#
# Usage:
#   check_pages_knowledge_sync.py --root <knowledge.json> \
#                                 --pages <pages/knowledge.json>
#
# Exit code 0 = consistent and honest; 1 = consistency drift or honesty violation
# (fail the build); 2 = usage / missing-input error.

import argparse
import json
import os
import sys


def load_corpus(path):
    """Return (text, parsed_or_None). Never raises on bad JSON."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        obj = json.loads(text)
    except Exception:
        obj = None
    return text, obj


def find_lambda_theorem(corpus):
    """Return the Λ-uniqueness (TH_L1 / Conjecture 1) theorem dict, or None."""
    for t in (corpus.get("theorems") or []):
        if not isinstance(t, dict):
            continue
        name = (t.get("name") or "")
        if t.get("id") == "TH_L1" or "uniqueness" in name.lower():
            return t
    return None


def validate_honesty(text, corpus, label):
    """Return a list of Doctrine-v11 honesty violations for one corpus.

    Identical logic to killinchu/scripts/check_knowledge_corpus_sync.py so both
    organs enforce the SAME honesty invariants.
    """
    errors = []

    if not isinstance(corpus, dict):
        return [f"{label}: corpus is not a valid JSON object"]

    # 1. version present
    if not corpus.get("version"):
        errors.append(f"{label}: missing top-level 'version'")

    # 2. Doctrine v11 self-declared
    if "v11" not in text:
        errors.append(f"{label}: corpus does not declare Doctrine v11 ('v11' token absent)")

    # 3. Λ-uniqueness / Conjecture 1 must remain OPEN (never marked proven)
    lam = find_lambda_theorem(corpus)
    if lam is None:
        errors.append(
            f"{label}: Λ-uniqueness entry (TH_L1, Conjecture 1) not found — cannot verify "
            f"Conjecture 1 honesty"
        )
    else:
        mat = (lam.get("maturity") or "").strip().lower()
        if mat != "conjectured":
            errors.append(
                f"{label}: Λ-uniqueness (TH_L1) maturity is "
                f"'{lam.get('maturity')}', must be 'conjectured' — Conjecture 1 is "
                f"OPEN (unconditional uniqueness is machine-FALSE under A1-A5)"
            )

    # 4. proof_summary honesty ledger: F23 is a conjecture, not a locked proof
    ps = corpus.get("proof_summary") or {}
    if not isinstance(ps, dict):
        ps = {}
    conjecture = ps.get("conjecture") or []
    locked_ids = ps.get("locked_ids") or []
    if "F23" not in conjecture:
        errors.append(
            f"{label}: proof_summary.conjecture must include 'F23' "
            f"(Conjecture 1 / Λ-uniqueness is OPEN)"
        )
    if "F23" in locked_ids:
        errors.append(
            f"{label}: 'F23' must NOT appear in proof_summary.locked_ids "
            f"(Conjecture 1 is not proven)"
        )
    if not ps.get("locked_count_theorem"):
        errors.append(
            f"{label}: proof_summary.locked_count_theorem missing — the locked "
            f"kernel count is not machine-pinned"
        )

    # 5. Theorem U (if present) must be qualified conditional
    if "Theorem U" in text and "conditional" not in text.lower():
        errors.append(
            f"{label}: 'Theorem U' is mentioned but the corpus never qualifies it "
            f"as 'conditional'"
        )

    return errors


def check_collection_overclaim(root, pages, key, noun, root_name, pages_name):
    """Return honesty-label mismatches for one shared collection (theorems /
    formulas / axioms).

    For every item id present in BOTH copies, if the SERVED copy carries a
    maturity/honesty label, that label must MATCH the canonical root label. A
    served item that OMITS the label makes no claim (the console serves a lighter
    view with fewer fields) — that is a legitimate subset, NOT an overclaim, so it
    is skipped. Only a DISAGREEING label is a violation.
    """
    errors = []
    root_mat = {}
    for item in (root.get(key) or []):
        if isinstance(item, dict) and item.get("id"):
            root_mat[item["id"]] = (item.get("maturity") or "").strip()
    for item in (pages.get(key) or []):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        iid = item["id"]
        if iid not in root_mat:
            continue
        pmat = (item.get("maturity") or "").strip()
        if not pmat:
            # served copy omits the label => makes no claim => not an overclaim.
            continue
        if pmat != root_mat[iid]:
            errors.append(
                f"{pages_name}: {noun} {iid} maturity '{pmat}' disagrees with "
                f"{root_name} '{root_mat[iid]}' — the served copy must not "
                f"restate a canonical honesty label"
            )
    return errors


def validate_consistency(root, pages, root_name="knowledge.json",
                         pages_name="pages/knowledge.json"):
    """Return a list of consistency violations: the SERVED copy (pages) must never
    overclaim relative to the CANONICAL root copy.

    pages may legitimately carry a SUBSET of root's theorems/formulas/axioms (it
    is a lighter console view) and its own version string, but for anything it
    DOES carry — and DOES label — it must agree with root's honesty stance.
    """
    errors = []
    if not isinstance(root, dict):
        return [f"{root_name}: not a valid JSON object — cannot use as source of truth"]
    if not isinstance(pages, dict):
        return [f"{pages_name}: not a valid JSON object — cannot compare to root"]

    # 1. Per-item maturity for theorems, formulas AND axioms: any id present in
    #    BOTH copies that the SERVED copy labels must match root's honesty label.
    #    (A served item that omits the label makes no claim — see helper.)
    for key, noun in (("theorems", "theorem"),
                      ("formulas", "formula"),
                      ("axioms", "axiom")):
        errors.extend(
            check_collection_overclaim(root, pages, key, noun,
                                       root_name, pages_name)
        )

    # 2. Honesty ledger that governs Conjecture 1 must match root.
    rps = root.get("proof_summary") or {}
    pps = pages.get("proof_summary") or {}
    if not isinstance(rps, dict):
        rps = {}
    if not isinstance(pps, dict):
        pps = {}
    for field in ("conjecture", "locked_ids"):
        rv = sorted(rps.get(field) or [])
        pv = sorted(pps.get(field) or [])
        if rv != pv:
            errors.append(
                f"{pages_name}: proof_summary.{field} {pv} disagrees with "
                f"{root_name} {rv} — Conjecture-1 honesty ledger out of sync"
            )
    if (pps.get("locked_count_theorem") or None) != (rps.get("locked_count_theorem") or None):
        errors.append(
            f"{pages_name}: proof_summary.locked_count_theorem "
            f"'{pps.get('locked_count_theorem')}' disagrees with {root_name} "
            f"'{rps.get('locked_count_theorem')}' — locked-count pin out of sync"
        )

    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Guard: a11oy's served pages/knowledge.json stays consistent "
        "with the canonical knowledge.json + Doctrine-v11 honesty invariants."
    )
    ap.add_argument("--root", dest="root_path", required=True,
                    help="path to the canonical (source-of-truth) knowledge.json")
    ap.add_argument("--pages", dest="pages_path", required=True,
                    help="path to the console-served pages/knowledge.json")
    ap.add_argument("--root-name", default="knowledge.json")
    ap.add_argument("--pages-name", default="pages/knowledge.json")
    args = ap.parse_args(argv)

    for p, who in ((args.root_path, args.root_name),
                   (args.pages_path, args.pages_name)):
        if not os.path.isfile(p):
            print(f"::error::{who} not found at {p}")
            return 2

    root_text, root = load_corpus(args.root_path)
    pages_text, pages = load_corpus(args.pages_path)

    print(f"Knowledge-corpus consistency guard: {args.pages_name} <- "
          f"{args.root_name} (root is the source of truth)")
    print(f"  {args.root_name:<22} {args.root_path}")
    print(f"  {args.pages_name:<22} {args.pages_path}")
    print()

    failed = False

    # 1) honesty invariants on BOTH copies (canonical AND served).
    seen = set()
    for text, obj, name in ((root_text, root, args.root_name),
                            (pages_text, pages, args.pages_name)):
        for err in validate_honesty(text, obj, name):
            if err in seen:
                continue
            seen.add(err)
            failed = True
            print(f"::error::{err}")
    if not seen:
        print("OK: Doctrine-v11 honesty invariants satisfied on both copies "
              "(Conjecture 1 OPEN, locked kernel count pinned, Theorem U conditional).")

    # 2) consistency: the served copy must not overclaim relative to root.
    cons = validate_consistency(root, pages, args.root_name, args.pages_name)
    if cons:
        for err in cons:
            failed = True
            print(f"::error::{err}")
    else:
        print(f"OK: {args.pages_name} is consistent with {args.root_name} "
              "(no overclaim; Conjecture-1 honesty ledger in sync).")

    print()
    if failed:
        print("FAIL: served knowledge corpus is inconsistent with the canonical "
              "copy or violates a Doctrine-v11 honesty invariant.")
        return 1
    print("PASS: pages/knowledge.json consistent with knowledge.json and honest.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
