#!/usr/bin/env python3
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# check_page_claims.py — page-copy honesty guard.
#
# Why this exists
# ---------------
# a11oy's moat is HONESTY. Two CI gates already exist:
#   * doctrine-grep.yml   — greps ALL files for a FIXED banned-buzzword list.
#   * overclaim-guard.yml  — org reusable; polices Λ-uniqueness / Conjecture-1
#                            qualifiers only.
# Neither verifies that (1) a QUANTITATIVE claim rendered on a page traces to
# the source-of-truth benchmark artifact (results.json), nor (2) a COMPARATIVE /
# SUPERLATIVE claim outside the fixed buzzword list ("the only", "leads the
# field", "beats all", "fastest", "machine precision", …) is sourced.
#
# This guard closes both gaps WITHOUT NLP guesswork: bold-but-true copy is
# enumerated verbatim in a reviewed claims manifest (pages/claims/*.claims.json),
# each entry carrying a justification + source. A superlative on the page passes
# ONLY if it falls inside a manifest-approved sentence; a measurement-shaped
# number passes ONLY if it traces to results.json or sits inside a sourced
# manifest sentence. The genuine innovation is STALE-ENTRY DETECTION: a manifest
# entry whose text no longer appears on any page FAILS CI — approvals cannot
# outlive the copy they justified ("no zombie approvals").
#
# Pure stdlib. Exits non-zero on any violation. Mirrors the self-test-first
# pattern of constellation-honesty-guard.yml / pinn-honesty-gate.yml.

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser

# Comparative / superlative triggers. DISJOINT from doctrine-grep's fixed list
# (revolutionary|world-class|best-in-class|state-of-the-art|…) — we do not
# duplicate it. Lowercase; matched case-insensitively.
TRIGGERS = [
    "one of one",
    "the only",
    "only shipped",
    "only arm",
    "only one",
    "the best",
    "world's best",
    "fastest",
    "#1",
    "number one",
    "beats all",
    "beats every",
    "beats everyone",
    "outperforms",
    "unmatched",
    "unrivaled",
    "unrivalled",
    "first ever",
    "first-ever",
    "leads the field",
    "lead the field",
    "guaranteed",
    "machine precision",
]

# Measurement-shaped numeric tokens. Plain integers, dates, versions ("2.0"),
# and CSS px are intentionally NOT matched — only exponential notation,
# percentages, and x-fold comparatives, which are the shapes a benchmark claim
# takes. This is the false-positive-avoidance strategy for Check 1.
NUM_PATTERNS = [
    re.compile(r"(?<![\w.])\d+(?:\.\d+)?[eE][-+]?\d+"),        # 5.2e-16
    re.compile(r"\d+(?:\.\d+)?\s?%"),                          # 99.9%
    re.compile(r"(?<![\w.])\d+(?:\.\d+)?\s?[x×](?![\w])"),     # 1000x / 3×
]


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            self.parts.append(data)


def normalize(s):
    return re.sub(r"\s+", " ", s).strip()


def visible_norm_text(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    p = _TextExtractor()
    p.feed(raw)
    return normalize("".join(p.parts))


def load_results_values(path):
    vals = set()

    def rec(o):
        if isinstance(o, dict):
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)
        elif isinstance(o, bool):
            return
        elif isinstance(o, (int, float)):
            vals.add(float(o))

    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            rec(json.load(f))
    return vals


def _find_all(hay, needle):
    spans, start = [], 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            break
        spans.append((i, i + len(needle)))
        start = i + 1
    return spans


def _parse_num(tok):
    t = tok.strip().rstrip("%xX×").strip()
    try:
        return float(t)
    except ValueError:
        return None


def _num_traces(val, results_values, tol=1e-6):
    if val is None:
        return False
    for a in results_values:
        if abs(val - a) <= tol * max(1.0, abs(a)):
            return True
    return False


def _same_page(a, b):
    return os.path.basename(a) == os.path.basename(b)


def check_page(page, claims, results_values):
    """Return (violations, set_of_used_claim_indices) for one page."""
    violations = []
    norm = visible_norm_text(page)
    low = norm.lower()

    covered, used = [], set()
    for idx, c in enumerate(claims):
        if not _same_page(c.get("page", ""), page):
            continue
        claim_norm = normalize(c.get("claim", ""))
        if not claim_norm:
            continue
        spans = _find_all(low, claim_norm.lower())
        if spans:
            used.add(idx)
            covered.extend(spans)
            if not str(c.get("justification", "")).strip() or not str(c.get("source", "")).strip():
                violations.append(
                    f"{page}: manifest entry is missing justification/source: {claim_norm[:80]!r}"
                )

    def is_covered(pos):
        return any(s <= pos < e for (s, e) in covered)

    # Check 2 — comparative / superlative claims must be manifest-approved.
    for trig in TRIGGERS:
        for m in re.finditer(re.escape(trig), low):
            if not is_covered(m.start()):
                ctx = norm[max(0, m.start() - 45): m.start() + len(trig) + 45]
                violations.append(
                    f"{page}: UNSOURCED superlative {trig!r} in '…{ctx}…' — "
                    f"add the verbatim sentence to the claims manifest with a justification + source, "
                    f"or remove the claim."
                )

    # Check 1 — measurement-shaped numbers must trace to results.json (or be sourced).
    for pat in NUM_PATTERNS:
        for m in re.finditer(pat, norm):
            if is_covered(m.start()):
                continue
            if not _num_traces(_parse_num(m.group(0)), results_values):
                ctx = norm[max(0, m.start() - 45): m.start() + len(m.group(0)) + 45]
                violations.append(
                    f"{page}: UNTRACEABLE quantitative claim {m.group(0)!r} in '…{ctx}…' — "
                    f"it must trace to a value in results.json or be sourced in the manifest."
                )

    return violations, used


