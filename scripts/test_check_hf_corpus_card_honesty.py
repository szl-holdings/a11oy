#!/usr/bin/env python3
# Signed-off-by: Forge (Replit task agent) <forge@szl-holdings>
"""Negative-fixture self-test for the card-honesty guard. Pure stdlib, offline.

Loads the SHIPPED .github/hf-corpus-guards.json so it tests the real deny /
require rules (not a copy) against honest cards (must pass) and tampered cards
(must fail), proving the rules neither false-trip nor miss an overclaim.

Run by file path:  python3 test_check_hf_corpus_card_honesty.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_hf_corpus_card_honesty as card  # noqa: E402
from szl_corpus_guard_common import (  # noqa: E402
    AuthError, Unreachable, EXIT_OK, EXIT_VIOLATION, EXIT_ERROR,
)

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", ".github", "hf-corpus-guards.json")

A11OY_HONEST = """# a11oy-verifiable-corpus
Every record is verify it yourself: recompute the content address and re-check the DSSE signature against the pinned key.
Theorem U is real but conditional (proven conditional on its hypotheses); it is not unconditionally proven.
Conjecture 1 (Lambda-uniqueness) is OPEN: it is machine-checked false in the finite model, it remains a conjecture and was never proven.
The locked-proven ladder is not collapsed: locked formulas stay locked and experimental work stays experimental.
"""

KILLINCHU_HONEST = """# killinchu-osint-corpus
Each record is a third-party claim aggregated from open sources, not attested truth.
The record id is a content-address (sha256), not a DSSE / Ed25519 signature.
No "proven" or "verified" claim is made about any individual item.
"""

FAILURES = []


def check(name, cond):
    if cond:
        print("  ok  - %s" % name)
    else:
        print("  FAIL- %s" % name)
        FAILURES.append(name)


def fetcher(mapping):
    def _f(cfg, ds, token):
        val = mapping.get(ds["repo_id"])
        if isinstance(val, Exception):
            raise val
        return val
    return _f


def load_cfg():
    with open(CONFIG, "r", encoding="utf-8") as fh:
        return json.load(fh)


A11OY = "SZLHOLDINGS/a11oy-verifiable-corpus"
KILL = "SZLHOLDINGS/killinchu-osint-corpus"


def main():
    cfg = load_cfg()

    # Both honest -> OK, no findings.
    code, res = card.evaluate(cfg, None, card_fetcher=fetcher(
        {A11OY: A11OY_HONEST, KILL: KILLINCHU_HONEST}))
    check("honest cards -> OK (rules do not false-trip)",
          code == EXIT_OK and all(not r["findings"] for r in res))

    # a11oy overclaim line -> VIOLATION.
    bad = A11OY_HONEST + "\nUpdate: Theorem U is now fully proven.\n"
    code, res = card.evaluate(cfg, None, card_fetcher=fetcher(
        {A11OY: bad, KILL: KILLINCHU_HONEST}))
    a = next(r for r in res if r["repo_id"] == A11OY)
    check("a11oy 'Theorem U proven' line -> VIOLATION",
          code == EXIT_VIOLATION and a["status"] == "violation")

    # a11oy 'Conjecture 1 proven' -> VIOLATION.
    bad2 = A11OY_HONEST + "\nConjecture 1 has now been proven.\n"
    code, res = card.evaluate(cfg, None, card_fetcher=fetcher(
        {A11OY: bad2, KILL: KILLINCHU_HONEST}))
    check("a11oy 'Conjecture 1 proven' -> VIOLATION", code == EXIT_VIOLATION)

    # a11oy missing a required anchor -> VIOLATION.
    dropped = A11OY_HONEST.replace("verify it yourself", "look at it")
    code, res = card.evaluate(cfg, None, card_fetcher=fetcher(
        {A11OY: dropped, KILL: KILLINCHU_HONEST}))
    a = next(r for r in res if r["repo_id"] == A11OY)
    check("a11oy dropped 'verify it yourself' anchor -> VIOLATION",
          code == EXIT_VIOLATION
          and any("anchor" in f for f in a["findings"]))

    # killinchu overclaim -> VIOLATION.
    kbad = KILLINCHU_HONEST + "\nThis dataset is proven accurate.\n"
    code, res = card.evaluate(cfg, None, card_fetcher=fetcher(
        {A11OY: A11OY_HONEST, KILL: kbad}))
    k = next(r for r in res if r["repo_id"] == KILL)
    check("killinchu 'proven accurate' -> VIOLATION",
          code == EXIT_VIOLATION and k["status"] == "violation")

    # killinchu dropped anchor -> VIOLATION.
    kdrop = KILLINCHU_HONEST.replace("third-party claim", "OSINT entry")
    code, res = card.evaluate(cfg, None, card_fetcher=fetcher(
        {A11OY: A11OY_HONEST, KILL: kdrop}))
    check("killinchu dropped 'third-party claim' anchor -> VIOLATION",
          code == EXIT_VIOLATION)

    # missing card -> ERROR (never silent green).
    code, res = card.evaluate(cfg, None, card_fetcher=fetcher(
        {A11OY: None, KILL: KILLINCHU_HONEST}))
    check("missing card -> EXIT_ERROR", code == EXIT_ERROR)

    # auth error -> ERROR.
    code, res = card.evaluate(cfg, None, card_fetcher=fetcher(
        {A11OY: AuthError("403"), KILL: KILLINCHU_HONEST}))
    check("auth error -> EXIT_ERROR", code == EXIT_ERROR)

    # unreachable -> ERROR.
    code, res = card.evaluate(cfg, None, card_fetcher=fetcher(
        {A11OY: A11OY_HONEST, KILL: Unreachable("down")}))
    check("unreachable -> EXIT_ERROR", code == EXIT_ERROR)

    print()
    if FAILURES:
        print("CARD-HONESTY SELF-TEST FAILED: %d" % len(FAILURES))
        return 1
    print("CARD-HONESTY SELF-TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
