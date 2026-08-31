#!/usr/bin/env python3
# Signed-off-by: Forge (Replit task agent) <forge@szl-holdings>
"""Render the failing items of a corpus-guard summary JSON as markdown bullets.

Used by the guard workflows to populate the rolling-incident body + the direct
webhook alert without embedding column-0 heredocs in YAML (which terminate the
`run: |` block scalar). Auto-dispatches on the summary's `guard` field.

Usage: python3 emit_corpus_guard_findings.py <summary.json>
Prints one "- ..." line per failing item; prints nothing if all clean.
"""
from __future__ import annotations

import json
import sys


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("- (no summary path given)")
        return 0
    path = argv[0]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            s = json.load(fh)
    except Exception as e:  # noqa: BLE001 — surface, never crash the alert
        print("- (summary unreadable: %s)" % e)
        return 0

    guard = s.get("guard", "")
    if guard == "hf-corpus-freshness":
        for r in s.get("results", []):
            if r.get("status") not in ("ok", "soft-pass"):
                print("- %s/%s [%s]: %s" % (r.get("dataset"), r.get("prefix"),
                                            r.get("status"), r.get("detail")))
    elif guard == "hf-corpus-card-honesty":
        for r in s.get("results", []):
            for f in r.get("findings", []):
                print("- %s: %s" % (r.get("repo_id"), f))
    elif guard == "hf-corpus-reverify":
        rep = s.get("report", {})
        fs = rep.get("findings", [])
        if not fs and int(s.get("exit", 0)) != 0:
            print("- (re-verify script errored before a breakdown was produced)")
        for f in fs:
            print("- %s" % f)
    else:
        print("- (unknown guard summary: %r)" % guard)
    return 0


if __name__ == "__main__":
    sys.exit(main())
