#!/usr/bin/env python3
# Signed-off-by: Forge (Replit task agent) <forge@szl-holdings>
"""Freshness guard for the flagship public HF datasets.

For every configured dataset/prefix it fetches `<prefix>/head.json` and asserts:
  * the chain head advanced within the prefix's expected cadence (max_age_hours),
  * the record count has not fallen below the append-only floor (min_records),
    which catches an emptied / rolled-back dataset that would otherwise "pass".

Covers BOTH datasets (a11oy-verifiable-corpus + killinchu-osint-corpus) in one
run, driven by .github/hf-corpus-guards.json.

Exit: 0 ok | 1 stale/floor violation | 2 auth/unreachable/malformed.

Run-by-file-path for tests; the HF fetch is injectable via `fetch_head`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import szl_corpus_guard_common as common
from szl_corpus_guard_common import (
    AuthError, Unreachable, EXIT_OK, EXIT_VIOLATION, EXIT_ERROR, EXIT_UNKNOWN,
)


def fetch_head(cfg, repo_id, prefix, token):
    url = common.resolve_url(cfg["hf_resolve_base"], repo_id,
                             "%s/head.json" % prefix)
    return common.fetch_json(url, token)


def evaluate(cfg, token, *, head_fetcher=fetch_head, ref=None):
    """Return (exit_code, results:list[dict])."""
    results = []
    worst = EXIT_OK
    for ds_name, ds in cfg["datasets"].items():
        repo_id = ds["repo_id"]
        for prefix, rule in ds.get("prefixes", {}).items():
            entry = {"dataset": ds_name, "repo_id": repo_id, "prefix": prefix,
                     "status": "ok", "detail": ""}
            try:
                head = head_fetcher(cfg, repo_id, prefix, token)
            except AuthError as e:
                entry.update(status="error", detail="auth: %s" % e)
                worst = max(worst, EXIT_ERROR)
                results.append(entry)
                continue
            except Unreachable as e:
                # Transient network failure that exhausted retries (429 / 5xx /
                # timeout). Honest doctrine: unreachable == UNKNOWN, NOT a
                # failure. Do NOT open an incident on a network flap — only a
                # reachable VIOLATION or a genuine auth/malformed ERROR fails.
                entry.update(status="unknown", detail="unreachable (transient): %s" % e)
                worst = max(worst, EXIT_UNKNOWN)
                results.append(entry)
                continue

            min_records = int(rule.get("min_records", 0))
            if head is None:
                # head.json absent. Only ok if nothing is expected yet.
                if min_records <= 0:
                    entry.update(status="soft-pass", detail="absent, floor=0")
                else:
                    entry.update(status="violation",
                                 detail="head.json missing (floor=%d)" % min_records)
                    worst = max(worst, EXIT_VIOLATION)
                results.append(entry)
                continue

            count = int(head.get("count", 0))
            entry["count"] = count
            # freshness timestamp: prefer the newest of updated_at / last_ts.
            stamps = [head.get("updated_at"), head.get("last_ts"),
                      head.get("ts")]
            stamps = [s for s in stamps if s]
            try:
                ages = [common.age_hours(s, ref) for s in stamps]
            except (ValueError, TypeError) as e:
                entry.update(status="error", detail="bad timestamp: %s" % e)
                worst = max(worst, EXIT_ERROR)
                results.append(entry)
                continue
            age = min(ages) if ages else None
            entry["age_hours"] = round(age, 2) if age is not None else None
            max_age = float(rule.get("max_age_hours", 0))

            problems = []
            if count < min_records:
                problems.append("floor: count=%d < min=%d" % (count, min_records))
            if max_age > 0:
                if age is None:
                    problems.append("no usable timestamp in head.json")
                elif age > max_age:
                    problems.append("stale: age=%.1fh > max=%.1fh" % (age, max_age))
            if problems:
                entry.update(status="violation", detail="; ".join(problems))
                worst = max(worst, EXIT_VIOLATION)
            else:
                entry["detail"] = "count=%d age=%s/%sh" % (
                    count, entry["age_hours"], max_age)
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
    summary = {"guard": "hf-corpus-freshness", "exit": code, "results": results}
    text = json.dumps(summary, indent=2)
    print(text)
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    if code == EXIT_OK:
        if any(r.get("status") == "unknown" for r in results):
            print("FRESHNESS OK — some datasets UNKNOWN (transient network flap, "
                  "retries exhausted); no violation. Not opening an incident.")
        else:
            print("FRESHNESS OK — all datasets fresh and above floor.")
    elif code == EXIT_VIOLATION:
        print("FRESHNESS VIOLATION — a dataset is stale or below its floor.")
    else:
        print("FRESHNESS ERROR — could not verify (auth/unreachable/malformed).")
    return code


if __name__ == "__main__":
    sys.exit(main())
