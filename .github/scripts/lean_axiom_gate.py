#!/usr/bin/env python3
"""Fail-closed Lean source + kernel axiom gate (never weakens; report-first).

Usage: python3 lean_axiom_gate.py PROJECT_DIR [--no-lake] [--exclude SUBSTR ...]
(--no-lake: standalone core-Lean files with no lakefile; uses `lean` directly.)

1. Source scan (comments and string literals stripped): any `sorry`, `admit`,
   or `axiom` declaration in a tracked *.lean file under PROJECT_DIR fails.
2. Kernel scan: every `theorem`/`lemma` found is given `#print axioms`, the file
   is elaborated by `lake env lean`, and the gate fails if (a) the number of
   reported theorems differs from the number declared, or (b) any theorem
   depends on `sorryAx` or an axiom outside {propext, Classical.choice,
   Quot.sound}.
It prints the exact theorem count and per-axiom histogram so the numbers in a
README can be checked against CI output.
"""
import os, re, subprocess, sys

ALLOWED = {"propext", "Classical.choice", "Quot.sound"}


def strip(s):
    out, i, d, n = [], 0, 0, len(s)
    while i < n:
        if s.startswith("/-", i):
            d += 1; i += 2; continue
        if d and s.startswith("-/", i):
            d -= 1; i += 2; continue
        if d:
            i += 1; continue
        if s.startswith("--", i):
            while i < n and s[i] != "\n":
                i += 1
            continue
        if s[i] == '"':
            i += 1
            while i < n and s[i] != '"':
                i += 2 if s[i] == "\\" else 1
            i += 1; out.append('""'); continue
        out.append(s[i]); i += 1
    return "".join(out)


DECL = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+|nonrec\s+)*(?:theorem|lemma)\s+([^\s:({\[]+)")
NS = re.compile(r"^\s*namespace\s+(\S+)")
END = re.compile(r"^\s*end(?:\s+(\S+))?\s*$")
SEC = re.compile(r"^\s*section\b")


def theorems(code):
    stack, names = [], []
    for line in code.split("\n"):
        m = NS.match(line)
        if m:
            stack.append(("ns", m.group(1))); continue
        if SEC.match(line):
            stack.append(("sec", None)); continue
        m = END.match(line)
        if m and stack:
            stack.pop(); continue
        m = DECL.match(line)
        if m:
            nm = m.group(1)
            ns = ".".join(x for k, x in stack if k == "ns")
            names.append((ns + "." if ns else "") + nm)
    return names


def main():
    args = sys.argv[1:]
    proj = args[0]
    cmd = ["lean"] if "--no-lake" in args else ["lake", "env", "lean"]
    excl = [args[i + 1] for i, a in enumerate(args) if a == "--exclude"]
    files = []
    for root, dirs, fs in os.walk(proj):
        dirs[:] = [d for d in dirs if d not in (".lake", "build", ".git")]
        for f in fs:
            p = os.path.join(root, f)
            if f.endswith(".lean") and f != "lakefile.lean" and not any(e in p for e in excl):
                files.append(p)
    files.sort()
    bad, total, hist = [], 0, {}
    for p in files:
        raw = open(p, encoding="utf-8", errors="replace").read()
        code = strip(raw)
        for tok, rx in (("sorry", r"\bsorry\b"), ("admit", r"\badmit\b"),
                        ("axiom", r"(?m)^\s*(?:private\s+|protected\s+)?axiom\b")):
            c = len(re.findall(rx, code))
            if c:
                bad.append(f"{p}: {c} x {tok}")
        names = theorems(code)
        if not names:
            continue
        total += len(names)
        # kernel scan: append #print axioms to a scratch copy next to the original
        scratch = p[:-5] + "__axiomgate.lean"
        with open(scratch, "w", encoding="utf-8") as fh:
            fh.write(raw + "\n" + "\n".join(f"#print axioms {n}" for n in names) + "\n")
        try:
            r = subprocess.run(cmd + [scratch], cwd=proj,
                               capture_output=True, text=True)
        finally:
            os.remove(scratch)
        out = r.stdout + r.stderr
        if r.returncode != 0:
            bad.append(f"{p}: lean elaboration failed:\n{out[-2000:]}")
            continue
        seen = set()
        for line in out.split("\n"):
            m = re.match(r"'(.+)' depends on axioms: \[(.*)\]", line)
            if m:
                seen.add(m.group(1))
                for a in [x.strip() for x in m.group(2).split(",") if x.strip()]:
                    hist[a] = hist.get(a, 0) + 1
                    if a not in ALLOWED:
                        bad.append(f"{p}: {m.group(1)} depends on {a}")
            else:
                m = re.match(r"'(.+)' does not depend on any axioms", line)
                if m:
                    seen.add(m.group(1))
        missing = sorted(set(names) - seen)
        if missing:
            bad.append(f"{p}: kernel gave no axiom report for {missing}")
    print(f"files_scanned={len(files)} theorems={total} axiom_histogram={hist}")
    if bad:
        print("GATE FAILED:")
        for b in bad:
            print("  " + b)
        sys.exit(1)
    print("GATE OK: no sorry/admit/axiom declarations; every declared theorem was kernel-reported and uses only", sorted(ALLOWED))


main()
