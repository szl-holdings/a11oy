#!/usr/bin/env python3
# Signed-off-by: Forge (Replit task agent) <forge@szl-holdings>
"""Honesty-card guard for BOTH flagship public HF dataset cards.

Fetches each dataset's README.md (the HF dataset card) and enforces that it
cannot drift into overclaiming:

  * per-LINE deny rules: a single line that contains every token in `all` and
    none of the tokens in `none` is a finding (e.g. "Theorem U is proven" on a
    line with no "conditional"). Matching is case-insensitive on the line.
  * whole-card `require` anchors: each required honesty phrase must appear
    somewhere in the card (case-insensitive). A missing anchor is a finding —
    this catches a card that was rewritten to quietly drop its honesty caveats.

Covers a11oy-verifiable-corpus + killinchu-osint-corpus from one config.

Exit: 0 honest | 1 overclaim/missing-anchor | 2 auth/unreachable/missing-card.

Pure stdlib; the card text is injectable via `card_fetcher` for the self-test.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import szl_corpus_guard_common as common
from szl_corpus_guard_common import (
    AuthError, Unreachable, EXIT_OK, EXIT_VIOLATION, EXIT_ERROR,
)


def evaluate_card(card_text, rules):
    """Return list of findings for a single card given its honesty rules."""
    findings = []
    lines = card_text.splitlines()
    low_lines = [ln.lower() for ln in lines]
    for rule in rules.get("deny", []):
        need_all = [t.lower() for t in rule.get("all", [])]
        need_none = [t.lower() for t in rule.get("none", [])]
        msg = rule.get("msg", "deny rule")
        for i, ln in enumerate(low_lines):
            if all(t in ln for t in need_all) and not any(
                    t in ln for t in need_none):
                findings.append("line %d overclaim (%s): %s"
                                % (i + 1, msg, lines[i].strip()[:120]))
    whole = card_text.lower()
    for anchor in rules.get("require", []):
        if anchor.lower() not in whole:
            findings.append("missing honesty anchor: %r" % anchor)
    return findings


def fetch_card(cfg, ds, token):
    url = common.resolve_url(cfg["hf_resolve_base"], ds["repo_id"],
                             ds.get("card_path", "README.md"))
    return common.fetch_text(url, token)


def evaluate(cfg, token, *, card_fetcher=fetch_card):
    results = []
    worst = EXIT_OK
    for ds_name, ds in cfg["datasets"].items():
        rules = ds.get("card_honesty")
        if not rules:
            continue
        entry = {"dataset": ds_name, "repo_id": ds["repo_id"], "status": "ok",
                 "findings": []}
        try:
            card = card_fetcher(cfg, ds, token)
        except AuthError as e:
            entry.update(status="error", findings=["auth: %s" % e])
            worst = max(worst, EXIT_ERROR)
            results.append(entry)
            continue
        except Unreachable as e:
            entry.update(status="error", findings=["unreachable: %s" % e])
            worst = max(worst, EXIT_ERROR)
            results.append(entry)
            continue
        if card is None:
            entry.update(status="error", findings=["card README.md missing"])
            worst = max(worst, EXIT_ERROR)
            results.append(entry)
            continue
        findings = evaluate_card(card, rules)
        if findings:
            entry.update(status="violation", findings=findings)
            worst = max(worst, EXIT_VIOLATION)
        results.append(entry)
    return worst, results


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(
        os.path.dirname(__file__), "..", ".github", "hf-corpus-guards.json"))
    ap.add_argument("--summary-out", default="")
    args = ap.parse_args(argv)

    with open(args.config, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    token = os.environ.get("HF_TOKEN") or os.environ.get("HF_ORG_TOKEN") or None

    code, results = evaluate(cfg, token)
    summary = {"guard": "hf-corpus-card-honesty", "exit": code,
               "results": results}
    text = json.dumps(summary, indent=2)
    print(text)
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    if code == EXIT_OK:
        print("CARD HONESTY OK — no overclaim, all anchors present.")
    elif code == EXIT_VIOLATION:
        print("CARD HONESTY VIOLATION — a card overclaims or dropped an anchor.")
    else:
        print("CARD HONESTY ERROR — could not fetch a card (auth/unreachable).")
    return code


if __name__ == "__main__":
    sys.exit(main())