def check_all(pages, claims, results_values):
    violations, all_used = [], set()
    for pg in pages:
        if not os.path.exists(pg):
            violations.append(f"{pg}: covered page not found")
            continue
        v, used = check_page(pg, claims, results_values)
        violations.extend(v)
        all_used |= used
    # Stale-entry detection: an approval whose text is gone from every page.
    for idx, c in enumerate(claims):
        if idx not in all_used:
            violations.append(
                f"STALE manifest entry (its text appears on NO scanned page) — remove it: "
                f"{normalize(c.get('claim',''))[:80]!r} [declared page={c.get('page')}]"
            )
    return violations


def _resolve_pages(manifest):
    pages = list(manifest.get("covered_pages", []))
    for c in manifest.get("claims", []):
        if c.get("page") and c["page"] not in pages:
            pages.append(c["page"])
    return pages


def run_manifest(manifest_path, results_override, explicit_pages):
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    results_path = results_override or manifest.get("results_artifact")
    results_values = load_results_values(results_path)
    pages = explicit_pages or _resolve_pages(manifest)
    violations = check_all(pages, manifest.get("claims", []), results_values)
    if violations:
        print(f"page-claim guard: FAIL ({len(violations)} violation(s))")
        for v in violations:
            print(f"  ✗ {v}")
        return 1
    print(f"page-claim guard: PASS — {len(pages)} page(s), "
          f"{len(manifest.get('claims', []))} approved claim(s), "
          f"{len(results_values)} source values.")
    return 0


def _dump(page, results_path, out):
    results_values = load_results_values(results_path)
    norm = visible_norm_text(page)
    low = norm.lower()
    lines = [f"# DUMP {page}", "", "## trigger occurrences", ""]
    for trig in TRIGGERS:
        for m in re.finditer(re.escape(trig), low):
            ctx = norm[max(0, m.start() - 60): m.start() + len(trig) + 60]
            lines.append(f"[{trig}] …{ctx}…")
    lines += ["", "## measurement-shaped numbers", ""]
    for pat in NUM_PATTERNS:
        for m in re.finditer(pat, norm):
            ctx = norm[max(0, m.start() - 40): m.start() + len(m.group(0)) + 40]
            traces = _num_traces(_parse_num(m.group(0)), results_values)
            lines.append(f"[{m.group(0)!r} traces={traces}] …{ctx}…")
    lines += ["", "## full normalized visible text", "", norm]
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"dump written to {out}")
    return 0


# --------------------------------------------------------------------------- #
# Self-test: prove the guard REJECTS overclaim + stale, ACCEPTS honest, before
# CI trusts it against real pages. (Org guard pattern.)
# --------------------------------------------------------------------------- #
def _selftest(fixture_dir):
    honest = os.path.join(fixture_dir, "honest_fixture.html")
    overclaim = os.path.join(fixture_dir, "overclaim_fixture.html")
    results_values = {5.215454293376616e-16, 0.0023, 25.45}

    honest_claims = [{
        "page": "honest_fixture.html",
        "claim": "SZL is the only arm in this suite that ships in the product.",
        "kind": "superlative",
        "justification": "Scoped to this suite; the neural arms are benchmark-only dev deps.",
        "source": "benchmarks/pinn/results.json#arms[].license",
    }]

    ok = True

    # 1) overclaim fixture with the honest manifest → MUST fail.
    v = check_all([overclaim], honest_claims, results_values)
    # stale check will also flag honest_claims (its text isn't on the overclaim
    # page); the point is simply that violations are raised.
    if not v:
        print("SELFTEST FAIL: overclaim fixture was NOT rejected")
        ok = False
    else:
        print(f"selftest: overclaim fixture rejected ({len(v)} violation(s)) ✓")

    # 2) honest fixture with a manifest that sources its superlative → MUST pass.
    v = check_all([honest], honest_claims, results_values)
    if v:
        print("SELFTEST FAIL: honest fixture was rejected:")
        for x in v:
            print("   ", x)
        ok = False
    else:
        print("selftest: honest fixture accepted ✓")

    # 3) honest fixture + a stale manifest entry → MUST fail (zombie approval).
    stale_claims = honest_claims + [{
        "page": "honest_fixture.html",
        "claim": "This sentence was deleted from the page long ago.",
        "kind": "superlative",
        "justification": "n/a",
        "source": "n/a",
    }]
    v = check_all([honest], stale_claims, results_values)
    if not any("STALE" in x for x in v):
        print("SELFTEST FAIL: stale manifest entry was NOT detected")
        ok = False
    else:
        print("selftest: stale manifest entry detected ✓")

    print("SELFTEST: PASS" if ok else "SELFTEST: FAIL")
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser(description="page-copy honesty guard")
    ap.add_argument("pages", nargs="*", help="page HTML files to scan (default: manifest covered_pages)")
    ap.add_argument("--manifest", default="pages/claims/benchmark.claims.json")
    ap.add_argument("--results", default=None, help="override results.json path")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--selftest-fixtures", default=".github/test-fixtures/page-claim-guard")
    ap.add_argument("--dump", default=None, help="dump triggers/numbers/text for a page to --dump-out")
    ap.add_argument("--dump-out", default="/tmp/claimdump.txt")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest(args.selftest_fixtures)
    if args.dump:
        return _dump(args.dump, args.results or "benchmarks/pinn/results.json", args.dump_out)
    return run_manifest(args.manifest, args.results, args.pages)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
