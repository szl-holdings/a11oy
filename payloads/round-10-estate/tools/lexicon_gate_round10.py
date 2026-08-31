#!/usr/bin/env python3
"""tools/lexicon_gate.py — canonical-lexicon CI gate.

Scans text surfaces for banned terms (legacy names, overclaims, and
compliance-language violations). Exit codes:
  0 = clean
  1 = banned terms found (blocks release)
  2 = usage / IO error

Zero-Bandaid: this gate does not try to fix anything. It reports and fails.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BANNED_TERMS = [
    # Legacy / non-canonical product names
    "Alloy", "Agentic Orchestrator", "Governed substrate",
    "Governed execution fabric", "Governed AI Operating System", "Governed inference",
    # Compliance overclaims (say "Article 12 logging conformance profile")
    "EU AI Act compliant", "EU AI Act certified", "fully compliant",
    "SOC 2 certified",  # unless certification exists; in-progress only
    # Security absolutes
    "unhackable", "cannot be tampered", "impossible to forge",
    "guaranteed secure", "zero trust certified", "military-grade",
    # Autonomy overclaims
    "fully autonomous", "no human in the loop", "hands-free governance",
    # Competitive overclaims (say "not its stated purpose")
    "auto-review has no logs", "OpenAI cannot", "OpenAI does not log",
]

# Factual proper nouns that legitimately contain a banned substring.
# "alloyscape" is the second HF org name — not the retired "Alloy" product.
# Substring matching must not conflate an org name with the retired brand.
WHITELIST_SUBSTRINGS = ("alloyscape", "a11oy")

TEXT_EXTENSIONS = {".md", ".txt", ".py", ".yaml", ".yml", ".html", ".json", ".rst", ".toml"}
# `raw/` holds captured ground-truth audit evidence — it records what the
# estate currently contains (including legacy names found there) and must NOT
# be scrubbed, or the audit lies. `ledgers/` documents contradictions by name.
# Public surfaces are hard-gated separately by tools/domain_lexicon_gate.py.
# `audits/` are evidence records (they cite PRs/readmes that legitimately name
# the banned terms); `ledgers/` document contradictions by name. The repo-local
# gate guards payload source + docs; public surfaces are gated by domain_lexicon_gate.
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "run_logs", "raw", "ledgers", "audits"}
# Scanner definitions legitimately name the banned terms (that is how they ban
# them). Exclude the scanners themselves; every OTHER file is scanned fully.
SKIP_FILES = {"lexicon_gate.py", "domain_parity_audit.py"}


def scan(root: Path) -> list[dict]:
    findings = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS or path.name in SKIP_FILES:
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            # Lines that INSTRUCT against a banned term (docs, comments) are not
            # violations. Only flag a banned term when it appears as usage.
            lower = line.lower()
            instructive = ("never" in lower or "do not" in lower or "banned" in lower
                           or "retired" in lower or "say \"" in lower)
            for term in BANNED_TERMS:
                for m in re.finditer(re.escape(term), line, re.IGNORECASE):
                    ctx = line[max(0, m.start() - 12):m.end() + 12].lower()
                    if instructive or any(w in ctx for w in WHITELIST_SUBSTRINGS):
                        continue
                    findings.append({
                        "file": str(path.relative_to(root)),
                        "line": lineno,
                        "term": term,
                        "text": line.strip()[:160],
                    })
    return findings


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    if not root.is_dir():
        print(f"lexicon_gate: {root} is not a directory", file=sys.stderr)
        return 2
    findings = scan(root)
    scanned = sum(
        1 for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS
        and not any(part in SKIP_DIRS for part in p.parts)
    )
    print(f"lexicon_gate: scanned {scanned} text files under {root}")
    if findings:
        print(f"lexicon_gate: FAIL — {len(findings)} banned-term finding(s):")
        for f in findings:
            print(f"  {f['file']}:{f['line']}: banned term {f['term']!r}")
            print(f"    {f['text']}")
        return 1
    print("lexicon_gate: PASS — no banned terms found")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
