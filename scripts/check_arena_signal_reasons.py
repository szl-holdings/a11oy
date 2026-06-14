#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Guard: every Eval Arena rejection signal must have a plain-English reason.

Why this exists
---------------
The live Eval Arena (`_a11oy_eval_run_live` in `serve.py`) attaches a list of
raw `policy_signals` to every rejected scenario (e.g.
`size-guard:payload-exceeds-1MB`,
`approval-guard:operator-approval-required-for-high-impact-action`, and the bare
threat tokens from `_A11OY_ARENA_THREATS`). The console
(`pages/console.html`) turns each raw token into a one-line, plain-English reason
via a data-driven prefix table, `ARENA_SIGNAL_REASONS`, and the
`arenaSignalReason()` lookup.

The friendly labels live in the FRONTEND while the signal tokens are produced by
the BACKEND. The two surfaces are coupled only by convention. If someone later
adds a NEW structured signal prefix in `serve.py` (say `rate-guard:...`) and
forgets to add a matching `ARENA_SIGNAL_REASONS` entry, the console silently
falls through to its catch-all and mislabels the new rejection as a generic
prompt-injection reason — a quiet honesty regression where the real reason for a
block is never shown.

What it checks
--------------
Statically (no server boot), it cross-checks the two surfaces:

  * It parses `serve.py` with the `ast` module and enumerates every STRUCTURED
    policy-signal prefix the Eval Arena code path can emit — the `prefix` of any
    `"prefix:detail"` string literal appended to `fired` inside the arena
    inspection / eval functions (`_a11oy_arena_inspect`, `_a11oy_eval_run_live`).
  * It parses the `ARENA_SIGNAL_REASONS` prefix table out of
    `pages/console.html`.
  * It FAILS if any structured arena prefix has no matching entry in the table
    (mirroring the console's own `indexOf(prefix)===0` match rule).

Bare threat tokens (the `_A11OY_ARENA_THREATS` list — e.g. `exfiltrate`,
`weapons:release`) carry no structured prefix scheme and are INTENTIONALLY mapped
to the shared "prompt-injection / data-exfiltration" reason via the console's
default fallback; they do NOT each need an individual entry. The guard treats
those literals as exempt by source, so a bare threat that happens to contain a
colon (like `weapons:release`) is never mistaken for a structured prefix.

The guard fails CLOSED: if it cannot find the arena functions, the threats
constant, or the `ARENA_SIGNAL_REASONS` table (i.e. the code shape changed so it
can no longer verify coverage), that is itself a failure — the cross-check must
be kept working, not silently skipped.

Usage
-----
  python3 scripts/check_arena_signal_reasons.py            # check the repo
  python3 scripts/check_arena_signal_reasons.py --selftest # negative-fixture tests

Exit 0 = every structured arena signal prefix has a plain-English reason.
Exit 1 = a structured prefix has no entry, or a surface could not be parsed.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

# Arena code-path functions whose `fired` mutations feed a rejection's
# `policy_signals`. Scoped deliberately: other inspection paths in serve.py
# (e.g. the sentra immune organ's `lambda-gate` / `threat-signature` verdicts)
# do NOT flow into the arena console table and must not be cross-checked here.
ARENA_FUNCS = ("_a11oy_arena_inspect", "_a11oy_eval_run_live")
THREATS_CONST = "_A11OY_ARENA_THREATS"

# A structured signal looks like "prefix:detail" where prefix is a lowercase,
# hyphenated token. This mirrors the console's prefix scheme.
_PREFIX_RE = re.compile(r"^[a-z][a-z0-9-]+$")


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def extract_arena_threats(serve_src: str) -> list[str]:
    """Return the literal string members of the _A11OY_ARENA_THREATS list."""
    tree = ast.parse(serve_src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Name) and tgt.id == THREATS_CONST
                        and isinstance(node.value, (ast.List, ast.Tuple))):
                    return [e.value for e in node.value.elts
                            if isinstance(e, ast.Constant)
                            and isinstance(e.value, str)]
    return []


def extract_structured_signals(serve_src: str) -> list[tuple[str, str, str]]:
    """Return (func, signal, prefix) for every structured "prefix:detail" string
    literal that appears inside an arena code-path function."""
    tree = ast.parse(serve_src)
    threats = set(extract_arena_threats(serve_src))
    found: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ARENA_FUNCS:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    val = sub.value
                    if ":" not in val or val in threats:
                        continue
                    prefix = val.split(":", 1)[0]
                    if not _PREFIX_RE.fullmatch(prefix):
                        continue
                    key = (node.name, val)
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append((node.name, val, prefix))
    return found


