#!/usr/bin/env python3
# Signed-off-by: Forge (Replit task agent) <forge@szl-holdings>
"""Negative-fixture self-test for the freshness guard. Pure stdlib, offline.

Run by file path:  python3 test_check_hf_corpus_freshness.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_hf_corpus_freshness as fresh  # noqa: E402
from szl_corpus_guard_common import (  # noqa: E402
    AuthError, Unreachable, EXIT_OK, EXIT_VIOLATION, EXIT_ERROR,
)

REF = datetime(2026, 6, 12, 12, 0, 0, tzinfo=timezone.utc)


def iso(hours_ago):
    return (REF - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def cfg_one(max_age, min_records):
    return {
        "hf_resolve_base": "https://x/{repo_id}/{path}",
        "datasets": {
            "ds": {"repo_id": "R", "prefixes": {
                "p": {"max_age_hours": max_age, "min_records": min_records}}}
        },
    }


def fetcher_for(head):
    def _f(cfg, repo_id, prefix, token):
        if isinstance(head, Exception):
            raise head
        return head
    return _f


FAILURES = []


def check(name, cond):
    if cond:
        print("  ok  - %s" % name)
    else:
        print("  FAIL- %s" % name)
        FAILURES.append(name)


def main():
    # fresh + above floor -> OK
    code, res = fresh.evaluate(cfg_one(72, 2), None,
                               head_fetcher=fetcher_for(
                                   {"count": 5, "updated_at": iso(1)}), ref=REF)
    check("fresh+above-floor is OK", code == EXIT_OK
          and res[0]["status"] == "ok")

    # stale -> VIOLATION
    code, res = fresh.evaluate(cfg_one(72, 2), None,
                               head_fetcher=fetcher_for(
                                   {"count": 5, "updated_at": iso(200)}), ref=REF)
    check("stale is VIOLATION", code == EXIT_VIOLATION
          and "stale" in res[0]["detail"])

    # below floor -> VIOLATION (catches an emptied corpus)
    code, res = fresh.evaluate(cfg_one(72, 5), None,
                               head_fetcher=fetcher_for(
                                   {"count": 1, "updated_at": iso(1)}), ref=REF)
    check("below-floor is VIOLATION", code == EXIT_VIOLATION
          and "floor" in res[0]["detail"])

    # head missing + floor>0 -> VIOLATION
    code, res = fresh.evaluate(cfg_one(72, 2), None,
                               head_fetcher=fetcher_for(None), ref=REF)
    check("missing-head+floor is VIOLATION", code == EXIT_VIOLATION)

    # head missing + floor 0 -> soft-pass OK
    code, res = fresh.evaluate(cfg_one(72, 0), None,
                               head_fetcher=fetcher_for(None), ref=REF)
    check("missing-head+no-floor soft-pass OK",
          code == EXIT_OK and res[0]["status"] == "soft-pass")

    # no usable timestamp + a cadence -> VIOLATION
    code, res = fresh.evaluate(cfg_one(72, 1), None,
                               head_fetcher=fetcher_for({"count": 3}), ref=REF)
    check("no-timestamp+cadence is VIOLATION", code == EXIT_VIOLATION)

    # no cadence (max_age 0) + above floor + no timestamp -> OK
    code, res = fresh.evaluate(cfg_one(0, 1), None,
                               head_fetcher=fetcher_for({"count": 3}), ref=REF)
    check("no-cadence+above-floor OK", code == EXIT_OK)

    # auth error -> EXIT_ERROR (never silent green)
    code, res = fresh.evaluate(cfg_one(72, 1), None,
                               head_fetcher=fetcher_for(AuthError("401")), ref=REF)
    check("auth error is EXIT_ERROR", code == EXIT_ERROR)

    # unreachable -> EXIT_ERROR
    code, res = fresh.evaluate(cfg_one(72, 1), None,
                               head_fetcher=fetcher_for(Unreachable("down")),
                               ref=REF)
    check("unreachable is EXIT_ERROR", code == EXIT_ERROR)

    print()
    if FAILURES:
        print("FRESHNESS SELF-TEST FAILED: %d" % len(FAILURES))
        return 1
    print("FRESHNESS SELF-TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
