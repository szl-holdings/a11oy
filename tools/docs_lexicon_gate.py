#!/usr/bin/env python3
"""docs_lexicon_gate.py — the docs language gate (round-10 master payload).

Wired into szl-holdings/a11oy under this name because tools/lexicon_gate.py
already exists in this repository as the round-5 HTML legacy-name gate. The
two gates scan different surfaces (HTML product surfaces vs every Markdown
file) and both run. Gate logic is byte-identical to the round-10 payload's
tools/lexicon_gate.py; only this docstring and the usage line were adapted.

Enforces the canonical lexicon (CANON section 11 house style) across every
Markdown file in the repository. Two classes of violation:

  1. Banned phrases: hype and unearned-compliance language. The canonical
     list lives ONLY here; docs reference this file by pointer, never by
     quoting the banned phrases (so the gate cannot be trivially satisfied
     by mirroring the list).
  2. Empty truth states: a line declaring a truth state with nothing after
     the colon (Zero-Bandaid Law: UNKNOWN is an audited state; an empty
     field is an oversight).

Banned phrases are matched per rendered paragraph, not per raw line, because
Markdown joins wrapped lines — a phrase split across a wrap is still banned.

Usage: python3 tools/docs_lexicon_gate.py [--root .]
Exit 0 = clean, exit 1 = violations, exit 2 = tool error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXIT_CLEAN = 0
EXIT_VIOLATIONS = 1
EXIT_ERROR = 2

# Canonical banned-phrase list. Additions require a payload-level review;
# docs must never quote these strings (they point here instead).
BANNED_REGEXES: list[tuple[str, str]] = [
    (
        r"\bEU\s+AI\s+Act\s+complian(?:t|ce)\b",
        "blanket compliance claim — approved wording: 'Article 12 logging "
        "conformance profile' (CANON Law 10)",
    ),
    (r"\bworld[\s-]?class\b", "hype adjective (CANON section 11 house style)"),
    (r"\benterprise[\s-]?grade\b", "hype adjective (CANON section 11 house style)"),
    (r"\bstate[\s-]?of[\s-]?the[\s-]?art\b", "hype adjective"),
    (r"\bcutting[\s-]?edge\b", "hype adjective"),
    (r"\bbest[\s-]?in[\s-]?class\b", "hype adjective"),
    (r"\bindustry[\s-]?leading\b", "hype adjective"),
    (r"\brevolutionary\b", "hype adjective"),
    (r"\bgame[\s-]?chang(?:ing|er)\b", "hype adjective"),
    (r"\bmilitary[\s-]?grade\b", "hype adjective"),
    (r"\bbulletproof\b", "overclaim; describe the failure model instead"),
]

TRUTH_STATE_LABEL = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?truth\s+state(?:s)?(?:\*\*)?\s*:", re.IGNORECASE
)


def _classify_truth_value(value: str) -> str | None:
    """Return a violation message, or None if the truth-state line is sound.

    Only emptiness is banned here: any declared state (VERIFIED, UNKNOWN,
    UNAVAILABLE, a surface tier, or prose) is an audited state; a blank is
    an oversight (Zero-Bandaid Law).
    """
    if not value.replace("`", "").strip():
        return (
            "empty truth state (Zero-Bandaid Law: UNKNOWN is an audited "
            "state; an empty field is an oversight)"
        )
    return None


def scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path}: unreadable ({exc})"]

    in_fence = False
    paragraph: list[str] = []
    paragraph_start = 0

    def flush_paragraph() -> None:
        if not paragraph:
            return
        joined = " ".join(part.strip() for part in paragraph)
        for pattern, message in BANNED_REGEXES:
            match = re.search(pattern, joined, flags=re.IGNORECASE)
            if match:
                findings.append(
                    f"{path}:{paragraph_start}: banned phrase "
                    f"{match.group(0)!r}: {message}"
                )

    for lineno, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            flush_paragraph()
            paragraph = []
            in_fence = not in_fence
            continue
        if in_fence:
            continue  # code blocks may legitimately contain anything
        if not line.strip():
            flush_paragraph()
            paragraph = []
            continue
        if not paragraph:
            paragraph_start = lineno
        paragraph.append(line)
        if TRUTH_STATE_LABEL.match(line):
            state_match = re.match(r"(.*?:\s*)(.*)$", line)
            if state_match:
                violation = _classify_truth_value(state_match.group(2))
                if violation:
                    findings.append(f"{path}:{lineno}: {violation}")
    flush_paragraph()
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="repo root to scan")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"lexicon_gate ERROR: {root} is not a directory", file=sys.stderr)
        return EXIT_ERROR

    # tools/_templates holds bootstrap sources; every template is scanned
    # where it lands in the rendered tree (docs/, README.md), so the
    # sources are excluded here to keep each finding reported exactly once.
    docs = sorted(
        p
        for p in root.rglob("*.md")
        if not any(
            part in {".git", "node_modules", "__pycache__", "_templates"}
            for part in p.parts
        )
    )
    findings: list[str] = []
    for doc in docs:
        findings.extend(scan_file(doc))

    print(f"lexicon_gate: scanned {len(docs)} markdown file(s) under {root}")
    if findings:
        print(f"lexicon_gate: FAIL — {len(findings)} violation(s)")
        for finding in findings:
            print(f"  {finding}")
        return EXIT_VIOLATIONS
    print("lexicon_gate: PASS")
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