def extract_console_prefixes(console_src: str) -> list[str]:
    """Return the prefix tokens declared in the ARENA_SIGNAL_REASONS table."""
    m = re.search(r"var\s+ARENA_SIGNAL_REASONS\s*=\s*\[(.*?)\];",
                  console_src, re.S)
    if not m:
        return []
    return re.findall(r"\{\s*p\s*:\s*'([^']+)'", m.group(1))


def has_default_fallback(console_src: str) -> bool:
    """The console maps unprefixed bare threats via a default return inside
    arenaSignalReason(); confirm that catch-all still exists."""
    m = re.search(r"function\s+arenaSignalReason\s*\(", console_src)
    if not m:
        return False
    tail = console_src[m.end():m.end() + 1200]
    # The prefix loop returns `ARENA_SIGNAL_REASONS[i].label` (unquoted), so the
    # only quoted-literal return in the body is the catch-all for bare threats.
    returns = re.findall(r"return\s+'[^']+'", tail)
    return len(returns) >= 1


def analyze(serve_src: str, console_src: str) -> tuple[bool, list[str], dict]:
    """Pure cross-check. Returns (ok, problems, info)."""
    problems: list[str] = []

    threats = extract_arena_threats(serve_src)
    if not threats:
        problems.append(
            "could not find %s in serve.py (parse shape changed) — "
            "cannot verify which tokens are bare threats" % THREATS_CONST)

    structured = extract_structured_signals(serve_src)
    if not structured:
        problems.append(
            "found no structured policy signals in arena functions %s — "
            "the guard can no longer locate the signals it must cross-check "
            "(parse shape changed); failing closed" % (ARENA_FUNCS,))

    prefixes = extract_console_prefixes(console_src)
    if not prefixes:
        problems.append(
            "could not parse ARENA_SIGNAL_REASONS table from console.html "
            "(no prefixes found); failing closed")

    if not has_default_fallback(console_src):
        problems.append(
            "arenaSignalReason() has no default fallback return — bare threat "
            "tokens would render with no plain-English reason")

    prefix_set = set(prefixes)
    missing: list[tuple[str, str, str]] = []
    for func, signal, prefix in structured:
        # Mirror the console match rule: a table prefix p matches when the
        # signal starts with p (indexOf(p)===0). Direct membership of the
        # first token covers it for our "prefix:detail" grammar.
        matched = prefix in prefix_set or any(signal.startswith(p)
                                              for p in prefixes)
        if not matched:
            missing.append((func, signal, prefix))

    for func, signal, prefix in missing:
        problems.append(
            "arena signal '%s' (emitted by %s) has no ARENA_SIGNAL_REASONS "
            "entry for prefix '%s' — the console would mislabel this rejection "
            "via its catch-all. Add {p:'%s',label:'...'} to console.html."
            % (signal, func, prefix, prefix))

    info = {
        "threats": threats,
        "structured": structured,
        "console_prefixes": prefixes,
        "missing": missing,
    }
    return (not problems, problems, info)


def _check_repo() -> int:
    root = _repo_root()
    serve_path = os.path.join(root, "serve.py")
    console_path = os.path.join(root, "pages", "console.html")
    try:
        serve_src = open(serve_path, encoding="utf-8").read()
    except OSError as exc:
        print("::error::cannot read serve.py: %r" % exc, file=sys.stderr)
        return 2
    try:
        console_src = open(console_path, encoding="utf-8").read()
    except OSError as exc:
        print("::error::cannot read pages/console.html: %r" % exc,
              file=sys.stderr)
        return 2

    ok, problems, info = analyze(serve_src, console_src)

    print("Arena structured signals: %d | bare threats (default-mapped): %d | "
          "console prefixes: %s"
          % (len(info["structured"]), len(info["threats"]),
             info["console_prefixes"]))
    for func, signal, prefix in info["structured"]:
        state = "MISSING" if (func, signal, prefix) in info["missing"] else "ok"
        print("  - [%s] %-58s prefix=%-14s %s" % (state, signal, prefix, func))

    if not ok:
        for p in problems:
            print("::error::arena-signal-reasons guard: %s" % p,
                  file=sys.stderr)
        return 1

    print("\nGuard OK: every structured arena rejection signal has a "
          "plain-English ARENA_SIGNAL_REASONS entry.")
    return 0


# --------------------------------------------------------------------------
# Self-test: feed the pure analyzer fixtures and assert it REJECTS a missing
# mapping and ACCEPTS a complete one. Mirrors the org guard+self-test pattern
# (cf. check_eval_arena_negative_control.py --selftest).
# --------------------------------------------------------------------------
_GOOD_CONSOLE = """
var ARENA_SIGNAL_REASONS=[
  {p:'size-guard',label:'Blocked: request body exceeded the 1MB safety limit'},
  {p:'approval-guard',label:'Blocked: missing required operator approval'},
  {p:'threat-signature',label:'Blocked: prompt-injection pattern detected'}
];
function arenaSignalReason(sig){
  var s=String(sig||'');
  for(var i=0;i<ARENA_SIGNAL_REASONS.length;i++){ if(s.indexOf(ARENA_SIGNAL_REASONS[i].p)===0) return ARENA_SIGNAL_REASONS[i].label; }
  return 'Blocked: prompt-injection / data-exfiltration pattern detected';
}
"""

_GOOD_SERVE = '''
_A11OY_ARENA_THREATS = ["exfiltrate", "rm -rf", "weapons:release"]

def _a11oy_arena_inspect(action):
    fired = [s for s in _A11OY_ARENA_THREATS if s in action]
    if len(action) > 1_000_000:
        fired.append("size-guard:payload-exceeds-1MB")
    return (len(fired) == 0, fired)

def _a11oy_eval_run_live():
    clean, fired = _a11oy_arena_inspect("x")
    if True:
        fired = fired + ["approval-guard:operator-approval-required-for-high-impact-action"]
    return {"policy_signals": fired}
'''


def _selftest() -> int:
    failures = []

    # 1) Complete mapping → guard PASSES.
    ok, problems, _ = analyze(_GOOD_SERVE, _GOOD_CONSOLE)
    if not ok:
        failures.append("complete fixture should PASS but failed: %s" % problems)

    # 2) Negative fixture: backend gains a new structured prefix the console
    #    table does not explain → guard MUST FAIL, naming the new prefix.
    new_signal_serve = _GOOD_SERVE.replace(
        'fired.append("size-guard:payload-exceeds-1MB")',
        'fired.append("size-guard:payload-exceeds-1MB")\n'
        '    fired.append("rate-guard:too-many-requests")')
    ok, problems, info = analyze(new_signal_serve, _GOOD_CONSOLE)
    if ok:
        failures.append("missing-mapping fixture should FAIL but passed")
    elif not any("rate-guard" in p for p in problems):
        failures.append("missing-mapping fixture failed but did not name "
                        "'rate-guard': %s" % problems)

    # 3) A bare threat that contains a colon ("weapons:release") must NOT be
    #    treated as a structured prefix needing its own entry.
    structured_prefixes = {p for (_f, _s, p)
                           in extract_structured_signals(_GOOD_SERVE)}
    if "weapons" in structured_prefixes:
        failures.append("bare threat 'weapons:release' was wrongly treated as a "
                        "structured prefix")

    # 4) Removing the console default fallback → guard MUST FAIL (bare threats
    #    would otherwise have no reason).
    no_default = _GOOD_CONSOLE.replace(
        "  return 'Blocked: prompt-injection / data-exfiltration pattern detected';",
        "  return s;")
    ok, problems, _ = analyze(_GOOD_SERVE, no_default)
    # Bare threats now map to the raw token; the fallback heuristic must trip.
    if ok:
        failures.append("removed-default fixture should FAIL but passed")

    # 5) Unparseable console table → fail closed.
    ok, _problems, _ = analyze(_GOOD_SERVE, "no table here")
    if ok:
        failures.append("unparseable console should FAIL closed but passed")

    if failures:
        for f in failures:
            print("::error::self-test: %s" % f, file=sys.stderr)
        print("\nSELF-TEST FAILED (%d)" % len(failures), file=sys.stderr)
        return 1

    print("Self-test OK: analyzer rejects a missing mapping / removed default / "
          "unparseable table, accepts a complete one, and exempts bare threats.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true",
                    help="run the negative-fixture analyzer tests and exit")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    return _check_repo()


if __name__ == "__main__":
    raise SystemExit(main())
